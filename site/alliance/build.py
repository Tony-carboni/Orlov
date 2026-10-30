"""Build the alliance news site (alliance.orlovfamily.space) from Markdown posts.

Usage, on the PC from the repo root:  python site/alliance/build.py
Reads site/alliance/posts/*.md (newest first by file name), writes site/alliance/dist/:
index.html (the list) and one page per post. The local session then copies dist/ to the
server's ~/aa-docker/alliance-site/ (runbook 15 D). Needs the `markdown` package
(python -m pip install --user markdown).

A post starts with a small header block, one item per line, then a blank line:

    title: State of the Union, October 2026
    date: 2026-10-14
    author: Catherine Frey
    summary: One paragraph shown on the index page.

Everything after the blank line is Markdown. The file name decides the order and the
page address: posts/2026-10-14-state-of-the-union.md becomes /2026-10-14-state-of-the-union.html.
"""

import html
import json
import pathlib
import re
import shutil
import sys

try:
    import markdown
except ImportError:  # pragma: no cover
    sys.exit("Install the markdown package first: python -m pip install --user markdown")

HERE = pathlib.Path(__file__).resolve().parent
DRAFTS = HERE / "drafts"
POSTS = HERE / "posts"
DIST = HERE / "dist"
TEMPLATE = (HERE / "template.html").read_text(encoding="utf-8")
SITE_NAME = "The Orlov Family"


def parse(path: pathlib.Path) -> dict:
    text = path.read_text(encoding="utf-8")
    head, _, body = text.partition("\n\n")
    meta = {}
    for line in head.splitlines():
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip().lower()] = value.strip()
    if "title" not in meta:
        sys.exit(f"{path.name}: the header block needs a 'title:' line")
    meta.setdefault("date", path.name[:10])
    meta.setdefault("author", "")
    meta.setdefault("summary", "")
    meta["slug"] = path.stem
    meta["body_html"] = markdown.markdown(body, extensions=["extra", "sane_lists", "toc"])
    return meta


def render(**ctx) -> str:
    out = TEMPLATE
    for key, value in ctx.items():
        out = out.replace("{{ " + key + " }}", value)
    return out


def main() -> int:
    posts = sorted((parse(p) for p in POSTS.glob("*.md") if not p.name.startswith("_")), key=lambda m: m["slug"], reverse=True)
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    shutil.copy(HERE / "style.css", DIST / "style.css")
    for meta in posts:
        page = render(
            site=SITE_NAME, title=html.escape(meta["title"]), date=html.escape(meta["date"]),
            author=(" · " + html.escape(meta["author"])) if meta["author"] else "", content=meta["body_html"],
            nav='<a href="/">All posts</a>',
        )
        (DIST / f"{meta['slug']}.html").write_text(page, encoding="utf-8")
    items = []
    for meta in posts:
        items.append(
            f'<article class="teaser"><h2><a href="/{meta["slug"]}.html">{html.escape(meta["title"])}</a></h2>'
            f'<p class="meta">{html.escape(meta["date"])}{" · " + html.escape(meta["author"]) if meta["author"] else ""}</p>'
            f'<p>{html.escape(meta["summary"])}</p></article>'
        )
    index = render(site=SITE_NAME, title="Alliance news", date="", author="", nav="",
                   content="\n".join(items) or "<p>No posts yet.</p>")
    (DIST / "index.html").write_text(index, encoding="utf-8")
    # posts.json: the list for other tools (the Shipyard's Finance tab opens a new reporting period at each State of the Alliance post)
    (DIST / "posts.json").write_text(json.dumps([{k: meta[k] for k in ("slug", "title", "date", "author", "summary")} for meta in posts], indent=1), encoding="utf-8")
    # a 404 page so a mistyped link still looks like ours
    (DIST / "404.html").write_text(render(site=SITE_NAME, title="Not found", date="", author="", nav='<a href="/">All posts</a>',
                                          content="<p>That page does not exist. The posts are on the front page.</p>"), encoding="utf-8")
    # drafts/: previews for the owner only (2026-10-30). Rendered under an unguessable folder, not in the index, not in
    # posts.json (the Shipyard would open a reporting period), with a noindex tag. The folder name lives in .preview-token
    # (gitignored); delete the file for a new address.
    drafts = sorted(parse(p) for p in DRAFTS.glob("*.md")) if DRAFTS.exists() else []
    if drafts:
        token_file = HERE / ".preview-token"
        if not token_file.exists():
            import secrets
            token_file.write_text(secrets.token_urlsafe(18), encoding="utf-8")
        token = token_file.read_text(encoding="utf-8").strip()
        folder = DIST / "preview" / token
        folder.mkdir(parents=True)
        for meta in drafts:
            page = render(site=SITE_NAME, title=html.escape(meta["title"]) + " (preview)", date=html.escape(meta["date"]),
                          author=(" · " + html.escape(meta["author"])) if meta["author"] else "", content=meta["body_html"], nav="")
            page = page.replace("</head>", '<meta name="robots" content="noindex, nofollow">' + chr(10) + "</head>", 1)
            (folder / f"{meta['slug']}.html").write_text(page, encoding="utf-8")
            print(f"  preview: /preview/{token}/{meta['slug']}.html  {meta['title']}")
    print(f"built {len(posts)} post(s) into {DIST}")
    for meta in posts:
        print(f"  {meta['slug']}.html  {meta['title']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
