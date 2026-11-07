#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Refuse a services page whose job-to-service mapping has gone stale.

    python scripts/check_services_jobs.py
    python scripts/check_services_jobs.py --canary   # prove it can fail

Why this exists
---------------
/intelligence/services/ maps twelve jobs onto the services that answer them.
That mapping is EDITORIAL -- the store tags service names, and nothing in
the data says S3 and Cloud Storage answer the same question. Editorial means
a human wrote it, which means it rots when the clouds rename things, and the
clouds rename things constantly.

The failure has no symptom, which is why it needs a check rather than
attention. A stale alias matches nothing, the cell renders 0.0%, and an
empty cell reads as "this cloud does not do that" -- a confident, wrong
claim about a vendor, sitting in a grid where every neighbouring number is
right.

This is not hypothetical and it is not a risk being guarded against in
advance. It had already happened twice before the page existed, in the
draft that proposed it:

  * Azure OpenAI read 0.0% of Microsoft's quarter. The service had been
    renamed to Azure AI Foundry, and the catalogue carried neither name.
  * Cloud IAM read 0 items, because Google's release notes say "Identity
    and Access Management" and the alias list only had the short form.

Both looked exactly like findings. Neither was.

What it asserts
---------------
For every alias in JOBS: at least one service tag in the store contains it.
Not that the service is busy -- a quiet quarter is a real answer and this
check must never punish one. Only that the NAME still resolves to something
the tagger produces. A name that matches nothing anywhere in the store's
whole history is a name nobody is ever going to see.

Aliases are checked against all of history rather than the page's 90-day
window, deliberately. A service that shipped nothing this quarter still has
a valid name; a service whose name is wrong never matched at all.
"""
import argparse
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

STORE = os.path.join(ROOT, "intelligence", "news.json")


def tags_by_cloud(items):
    out = {}
    for i in items:
        c = i.get("c")
        if not c:
            continue
        out.setdefault(c, set()).update(i.get("s") or [])
    return out


def unresolved(jobs, tags):
    """Return [(job, cloud, alias)] for aliases that match no live tag.

    Pure, and shared with the canary so the two cannot disagree.
    """
    bad = []
    for job, a, z, g in jobs:
        for cloud, aliases in (("aws", a), ("azure", z), ("gcp", g)):
            live = tags.get(cloud) or set()
            for alias in aliases:
                al = alias.lower()
                if not any(al in t.lower() for t in live):
                    bad.append((job, cloud, alias))
    return bad


def canary():
    """A rule that cannot fail is worse than no rule."""
    jobs = [("Imaginary", ["S3"], ["Azure Nonesuch"], ["Cloud Storage"])]
    tags = {"aws": {"S3", "S3 Tables"}, "azure": {"Azure Monitor"},
            "gcp": {"Cloud Storage"}}
    bad = unresolved(jobs, tags)
    problems = []
    if [b for b in bad if b[2] == "Azure Nonesuch"] == []:
        problems.append("canary: a dead alias was not reported")
    if [b for b in bad if b[2] in ("S3", "Cloud Storage")]:
        problems.append("canary: a live alias was reported as dead")
    # A substring match must count: 'S3' lives inside 'S3 Tables'.
    if unresolved([("x", ["S3 Vectors"], [], [])],
                  {"aws": {"S3 Vectors on Demand"}}):
        problems.append("canary: substring matching is not working")
    for p in problems:
        print("  %s" % p)
    print("  canary: %s" % ("FAILED" if problems else "the check can fail"))
    return 1 if problems else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--canary", action="store_true")
    args = ap.parse_args()
    if args.canary:
        return canary()

    rc = canary()
    if rc:
        return rc

    if not os.path.isfile(STORE):
        print("  no store at %s -- nothing to check"
              % os.path.relpath(STORE, ROOT))
        return 0

    import build_services_page as bsp

    items = json.load(io.open(STORE, encoding="utf-8")).get("items", [])
    tags = tags_by_cloud(items)
    bad = unresolved(bsp.JOBS, tags)

    print("  %d job(s), %d alias(es) checked against %d live service name(s)"
          % (len(bsp.JOBS),
             sum(len(a) + len(z) + len(g) for _, a, z, g in bsp.JOBS),
             sum(len(v) for v in tags.values())))

    if not bad:
        print("  every alias still resolves to a service the tagger "
              "produces.")
        return 0

    print()
    print("  %d ALIAS(ES) MATCH NOTHING IN THE STORE" % len(bad))
    for job, cloud, alias in bad:
        print("  - %-24s %-6s %r" % (job, cloud, alias))
    print()
    print("  An alias that matches nothing renders an empty cell, and an")
    print("  empty cell on that grid reads as 'this cloud does not do that'.")
    print("  Either the service was renamed, or the tagger stopped producing")
    print("  the name. Fix JOBS in scripts/build_services_page.py.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
