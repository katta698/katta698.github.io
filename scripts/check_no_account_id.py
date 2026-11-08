#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail if a post leaks the AWS account id or a personal email address.

    python scripts/check_no_account_id.py
    python scripts/check_no_account_id.py --self-test

WHY THIS EXISTS (2026-11-01)
----------------------------
A standing instruction on this lab is that the AWS account id never appears in
a README or any committed file. It was nonetheless live on the site in two
published posts -- week 4, inside an S3 prefix example
(accountid=<redacted>/region=us-east-1/), and the EBS dashboard post, inside an
`aws s3 sync` command naming a bucket whose name ends in the account id. Both
had been through every other check in this repo without a word, because no
check looked.

It was found by eye, while reading a code block for an unrelated reason. That
is not a repeatable way to find the next one.

WHAT IT LOOKS FOR
  * any 12-digit run, which is the shape of an AWS account id, including when
    embedded in a bucket name or an ARN
  * the owner's personal email address

A 12-digit number that is genuinely not an account id (a byte count, say)
should be written with separators, which is better for the reader anyway.
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Twelve consecutive digits that are not part of a longer hex token. The
# digit-only lookaround was not enough: a sha256 in a build comment contains
# runs of twelve digits surrounded by hex letters, and every built page carries
# one, so the first run of this check reported twenty-odd leaks that were all
# the same false positive.
ACCOUNT_RE = re.compile(r"(?<![0-9A-Fa-f])\d{12}(?![0-9A-Fa-f])")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@gmail\.com", re.I)

# Documentation placeholders AWS itself uses in examples.
ALLOWED = {
    "111122223333", "123456789012", "000000000000",
    # Invented ids in the interactive IAM simulator, whose whole point is that
    # the reader compares two account numbers. Their repeated-digit shape makes
    # them obviously not real.
    "999988887777", "111100001111",
    # AWS's other documentation account, used in the architecture notes.
    "222233334444",
    # An Azure billing-profile id, which is not an AWS account at all.
    "100000000006",
    # From AWS's AppRegistry documentation, quoted verbatim in the
    # architecture notes as the shape of the awsApplication tag value:
    #   arn:aws:resource-groups:us-east-1:234567891011:group/myExampleApp/...
    # Sequential digits, and the claim citing it names the AWS page it came
    # from.
    "234567891011",
}


def _looks_like_timestamp(s):
    """YYYYMMDDHHMM, which is twelve digits and not an account id.

    daily-051 carries 202610081601 in an export filename. Reporting that as a
    leaked account id would train the reader of this check to ignore it.
    """
    y, mo, d, h, mi = (int(s[0:4]), int(s[4:6]), int(s[6:8]),
                       int(s[8:10]), int(s[10:12]))
    return 2000 <= y <= 2099 and 1 <= mo <= 12 and 1 <= d <= 31         and h <= 23 and mi <= 59

SEARCH_DIRS = ("posts", "blog", "_assets")
SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".woff",
            ".woff2", ".ttf", ".zip", ".pdf", ".mp3", ".mp4"}


# The site footer publishes a contact address on purpose: it is the "get in
# touch" link every page carries, and it is already public by design. That is a
# different thing from an address pasted into a copyable terraform command,
# which is what this check exists to catch. Narrow, and named, so the exception
# cannot quietly widen.
INTENTIONAL_CONTACT = "var CONTACT = "


def findings_in(text, allow_site_contact=False):
    out = []
    for m in ACCOUNT_RE.finditer(text):
        if m.group(0) in ALLOWED or _looks_like_timestamp(m.group(0)):
            continue
        out.append(("account id", m.group(0), m.start()))
    for m in EMAIL_RE.finditer(text):
        before = text[max(0, m.start() - 40):m.start()]
        if allow_site_contact and INTENTIONAL_CONTACT in before:
            continue
        out.append(("personal email", m.group(0), m.start()))
    return out


def self_test() -> int:
    cases = [
        ("a bare account id", "arn:aws:iam::684346483786:role/x", 1),
        ("inside a bucket name", "s3://ebsp1-frontend-684346483786/", 1),
        ("in an S3 prefix", "accountid=684346483786/region=us-east-1/", 1),
        ("AWS's own placeholder", "arn:aws:iam::111122223333:role/x", 0),
        ("a personal email", "write to someone@gmail.com please", 1),
        ("the footer's deliberate contact constant",
         "var CONTACT = 'someone@gmail.com';", 0),
        ("a long digit run that is not an id", "1234567890123456", 0),
        ("clean text", "the fleet had 1,200 instances", 0),
        ("a timestamp, not an id", "findings-202610081601.json", 0),
        ("an id that only looks like a date", "arn:aws:iam::209912319999:root", 1),
    ]
    bad = 0
    for label, text, want in cases:
        got = len(findings_in(text, allow_site_contact=True))
        ok = got == want
        bad += not ok
        print("  [%s] %s -> %d, want %d"
              % (" ok " if ok else "FAIL", label, got, want))
    if bad:
        print("\nSELF-TEST FAILED")
        return 1
    print("\nself-test passed: bare ids, ids inside names and prefixes, and a "
          "personal address are all detected; AWS's documentation placeholders "
          "are not.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()

    hits = 0
    scanned = 0
    for d in SEARCH_DIRS:
        base = os.path.join(ROOT, d)
        if not os.path.isdir(base):
            continue
        for root, _dirs, files in os.walk(base):
            for fn in files:
                if os.path.splitext(fn)[1].lower() in SKIP_EXT:
                    continue
                p = os.path.join(root, fn)
                try:
                    text = io.open(p, encoding="utf-8", errors="ignore").read()
                except OSError:
                    continue
                scanned += 1
                allow = rel_is_footer = fn == "site-footer.js"
                for kind, value, pos in findings_in(text, allow_site_contact=allow):
                    hits += 1
                    rel = os.path.relpath(p, ROOT).replace("\\", "/")
                    ctx = re.sub(r"\s+", " ", text[max(0, pos - 60):pos + 40])
                    print("  [LEAK] %s: %s %r" % (rel, kind, value))
                    print("         ...%s..." % ctx.strip()[:110])

    print("\n%d file(s) scanned, %d leak(s)." % (scanned, hits))
    if hits:
        print("An account id or personal address must not appear in anything "
              "published. Replace it with a placeholder.")
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
