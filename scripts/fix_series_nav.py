#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Set Previous/Next on the architecture pages sync_blog.py never rebuilds.

Why this exists
---------------
`build_arch_post.py` builds a page once, at publish time, and drops the next half
of the post-nav because at that moment nothing follows the post. Those pages are
`externally_built`, so `sync_blog.py` never regenerates them — which means when
the next post ships, the previous one is never updated to point forward at it.

Measured 2026-08-15, only 6 of 24 architecture pages carried a next link and
`gcp-architecture-resource-hierarchy` had no navigation at all.

Chronological, not per-series
-----------------------------
The order is chronological across every post, matching what sync_blog.py does
for the ~110 pages it builds itself:

    post["_prev"] = visible_posts[i + 1]     # the next older post, any series
    post["_next"] = visible_posts[i - 1]     # the next newer post, any series

So a reader on any sync-built page walks the whole blog, not one series. This
script exists to make the hand-built pages agree with them. It computes the same
order from posts/ (see load_order) and cross-checks it against sync's own
cards.json, warning on any divergence rather than assuming the two agree.

The first version of this script scoped the nav to each series instead, which was
wrong in two ways. It made the arch pages the only ones on the site that navigate
differently from everything else. And it led me to misread the older AWS pages
whose Previous points at a Weekly Lab post: those were correct chronological
links, not leftovers from before the conventions settled, and the earlier
version of this file deliberately preserved them for the wrong reason.

It sets both halves, and it is idempotent: a page already carrying the right
links is left untouched, so it is safe to run on every publish and safe to run
twice.

Usage
-----
    python scripts/fix_series_nav.py            # fix every hand-built page
    python scripts/fix_series_nav.py --check    # report only, exit 1 if wrong
"""
import argparse
import glob
import io
import json
import os
import re
import sys

import yaml

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARDS = os.path.join(ROOT, "blog", "cards.json")

# The slug prefixes sync_blog.py passes through untouched, i.e. the pages whose
# nav nothing else maintains. Keep in step with `externally_built` there.
HAND_BUILT = ("aws-architecture-", "azure-architecture-", "gcp-architecture-")

LINK_RE = {
    "prev": re.compile(r'<a href="[^"]*" class="post-nav-link prev">.*?</a>', re.S),
    "next": re.compile(r'<a href="[^"]*" class="post-nav-link next">.*?</a>', re.S),
}
DIR_LABEL = {"prev": "← Previous", "next": "Next →"}


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def link_html(kind, slug, title):
    return ('<a href="/blog/%s/" class="post-nav-link %s">'
            '<span class="post-nav-dir">%s</span>'
            '<span class="post-nav-title">%s</span></a>'
            % (slug, kind, DIR_LABEL[kind], esc(title)))


def href_of(anchor):
    m = re.search(r'href="([^"]*)"', anchor)
    return m.group(1) if m else ""


def fix_page(slug, prev, nxt, check):
    """Make this page's nav match (prev, nxt); each is (slug, title) or None."""
    path = os.path.join(ROOT, "blog", slug, "index.html")
    if not os.path.isfile(path):
        return "missing", "no served page at blog/%s/" % slug
    html = io.open(path, encoding="utf-8").read()

    # The post-nav, not the site header's <nav>. These pages have two, and
    # matching the first </nav> in the document put 19 Next links inside the top
    # navigation bar, floating over the header nowhere near the post.
    navm = re.search(r'<nav class="post-nav"[^>]*>(.*?)</nav>', html, re.S)
    if not navm:
        return "missing", 'no <nav class="post-nav"> element'

    want = "".join(link_html(k, *t) for k, t in (("prev", prev), ("next", nxt)) if t)
    have = navm.group(1)

    # Compare destinations, not markup. Titles on existing links are sometimes
    # the short form rather than the full one -- pages were hand-built at
    # different times -- and rewriting that is churn on a page nothing else
    # regenerates.
    def dests(fragment):
        return {k: href_of(m.group(0)) for k, rx in LINK_RE.items()
                for m in [rx.search(fragment)] if m}
    if dests(have) == dests(want):
        return "ok", ""

    new = html[:navm.start(1)] + want + html[navm.end(1):]
    changes = []
    for k, t in (("prev", prev), ("next", nxt)):
        old_d = dests(have).get(k)
        new_d = "/blog/%s/" % t[0] if t else None
        if old_d != new_d:
            changes.append("%s: %s -> %s" % (k, old_d or "(none)", new_d or "(none)"))
    if not check:
        io.open(path, "w", encoding="utf-8", newline="\n").write(new)
    return "fixed", "; ".join(changes)


def load_order():
    """Newest-first order of every visible post, as (slug, title).

    Computed from posts/ rather than read from blog/cards.json, because this runs
    from build_arch_post.py BEFORE sync regenerates cards.json -- so the card
    file does not yet contain the post just built, and using it would set the
    predecessor's Next from an order the new post is missing from.

    It mirrors sync_blog.py's rule deliberately: every post with a usable title
    and date, sorted by date descending. `check_matches_sync` below verifies that
    claim against cards.json instead of trusting this comment.
    """
    out = []
    for path in glob.glob(os.path.join(ROOT, "posts", "*.html")):
        raw = io.open(path, encoding="utf-8").read()
        if not raw.startswith("---"):
            continue
        try:
            fm = yaml.safe_load(raw.split("---", 2)[1]) or {}
        except yaml.YAMLError:
            continue
        title, slug, date = fm.get("title"), fm.get("slug"), fm.get("date")
        if not (title and slug and date):
            continue
        out.append((str(date)[:19], str(slug), str(title)))
    # Slug is the tie-break, and it is not optional. Sorting on date alone is a
    # STABLE sort, so two posts sharing a timestamp keep the order glob() handed
    # back -- which is filesystem order, and differs between platforms. That is
    # not hypothetical: arch-024 and gcp-004 were both published at
    # 2026-08-17T09:00:00 by two different windows, this check passed on Windows
    # and failed on the Linux CI runner reporting 8 changed pages, and the diff
    # was real -- the two orders genuinely disagreed about which came first.
    #
    # sync_blog.py sorts by the same (date, slug) key for the same reason. If one
    # of them changes, the other must, or check_matches_sync starts failing on a
    # difference that is nobody's bug.
    #
    # Which post wins a tie is arbitrary (alphabetically later slug first, since
    # reverse=True applies to the whole tuple). Arbitrary but identical everywhere
    # is the property that matters; CLAUDE.md's advice to give every post a real
    # publish time is what avoids the tie in the first place.
    out.sort(key=lambda r: (r[0], r[1]), reverse=True)
    return [(slug, title) for _d, slug, title in out]


def check_matches_sync(order):
    """Warn if our order disagrees with the one sync actually built pages from.

    A silent divergence here would give the hand-built pages different
    neighbours from every sync-built page -- the exact inconsistency this script
    was rewritten to remove.
    """
    if not os.path.isfile(CARDS):
        return
    theirs = [c["slug"] for c in json.load(io.open(CARDS, encoding="utf-8"))]
    ours = [s for s, _t in order]
    if ours != theirs:
        only_ours = [s for s in ours if s not in theirs]
        only_theirs = [s for s in theirs if s not in ours]
        print("  WARNING: order differs from blog/cards.json.")
        if only_ours:
            print("    in posts/ but not cards.json: %s" % ", ".join(only_ours[:5]))
        if only_theirs:
            print("    in cards.json but not posts/: %s" % ", ".join(only_theirs[:5]))
        if not only_ours and not only_theirs:
            first = next(i for i, (a, b) in enumerate(zip(ours, theirs)) if a != b)
            print("    same posts, different sequence, first at index %d: "
                  "%s vs %s" % (first, ours[first], theirs[first]))


def backfill_all(quiet=False, check=False):
    order = load_order()
    check_matches_sync(order)
    fixed = problems = 0
    for i, (slug, _title) in enumerate(order):
        if not slug.startswith(HAND_BUILT):
            continue                      # sync rebuilds this page's nav itself
        prev = order[i + 1] if i + 1 < len(order) else None
        nxt = order[i - 1] if i > 0 else None
        state, detail = fix_page(slug, prev, nxt, check)
        if state == "fixed":
            fixed += 1
            if not quiet:
                print("  %-46s %s" % (slug[:46], detail))
        elif state == "missing":
            problems += 1
            print("  %-46s PROBLEM: %s" % (slug[:46], detail))
    return fixed, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report what is wrong and exit non-zero, changing nothing")
    args = ap.parse_args()
    fixed, problems = backfill_all(quiet=False, check=args.check)
    verb = "would change" if args.check else "changed"
    print("%s %d page(s); %d problem(s)." % (verb, fixed, problems))
    if args.check and (fixed or problems):
        return 1
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
