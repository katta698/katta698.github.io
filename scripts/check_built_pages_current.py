#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A post's served page must be newer than the source it was built from.

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

What it asserts
---------------
For every post in `posts/`, DRAFTS INCLUDED:

1. a built page exists at `blog/<slug>/index.html`
2. that page is not older than its source

Age comes from git -- the timestamp of the last commit to touch each path --
plus the working tree, so a source edited and not yet synced fails before it is
ever committed. Both changed in one commit is the normal, passing case: that is
what a sync-then-commit produces.

What it deliberately does not do
--------------------------------
It does not compare CONTENT. The built page wraps the source in a template, so
"the edit is present in both" has no cheap exact form, and a hash embedded at
build time would require changing the generator to catch a mistake in using it.
Order of modification is enough: it is exactly the thing that was wrong.

It does not run the generator. A check that fixes the problem it finds teaches
you to ignore what it says, and syncing is not always the right answer -- a
stale page can also mean a bad rebase, which regenerating would paper over.
"""
import argparse
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
POSTS = os.path.join(ROOT, "posts")


def git(*args, strip=True):
    """Run a git command in the repo root; '' on any failure.

    strip=False matters for `status --porcelain`, whose format is
    `XY<space>path` -- the status of an unstaged edit is " M", so stripping
    the output eats the leading space of the FIRST line only and shifts that
    one path left by a character. The check then reports every file clean
    while silently looking for "osts/week-09-...". Found by reintroducing the
    bug this file exists to catch, which is the only reason it was found.
    """
    try:
        out = subprocess.run(
            ["git", "-C", ROOT, *args],
            capture_output=True, text=True, timeout=30,
        )
        if out.returncode != 0:
            return ""
        return out.stdout.strip() if strip else out.stdout
    except Exception:
        return ""


def last_commit_time(relpath):
    """Unix time of the last commit touching relpath; 0 if never committed."""
    ts = git("log", "-1", "--format=%ct", "--", relpath)
    return int(ts) if ts.isdigit() else 0


def dirty_paths():
    """Every path with uncommitted changes, as a set of repo-relative paths."""
    out = git("status", "--porcelain", strip=False)
    paths = set()
    for line in out.splitlines():
        if len(line) < 4:
            continue
        p = line[3:].strip().strip('"')
        if " -> " in p:            # a rename reports "old -> new"
            p = p.split(" -> ", 1)[1]
        if p:
            paths.add(p)
    return paths


def is_stale(src_time, built_time, src_dirty, built_dirty):
    """The whole decision, as a pure function so --self-test can prove it.

    An uncommitted source edit is the live case: it is newer than anything
    git knows about, so it is stale unless the built page is also uncommitted
    (that pair is a sync that has not been committed yet, which is fine).
    """
    if src_dirty and not built_dirty:
        return True
    if src_dirty and built_dirty:
        return False
    return src_time > built_time


def slug_of(path, text):
    m = re.search(r"^slug:\s*['\"]?([A-Za-z0-9._-]+)", text, re.M)
    if m:
        return m.group(1)
    return os.path.splitext(os.path.basename(path))[0]


def check(filters):
    dirty = dirty_paths()
    report, failures, checked = [], 0, 0

    for fn in sorted(os.listdir(POSTS)):
        if not fn.endswith(".html"):
            continue
        if filters and not any(a in fn for a in filters):
            continue
        src_rel = f"posts/{fn}"
        with open(os.path.join(POSTS, fn), encoding="utf-8") as fh:
            text = fh.read()
        slug = slug_of(fn, text)
        built_rel = f"blog/{slug}/index.html"
        checked += 1

        if not os.path.exists(os.path.join(ROOT, built_rel)):
            report.append(f"  [FAIL] {fn}: no built page at {built_rel} "
                          "-- run: python scripts/sync_blog.py")
            failures += 1
            continue

        if is_stale(last_commit_time(src_rel), last_commit_time(built_rel),
                    src_rel in dirty, built_rel in dirty):
            report.append(f"  [FAIL] {fn}: {built_rel} is older than its source. "
                          "The site will serve the previous version "
                          "-- run: python scripts/sync_blog.py")
            failures += 1
        else:
            report.append(f"  [ ok ] {fn}")

    print("\n".join(report))
    print(f"\n{checked} post(s) checked.")
    if failures:
        print(f"{failures} built page(s) are stale or missing.")
        print("A push that does not regenerate them changes nothing a reader sees.")
        return 1
    print("Every built page is at least as new as the post it was built from.")
    return 0


def self_test():
    cases = [
        # (src_time, built_time, src_dirty, built_dirty, expect_stale, label)
        (100, 200, False, False, False, "built after source"),
        (100, 100, False, False, False, "same commit (sync then commit)"),
        (200, 100, False, False, True,  "source committed after the build"),
        (100, 200, True,  False, True,  "source edited, not yet synced"),
        (100, 200, True,  True,  False, "both uncommitted (synced, not committed)"),
        (0,   0,   False, False, False, "neither committed"),
    ]
    bad = 0
    for src, built, sd, bd, want, label in cases:
        got = is_stale(src, built, sd, bd)
        ok = got == want
        bad += not ok
        print(f"  [{' ok ' if ok else 'FAIL'}] {label}: stale={got} (want {want})")
    if bad:
        print("\nSELF-TEST FAILED: the check cannot detect the defect it exists for.")
        return 1
    print("\nself-test passed: a source newer than its built page is detected,")
    print("including the uncommitted case, and a clean sync is not flagged.")
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
