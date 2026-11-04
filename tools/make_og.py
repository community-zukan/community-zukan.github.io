#!/usr/bin/env python3
"""SNSで共有されたときの画像（1200×630）を作るスクリプト。Pillow を使います。

  python3 tools/make_og.py                          # 公開用CSVから事例ごとの画像を作る
  python3 tools/make_og.py --csv testdata/public.csv  # 手元のCSVで作る
  python3 tools/make_og.py --site                   # サイト全体の画像 assets/ogp.png を作り直す

- 事例ごとの画像は og-items/{ID}.png に書きます。build.py が見つけたら /og/{ID}.png として公開し、
  事例ページの og:image にします。画像がない事例は assets/ogp.png のままです。
- og-items/ はリポジトリに入れません（毎日のビルドで作り直します）。
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
BG, SURFACE, INK, INK2, INK3 = "#f7f5f0", "#ffffff", "#1f2328", "#4a5058", "#6b7178"
LINE, ACCENT = "#e2ded5", "#1d5a6e"
TYPE_COLORS = {"社内": ("#3c4f8f", "#e6e9f5"), "ファン・顧客": ("#a5471f", "#f8e9e1")}
DOT_PEACH = "#f0b48a"

FONT_FILES = {
    "bold": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "NotoSansCJKjp-Bold.otf"],
    "regular": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "NotoSansCJKjp-Regular.otf"],
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


def dots(draw, x, y, r):
    """ファビコンと同じ3つの丸。(x, y) は左上の丸の中心。"""
    gap = r * 2.5
    draw.ellipse([x - r, y - r, x + r, y + r], fill=ACCENT)
    draw.ellipse([x + gap - r, y - r, x + gap + r, y + r], fill=DOT_PEACH)
    draw.ellipse([x + gap / 2 - r, y + gap * 0.8 - r, x + gap / 2 + r, y + gap * 0.8 + r], fill=ACCENT)


def frame(cfg):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 16, H], fill=ACCENT)
    # 下の帯：サイト名とURL
    d.line([(80, H - 104), (W - 80, H - 104)], fill=LINE, width=2)
    dots(d, 96, H - 62, 9)
    d.text((140, H - 52), cfg["name"], font=font("bold", 30), fill=ACCENT, anchor="ls")
    host = cfg["base_url"].split("//", 1)[-1].rstrip("/")
    d.text((W - 80, H - 52), host, font=font("regular", 24), fill=INK3, anchor="rs")
    return img, d


def make_site(cfg):
    img, d = frame(cfg)
    dots(d, 112, 150, 22)
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
    fg, bg = TYPE_COLORS.get(t, (ACCENT, "#e3eef1"))
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", help="手元のCSVファイルを使う")
    ap.add_argument("--site", action="store_true", help="assets/ogp.png を作り直す")
    args = ap.parse_args()
    cfg = build.load_config()
    if args.site:
        make_site(cfg)
        return
    cases = build.enrich(cfg, build.load_rows(cfg, args.csv))
    os.makedirs(OUT, exist_ok=True)
    for c in cases:
        make_case(cfg, c, os.path.join(OUT, f"{c['ID']}.png"))
    print(f"{len(cases)}件の共有画像を {os.path.relpath(OUT, ROOT)}/ に作りました。")


if __name__ == "__main__":
    main()
