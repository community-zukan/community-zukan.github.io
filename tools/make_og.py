#!/usr/bin/env python3
"""SNSで共有されたときの画像（1200×630）を作るスクリプト。Pillow を使います。

  python3 tools/make_og.py                          # 公開用CSVから事例ごとの画像を作る
  python3 tools/make_og.py --csv testdata/public.csv  # 手元のCSVで作る
  python3 tools/make_og.py --site                   # サイト全体の画像 assets/ogp.png とファビコンの PNG を作り直す
  python3 tools/make_og.py --notes                  # 図鑑ノートの画像だけを作る（記事を書いたときの確かめ用）

- 事例ごとの画像は og-items/{ID}.png に書きます。build.py が見つけたら /og/{ID}.png として公開し、
  事例ページの og:image にします。画像がない事例は assets/ogp.png のままです。
- og-items/ はリポジトリに入れません（毎日のビルドで作り直します）。
- 図鑑ノートの記事ごとの画像は og-items/note-<スラッグ>.png に書きます（一覧のカード・SNSの共有画像に使う）。
  薄い空色の地に、右上の円と絵文字、「図鑑ノート｜社内」の札、題名、署名（2026-11-05 の見本の案B）。
  絵文字は Noto Emoji の 512px を tools/emoji/cache/ に取ってきて使い、取れないときは assets/emoji/ の 128px を使います。
- 載せるのは種別・企業名・コミュニティ名だけです。企業のロゴや出典の画像は使いません。
- 書体は Noto Sans CJK JP。Actions では apt の fonts-noto-cjk を使い、見つからないときは
  tools/fonts/ にダウンロードします（リポジトリには入れません）。
"""
import argparse
import os
import sys
import urllib.request

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import build  # noqa: E402  CSVの読み取りは build.py と同じものを使う

OUT = os.path.join(ROOT, "og-items")
SITE_OG = os.path.join(ROOT, "assets", "ogp.png")
FONTS = os.path.join(ROOT, "tools", "fonts")
W, H = 1200, 630

# サイトの配色（assets/style.css と同じ）
# デザインシステム「黒田悠介」の色（assets/style.css と同じ）
BG, SURFACE, INK, INK2, INK3 = "#f7f9fb", "#ffffff", "#1a1d23", "#4a4f57", "#5e636b"
LINE, ACCENT, YELLOW = "#e3e6ea", "#1874b8", "#f5c518"
TYPE_COLORS = {"社内": ("#1568a6", "#e8eef5"), "ファン・顧客": ("#6b4e00", "#fff3c4"), "多企業": ("#2e6b3c", "#e4f1e1")}

FONT_FILES = {
    "bold": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "NotoSansCJKjp-Bold.otf"],
    "regular": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "NotoSansCJKjp-Regular.otf"],
    # 図鑑ノートの題名用（2026-11-10 unslop の見直しでサイトの見出しを太さ500にしたので、画像もそろえる）
    "medium": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc", "NotoSansCJKjp-Medium.otf"],
}
FONT_URL = "https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/Japanese/%s"
NO_START = "、。，．・ー）」』】！？!?ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮ"
NO_END = "（「『【"


def font_path(kind):
    system, name = FONT_FILES[kind]
    if os.path.exists(system):
        return system, 0
    local = os.path.join(FONTS, name)
    if not os.path.exists(local):
        os.makedirs(FONTS, exist_ok=True)
        print(f"書体をダウンロードします: {name}")
        urllib.request.urlretrieve(FONT_URL % name, local)
    return local, 0


def font(kind, size):
    path, _ = font_path(kind)
    # .ttc の0番目は Noto Sans CJK JP
    return ImageFont.truetype(path, size, index=0)


def wrap(draw, text, fnt, width, max_lines):
    """幅に収まるように1文字ずつ折り返す。英単語は途中で切らず、行頭・行末の禁則を少し守る。"""
    tokens, buf = [], ""
    for ch in text:
        if ch.isascii() and ch.isalnum():
            buf += ch
            continue
        if buf:
            tokens.append(buf)
            buf = ""
        tokens.append(ch)
    if buf:
        tokens.append(buf)
    lines, cur = [], ""
    for t in tokens:
        if draw.textlength(cur + t, font=fnt) <= width or not cur:
            cur += t
            continue
        if t in NO_START and cur:
            # 行頭に来てはいけない文字は、前の行の最後の文字と一緒に送る
            t = cur[-1] + t
            cur = cur[:-1]
        if cur and cur[-1] in NO_END:
            t = cur[-1] + t
            cur = cur[:-1]
        lines.append(cur.rstrip())
        cur = t.lstrip()
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and draw.textlength(last + "…", font=fnt) > width:
            last = last[:-1]
        lines[-1] = last.rstrip("、。 ") + "…"
    return lines


BOOK = os.path.join(ROOT, "tools", "emoji", "book-512.png")  # 本を開いた絵文字「📖」（Noto Emoji）


def book(img, x, y, size):
    """ファビコンと同じ「📖」の絵。(x, y) は絵の左上。"""
    mark = Image.open(BOOK).convert("RGBA").resize((size, size), Image.LANCZOS)
    img.paste(mark, (int(x), int(y)), mark)


def make_icons():
    """ファビコンの PNG（32px）と apple-touch-icon（180px、生成りの地）を作る。"""
    src = Image.open(BOOK).convert("RGBA")
    src.resize((32, 32), Image.LANCZOS).save(os.path.join(ROOT, "assets", "favicon-32.png"), optimize=True)
    touch = Image.new("RGBA", (180, 180), BG)
    mark = src.resize((140, 140), Image.LANCZOS)
    touch.paste(mark, (20, 20), mark)
    touch.convert("RGB").save(os.path.join(ROOT, "assets", "apple-touch-icon.png"), optimize=True)
    print("作りました: assets/favicon-32.png・assets/apple-touch-icon.png")


def frame(cfg):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 16, H], fill=YELLOW)
    # 下の帯：サイト名とURL
    d.line([(80, H - 104), (W - 80, H - 104)], fill=LINE, width=2)
    book(img, 80, H - 88, 48)
    d.text((140, H - 52), cfg["name"], font=font("bold", 30), fill=INK, anchor="ls")
    host = cfg["base_url"].split("//", 1)[-1].rstrip("/")
    d.text((W - 80, H - 52), host, font=font("regular", 24), fill=INK3, anchor="rs")
    return img, d


def make_site(cfg):
    img, d = frame(cfg)
    book(img, 78, 76, 112)
    d.text((80, 300), cfg["name"], font=font("bold", 96), fill=INK, anchor="ls")
    lines = wrap(d, cfg["subtitle"], font("regular", 40), W - 160, 2)
    y = 372
    for ln in lines:
        d.text((80, y), ln, font=font("regular", 40), fill=INK2, anchor="ls")
        y += 58
    d.text((80, y + 20), "目的・段階・活動の型で、自社に近い事例を探せます", font=font("regular", 30), fill=INK3, anchor="ls")
    img.save(SITE_OG, optimize=True)
    print(f"作りました: {os.path.relpath(SITE_OG, ROOT)}")


def make_case(cfg, c, path):
    img, d = frame(cfg)
    t = c.get("種別", "")
    fg, bg = TYPE_COLORS.get(t, (ACCENT, "#e8eef5"))
    label = t or "事例"
    bf = font("bold", 30)
    bw = d.textlength(label, font=bf)
    d.rounded_rectangle([80, 72, 80 + bw + 48, 124], radius=26, fill=bg)
    d.text((80 + 24, 110), label, font=bf, fill=fg, anchor="ls")

    company = c.get("企業名", "")
    cf = font("regular", 40)
    clines = wrap(d, company, cf, W - 160, 1)
    d.text((80, 200), clines[0] if clines else "", font=cf, fill=INK2, anchor="ls")

    title = c["_title"]
    # 長いコミュニティ名は文字を小さくして3行までに収める
    # 見出しに使える高さは、企業名の下から下の線の上まで（約270px）
    for size in (76, 68, 60, 54, 48):
        tf = font("bold", size)
        lh = int(size * 1.3)
        lines = wrap(d, title, tf, W - 160, 3)
        if (not lines[-1].endswith("…") and len(lines) * lh <= 270) or size == 48:
            break
    y = 230 + size
    for ln in lines:
        d.text((80, y), ln, font=tf, fill=INK, anchor="ls")
        y += lh
    img.save(path, optimize=True)


NOTE_BG, NOTE_CIRCLE = "#e8eef5", "#d3e1ef"   # 図鑑ノートの画像：薄い空色の地（--chip-bg）と、右上の円
EMOJI_CACHE = os.path.join(ROOT, "tools", "emoji", "cache")
EMOJI_URL = "https://raw.githubusercontent.com/googlefonts/noto-emoji/main/2D/png/512/emoji_u%s.png"


def emoji_image(code):
    path = os.path.join(EMOJI_CACHE, code + ".png")
    if not os.path.exists(path):
        try:
            os.makedirs(EMOJI_CACHE, exist_ok=True)
            urllib.request.urlretrieve(EMOJI_URL % code, path)
        except Exception:  # noqa: BLE001
            path = os.path.join(ROOT, "assets", "emoji", code + ".png")
    if not os.path.exists(path):
        path = os.path.join(ROOT, "assets", "emoji", "1f4d3.png")
    return Image.open(path).convert("RGBA")


def title_lines(d, title, fnt, width, max_lines):
    """題名を「。」「、」のところで区切って行に詰める。1つの区切りが長すぎるときだけ文字の途中で折り返す。"""
    import re
    lines, cur = [], ""
    for seg in re.findall(r"[^。、）」』]+[。、）」』]*", title):
        if d.textlength(cur + seg, font=fnt) <= width:
            cur += seg
            continue
        if cur:
            lines.append(cur)
        cur = ""
        if d.textlength(seg, font=fnt) <= width:
            cur = seg
        else:
            parts = wrap(d, seg, fnt, width, 9)
            lines += parts[:-1]
            cur = parts[-1]
    if cur:
        lines.append(cur)
    return lines if len(lines) <= max_lines else None


def make_note(cfg, n, path):
    img = Image.new("RGB", (W, H), NOTE_BG)
    d = ImageDraw.Draw(img)
    d.ellipse((W - 330, -170, W + 170, 330), fill=NOTE_CIRCLE)
    d.ellipse((W - 260, 60, W - 80, 240), fill=SURFACE)
    e = emoji_image(n["emoji"]).resize((128, 128), Image.LANCZOS)
    img.paste(e, (W - 234, 86), e)
    label = "図鑑ノート" + ("｜" + n["kind"] if n["kind"] else "")
    pf = font("bold", 30)
    tw = d.textlength(label, font=pf)
    d.rounded_rectangle((72, 72, 72 + tw + 48, 128), radius=12, fill=ACCENT)  # 札の角は小さく（サイトの札と同じ考え方。もとは丸い形の 28）
    d.text((96, 112), label, font=pf, fill=SURFACE, anchor="ls")
    # 題名は円にかからない幅で、3行までに収まる大きさを選ぶ
    for size in (64, 60, 56, 50, 46):
        tf = font("medium", size)  # 題名は Medium（もとは Bold）
        lines = title_lines(d, n["title"], tf, W - 72 - 330, 3)
        if lines:
            break
    if not lines:
        lines = wrap(d, n["title"], tf, W - 72 - 330, 3)
    lh = int(size * 1.42)
    y = 170 + size
    for ln in lines:
        d.text((72, y), ln, font=tf, fill=INK, anchor="ls")
        y += lh
    d.text((72, H - 64), "文：黒田悠介（コミュニティ研究家）", font=font("regular", 28), fill=INK2, anchor="ls")
    d.text((W - 72, H - 64), cfg["name"], font=font("bold", 28), fill=INK2, anchor="rs")
    img.save(path, optimize=True)


def make_notes(cfg):
    notes = build.load_notes()
    os.makedirs(OUT, exist_ok=True)
    for n in notes:
        make_note(cfg, n, os.path.join(OUT, f"note-{n['slug']}.png"))
    print(f"図鑑ノートの画像 {len(notes)}枚を {os.path.relpath(OUT, ROOT)}/ に作りました。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", help="手元のCSVファイルを使う")
    ap.add_argument("--site", action="store_true", help="assets/ogp.png を作り直す")
    ap.add_argument("--notes", action="store_true", help="図鑑ノートの画像だけを作る")
    args = ap.parse_args()
    cfg = build.load_config()
    if args.site:
        make_site(cfg)
        make_icons()
        return
    if args.notes:
        make_notes(cfg)
        return
    cases = build.enrich(cfg, build.load_rows(cfg, args.csv))
    os.makedirs(OUT, exist_ok=True)
    for c in cases:
        make_case(cfg, c, os.path.join(OUT, f"{c['ID']}.png"))
    print(f"{len(cases)}件の共有画像を {os.path.relpath(OUT, ROOT)}/ に作りました。")
    make_notes(cfg)


if __name__ == "__main__":
    main()
