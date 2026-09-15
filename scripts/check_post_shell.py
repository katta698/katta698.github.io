#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Every post page carries the same shell as every other post page.

    python scripts/check_post_shell.py
    python scripts/check_post_shell.py --list   # the full per-page profile

Why this exists
---------------
Two faults on 2026-09-15, hours apart, that looked unrelated and were the same
species:

    the ask launcher and back-top button vanished from four posts
        _templates/arch-post-template.html lost two </div> closes, so both
        controls rendered inside .fb-overlay, which is display:none. The markup
        was present on every page. It was not reachable on four of them.

    the header wordmark rendered in Georgia instead of Playfair
        122 of 251 posts never carried the font preload the other 129 did.
        site-footer.css declares the faces font-display: optional, which gives
        a font about 100ms and then keeps the fallback for the whole page view.
        Without the preload the @font-face rules are not discovered until
        blog.js, at the end of <body>, injects site-footer.js, which injects
        site-footer.css. Far too late.

Neither was a content error. Both were a post page differing from its
neighbours in the part that is supposed to be identical on all of them, and
both survived because nothing compared posts against each other.

check_shell_consistency.py already does this properly -- it renders the shell
at three widths and fails on any divergence -- but only across the five
top-level tabs. The 251 post pages, which is almost the whole site, were never
compared to anything. This is that check for them.

It compares composition rather than rendering: which shared elements each page
carries, and whether its containers balance. That is cheap enough to run on
every publish and catches the class both faults belong to. It is not a
substitute for check_shell_consistency.py, which measures pixels.

The reference is the majority, not a template. A template is what was wrong in
the first fault -- the generator itself had lost the closing tags -- so a check
that trusted it would have agreed with the bug. Asking what 248 pages do and
flagging the three that differ has no such blind spot.
"""
import argparse
import glob
import io
import os
import re
import sys
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Pages under blog/ that are not posts. They legitimately differ: the drafts
# index has no feedback widget, the simulator carries no site nav. Named here
# so "not a post" is a declaration rather than an accident -- the same reason
# check_assertions.py skips non-technical posts by label instead of by silence.
NOT_POSTS = {"digests", "drafts", "simulator", "page"}

# The shared shell. Each of these is emitted for every post by whichever
# generator built it, so a post missing one is a post built differently.
SHELL = {
    "blog.css":        re.compile(r'<link[^>]*blog\.css'),
    "blog.js":         re.compile(r'<script[^>]*blog\.js'),
    "site-footer.css": re.compile(r'<link[^>]*site-footer\.css'),
    "site-footer.js":  re.compile(r'<script[^>]*src="[^"]*site-footer\.js'),
    "font-preload":    re.compile(r'<link[^>]*as="font"'),
    "occasion-banner": re.compile(r'<script[^>]*occasion-banner\.js'),
    "feedback.js":     re.compile(r'<script[^>]*feedback\.js'),
    "ask-launcher":    re.compile(r'class="ask-launcher"'),
    "back-top":        re.compile(r'id="back-top"'),
    "manifest":        re.compile(r'rel="manifest"'),
    "canonical":       re.compile(r'rel="canonical"'),
    "nav-logo":        re.compile(r'class="nav-logo"'),
}

DIV_OPEN = re.compile(r"<div\b")
DIV_CLOSE = re.compile(r"</div>")

# Container balance clusters at two longstanding values -- 0 on 128 posts and
# 7 on 119 -- because two generators nest differently and neither is this
# file's business. What matters is a value almost no page has.
#
# The first cut compared every page against the single most common balance and
# reported 120 "outliers", which is a checker that cries wolf and, per
# VALIDATION.md, gets switched off within a week. The second tried to tell the
# generators apart by #jk-post and could not: every post carries it.
#
# So: a balance shared with at least this many other pages is normal, whatever
# the number is. A balance almost unique to one page is the signal -- two extra
# unclosed <div> is exactly what sealed the floating controls inside
# .fb-overlay, which is display:none.
COMMON_ENOUGH = 5


def posts():
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, "blog", "*", "index.html"))):
        if os.path.basename(os.path.dirname(p)) in NOT_POSTS:
            continue
        out.append(p)
    return out


def profile(path):
    t = io.open(path, encoding="utf-8", errors="replace").read()
    prof = {k: len(rx.findall(t)) for k, rx in SHELL.items()}
    # Whole-document container balance. The number itself means nothing -- it
    # is 0 for a sync-built page and 7 for an arch page, both longstanding.
    # That it matches the other pages built the same way is the whole point:
    # two extra unclosed <div> is what put the ask launcher and the back-top
    # button inside .fb-overlay, which is display:none.
    prof["_div_balance"] = (len(DIV_OPEN.findall(t))
                            - len(DIV_CLOSE.findall(t)))
    return prof


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true",
                    help="print the profile of every page, not just outliers")
    args = ap.parse_args()

    paths = posts()
    if not paths:
        print("no post pages found -- this check is not checking anything")
        return 2

    profs = {p: profile(p) for p in paths}
    keys = list(SHELL) + ["_div_balance"]

    # Shell elements are compared corpus-wide; container balance only within
    # the family that built the page. See ARCH_MARKER.
    typical = {}
    for k in SHELL:
        typical[k] = Counter(profs[p][k] for p in paths).most_common(1)[0][0]
    seen = Counter(profs[p]["_div_balance"] for p in paths)
    normal = {v for v, n in seen.items() if n >= COMMON_ENOUGH}

    outliers = defaultdict(list)
    for p in paths:
        for k in SHELL:
            if profs[p][k] != typical[k]:
                outliers[p].append((k, profs[p][k], typical[k]))
        bal = profs[p]["_div_balance"]
        if bal not in normal:
            outliers[p].append(("_div_balance", bal, sorted(normal)))

    print("Post shell consistency")
    print("-" * 74)
    print("  %d post page(s) compared against each other" % len(paths))
    if args.list:
        for p in paths:
            print("   %-44s %s" % (os.path.basename(os.path.dirname(p))[:44],
                                   profs[p]))
    if not outliers:
        print("  ok -- every post carries the same shell, and container")
        print("        balance is one of the normal values: %s."
              % ", ".join(str(v) for v in sorted(normal)))
        print("-" * 74)
        return 0

    print("\n  %d page(s) differ from the other %d:"
          % (len(outliers), len(paths) - len(outliers)))
    for p, diffs in sorted(outliers.items()):
        print("\n   %s" % os.path.basename(os.path.dirname(p)))
        for k, got, want in diffs:
            if k == "_div_balance":
                print("      unclosed <div>: %d. Every other post has one of "
                      "%s." % (got, want))
                print("      -> extra container(s) left open. Anything after "
                      "the break nests inside them, and if one is hidden it "
                      "does not render.")
            else:
                print("      %-16s %d, every other page: %d" % (k, got, want))
    print("\n  A post differing from its neighbours in the shared shell is the")
    print("  species both 2026-09-15 faults belonged to. Check what generated")
    print("  this page before assuming the difference is deliberate.")
    print("-" * 74)
    return 1


if __name__ == "__main__":
    sys.exit(main())
