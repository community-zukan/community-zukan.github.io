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
import hashlib
import csv
import html
import io
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from collections import Counter
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
    ("size", "規模の区分", "規模の区分"),
]
STAGE_ORDER = ["立ち上げ期", "成長期", "成熟期", "転換期"]
PLACE_ORDER = ["オンライン", "オフライン", "両方"]
SIZE_ORDER = ["〜100人", "100〜1,000人", "1,000〜1万人", "1万人超"]
PURPOSE_ORDER = [
    "ビジョン浸透", "エンゲージメント", "イノベーション", "ナレッジ共有",
    "部門横断", "オンボーディング",
    "LTV・継続", "共創・商品開発", "サポート効率化", "口コミ・認知", "ブランド体験",
]
# サイトでの目的の名前。シートの値が長くタイルで2行になるものだけ短くする（2026-11-05 黒田さんの判断）。
# 読み込むときに置き換えるので、絞り込み・URL・組み合わせのページもすべて短い名前になる。シートの値は変えない
PURPOSE_RENAME = {"ナレッジ共有・継承": "ナレッジ共有", "定着・オンボーディング": "オンボーディング"}
TYPE_LABEL = {"社内": "社内", "ファン・顧客": "ファン・顧客"}



def ver(name):
    """assets/ のファイルの中身から短い版の印を作る。更新したとき、古いCSSやJavaScriptがブラウザに残らないようにする。"""
    try:
        with open(os.path.join(ROOT, "assets", name), "rb") as f:
            return hashlib.sha1(f.read()).hexdigest()[:8]
    except OSError:
        return "0"

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


def normalize(text):
    """検索用にそろえる：全角英数を半角に、大文字を小文字に、ひらがなをカタカナに（assets/app.js と同じ）。"""
    import unicodedata
    text = unicodedata.normalize("NFKC", text or "").lower()
    return "".join(chr(ord(ch) + 0x60) if "ぁ" <= ch <= "ゖ" else ch for ch in text)


_KAKASI = None


def reading(text):
    """漢字の読み（カタカナ）。ひらがなでも探せるように検索の対象に入れる。
    pykakasi が入っているとき（Actions では入れる）だけ作り、なければ空文字（ひらがな検索ができないだけで、ほかは変わらない）。"""
    global _KAKASI
    if _KAKASI is None:
        try:
            import pykakasi
            _KAKASI = pykakasi.kakasi()
        except ImportError:
            _KAKASI = False
    if not _KAKASI or not text:
        return ""
    return normalize("".join(part["kana"] for part in _KAKASI.convert(text)))


def load_synonyms():
    """config/synonyms.json の言い換え表。読みは「どのグループに当たるか」の判定にだけ使う。"""
    path = os.path.join(ROOT, "config", "synonyms.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        groups = json.load(f).get("groups", [])
    out = []
    for g in groups:
        if not isinstance(g, list):
            continue
        words = sorted({normalize(w) for w in g if w.strip()})
        readings = sorted({reading(w) for w in g if w.strip()} - {""} - set(words))
        out.append({"words": words, "readings": readings})
    return out


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
    """出典URL（「 / 」区切りで2つまで）を分ける。URLの中の半角スペース（ファイル名など）は %20 にする。
    以前は空白でも区切っていたため、スペースを含むURLが途中で切れていた。"""
    urls = []
    for part in re.split(r"\s+/\s+", (v or "").strip()):
        # 「 / 」を使わずに空白だけで並べたURLも分ける（次の http の手前で区切る）
        for u in re.split(r"\s+(?=https?://)", part.strip()):
            u = u.strip()
            if u.startswith("http"):
                urls.append(re.sub(r"\s", "%20", u))
    return urls


def domain(u):
    m = re.match(r"https?://([^/]+)", u)
    return m.group(1).removeprefix("www.") if m else u


def shorten(s, n):
    s = re.sub(r"\s+", " ", s or "")
    return s if len(s) <= n else s[: n - 1].rstrip("、。 ") + "…"


def date_key(v):
    """確認日を並べ替え用の 20261104 の形にする。空欄や読めない値は空文字。"""
    m = re.match(r"(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})", v or "")
    return f"{m.group(1)}{int(m.group(2)):02d}{int(m.group(3)):02d}" if m else ""


def score_value(v):
    """観測スコア（0〜100）。列がない・空欄・数値でないときは空文字。"""
    try:
        return str(round(float((v or "").strip())))
    except ValueError:
        return ""


def fmt_month(v):
    """出典の時期（'2025/12 など）を「2025年12月」にする。読めないときはそのまま。"""
    v = (v or "").strip().lstrip("'")
    m = re.match(r"(\d{4})\s*[-/.年]\s*(\d{1,2})", v)
    return f"{m.group(1)}年{int(m.group(2))}月" if m else v


def fmt_date(v):
    m = re.match(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", v or "")
    return f"{m.group(1)}年{int(m.group(2))}月{int(m.group(3))}日" if m else (v or "")


def enrich(cfg, rows):
    cases = []
    for r in rows:
        c = dict(r)
        c["_purpose"] = [PURPOSE_RENAME.get(p, p) for p in split_multi(r.get("目的"))]
        c["_activity"] = split_multi(r.get("活動の型"))
        c["_industry"] = industry_group(cfg, r.get("業種"))
        c["_urls"] = split_urls(r.get("出典URL"))
        c["_title"] = r.get("コミュニティ名") or f"{r['企業名']}のコミュニティ"
        cases.append(c)
    return cases


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


def to_date(v):
    k = date_key(v)
    return datetime.strptime(k, "%Y%m%d").date() if k else None


def find_changes(cases, history, today):
    """新しく出た事例と、内容が変わった事例を返す。
    新着の日付は確認日（U列）。確認日が空なら、履歴で初めて出た日。履歴がなければ確認日だけで新着を出す。"""
    by_id = {c["ID"]: c for c in cases}
    snaps = history + [(today, {c["ID"]: c for c in cases})]
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


def fmt_day(d):
    return f"{d.year}年{d.month}月{d.day}日"


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
    for kind, e in entries[:50]:
        if kind == NOTES_LABEL:
            n = e["note"]
            when = datetime(n["published"].year, n["published"].month, n["published"].day, 9, 0, tzinfo=JST)
            items.append(f"""  <item>
    <title>{esc(f"【{NOTES_LABEL}】{n['title']}")}</title>
    <link>{esc(f"{base}/notes/{n['slug']}/")}</link>
    <guid isPermaLink="false">{esc(f"note-{n['slug']}")}</guid>
    <pubDate>{format_datetime(when)}</pubDate>
    <description>{esc(n['description'])}</description>
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
    <description>{esc(desc)}</description>
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


# ---------- 組み合わせのページ ----------

COMBO_MIN = 5   # この件数以上の組み合わせだけページにする
COMBO_PAIRS = [("purpose", "stage"), ("type", "activity")]
COMBO_LABEL = {"purpose": "目的", "stage": "段階", "type": "種別", "activity": "活動の型"}
SLUG = {
    "ビジョン浸透": "vision", "エンゲージメント": "engagement", "イノベーション": "innovation",
    "ナレッジ共有": "knowledge", "部門横断": "cross-functional", "オンボーディング": "onboarding",
    "LTV・継続": "ltv", "共創・商品開発": "co-creation", "サポート効率化": "support", "口コミ・認知": "awareness",
    "ブランド体験": "brand-experience",
    "立ち上げ期": "launch", "成長期": "growth", "成熟期": "mature", "転換期": "transition",
    "社内": "internal", "ファン・顧客": "fan",
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
        order_a = {"purpose": PURPOSE_ORDER, "type": ["ファン・顧客", "社内"]}[a]
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
        rows.append(("種別", breakdown(cs, lambda c: [c.get("種別")], ["ファン・顧客", "社内"])))
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
              "ファン・顧客": "1f64c", "社内": "1f3e2",
              "ナレッジ共有型": "1f4ac", "プロジェクト型": "1f6e0", "趣味親睦型": "2615"}
ACTIVITY_ORDER = ["ナレッジ共有型", "プロジェクト型", "趣味親睦型"]


def build_combos_index(cfg, combos, cases):
    # 組み合わせから探す（2026-11-05 の見本で選んだ案1）：目的×段階を地図（マス目）にし、件数が多いマスほど濃い空色にする。
    # COMBO_MIN 件以上のマスは、その組み合わせのページへのリンク。足りないマスは点線で薄く出す。種別×活動の型は6つのタイル
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
    for t in ["ファン・顧客", "社内"]:
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


# ---------- 図鑑ノート（テーマごとに事例を読み比べる記事） ----------
# 原稿は notes/<スラッグ>.md（名前が「_」で始まるファイルは読まない）。先頭の --- で囲んだ部分に題名などを書き、
# 本文は次の書き方だけを使う。書き方の決めごとは notes/_guide.md。
#   ## 見出し / ### 小見出し / 空行で段落 / 「- 」で箇条書き / [文字](URL) でリンク / **強調**
#   :::case S75   ← 事例を1件差し込む（企業名・コミュニティ名・目的の札はデータから入る）
#   黒田のひとこと（次の ::: までの段落）
#   :::
# 公開日（published）がない原稿と、draft: true の原稿は出さない。
# 見た目は 2026-11-05 の見本で選んだもの：記事は「表から読み物へ」（案3）、冒頭と画像は薄い空色の地（案B）。
NOTES_DIR = os.path.join(ROOT, "notes")
NOTES_LABEL = "図鑑ノート"
NOTES_PUBLIC = False   # 公開する記事が1本でもあれば True（メニューに「図鑑ノート」を出す）


def parse_note_file(path):
    with open(path, encoding="utf-8") as f:
        text = f.read().replace("\r\n", "\n")
    meta, body = {}, text
    if text.startswith("---\n"):
        head, _, body = text[4:].partition("\n---\n")
        for line in head.split("\n"):
            if ":" in line:
                k, _, v = line.partition(":")
                meta[k.strip()] = v.strip()
    slug = os.path.splitext(os.path.basename(path))[0]
    return {"slug": slug, "title": meta.get("title", slug), "description": meta.get("description", ""),
            "kind": meta.get("kind", ""), "emoji": meta.get("emoji", "") or "1f4d3",
            "published": to_date(meta.get("published", "")), "updated": to_date(meta.get("updated", "")),
            "draft": meta.get("draft", "").lower() in ("true", "yes", "1"), "body": body,
            "ids": re.findall(r"^:::case\s+(\S+)", body, re.M)}


def load_notes(cases=None):
    """公開する図鑑ノート（新しい順）。掲載していない事例を差し込んでいたら知らせる（記事からは外して出す）。"""
    if not os.path.isdir(NOTES_DIR):
        return []
    known = {c["ID"] for c in cases} if cases is not None else None
    notes = []
    for name in sorted(os.listdir(NOTES_DIR)):
        if not name.endswith(".md") or name.startswith("_"):
            continue
        n = parse_note_file(os.path.join(NOTES_DIR, name))
        if n["draft"]:
            continue
        if not n["published"]:
            print(f"注意: 図鑑ノート {name} に published（公開日）がないので公開しません")
            continue
        if known is not None:
            for i in n["ids"]:
                if i not in known:
                    print(f"注意: 図鑑ノート {name} の事例 {i} は掲載していないので、記事から外して表示します")
        notes.append(n)
    notes.sort(key=lambda n: (n["published"], n["slug"]), reverse=True)
    return notes


def note_inline(text):
    out = esc(text)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)

    def link(m):
        label, url = m.group(1), m.group(2)
        ext = url.startswith("http") and not url.startswith("https://community-zukan.github.io")
        attrs = ' target="_blank" rel="noopener"' if ext else ""
        mark = "\u2060↗" if ext else ""
        return f'<a href="{url}"{attrs}>{label}{mark}</a>'
    return re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, out)


def note_blocks(text):
    html_out = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [l for l in block.split("\n") if l.strip()]
        if not lines:
            continue
        if lines[0].startswith("### "):
            html_out.append(f"<h3>{note_inline(lines[0][4:].strip())}</h3>")
            lines = lines[1:]
        elif lines[0].startswith("## "):
            title = lines[0][3:].strip()
            html_out.append(f'<h2 id="{esc(title)}">{note_inline(title)}</h2>')
            lines = lines[1:]
        if not lines:
            continue
        if all(l.startswith("- ") for l in lines):
            html_out.append("<ul>" + "".join(f"<li>{note_inline(l[2:].strip())}</li>" for l in lines) + "</ul>")
        else:
            html_out.append("<p>" + "<br>".join(note_inline(l.strip()) for l in lines) + "</p>")
    return "\n".join(html_out)


def note_pick(cfg, c, comment_html, num, rel):
    icons = cfg.get("purpose_icons") or {}
    chips = "".join(f'<span class="tl-purpose"><img src="{rel}assets/emoji/{icons.get(p, "1f4cc")}.png" alt="" width="16" height="16">{esc(p)}</span>'
                    for p in c["_purpose"][:2])
    word = f'<div class="pick-word"><p class="pick-who">黒田のひとこと</p>{comment_html}</div>' if comment_html else ""
    return (f'<section class="pick" id="pick-{esc(c["ID"])}"><a class="pick-card" href="{rel}cases/{esc(c["ID"])}/">'
            f'<span class="pick-num" aria-hidden="true">{num:02d}</span><span class="pick-body">'
            f'<span class="card-top">{type_badge(c.get("種別"))}<span class="card-company">{esc(c["企業名"])}</span></span>'
            f'<strong>{esc(c["_title"])}</strong><span class="tl-purposes">{chips}</span></span></a>{word}</section>')


def note_cases(n, by_id):
    return [by_id[i] for i in n["ids"] if i in by_id]


def note_html(cfg, n, by_id, rel):
    parts = re.split(r"^:::case\s+(\S+)\s*\n(.*?)^:::\s*$", n["body"], flags=re.M | re.S)
    out = [note_blocks(parts[0])]
    num = 0
    for i in range(1, len(parts), 3):
        c = by_id.get(parts[i])
        if c:
            num += 1
            out.append(note_pick(cfg, c, note_blocks(parts[i + 1]), num, rel))
        out.append(note_blocks(parts[i + 2]))
    return "\n".join(out)


def note_title_html(t):
    # 「。」「、」と閉じかっこのところで区切り、言葉の途中で折り返さないようにする（観測所と同じ）
    return "".join(f"<span>{esc(x)}</span>" for x in re.findall(r"[^。、）」』]+[。、）」』]*", t))


def note_emoji(n, rel):
    code = n["emoji"] if os.path.exists(os.path.join(ROOT, "assets", "emoji", n["emoji"] + ".png")) else "1f4d3"
    return f'<img src="{rel}assets/emoji/{code}.png" alt="" width="64" height="64">'


def note_image(n, og_notes):
    return f"og/note-{n['slug']}.png" if n["slug"] in og_notes else "assets/ogp.png"


def note_list(notes, og_notes, rel):
    def li(n):
        meta = f"紹介する事例 {len(n['ids'])}件・{fmt_day(n['published'])}"
        return (f'<li><a href="{rel}notes/{esc(n["slug"])}/"><img class="note-card-img" src="{rel}{note_image(n, og_notes)}" alt="" loading="lazy" width="1200" height="630">'
                f'<span class="note-card-body"><strong>{esc(n["title"])}</strong><span>{esc(n["description"])}</span><small>{meta}</small></span></a></li>')
    return '<ul class="note-grid">' + "".join(li(n) for n in notes) + "</ul>"


def build_note(cfg, n, notes, by_id, og_notes):
    rel = "../../"
    cs = note_cases(n, by_id)
    rows = "".join(
        f'<tr><th scope="row"><a href="{rel}cases/{esc(c["ID"])}/"><span class="num">{i + 1:02d}</span>{esc(c["企業名"])}</a></th>'
        f'<td>{esc(c.get("段階") or "—")}</td><td>{esc(c.get("場") or "—")}</td><td>{esc(c.get("規模") or c.get("規模の区分") or "—")}</td>'
        f'<td>{esc(c.get("工夫のポイント") or "—")}</td></tr>' for i, c in enumerate(cs))
    table = (f'<h2 class="note-table-head"><img src="{rel}assets/emoji/1f4c4.png" alt="" width="24" height="24">この記事で紹介する{len(cs)}件を並べると</h2>'
             f'<div class="note-table-wrap"><table class="note-table"><thead><tr><th scope="col">事例</th><th scope="col">段階</th><th scope="col">場</th>'
             f'<th scope="col">規模</th><th scope="col">工夫のポイント</th></tr></thead><tbody>{rows}</tbody></table></div>') if cs else ""
    others = [o for o in notes if o is not n][:4]
    more = f'<section class="note-more"><h2>ほかの{NOTES_LABEL}</h2>{note_list(others, og_notes, rel)}</section>' if others else ""
    date = f"{fmt_day(n['published'])}公開" + (f"・{fmt_day(n['updated'])}更新" if n["updated"] else "")
    operator = esc(cfg.get("operator_url", ""))
    body = f"""
<article class="wrap note-page">
  <nav class="crumbs" aria-label="パンくずリスト"><ol><li><a href="{rel}">事例一覧</a></li><li><a href="../">{NOTES_LABEL}</a></li><li aria-current="page">{esc(n['title'])}</li></ol></nav>
  <header class="note-hero">
    <span class="note-hero-emoji" aria-hidden="true">{note_emoji(n, rel)}</span>
    <p class="note-pill">{NOTES_LABEL}{"｜" + esc(n["kind"]) if n["kind"] else ""}</p>
    <h1>{note_title_html(n['title'])}</h1>
    <p class="note-by">文：<a href="{operator}">黒田悠介</a>（コミュニティ研究家）<span>{date}</span></p>
  </header>
  {table}
  <div class="note-body">
{note_html(cfg, n, by_id, rel)}
  </div>
  <p class="note-end">紹介した取り組みは、出典が公開された時点のものです。くわしくは各事例のページの出典をご覧ください。</p>
  {more}
</article>
"""
    base = cfg["base_url"].rstrip("/") + "/"
    url = f"{base}notes/{n['slug']}/"
    ld = {"@context": "https://schema.org", "@type": "Article", "headline": n["title"], "description": n["description"],
          "inLanguage": "ja", "url": url, "image": base + note_image(n, og_notes),
          "datePublished": n["published"].isoformat(), "dateModified": (n["updated"] or n["published"]).isoformat(),
          "author": {"@type": "Person", "name": cfg.get("operator", "黒田悠介"), "jobTitle": "コミュニティ研究家", "url": cfg.get("operator_url", "")},
          "publisher": {"@type": "Organization", "name": cfg["name"], "url": base}}
    crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "事例一覧", "item": base},
        {"@type": "ListItem", "position": 2, "name": NOTES_LABEL, "item": base + "notes/"},
        {"@type": "ListItem", "position": 3, "name": n["title"], "item": url}]}
    return page(cfg, title=n["title"], description=n["description"], path=f"notes/{n['slug']}/", body=body, depth=2,
                og_image=note_image(n, og_notes), og_type="article", jsonld=[ld, crumbs])


def build_notes_index(cfg, notes, og_notes):
    rel = "../"
    body = f"""
<article class="wrap note-page">
  <nav class="crumbs" aria-label="パンくずリスト"><ol><li><a href="{rel}">事例一覧</a></li><li aria-current="page">{NOTES_LABEL}</li></ol></nav>
  <header class="note-hero note-hero-index">
    <span class="note-hero-emoji" aria-hidden="true"><img src="{rel}assets/emoji/1f4d3.png" alt="" width="64" height="64"></span>
    <h1>{NOTES_LABEL}</h1>
    <p class="note-lead"><span>テーマごとに公開事例を読み比べて、</span><span>コミュニティ研究家の黒田悠介が</span><span>まとめた記事です。</span></p>
    <p class="note-count"><b>{len(notes)}</b>本の記事</p>
  </header>
  {note_list(notes, og_notes, rel)}
</article>
"""
    return page(cfg, title=NOTES_LABEL, description="テーマごとに企業コミュニティの公開事例を読み比べて、コミュニティ研究家の黒田悠介がまとめた記事です。",
                path="notes/", body=body, depth=1)


def copy_og_notes(notes):
    """tools/make_og.py が作った図鑑ノートの画像（og-items/note-<スラッグ>.png）を /og/ に置く。"""
    found = set()
    for n in notes:
        f = os.path.join(ROOT, "og-items", f"note-{n['slug']}.png")
        if os.path.exists(f):
            os.makedirs(os.path.join(OUT, "og"), exist_ok=True)
            shutil.copy(f, os.path.join(OUT, "og", f"note-{n['slug']}.png"))
            found.add(n["slug"])
    return found


# ---------- HTML の部品 ----------


# ヘッダーのロゴ（ファビコンと同じ絵：本を開いた絵文字「📖」。Noto Emoji の絵を assets/icon.svg に置いている）
def logo_mark(rel):
    return f'<img class="logo-mark" src="{rel}assets/icon.svg?v={ver("icon.svg")}" alt="" width="30" height="30">'


def nav_links(rel, path):
    """ヘッダーのメニュー。いま開いているページには aria-current を付ける。"""
    items = [("", "事例一覧"), ("new/", "新着"), ("combos/", "組み合わせ")]
    if NOTES_PUBLIC:
        items.append(("notes/", NOTES_LABEL))
    items.append(("about/", "この図鑑について"))
    out = []
    for href, label in items:
        here = (path == href) if href == "" else path.startswith(href)
        cur = ' aria-current="page"' if here else ""
        out.append(f'<a href="{(rel + href) or "./"}"{cur}>{label}</a>')
    return "\n      ".join(out)


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
        text = json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")
        extra += f'<script type="application/ld+json">{text}</script>\n'
    if noindex:
        extra += '<meta name="robots" content="noindex">\n'
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
<link rel="icon" href="{rel}assets/icon.svg?v={ver('icon.svg')}" type="image/svg+xml">
<link rel="icon" href="{rel}assets/favicon-32.png?v={ver('favicon-32.png')}" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="{rel}assets/apple-touch-icon.png?v={ver('apple-touch-icon.png')}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Zen+Kaku+Gothic+New:wght@700;900&display=swap" rel="stylesheet">
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
    cls = "is-internal" if t == "社内" else "is-fan"
    return f'<span class="badge {cls}">{esc(TYPE_LABEL.get(t, t))}</span>'


def card(c, prefix=""):
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
        "size": c.get("規模の区分", ""),
        "year": c.get("開始年", ""),
        "checked": date_key(c.get("確認日")),
        "score": score_value(c.get("観測スコア")),
    }
    attrs = " ".join(f'data-{k}="{esc(v)}"' for k, v in data.items())
    # 検索用キーワード（X列）は画面には出さず、検索の対象にだけ入れる
    search = " ".join(c.get(k, "") for k in ["企業名", "コミュニティ名", "業種", "ツール", "主な施策", "工夫のポイント", "目的", "活動の型", "検索用キーワード"])
    # 企業名・コミュニティ名の読みを足して、ひらがなでも見つかるようにする
    yomi = reading(" ".join([c.get("企業名", ""), c.get("コミュニティ名", "")]))
    search = normalize(search) + (" " + yomi if yomi else "")
    return f"""<li class="card" {attrs} data-search="{esc(search)}">
  <a href="{prefix}cases/{esc(c['ID'])}/">
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
    order = {"stage": STAGE_ORDER, "place": PLACE_ORDER, "purpose": PURPOSE_ORDER, "size": SIZE_ORDER,
             "type": ["ファン・顧客", "社内"]}.get(key)
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
<section class="purposes wrap" aria-labelledby="purposes-title">
  <div class="strip-head">
    <h2 id="purposes-title">目的から探す</h2>
    <span class="strip-arrows" id="strip-arrows" hidden><button type="button" data-dir="-1" aria-label="前の目的へ">←</button><button type="button" data-dir="1" aria-label="次の目的へ">→</button></span>
  </div>
  <div class="strip-wrap"><div class="strip" id="purpose-strip">{''.join(tiles)}</div></div>
</section>"""


def build_index(cfg, cases):
    n_int = sum(1 for c in cases if c.get("種別") == "社内")
    n_fan = len(cases) - n_int
    filters = []
    for key, col, label in FACETS:
        opts = facet_values(cases, key)
        if not opts:
            continue
        chips = "".join(
            f'<label class="chip"><input type="checkbox" name="{key}" value="{esc(v)}"><span>{esc(v)}<small>{n}</small></span></label>'
            for v, n in opts
        )
        filters.append(f'<fieldset class="facet" data-facet="{key}"><legend>{esc(label)}</legend><div class="chips">{chips}</div></fieldset>')
    synonyms_json = json.dumps(load_synonyms(), ensure_ascii=False).replace("</", "<\\/")
    body = f"""
<section class="hero">
  <div class="wrap">
    <h1>企業のコミュニティ運営を、<br class="sp"><span class="mark">公開事例から知る</span></h1>
    <p class="lead">ファンコミュニティと社内コミュニティについて、プレスリリースや記事などの公開情報から事例を集めています。目的・段階・活動の型で絞り込んで、自社に近い事例を探せます。</p>
    <div class="stats">
      <div class="stat"><span class="stat-num" data-count="{len(cases)}">{len(cases)}</span><span class="stat-label">収録している事例</span></div>
      <div class="stat"><span class="stat-num" data-count="{n_fan}">{n_fan}</span><span class="stat-label">ファン・顧客</span></div>
      <div class="stat"><span class="stat-num" data-count="{n_int}">{n_int}</span><span class="stat-label">社内</span></div>
    </div>
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
      {''.join(filters)}
    </div>
  </details>
  <div class="result-bar">
    <p id="result-count" aria-live="polite">{len(cases)}件の事例</p>
    <p class="search-note" id="search-note" hidden></p>
    <button type="button" id="reset" class="link-button" hidden>条件をすべて外す</button>
    <button type="button" id="saved-toggle" class="saved-toggle" aria-pressed="false" hidden>あとで見る</button>
    <div class="view-toggle" id="view-toggle" role="group" aria-label="表示のしかた" hidden>
      <button type="button" class="view-btn" data-view="card" aria-pressed="true" title="カードで表示"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="4" width="7" height="7" rx="1"/><rect x="13" y="4" width="7" height="7" rx="1"/><rect x="4" y="13" width="7" height="7" rx="1"/><rect x="13" y="13" width="7" height="7" rx="1"/></svg><span class="visually-hidden">カードで表示</span></button>
      <button type="button" class="view-btn" data-view="list" aria-pressed="false" title="一覧で表示"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16"/></svg><span class="visually-hidden">一覧で表示</span></button>
    </div>
  </div>
  <ul class="cards" id="cards">
    {''.join(card(c) for c in cases)}
  </ul>
  <div class="more" id="more" hidden>
    <button type="button" class="more-button" id="more-button">もっと見る</button>
  </div>
  <div class="empty" id="empty" hidden>
    <p>条件に合う事例はありませんでした。</p>
    <p id="empty-hint">条件を減らすか、キーワードを変えてみてください。</p>
    <ul class="relax" id="relax" hidden></ul>
    <button type="button" class="button" id="reset2">条件をすべて外す</button>
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


def build_case(cfg, c, related, og_image=None, notes=None):
    # 事例ページ（2026-11-05 の見本で選んだ「読み物」の形）：
    # 基本の情報を小さな札に → 「この事例のポイント」（工夫のポイント）を大きく → 何をしたか → どうなったか →
    # だれが動かしているか → あなたの会社なら（AIによる提案）の流れ → 出典 → あとで見る・共有 → 近い事例。空欄の段は出さない
    icons = cfg.get("purpose_icons") or {}
    facts = [c.get("業種"), c.get("開始年") and f"{c['開始年']}年開始", c.get("規模") or c.get("規模の区分"),
             c.get("段階"), *c["_activity"], c.get("場"), c.get("ツール")]  # 白い札（基本の情報と活動の型）はまとめて1か所に
    chips = "".join(f"<li>{esc(x)}</li>" for x in facts if x)
    purposes = "".join(
        f'<li><a href="../../?purpose={urllib.parse.quote(p)}"><img src="../../assets/emoji/{icons.get(p, "1f4cc")}.png" alt="" width="20" height="20">{esc(p)}</a></li>'
        for p in c["_purpose"])
    lede = ""
    if c.get("工夫のポイント"):
        lede = f"""<section class="lede" style="--i: 0">
    <h2><img src="../../assets/emoji/1f4a1.png" alt="" width="20" height="20">この事例のポイント</h2>
    <p>{esc(c['工夫のポイント'])}</p>
  </section>"""
    steps = []
    for code, question, col in [("1f6e0", "何をしたか", "主な施策"), ("1f4c8", "どうなったか", "公開されている成果"),
                                ("1f465", "だれが動かしているか", "運営体制")]:
        if c.get(col):
            steps.append(f'<li style="--i: {len(steps) + 1}"><span class="step"><img src="../../assets/emoji/{code}.png" alt="" width="26" height="26"></span>'
                         f'<div><h2>{question}</h2><p>{esc(c[col])}</p></div></li>')
    if c.get(HINT_COL):
        steps.append(f"""<li style="--i: {len(steps) + 1}"><span class="step"><img src="../../assets/emoji/1f914.png" alt="" width="26" height="26"></span><div><h2>あなたの会社なら</h2>
      <div class="hint"><p>{esc(c[HINT_COL])}</p><p class="hint-note">事例をもとにAIが考えた応用案です。出典に書かれている事実ではありません。</p></div></div></li>""")
    flow = f'<ol class="flow">{"".join(steps)}</ol>' if steps else ""
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
        items = "".join(
            f'<a class="rel" href="../{esc(r["ID"])}/"><small>{esc(r["企業名"])}</small><strong>{esc(r["_title"])}</strong></a>'
            for r in related
        )
        rel_html = f'<section class="related"><h2>近い事例</h2><div class="rel-strip">{items}</div></section>'
    note_html_ = ""
    in_notes = [n for n in (notes or []) if c["ID"] in n["ids"]]
    if in_notes:
        lis = "".join(f'<li><a href="../../notes/{esc(n["slug"])}/">{esc(n["title"])}</a></li>' for n in in_notes)
        note_html_ = f'<section class="case-notes"><h2><img src="../../assets/emoji/1f4d3.png" alt="" width="22" height="22">この事例を紹介している{NOTES_LABEL}</h2><ul>{lis}</ul></section>'
    desc = shorten(f"{c['企業名']}の{c['_title']}。" + (c.get("工夫のポイント") or c.get("主な施策") or ""), 120)
    body = f"""
<article class="case wrap">
  <nav class="crumbs" aria-label="パンくずリスト"><ol><li><a href="../../">事例一覧</a></li><li aria-current="page">{esc(c['企業名'])}</li></ol></nav>
  <header class="case-head">
    <div class="card-top">{type_badge(c.get('種別'))}<span class="card-company">{esc(c['企業名'])}</span></div>
    <h1>{esc(c['_title'])}</h1>
    {f'<ul class="case-chips" aria-label="基本の情報">{chips}</ul>' if chips else ''}
    {f'<ul class="case-purposes" aria-label="目的">{purposes}</ul>' if purposes else ''}
  </header>
  {lede}
  {flow}
  {source}
  {share_bar(cfg, c)}
  <div class="feedback">
    <div class="useful" id="useful" hidden>
      <p>この事例は参考になりましたか。</p>
      <button type="button" class="small-button" id="useful-button" data-id="{esc(c['ID'])}" data-goatcounter-click="useful-{esc(c['ID'])}">役に立った</button>
      <button type="button" class="small-button" id="notuseful-button" data-id="{esc(c['ID'])}" data-goatcounter-click="notuseful-{esc(c['ID'])}">いまひとつ</button>
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


def share_bar(cfg, c):
    """あとで見る・URLのコピー・SNSへの共有。あとで見るとコピーは JavaScript が動くときだけ出す。"""
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
  <button type="button" class="action-button save" id="save" data-id="{esc(c['ID'])}" aria-pressed="false" data-goatcounter-click="save-{esc(c['ID'])}" hidden><span class="save-icon" aria-hidden="true"></span><span class="save-label">あとで見る</span></button>
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
        ("目的（社内）", "ビジョン浸透、エンゲージメント、イノベーション、ナレッジ共有、部門横断、オンボーディング", "企業が社内コミュニティに期待していること。出典に書かれている範囲で、複数つけています。"),
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

  <h2>おすすめ順</h2>
  <p>事例一覧は、はじめは「おすすめ順」で並んでいます。事例ごとに次の4つの点数を足した「観測スコア」（100点満点）の高い順で、同じ点数のときは確認日の新しい順です。初めて読む人が、よく知られていて情報の多い事例から読めるようにするための並び順で、各社の取り組みの良し悪しを評価した点数ではありません。</p>
  <div class="table-wrap">
  <table class="defs compact">
    <thead><tr><th scope="col">項目</th><th scope="col">配点</th><th scope="col">決め方</th></tr></thead>
    <tbody>
      <tr><th scope="row">知名度</th><td>30点</td><td>企業やコミュニティがどのくらい知られているかを、AIが5段階で推定しています。推定していない事例は12点です。</td></tr>
      <tr><th scope="row">情報の厚み</th><td>30点</td><td>規模・成果・運営体制・開始年・ツールのうち、公開情報で分かった項目1つにつき6点です。</td></tr>
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
  <p>どのページがよく読まれているかを知るために、アクセス解析の GoatCounter を使っています。数えているのは、ページが開かれた回数と、出典へのリンク・「あとで見る」・共有・「役に立った」「いまひとつ」のボタン・事例一覧の「目的から探す」のタイル・「組み合わせから探す」の地図のマスが押された回数です。GoatCounter はクッキーを使わず、名前やメールアドレスなど個人を特定できる情報も集めません。</p>
  <p>事例一覧の検索欄に入力された言葉と、その言葉で事例が見つかったかどうかも数えています。言い換えの表を増やしたり、集める事例のテーマを決めたりするのに使います。検索欄には、名前やメールアドレスなど個人を特定できる情報を入れないでください。</p>
  <p>「あとで見る」に入れた事例は、お使いのブラウザの中だけに保存しています。運営者には送られません。</p>

  <h2>掲載内容について</h2>
  <p>内容の誤りのお知らせや、事例のご提案は、{contact_text(cfg)}</p>

  <h2>運営者</h2>
  <div class="operator-card">
    <p class="operator-name"><strong>{esc(cfg.get('operator', ''))}</strong><span>コミュニティ研究家</span></p>
    <p>2017年に、日本最大級の実名制フリーランスコミュニティ「FreelanceNow」と、問いでつながるコミュニティ「議論メシ」を立ち上げました。議論メシでは1,200回以上のイベントを開き、延べ13,000人以上が参加しています。スタートアップ、大企業、NPO、行政などとのコラボレーションは400回を超えます。</p>
    <p>2024年3月からは、コミューン株式会社のコミューンコミュニティラボ所長として、コミュニティの研究と社会実装に取り組みました。著書に、社会の変化とコミュニティの関係を書いた『コミュニティシフト』と、企業の経営や事業におけるコミュニティの役割を論じた『コミュニティ経営の教科書』があります。</p>
    <p>2026年10月からはフリーランスとして、コミュニティ研究家、キャリア研究家、ディスカッションパートナーを仕事にしています。同じ時期に FreelanceNow を、キャリアの転機をシェアするコミュニティ「あしたの転機」にリニューアルしました。メンバーは1.6万人を超えています。この図鑑のほか、「<a href="https://ashitano-tenki.github.io/">あしたの転機観測所</a>」も運営しています。</p>
    <p class="operator-link"><a class="button" href="{esc(cfg.get('operator_url', ''))}" rel="noopener" target="_blank">黒田悠介のリンク集を見る</a><span>ほかの活動や発信をまとめています</span></p>
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
    """
    body = f"""
<article class="wrap saved-page">
  <nav class="crumbs" aria-label="パンくずリスト"><ol><li><a href="../">事例一覧</a></li><li aria-current="page">あとで見る</li></ol></nav>
  <h1>あとで見る</h1>
  <p class="lead">事例ページで「あとで見る」を押した事例です。このブラウザの中にだけ保存していて、運営者には送られません。</p>
  <p class="saved-count" id="saved-count" aria-live="polite"></p>
  <ul class="cards" id="saved-cards">
    {''.join(card(c, prefix="../").replace('<li class="card" ', '<li class="card" hidden ', 1) for c in cases)}
  </ul>
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

    global NOTES_PUBLIC
    notes_list = load_notes(cases)
    NOTES_PUBLIC = bool(notes_list)

    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    shutil.copytree(os.path.join(ROOT, "assets"), os.path.join(OUT, "assets"))

    write("index.html", build_index(cfg, cases))
    og_items = copy_og_items(cases)
    for c in cases:
        og = f"og/{c['ID']}.png" if c["ID"] in og_items else None
        write(f"cases/{c['ID']}/index.html", build_case(cfg, c, find_related(c, cases, n=6), og, notes_list))
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
    print(f"新着 {len(new)}件、更新 {len(updates)}件（履歴{'あり' if has_history else 'なし：確認日だけで判定'}）")
    write("404.html", build_404(cfg))
    write("saved/index.html", build_saved(cfg, cases))

    public = [{k: v for k, v in c.items() if not k.startswith("_")} for c in cases]
    write("data.json", json.dumps({"updated": datetime.now(JST).isoformat(), "cases": public},
                                  ensure_ascii=False, indent=1))
    base = cfg["base_url"].rstrip("/")
    urls = ([f"{base}/", f"{base}/new/", f"{base}/combos/", f"{base}/about/"]
            + ([f"{base}/notes/"] + [f"{base}/notes/{n['slug']}/" for n in notes_list] if notes_list else [])
            + [f"{base}/{cb['path']}" for cb in combos] + [f"{base}/cases/{c['ID']}/" for c in cases])
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
            # 観測スコアは鮮度で毎日変わり、履歴（新着と更新）が読みにくくなるので残さない
            fields = [k for k in rows[0].keys() if k != "観測スコア"]
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)

    print(f"{len(cases)}件の事例でサイトを作りました（{updated}）。")


if __name__ == "__main__":
    main()
