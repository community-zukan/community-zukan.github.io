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
"""

import argparse
import csv
import html
import io
import json
import os
import re
import shutil
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "_site")
JST = timezone(timedelta(hours=9))

HINT_COL = "自社でやるならのヒント（AI生成）"
MULTI_COLS = ["目的", "活動の型"]
FACETS = [
    ("type", "種別", "種別"),
    ("purpose", "目的", "目的"),
    ("stage", "段階", "段階"),
    ("activity", "活動の型", "活動の型"),
    ("place", "場", "場"),
    ("industry", "業種", "業種グループ"),
]
STAGE_ORDER = ["立ち上げ期", "成長期", "成熟期", "転換期"]
PLACE_ORDER = ["オンライン", "オフライン", "両方"]
PURPOSE_ORDER = [
    "ビジョン浸透", "エンゲージメント", "イノベーション", "ナレッジ共有・継承",
    "部門横断", "定着・オンボーディング",
    "LTV・継続", "共創・商品開発", "サポート効率化", "口コミ・認知", "ブランド体験",
]
TYPE_LABEL = {"社内": "社内", "ファン・顧客": "ファン・顧客"}


def esc(s):
    return html.escape(s or "", quote=True)


def fail(msg):
    print(f"[公開を中止] {msg}", file=sys.stderr)
    sys.exit(1)


def load_config():
    with open(os.path.join(ROOT, "config", "site.json"), encoding="utf-8") as f:
        return json.load(f)


def fetch_text(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "community-zukan-build"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8-sig")


def load_rows(cfg, csv_path):
    if csv_path:
        with open(csv_path, encoding="utf-8-sig") as f:
            text = f.read()
    else:
        url = os.environ.get("CSV_URL") or cfg.get("csv_url", "")
        if not url.startswith("http"):
            fail("config/site.json の csv_url が設定されていません。")
        try:
            text = fetch_text(url)
        except Exception as e:  # noqa: BLE001
            fail(f"CSVを取得できませんでした: {e}")
        if text.lstrip().startswith("<"):
            fail("CSVではなくHTMLが返ってきました。公開設定を確認してください。")
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        r = {(k or "").strip(): (v or "").strip() for k, v in r.items()}
        if not r.get("ID") or not r.get("企業名"):
            continue
        if not re.fullmatch(r"[A-Za-z]\d+", r["ID"]):
            continue
        rows.append(r)
    return rows


def live_count(cfg):
    try:
        data = json.loads(fetch_text(cfg["base_url"].rstrip("/") + "/data.json", timeout=20))
        return len(data.get("cases", []))
    except Exception:  # noqa: BLE001
        return None


def split_multi(v):
    return [t.strip() for t in re.split(r"[、,，]", v or "") if t.strip()]


def industry_group(cfg, v):
    if not v:
        return ""
    for name, keys in cfg["industry_groups"]:
        if any(k in v for k in keys):
            return name
    return "その他"


def split_urls(v):
    return [u.strip() for u in re.split(r"\s+/\s+|\s+", v or "") if u.strip().startswith("http")]


def domain(u):
    m = re.match(r"https?://([^/]+)", u)
    return m.group(1).removeprefix("www.") if m else u


def shorten(s, n):
    s = re.sub(r"\s+", " ", s or "")
    return s if len(s) <= n else s[: n - 1].rstrip("、。 ") + "…"


def fmt_date(v):
    m = re.match(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", v or "")
    return f"{m.group(1)}年{int(m.group(2))}月{int(m.group(3))}日" if m else (v or "")


def enrich(cfg, rows):
    cases = []
    for r in rows:
        c = dict(r)
        c["_purpose"] = split_multi(r.get("目的"))
        c["_activity"] = split_multi(r.get("活動の型"))
        c["_industry"] = industry_group(cfg, r.get("業種"))
        c["_urls"] = split_urls(r.get("出典URL"))
        c["_title"] = r.get("コミュニティ名") or f"{r['企業名']}のコミュニティ"
        cases.append(c)
    return cases


# ---------- HTML の部品 ----------

def page(cfg, *, title, description, path, body, depth=0, og_image=None, og_type="website", jsonld=None):
    rel = "../" * depth
    full_title = f"{title}｜{cfg['name']}" if title else f"{cfg['name']}｜{cfg['subtitle']}"
    base = cfg["base_url"].rstrip("/")
    canonical = base + "/" + path
    og_image = base + "/" + (og_image or "assets/ogp.png")
    extra = ""
    for obj in jsonld or []:
        text = json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")
        extra += f'<script type="application/ld+json">{text}</script>\n'
    if cfg.get("google_site_verification"):
        extra += f'<meta name="google-site-verification" content="{esc(cfg["google_site_verification"])}">\n'
    if cfg.get("goatcounter"):
        extra += f'<script data-goatcounter="https://{esc(cfg["goatcounter"])}.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>\n'
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:title" content="{esc(full_title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:type" content="{og_type}">
<meta property="og:url" content="{esc(canonical)}">
<meta property="og:site_name" content="{esc(cfg['name'])}">
<meta property="og:locale" content="ja_JP">
<meta property="og:image" content="{esc(og_image)}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{esc(full_title)}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{rel}assets/icon.svg" type="image/svg+xml">
<link rel="icon" href="{rel}assets/favicon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="{rel}assets/apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{rel}assets/style.css">
{extra}</head>
<body>
<a class="skip" href="#main">本文へ移動</a>
<header class="site-header">
  <div class="wrap">
    <a class="brand" href="{rel or './'}">
      <span class="brand-name">{esc(cfg['name'])}</span>
      <span class="brand-sub">{esc(cfg['subtitle'])}</span>
    </a>
    <nav class="site-nav" aria-label="サイト内">
      <a href="{rel or './'}">事例一覧</a>
      <a href="{rel}about/">この図鑑について</a>
    </nav>
  </div>
</header>
<main id="main">
{body}
</main>
<footer class="site-footer">
  <div class="wrap">
    <p>{esc(cfg['name'])}｜{esc(cfg['subtitle'])}</p>
    <p>掲載内容は各出典の公開情報の要約です。詳しくは出典をご覧ください。</p>
    {operator_line(cfg)}
  </div>
</footer>
</body>
</html>
"""


def operator_line(cfg):
    parts = []
    if cfg.get("operator"):
        name = esc(cfg["operator"])
        if cfg.get("operator_url"):
            name = f'<a href="{esc(cfg["operator_url"])}">{name}</a>'
        parts.append(f"運営：{name}")
    if cfg.get("contact_url"):
        parts.append(f'<a href="{esc(cfg["contact_url"])}">掲載内容の修正のご連絡</a>')
    return f"<p>{'　'.join(parts)}</p>" if parts else ""


def type_badge(t):
    cls = "is-internal" if t == "社内" else "is-fan"
    return f'<span class="badge {cls}">{esc(TYPE_LABEL.get(t, t))}</span>'


def card(c):
    meta = [x for x in [c.get("業種"), c.get("開始年") and f"{c['開始年']}年〜", c.get("段階"), c.get("場")] if x]
    point = c.get("工夫のポイント") or c.get("主な施策")
    tags = "".join(f"<li>{esc(t)}</li>" for t in c["_purpose"])
    data = {
        "type": c.get("種別", ""),
        "purpose": "|".join(c["_purpose"]),
        "stage": c.get("段階", ""),
        "activity": "|".join(c["_activity"]),
        "place": c.get("場", ""),
        "industry": c["_industry"],
        "year": c.get("開始年", ""),
    }
    attrs = " ".join(f'data-{k}="{esc(v)}"' for k, v in data.items())
    search = " ".join(c.get(k, "") for k in ["企業名", "コミュニティ名", "業種", "ツール", "主な施策", "工夫のポイント", "目的", "活動の型"])
    return f"""<li class="card" {attrs} data-search="{esc(search.lower())}">
  <a href="cases/{esc(c['ID'])}/">
    <div class="card-top">{type_badge(c.get('種別'))}<span class="card-company">{esc(c['企業名'])}</span></div>
    <h3 class="card-title">{esc(c['_title'])}</h3>
    {f'<p class="card-meta">{" ・ ".join(esc(m) for m in meta)}</p>' if meta else ''}
    {f'<p class="card-point">{esc(shorten(point, 90))}</p>' if point else ''}
    {f'<ul class="tags">{tags}</ul>' if tags else ''}
  </a>
</li>"""


def facet_values(cases, key):
    vals = {}
    for c in cases:
        if key == "purpose":
            items = c["_purpose"]
        elif key == "activity":
            items = c["_activity"]
        elif key == "industry":
            items = [c["_industry"]] if c["_industry"] else []
        else:
            col = dict((k, col) for k, col, _ in FACETS)[key]
            items = [c.get(col)] if c.get(col) else []
        for v in items:
            vals[v] = vals.get(v, 0) + 1
    order = {"stage": STAGE_ORDER, "place": PLACE_ORDER, "purpose": PURPOSE_ORDER,
             "type": ["ファン・顧客", "社内"]}.get(key)
    if order:
        return sorted(vals.items(), key=lambda kv: (order.index(kv[0]) if kv[0] in order else 99, kv[0]))
    return sorted(vals.items(), key=lambda kv: (kv[0] == "その他", -kv[1], kv[0]))


def build_index(cfg, cases, updated):
    n_int = sum(1 for c in cases if c.get("種別") == "社内")
    n_fan = len(cases) - n_int
    filters = []
    for key, col, label in FACETS:
        opts = facet_values(cases, key)
        chips = "".join(
            f'<label class="chip"><input type="checkbox" name="{key}" value="{esc(v)}"><span>{esc(v)}<small>{n}</small></span></label>'
            for v, n in opts
        )
        filters.append(f'<fieldset class="facet" data-facet="{key}"><legend>{esc(label)}</legend><div class="chips">{chips}</div></fieldset>')
    body = f"""
<section class="hero">
  <div class="wrap">
    <h1>企業のコミュニティ運営を、<br class="sp">公開事例から知る</h1>
    <p class="lead">ファンコミュニティと社内コミュニティについて、プレスリリースや記事などの公開情報から事例を集めています。目的・段階・活動の型で絞り込んで、自社に近い事例を探せます。</p>
    <p class="stats"><span><b>{len(cases)}</b>件</span><span>ファン・顧客 {n_fan}件</span><span>社内 {n_int}件</span><span>{esc(updated)}更新</span></p>
  </div>
</section>
<section class="finder wrap" aria-label="事例を探す">
  <div class="search-row">
    <label class="visually-hidden" for="q">キーワード</label>
    <input id="q" type="search" placeholder="企業名・ツールなどで検索" autocomplete="off">
    <label class="visually-hidden" for="sort">並び順</label>
    <select id="sort">
      <option value="default">収録順</option>
      <option value="year-desc">開始年が新しい順</option>
      <option value="year-asc">開始年が古い順</option>
    </select>
  </div>
  <details class="filters" id="filters">
    <summary><span>条件で絞り込む</span><span class="active-count" id="active-count"></span></summary>
    <div class="filters-body">
      {''.join(filters)}
      <p class="filter-note">同じ項目の中では「いずれか」、項目をまたぐと「すべて」に当てはまる事例を表示します。空欄の事例は、その項目で絞り込むと表示されません。</p>
    </div>
  </details>
  <div class="result-bar">
    <p id="result-count" aria-live="polite">{len(cases)}件の事例</p>
    <button type="button" id="reset" class="link-button" hidden>条件をすべて外す</button>
  </div>
  <ul class="cards" id="cards">
    {''.join(card(c) for c in cases)}
  </ul>
  <div class="more" id="more" hidden>
    <button type="button" class="more-button" id="more-button">もっと見る</button>
  </div>
  <div class="empty" id="empty" hidden>
    <p>条件に合う事例はありませんでした。</p>
    <p>条件を減らすか、キーワードを変えてみてください。</p>
    <button type="button" class="button" id="reset2">条件をすべて外す</button>
  </div>
</section>
<script src="assets/app.js" defer></script>
"""
    base = cfg["base_url"].rstrip("/") + "/"
    website = {
        "@context": "https://schema.org", "@type": "WebSite",
        "name": cfg["name"], "alternateName": f"{cfg['name']}｜{cfg['subtitle']}",
        "url": base, "description": cfg["description"], "inLanguage": "ja",
        "publisher": {"@type": "Person", "name": cfg.get("operator", ""), "url": cfg.get("operator_url", "")},
        "potentialAction": {"@type": "SearchAction", "target": base + "?q={search_term_string}",
                            "query-input": "required name=search_term_string"},
    }
    return page(cfg, title="", description=cfg["description"], path="", body=body, jsonld=[website])


WIDE = {"規模", "ツール", "運営体制", "目的", "注意点"}


def dl_row(label, value):
    if not value:
        return ""
    cls = ' class="wide"' if label in WIDE else ""
    return f"<div{cls}><dt>{esc(label)}</dt><dd>{value}</dd></div>"


def tag_list(items):
    return '<ul class="tags">' + "".join(f"<li>{esc(t)}</li>" for t in items) + "</ul>" if items else ""


def build_case(cfg, c, related, og_image=None):
    meta = [x for x in [c.get("業種"), c.get("開始年") and f"{c['開始年']}年開始", c.get("段階"), c.get("場") and f"{c['場']}で活動"] if x]
    blocks = []
    for col, label in [("主な施策", "主な施策"), ("公開されている成果", "公開されている成果"), ("工夫のポイント", "工夫のポイント")]:
        if c.get(col):
            blocks.append(f'<section class="block"><h2>{label}</h2><p>{esc(c[col])}</p></section>')
    if c.get(HINT_COL):
        blocks.append(f"""<section class="block hint">
  <h2>自社でやるなら<span class="ai-label">AIによる提案</span></h2>
  <p>{esc(c[HINT_COL])}</p>
  <p class="hint-note">この欄は事例をもとにAIが考えた応用案です。出典に書かれている事実ではありません。</p>
</section>""")
    missing_cols = ["規模", "開始年", "公開されている成果", "運営体制", "ツール", "段階", "場"]
    missing = [m for m in missing_cols if not c.get(m)]
    overview = "".join([
        dl_row("種別", esc(c.get("種別"))),
        dl_row("業種", esc(c.get("業種"))),
        dl_row("開始年", esc(c.get("開始年") and c["開始年"] + "年")),
        dl_row("規模", esc(c.get("規模"))),
        dl_row("目的", tag_list(c["_purpose"])),
        dl_row("活動の型", tag_list(c["_activity"])),
        dl_row("段階", esc(c.get("段階"))),
        dl_row("場", esc(c.get("場"))),
        dl_row("ツール", esc(c.get("ツール"))),
        dl_row("運営体制", esc(c.get("運営体制"))),
    ])
    links = "".join(f'<li><a href="{esc(u)}" rel="noopener" target="_blank">{esc(domain(u))}</a></li>' for u in c["_urls"])
    source = f"""<section class="block source">
  <h2>出典</h2>
  {f'<ul class="source-links">{links}</ul>' if links else ''}
  <dl class="source-meta">
    {dl_row("出典の種類", esc(c.get("出典の種類")))}
    {dl_row("注意点", esc(c.get("出典の注意")))}
    {dl_row("確認日", esc(fmt_date(c.get("確認日"))))}
  </dl>
  {report_link(cfg, c)}
</section>"""
    missing_html = ""
    if missing:
        missing_html = f'<p class="missing">公開情報で確認できなかった項目：{esc("、".join(missing))}</p>'
    rel_html = ""
    if related:
        items = "".join(
            f'<li><a href="../{esc(r["ID"])}/"><span class="rel-company">{esc(r["企業名"])}</span>{esc(r["_title"])}</a></li>'
            for r in related
        )
        rel_html = f'<section class="related"><h2>近い事例</h2><ul>{items}</ul></section>'
    desc = shorten(f"{c['企業名']}の{c['_title']}。" + (c.get("工夫のポイント") or c.get("主な施策") or ""), 120)
    body = f"""
<article class="case wrap">
  <p class="crumb"><a href="../../">事例一覧</a></p>
  <header class="case-head">
    <div class="card-top">{type_badge(c.get('種別'))}<span class="card-company">{esc(c['企業名'])}</span></div>
    <h1>{esc(c['_title'])}</h1>
    {f'<p class="case-meta">{" ・ ".join(esc(m) for m in meta)}</p>' if meta else ''}
  </header>
  <div class="case-grid">
    <div class="case-main">
      {''.join(blocks)}
      {source}
    </div>
    <aside class="case-side">
      <h2 class="visually-hidden">概要</h2>
      <dl class="overview">{overview}</dl>
      {missing_html}
    </aside>
  </div>
  {rel_html}
</article>
"""
    base = cfg["base_url"].rstrip("/") + "/"
    url = f"{base}cases/{c['ID']}/"
    name = f"{c['企業名']} {c['_title']}"
    webpage = {
        "@context": "https://schema.org", "@type": "WebPage",
        "name": name, "url": url, "description": desc, "inLanguage": "ja",
        "isPartOf": {"@type": "WebSite", "name": cfg["name"], "url": base},
        "about": {"@type": "Organization", "name": c["企業名"]},
        "primaryImageOfPage": base + (og_image or "assets/ogp.png"),
    }
    if c.get("確認日") and re.match(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}", c["確認日"]):
        y, m, d = re.split(r"[-/]", c["確認日"])[:3]
        webpage["dateModified"] = f"{y}-{int(m):02d}-{int(d):02d}"
    crumbs = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "事例一覧", "item": base},
            {"@type": "ListItem", "position": 2, "name": name, "item": url},
        ],
    }
    return page(cfg, title=f"{c['企業名']} {c['_title']}", description=desc, jsonld=[webpage, crumbs],
                path=f"cases/{c['ID']}/", body=body, depth=2, og_image=og_image, og_type="article")


def report_link(cfg, c):
    if not cfg.get("contact_url"):
        return ""
    url = cfg["contact_url"]
    if cfg.get("contact_id_entry"):
        target = f"{c['ID']} {c['企業名']} {c['_title']}"
        url += "?usp=pp_url&" + urllib.parse.urlencode({cfg["contact_id_entry"]: target})
    return f'<p class="report"><a href="{esc(url)}" target="_blank" rel="noopener">この事例の誤りを知らせる</a></p>'


def find_related(c, cases, n=3):
    def score(o):
        s = 0
        s += 3 if o.get("種別") == c.get("種別") else 0
        s += 2 * len(set(o["_purpose"]) & set(c["_purpose"]))
        s += len(set(o["_activity"]) & set(c["_activity"]))
        s += 1 if o["_industry"] and o["_industry"] == c["_industry"] else 0
        return s
    others = [o for o in cases if o["ID"] != c["ID"]]
    others.sort(key=lambda o: (-score(o), o["ID"]))
    return others[:n]


def build_about(cfg, cases, updated):
    defs = [
        ("種別", "社内／ファン・顧客", "誰が集まるコミュニティか。社内は従業員（退職者のアルムナイを含む）、ファン・顧客は製品やブランドの利用者です。"),
        ("目的（社内）", "ビジョン浸透、エンゲージメント、イノベーション、ナレッジ共有・継承、部門横断、定着・オンボーディング", "企業が社内コミュニティに期待していること。出典に書かれている範囲で、複数つけています。"),
        ("目的（ファン・顧客）", "LTV・継続、共創・商品開発、サポート効率化、口コミ・認知、ブランド体験", "企業がファンコミュニティに期待していること。複数つけています。"),
        ("段階", "立ち上げ期／成長期／成熟期／転換期", "出典の時点での状態です。立ち上げ期は開始から1年程度、成長期は規模や活動が広がっている途中、成熟期は長く続いて仕組みが定着している状態、転換期は終了・統合・方針転換を指します。"),
        ("活動の型", "ナレッジ共有型、プロジェクト型、趣味親睦型", "ナレッジ共有型は学び合いや質問への回答、プロジェクト型は共創や企画、趣味親睦型は交流が中心の活動です。複数つけています。"),
        ("場", "オンライン／オフライン／両方", "主な活動の場所です。"),
        ("出典の種類", "プレスリリース／インタビュー記事／登壇資料／公式note・サイト／広告・PR記事", "広告・PR記事は、ツールを提供する企業などが作った記事です。記事中の数値は、企業側の説明として扱っています。"),
    ]
    rows = "".join(f"<tr><th scope=\"row\">{esc(a)}</th><td>{esc(b)}</td><td>{esc(d)}</td></tr>" for a, b, d in defs)
    body = f"""
<article class="prose wrap">
  <h1>この図鑑について</h1>
  <p>コミュニティ図鑑は、企業が運営するファンコミュニティと社内コミュニティの事例を、公開情報から集めたものです。コミュニティを立ち上げたい人や、運営に行き詰まっている人が、自社に近い事例を探して読めるようにしています。</p>

  <h2>載せている情報</h2>
  <p>プレスリリース、メディアの記事、登壇資料、企業の公式サイトやnoteなど、誰でも読める情報だけを使っています。本文は転載せず、要点の要約とタグ、出典へのリンクでまとめています。</p>
  <p>公開情報から分からない項目は、推測で埋めずに空欄のままにしています。たとえば規模や成果は、公表していない企業も多くあります。各事例のページには「公開情報で確認できなかった項目」を表示しています。</p>

  <h2>集め方と更新</h2>
  <p>事例の探索、出典の確認、タグづけ、掲載してよいかの判断は、AI（Claude）が決まった手順で行い、運営者がふりかえりで点検しています。新しい事例は随時追加し、サイトは毎日更新しています。最終更新は{esc(updated)}です。</p>
  <p>数値や状況は出典の時点のものです。最新の状況は、各企業の発表をご確認ください。</p>

  <h2>「自社でやるなら」の欄</h2>
  <p>事例ページの「自社でやるなら」は、事例をもとにAIが考えた応用案です。出典に書かれている事実ではないため、ほかの欄と分けて表示しています。</p>

  <h2>タグの意味</h2>
  <div class="table-wrap">
  <table class="defs">
    <thead><tr><th scope="col">項目</th><th scope="col">選択肢</th><th scope="col">意味</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  </div>

  <h2>掲載内容について</h2>
  <p>内容の誤りのお知らせや、事例のご提案は、{contact_text(cfg)}</p>
</article>
"""
    return page(cfg, title="この図鑑について", description="コミュニティ図鑑の収録ルール、集め方、タグの意味を説明しています。",
                path="about/", body=body, depth=1)


def contact_text(cfg):
    if cfg.get("contact_url"):
        return f'<a href="{esc(cfg["contact_url"])}">こちらのフォーム</a>からお送りください。'
    return "運営者までお知らせください。"


def build_404(cfg):
    body = """
<article class="prose wrap">
  <h1>ページが見つかりませんでした</h1>
  <p>URLが変わったか、事例が削除された可能性があります。</p>
  <p><a class="button" href="/">事例一覧へ戻る</a></p>
</article>
"""
    return page(cfg, title="ページが見つかりません", description="", path="404.html", body=body).replace(
        'href="assets/', 'href="/assets/').replace('src="assets/', 'src="/assets/').replace(
        'href="./"', 'href="/"').replace('href="about/"', 'href="/about/"')


def copy_og_items(cases):
    """tools/make_og.py が作った事例ごとの共有画像を /og/ に置く。ない事例は共通の画像を使う。"""
    src = os.path.join(ROOT, "og-items")
    found = set()
    if not os.path.isdir(src):
        return found
    os.makedirs(os.path.join(OUT, "og"), exist_ok=True)
    for c in cases:
        f = os.path.join(src, f"{c['ID']}.png")
        if os.path.exists(f):
            shutil.copy(f, os.path.join(OUT, "og", f"{c['ID']}.png"))
            found.add(c["ID"])
    return found


def write(path, text):
    full = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(text)


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

    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    shutil.copytree(os.path.join(ROOT, "assets"), os.path.join(OUT, "assets"))

    write("index.html", build_index(cfg, cases, updated))
    og_items = copy_og_items(cases)
    for c in cases:
        og = f"og/{c['ID']}.png" if c["ID"] in og_items else None
        write(f"cases/{c['ID']}/index.html", build_case(cfg, c, find_related(c, cases), og))
    write("about/index.html", build_about(cfg, cases, updated))
    write("404.html", build_404(cfg))

    public = [{k: v for k, v in c.items() if not k.startswith("_")} for c in cases]
    write("data.json", json.dumps({"updated": datetime.now(JST).isoformat(), "cases": public},
                                  ensure_ascii=False, indent=1))
    base = cfg["base_url"].rstrip("/")
    urls = [f"{base}/", f"{base}/about/"] + [f"{base}/cases/{c['ID']}/" for c in cases]
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "".join(f"<url><loc>{esc(u)}</loc></url>\n" for u in urls) + "</urlset>\n")
    # 毎週のリンク点検の結果（tools/check_links.py）をそのまま公開する
    lc = os.path.join(ROOT, "data", "linkcheck.json")
    if os.path.exists(lc):
        shutil.copy(lc, os.path.join(OUT, "linkcheck.json"))
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n")
    write(".nojekyll", "")

    # 確認用に、使ったデータを残す（手元のCSVで試したときは書き換えない）
    if not args.csv:
        os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
        with open(os.path.join(ROOT, "data", "latest.csv"), "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    print(f"{len(cases)}件の事例でサイトを作りました（{updated}）。")


if __name__ == "__main__":
    main()
