#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Point every page at the current feedback.js, by content hash.

    python scripts/stamp_feedback.py            # stamp, report what changed
    python scripts/stamp_feedback.py --check    # report only, exit 1 if stale

Why this exists
---------------
blog/assets/feedback.js is loaded by 239 pages, and it shipped unversioned --
which is the exact failure this repo already paid for once: a script linked
with no version is never cache-busted for anyone, so a returning reader keeps
running the copy their browser already has while the file on the server is
correct. Nothing looks broken. The fix is deployed and the reader still sees
the old behaviour.

The pages cannot all be rebuilt to pick up a new hash, either: sync_blog treats
the Architecture Series as read-only pass-through, so 105 of them are
build-once artefacts edited in place. So this stamps in place, across
everything, from one source of truth -- the hash of the file itself.

Newlines are normalised before hashing. The working tree here is CRLF and CI is
LF, and hashing the bytes as they sit on disk gives two different answers for
identical content -- which would have every local build disagree with every CI
build forever.
"""
import argparse
import hashlib
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET = os.path.join(ROOT, "blog", "assets", "feedback.js")
SKIP = {".git", "node_modules", "_archive", "__pycache__"}
LINK = re.compile(r'(/blog/assets/feedback\.js)(\?v=[a-f0-9]+)?')


def current():
    raw = io.open(ASSET, "rb").read().replace(b"\r\n", b"\n")
    return hashlib.md5(raw).hexdigest()[:8]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report without writing, and fail if anything is stale")
    args = ap.parse_args()

    want = current()
    print("  feedback.js hashes to %s" % want)

    stale, ok = [], 0
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP and not d.startswith(".")]
        for name in files:
            if not name.endswith((".html", ".py")):
                continue
            path = os.path.join(base, name)
            # Not this file. It contains the asset path as a literal, so the
            # first run stamped its own source and left the guard below
            # matching one frozen version -- after which it would have found
            # nothing to restamp, quietly, forever.
            if os.path.abspath(path) == os.path.abspath(__file__):
                continue
            try:
                s = io.open(path, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            if not LINK.search(s):
                continue
            rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
            got = set(m.group(2) for m in LINK.finditer(s))
            if got == {"?v=" + want}:
                ok += 1
                continue
            stale.append(rel)
            if args.check:
                continue
            io.open(path, "w", encoding="utf-8", newline="\n").write(
                LINK.sub(lambda m: m.group(1) + "?v=" + want, s))

    if args.check:
        print("  %d page(s) current, %d stale" % (ok, len(stale)))
        if stale:
            print("\n  PAGES ASKING FOR THE WRONG FEEDBACK.JS\n")
            for rel in stale[:15]:
                print("  - %s" % rel)
            if len(stale) > 15:
                print("    ...and %d more" % (len(stale) - 15))
            print("\n  Run: python scripts/stamp_feedback.py")
            return 1
        print("  every page asks for the current feedback.js.")
        return 0

    print("  %d page(s) already current, %d restamped" % (ok, len(stale)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
