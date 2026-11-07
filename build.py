#!/usr/bin/env python3
"""コミュニティ図鑑のサイトを作るスクリプト。

スプレッドシートの「公開用」タブをウェブに公開したCSVを読み込み、
_site/ に静的なHTMLを書き出します。標準ライブラリだけで動きます。

使い方:
  python3 build.py                     # config/site.json の csv_url から読む
  python3 build.py --csv testdata/public.csv   # 手元のCSVで試す（data/latest.csv は書き換えない）
  python3 build.py --force             # 件数が急に減っても公開する

公開を止める条件（観測所と同じ考え方）:
  - CSVを取得できない
  - 事例が0件
  - 公開中のサイトの件数より半分以上減っている（--force で無視）

ページの作り方は sitegen/ に分けてある（2026-11-07。観測所と同じ形）：
  core：設定とデータの読み込み・事例の整え方・共通の値、parts：ページの枠やカードなどの部品、
  notes：図鑑ノート、changes：新着と更新・RSS、combos：組み合わせのページ、pages：事例一覧・事例ページなど。
この build.py は入口と全体の流れ。tools/ のスクリプトは import build で sitegen の関数も使える。
"""

from sitegen.core import *  # noqa: F401,F403
from sitegen import core
from sitegen.parts import *  # noqa: F401,F403
from sitegen.notes import *  # noqa: F401,F403
from sitegen.changes import *  # noqa: F401,F403
from sitegen.combos import *  # noqa: F401,F403
from sitegen.pages import *  # noqa: F401,F403


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", help="手元のCSVファイルを使う")
    ap.add_argument("--force", action="store_true", help="件数が急に減っても公開する")
    ap.add_argument("--no-live-check", action="store_true", help="公開中サイトとの件数比較をしない")
    args = ap.parse_args()

    cfg = load_config()
    rows = load_rows(cfg, args.csv)
    if not rows:
        fail("事例が0件でした。")

    if not args.no_live_check:
        prev = live_count(cfg)
        if prev and len(rows) < prev * cfg.get("min_ratio", 0.5):
            if args.force:
                print(f"[注意] 件数が {prev} → {len(rows)} に減っていますが、--force のため公開します。")
            else:
                fail(f"件数が {prev} → {len(rows)} と大きく減っています。シートを確認してください。")

    cases = enrich(cfg, rows)
    updated = datetime.now(JST).strftime("%Y年%-m月%-d日")

    # ほかのモジュールからも同じものを見るので、core の値を書き換える（PURPOSE_ICONS は中身を入れ替える）
    core.COMMUNITY_AI = cfg.get("community_ai_url", "")
    PURPOSE_ICONS.clear()
    PURPOSE_ICONS.update(cfg.get("purpose_icons") or {})
    notes_list = load_notes(cases)
    core.NOTES_PUBLIC = bool(notes_list)

    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    shutil.copytree(os.path.join(ROOT, "assets"), os.path.join(OUT, "assets"))

    write("index.html", build_index(cfg, cases))
    og_items = copy_og_items(cases)
    og_notes_case = copy_og_notes(notes_list) if notes_list else set()  # 事例ページの「この事例を紹介している図鑑ノート」の画像
    for c in cases:
        og = f"og/{c['ID']}.png" if c["ID"] in og_items else None
        write(f"cases/{c['ID']}/index.html", build_case(cfg, c, related_rows(cfg, c, cases), og, notes_list, og_notes_case))
    write("about/index.html", build_about(cfg, cases, updated))
    today = datetime.now(JST).date()
    new, updates, has_history = find_changes(cases, load_history(), today)
    write("new/index.html", build_new(cfg, cases, new, updates, has_history, updated))
    write("feed.xml", build_feed(cfg, cases, new, updates, notes_list))
    if notes_list:
        by_id = {c["ID"]: c for c in cases}
        og_notes = copy_og_notes(notes_list)
        write("notes/index.html", build_notes_index(cfg, notes_list, og_notes))
        for n in notes_list:
            write(f"notes/{n['slug']}/index.html", build_note(cfg, n, notes_list, by_id, og_notes))
        print(f"図鑑ノート {len(notes_list)}本")
    combos = find_combos(cases)
    notes, written = load_combo_notes()
    write("combos/index.html", build_combos_index(cfg, combos, cases))
    for cb in combos:
        write(cb["path"] + "index.html", build_combo(cfg, cb, notes, written))
    missing = [cb["key"] for cb in combos if cb["key"] not in notes]
    print(f"組み合わせのページ {len(combos)}件（解説なし {len(missing)}件）")
    for k in missing:
        print(f"  解説なし：{k}")
    other = sum(1 for c in cases if c["_industry"] == "その他")
    print(f"業種のまとめ「その他」 {other}件（増えてきたら config/site.json の industry_groups を見直す）")
    print(f"ツールの札を押せるもの {sum(1 for n in TOOL_COUNTS.values() if n >= 2)}種類 / {len(TOOL_COUNTS)}種類")
    print(f"新着 {len(new)}件、更新 {len(updates)}件（履歴{'あり' if has_history else 'なし：確認日だけで判定'}）")
    write("404.html", build_404(cfg))
    write("saved/index.html", build_saved(cfg, cases))

    # 事例ページの「ほかの事例をひく」が読む小さな一覧（data.json は大きいので別に作る）
    write("pick.json", json.dumps([{"id": c["ID"], "type": c.get("種別", ""), "co": c["企業名"], "title": c["_title"],
                                    "point": shorten(c.get("工夫のポイント") or c.get("主な施策") or "", 60),
                                    "emoji": PURPOSE_ICONS.get(c["_purpose"][0], "1f4cc") if c["_purpose"] else "1f4cc"} for c in cases],
                                  ensure_ascii=False, separators=(",", ":")))
    public = [{k: v for k, v in c.items() if not k.startswith("_")} for c in cases]
    write("data.json", json.dumps({"updated": datetime.now(JST).isoformat(), "cases": public},
                                  ensure_ascii=False, indent=1))
    base = cfg["base_url"].rstrip("/")
    urls = ([f"{base}/", f"{base}/new/", f"{base}/combos/", f"{base}/about/"]
            + ([f"{base}/notes/"] + [f"{base}/notes/{n['slug']}/" for n in notes_list] if notes_list else [])
            + [f"{base}/{cb['path']}" for cb in combos] + [f"{base}/cases/{c['ID']}/" for c in cases])
    # 各ページの更新日（lastmod）：事例ページは確認日、図鑑ノートは更新日（なければ公開日）。ほかは付けない（観測所と同じ。2026-11-07）
    lastmod = {}
    for c in cases:
        k = date_key(c.get("確認日"))
        if k:
            lastmod[f"{base}/cases/{c['ID']}/"] = f"{k[:4]}-{k[4:6]}-{k[6:]}"
    for n in notes_list:
        d = n["updated"] or n["published"]
        if d:
            lastmod[f"{base}/notes/{n['slug']}/"] = d.isoformat()
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "".join(f"<url><loc>{esc(u)}</loc>" + (f"<lastmod>{lastmod[u]}</lastmod>" if u in lastmod else "") + "</url>\n" for u in urls)
          + "</urlset>\n")
    # 毎週のリンク点検の結果（tools/check_links.py）をそのまま公開する
    lc = os.path.join(ROOT, "data", "linkcheck.json")
    if os.path.exists(lc):
        shutil.copy(lc, os.path.join(OUT, "linkcheck.json"))
    # 週次の数字（tools/fetch_stats.py が毎週月曜に書く）。週次レポートが /stats.json を読む
    st = os.path.join(ROOT, "data", "stats.json")
    if os.path.exists(st):
        shutil.copy(st, os.path.join(OUT, "stats.json"))
    # AI の学習用のクローラーだけを断る（2026-11-06 黒田さんの判断）。検索用（OAI-SearchBot・Claude-SearchBot・PerplexityBot など）と
    # ふつうの検索エンジンは通す。AI の検索の答えに図鑑が出典として出る道は残すため。robots.txt はお願いで、守らない相手は止められない
    ai_training = ["GPTBot", "ClaudeBot", "anthropic-ai", "Google-Extended", "CCBot", "Applebot-Extended", "Meta-ExternalAgent", "Bytespider", "cohere-training-data-crawler"]
    blocks = "".join(f"User-agent: {b}\nDisallow: /\n\n" for b in ai_training)
    write("robots.txt", f"{blocks}User-agent: *\nAllow: /\n\nSitemap: {base}/sitemap.xml\n")
    write(".nojekyll", "")

    # 確認用に、使ったデータを残す（手元のCSVで試したときは書き換えない）
    if not args.csv:
        os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
        with open(os.path.join(ROOT, "data", "latest.csv"), "w", encoding="utf-8", newline="") as f:
            # 観測スコアは鮮度で毎日変わり、履歴（新着と更新）が読みにくくなるので残さない
            fields = [k for k in rows[0].keys() if k != "観測スコア"]
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)

    print(f"{len(cases)}件の事例でサイトを作りました（{updated}）。")


if __name__ == "__main__":
    main()
