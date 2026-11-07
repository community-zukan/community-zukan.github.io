#!/usr/bin/env python3
"""作ったサイト（_site/）を公開の前に点検する（ops-test。2026-11-07 黒田さんの採用）。

確かめること：
- data.json の事例すべてに事例ページがあり、title と共有画像（og:image）が入っていること
- og:image がサイト内の画像を指すときは、その画像が _site にあること
- サイト内のリンク（href・src）の行き先のファイルがあること
- トップに最初の24件が入り、残りの cards.html と合わせて全件になること
- sitemap.xml のURLのページがあること

1つでもおかしければ、内容を出して終了コード1で止まる（Actions では公開の前に止まる）。

このほか、h1 が1つか・見出しの段が飛んでいないか（h2 の次がいきなり h4 など）・画像に alt があるか・同じ id が
1ページに2つないかも確かめる（観測所の点検から。2026-11-07）。こちらは読み上げなどの使いやすさの問題なので公開は止めず、
--report を付けたときに報告のファイルを書く（Actions はこれを Issue にする）。

使い方：python3 tools/check_site.py [--report site-report.md] [_site のパス]
"""
import collections
import html.parser
import json
import os
import re
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARGS = sys.argv[1:]
REPORT = None
if "--report" in ARGS:
    i = ARGS.index("--report")
    REPORT = ARGS[i + 1]
    del ARGS[i:i + 2]
SITE = ARGS[0] if ARGS else os.path.join(ROOT, "_site")
MAX_SHOW = 30
BASE = json.load(open(os.path.join(ROOT, "config", "site.json"), encoding="utf-8"))["base_url"].rstrip("/") + "/"

problems = []
soft = collections.defaultdict(list)   # 公開は止めず、Issue で知らせるもの


class Outline(html.parser.HTMLParser):
    """見出し・id・alt を集める"""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.headings, self.ids, self.no_alt = [], [], 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.headings.append(int(tag[1]))
        if a.get("id"):
            self.ids.append(a["id"])
        if tag == "img" and "alt" not in a:
            self.no_alt += 1


def soft_checks(page, rel):
    o = Outline()
    o.feed(read(page))
    h1 = o.headings.count(1)
    if h1 != 1 and not rel.endswith("404.html"):
        soft["h1 が1つでないページ"].append(f"{rel}（{h1}個）")
    for a, b in zip(o.headings, o.headings[1:]):
        if b > a + 1:
            soft["見出しの段が飛んでいるページ"].append(f"{rel}（h{a} の次が h{b}）")
            break
    dup = [i for i, n in collections.Counter(o.ids).items() if n > 1]
    if dup:
        soft["同じ id が2つ以上あるページ"].append(f"{rel}（{'、'.join(dup[:5])}）")
    if o.no_alt:
        soft["alt のない画像があるページ"].append(f"{rel}（{o.no_alt}枚）")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def target_exists(page_dir, ref):
    """サイト内の参照（相対・/ 始まり・BASE 始まり）の行き先があるか。外へのリンクや # だけのものは確かめない（True）。"""
    ref = html_unescape(ref)
    if ref.startswith(BASE):
        ref = "/" + ref[len(BASE):]
    if re.match(r"^[a-z]+:", ref) or ref.startswith("//") or ref.startswith("#") or not ref:
        return True
    path = urllib.parse.unquote(ref.split("#")[0].split("?")[0])
    if not path:
        return True
    full = os.path.join(SITE, path.lstrip("/")) if path.startswith("/") else os.path.normpath(os.path.join(page_dir, path))
    if os.path.isdir(full):
        full = os.path.join(full, "index.html")
    return os.path.exists(full)


def html_unescape(s):
    return s.replace("&amp;", "&").replace("&quot;", '"').replace("&#x27;", "'")


def write_report():
    total = sum(len(v) for v in soft.values())
    if total:
        print(f"直したほうがよいところ（公開は止めない）：{total}件" + "".join(f"\n  {k} {len(v)}件" for k, v in soft.items()))
    if not REPORT:
        return
    if os.path.isfile(REPORT):
        os.remove(REPORT)
    if not total:
        return
    lines = [f"毎日の自動更新で、作ったサイトを点検しました。直したほうがよいところが {total}件ありました。サイトの公開は止めていません。", ""]
    for kind, rows in soft.items():
        lines += [f"## {kind}（{len(rows)}件）", ""]
        lines += ["- " + r for r in rows[:MAX_SHOW]]
        if len(rows) > MAX_SHOW:
            lines.append(f"- ほか {len(rows) - MAX_SHOW}件")
        lines.append("")
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    if not os.path.isdir(SITE):
        print(f"{SITE} がありません")
        return 1
    data = json.load(open(os.path.join(SITE, "data.json"), encoding="utf-8"))
    ids = [c.get("ID") for c in data["cases"]]

    # 事例ページ
    for cid in ids:
        page = os.path.join(SITE, "cases", cid, "index.html")
        if not os.path.exists(page):
            problems.append(f"事例ページがない：{cid}")
            continue
        t = read(page)
        title = re.search(r"<title>([^<]*)</title>", t)
        if not title or not title.group(1).strip():
            problems.append(f"title が空：{cid}")
        og = re.search(r'<meta property="og:image" content="([^"]+)"', t)
        if not og:
            problems.append(f"共有画像の指定がない：{cid}")
        elif not target_exists(os.path.dirname(page), og.group(1)):
            problems.append(f"共有画像のファイルがない：{cid} {og.group(1)}")

    # トップの件数
    index = read(os.path.join(SITE, "index.html"))
    first = index.count('<li class="card" ')
    rest_path = os.path.join(SITE, "cards.html")
    rest = read(rest_path).count('<li class="card" ') if os.path.exists(rest_path) else 0
    if first + rest != len(ids):
        problems.append(f"トップのカードが全件と合わない：HTML {first}件＋cards.html {rest}件、事例 {len(ids)}件")
    if first > 24:
        problems.append(f"トップのHTMLに24件より多いカードがある：{first}件")

    # サイト内のリンク
    broken = {}
    for dirpath, _, files in os.walk(SITE):
        for name in files:
            if not name.endswith(".html"):
                continue
            page = os.path.join(dirpath, name)
            if name == "cards.html":
                # トップ（と /saved/）に差し込むカードの断片。置き場所のフォルダから見た相対の参照なので、そのまま確かめる
                page_dir = dirpath
            else:
                page_dir = dirpath
                soft_checks(page, os.path.relpath(page, SITE))
            for ref in re.findall(r'(?:href|src)="([^"]+)"', read(page)):
                if not target_exists(page_dir, ref):
                    broken.setdefault(os.path.relpath(page, SITE), set()).add(ref)
    for page, refs in sorted(broken.items()):
        for ref in sorted(refs)[:5]:
            problems.append(f"リンク先がない：{page} → {ref}")

    # サイトマップ
    sitemap = read(os.path.join(SITE, "sitemap.xml"))
    for url in re.findall(r"<loc>([^<]+)</loc>", sitemap):
        if not target_exists(SITE, url):
            problems.append(f"サイトマップのページがない：{url}")

    write_report()
    if problems:
        print(f"サイトの点検で {len(problems)}件の問題が見つかりました。公開を止めます。")
        for p in problems[:100]:
            print("  - " + p)
        return 1
    print(f"サイトの点検：事例ページ {len(ids)}件、リンク・共有画像・サイトマップに問題はありません。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
