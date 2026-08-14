#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Report which figures in each post are backed by a sourced claim.

    python scripts/audit_claims.py                 # every arch post
    python scripts/audit_claims.py arch-018        # one post

validate_arch_post.py answers "does this post cite AWS for at least two
claims". That is a check on sourcing, not on correctness, and the difference
is not academic: arch-018 cited two real AWS pricing pages and still stated a
wrong break-even, because the error was in the arithmetic done on top of the
sources rather than in the sources.

This script answers a different question: of the figures actually printed in
the post, how many appear in a verified_claim? A number in the body that
appears nowhere in the claim list is a number nobody checked -- which is fine
for an illustrative example and not fine for a price, a limit or a threshold.

It reports rather than fails. Judgement about which numbers matter belongs to
a person; the point is to make the unchecked ones visible instead of letting
them blend in with the checked ones.
"""
import glob
import io
import os
import re
import sys

import yaml

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Figures worth tracing: money, percentages, multipliers, sizes, durations and
# bare counts of four digits or more. Deliberately not every integer -- "the
# two controls" and "wave 1" are prose, not claims.
NUMBER_RE = re.compile(r"""
    \$\s?\d[\d,]*(?:\.\d+)?             # $0.625  $1,234
  | \d[\d,]*(?:\.\d+)?\s?%              # 29%  5.5 %
  | \d[\d,]*(?:\.\d+)?\s?(?:x|×)\b      # 3.5x  6.9×
  | \d[\d,]*(?:\.\d+)?\s?(?:GB|TB|MB|KB|GiB|TiB)\b
  | \d[\d,]*(?:\.\d+)?\s?(?:ms|hours?|days?|weeks?|months?|years?|minutes?)\b
  | \b\d{4,}\b                          # 1,000 / 8760 style counts
""", re.X | re.I)

# Phrases that signal a number was computed rather than quoted. These are the
# ones that have actually been wrong here.
DERIVED_RE = re.compile(
    r"break[- ]even|cheaper|more expensive|ratio|times (?:more|less|cheaper)"
    r"|halv|double|per cent of|% of|works out|comes to|effective rate",
    re.I)


def normalise(s):
    return re.sub(r"[\s,]", "", str(s)).lower().rstrip(".")


def audit(path):
    raw = io.open(path, encoding="utf-8").read()
    if not raw.startswith("---"):
        return None
    _, fm_text, body = raw.split("---", 2)
    fm = yaml.safe_load(fm_text) or {}

    text = re.sub(r"<[^>]+>", " ", body)
    text = re.sub(r"&#\d+;|&[a-z]+;", " ", text)

    claims = fm.get("verified_claims") or []
    claim_text = " ".join(str(c.get("claim", "")) for c in claims if isinstance(c, dict))
    claim_nums = {normalise(n) for n in NUMBER_RE.findall(claim_text)}

    body_nums = [n for n in NUMBER_RE.findall(text)]
    uniq = []
    seen = set()
    for n in body_nums:
        k = normalise(n)
        if k not in seen:
            seen.add(k)
            uniq.append(n.strip())

    covered = [n for n in uniq if normalise(n) in claim_nums]
    uncovered = [n for n in uniq if normalise(n) not in claim_nums]
    derived = len(DERIVED_RE.findall(text))

    return {
        "post": os.path.basename(path),
        "badged": bool(fm.get("verified")),
        "claims": len(claims),
        "figures": len(uniq),
        "covered": len(covered),
        "uncovered": uncovered,
        "derived_phrases": derived,
    }


def main():
    args = [a for a in sys.argv[1:]]
    files = sorted(glob.glob(os.path.join(ROOT, "posts", "arch-*.html")))
    if args:
        files = [f for f in files if any(a in os.path.basename(f) for a in args)]

    rows = [r for r in (audit(f) for f in files) if r]
    print("%-46s %-6s %-7s %-9s %s" % ("post", "badge", "claims", "figures", "traced"))
    print("-" * 92)
    for r in rows:
        pct = (100 * r["covered"] // r["figures"]) if r["figures"] else 0
        print("%-46s %-6s %-7d %-9d %d%%"
              % (r["post"][:46], "yes" if r["badged"] else "no",
                 r["claims"], r["figures"], pct))

    print()
    print("Figures printed in badged posts that appear in no verified_claim:")
    any_gap = False
    for r in rows:
        if r["badged"] and r["uncovered"]:
            any_gap = True
            print("  %s (%d derived-phrase mentions)" % (r["post"], r["derived_phrases"]))
            print("      " + ", ".join(r["uncovered"][:14]))
    if not any_gap:
        print("  none")

    unbadged = [r for r in rows if not r["badged"] and r["figures"]]
    if unbadged:
        print()
        print("Unbadged posts that still print figures (asserted, never checked):")
        for r in unbadged:
            print("  %-44s %d figures, %d derived-phrase mentions"
                  % (r["post"], r["figures"], r["derived_phrases"]))


if __name__ == "__main__":
    main()
