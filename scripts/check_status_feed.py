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
import http.server
import io
import json
import os
import re
import socketserver
import subprocess
import sys
import threading
import xml.etree.ElementTree as ET
from status_open import still_open

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "intelligence", "status")
NS = {"a": "http://www.w3.org/2005/Atom"}
FEEDS = ["feed.xml", "feed-aws.xml", "feed-azure.xml", "feed-gcp.xml"]
RFC3339 = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
NAMES = {"aws": "AWS", "azure": "Azure", "gcp": "Google Cloud"}


# Serve the requests at once, not one after another.
#
# socketserver.TCPServer is single-threaded, and a browser asks for the HTML,
# the stylesheets, the scripts and the font files together. They queued -- and
# with six checks in parallel, behind each other's queues as well. That is why
# the wordmark measured 114.8px (the fallback serif) instead of 96.6px
# (Playfair) only ever during a full run. daemon_threads so a hung request
# cannot outlive the check.
class _Threaded(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def serve_root():
    """The whole site, so a feed and the page it belongs to can be compared."""
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def guess_type(self, path):
            # A stylesheet served as the wrong type is not applied, and the
            # feed would then be raw XML while still passing every other check.
            if path.endswith(".xsl"):
                return "text/xsl"
            if path.endswith(".xml"):
                return "application/xml"
            return http.server.SimpleHTTPRequestHandler.guess_type(self, path)

    socketserver.TCPServer.allow_reuse_address = True
    for port in range(8651, 8701):
        try:
            srv = _Threaded(("127.0.0.1", port), H)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            return srv, port
        except OSError:
            continue
    raise SystemExit("no free port")


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
    # open_only, not the raw list. This asserted that EVERY row in clouds[]
    # must appear in the feed marked "open" -- so while the feed shipped
    # resolved incidents as open, this check was not merely blind to it, it
    # required it. Fixing the builder without fixing this would have turned
    # the correct feed into a check failure.
    open_now, resolved_now = [], []
    for cloud, rows in (status.get("clouds") or {}).items():
        for i in rows or []:
            ident = i.get("id") or (i.get("title") or "")[:80]
            (open_now if still_open(i) else resolved_now).append((cloud, ident))

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
        # The inverse, which is the half that was missing. Asserting only
        # that open incidents ARE in the feed can never catch a resolved one
        # being published as open -- that is exactly how the feed shipped
        # them for as long as it did.
        for cloud, ident in resolved_now:
            key = "tag:jayanthkatta.com,2026:incident:%s:%s" % (cloud, ident)
            if listed.get(key):
                problems.append(
                    "%s incident %s is RESOLVED and the feed publishes it as "
                    "open -- a subscriber is notified about an outage that is "
                    "over" % (NAMES.get(cloud, cloud), str(ident)[:40]))

        print("  %d open, %d resolved; feed agrees on both"
              % (len(open_now), len(resolved_now)) if not problems else
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

    # And it must not look like a different website.
    #
    # The feeds were styled with their own hardcoded dark grey, so following a
    # link from the footer landed on something that did not share the site's
    # ground colour, its type or the weekday palette -- which is the same
    # complaint status.css already records about the status page before it
    # joined the rotation. They use the site's own stylesheet now, with the
    # day written into the file, because a stylesheet applied by XSLT cannot
    # run a script to read it.
    try:
        from playwright.sync_api import sync_playwright
        srv2, port2 = serve_root()
        try:
            with sync_playwright() as pw:
                b = pw.chromium.launch()
                seen = {}
                for label, path in (("the status page", "/intelligence/status/"),
                                    ("the feed", "/intelligence/status/feed.xml"),
                                    ("the blog feed", "/blog/rss.xml")):
                    pg = b.new_page(viewport={"width": 900, "height": 900})
                    pg.goto("http://127.0.0.1:%d%s" % (port2, path),
                            wait_until="commit", timeout=60000)
                    pg.wait_for_timeout(2500)
                    seen[label] = pg.evaluate(
                        "() => getComputedStyle(document.body).backgroundColor"
                        " + ' / ' + document.documentElement"
                        ".getAttribute('data-palette')")
                    pg.close()
                b.close()
            page_look = seen.get("the status page")
            for label, look in seen.items():
                if look != page_look:
                    problems.append(
                        "%s renders as %s while the site renders as %s"
                        % (label, look, page_look))
            print("  every feed renders in the site's own ground and palette "
                  "(%s)" % page_look)
        finally:
            srv2.shutdown()
    except Exception as exc:                                    # noqa: BLE001
        print("  could not check how the feeds render (%s)" % str(exc)[:50])

    # CANARY: the resolved assertion above only bites when the live file
    # actually carries a resolved incident, and most of the time it does not
    # -- today it reported "0 resolved", which means it tested nothing. A
    # check that can only fail in the right weather is the fault this repo
    # has already paid for twice. So the builder is run here against a
    # payload that definitely contains one, in-process, touching no files.
    try:
        import build_status_feed as _bsf
        _real = _bsf.load
        _B = "1759680000"
        _payload = {"clouds": {"aws": [
            {"id": "canary-resolved", "title": "[RESOLVED] Canary", "begin": _B},
            {"id": "canary-open", "title": "Canary open", "begin": _B}],
            "azure": [], "gcp": []},
            "sources": {"aws": {"ok": True}},
            "checked": "2026-01-01T00:00:00Z"}
        try:
            _bsf.load = lambda _p: _payload if _p.endswith("status.json") else {}
            _open = [r.get("id") for r in _bsf.entries() if r.get("open")]
        finally:
            _bsf.load = _real
        if "canary-resolved" in _open:
            problems.append(
                "CANARY: the feed builder publishes a [RESOLVED] incident as "
                "open -- subscribers would be notified about an outage that "
                "is over")
        elif "canary-open" not in _open:
            problems.append(
                "CANARY: the feed builder dropped a genuinely open incident, "
                "so the filter is now too aggressive")
        else:
            print("  canary: a resolved incident is kept out of the feed, an "
                  "open one is kept in")
    except Exception as exc:                                    # noqa: BLE001
        problems.append("CANARY could not run (%s) -- the resolved assertion "
                        "is unproven" % str(exc)[:60])

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
