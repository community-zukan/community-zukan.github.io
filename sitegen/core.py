"""サイトを作る仕組みの土台：設定とデータの読み込み、言い換え・読み、事例の整え方、共通の値と小さな道具。"""

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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # リポジトリの一番上（sitegen/ の一つ上）
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
    ("tool", "ツール", "ツール"),   # 3件以上の事例が使っているツールだけ（TOOL_FACET_MIN）
    ("size", "規模の区分", "規模の区分"),
]
STAGE_ORDER = ["立ち上げ期", "成長期", "成熟期", "転換期"]
# 場の「両方」は、サイトでは「オンオフ両方」と出す（2026-11-05 黒田さんの判断。シートの値はそのまま）
PLACE_RENAME = {"両方": "オンオフ両方"}
PLACE_ORDER = ["オンライン", "オフライン", "オンオフ両方"]
SIZE_ORDER = ["〜100人", "100〜1,000人", "1,000〜1万人", "1万人超"]
PURPOSE_ORDER = [
    "ビジョン浸透", "エンゲージメント", "イノベーション", "ナレッジ共有",
    "部門横断", "オンボーディング",
    "LTV・継続", "共創・商品開発", "サポート効率化", "口コミ・認知", "ブランド体験",
    "事業共創・協業", "起業・成長支援", "投資・資金調達", "採用・人材", "拠点・地域の活性化", "業界の学び合い",
]
# サイトでの目的の名前。シートの値が長くタイルで2行になるものだけ短くする（2026-11-05 黒田さんの判断）。
# 読み込むときに置き換えるので、絞り込み・URL・組み合わせのページもすべて短い名前になる。シートの値は変えない
PURPOSE_RENAME = {"ナレッジ共有・継承": "ナレッジ共有", "定着・オンボーディング": "オンボーディング"}
# 種別。2026-11-06 に「多企業」を足した。並び順は ファン・顧客 → 社内 → 多企業（黒田さんの判断）。
# 種別は必ず B列で判断する。ID の頭文字（S／F／M）では決めない（ファン・顧客から多企業に移した行は F のまま）
TYPE_ORDER = ["ファン・顧客", "社内", "多企業"]
TYPE_LABEL = {"社内": "社内", "ファン・顧客": "ファン・顧客", "多企業": "多企業"}
TYPE_CLASS = {"社内": "is-internal", "ファン・顧客": "is-fan", "多企業": "is-multi"}   # 知らない値は中立の札



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


def split_tools(v):
    """ツール列を1つずつに分ける（「、」「/」などで区切る。（ ）の中の区切りでは分けない）。"""
    out, buf, depth = [], "", 0
    for ch in v or "":
        if ch in "（(":
            depth += 1
        elif ch in "）)":
            depth = max(0, depth - 1)
        if depth == 0 and ch in "、,，/／":
            out.append(buf)
            buf = ""
        else:
            buf += ch
    out.append(buf)
    return [t.strip() for t in out if t.strip()]


def tool_base(t):
    """ツールの名前から（ ）の中を外す。「Beach（クオン）」→「Beach」"""
    return re.sub(r"\s*[（(].*$", "", t).strip()


def assign_tools(cases):
    """事例ごとのツールを [(シートの書き方, まとめた名前)] にして c["_tools"] に入れ、まとめた名前ごとの事例の数を返す。
    （ ）の中を外し、大文字・小文字と全角・半角をそろえ、言い換え表（config/synonyms.json）の同じグループは1つにまとめる
    （「commmune」と「Commune」など）。まとめた名前は、データの中でいちばん多い書き方にする。"""
    groups = load_synonyms()
    def key_of(base):
        n = normalize(base)
        for i, g in enumerate(groups):
            if n in g["words"]:
                return f"g{i}"
        return n
    spell = {}
    for c in cases:
        c["_tool_keys"] = []
        for t in split_tools(c.get("ツール")):
            base = tool_base(t)
            if not base:
                continue
            k = key_of(base)
            spell.setdefault(k, Counter())[base] += 1
            c["_tool_keys"].append((t, k))
    names = {k: sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] for k, cnt in spell.items()}
    counts = Counter()
    for c in cases:
        c["_tools"] = [(t, names[k]) for t, k in c.pop("_tool_keys")]
        for name in {n for _, n in c["_tools"]}:
            counts[name] += 1
    return counts


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
        c["_row"] = r   # シートのままの値（新着と更新の判定は、表示のための言い換えをする前の値で比べる）
        c["_purpose"] = [PURPOSE_RENAME.get(p, p) for p in split_multi(r.get("目的"))]
        c["_activity"] = split_multi(r.get("活動の型"))
        if c.get("場"):
            c["場"] = PLACE_RENAME.get(c["場"].strip(), c["場"].strip())
        c["_industry"] = industry_group(cfg, r.get("業種"))
        c["_urls"] = split_urls(r.get("出典URL"))
        c["_title"] = r.get("コミュニティ名") or f"{r['企業名']}のコミュニティ"
        cases.append(c)
    # TOOL_COUNTS はほかのモジュールからも同じものを見るので、入れ替えずに中身を書き換える
    TOOL_COUNTS.clear()
    TOOL_COUNTS.update(assign_tools(cases))
    return cases


COMMUNITY_AI = ""        # コミュニティAI のURL（config/site.json の community_ai_url。main で読み込む）。空ならリンクを出さない
PURPOSE_ICONS = {}        # 目的ごとの絵（config/site.json の purpose_icons。main で読み込む）
TOOL_FACET_MIN = 3       # 絞り込みの欄に出すツールの件数の下限（2件のツールは事例ページの札から開く。2026-11-05 黒田さんの判断）
TOOL_COUNTS = Counter()  # まとめたツールの名前ごとの事例の数（enrich で数える）。2件以上のものだけ札を押せるようにする




def to_date(v):
    k = date_key(v)
    return datetime.strptime(k, "%Y%m%d").date() if k else None


def fmt_day(d):
    return f"{d.year}年{d.month}月{d.day}日"


NOTES_DIR = os.path.join(ROOT, "notes")
NOTES_LABEL = "図鑑ノート"
NOTES_PUBLIC = False   # 公開する記事が1本でもあれば True（メニューに「図鑑ノート」を出す）


def write(path, text):
    full = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(text)
