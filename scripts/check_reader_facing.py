#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Catch developer leftovers that reach a reader's screen.

    python scripts/check_reader_facing.py
    python scripts/check_reader_facing.py --list

Why this exists
---------------
The site's checks all test machine-checkable properties: contrast ratios, link
syntax, colour values, page structure. Every one of those passed while these
shipped to a live page in a single day:

    a link to a raw .json file, offered to readers as "evidence"
    "no record before %d %b"      -- a strftime format that never ran
    "=======" and the page twice  -- git conflict markers, committed
    "refreshed every 15 minutes"  -- beside a timestamp saying 49 minutes

None of those are wrong in any way a checker was asking about. They are wrong
in the sense a person notices in one second and a validator never does.

This is the mechanical slice of that -- not judgment, just the leftovers that
are always mistakes and can be recognised by shape. It cannot tell whether a
sentence is worth saying. It can tell that a page is showing a reader a raw
config file, a template placeholder, or a printf specifier.

Every rule here corresponds to something that actually shipped. New rules
should earn their place the same way.
"""
import argparse
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "node_modules", ".github", "scripts", "posts"}

# Text a reader sees, i.e. outside tags, scripts and styles.
TAGS = re.compile(r"(?is)<(script|style|template)[^>]*>.*?</\1>")
STRIP = re.compile(r"<[^>]+>")


def visible(html):
    return STRIP.sub(" ", TAGS.sub(" ", html))


# Code samples are CONTENT on a technical blog. A Python snippet containing
# "%s" is the post doing its job, so anything inside <code> or <pre> is removed
# before the visible-text rules run. Without this the check flagged three blog
# posts for printing their own example code, which is the kind of false alarm
# that gets a check switched off.
CODE = re.compile(r"(?is)<(code|pre|kbd|samp)[^>]*>.*?</\1>")


def prose(html):
    return STRIP.sub(" ", CODE.sub(" ", TAGS.sub(" ", html)))


def has_token(raw, token):
    """Is this custom property actually defined in this file?"""
    return re.search(re.escape(token) + r"\s*:", raw) is not None


RULES = [
    # Shipped 2026-09-08: `git stash pop` conflicted, `git add -A` staged the
    # markers, and the live page rendered "=======" with everything twice.
    #
    # Anchored and exact. Matching a bare run of "=" flagged an HTML comment
    # divider (<!-- ======== -->), which is decoration every generator writes.
    # A real marker is a line that is EXACTLY seven characters, or seven
    # followed by a branch name.
    ("git conflict marker",
     re.compile(r"(?m)^(?:={7}|<{7}(?: .+)?|>{7}(?: .+)?)\s*$"), "raw"),

    # Shipped 2026-09-09: the timeline band read "no record before %d %b"
    # because a strftime format was double-escaped and never ran.
    ("printf/strftime specifier in visible text",
     re.compile(r"%[-0-9.]*[sdif](?![a-zA-Z0-9])|%[YmdHMS](?![a-zA-Z0-9])"), "prose"),

    ("unsubstituted template placeholder",
     re.compile(r"__[A-Z][A-Z0-9_]{2,}__"), "raw"),

    # Shipped 2026-09-09: "the record is public at status-runs.json" -- true,
    # and useless to a reader, who gets a wall of JSON.
    #
    # Only links to files THIS SITE serves. A github.com URL ending in .json
    # renders as a syntax-highlighted page with history and blame, which is a
    # perfectly good thing to send a reader to; flagging those made the rule
    # fire on the very link that replaced the bad one.
    ("link to a raw data or config file on this site",
     re.compile(r'<a\b[^>]*href="(?!https?://)[^"]*\.(?:json|ya?ml|csv|log|py|ps1)"',
                re.I), "raw"),


    # Shipped 2026-09-09: the Sources table linked the raw feeds it reads --
    # AWS's gzip history (downloads as a file), Azure's status-history API
    # (an HTML fragment that renders as half a page) and Google's
    # products.json (a wall of text). Naming an endpoint is right; sending a
    # reader to it is not.
    #
    # github.com is excluded because it renders JSON and YAML as a page with
    # history and blame, which is a fine place to send someone. Any other
    # host serving a data file is not.
    ("link to a vendor's raw data endpoint",
     re.compile(r'<a\b[^>]*href="https?://(?!(?:[a-z0-9-]+\.)*github\.com/)'
                r'[^"]*\.(?:json|ya?ml|csv)(?:[?#][^"]*)?"', re.I), "raw"),
    ("internal identifier in visible text",
     re.compile(r"\b(?:session_01[A-Za-z0-9]{10,}|env_01[A-Za-z0-9]{10,})\b"), "prose"),

    ("unfinished-work marker",
     re.compile(r"\b(?:TODO|FIXME|Lorem ipsum|PLACEHOLDER)\b"), "prose"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    pages = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f.endswith(".html"):
                pages.append(os.path.join(base, f))
    pages.sort()

    findings = []
    for p in pages:
        rel = os.path.relpath(p, ROOT).replace("\\", "/")
        raw = io.open(p, encoding="utf-8", errors="replace").read()
        vis = prose(raw)
        # An undefined custom property invalidates the whole declaration and
        # the element silently loses its colour. This has bitten four times
        # (--accent-gold, --nav-bg, --accent, --ink). Only report a token that
        # is USED here and defined nowhere in the same file -- flagging every
        # use meant flagging index.html, which defines it correctly.
        for tok in ("--accent-gold", "--nav-bg", "--cloud-accent"):
            if ("var(%s)" % tok) in raw and not has_token(raw, tok):
                findings.append((rel, "undefined custom property", tok,
                                 "used in var() and never defined in this file"))

        for name, rx, scope in RULES:
            hay = raw if scope == "raw" else vis
            for m in rx.finditer(hay):
                start = max(0, m.start() - 45)
                ctx = re.sub(r"\s+", " ", hay[start:m.end() + 45]).strip()
                findings.append((rel, name, m.group(0)[:40], ctx[:110]))
                break                      # one per rule per page is enough

    if args.list:
        for rel, name, hit, ctx in findings:
            print("  %-44s %s" % (rel, name))

    # Silence must not be able to masquerade as cleanliness.
    if not pages:
        print("  NO PAGES SCANNED. The walk found nothing, so this proves nothing.")
        return 1

    if findings:
        print("\n  DEVELOPER LEFTOVERS ON READER-FACING PAGES\n")
        for rel, name, hit, ctx in findings:
            print("  %s" % rel)
            print("    %s  ->  %s" % (name, hit))
            print("    ...%s..." % ctx)
            print()
        print("  %d finding(s) across %d page(s)." % (len(findings), len(pages)))
        print("  These are not style opinions. Each one is something that")
        print("  shipped to this live site and was found by a reader, not a check.")
        return 1

    print("  %d page(s) clean: no conflict markers, placeholders, format "
          "specifiers, raw-file links or internal ids." % len(pages))
    return 0


if __name__ == "__main__":
    sys.exit(main())
