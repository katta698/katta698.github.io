#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The incident feeds must be valid, honest, and quiet.

    python scripts/check_status_feed.py

Three things, in order of how badly they would fail:

QUIET.  The feed is rebuilt every hour by the status job. If any timestamp
        moves on a rebuild where nothing actually happened, every subscriber
        is re-notified about incidents they already know, every hour, forever.
        That is not a noisy feature, it is the reason someone unsubscribes and
        never comes back -- and it would look completely fine from here,
        because the page and the file are both correct. So this builds the feed
        twice and requires the bytes to be identical.

HONEST. Every incident open in status.json must be in the feed and marked
        open. A status page that says "2 open right now" while its feed says
        nothing is wrong is worse than having no feed.

VALID.  It parses, every entry has a stable id and an RFC3339 date, and no id
        appears twice -- a duplicate id makes a reader show one incident twice
        or hide one entirely, depending on whose reader it is.
"""
import io
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "intelligence", "status")
NS = {"a": "http://www.w3.org/2005/Atom"}
FEEDS = ["feed.xml", "feed-aws.xml", "feed-azure.xml", "feed-gcp.xml"]
RFC3339 = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
NAMES = {"aws": "AWS", "azure": "Azure", "gcp": "Google Cloud"}


def main():
    problems = []

    for name in FEEDS:
        path = os.path.join(DIR, name)
        if not os.path.exists(path):
            problems.append("%s has not been built" % name)
            print("  %-16s MISSING" % name)
            continue
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as exc:
            problems.append("%s is not valid XML: %s" % (name, str(exc)[:60]))
            print("  %-16s INVALID XML" % name)
            continue

        entries = root.findall("a:entry", NS)
        ids, bad_dates = set(), 0
        for e in entries:
            eid = (e.findtext("a:id", "", NS) or "").strip()
            when = (e.findtext("a:updated", "", NS) or "").strip()
            if not eid:
                problems.append("%s: an entry has no id" % name)
            elif eid in ids:
                problems.append("%s: two entries share the id %s" % (name, eid[:60]))
            ids.add(eid)
            if not RFC3339.match(when):
                bad_dates += 1
            if not (e.findtext("a:title", "", NS) or "").strip():
                problems.append("%s: an entry has no title" % name)
        if bad_dates:
            problems.append("%s: %d entr(y/ies) carry a date a reader cannot "
                            "parse" % (name, bad_dates))

        fu = (root.findtext("a:updated", "", NS) or "").strip()
        newest = max([(e.findtext("a:updated", "", NS) or "") for e in entries],
                     default="")
        if entries and fu != newest:
            problems.append("%s: the feed's own date (%s) is not its newest "
                            "entry (%s) — it is probably stamped with the "
                            "build time" % (name, fu, newest))

        # A self link, or a reader cannot tell where it came from.
        if not any(l.get("rel") == "self"
                   for l in root.findall("a:link", NS)):
            problems.append("%s: no rel=self link" % name)

        print("  %-16s %2d entries, %d unique ids, feed date %s"
              % (name, len(entries), len(ids), fu or "(none)"))

    # HONEST: everything open must be in the all-clouds feed, marked open.
    try:
        status = json.load(io.open(os.path.join(ROOT, "intelligence",
                                                "status.json"), encoding="utf-8"))
    except Exception:                                           # noqa: BLE001
        status = {}
    open_now = []
    for cloud, rows in (status.get("clouds") or {}).items():
        for i in rows or []:
            open_now.append((cloud, i.get("id") or (i.get("title") or "")[:80]))

    if os.path.exists(os.path.join(DIR, "feed.xml")):
        root = ET.parse(os.path.join(DIR, "feed.xml")).getroot()
        listed = {}
        for e in root.findall("a:entry", NS):
            eid = e.findtext("a:id", "", NS) or ""
            cats = [c.get("term") for c in e.findall("a:category", NS)]
            listed[eid] = "open" in cats
        for cloud, ident in open_now:
            key = "tag:jayanthkatta.com,2026:incident:%s:%s" % (cloud, ident)
            if key not in listed:
                problems.append("%s incident %s is open on the page and absent "
                                "from the feed" % (NAMES.get(cloud, cloud),
                                                   str(ident)[:40]))
            elif not listed[key]:
                problems.append("%s incident %s is open but the feed does not "
                                "say so" % (NAMES.get(cloud, cloud),
                                            str(ident)[:40]))
        print("  %d incident(s) open on the page, all present and marked"
              % len(open_now) if not problems else
              "  %d incident(s) open on the page" % len(open_now))

    # QUIET: rebuilding with nothing changed must not change a single byte.
    before = {n: io.open(os.path.join(DIR, n), "rb").read()
              for n in FEEDS if os.path.exists(os.path.join(DIR, n))}
    subprocess.run([sys.executable,
                    os.path.join(ROOT, "scripts", "build_status_feed.py")],
                   capture_output=True, cwd=ROOT, timeout=120)
    churned = [n for n, b in before.items()
               if io.open(os.path.join(DIR, n), "rb").read() != b]
    if churned:
        problems.append("rebuilding changed %s with nothing new to report — "
                        "every subscriber would be alerted again"
                        % ", ".join(churned))
        print("  rebuild: CHANGED %s" % ", ".join(churned))
    else:
        print("  rebuild with nothing new: byte-identical, so no subscriber "
              "is woken twice")

    print()
    if problems:
        print("  %d PROBLEM(S) WITH THE FEEDS\n" % len(problems))
        for p in problems[:20]:
            print("  - %s" % p)
        return 1
    print("  the feeds are valid, agree with the page, and stay quiet when")
    print("  nothing has happened.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
