#!/usr/bin/env python3
"""公開中の事例の出典URLが開けるかを確かめ、結果を data/linkcheck.json に書くスクリプト（毎週の自動点検で使う）。
あしたの転機観測所の tools/check_links.py を図鑑向けに写したものです。

  python3 tools/check_links.py [report.md]               # 公開用CSVから読む
  python3 tools/check_links.py --csv testdata/public.csv  # 手元のCSVで試す

- 対象：公開用CSVの「出典URL」列（1件に2つまで）。
- 結果は 正常／移転／拒否／要確認 の4つに分ける。linkcheck.json の items には「正常」以外だけを入れる。
- MarkeZine や日経のように自動アクセスを断るサイト（config/site.json の linkcheck_refusing_hosts）は、
  開けなかったときに「要確認」ではなく「拒否」に分ける。
- 「要確認」があったときは、Issue 用の report.md も書く（引数で指定したとき）。
- スプレッドシートやサイトの掲載は変えない。直すかどうかは、データ側の定期実行が linkcheck.json を読んで判断する。
- 1回ですべてを開かない（観測所と同じ。2026-11-07）。毎回確かめるのは、まだ一度も確かめていないもの・前回「正常」以外だったもの・
  残りのうち確かめた日が古いもの（全体の4分の1）。4週で全体を一巡する。確かめた日と結果は data/linkcheck_seen.json に残す。
- 時間の上限（BUDGET 秒）を過ぎたら新しく開くのをやめ、そこまでの結果を保存する。残りは次回に回る。
- linkcheck.json の items と summary は、今回確かめていないものも含めた「最後に確かめた結果」。
"""
import argparse
import collections
import concurrent.futures
import datetime
import http.cookiejar
import json
import os
import socket
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import build  # noqa: E402  CSVの取得と設定は build.py と同じものを使う

OUT = os.path.join(ROOT, "data", "linkcheck.json")
SEEN = os.path.join(ROOT, "data", "linkcheck_seen.json")  # URLごとの、最後に確かめた日・結果
BUDGET = int(os.environ.get("LINKCHECK_BUDGET", "1200"))  # 新しく開くのをやめるまでの秒数（取り直しは含まない）
RETRY_BUDGET = 300                                       # 1回の取り直しに使ってよい秒数
ROTATION = 4                                             # 何週で全体を一巡するか
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
           "Accept-Language": "ja,en-US;q=0.8,en;q=0.6"}
TIMEOUT = 15          # 1件あたりの待ち時間（秒）
RETRY_TIMEOUT = 30    # 取り直すときの待ち時間（秒）。応答の遅いサイトのために長めにする
WORKERS = 4           # 同時に確かめるドメインの数（相手に負担をかけないよう少なめ）
DOMAIN_GAP = 2.0      # 同じドメインに続けてアクセスするときの間隔（秒）
RETRY_WAITS = [60, 180]  # 「応答なし」「404」などを取り直すまでの待ち時間（秒）。この回数だけ取り直す
REFUSED = {401, 403, 405, 406, 429, 451, 999}  # 自動アクセスを断るときによく返る番号

_last_access = {}
_lock = threading.Lock()


def host_of(url):
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def wait_for_domain(host):
    """同じドメインへの連続アクセスに間をあける。"""
    while True:
        with _lock:
            last = _last_access.get(host, 0)
            now = time.monotonic()
            if now - last >= DOMAIN_GAP:
                _last_access[host] = now
                return
        time.sleep(DOMAIN_GAP - (now - last))


class Redirects(urllib.request.HTTPRedirectHandler):
    """308（恒久的な転送）もたどる。"""
    def http_error_308(self, req, fp, code, msg, headers):
        return self.http_error_302(req, fp, 307, msg, headers)

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, 307 if code == 308 else code, msg, headers, newurl)
        if new is not None and req.get_method() == "HEAD":
            new.method = "HEAD"
        return new


def to_ascii(url):
    """日本語などを含むURLを、送れる形（パーセントエンコード）にする。すでにエンコード済みの部分はそのまま。"""
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname.encode("idna").decode("ascii") if parts.hostname else ""
    netloc = host + (":%d" % parts.port if parts.port else "")
    safe = "/:@!$&'()*+,;=%-._~"
    return urllib.parse.urlunsplit((parts.scheme, netloc, urllib.parse.quote(parts.path, safe=safe),
                                    urllib.parse.quote(parts.query, safe=safe + "?"), ""))


def request(url, method, timeout=TIMEOUT):
    """(HTTPの番号, 最終的なURL) を返す。つながらないときは例外。転送はたどり、Cookie を使う転送にも対応する。"""
    wait_for_domain(host_of(url))
    opener = urllib.request.build_opener(Redirects, urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
                                         urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    req = urllib.request.Request(to_ascii(url), headers=HEADERS, method=method)
    with opener.open(req, timeout=timeout) as res:
        if method == "GET":
            res.read(4096)
        return res.status, res.geturl()


def check_once(url, timeout=TIMEOUT):
    """1回確かめる。HEAD で失敗したら GET で試し直す。(status, http_status, final_url, note, retryable) を返す。
    retryable が真のもの（応答なし・404・サーバーの不具合など）は、時間をおいて取り直す。"""
    code, final, note = None, "", ""
    for method in ("HEAD", "GET"):
        try:
            code, final = request(url, method, timeout)
            break
        except urllib.error.HTTPError as ex:
            code, final, note = ex.code, "", ""
            if method == "HEAD":
                continue  # HEAD を受け付けないサイトがあるので GET で試し直す
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, ssl.SSLError) as ex:
            reason = getattr(ex, "reason", ex)
            if isinstance(reason, socket.gaierror):
                return "要確認", None, "", "ドメインが見つかりません", False
            if method == "HEAD":
                continue
            if isinstance(reason, (socket.timeout, TimeoutError)) or isinstance(ex, (socket.timeout, TimeoutError)):
                return "要確認", None, "", "応答がありません", True
            return "要確認", None, "", "つながりません（%s）" % reason, True
        except Exception as ex:  # 予想外の失敗も結果に残す
            if method == "HEAD":
                continue
            return "要確認", None, "", "確認できませんでした（%s）" % ex, True
    if code is None:
        return "要確認", None, "", "応答がありません", True
    if 200 <= code < 300:
        if final and host_of(final) != host_of(url):
            return "移転", code, final, "開き先のドメインが変わっています", False
        return "正常", code, "", "", False
    if code in REFUSED:
        return "拒否", code, "", "自動アクセスを断られました（壊れているとは限りません）", False
    if code in (404, 410):
        # ブラウザでは開けるのに、自動のアクセスにだけ404を返すサイトがあるので、取り直してから決める
        return "要確認", code, "", "ページが見つかりません", True
    if code >= 500:
        return "要確認", code, "", "サーバーの不具合", True
    return "要確認", code, "", "想定外の応答です", False


def refusing(url, hosts):
    h = host_of(url)
    return any(h == x or h.endswith("." + x) for x in hosts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("report", nargs="?", help="要確認があったときに Issue 用の本文を書くファイル")
    ap.add_argument("--csv", help="手元のCSVファイルを使う")
    args = ap.parse_args()
    cfg = build.load_config()
    hosts = [h.lower() for h in cfg.get("linkcheck_refusing_hosts", [])]
    cases = build.enrich(cfg, build.load_rows(cfg, args.csv))
    targets = [(c["ID"], c["企業名"], c["_title"], u) for c in cases for u in c["_urls"]]

    key = lambda t: t[0] + " " + t[3]
    targets = list({key(t): t for t in targets}.values())  # 同じ事例の同じURLは1回だけ
    try:
        with open(SEEN, encoding="utf-8") as f:
            seen = json.load(f)
    except (OSError, ValueError):
        seen = {}
    # 今回確かめるもの：一度も確かめていない・前回「正常」以外 は必ず。残りは確かめた日が古い順に全体の4分の1
    must, rest = [], []
    for t in targets:
        old = seen.get(key(t))
        (must if not old or old.get("status") != "正常" else rest).append(t)
    rest.sort(key=lambda t: (seen[key(t)].get("date", ""), t[0]))
    quota = -(-len(targets) // ROTATION)
    todo = must + rest[:quota]

    def run(batch, budget, timeout=TIMEOUT):
        """ドメインごとにまとめ、ドメイン単位で並べて確かめる（同じドメインは順番に、間をあけて）。時間を過ぎたら開くのをやめる。"""
        deadline = time.monotonic() + budget
        by_host = collections.defaultdict(list)
        for t in batch:
            by_host[host_of(t[3])].append(t)
        out = {}

        def work(group):
            done = []
            for t in group:
                if time.monotonic() > deadline:
                    break
                done.append((key(t), check_once(t[3], timeout)))
            return done
        with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
            for results in pool.map(work, by_host.values()):
                out.update(dict(results))
        return out

    started = time.monotonic()
    results = run(todo, BUDGET)
    # 応答なし・404・サーバーの不具合だったものは、時間をおいて取り直す。開けたらその結果を使う
    for i, wait in enumerate(RETRY_WAITS, 1):
        retry = [t for t in todo if key(t) in results and results[key(t)][4]]
        if not retry:
            break
        print("取り直し %d回目：%d件（%d秒待ちます）" % (i, len(retry), wait))
        time.sleep(wait)
        results.update(run(retry, RETRY_BUDGET, RETRY_TIMEOUT))

    today = datetime.datetime.now(build.JST).date().isoformat()
    for t in todo:
        if key(t) in results:
            status, code, final, note, again = results[key(t)]
            if status == "要確認" and refusing(t[3], hosts):
                status, note = "拒否", "自動アクセスを断るサイトです（壊れているとは限りません）"
            elif status == "要確認" and again:
                note += "（時間をおいて%d回取り直しても同じでした）" % len(RETRY_WAITS)
            seen[key(t)] = {"date": today, "status": status, "http_status": code, "final_url": final, "note": note}
    listed = {key(t) for t in targets}
    seen = {k: v for k, v in sorted(seen.items()) if k in listed}  # 公開から外れたものは忘れる
    with open(SEEN, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=0)
        f.write("\n")

    summary = {"正常": 0, "移転": 0, "拒否": 0, "要確認": 0}
    items, unchecked = [], 0
    for cid, company, title, url in targets:
        rec = seen.get(cid + " " + url)
        if not rec:
            unchecked += 1
            continue
        status = rec["status"]
        if status == "要確認" and refusing(url, hosts):   # 拒否に分けるサイトが後から足されたとき
            status = "拒否"
        summary[status] += 1
        if status != "正常":
            items.append({"id": cid, "company": company, "title": title, "url": url, "status": status,
                          "http_status": rec.get("http_status"), "final_url": rec.get("final_url", ""), "note": rec.get("note", ""),
                          "checked": rec["date"]})
    order = {"要確認": 0, "移転": 1, "拒否": 2}
    items.sort(key=lambda it: (order[it["status"]], it["id"]))
    now = datetime.datetime.now(build.JST).replace(microsecond=0)
    data = {"checked_at": now.isoformat(), "cases": len(cases), "urls": len(targets),
            "summary": summary,
            "this_run": {"checked": sum(1 for t in todo if key(t) in results), "planned": len(todo),
                         "minutes": round((time.monotonic() - started) / 60, 1)},
            "unchecked": unchecked, "items": items}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("点検：今回 %d件（予定 %d件、%.1f分）、まだ一度も確かめていないもの %d件。最後に確かめた結果（URL %d件）：%s"
          % (data["this_run"]["checked"], len(todo), data["this_run"]["minutes"], unchecked, len(targets),
             "、".join("%s %d" % kv for kv in summary.items())))

    need = [it for it in items if it["status"] == "要確認"]
    if args.report and need:
        base = cfg["base_url"].rstrip("/")
        lines = ["公開中の事例の出典URLを %s に自動で開いて確かめました（今回 %d件。残りは週ごとに順番に確かめます）。" % (build.fmt_date(now.strftime("%Y/%m/%d")), data["this_run"]["checked"]),
                 "結果：" + "、".join("%s %d件" % kv for kv in summary.items()),
                 "くわしい結果は %s/linkcheck.json でも見られます。サイトの掲載は自動では変えていません。" % base, "",
                 "## 要確認（ブラウザで開いて確かめてください）", "",
                 "自動の点検は GitHub のサーバーから開くため、ブラウザでは見られるのに「見つかりません」と出るサイトもあります。", "",
                 "| ID | 企業名 | URL | 内容 | 確かめた日 |", "|---|---|---|---|---|"]
        lines += ["| %s | %s | %s | %s | %s |" % (it["id"], it["company"], it["url"], it["note"], it["checked"]) for it in need]
        with open(args.report, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
