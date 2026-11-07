"""図鑑ノート（テーマごとに事例を読み比べる記事）：notes/*.md の読み込みと、記事・一覧のページ。"""

from .core import *  # noqa: F401,F403
from . import core
from .parts import *  # noqa: F401,F403


# ---------- 図鑑ノート（テーマごとに事例を読み比べる記事） ----------
# 原稿は notes/<スラッグ>.md（名前が「_」で始まるファイルは読まない）。先頭の --- で囲んだ部分に題名などを書き、
# 本文は次の書き方だけを使う。書き方の決めごとは notes/_guide.md。
#   ## 見出し / ### 小見出し / 空行で段落 / 「- 」で箇条書き / [文字](URL) でリンク / **強調**
#   :::case S75   ← 事例を1件差し込む（企業名・コミュニティ名・目的の札はデータから入る）
#   黒田のひとこと（次の ::: までの段落）
#   :::
# 公開日（published）がない原稿と、draft: true の原稿は出さない。
# 見た目は 2026-11-05 の見本で選んだもの：記事は「表から読み物へ」（案3）、冒頭と画像は薄い空色の地（案B）。


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


def note_ai_anchor(n, cs):
    """図鑑ノートからコミュニティAIを開くときの印。コミュニティAIは紹介している事例のカードを出し、
    「図鑑ノートを読んだ」という相談から始める（2026-11-06 にコミュニティAI側も対応）。"""
    # claude.ai は「=」「&」を含む印をアーティファクトに渡さないので、英数字とハイフンだけの形にする（例：note-alumni-community-S75-S87）
    return "-".join(["note", n["slug"]] + [c["ID"] for c in cs])


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
  {ai_line(rel, "自社で始めるなら？この記事の事例をもとに、コミュニティAIに相談する", "note/" + n["slug"], note_ai_anchor(n, cs))}
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
