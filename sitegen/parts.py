"""HTML の部品：ヘッダー・フッターつきのページの枠、メニュー、カード、絞り込みの値、コミュニティAIへのリンクなど。"""

from .core import *  # noqa: F401,F403
from . import core


# ---------- HTML の部品 ----------


# ヘッダーのロゴ（ファビコンと同じ絵：本を開いた絵文字「📖」。Noto Emoji の絵を assets/icon.svg に置いている）
def logo_mark(rel):
    return f'<img class="logo-mark" src="{rel}assets/icon.svg?v={ver("icon.svg")}" alt="" width="30" height="30">'


def nav_links(rel, path):
    """ヘッダーのメニュー。いま開いているページには aria-current を付ける。
    「この図鑑について」はフッターにあるので、メニューには入れない（2026-11-06 黒田さんの判断）。"""
    items = [("", "事例一覧"), ("new/", "新着"), ("combos/", "組み合わせ")]
    if core.NOTES_PUBLIC:
        items.append(("notes/", NOTES_LABEL))
    out = []
    for href, label in items:
        here = (path == href) if href == "" else path.startswith(href)
        cur = ' aria-current="page"' if here else ""
        out.append(f'<a href="{(rel + href) or "./"}"{cur}>{label}</a>')
        if href == "notes/" or (href == "combos/" and not core.NOTES_PUBLIC):
            ai = ai_link("コミュニティAIに相談", "nav")
            if ai:
                out.append(ai)
    return "\n      ".join(out)




def ai_link(label, where, anchor="", cls=""):
    """コミュニティAI（図鑑の外、Claude のアーティファクト）へのリンク。新しいタブで開き（↗ は style.css が付ける）、
    どこから移ったかを GoatCounter の community-ai/{where} で数える。観測所の転機AIへのリンク（ai_link）を写したもの。"""
    if not core.COMMUNITY_AI:
        return ""
    href = core.COMMUNITY_AI + (f"#{anchor}" if anchor else "")
    cls_attr = f' class="{cls}"' if cls else ""
    return (f'<a{cls_attr} href="{esc(href)}" target="_blank" rel="noopener" '
            f'data-goatcounter-click="community-ai/{esc(where)}" data-goatcounter-title="コミュニティAI（{esc(where)}）">{label}'
            f'<span class="visually-hidden">（新しいタブで開く）</span></a>')


def ai_line(rel, label, where, anchor=""):
    """1行の入口（💬 の絵＋リンク）。"""
    a = ai_link(label, where, anchor)
    if not a:
        return ""
    return (f'<p class="ai-line"><img src="{rel}assets/emoji/1f4ac.png" alt="" width="18" height="18">{a}</p>')


EXAMPLES_SHOWN = 5  # 検索の例を一度に出す数


def search_examples(cfg):
    """検索欄の下に小さく並べる「検索の例」。

    候補は config/site.json の search_examples（運営が選んだ言葉）と searched_words（実際に検索された言葉。
    週次レポートで GoatCounter の search/ から足す）。読み込むたびに app.js が候補から5つをランダムに選び、
    今のデータで1件も見つからない言葉は出さない。JavaScript が動かないときは search_examples の先頭5つを出す。
    """
    picked = [w for w in (cfg.get("search_examples") or []) if w]
    searched = [w for w in (cfg.get("searched_words") or []) if w and w not in picked]
    if not picked and not searched:
        return ""
    first = (picked + searched)[:EXAMPLES_SHOWN]
    links = "".join(f'<a href="?q={urllib.parse.quote(w)}" data-q="{esc(w)}">{esc(w)}</a>' for w in first)
    data = json.dumps({"picked": picked, "searched": searched, "shown": EXAMPLES_SHOWN}, ensure_ascii=False).replace("</", "<\\/")
    return (f'<p class="examples" id="examples"><span>検索の例</span>{links}</p>'
            f'<script type="application/json" id="examples-data">{data}</script>')


def page(cfg, *, title, description, path, body, depth=0, og_image=None, og_type="website", jsonld=None, noindex=False):
    rel = "../" * depth
    full_title = f"{title}｜{cfg['name']}" if title else f"{cfg['name']}｜{cfg['subtitle']}"
    base = cfg["base_url"].rstrip("/")
    canonical = base + "/" + path
    og_image = base + "/" + (og_image or "assets/ogp.png")
    extra = ""
    for obj in jsonld or []:
        # 「<」をすべて置き換え、どんな文字が来ても埋め込みが壊れないようにする（観測所と同じ。2026-11-07）
        text = json.dumps(obj, ensure_ascii=False).replace("<", "\\u003c")
        extra += f'<script type="application/ld+json">{text}</script>\n'
    if noindex:
        extra += '<meta name="robots" content="noindex">\n'
    if cfg.get("google_site_verification"):
        extra += f'<meta name="google-site-verification" content="{esc(cfg["google_site_verification"])}">\n'
    if cfg.get("goatcounter"):
        # count.js は GoatCounter の公式のものに手を加え、URLの「?」以降は来た元（ref・utm）だけを送る（観測所と同じ。2026-11-07）
        count_v = ver("count.js")
        extra += f'<script data-goatcounter="https://{esc(cfg["goatcounter"])}.goatcounter.com/count" async src="{rel}assets/count.js?v={count_v}"></script>\n'
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
<link rel="icon" href="{rel}assets/icon.svg?v={ver('icon.svg')}" type="image/svg+xml">
<link rel="icon" href="{rel}assets/favicon-32.png?v={ver('favicon-32.png')}" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="{rel}assets/apple-touch-icon.png?v={ver('apple-touch-icon.png')}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Zen+Kaku+Gothic+New:wght@500;700&display=swap" rel="stylesheet">
<script>document.documentElement.classList.add("js");try{{if(localStorage.getItem("zukan-theme")==="dark")document.documentElement.setAttribute("data-theme","dark")}}catch(e){{}}</script>
<link rel="stylesheet" href="{rel}assets/style.css?v={ver('style.css')}">
<script src="{rel}assets/site.js?v={ver('site.js')}" defer></script>
<link rel="alternate" type="application/rss+xml" title="{esc(cfg['name'])}｜新着" href="{esc(base)}/feed.xml">
{extra}</head>
<body>
<a class="skip" href="#main">本文へ移動</a>
<header class="site-header">
  <div class="wrap header-inner">
    <a class="logo" href="{rel or './'}">{logo_mark(rel)}<span class="logo-name">{esc(cfg['name'])}</span></a>
    <nav class="global-nav" id="global-nav" aria-label="サイト内">
      {nav_links(rel, path)}
    </nav>
    <a class="icon-btn header-saved" id="header-saved" href="{rel}saved/" title="あとで見る"{' aria-current="page"' if path == "saved/" else ""}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3h12v18l-6-4-6 4z"/></svg><span class="visually-hidden">あとで見る</span><span class="count" id="header-saved-count"></span></a>
    <a class="icon-btn" id="header-search-btn" href="{rel or './'}#q" aria-controls="header-search" aria-expanded="false"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg><span class="visually-hidden">検索</span></a>
    <button type="button" class="icon-btn menu-btn" id="menu-btn" aria-controls="global-nav" aria-expanded="false"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/></svg><span class="visually-hidden">メニュー</span></button>
  </div>
  <form class="wrap header-search" id="header-search" action="{rel or './'}" role="search" hidden>
    <input type="search" name="q" aria-label="キーワードで探す" placeholder="企業名・ツール・施策などで探す">
    <button type="submit" class="button">探す</button>
  </form>
</header>
<main id="main">
{body}
</main>
<footer class="site-footer">
  <div class="wrap">
    <p class="footer-name">{esc(cfg['name'])}</p>
    <p>{esc(cfg['subtitle'])}。掲載内容は各出典の公開情報の要約です。詳しくは出典をご覧ください。</p>
    {operator_line(cfg, rel)}
    <p>運営者のほかのサイト：<a href="https://ashitano-tenki.github.io/" rel="noopener" target="_blank" data-goatcounter-click="sister/kansoku">あしたの転機観測所</a>・<a href="https://gendai-aimai-tango-jiten.github.io/" rel="noopener" target="_blank" data-goatcounter-click="sister/jiten">現代曖昧単語辞典</a>・<a href="https://kotoba-kenkyujo.github.io/" rel="noopener" target="_blank" data-goatcounter-click="sister/kotoba">会社のことば研究所</a></p>
    <div class="footer-bottom">
      <p class="footer-meta"><a href="{esc(base)}/feed.xml">新着のRSS</a></p>
      <button type="button" class="theme-toggle" id="theme-toggle" aria-pressed="false" hidden>ダーク表示</button>
    </div>
  </div>
</footer>
</body>
</html>
"""


def operator_line(cfg, rel=""):
    parts = []
    if cfg.get("operator"):
        name = esc(cfg["operator"])
        if cfg.get("operator_url"):
            name = f'<a href="{esc(cfg["operator_url"])}">{name}</a>'
        parts.append(f"運営：{name}")
    if cfg.get("contact_url"):
        parts.append(f'<a href="{esc(cfg["contact_url"])}">掲載内容の修正のご連絡</a>')
    parts.append(f'<a href="{rel}about/">この図鑑について</a>')
    return f"<p>{'　'.join(parts)}</p>" if parts else ""


def type_badge(t):
    cls = TYPE_CLASS.get(t, "is-other")
    return f'<span class="badge {cls}">{esc(TYPE_LABEL.get(t, t))}</span>'


def card(c, prefix="", order=None):
    meta = [x for x in [c.get("業種"), c.get("開始年") and f"{c['開始年']}年〜", c.get("段階"), c.get("場")] if x]
    point = c.get("工夫のポイント") or c.get("主な施策")
    # 2026-11-05 の見本で案A：右上に最初の目的の絵を丸の中に置き、目的の札も絵つきにする（絵は config/site.json の purpose_icons）
    icon = lambda p: PURPOSE_ICONS.get(p, "1f4cc")
    tags = "".join(f'<li><img src="{prefix}assets/emoji/{icon(t)}.png" alt="" width="16" height="16" loading="lazy">{esc(t)}</li>'
                   for t in c["_purpose"])
    emo = (f'<span class="card-emo"><img src="{prefix}assets/emoji/{icon(c["_purpose"][0])}.png" alt="" width="32" height="32" loading="lazy"></span>'
           if c["_purpose"] else "")
    data = {
        "type": c.get("種別", ""),
        "purpose": "|".join(c["_purpose"]),
        "stage": c.get("段階", ""),
        "activity": "|".join(c["_activity"]),
        "place": c.get("場", ""),
        "industry": c["_industry"],
        "size": c.get("規模の区分", ""),
        "tool": "|".join(dict.fromkeys(n for _, n in c.get("_tools", []))),
        "year": c.get("開始年", ""),
        "checked": date_key(c.get("確認日")),
        "score": score_value(c.get("観測スコア")),
    }
    if order is not None:
        data["order"] = str(order)
    attrs = " ".join(f'data-{k}="{esc(v)}"' for k, v in data.items())
    # 検索用キーワード（X列）は画面には出さず、検索の対象にだけ入れる
    search = " ".join(c.get(k, "") for k in ["企業名", "コミュニティ名", "業種", "ツール", "主な施策", "工夫のポイント", "目的", "活動の型", "検索用キーワード"])
    # 企業名・コミュニティ名の読みを足して、ひらがなでも見つかるようにする
    yomi = reading(" ".join([c.get("企業名", ""), c.get("コミュニティ名", "")]))
    search = normalize(search) + (" " + yomi if yomi else "")
    # キーワードで探したときの並び（企業名・コミュニティ名に合う → ツール・目的などに合う → 本文に合う）に使う。app.js の tierOf
    name_key = normalize(" ".join([c.get("企業名", ""), c.get("コミュニティ名", "")])) + (" " + yomi if yomi else "")
    tag_key = normalize(" ".join(c.get(k, "") for k in ["ツール", "目的", "活動の型", "業種", "検索用キーワード"]))
    return f"""<li class="card" {attrs} data-search="{esc(search)}" data-name="{esc(name_key)}" data-tags="{esc(tag_key)}">
  <a href="{prefix}cases/{esc(c['ID'])}/">
    {emo}<div class="card-top">{type_badge(c.get('種別'))}<span class="card-company">{esc(c['企業名'])}</span></div>
    <h3 class="card-title">{esc(c['_title'])}</h3>
    {f'<p class="card-meta">{" ・ ".join(esc(m) for m in meta)}</p>' if meta else ''}
    {f'<p class="card-point">{esc(shorten(point, 90))}</p>' if point else ''}
    {f'<ul class="tags tags-purpose">{tags}</ul>' if tags else ''}
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
        elif key == "tool":
            items = [n for n in dict.fromkeys(n for _, n in c.get("_tools", [])) if TOOL_COUNTS[n] >= TOOL_FACET_MIN]
        else:
            col = dict((k, col) for k, col, _ in FACETS)[key]
            items = [c.get(col)] if c.get(col) else []
        for v in items:
            vals[v] = vals.get(v, 0) + 1
    order = {"stage": STAGE_ORDER, "place": PLACE_ORDER, "purpose": PURPOSE_ORDER, "size": SIZE_ORDER,
             "type": TYPE_ORDER}.get(key)
    if order:
        return sorted(vals.items(), key=lambda kv: (order.index(kv[0]) if kv[0] in order else 99, kv[0]))
    return sorted(vals.items(), key=lambda kv: (kv[0] == "その他", -kv[1], kv[0]))


def purpose_strip(cfg, cases):
    """トップの「目的から探す」の帯。先頭に「すべて」、続けて目的を件数の多い順に並べる。

    押すと目的の絞り込みをその1つにする（app.js）。JavaScript が動かないときは ?purpose= のリンクとして働く。
    件数の数字は、読み込むと0から数え上がる。
    """
    icons = cfg.get("purpose_icons") or {}
    opts = sorted(facet_values(cases, "purpose"), key=lambda x: -x[1])
    if not opts:
        return ""

    def tile(href, purpose, code, n, name, current=False):
        cur = ' aria-current="true"' if current else ""
        return (f'<a class="tile" href="{href}" data-purpose="{esc(purpose)}"{cur} '
                f'data-goatcounter-click="purpose/{esc(name)}" data-goatcounter-title="目的から探す：{esc(name)}">'
                f'<img src="assets/emoji/{code}.png" alt="" width="34" height="34" loading="lazy">'
                f'<span class="tile-num" data-count="{n}">{n}</span><span class="tile-name">{esc(name)}</span></a>')

    tiles = [tile("./", "", "1f4d6", len(cases), "すべて", current=True)]
    tiles += [tile(f"?purpose={urllib.parse.quote(v)}", v, icons.get(v, "1f4cc"), n, v) for v, n in opts]
    return f"""
<section class="purposes wrap" aria-label="目的から探す">
  <div class="strip-head">
    <span class="strip-arrows" id="strip-arrows" hidden><button type="button" data-dir="-1" aria-label="前の目的へ">←</button><button type="button" data-dir="1" aria-label="次の目的へ">→</button></span>
  </div>
  <div class="strip-wrap"><div class="strip" id="purpose-strip">{''.join(tiles)}</div></div>
</section>"""
