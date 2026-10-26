#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare the FACTS in a rewritten post against the version it replaced.

    python scripts/diff_post_facts.py <post.html> [--since <git-ref>]

WHY THIS EXISTS (2026-10-25)
----------------------------
Jay asked the right question while 23 published posts were being restructured:
"should I worry about data being rewritten... or do I have to go through each
and every post again to validate?"

The restructure is not a mechanical move. Each post is READ and RE-EXPRESSED
into the mandated nine sections. `lab_post_kit.py` guarantees the front matter,
the publish date and the figure set survive untouched -- and guarantees nothing
whatsoever about whether the prose still says the same thing. A dropped
qualifier, a transposed decimal or a confidently invented figure passes every
other gate in this repository.

So this compares the numbers.

  DROPPED  a figure in the old version that is absent from the new one.
           Usually fine -- the rewrite cuts 40-60% of the words on purpose --
           but worth eyeballing for anything load-bearing.

  ADDED    a figure in the new version that does NOT appear in the old one.
           This is the dangerous category and the reason the script exists.
           Every number in a restructured post must have come from the post it
           replaced, from the repository, or from a measurement taken today.
           A number that appears from nowhere is the failure mode nobody
           catches by reading, because it reads perfectly.

It compares numbers rather than sentences deliberately: numbers are where
"roughly the same meaning" stops being good enough, and they are the part a
reader will quote.
"""
from __future__ import annotations

import argparse
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Money, percentages, durations, counts with a unit, and bare multi-digit
# numbers. Deliberately greedy: a false positive costs a glance, a false
# negative costs a wrong number in a published post.
NUM = re.compile(
    r"\$\s?\d[\d,]*(?:\.\d+)?"          # $1.26, $23.28
    r"|\d+(?:\.\d+)?\s?%"                # 81%
    r"|\d+(?:\.\d+)?\s?(?:ms|s|sec|secs|seconds|min|mins|minutes|hr|hrs|hours|days?|GB|MB|KiB|MiB|TB)\b"
    r"|\b\d{2,}\b"                       # 373, 2026, 19
    r"|\b\d+(?:\.\d+)+\b",               # 1.15.8
    re.I)

# Noise that changes for reasons unrelated to meaning.
IGNORE = re.compile(r"^(?:20\d\d|0|1|2|3|4|5|6|7|8|9)$")


def body_text(html: str) -> str:
    parts = html.split("---", 2)
    body = parts[2] if len(parts) >= 3 else html
    body = re.sub(r"<svg.*?</svg>", " ", body, flags=re.S)   # diagram coords
    body = re.sub(r"<!--.*?-->", " ", body, flags=re.S)
    body = re.sub(r'<img[^>]*>', " ", body)                  # filenames
    body = re.sub(r'href="[^"]*"', " ", body)                # urls
    body = re.sub(r"<[^>]+>", " ", body)
    return re.sub(r"\s+", " ", body)


def facts(html: str):
    out = {}
    text = body_text(html)
    for m in NUM.finditer(text):
        tok = re.sub(r"\s+", "", m.group(0))
        if IGNORE.match(tok):
            continue
        ctx = text[max(0, m.start() - 55):m.end() + 55].strip()
        out.setdefault(tok, ctx)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("post")
    ap.add_argument("--since", default=None,
                    help="git ref holding the previous version "
                         "(default: the commit before the file last changed)")
    ap.add_argument("--repo", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    help="defaults to this checkout, so it works from any series worktree")
    args = ap.parse_args()

    rel = args.post.replace("\\", "/")
    if not rel.startswith("posts/"):
        rel = "posts/" + rel.rsplit("/", 1)[-1]

    ref = args.since
    if not ref:
        log = subprocess.run(["git", "log", "--format=%H", "-2", "--", rel],
                             cwd=args.repo, capture_output=True, text=True).stdout.split()
        if len(log) < 2:
            raise SystemExit("no previous version of %s in git" % rel)
        ref = log[1]

    old = subprocess.run(["git", "show", "%s:%s" % (ref, rel)],
                         cwd=args.repo, capture_output=True, text=True,
                         encoding="utf-8", errors="replace").stdout
    if not old.strip():
        raise SystemExit("could not read %s at %s" % (rel, ref[:12]))
    new = io.open("%s/%s" % (args.repo, rel), encoding="utf-8").read()

    o, n = facts(old), facts(new)
    dropped = sorted(set(o) - set(n))
    added = sorted(set(n) - set(o))

    print("%s   (against %s)" % (rel.rsplit("/", 1)[-1], ref[:12]))
    print("  numbers: %d before, %d after" % (len(o), len(n)))

    if added:
        print("\n  ADDED - these appear in the new version and NOT the old one.")
        print("  Each must trace to the repo or a measurement, or it is invented:")
        for t in added:
            print("    %-12s %s" % (t, n[t][:95]))
    else:
        print("\n  ADDED: none. Every number in the new version was in the old one.")

    if dropped:
        print("\n  dropped (%d) - expected, the rewrite cuts hard. Scan for anything load-bearing:"
              % len(dropped))
        print("    " + "  ".join(dropped[:40]))

    return 1 if added else 0


if __name__ == "__main__":
    sys.exit(main())
