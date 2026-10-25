#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A post's served page must have been built from the post as it stands now.

    python scripts/check_built_pages_current.py
    python scripts/check_built_pages_current.py week-09      # one post
    python scripts/check_built_pages_current.py --self-test  # prove it can fail

Why this exists
---------------
`posts/<slug>.html` is the source. `blog/<slug>/index.html` is what a reader
loads, and `sync_blog.py` generates it. Editing the source and committing
without re-running sync changes nothing anyone can see -- and nothing fails.
`git push` reports success, the commit is real, the file on origin genuinely
contains the edit, and the site serves the previous version indefinitely.

It happened on 2026-10-16. Three consecutive pushes revised the Week 09 draft's
"What You Need to Know" section; all three touched only `posts/`. Each push was
reported as delivered and each was verified by curling the live page, which
returned the OLD text -- read, at the time, as GitHub Pages deploy lag. It was
not lag. The built page had never been regenerated, so no amount of waiting was
ever going to produce the change.

The nearest existing check cannot catch this. `check_index_complete.py` asserts
that a post REACHED the generated surfaces -- card, cards.json, rss -- and it
skips drafts entirely, because a draft is deliberately absent from all of them.
This failure was a draft whose page existed and was simply out of date.
Existence and freshness are different assertions.

How it decides, and why not by timestamp
----------------------------------------
`sync_blog.py` stamps each page it writes with `<!-- src-sha256 ... -->`, the
hash of the source file it was built from. This check recomputes that hash and
compares. Equal means the page was built from exactly this source; different
means it was not; absent means the page predates the stamp or was not written
by the generator at all.

Two timestamp-based versions were written first and BOTH shipped wrong, in
opposite directions, within an hour:

- Comparing last-commit times flagged every publish. Commit the post, rebase,
  sync, commit the build is the normal order, and in the window before that
  last commit the source's commit is newer than the build's.
- "Never stale while the build is uncommitted" fixed that and blinded the
  check completely: during the same window an unsynced source edit also reads
  clean, which is the one thing this file exists to catch.
- Falling back to file mtimes in that window failed too -- `git checkout` and
  `git rebase` rewrite mtimes without changing what was built from what, so a
  page that was genuinely current reported stale.

No clock answers "was this built from that". A fingerprint does, with no
windows, no regimes, and nothing to tune.

What it deliberately does not do
--------------------------------
It does not run the generator. A check that fixes what it finds teaches you to
ignore what it says, and syncing is not always the right answer -- a stale page
can also mean a bad rebase, which regenerating would paper over.

Architecture Series posts are built by a different pipeline, carry no stamp and
are skipped, the same exemption those pages have in `sync_blog.py` itself.
"""
import argparse
import hashlib
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
POSTS = os.path.join(ROOT, "posts")

STAMP_RE = re.compile(r"<!--\s*src-sha256\s+([0-9a-f]{64})\s*-->")

# Built elsewhere, from _templates/arch-post-template.html -- see the
# externally_built handling in sync_blog.py. Nothing in posts/ is the input to
# those pages, so there is nothing here to fingerprint and they carry no stamp.
#
# These prefixes are COPIED from sync_blog.py's own test, deliberately as a
# literal rather than a guess: the first version here matched only "arch-" and
# flagged all 129 Azure Architecture posts as unstamped, which is a check
# failing 129 times for being wrong. If sync_blog.py's list changes, this one
# has to change with it -- hence the assertion below, which fails loudly
# instead of letting the two drift apart silently.
EXTERNALLY_BUILT_PREFIXES = ("arch-", "az-", "gcp-")


def _assert_prefixes_match_generator():
    """The two lists must stay identical; a drift makes this check lie."""
    gen = os.path.join(HERE, "sync_blog.py")
    if not os.path.exists(gen):
        return
    with open(gen, encoding="utf-8") as fh:
        src = fh.read()
    m = re.search(r'post_file\.name\.startswith\(\(([^)]*)\)\)', src)
    if not m:
        return
    theirs = tuple(re.findall(r'"([^"]+)"', m.group(1)))
    if theirs and theirs != EXTERNALLY_BUILT_PREFIXES:
        sys.exit("sync_blog.py's externally-built prefixes are "
                 f"{theirs}, this check has {EXTERNALLY_BUILT_PREFIXES}. "
                 "Update EXTERNALLY_BUILT_PREFIXES to match.")


def verdict(source_bytes, built_text):
    """CURRENT / STALE / UNSTAMPED, pure so --self-test can prove it.

    Line endings are normalised before hashing, on BOTH sides - here and in
    sync_blog.py. git's autocrlf rewrites LF to CRLF on checkout, so the bytes
    of a source file change without its content changing, and a hash over raw
    bytes then reports a perfectly current page as stale.

    Found 2026-10-25, when this check blocked a push over a 2023 post nobody
    had touched: the stamp matched the LF-normalised hash exactly. A blocking
    gate that cries wolf is worse than no gate, because the first thing anyone
    does is bypass it - which is how this repo ended up pushing with
    --no-verify in the first place.

    bytes([13, 10]) rather than an escape sequence: three attempts at this edit
    were destroyed by backslash handling in shell heredocs. A byte literal has
    nothing to mangle.
    """
    normalised = source_bytes.replace(bytes([13, 10]), bytes([10]))
    m = STAMP_RE.search(built_text)
    if not m:
        return "UNSTAMPED"
    if m.group(1) == hashlib.sha256(normalised).hexdigest():
        return "CURRENT"
    return "STALE"


def slug_of(filename, text):
    m = re.search(r"^slug:\s*['\"]?([A-Za-z0-9._-]+)", text, re.M)
    if m:
        return m.group(1)
    return os.path.splitext(filename)[0]


def check(filters):
    _assert_prefixes_match_generator()
    report, failures, checked, skipped = [], 0, 0, 0

    for fn in sorted(os.listdir(POSTS)):
        if not fn.endswith(".html"):
            continue
        if filters and not any(a in fn for a in filters):
            continue
        if fn.startswith(EXTERNALLY_BUILT_PREFIXES):
            skipped += 1
            continue

        with open(os.path.join(POSTS, fn), "rb") as fh:
            raw = fh.read()
        slug = slug_of(fn, raw.decode("utf-8", "replace"))
        built_rel = os.path.join("blog", slug, "index.html")
        built_abs = os.path.join(ROOT, built_rel)
        checked += 1

        if not os.path.exists(built_abs):
            report.append(f"  [FAIL] {fn}: no built page at {built_rel}")
            failures += 1
            continue

        with open(built_abs, encoding="utf-8") as fh:
            state = verdict(raw, fh.read())

        if state == "CURRENT":
            report.append(f"  [ ok ] {fn}")
        elif state == "STALE":
            report.append(
                f"  [FAIL] {fn}: {built_rel} was built from a DIFFERENT version "
                "of this post. The site serves that one, not this one.")
            failures += 1
        else:
            report.append(
                f"  [FAIL] {fn}: {built_rel} carries no src-sha256 stamp, so it "
                "predates the current generator and cannot be checked.")
            failures += 1

    print("\n".join(report))
    tail = f", {skipped} externally-built skipped." if skipped else "."
    print(f"\n{checked} post(s) checked{tail}")
    if failures:
        print(f"{failures} built page(s) do not match their source.")
        print("Run: python scripts/sync_blog.py   and commit blog/.")
        print("A push that does not regenerate them changes nothing a reader sees.")
        return 1
    print("Every served page was built from the post as it stands now.")
    return 0


def self_test():
    src = b"<h1>the post</h1>"
    good = hashlib.sha256(src).hexdigest()
    other = hashlib.sha256(b"<h1>an older draft</h1>").hexdigest()
    cases = [
        (src, "<html>x</html>\n<!-- src-sha256 " + good + " -->\n", "CURRENT",
         "page stamped with this source"),
        (src, "<html>x</html>\n<!-- src-sha256 " + other + " -->\n", "STALE",
         "page stamped with a different source"),
        (src, "<html>x</html>\n", "UNSTAMPED",
         "page carries no stamp at all"),
        (src, "<!-- src-sha256 " + good.upper() + " -->", "UNSTAMPED",
         "an uppercase digest is not a stamp (the regex is strict)"),
        (b"<h1>the post</h1> ", "<!-- src-sha256 " + good + " -->", "STALE",
         "one trailing space in the source is a different post"),
        (bytes([60,104,49,62,116,104,101,13,10,112,111,115,116]),
         "<!-- src-sha256 " + hashlib.sha256(bytes([60,104,49,62,116,104,101,10,112,111,115,116])).hexdigest() + " -->",
         "CURRENT",
         "CRLF source against an LF-built stamp is NOT stale (autocrlf)"),
    ]
    bad = 0
    for source, built, want, label in cases:
        got = verdict(source, built)
        ok = got == want
        bad += not ok
        mark = " ok " if ok else "FAIL"
        print(f"  [{mark}] {label}: {got} (want {want})")
    if bad:
        print("\nSELF-TEST FAILED: the check cannot detect the defect it exists for.")
        return 1
    print("\nself-test passed: a page built from a different version of the post")
    print("is detected, an unstamped page is not silently accepted, and a")
    print("one-character source change is enough to register.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("posts", nargs="*", help="substring of a post filename")
    ap.add_argument("--series", help="accepted and ignored; scope is every post")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    return self_test() if args.self_test else check(args.posts)


if __name__ == "__main__":
    sys.exit(main())
