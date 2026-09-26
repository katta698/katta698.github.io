#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail when a post going live for the first time carries a stale date.

    python scripts/check_publish_date.py
    python scripts/check_publish_date.py --self-test

Why this exists (2026-09-26)
----------------------------
Week 20 was written on 24 September, reviewed for two days, and published on
the 26th. It went live reading "Sep 24, 2026". Jay caught it on the site.

Weeks 18 and 19 were written and published on the same day, so their dates were
right by accident, and nothing here was ever exercised. The moment a review
separated writing from publishing, the date was simply the day the file was
authored -- which is not a fact anybody reading the blog cares about.

So the rule is about first publication only:

    A post whose built page is NOT yet in HEAD is going live for the first
    time. Its front-matter date must be today.

Re-publishing an existing post does not re-date it, because editing a post
later does not change when it was published. Drafts are exempt: a draft's date
is a plan, and it gets checked on the run that actually publishes it.
"""
import datetime as dt
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATE_RE = re.compile(r"^date:\s*'?([0-9]{4}-[0-9]{2}-[0-9]{2})", re.M)
SLUG_RE = re.compile(r"^slug:\s*([A-Za-z0-9._-]+)", re.M)
DRAFT_RE = re.compile(r"^draft:\s*true\s*$", re.M | re.I)


def verdict(front_matter, built_page_in_head, today):
    """Reason the post's date is wrong, or None.

    Pure, so --self-test can exercise it without a repo. The three inputs are
    the only things the rule depends on.
    """
    if DRAFT_RE.search(front_matter):
        return None                      # a draft's date is a plan, not a claim
    if built_page_in_head:
        return None                      # already published; editing is not re-dating
    m = DATE_RE.search(front_matter)
    if not m:
        return "no date in front matter"
    if m.group(1) != today:
        return ("going live today (%s) but dated %s -- a first publish must carry "
                "the date it actually publishes" % (today, m.group(1)))
    return None


def in_head(path):
    try:
        out = subprocess.run(["git", "cat-file", "-e", "HEAD:" + path],
                             cwd=ROOT, capture_output=True, timeout=30)
        return out.returncode == 0
    except Exception:                                           # noqa: BLE001
        return True      # cannot tell -> assume published, never block a rebuild


def self_test():
    TODAY = "2026-09-26"
    cases = [
        ("stale date on a first publish is caught",
         verdict("slug: x\ndate: '2026-09-24T18:00:00'\n", False, TODAY) is not None),
        ("the real Week 20 case",
         verdict("date: '2026-09-24T18:00:00'\nslug: week-20\n", False, TODAY) is not None),
        ("a missing date is caught",
         verdict("slug: x\ntitle: y\n", False, TODAY) is not None),
        ("today's date on a first publish passes",
         verdict("date: '2026-09-26T14:00:00'\n", False, TODAY) is None),
        ("a draft is exempt",
         verdict("date: '2026-09-24T18:00:00'\ndraft: true\n", False, TODAY) is None),
        ("an already-published post is not re-dated",
         verdict("date: '2026-01-05T10:00:00'\n", True, TODAY) is None),
    ]
    bad = 0
    for label, ok in cases:
        print("  [%s] %s" % ("PASS" if ok else "DEAD", label))
        bad += not ok
    print()
    if bad:
        print("%d case(s) DO NOT WORK." % bad)
        return 1
    print("All %d publish-date cases pass." % len(cases))
    return 0


def main():
    if "--self-test" in sys.argv:
        return self_test()
    if self_test_quiet():
        print("ABORTING: this check does not work. Run --self-test.")
        return 2

    posts = os.path.join(ROOT, "posts")
    today = dt.date.today().isoformat()
    problems, checked, unknown = [], 0, []

    for name in sorted(os.listdir(posts)):
        if not name.endswith(".html"):
            continue
        src = os.path.join(posts, name)
        try:
            # Read the WHOLE file. A 4000-char window missed the slug line in
            # nine posts, so the slug fell back to the filename, the built page
            # for that made-up slug was absent from HEAD, and every one of them
            # was reported as an unpublished post with a stale date. A guess
            # inside a checker produces findings that look exactly like real
            # ones, which is worse than not checking.
            head = open(src, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        m = SLUG_RE.search(head)
        if not m:
            unknown.append(name)
            continue
        slug = m.group(1)
        checked += 1
        why = verdict(head, in_head("blog/%s/index.html" % slug), today)
        if why:
            problems.append((name, why))

    print("  %d post(s) checked" % checked)
    if unknown:
        # Never silently skip. A post with no slug cannot be located, so the
        # rule did not run on it, and saying so is the honest outcome.
        print("  %d post(s) have NO slug -- not checked:" % len(unknown))
        for n in unknown[:5]:
            print("        %s" % n)
    if problems:
        print("  %d WRONGLY DATED" % len(problems))
        for n, why in problems:
            print("        %-52s %s" % (n, why))
        print()
        print("  A reader takes the date at face value. Publishing on one day")
        print("  under another day's date is simply false, and it is the kind")
        print("  of wrong nothing downstream can detect.")
        return 1
    print("  every post going live today is dated today.")
    return 0


def self_test_quiet():
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        return self_test()


if __name__ == "__main__":
    sys.exit(main())
