"""新着と更新：data/latest.csv の履歴から新しく載せた事例・更新した事例を見つけ、/new/ と RSS を作る。"""

from .core import *  # noqa: F401,F403
from . import core
from .parts import *  # noqa: F401,F403
from .notes import *  # noqa: F401,F403


# ---------- 新着と更新 ----------

# 「更新」として数える列。確認日・観測スコア・検索用キーワード・規模の区分・AIのヒントは、変わっても更新に数えない
UPDATE_FIELDS = ["企業名", "コミュニティ名", "業種", "開始年", "規模", "目的", "段階", "活動の型", "場", "ツール",
                 "主な施策", "公開されている成果", "運営体制", "工夫のポイント", "出典URL", "出典の時期"]
HISTORY_LIMIT = 200   # 読む履歴の数（毎日1回の記録なら、およそ半年分）
NEW_DAYS = 90         # 新着と更新のページに載せる期間（日）


def load_history():
    """data/latest.csv の git の履歴を、古い順に [(日付, {ID: 行})] で返す。
    履歴が読めない（git がない、Actions で fetch-depth が浅い）ときは空のリスト。"""
    try:
        log = subprocess.run(["git", "log", f"-{HISTORY_LIMIT}", "--format=%H %cI", "--", "data/latest.csv"],
                             cwd=ROOT, capture_output=True, text=True, check=True, timeout=30).stdout.split()
    except Exception:  # noqa: BLE001
        return []
    snaps = []
    for sha, when in zip(log[0::2], log[1::2]):
        try:
            text = subprocess.run(["git", "show", f"{sha}:data/latest.csv"], cwd=ROOT, capture_output=True,
                                  check=True, timeout=30).stdout.decode("utf-8-sig")
        except Exception:  # noqa: BLE001
            continue
        rows = {}
        for r in csv.DictReader(io.StringIO(text)):
            r = {(k or "").strip(): (v or "").strip() for k, v in r.items()}
            if r.get("ID"):
                rows[r["ID"]] = r
        day = datetime.fromisoformat(when.replace("Z", "+00:00")).astimezone(JST).date()
        snaps.append((day, rows))
    snaps.reverse()
    return snaps




def find_changes(cases, history, today):
    """新しく出た事例と、内容が変わった事例を返す。
    新着の日付は確認日（U列）。確認日が空なら、履歴で初めて出た日。履歴がなければ確認日だけで新着を出す。"""
    by_id = {c["ID"]: c for c in cases}
    snaps = history + [(today, {c["ID"]: c.get("_row", c) for c in cases})]
    first_seen, updates = {}, []
    if len(snaps) >= 2:
        base_day, prev = snaps[0]
        for cid in prev:
            first_seen[cid] = None          # 履歴の一番古い時点にすでにあった事例は、新着に数えない
        for day, cur in snaps[1:]:
            for cid, row in cur.items():
                if cid not in first_seen:
                    first_seen[cid] = day
                elif cid in prev:
                    changed = [f for f in UPDATE_FIELDS if f in row and f in prev[cid] and row[f] != prev[cid][f]]
                    if row.get("種別") != prev[cid].get("種別"):
                        # 種別を変えた行（2026-11-06 の多企業への移しかえ）は、同時に選び直した目的の差分を更新に数えない（黒田さんの判断）
                        changed = [f for f in changed if f != "目的"]
                    if changed:
                        updates.append({"id": cid, "date": day, "fields": changed})
            prev = cur
    new = []
    for c in cases:
        checked = to_date(c.get("確認日"))
        if history:
            if first_seen.get(c["ID"]) is None:
                continue
            day = checked or first_seen[c["ID"]]
        else:
            if not checked:
                continue
            day = checked
        new.append({"id": c["ID"], "date": day})
    since = today - timedelta(days=NEW_DAYS)
    new = [n for n in new if n["date"] >= since and n["id"] in by_id]
    # 同じ事例の更新は新しいものだけを残し、新着と同じ日の更新は出さない
    latest = {}
    for u in updates:
        if u["id"] in by_id and u["date"] >= since:
            latest[u["id"]] = u
    new_day = {n["id"]: n["date"] for n in new}
    updates = [u for u in latest.values() if new_day.get(u["id"]) != u["date"]]
    new.sort(key=lambda n: (n["date"], n["id"]), reverse=True)
    updates.sort(key=lambda u: (u["date"], u["id"]), reverse=True)
    return new, updates, bool(history)




STRIP_MAX = 10  # 日ごとの帯に出す事例の数。超えた分は「すべて見る」で開く


def build_new(cfg, cases, new, updates, has_history, updated):
    # 新着（2026-11-05 の見本で選んだ「日めくりのタイムライン」）：日付を日めくりの形にして縦の線でつなぎ、
    # 日ごとに「○件を新しく載せ、○件を更新しました」→ その日に載せた事例の帯 → 更新した項目の札と、更新した事例の一覧（開く）
    by_id = {c["ID"]: c for c in cases}
    icons = cfg.get("purpose_icons") or {}

    def item(cid, extra=""):
        c = by_id[cid]
        return (f'<li><a href="../cases/{esc(cid)}/">{type_badge(c.get("種別"))}'
                f'<span class="rel-company">{esc(c["企業名"])}</span><span class="new-title">{esc(c["_title"])}</span></a>{extra}</li>')

    def card(cid):
        c = by_id[cid]
        chips = "".join(f'<span class="tl-purpose"><img src="../assets/emoji/{icons.get(p, "1f4cc")}.png" alt="" width="16" height="16">{esc(p)}</span>'
                        for p in c["_purpose"][:2])
        return (f'<a class="rel tl-card" href="../cases/{esc(cid)}/">{type_badge(c.get("種別"))}'
                f'<small>{esc(c["企業名"])}</small><strong>{esc(c["_title"])}</strong>'
                f'{f"<span class=tl-purposes>{chips}</span>" if chips else ""}</a>')

    days = {}
    for e in new:
        days.setdefault(e["date"], {"new": [], "upd": []})["new"].append(e)
    for e in updates:
        days.setdefault(e["date"], {"new": [], "upd": []})["upd"].append(e)
    rows = []
    for i, day in enumerate(sorted(days, reverse=True)):
        nw, up = days[day]["new"], days[day]["upd"]
        if nw and up:
            summary = f'<b>{len(nw)}</b>件を新しく載せ、<b>{len(up)}</b>件を更新しました'
        elif nw:
            summary = f'<b>{len(nw)}</b>件を新しく載せました'
        else:
            summary = f'<b>{len(up)}</b>件を更新しました'
        parts = []
        if nw:
            parts.append(f'<div class="tl-strip">{"".join(card(e["id"]) for e in nw[:STRIP_MAX])}</div>')
            if len(nw) > STRIP_MAX:
                parts.append(f'<details class="tl-more"><summary>この日に載せた事例をすべて見る（{len(nw)}件）</summary>'
                             f'<ul class="new-list">{"".join(item(e["id"]) for e in nw)}</ul></details>')
        if up:
            counts = Counter(f for e in up for f in e["fields"])
            chips = "".join(f'<span class="tl-field">{esc(f)}<b>{n}</b></span>' for f, n in counts.most_common(4))
            parts.append(f'<p class="tl-fields"><img src="../assets/emoji/270f.png" alt="" width="18" height="18">更新した項目 {chips}</p>')
            upd_items = "".join(item(e["id"], f'<p class="changed">更新した項目：{esc("、".join(e["fields"]))}</p>') for e in up)
            parts.append(f'<details class="tl-more"><summary>更新した事例を見る（{len(up)}件）</summary><ul class="new-list">{upd_items}</ul></details>')
        rows.append(f"""
    <li style="--i: {min(i, 6)}">
      <div class="tl-cal" aria-hidden="true"><span class="tl-m">{day.month}月</span><span class="tl-d">{day.day}</span></div>
      <div class="tl-body">
        <h2 class="tl-sum"><span class="visually-hidden">{fmt_day(day)}：</span>{summary}</h2>
        {"".join(parts)}
      </div>
    </li>""")
    timeline = (f'<ol class="timeline">{"".join(rows)}</ol>' if rows
                else "<p>この期間に新しく載せた事例や、内容を更新した事例はありません。</p>")
    how = ("新しく載せた事例の日付は、運営側で出典を確かめた日（確認日）です。確認日がない事例は、サイトに初めて載った日にしています。"
           "内容を更新した事例は、毎日のデータの読み込みで前日と比べて、本文や出典などが変わったものです。")
    if not has_history:
        how = "新しく載せた事例の日付は、運営側で出典を確かめた日（確認日）です。"
    body = f"""
<article class="wrap new-page">
  <h1>新着</h1>
  <p class="lead">この{NEW_DAYS}日間に新しく載せた事例と、内容を更新した事例を、日ごとにまとめています。{how}</p>
  <p class="feed-link"><a href="../feed.xml">RSSで受け取る</a></p>
  {timeline}
</article>
"""
    return page(cfg, title="新着", description=f"{cfg['name']}に新しく載せた事例と、内容を更新した事例の一覧です。",
                path="new/", body=body, depth=1)


def build_feed(cfg, cases, new, updates, notes=()):
    """RSS 2.0。新着と更新を新しい順に50件まで。"""
    from email.utils import format_datetime
    by_id = {c["ID"]: c for c in cases}
    base = cfg["base_url"].rstrip("/")
    entries = [("新着", n) for n in new] + [("更新", u) for u in updates]
    entries += [(NOTES_LABEL, {"date": n["published"], "id": "~" + n["slug"], "note": n}) for n in notes]
    entries.sort(key=lambda e: (e[1]["date"], e[1]["id"]), reverse=True)
    items = []

    def enclosure(name):
        """RSS の項目に添える画像（事例ごと・図鑑ノートごとの共有画像。観測所と同じ。2026-11-07）。画像がないときは付けない"""
        f = os.path.join(OUT, "og", name)
        if not os.path.exists(f):
            return ""
        return f'\n    <enclosure url="{esc(base)}/og/{esc(name)}" type="image/png" length="{os.path.getsize(f)}"/>'
    for kind, e in entries[:50]:
        if kind == NOTES_LABEL:
            n = e["note"]
            when = datetime(n["published"].year, n["published"].month, n["published"].day, 9, 0, tzinfo=JST)
            items.append(f"""  <item>
    <title>{esc(f"【{NOTES_LABEL}】{n['title']}")}</title>
    <link>{esc(f"{base}/notes/{n['slug']}/")}</link>
    <guid isPermaLink="false">{esc(f"note-{n['slug']}")}</guid>
    <pubDate>{format_datetime(when)}</pubDate>
    <description>{esc(n['description'])}</description>{enclosure(f"note-{n['slug']}.png")}
  </item>""")
            continue
        c = by_id[e["id"]]
        url = f"{base}/cases/{c['ID']}/"
        when = datetime(e["date"].year, e["date"].month, e["date"].day, 9, 0, tzinfo=JST)
        desc = shorten(c.get("工夫のポイント") or c.get("主な施策") or "", 200)
        if kind == "更新":
            desc = f"更新した項目：{'、'.join(e['fields'])}。" + desc
        items.append(f"""  <item>
    <title>{esc(f"【{kind}】{c['企業名']} {c['_title']}")}</title>
    <link>{esc(url)}</link>
    <guid isPermaLink="false">{esc(f"{c['ID']}-{kind}-{e['date'].isoformat()}")}</guid>
    <pubDate>{format_datetime(when)}</pubDate>
    <description>{esc(desc)}</description>{enclosure(f"{c['ID']}.png")}
  </item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
  <title>{esc(cfg['name'])}｜新着</title>
  <link>{esc(base)}/new/</link>
  <atom:link href="{esc(base)}/feed.xml" rel="self" type="application/rss+xml"/>
  <description>{esc(cfg['description'])}</description>
  <language>ja</language>
  <lastBuildDate>{format_datetime(datetime.now(JST))}</lastBuildDate>
{chr(10).join(items)}
</channel>
</rss>
"""
