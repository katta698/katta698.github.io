#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Refuse a /data/ page whose editorial mapping has rotted.

    python scripts/check_data_page.py

The six stages on /data/ map cloud service names onto a lifecycle. That
mapping is a judgement, and judgements written in a list rot silently: a
service gets renamed, its cell empties, and an empty cell on that page reads
as "this cloud does not do that". Nothing else on the site would notice.

WHAT THIS SEPARATES, BECAUSE THEY LOOK THE SAME AND ARE NOT
-----------------------------------------------------------
  DEAD      the name can never match: it is not in that cloud's service
            catalogue AND it has never appeared as a tag on any stored
            announcement. This fails the build.
  QUIET     the name resolves, but no announcement in the window carried it.
            That is a real measurement and is reported, not failed -- a quiet
            quarter is information.

Both halves of the "can it ever match" test are needed, and the catalogue
alone is not enough. news_tag.py's first tier is GCP-only and authoritative:
it tags from the release note's own product heading and never consults the
catalogue, so "Looker" and "Managed Service for Apache Spark" are real tags
that appear in no catalogue. Testing against the catalogue alone called 34
working names dead.

The distinction is the whole point. check_services_jobs.py, the equivalent
for /intelligence/services/, found five dead aliases the first time it ran.
"""
import datetime
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

DIAGRAM = os.path.join(ROOT, "blog", "assets", "diagrams", "data-lifecycle.svg")
PAGE = os.path.join(ROOT, "data", "index.html")


def catalogue(cloud):
    p = os.path.join(ROOT, "scripts", "%s_services.json" % cloud)
    with io.open(p, encoding="utf-8") as f:
        return set(json.load(f).get("services", {}))


def tagged(items, cloud, days=None):
    """Tags seen for a cloud -- in the window if days is given, else ever."""
    cut = None
    if days is not None:
        cut = (datetime.date.today()
               - datetime.timedelta(days=days)).isoformat()
    seen = set()
    for i in items:
        if i.get("c") != cloud:
            continue
        if cut and (i.get("d") or "") < cut:
            continue
        seen.update(i.get("s") or [])
    return seen


def audit(stages, items, window_days):
    """Returns (dead, quiet). Dead is fatal; quiet is reported."""
    dead, quiet = [], []
    for cloud in ("aws", "azure", "gcp"):
        resolvable = catalogue(cloud) | tagged(items, cloud)
        live = tagged(items, cloud, window_days)
        for key, title, _m, _w, svc in stages:
            for name in svc.get(cloud) or []:
                if name not in resolvable:
                    dead.append((title, cloud, name))
                elif name not in live:
                    quiet.append((title, cloud, name))
    return dead, quiet


def canary(stages, items, window_days):
    """A check that cannot fail is worse than no check.

    Injects a service name that is in no catalogue and asserts the audit
    reports it as dead rather than as quiet.
    """
    fake = ("ingest", "Ingest", "", "",
            {"aws": ["Amazon Definitely Not A Service"], "azure": [],
             "gcp": []})
    dead, _quiet = audit([fake], items, window_days)
    assert dead, "canary: a nonexistent service was not reported as dead"
    assert dead[0][2] == "Amazon Definitely Not A Service", dead


def main():
    import build_data_page as bdp

    news = bdp.load(bdp.NEWS, {"items": []})
    items = news.get("items", [])
    if not items:
        print("FAIL: intelligence/news.json holds no items")
        return 1

    canary(bdp.STAGES, items, bdp.WINDOW_DAYS)
    dead, quiet = audit(bdp.STAGES, items, bdp.WINDOW_DAYS)

    mapped = sum(len(v or []) for _k, _t, _m, _w, s in bdp.STAGES
                 for v in s.values())
    print("stage mapping: %d service names across %d stages, %d-day window"
          % (mapped, len(bdp.STAGES), bdp.WINDOW_DAYS))

    if quiet:
        print("\nQUIET -- in the catalogue, no announcement in the window "
              "(%d). This is a measurement, not a fault:" % len(quiet))
        for title, cloud, name in quiet[:40]:
            print("    %-10s %-6s %s" % (title, cloud, name))
        if len(quiet) > 40:
            print("    ... and %d more" % (len(quiet) - 40))

    problems = 0
    if dead:
        print("\nDEAD -- not in that cloud's service catalogue, so this cell "
              "can never fill (%d):" % len(dead))
        for title, cloud, name in dead:
            print("    %-10s %-6s %s" % (title, cloud, name))
        problems += len(dead)

    if not os.path.exists(DIAGRAM):
        print("\nFAIL: %s is missing and the page links it"
              % os.path.relpath(DIAGRAM, ROOT))
        problems += 1
    elif os.path.exists(PAGE):
        with io.open(PAGE, encoding="utf-8") as f:
            html = f.read()
        if "data-lifecycle.svg" not in html:
            print("\nFAIL: the page no longer references the diagram")
            problems += 1

    for path, what in ((bdp.RELEASES, "engine releases"),
                       (bdp.ECONOMICS, "vendor economics")):
        if not os.path.exists(path):
            print("\nFAIL: %s is missing (%s)"
                  % (os.path.relpath(path, ROOT), what))
            problems += 1
            continue
        doc = bdp.load(path, {})
        gen = (doc.get("generated") or "")[:10]
        if gen:
            age = (datetime.date.today()
                   - datetime.date.fromisoformat(gen)).days
            flag = "  <-- STALE" if age > 21 else ""
            print("%-22s generated %s (%d days ago)%s"
                  % (what, gen, age, flag))

    if problems:
        print("\n%d problem(s). The mapping or its inputs need fixing."
              % problems)
        return 1
    print("\nEverything the page claims it can measure, it can.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
