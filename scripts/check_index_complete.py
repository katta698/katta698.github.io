#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Every post in posts/ must actually be reachable from the generated surfaces.

    python scripts/check_index_complete.py
    python scripts/check_index_complete.py --root <dir>   # check another tree

Why this exists
---------------
This is the one failure on this site that produces no error, no warning and no
visible symptom on the post's own page -- so it can only be caught by asserting
the thing nobody was asserting.

`sync_blog.py` rebuilds the whole index from `posts/`. Four worktrees publish to
one branch, and each has its own `posts/` directory, so a window that runs sync
before rebasing builds the index from a tree that is missing another window's
post. The post's own page survives on disk and serves fine. Its card, its filter
pill count, its RSS item and its `cards.json` entry all come out absent, and
nothing fails.

It happened on 2026-08-17. Commit e131603 published Azure #4 with its card in
place; a9bbdd6, the next commit, published GCP #4 from a checkout that predated
it and the Azure card was gone; a0f49bb put it back. Three commits, one of them
shipping an index missing a post published fifteen minutes earlier, and the only
reason it was noticed is that a person went looking for a post and could not see
it.

CLAUDE.md has warned about this in prose since the worktrees were created. Prose
does not fail a build.

What it asserts
---------------
For every non-draft post in posts/:

1. a served page exists at blog/<slug>/index.html
2. a card for it exists in blog/index.html or one of blog/page/N/index.html
   -- pagination means a card legitimately lives on page 2 or later
3. an entry for it exists in blog/cards.json
4. an item for it exists in blog/rss.xml

And in the other direction, that cards.json holds no entry for a post that is
no longer in posts/ -- the renamed-post case, where staging the new filename
without the deletion leaves two copies in the index.

Draft posts are excluded, matching sync_blog.py's own rule
(`visible_posts = [p for p in posts if not p.get("draft")]`).

Exit code is non-zero on any missing surface, so it can gate a workflow.
"""
import argparse
import glob
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(path):
    try:
        return io.open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return None


def front_matter(text):
    """Slug, title and draft flag from a posts/ file, without a YAML parser.

    sync_blog.py is the authority on this and uses pyyaml, but this check has to
    run in CI on a tree where a dependency install may not have happened yet, and
    the three fields needed here are flat scalars. Anything it cannot parse is
    reported rather than skipped -- a post whose front matter this cannot read is
    a post sync may also have skipped, which is itself worth failing on.
    """
    if not text.lstrip().startswith("---"):
        return None
    body = text.lstrip()[3:]
    end = body.find("\n---")
    if end == -1:
        return None
    fm = body[:end]
    out = {}
    for key in ("slug", "title", "draft", "date"):
        m = re.search(r"^%s:\s*(.+?)\s*$" % key, fm, re.M)
        if m:
            out[key] = m.group(1).strip().strip("'\"")
    return out


def slugify(title):
    """Mirror of sync_blog.py's fallback when a post declares no slug."""
    s = re.sub(r"[^\w\s-]", "", title.lower())
    return re.sub(r"[-\s]+", "-", s).strip("-")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=REPO,
                    help="tree to check (default: this repo)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    root = args.root

    posts = {}
    unparsed = []
    for f in sorted(glob.glob(os.path.join(root, "posts", "*.html"))):
        text = read(f)
        fm = front_matter(text or "")
        name = os.path.basename(f)
        if not fm or not fm.get("title"):
            unparsed.append(name)
            continue
        if str(fm.get("draft", "false")).lower() == "true":
            continue
        posts[fm.get("slug") or slugify(fm["title"])] = name

    # Cards can sit on any pagination page, so all of them count as "the index".
    index_html = ""
    for p in [os.path.join(root, "blog", "index.html")] + sorted(
            glob.glob(os.path.join(root, "blog", "page", "*", "index.html"))):
        index_html += read(p) or ""

    rss = read(os.path.join(root, "blog", "rss.xml")) or ""
    cards_raw = read(os.path.join(root, "blog", "cards.json"))
    try:
        cards = json.loads(cards_raw) if cards_raw else []
    except ValueError as exc:
        print("blog/cards.json is not valid JSON: %s" % exc)
        return 1
    card_slugs = {c.get("slug") for c in cards}

    problems = []
    for slug, src in sorted(posts.items()):
        if not os.path.exists(os.path.join(root, "blog", slug, "index.html")):
            problems.append("%s: no served page at blog/%s/" % (src, slug))
        if ('href="/blog/%s/"' % slug) not in index_html:
            problems.append("%s: no card on the index (or any page/N) for %s"
                            % (src, slug))
        if slug not in card_slugs:
            problems.append("%s: absent from blog/cards.json" % src)
        if ("/blog/%s/" % slug) not in rss:
            problems.append("%s: no item in blog/rss.xml" % src)

    for slug in sorted(card_slugs - set(posts)):
        problems.append("cards.json lists %s, which no posts/ file produces "
                        "(renamed post with the deletion unstaged?)" % slug)

    for name in unparsed:
        problems.append("%s: front matter unreadable -- sync may skip it too"
                        % name)

    if problems:
        print("")
        for p in problems:
            print("  %s" % p)
    if not args.quiet or problems:
        print("\n%d public post(s), %d card(s): %d problem(s)."
              % (len(posts), len(card_slugs), len(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
