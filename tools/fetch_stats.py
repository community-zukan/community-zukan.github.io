#!/usr/bin/env python3
"""GoatCounter の数字を読み、週次レポート用の data/stats.json を書くスクリプト（毎週月曜の自動実行で使う）。
観測所の tools/fetch_stats.py を図鑑に合わせて写したもの（2026-11-07）。

  GOATCOUNTER_API_KEY=… python3 tools/fetch_stats.py

- 期間は日本時間の日付で区切る。「直近7日」は昨日までの7日間、「前の7日」はその前の7日間。
- 入れるもの：図鑑の目的で決めた3つの数字（事例ページの訪問数・「あとで見る」・「役に立った」。2026-11-07）、訪問数、
  上位20ページ・上位20の事例ページ、検索語の上位20（結果あり search/〇〇 と 0件 search-zero/〇〇）、「いまひとつ」の数、
  図鑑ノートの訪問数、コミュニティAIへの入口とAIの「役に立った」の記録、そのほかのクリックの記録の合計。
- 個人を特定できる情報（IPアドレス・参照元のURLなど）は入れない。GoatCounter もそれらを返さない。
- GoatCounter は「訪問数」（同じ人の同じページは1日1回）で数える。ページビューの数は持っていない。
- API キーがないときは何も書かずに終わる（終了コード0）。
"""
import datetime
import json
import os
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "stats.json")
API = "https://communityzukan.goatcounter.com/api/v0"
JST = datetime.timezone(datetime.timedelta(hours=9))
TOP = 20


def get(path, key, **params):
    url = API + path + ("?" + urllib.parse.urlencode(params, doseq=True) if params else "")
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                return json.load(res)
        except urllib.error.HTTPError as ex:
            if ex.code == 429 and attempt < 3:  # 呼びすぎ。少し待って試し直す
                time.sleep(5 * (attempt + 1))
                continue
            print("GoatCounter の API：%s → %s %s" % (path, ex.code, ex.read(300).decode("utf-8", "replace")), file=sys.stderr)
            raise


def iso(d):
    """日本時間のその日の0時を、UTC の時刻の文字列にする（GoatCounter は1時間単位）。"""
    return datetime.datetime(d.year, d.month, d.day, tzinfo=JST).astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def all_hits(key, start, end):
    """期間中のすべてのページ・イベントと、その訪問数。100件ずつ読む。"""
    hits, seen = [], []
    while True:
        params = {"start": start, "end": end, "limit": 100}
        if seen:
            params["exclude_paths"] = ",".join(str(i) for i in seen)
        data = get("/stats/hits", key, **params)
        page = data.get("hits") or []
        hits += page
        seen += [h["path_id"] for h in page]
        if not data.get("more") or not page:
            return hits
        time.sleep(1)


def summarize(key, first, last):
    """first〜last（日本時間の日付、両端を含む）の数字。"""
    start, end = iso(first), iso(last + datetime.timedelta(days=1))
    total = get("/stats/total", key, start=start, end=end)
    hits = all_hits(key, start, end)
    pages = sorted((h for h in hits if not h.get("event")), key=lambda h: -h["count"])
    events = [h for h in hits if h.get("event")]

    def ev(prefix):
        rows = sorted((h for h in events if h["path"].startswith(prefix)), key=lambda h: -h["count"])
        return rows

    def words(prefix):
        return [{"word": h["path"][len(prefix):], "count": h["count"]} for h in ev(prefix)[:TOP]]

    def by_id(prefix):
        """useful-S03 のように、名前の後ろに事例IDがつく記録の合計と上位10件"""
        rows = ev(prefix)
        return {"total": sum(h["count"] for h in rows),
                "items": [{"id": h["path"][len(prefix):].strip("/"), "count": h["count"]} for h in rows[:10]]}

    def total_of(prefix):
        return sum(h["count"] for h in ev(prefix))

    cases = [h for h in pages if h["path"].startswith("/cases/")]
    notes = [h for h in pages if h["path"].startswith("/notes/")]
    ai_entry = [h for h in ev("community-ai/") if not h["path"].startswith("community-ai/feedback/")]
    ai_feedback = ev("community-ai/feedback/")
    clicks = {}
    for name, prefix in [("出典を開く", "source-"), ("共有", "share"), ("目的から探すのタイル", "purpose/"),
                         ("組み合わせの地図のマス", "combo/"), ("近い事例", "related"), ("事例ページの札", "fact/"),
                         ("運営者のリンク集（この図鑑について）", "contact-operator/"), ("観測所へのリンク", "sister/"),
                         ("あとで見るのリストを送る・入れる", "saved-list/")]:
        clicks[name] = total_of(prefix)
    return {
        "start": first.isoformat(), "end": last.isoformat(),
        "visits": total.get("total", 0) - total.get("total_events", 0) if total.get("total_events") is not None else total.get("total", 0),
        "visits_including_events": total.get("total", 0),
        # 図鑑の目的（調べものの道具）で追う3つの数字
        "key_numbers": {
            "case_page_visits": sum(h["count"] for h in cases),
            "saved": total_of("save-"),
            "useful": total_of("useful-"),
        },
        "top_pages": [{"path": h["path"], "title": h.get("title", ""), "count": h["count"]} for h in pages[:TOP]],
        "top_cases": [{"id": h["path"].strip("/").split("/")[-1], "title": h.get("title", ""), "count": h["count"]} for h in cases[:TOP]],
        "notes_visits": [{"path": h["path"], "count": h["count"]} for h in notes],
        "search_words": words("search/"),
        "search_zero_words": words("search-zero/"),
        "saved_items": by_id("save-"),
        "useful_items": by_id("useful-"),
        "notuseful_items": by_id("notuseful-"),
        "community_ai_entry": {"total": sum(h["count"] for h in ai_entry),
                               "by_place": [{"place": h["path"][len("community-ai/"):], "count": h["count"]} for h in ai_entry[:TOP]]},
        "community_ai_feedback": [{"path": h["path"][len("community-ai/feedback/"):], "count": h["count"]} for h in ai_feedback],
        "clicks": clicks,
    }


def main():
    key = os.environ.get("GOATCOUNTER_API_KEY", "").strip()
    if not key:
        print("GOATCOUNTER_API_KEY がないので、stats.json は作りませんでした")
        return
    today = datetime.datetime.now(JST).date()
    last = today - datetime.timedelta(days=1)
    week = summarize(key, last - datetime.timedelta(days=6), last)
    prev = summarize(key, last - datetime.timedelta(days=13), last - datetime.timedelta(days=7))
    data = {"updated": datetime.datetime.now(JST).replace(microsecond=0).isoformat(),
            "note": "GoatCounter の訪問数（同じ人の同じページは1日1回）。期間は日本時間の日付で、両端を含む。visits はページの訪問数（クリックの記録を除く）。key_numbers は図鑑の目的で追う3つ（事例ページの訪問数・あとで見る・役に立った）。GoatCounter の画面の Totals はクリックの記録も含む数で、visits_including_events と同じ。",
            "this_week": week, "previous_week": prev}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("stats.json：%s〜%s 訪問 %d（前の7日 %d）" % (week["start"], week["end"], week["visits"], prev["visits"]))


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as ex:
        print("GoatCounter の API でエラーになりました（%s）。キーの権限（Read statistics）を確かめてください" % ex.code, file=sys.stderr)
        sys.exit(1)
