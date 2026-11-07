"""組み合わせのページ（/combos/）：目的×段階、種別×活動の型。"""

from .core import *  # noqa: F401,F403
from . import core
from .parts import *  # noqa: F401,F403
from .notes import *  # noqa: F401,F403


# ---------- 組み合わせのページ ----------

COMBO_MIN = 5   # この件数以上の組み合わせだけページにする
COMBO_PAIRS = [("purpose", "stage"), ("type", "activity")]
COMBO_LABEL = {"purpose": "目的", "stage": "段階", "type": "種別", "activity": "活動の型"}
SLUG = {
    "ビジョン浸透": "vision", "エンゲージメント": "engagement", "イノベーション": "innovation",
    "ナレッジ共有": "knowledge", "部門横断": "cross-functional", "オンボーディング": "onboarding",
    "LTV・継続": "ltv", "共創・商品開発": "co-creation", "サポート効率化": "support", "口コミ・認知": "awareness",
    "ブランド体験": "brand-experience",
    "事業共創・協業": "business-collaboration", "起業・成長支援": "startup-support", "投資・資金調達": "investment",
    "採用・人材": "hiring", "拠点・地域の活性化": "hub-and-region", "業界の学び合い": "industry-learning",
    "立ち上げ期": "launch", "成長期": "growth", "成熟期": "mature", "転換期": "transition",
    "社内": "internal", "ファン・顧客": "fan", "多企業": "multi",
    "ナレッジ共有型": "knowledge-sharing", "プロジェクト型": "project", "趣味親睦型": "social",
}


def combo_values(c, key):
    return {"purpose": c["_purpose"], "activity": c["_activity"],
            "stage": [c.get("段階")], "type": [c.get("種別")]}[key]


def find_combos(cases):
    """件数が COMBO_MIN 以上の組み合わせ。値に slug がないもの（選択肢の外の値）は飛ばす。"""
    combos = []
    for a, b in COMBO_PAIRS:
        groups = {}
        for c in cases:
            for x in combo_values(c, a):
                for y in combo_values(c, b):
                    if x in SLUG and y in SLUG:
                        groups.setdefault((x, y), []).append(c)
        order_a = {"purpose": PURPOSE_ORDER, "type": TYPE_ORDER}[a]
        order_b = {"stage": STAGE_ORDER, "activity": ["ナレッジ共有型", "プロジェクト型", "趣味親睦型"]}[b]
        for (x, y), cs in sorted(groups.items(), key=lambda kv: (order_a.index(kv[0][0]) if kv[0][0] in order_a else 99,
                                                                  order_b.index(kv[0][1]) if kv[0][1] in order_b else 99)):
            if len(cs) >= COMBO_MIN:
                combos.append({"a": a, "b": b, "x": x, "y": y, "cases": cs,
                               "key": f"{COMBO_LABEL[a]}={x}|{COMBO_LABEL[b]}={y}",
                               "path": f"combos/{a}-{b}/{SLUG[x]}-{SLUG[y]}/"})
    return combos


def load_combo_notes():
    path = os.path.join(ROOT, "config", "combo_notes.json")
    if not os.path.exists(path):
        return {}, ""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("notes", {}), data.get("written", "")


def breakdown(cs, f, order=None):
    counts = {}
    for c in cs:
        for v in f(c):
            if v:
                counts[v] = counts.get(v, 0) + 1
    items = sorted(counts.items(), key=lambda kv: (order.index(kv[0]) if order and kv[0] in order else 99, -kv[1], kv[0]))
    return "、".join(f"{k} {v}件" for k, v in items)


def build_combo(cfg, combo, notes, written):
    a, b, x, y, cs = combo["a"], combo["b"], combo["x"], combo["y"], combo["cases"]
    la, lb = COMBO_LABEL[a], COMBO_LABEL[b]
    title = f"{x}×{y}"
    note = notes.get(combo["key"], "")
    note_html = ""
    if note:
        d = to_date(written)
        when = f"{fmt_day(d)}時点の" if d else ""
        note_html = f"""<section class="block hint combo-note">
  <h2>この組み合わせの傾向<span class="ai-label">AIによる解釈</span></h2>
  <p>{esc(note)}</p>
  <p class="hint-note">{when}事例の目的・段階・活動の型などのタグから、AIがまとめた傾向です。各社の取り組みを評価したものではありません。</p>
</section>"""
    rows = []
    if a != "type" and b != "type":
        rows.append(("種別", breakdown(cs, lambda c: [c.get("種別")], TYPE_ORDER)))
    if b != "stage":
        rows.append(("段階", breakdown(cs, lambda c: [c.get("段階")], STAGE_ORDER)))
    if b != "activity":
        rows.append(("活動の型", breakdown(cs, lambda c: c["_activity"], ["ナレッジ共有型", "プロジェクト型", "趣味親睦型"])))
    rows.append(("場", breakdown(cs, lambda c: [c.get("場")], PLACE_ORDER)))
    if a != "purpose":
        rows.append(("目的", breakdown(cs, lambda c: c["_purpose"], PURPOSE_ORDER)))
    else:
        rows.append(("ほかの目的", breakdown(cs, lambda c: [p for p in c["_purpose"] if p != x], PURPOSE_ORDER)))
    stats = "".join(f"<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>" for k, v in rows if v)
    qs = urllib.parse.urlencode({a: x, b: y})
    cs_sorted = sorted(cs, key=lambda c: (-(int(score_value(c.get("観測スコア")) or -1)), c["ID"]))
    body = f"""
<article class="wrap combo">
  <nav class="crumbs" aria-label="パンくずリスト"><ol><li><a href="../../../">事例一覧</a></li><li><a href="../../">組み合わせ</a></li><li aria-current="page">{esc(title)}</li></ol></nav>
  <header class="case-head">
    <p class="combo-axes">{esc(la)}「{esc(x)}」×{esc(lb)}「{esc(y)}」</p>
    <h1>{esc(title)}</h1>
    <p class="case-meta">{esc(la)}が「{esc(x)}」で、{esc(lb)}が「{esc(y)}」の事例は{len(cs)}件です。</p>
  </header>
  {note_html}
  <dl class="source-meta combo-stats">{stats}</dl>
  <p class="combo-filter"><a href="../../../?{esc(qs)}">事例一覧でこの条件を開く</a>（ほかの条件も重ねて絞り込めます）</p>
  <h2 class="combo-list-head">事例<small>{len(cs)}件</small></h2>
  <ul class="cards">
    {''.join(card(c, "../../../") for c in cs_sorted)}
  </ul>
</article>
"""
    desc = f"{la}が「{x}」で、{lb}が「{y}」の企業コミュニティの事例{len(cs)}件。" + (shorten(note, 60) if note else "")
    return page(cfg, title=f"{title}の事例", description=desc, path=combo["path"], body=body, depth=3)


# 組み合わせの一覧で、段階・種別・活動の型に添える絵（Noto Emoji。assets/emoji/ のファイル名）。目的の絵は config の purpose_icons
AXIS_ICONS = {"立ち上げ期": "1f680", "成長期": "1f4c8", "成熟期": "1f333", "転換期": "1f504",
              "ファン・顧客": "1f64c", "社内": "1f3e2", "多企業": "1f3d9",
              "ナレッジ共有型": "1f4ac", "プロジェクト型": "1f6e0", "趣味親睦型": "2615"}
ACTIVITY_ORDER = ["ナレッジ共有型", "プロジェクト型", "趣味親睦型"]


def build_combos_index(cfg, combos, cases):
    # 組み合わせから探す（2026-11-05 の見本で選んだ案1）：目的×段階を地図（マス目）にし、件数が多いマスほど濃い空色にする。
    # COMBO_MIN 件以上のマスは、その組み合わせのページへのリンク。足りないマスは点線で薄く出す。種別×活動の型は9つのタイル（2026-11-06 から。種別3つ×活動の型3つ）
    icons = cfg.get("purpose_icons") or {}
    paths = {(cb["x"], cb["y"]): cb["path"].removeprefix("combos/") for cb in combos}

    def emoji(code, size):
        return f'<img src="../assets/emoji/{code}.png" alt="" width="{size}" height="{size}">'

    counts = Counter()
    for c in cases:
        for p in c["_purpose"]:
            counts[(p, c.get("段階"))] += 1
        for a in c["_activity"]:
            counts[(c.get("種別"), a)] += 1
    purposes = [p for p in sorted(PURPOSE_ORDER, key=lambda p: -sum(counts[(p, s)] for s in STAGE_ORDER))
                if any(counts[(p, s)] for s in STAGE_ORDER)]
    top = max([counts[(p, s)] for p in purposes for s in STAGE_ORDER] or [1])

    head = "".join(f'<th scope="col">{emoji(AXIS_ICONS[s], 24)}<span>{esc(s)}</span></th>' for s in STAGE_ORDER)
    rows = []
    for i, p in enumerate(purposes):
        cells = []
        for s in STAGE_ORDER:
            n = counts[(p, s)]
            if (p, s) in paths:
                lv = min(4, 1 + n * 4 // (top + 1))
                cells.append(f'<td><a class="cell lv{lv}" href="{paths[(p, s)]}" aria-label="{esc(p)}×{esc(s)} {n}件"'
                             f' data-goatcounter-click="combo/{esc(p)}×{esc(s)}">{n}</a></td>')
            else:
                cells.append(f'<td><span class="cell lv0">{n or ""}<span class="visually-hidden">{n}件</span></span></td>')
        rows.append(f'<tr style="--i: {min(i, 10)}"><th scope="row">{emoji(icons.get(p, "1f4cc"), 22)}<span>{esc(p)}</span></th>{"".join(cells)}</tr>')

    tiles = []
    for t in TYPE_ORDER:
        for a in ACTIVITY_ORDER:
            n = counts[(t, a)]
            inner = (f'<span class="ta-icons">{emoji(AXIS_ICONS[t], 28)}{emoji(AXIS_ICONS[a], 28)}</span>'
                     f'<span class="ta-num">{n}</span><span class="ta-name">{esc(t)}<br>×{esc(a)}</span>')
            if (t, a) in paths:
                tiles.append(f'<a class="ta" href="{paths[(t, a)]}" data-goatcounter-click="combo/{esc(t)}×{esc(a)}">{inner}</a>')
            else:
                tiles.append(f'<span class="ta off">{inner}</span>')
    body = f"""
<article class="wrap combos-page">
  <h1>組み合わせから探す</h1>
  <p class="lead">目的と段階を掛け合わせた地図です。色が濃いマスほど、事例が多い組み合わせです。数字を押すと、その組み合わせの事例と、事例のタグからAIがまとめた傾向の解説が開きます。</p>
  <h2 class="combos-head">{emoji("1f5fa", 26)}目的×段階の地図</h2>
  <div class="map-wrap"><table class="map">
    <caption class="visually-hidden">目的と段階の組み合わせごとの事例の数</caption>
    <thead><tr><td></td>{head}</tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table></div>
  <p class="map-note">点線のマスは、事例がまだ{COMBO_MIN}件に満たない組み合わせです。</p>
  <h2 class="combos-head">{emoji("1f64c", 26)}種別×活動の型</h2>
  <div class="tas">{"".join(tiles)}</div>
</article>
"""
    return page(cfg, title="組み合わせから探す", description="目的×段階、種別×活動の型の組み合わせごとに、企業コミュニティの事例をまとめています。",
                path="combos/", body=body, depth=1)
