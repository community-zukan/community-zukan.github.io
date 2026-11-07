"""事例一覧・事例ページ・この図鑑について・あとで見る・404 などのページ。"""

from .core import *  # noqa: F401,F403
from . import core
from .parts import *  # noqa: F401,F403
from .notes import *  # noqa: F401,F403
from .combos import *  # noqa: F401,F403


FIRST_CARDS = 24   # トップのHTMLに入れる件数（app.js の PAGE と同じ）


def build_index(cfg, cases):
    n_type = Counter(c.get("種別") for c in cases)
    # トップの大きな件数の名前は短くする（2026-11-06 黒田さんの判断。札や絞り込みは「ファン・顧客」のまま）
    STAT_LABEL = {"ファン・顧客": "顧客"}
    type_stats = "".join(f'\n      <div class="stat"><span class="stat-num" data-count="{n_type[t]}">{n_type[t]}</span><span class="stat-label">{esc(STAT_LABEL.get(t, t))}</span></div>'
                         for t in TYPE_ORDER if n_type[t])
    filters = []
    def chip_list(key, opts):
        return "".join(
            f'<label class="chip"><input type="checkbox" name="{key}" value="{esc(v)}"><span>{esc(v)}<small>{n}</small></span></label>'
            for v, n in opts)
    for key, col, label in FACETS:
        opts = facet_values(cases, key)
        if not opts:
            continue
        chips = chip_list(key, opts)
        if key == "purpose":
            # 目的は種別の小見出しで分ける（2026-11-05 の見本で案A。2026-11-06 に多企業を足した）。どこに入れるかは、その目的を持つ事例の種別の多いほう。
            # 種別が知らない値の事例ばかりの目的は「その他」に入れ、絞り込みから消えないようにする
            side = {}
            for c in cases:
                for p in c["_purpose"]:
                    side.setdefault(p, Counter())[c.get("種別")] += 1
            heads = ["社内", "ファン・顧客", "多企業"]
            def head_of(v):
                known = [(n, t) for t, n in side[v].items() if t in heads]
                return max(known, key=lambda x: (x[0], -heads.index(x[1])))[1] if known else "その他"
            groups = [(t, [(v, n) for v, n in opts if head_of(v) == t]) for t in heads + ["その他"]]
            # 種別を選んだら、その種別の小見出しの目的だけを出す（ux-purpose。2026-11-07 黒田さんの採用。app.js の narrowPurposes）
            chips = "".join(f'<div class="purpose-group" data-type="{esc(t)}"><p class="sublabel">{esc(TYPE_LABEL.get(t, t))}</p>'
                            f'<div class="chips">{chip_list(key, g)}</div></div>' for t, g in groups if g)
            filters.append(f'<fieldset class="facet" data-facet="{key}"><legend>{esc(label)}</legend>{chips}</fieldset>')
            continue
        filters.append(f'<fieldset class="facet" data-facet="{key}"><legend>{esc(label)}</legend><div class="chips">{chips}</div></fieldset>')
    # トップを軽くする（c-light。2026-11-07 黒田さんの採用）：HTMLには最初に見える24件（おすすめ順）だけを入れ、
    # 残りは cards.html に分けて、app.js が読み込んだあとに足す。絞り込み・検索・並べ替えは足し終わってから全件に効く。
    # data-order は収録順（並べ替えの最後の決め手）。app.js の doSort の「おすすめ順」と同じ順に並べる
    def default_key(i):
        c = cases[i]
        sc = score_value(c.get("観測スコア"))
        ck = date_key(c.get("確認日"))
        return (sc == "", -int(sc) if sc else 0, ck == "", "" if not ck else str(99999999 - int(ck)), i)
    order = sorted(range(len(cases)), key=default_key)
    first_cards = "".join(card(cases[i], order=i) for i in order[:FIRST_CARDS])
    rest_html = "".join(card(cases[i], order=i) for i in order[FIRST_CARDS:])
    rest_ver = hashlib.sha1(rest_html.encode("utf-8")).hexdigest()[:8]
    write("cards.html", rest_html)
    synonyms_json = json.dumps(load_synonyms(), ensure_ascii=False).replace("</", "<\\/")
    # コミュニティAIへの入口（2026-11-06 の見本で案B）：トップは大きな件数の下に1行。事例一覧は、結果が5件以下なら囲み、多いときは一番下に1行（app.js が切り替える）
    top_link = ai_link("コミュニティAIに相談する", "home")
    top_ai = (f'<p class="ai-top"><img src="assets/emoji/1f4ac.png" alt="" width="18" height="18">{top_link}'
              f'<span>立ち上げや運営の悩みを、事例をもとに一緒に考えます</span></p>') if top_link else ""
    few_link = ai_link("AIに相談する", "list-few", cls="button button-ghost ai-help-button")
    list_ai = (f'<aside class="ai-help" id="ai-help" data-few="5" hidden><p class="ai-help-title">うまく見つからないときは</p>'
               f'<p class="ai-help-text">いまのコミュニティの状況を話すと、コミュニティAIが近い事例を一緒に探します。</p>{few_link}</aside>') if few_link else ""
    body = f"""
<section class="hero">
  <div class="wrap">
    <h1><span class="mark">公開事例でみる</span><br class="sp">企業のコミュニティ運営のすべて</h1>
    <p class="lead">企業が運営するファンコミュニティ、社内コミュニティ、多企業コミュニティについて、プレスリリースや記事などの公開情報から事例を集めています。目的・段階・活動の型で絞り込んで、自社に近い事例を探せます。</p>
    <div class="stats">
      <div class="stat"><span class="stat-num" data-count="{len(cases)}">{len(cases)}</span><span class="stat-label">収録事例</span></div>
{type_stats}
    </div>
    {top_ai}
  </div>
</section>
{purpose_strip(cfg, cases)}
<section class="finder wrap" aria-label="事例を探す">
  <div class="search-row">
    <label class="visually-hidden" for="q">キーワード</label>
    <input id="q" type="search" placeholder="企業名・ツールなどで検索" autocomplete="off">
    <label class="visually-hidden" for="sort">並び順</label>
    <select id="sort">
      <option value="score" selected>おすすめ順</option>
      <option value="default">収録順</option>
      <option value="year-desc">開始年が新しい順</option>
      <option value="year-asc">開始年が古い順</option>
      <option value="checked-desc">確認日が新しい順</option>
    </select>
    {search_examples(cfg)}
  </div>
  <details class="filters" id="filters">
    <summary><span>条件で絞り込む</span><span class="active-count" id="active-count"></span></summary>
    <div class="filters-body">
      <button type="button" id="reset3" class="link-button filters-reset" hidden>すべて外す</button>
      {''.join(filters)}
    </div>
  </details>
  <div class="result-bar">
    <p id="result-count" aria-live="polite">{len(cases)}件の事例</p>
    <p class="search-note" id="search-note" hidden></p>
    <p class="tool-note" id="tool-note" hidden><span></span><button type="button" class="small-button" id="tool-clear">外す</button></p>
    <button type="button" id="reset" class="link-button" hidden>条件をすべて外す</button>
    <button type="button" id="saved-toggle" class="saved-toggle" aria-pressed="false" hidden>あとで見る</button>
    <div class="view-toggle" id="view-toggle" role="group" aria-label="表示のしかた" hidden>
      <button type="button" class="view-btn" data-view="card" aria-pressed="true" title="カードで表示"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="4" width="7" height="7" rx="1"/><rect x="13" y="4" width="7" height="7" rx="1"/><rect x="4" y="13" width="7" height="7" rx="1"/><rect x="13" y="13" width="7" height="7" rx="1"/></svg><span class="visually-hidden">カードで表示</span></button>
      <button type="button" class="view-btn" data-view="list" aria-pressed="false" title="一覧で表示"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16"/></svg><span class="visually-hidden">一覧で表示</span></button>
    </div>
  </div>
  <ul class="cards" id="cards" data-rest="cards.html?v={rest_ver}" data-total="{len(cases)}">
    {first_cards}
  </ul>
  <div class="empty" id="empty" hidden>
    <p>条件に合う事例はありませんでした。</p>
    <p id="empty-hint">条件を減らすか、キーワードを変えてみてください。</p>
    <ul class="relax" id="relax" hidden></ul>
    <button type="button" class="button" id="reset2">条件をすべて外す</button>
  </div>
  <div class="finder-foot">
    <div class="more" id="more" hidden>
      <button type="button" class="more-button" id="more-button">もっと見る</button>
    </div>
    {list_ai}
  </div>
</section>
<script type="application/json" id="synonyms">{synonyms_json}</script>
<script src="assets/app.js?v={ver('app.js')}" defer></script>
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


def build_case(cfg, c, related, og_image=None, notes=None, og_notes=None):
    # 事例ページ（2026-11-05 の見本で選んだ「読み物」の形）：
    # 基本の情報を小さな札に → 「この事例のポイント」（工夫のポイント）を大きく → 何をしたか → どうなったか →
    # だれが動かしているか → あなたの会社なら（AIによる提案）の流れ → 出典 → あとで見る・共有 → 近い事例。空欄の段は出さない
    icons = cfg.get("purpose_icons") or {}
    # 白い札（基本の情報と活動の型）はまとめて1か所に。どれも押すと近い事例の一覧を開く（押せない札は置かない。2026-11-05 黒田さんの判断）：
    # 段階・活動の型・場は絞り込み、業種は業種のまとめの絞り込み、ツールは「ツールにその名前がある事例」（ほかにも使っている事例があるものだけ）。
    # 開始年・規模・ほかで使われていないツールは、下の流れの段に文章で添える
    def fact_link(text, param, value, label):
        href = f"../../?{param}={urllib.parse.quote(value)}"
        return (f'<li><a href="{href}" title="{esc(label)}の事例を見る" '
                f'data-goatcounter-click="fact/{esc(param)}/{esc(value)}">{esc(text)}</a></li>')
    facts = []
    if c.get("業種"):
        facts.append(fact_link(c["業種"], "industry", c["_industry"], f"業種「{c['_industry']}」")
                     if c.get("_industry") else f"<li>{esc(c['業種'])}</li>")
    if c.get("段階"):
        facts.append(fact_link(c["段階"], "stage", c["段階"], f"段階「{c['段階']}」"))
    for a in c["_activity"]:
        facts.append(fact_link(a, "activity", a, f"活動の型「{a}」"))
    if c.get("場"):
        facts.append(fact_link(c["場"], "place", c["場"], f"場「{c['場']}」"))
    other_tools = []
    for t, name in c.get("_tools", []):
        if TOOL_COUNTS[name] >= 2:
            facts.append(fact_link(t, "tool", name, f"ツール「{name}」"))
        else:
            other_tools.append(t)
    chips = "".join(facts)
    purposes = "".join(
        f'<li><a href="../../?purpose={urllib.parse.quote(p)}"><img src="../../assets/emoji/{icons.get(p, "1f4cc")}.png" alt="" width="20" height="20">{esc(p)}</a></li>'
        for p in c["_purpose"])
    lede = ""
    if c.get("工夫のポイント"):
        lede = f"""<section class="lede" style="--i: 0">
    <h2><img src="../../assets/emoji/1f4a1.png" alt="" width="20" height="20">この事例のポイント</h2>
    <p>{esc(c['工夫のポイント'])}</p>
  </section>"""
    # 札にしない基本の情報（開始年・規模・ほかで使われていないツール）は、流れの段の頭に小さく添える
    size = c.get("規模") or c.get("規模の区分")
    tools_label = "ほかのツール" if len(other_tools) < len(c.get("_tools", [])) else "ツール"
    metas = {
        "主な施策": [("開始", c.get("開始年") and f"{c['開始年']}年")],
        "公開されている成果": [("規模", size)],
        "運営体制": [(tools_label, "、".join(other_tools))],
    }
    steps = []
    for code, question, col in [("1f6e0", "何をしたか", "主な施策"), ("1f4c8", "どうなったか", "公開されている成果"),
                                ("1f465", "だれが動かしているか", "運営体制")]:
        meta = "".join(f'<p class="flow-meta"><span>{k}</span>{esc(v)}</p>' for k, v in metas[col] if v)
        if c.get(col) or meta:
            steps.append(f'<li style="--i: {len(steps) + 1}"><span class="step"><img src="../../assets/emoji/{code}.png" alt="" width="26" height="26"></span>'
                         f'<div><h2>{question}</h2>{meta}{f"<p>{esc(c[col])}</p>" if c.get(col) else ""}</div></li>')
    # コミュニティAIへの入口（2026-11-06 の見本で案B）：「あなたの会社なら」の箱の中、提案のすぐ下に置く。
    # リンクの末尾に #事例ID を付けると、コミュニティAIがこの事例のカードを出して相談を始める。提案がない事例は流れの下に1行で置く
    ai = ai_link("AIに相談する", f"case/{c['ID']}", c["ID"], "ai-btn")  # 狭い画面でも1行に収まるよう短く（箱の説明に「コミュニティAI」と書いてある）
    ai_box = (f'<div class="ai-box"><p class="ai-box-title"><img src="../../assets/emoji/1f4ac.png" alt="" width="20" height="20">自分の状況に合わせて考える</p>'
              f'<p class="ai-box-text">コミュニティAIが、この事例をふまえて相談に乗ります。いまの状況を書き足して送ってください。</p>'
              f'{ai}</div>') if ai else ""
    if c.get(HINT_COL):
        steps.append(f"""<li style="--i: {len(steps) + 1}"><span class="step"><img src="../../assets/emoji/1f914.png" alt="" width="26" height="26"></span><div><h2>あなたの会社なら</h2>
      <div class="hint"><p>{esc(c[HINT_COL])}</p><p class="hint-note">事例をもとにAIが考えた応用案です。出典に書かれている事実ではありません。</p>{ai_box}</div></div></li>""")
    flow = f'<ol class="flow">{"".join(steps)}</ol>' if steps else ""
    if not c.get(HINT_COL):
        flow += ai_line("../../", "この事例を自分のコミュニティに生かすには？コミュニティAIに相談する", f"case/{c['ID']}", c["ID"])
    missing_cols = ["規模", "開始年", "公開されている成果", "運営体制", "ツール", "段階", "場"]
    missing = [m for m in missing_cols if not c.get(m)]
    links = "".join(f'<li><a class="source-button" href="{esc(u)}" rel="noopener" target="_blank" data-goatcounter-click="source-{esc(c["ID"])}" '
                    f'data-goatcounter-title="出典 {esc(c["企業名"])} {esc(domain(u))}">出典を開く<span class="source-domain">{esc(domain(u))}</span></a></li>' for u in c["_urls"])
    source = f"""<section class="source">
    <h2>出典</h2>
    {f'<ul class="source-links">{links}</ul>' if links else ''}
    <dl class="source-meta">
      {dl_row("出典の時期", esc(fmt_month(c.get("出典の時期"))))}
      {dl_row("出典の種類", esc(c.get("出典の種類")))}
      {dl_row("注意点", esc(c.get("出典の注意")))}
      {dl_row("確認日", esc(fmt_date(c.get("確認日"))))}
    </dl>
    {f'<p class="missing">公開情報で確認できなかった項目：{esc("、".join(missing))}</p>' if missing else ''}
  </section>"""
    rel_html = ""
    if related:
        # 近い事例（2026-11-06 の見本で案2＋案3）：切り口（同じ目的・同じ業種・同じ種別で同じ段階）を件数つきのタブにし、
        # 押すとその切り口の4件（絵つきのカード）に切り替える。下に図鑑の全体から1件をめくる「ほかの事例をひく」
        tabs, panels = [], []
        for i, r in enumerate(related):
            cards = "".join(rel_card(o, f"related/{r['kind']}") for o in r["cases"])
            # タブは「同じ目的」と値の2段。狭い画面で折り返すときは「・」の後ろだけで折り返す
            value = esc(r["value"]).replace("・", "・<wbr>")
            tabs.append(
                f'<button type="button" class="rel-tab" role="tab" id="rel-tab-{i}" aria-controls="rel-panel-{i}" aria-selected="{"true" if i == 0 else "false"}" '
                f'data-goatcounter-click="related-tab/{esc(r["kind"])}"><img src="../../assets/emoji/{r["emoji"]}.png" alt="" width="28" height="28">'
                f'<span class="rel-tab-axis">{esc(r["axis"])}</span><span class="rel-tab-name">{value}</span><span class="rel-tab-num">{r["total"]}<small>件</small></span></button>')
            panels.append(
                f'<div class="rel-panel" role="tabpanel" id="rel-panel-{i}" aria-labelledby="rel-tab-{i}"{"" if i == 0 else " hidden"}>'
                f'<div class="rel-grid">{cards}</div>'
                f'<a class="rel-all" href="../../{r["href"]}" data-goatcounter-click="related-all/{esc(r["kind"])}" aria-label="{esc(r["title"])}をすべて見る（{r["total"]}件）">すべて見る（{r["total"]}件）<span aria-hidden="true"> →</span></a></div>')
        pick = (f'<div class="rel-pick" id="rel-pick" data-id="{esc(c["ID"])}" hidden><div class="rel-pick-text">'
                f'<h3><img src="../../assets/emoji/1f3b2.png" alt="" width="24" height="24">ほかの事例をチェック</h3>'
                f'<p>図鑑の事例からランダムに1件めくります。</p>'
                f'<button type="button" class="rel-pick-button" id="rel-pick-button"><img src="../../assets/emoji/1f3b2.png" alt="" width="22" height="22">ほかの事例をひく</button></div>'
                f'<div class="rel-pick-card" id="rel-pick-card" aria-live="polite"></div></div>')
        rel_html = (f'<section class="related"><h2>近い事例</h2><div class="rel-tabs" role="tablist" aria-label="近い事例の切り口">{"".join(tabs)}</div>'
                    f'{"".join(panels)}{pick}</section>')
    note_html_ = ""
    in_notes = [n for n in (notes or []) if c["ID"] in n["ids"]]
    if in_notes:
        # 図鑑ノートの一覧と同じ画像つきのカードで出す（2026-11-06 黒田さんの判断：もっと目立たせる）
        note_html_ = (f'<section class="case-notes"><h2><img src="../../assets/emoji/1f4d3.png" alt="" width="22" height="22">この事例を紹介している{NOTES_LABEL}</h2>'
                      f'{note_list(in_notes, og_notes or set(), "../../")}</section>')
    desc = shorten(f"{c['企業名']}の{c['_title']}。" + (c.get("工夫のポイント") or c.get("主な施策") or ""), 120)
    body = f"""
<article class="case wrap">
  <nav class="crumbs" aria-label="パンくずリスト"><ol><li><a href="../../">事例一覧</a></li><li aria-current="page">{esc(c['企業名'])}</li></ol></nav>
  <header class="case-head">
    <div class="card-top">{type_badge(c.get('種別'))}<span class="card-company">{esc(c['企業名'])}</span></div>
    <h1>{esc(c['_title'])}</h1>
    {f'<ul class="case-chips" aria-label="基本の情報">{chips}</ul>' if chips else ''}
    {f'<ul class="case-purposes" aria-label="目的">{purposes}</ul>' if purposes else ''}
    {save_button(c)}
  </header>
  {lede}
  {old_source_note(c)}
  {flow}
  {source}
  {share_bar(cfg, c)}
  <div class="feedback">
    <div class="useful" id="useful" hidden>
      <p>この事例は参考になりましたか。</p>
      <span class="useful-buttons">
        <button type="button" class="small-button" id="useful-button" data-id="{esc(c['ID'])}" data-goatcounter-click="useful-{esc(c['ID'])}">役に立った</button>
        <button type="button" class="small-button" id="notuseful-button" data-id="{esc(c['ID'])}" data-goatcounter-click="notuseful-{esc(c['ID'])}">いまひとつ</button>
      </span>
      <span class="useful-thanks" id="useful-thanks" role="status" aria-live="polite"></span>
    </div>
    {report_link(cfg, c)}
  </div>
  {note_html_}
  {rel_html}
</article>
<script src="../../assets/case.js?v={ver('case.js')}" defer></script>
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


OLD_SOURCE_YEARS = 3


def old_source_note(c):
    """出典の時期が3年以上前の事例に1行の注記を出す（c-old。2026-11-07 黒田さんの採用）。時期が空・読めないときは出さない。"""
    v = (c.get("出典の時期") or "").strip().lstrip("'")
    m = re.match(r"(\d{4})\s*[-/.年]\s*(\d{1,2})", v)
    if not m:
        return ""
    now = datetime.now(JST)
    months = (now.year - int(m.group(1))) * 12 + now.month - int(m.group(2))
    if months < OLD_SOURCE_YEARS * 12:
        return ""
    return f'<p class="case-old">出典は{esc(fmt_month(v))}のもので、いまは変わっている可能性があります。</p>'


def rel_card(o, click):
    """近い事例のカード。一覧のカードと同じく、右上に最初の目的の絵を丸の中に置き、下に目的の札（絵つき、2つまで）。"""
    icon = lambda p: PURPOSE_ICONS.get(p, "1f4cc")
    pt = shorten(o.get("工夫のポイント") or o.get("主な施策") or "", 34)
    p0 = o["_purpose"][0] if o["_purpose"] else ""
    emo = f'<span class="rel-emo"><img src="../../assets/emoji/{icon(p0)}.png" alt="" width="28" height="28"></span>' if p0 else ""
    tags = "".join(f'<li><img src="../../assets/emoji/{icon(p)}.png" alt="" width="14" height="14">{esc(p)}</li>' for p in o["_purpose"][:2])
    return (f'<a class="rel" href="../{esc(o["ID"])}/" data-goatcounter-click="{esc(click)}">{emo}'
            f'<span class="rel-top">{type_badge(o.get("種別"))}</span><small>{esc(o["企業名"])}</small>'
            f'<strong>{esc(o["_title"])}</strong>{f"<span class=rel-point>{esc(pt)}</span>" if pt else ""}'
            f'{f"<ul class=rel-tags>{tags}</ul>" if tags else ""}</a>')


def save_button(c):
    """あとで見る。読み終わる前に入れたい人のために、事例ページの見出しの札の下（最初に見える位置）に置く（2026-11-06 黒田さんの判断）。JavaScript が動くときだけ出す。"""
    i = esc(c["ID"])
    return (f'<button type="button" class="action-button save" id="save" data-id="{i}" aria-pressed="false" '
            f'data-goatcounter-click="save-{i}" hidden><span class="save-icon" aria-hidden="true"></span><span class="save-label">あとで見る</span></button>')


def share_bar(cfg, c):
    """URLのコピー・SNSへの共有。コピーは JavaScript が動くときだけ出す（あとで見るは見出しの札の下。save_button）。"""
    url = f"{cfg['base_url'].rstrip('/')}/cases/{c['ID']}/"
    text = f"{c['企業名']} {c['_title']}｜{cfg['name']}"
    q = urllib.parse.quote
    links = [
        ("X", f"https://x.com/intent/post?text={q(text)}&url={q(url)}"),
        ("Facebook", f"https://www.facebook.com/sharer/sharer.php?u={q(url)}"),
        ("LINE", f"https://social-plugins.line.me/lineit/share?url={q(url)}"),
    ]
    share = "".join(f'<li><a class="share-link" href="{esc(h)}" target="_blank" rel="noopener" '
                    f'data-goatcounter-click="share-{n.lower()}-{esc(c["ID"])}">{n}</a></li>' for n, h in links)
    return f"""<div class="actions">
  <div class="share">
    <ul class="share-list" aria-label="共有">
      <li><button type="button" class="share-link" id="copy-url" data-url="{esc(url)}" data-goatcounter-click="share-copy-{esc(c['ID'])}" hidden>URLをコピー</button></li>
      {share}
    </ul>
    <span class="copy-status" id="copy-status" role="status" aria-live="polite"></span>
  </div>
</div>"""


def report_link(cfg, c):
    if not cfg.get("contact_url"):
        return ""
    url = cfg["contact_url"]
    if cfg.get("contact_id_entry"):
        target = f"{c['ID']} {c['企業名']} {c['_title']}"
        url += "?usp=pp_url&" + urllib.parse.urlencode({cfg["contact_id_entry"]: target})
    return f'<p class="report"><a href="{esc(url)}" target="_blank" rel="noopener">この事例の誤りを知らせる</a></p>'


def related_rows(cfg, c, cases, per_row=4):
    """事例ページの「近い事例」の帯（案C）。同じ目的（最初の目的）・同じ業種・同じ種別で同じ段階の3つ。
    帯の中は観測スコアの高い順（同点は近さの順）。上の帯に出した事例は下の帯に重ねて出さない（件数は「すべて見る」で開く一覧の数）。
    当てはまる事例がない帯は出さない。"""
    icons = cfg.get("purpose_icons") or {}
    q = urllib.parse.quote
    others = [o for o in cases if o["ID"] != c["ID"]]
    near = {o["ID"]: i for i, o in enumerate(find_related(c, cases, n=len(cases)))}
    def rank(o):
        sv = score_value(o.get("観測スコア"))
        return (-(int(sv) if sv else -1), near.get(o["ID"], 0))
    rows = []
    if c["_purpose"]:
        p = c["_purpose"][0]
        rows.append(("purpose", icons.get(p, "1f4cc"), f"目的が「{p}」の事例", f"?purpose={q(p)}",
                     [o for o in others if p in o["_purpose"]], "同じ目的", p))
    if c["_industry"]:
        g = c["_industry"]
        rows.append(("industry", "1f3e2", f"業種が「{g}」の事例", f"?industry={q(g)}",
                     [o for o in others if o["_industry"] == g], "同じ業種", g))
    if c.get("段階") and c.get("種別"):
        t, st = c["種別"], c["段階"]
        rows.append(("stage", AXIS_ICONS.get(st, "1f4c8"), f"{TYPE_LABEL.get(t, t)}で{st}の事例", f"?type={q(t)}&stage={q(st)}",
                     [o for o in others if o.get("段階") == st and o.get("種別") == t], "同じ段階", st))  # 種別もそろえている（「すべて見る」の文言に出る）
    shown, out = set(), []
    for kind, emoji, title, href, lst, axis, value in rows:
        pick = [o for o in sorted(lst, key=rank) if o["ID"] not in shown][:per_row]
        if not pick:
            continue
        shown.update(o["ID"] for o in pick)
        out.append({"kind": kind, "emoji": emoji, "title": title, "href": href, "total": len(lst) + 1, "cases": pick, "axis": axis, "value": value})  # 件数は開いた一覧と同じ数（この事例自身も含む）
    return out


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
        ("種別", "社内／ファン・顧客／多企業", "誰が集まるコミュニティか。社内は従業員（退職者のアルムナイを含む）、ファン・顧客は製品やブランドの利用者です。多企業は、運営企業の社員や顧客に限らず、さまざまな企業・組織の人や企業が集まる多企業コミュニティです（スタートアップ・起業家、企業どうしの共創、業界・職種の担当者のコミュニティなど）。"),
        ("目的（社内）", "ビジョン浸透、エンゲージメント、イノベーション、ナレッジ共有、部門横断、オンボーディング", "企業が社内コミュニティに期待していること。出典に書かれている範囲で、複数つけています。"),
        ("目的（ファン・顧客）", "LTV・継続、共創・商品開発、サポート効率化、口コミ・認知、ブランド体験", "企業がファンコミュニティに期待していること。複数つけています。"),
        ("目的（多企業）", "事業共創・協業、起業・成長支援、投資・資金調達、採用・人材、拠点・地域の活性化、業界の学び合い", "企業が多企業コミュニティに期待していること。事業共創・協業は企業どうしの協業や実証、起業・成長支援はスタートアップの立ち上げや成長の支援、投資・資金調達は投資や資金調達の機会、採用・人材は採用や人とのつながり、拠点・地域の活性化は施設やエリアの利用とにぎわい、業界の学び合いは同じ業界・職種の人どうしの情報交換です。複数つけています。"),
        ("段階", "立ち上げ期／成長期／成熟期／転換期", "出典の時点での状態です。立ち上げ期は開始から1年程度、成長期は規模や活動が広がっている途中、成熟期は長く続いて仕組みが定着している状態、転換期は終了・統合・方針転換を指します。"),
        ("活動の型", "ナレッジ共有型、プロジェクト型、趣味親睦型", "ナレッジ共有型は学び合いや質問への回答、プロジェクト型は共創や企画、趣味親睦型は交流が中心の活動です。複数つけています。"),
        ("場", "オンライン／オフライン／オンオフ両方", "主な活動の場所です。"),
        ("出典の種類", "プレスリリース／インタビュー記事／登壇資料／公式note・サイト／広告・PR記事", "広告・PR記事は、ツールを提供する企業などが作った記事です。記事中の数値は、企業側の説明として扱っています。"),
    ]
    rows = "".join(f"<tr><th scope=\"row\">{esc(a)}</th><td>{esc(b)}</td><td>{esc(d)}</td></tr>" for a, b, d in defs)
    body = f"""
<article class="prose wrap">
  <h1>この図鑑について</h1>
  <p>コミュニティ図鑑は、企業が運営するファンコミュニティ、社内コミュニティ、多企業コミュニティの事例を、公開情報から集めたものです。コミュニティを立ち上げたい人や、運営に行き詰まっている人が、自社に近い事例を探して読めるようにしています。</p>

  <h2>載せている情報</h2>
  <p>プレスリリース、メディアの記事、登壇資料、企業の公式サイトやnoteなど、誰でも読める情報だけを使っています。本文は転載せず、要点の要約とタグ、出典へのリンクでまとめています。</p>
  <p>公開情報から分からない項目は、推測で埋めずに空欄のままにしています。たとえば規模や成果は、公表していない企業も多くあります。各事例のページには「公開情報で確認できなかった項目」を表示しています。</p>

  <h2>集め方と更新</h2>
  <p>事例の探索、出典の確認、タグづけ、掲載してよいかの判断は、AI（Claude）が決まった手順で行い、運営者がふりかえりで点検しています。新しい事例は随時追加し、サイトは毎日更新しています。最終更新は{esc(updated)}です。</p>
  <p>数値や状況は出典の時点のものです。最新の状況は、各企業の発表をご確認ください。</p>

  <h2>おすすめ順</h2>
  <p>事例一覧は、はじめは「おすすめ順」で並んでいます。事例ごとに次の4つの点数を足した「観測スコア」（100点満点）の高い順で、同じ点数のときは確認日の新しい順です。初めて読む人が、よく知られていて情報の多い事例から読めるようにするための並び順で、各社の取り組みの良し悪しを評価した点数ではありません。</p>
  <div class="table-wrap">
  <table class="defs compact">
    <thead><tr><th scope="col">項目</th><th scope="col">配点</th><th scope="col">決め方</th></tr></thead>
    <tbody>
      <tr><th scope="row">知名度</th><td>15点</td><td>企業やコミュニティがどのくらい知られているかを、AIが5段階で推定し、1段階を3点にしています。推定していない事例は6点です。</td></tr>
      <tr><th scope="row">情報の厚み</th><td>45点</td><td>規模・成果・運営体制・開始年・ツールのうち、公開情報で分かった項目1つにつき9点です。</td></tr>
      <tr><th scope="row">鮮度</th><td>25点</td><td>出典の時期が12か月以内なら25点、24か月以内なら18点、48か月以内なら10点、それより前なら4点、分からなければ8点です。</td></tr>
      <tr><th scope="row">出典の確かさ</th><td>15点</td><td>広告・PR記事は6点、それ以外は15点です。</td></tr>
    </tbody>
  </table>
  </div>
  <p>知名度はAIによる推定で、調査にもとづく数値ではありません。並び順は「収録順」「開始年が新しい順」などに切り替えられます。</p>

  <h2>「自社でやるなら」の欄</h2>
  <p>事例ページの「自社でやるなら」は、事例をもとにAIが考えた応用案です。出典に書かれている事実ではないため、ほかの欄と分けて表示しています。</p>

  <h2>タグの意味</h2>
  <div class="table-wrap">
  <table class="defs">
    <thead><tr><th scope="col">項目</th><th scope="col">選択肢</th><th scope="col">意味</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  </div>

  <h2>アクセス解析</h2>
  <p>どのページがよく読まれているかを知るために、アクセス解析の GoatCounter を使っています。数えているのは、ページが開かれた回数と、出典へのリンク・「あとで見る」・共有・「役に立った」「いまひとつ」のボタン・事例一覧の「目的から探す」のタイル・「組み合わせから探す」の地図のマス・この図鑑についての運営者のリンクが押された回数です。コミュニティAIへのリンクが押されたときは、どのページのリンクから移ったか（メニュー、トップ、事例一覧、事例ページ、図鑑ノートのどれか。事例ページなら事例のID）も数えます。コミュニティAIでは、返答の下の「役に立った」「立たなかった」が押された回数と、AIによる相談の分類（コミュニティの段階と種類）を同じ GoatCounter で数えます。相談の文章は運営者に届きません。GoatCounter はクッキーを使わず、名前やメールアドレスなど個人を特定できる情報も集めません。ページのアドレスのうち「?」から後ろ（検索語や絞り込みの条件）は送らず、来た元を示す部分だけを送っています。</p>
  <p>事例一覧の検索欄に入力された言葉と、その言葉で事例が見つかったかどうかも数えています。言い換えの表を増やしたり、集める事例のテーマを決めたりするのに使います。メールアドレス・電話番号・URLのような言葉は記録しません。検索欄には、名前など個人を特定できる情報を入れないでください。</p>
  <p>「あとで見る」に入れた事例は、お使いのブラウザの中だけに保存しています。運営者には送られません。</p>

  <h2>掲載内容について</h2>
  <p>内容の誤りのお知らせや、事例のご提案は、{contact_text(cfg)}</p>

  <h2>掲載されている企業の方へ</h2>
  <p>この図鑑は、公開されている情報を要約し、出典へのリンクを添えて紹介しています。内容の訂正や、掲載の取り下げをご希望の場合は、{contact_text(cfg)}事例ページの「この事例の誤りを知らせる」から開くと、対象の事例が入った状態でフォームが開きます。</p>
  <p>いただいたご連絡は、出典と照らして確かめたうえで、訂正または取り下げを行います。取り下げた事例は、サイトの毎日の更新で一覧と事例ページから外れます。</p>

  <h2>運営者</h2>
  <div class="operator-card">
    <p class="operator-name"><strong>{esc(cfg.get('operator', ''))}</strong><span>コミュニティ研究家</span></p>
    <p>2017年に、日本最大級の実名制フリーランスコミュニティ「FreelanceNow」と、問いでつながるコミュニティ「議論メシ」を立ち上げました。議論メシでは1,200回以上のイベントを開き、延べ13,000人以上が参加しています。スタートアップ、大企業、NPO、行政などとのコラボレーションは400回を超えます。</p>
    <p>2024年3月からは、コミューン株式会社のコミューンコミュニティラボ所長として、コミュニティの研究と社会実装に取り組みました。著書に、社会の変化とコミュニティの関係を書いた『コミュニティシフト』と、企業の経営や事業におけるコミュニティの役割を論じた『コミュニティ経営の教科書』があります。</p>
    <p>2026年10月からはフリーランスとして、コミュニティ研究家、キャリア研究家、ディスカッションパートナーを仕事にしています。同じ時期に FreelanceNow を、キャリアの転機をシェアするコミュニティ「あしたの転機」にリニューアルしました。メンバーは1.6万人を超えています。この図鑑のほか、「<a href="https://ashitano-tenki.github.io/">あしたの転機観測所</a>」も運営しています。</p>
    <p>企業でコミュニティを担当している方や、コミュニティを主宰している方の相談相手として、壁打ちや伴走も引き受けています。ご相談は、下のリンク集にある連絡先からお寄せください。</p>
    <p class="operator-link"><a class="button" href="{esc(cfg.get('operator_url', ''))}" rel="noopener" target="_blank" data-goatcounter-click="contact-operator/about">黒田悠介のリンク集を見る</a><span>連絡先や、ほかの活動・発信をまとめています</span></p>
  </div>
</article>
"""
    return page(cfg, title="この図鑑について", description="コミュニティ図鑑の収録ルール、集め方、タグの意味を説明しています。",
                path="about/", body=body, depth=1)


def contact_text(cfg):
    if cfg.get("contact_url"):
        return f'<a href="{esc(cfg["contact_url"])}">こちらのフォーム</a>からお送りください。'
    return "運営者までお知らせください。"


def build_saved(cfg, cases):
    """あとで見る（/saved/）。事例ページで「あとで見る」に入れた事例を、入れた順の新しいものから並べる。

    入れた事例はブラウザの localStorage（zukan-saved）にだけあるので、全事例のカードを隠して置き、
    assets/saved.js が入れたものだけを出す。検索エンジンには載せない。
    全事例のカードはページに入れず saved/cards.html に分け、saved.js が読み込んでから出す（ページを軽くするため。2026-11-07）。
    /saved/?ids=S01,F02 で開くと、送られてきたリストとして出し、自分の保存に入れることもできる（観測所と同じ。2026-11-07）。
    """
    all_cards = "".join(card(c, prefix="../").replace('<li class="card" ', '<li class="card" hidden ', 1) for c in cases)
    saved_ver = hashlib.sha1(all_cards.encode("utf-8")).hexdigest()[:8]
    write("saved/cards.html", all_cards)
    body = f"""
<article class="wrap saved-page">
  <nav class="crumbs" aria-label="パンくずリスト"><ol><li><a href="../">事例一覧</a></li><li aria-current="page">あとで見る</li></ol></nav>
  <h1>あとで見る</h1>
  <p class="lead">事例ページで「あとで見る」を押した事例です。このブラウザの中にだけ保存していて、運営者には送られません。</p>
  <div class="saved-bar">
    <p class="saved-count" id="saved-count" aria-live="polite">読み込んでいます…</p>
    <p class="saved-actions">
      <button type="button" class="button" id="saved-import" hidden data-goatcounter-click="saved-list/import">自分の「あとで見る」に入れる</button>
      <button type="button" class="small-button" id="saved-share" hidden data-goatcounter-click="saved-list/share">このリストを送る</button>
    </p>
  </div>
  <p class="saved-note" id="saved-note" aria-live="polite"></p>
  <h2 class="visually-hidden">事例の一覧</h2>
  <ul class="cards" id="saved-cards" data-src="cards.html?v={saved_ver}"></ul>
  <div class="empty" id="saved-empty" hidden>
    <p>まだ「あとで見る」に入れた事例はありません。</p>
    <p>事例ページの「あとで見る」を押すと、ここにたまります。</p>
    <a class="button" href="../">事例一覧を見る</a>
  </div>
  <noscript><p>このページを使うには、JavaScript を有効にしてください。</p></noscript>
</article>
<script src="../assets/saved.js?v={ver('saved.js')}" defer></script>
"""
    return page(cfg, title="あとで見る", description="あとで見るために残した事例の一覧です。", path="saved/",
                body=body, depth=1, noindex=True)


def build_404(cfg):
    body = """
<article class="prose wrap">
  <h1>ページが見つかりませんでした</h1>
  <p>URLが変わったか、事例が削除された可能性があります。企業名やコミュニティ名で探し直せます。</p>
  <form class="search-again" action="/" role="search">
    <input type="search" name="q" aria-label="キーワードで探す" placeholder="企業名・ツール・施策などで探す">
    <button type="submit" class="button">探す</button>
  </form>
  <h2>ほかの入口</h2>
  <ul class="entrances">
    <li><a href="/">事例一覧</a>：すべての事例を、目的・段階・活動の型で絞り込めます。</li>
    <li><a href="/new/">新着</a>：最近載った事例と、内容が変わった事例です。</li>
    <li><a href="/combos/">組み合わせ</a>：目的と段階、種別と活動の型の組み合わせから探せます。</li>
    <li><a href="/notes/">図鑑ノート</a>：テーマごとに事例を読み比べた記事です。</li>
  </ul>
</article>
"""
    return page(cfg, title="ページが見つかりません", description="", path="404.html", body=body).replace(
        'href="assets/', 'href="/assets/').replace('src="assets/', 'src="/assets/').replace(
        'href="./"', 'href="/"').replace('href="about/"', 'href="/about/"').replace('href="new/"', 'href="/new/"').replace('href="combos/"', 'href="/combos/"').replace('href="saved/"', 'href="/saved/"').replace('href="notes/"', 'href="/notes/"')


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
