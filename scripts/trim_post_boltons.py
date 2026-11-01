#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Remove the bolt-ons the early posts share, and fix the first reference.

    python scripts/trim_post_boltons.py 4 6 8 --write

Four things recur in weeks 1-8 and in none of the migrated posts:

  sign-off callout   "Week 06 complete. ... Next up: Week 07's ..." A sign-off
                     and a forward reference, neither of which the standard's
                     Cleanup and Key Takeaways asks for. The forward reference
                     also ages badly.

  service-news       A "What's New (2025-2026)" callout listing vendor
                     announcements. Not part of any section the standard
                     defines, and it is the first thing to go stale.

  takeaway cards     3-5 takeaways rendered as a grid of <div class="card">
                     with an emoji <h4> each. The standard asks for 3-5
                     takeaways; an <ol> is the same content without bespoke
                     markup.

  first reference    The standard puts the full lab guide first, so a reader
                     who wants the repo does not have to hunt. check_lab_post_
                     shape fails the post otherwise.

Everything here is markup or redundancy. No measured value is touched, which
is why this can run across several posts at once.
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import aws_post_path as paths            # noqa: E402

GUIDE_DIRS = {
    1: "week-01-enterprise-ec2-provisioning",
    2: "week-02-aurora-self-service",
    3: "week-03-ssm-fleet-management",
    4: "week-04-glue-fleet-intelligence",
    5: "week-05-cost-anomaly-detection",
    6: "week-06-account-vending-machine",
    7: "week-07-identity-center-sso",
    8: "week-08-s3-intelligent-storage",
}
REPO = "https://github.com/katta698/AWS-Platform-Engineering-Lab/blob/main/"


def _balanced(text, start):
    d, i = 0, start
    while i < len(text):
        if text.startswith("<div", i):
            d += 1
            i += 4
        elif text.startswith("</div>", i):
            d -= 1
            i += 6
            if d == 0:
                return i
        else:
            i += 1
    return -1


def drop_callout_containing(text, needle):
    i = text.find(needle)
    if i < 0:
        return text, False
    s = text.rfind('<div class="callout', 0, i)
    if s < 0:
        return text, False
    e = _balanced(text, s)
    if e < 0:
        return text, False
    return text[:s] + text[e:], True


def cards_to_list(text, heading_pat):
    """Turn the card grid under a heading into an <ol>, keeping the words."""
    m = re.search(heading_pat, text)
    if not m:
        return text, 0
    j = text.find('<div class="grid-2">', m.end())
    if j < 0 or j - m.end() > 400:
        return text, 0
    e = _balanced(text, j)
    if e < 0:
        return text, 0
    block = text[j:e]
    items = []
    for cm in re.finditer(r"<h4>(.*?)</h4>\s*<p>(.*?)</p>", block, re.S):
        title = re.sub(r"<[^>]+>", "", cm.group(1))
        title = re.sub(r"&#\d+;|&[a-z]+;", "", title).strip()
        body = cm.group(2).strip()
        items.append("  <li><strong>%s.</strong> %s</li>" % (title, body))
    if not items:
        return text, 0
    return text[:j] + "<ol>\n" + "\n".join(items) + "\n</ol>" + text[e:], len(items)


def first_reference(text, week):
    d = GUIDE_DIRS.get(week)
    if not d:
        return text, False
    m = re.search(r"<h3>References</h3>\s*<ul>", text)
    if not m:
        return text, False
    after = text[m.end():m.end() + 400]
    if "lab guide" in after.lower() or "README" in after:
        return text, False
    li = ('\n  <li><a href="%s%s/README.md">Full lab guide on GitHub</a> '
          "&mdash; prerequisites, Terraform, commands, validation and "
          "cleanup.</li>" % (REPO, d))
    return text[:m.end()] + li + text[m.end():], True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("weeks", nargs="+", type=int)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    for wk in a.weeks:
        p = paths.for_week(wk)
        t = io.open(p, encoding="utf-8").read()
        did = []

        # Service-news callouts are titled inconsistently across the early
        # posts: "What's New (2025-2026)" in some, "<Service> Updates
        # (2025-2026)" in others. Both are the same bolt-on.
        for needle in ("What&rsquo;s New", "What's New", "What&#39;s New",
                       "Updates (2025", "Updates (2026"):
            t, ok = drop_callout_containing(t, needle)
            if ok:
                did.append("service-news callout")
                break

        for needle in ("complete.</strong>", "Week %02d complete" % wk):
            t, ok = drop_callout_containing(t, needle)
            if ok:
                did.append("sign-off callout")
                break

        t, n = cards_to_list(t, r"<h3>[^<]*Takeaways[^<]*</h3>")
        if n:
            did.append("%d takeaway cards -> list" % n)

        t, ok = first_reference(t, wk)
        if ok:
            did.append("lab guide first reference")

        if not did:
            print("  week %-2d nothing to do" % wk)
            continue
        if a.write:
            io.open(p, "w", encoding="utf-8", newline="\n").write(t)
        print("  week %-2d %s: %s"
              % (wk, "done" if a.write else "would do", "; ".join(did)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
