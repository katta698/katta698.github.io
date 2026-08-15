#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Back-fill the "Next" link on architecture-series pages.

Why this exists
---------------
`build_arch_post.py` builds a page once, at publish time, and drops the next
half of the post-nav because at that moment nothing follows the post. Those
pages are `externally_built`, so `sync_blog.py` never regenerates them — which
means when post N+1 ships, post N is never updated to point forward at it.

The result is a series you can only read backwards. Measured 2026-08-15, only 6
of 24 architecture pages across the three clouds had a next link, the newest post
of every series was a dead end, and `gcp-architecture-resource-hierarchy` had no
navigation at all. On a 365-post series that compounds every day.

What it does, and deliberately does not do
------------------------------------------
It sets the **next** link only, from the series order, and leaves every existing
**prev** link exactly as it is. Some older AWS pages have a prev pointing at a
Weekly Lab post from before the series conventions settled; those are historical
navigation choices, and rewriting them is a different decision from fixing a
missing link. This script does not make that decision.

It is idempotent: a page already carrying the correct next link is left alone,
so it is safe to run on every publish and safe to run twice.

Usage
-----
    python scripts/fix_series_nav.py            # fix every series
    python scripts/fix_series_nav.py --check    # report only, exit 1 if wrong
    python scripts/fix_series_nav.py --series gcp
"""
import argparse
import glob
import io
import os
import re
import sys

import yaml

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Only the custom-built architecture series. The sync-built series get their
# pages regenerated on every run, so they never carry this problem.
SERIES = {
    "arch": ("arch-", "AWS Architecture Series"),
    "az":   ("az-",   "Azure Architecture Series"),
    "gcp":  ("gcp-",  "GCP Architecture Series"),
}

NEXT_LINK_RE = re.compile(
    r'<a href="[^"]*" class="post-nav-link next">.*?</a>', re.S)
NAV_CLOSE = "</nav>"


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def load_series(prefix):
    """Ordered [(n, slug, title)] for one series, by the #N in the title.

    Numbered from the title rather than by position or by date: the number is in
    the reader's URL and in their saved progress, and position is only correct
    while nothing is ever backfilled.
    """
    out = []
    for path in glob.glob(os.path.join(ROOT, "posts", prefix + "*.html")):
        raw = io.open(path, encoding="utf-8").read()
        if not raw.startswith("---"):
            continue
        try:
            fm = yaml.safe_load(raw.split("---", 2)[1]) or {}
        except yaml.YAMLError:
            continue
        title, slug = fm.get("title"), fm.get("slug")
        if not title or not slug:
            continue
        m = re.search(r"#(\d+)", str(title))
        if not m:
            continue
        out.append((int(m.group(1)), slug, str(title)))
    return sorted(out)


def _href_of(anchor):
    m = re.search(r'href="([^"]*)"', anchor)
    return m.group(1) if m else ""


def next_link_html(slug, title):
    return ('<a href="/blog/%s/" class="post-nav-link next">'
            '<span class="post-nav-dir">Next →</span>'
            '<span class="post-nav-title">%s</span></a>' % (slug, esc(title)))


def fix_page(slug, nxt, check):
    """Ensure this page's next link points at `nxt`, or has none if nxt is None."""
    path = os.path.join(ROOT, "blog", slug, "index.html")
    if not os.path.isfile(path):
        return "missing", "no served page at blog/%s/" % slug
    html = io.open(path, encoding="utf-8").read()
    if '<nav class="post-nav"' not in html:
        return "missing", "no <nav class=\"post-nav\"> element"

    have = NEXT_LINK_RE.search(html)
    want = next_link_html(*nxt) if nxt else None

    if want is None:
        # Latest post in the series: a next link here would be a dead end.
        if not have:
            return "ok", ""
        new = NEXT_LINK_RE.sub("", html, count=1)
        action = "removed stale next link"
    elif have and _href_of(have.group(0)) == "/blog/%s/" % nxt[0]:
        # Already points at the right post. The displayed title may be the short
        # form rather than the full one -- pages were built by hand at different
        # times and both styles exist. Rewriting that is churn on a page nothing
        # regenerates, so a correct destination is left exactly as it is.
        return "ok", ""
    elif have:
        new = html[:have.start()] + want + html[have.end():]
        action = "repointed next -> %s" % nxt[1]
    else:
        i = html.index(NAV_CLOSE)
        new = html[:i] + want + html[i:]
        action = "added next -> %s" % nxt[1]

    if not check:
        io.open(path, "w", encoding="utf-8", newline="\n").write(new)
    return "fixed", action


def backfill_all(quiet=False):
    """Fix every series. Called by build_arch_post.py after each publish."""
    fixed = 0
    for key in sorted(SERIES):
        prefix, _label = SERIES[key]
        posts = load_series(prefix)
        for i, (_n, slug, _title) in enumerate(posts):
            nxt = (posts[i + 1][1], posts[i + 1][2]) if i + 1 < len(posts) else None
            state, detail = fix_page(slug, nxt, check=False)
            if state == "fixed":
                fixed += 1
                if not quiet:
                    print("  %s: %s" % (slug, detail))
    return fixed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report what is wrong and exit non-zero, changing nothing")
    ap.add_argument("--series", help="one of: %s" % ", ".join(sorted(SERIES)))
    args = ap.parse_args()

    keys = [args.series] if args.series else sorted(SERIES)
    for k in keys:
        if k not in SERIES:
            print("unknown series %r. Known: %s" % (k, ", ".join(sorted(SERIES))))
            return 2

    fixed = problems = 0
    for key in keys:
        prefix, label = SERIES[key]
        posts = load_series(prefix)
        if not posts:
            continue
        print("%s (%d posts)" % (label, len(posts)))
        for i, (n, slug, _title) in enumerate(posts):
            nxt = (posts[i + 1][1], posts[i + 1][2]) if i + 1 < len(posts) else None
            state, detail = fix_page(slug, nxt, args.check)
            if state == "fixed":
                fixed += 1
                print("  #%-3d %-52s %s" % (n, slug[:52], detail))
            elif state == "missing":
                problems += 1
                print("  #%-3d %-52s PROBLEM: %s" % (n, slug[:52], detail))
        print()

    verb = "would change" if args.check else "changed"
    print("%s %d page(s); %d problem(s)." % (verb, fixed, problems))
    if args.check and (fixed or problems):
        return 1
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
