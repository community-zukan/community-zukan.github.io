#!/usr/bin/env python3
"""作ったサイト（_site/）を公開の前に点検する（ops-test。2026-11-07 黒田さんの採用）。

確かめること：
- data.json の事例すべてに事例ページがあり、title と共有画像（og:image）が入っていること
- og:image がサイト内の画像を指すときは、その画像が _site にあること
- サイト内のリンク（href・src）の行き先のファイルがあること
- トップに最初の24件が入り、残りの cards.html と合わせて全件になること
- sitemap.xml のURLのページがあること

1つでもおかしければ、内容を出して終了コード1で止まる（Actions では公開の前に止まる）。
使い方：python3 tools/check_site.py [_site のパス]
"""
import json
import os
import re
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "_site")
BASE = json.load(open(os.path.join(ROOT, "config", "site.json"), encoding="utf-8"))["base_url"].rstrip("/") + "/"

problems = []


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
                page_dir = SITE   # トップに差し込む断片なので、トップから見た相対の参照
            else:
                page_dir = dirpath
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

    if problems:
        print(f"サイトの点検で {len(problems)}件の問題が見つかりました。公開を止めます。")
        for p in problems[:100]:
            print("  - " + p)
        return 1
    print(f"サイトの点検：事例ページ {len(ids)}件、リンク・共有画像・サイトマップに問題はありません。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
