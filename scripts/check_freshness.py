#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Report which published posts have gone stale, across every series.

    python scripts/check_freshness.py                 # full report
    python scripts/check_freshness.py --stale-batch 5 # smaller re-check queue
    python scripts/check_freshness.py --no-network    # staleness only, no fetches

`validate_arch_post.py` answers "is this post correct today, at the moment I am
publishing it". That is a different question from "is post #7 still correct
eighteen months later", and nothing answered the second one:

  * `STALE_DAYS = 180` warns when a badge is old -- but only when somebody runs
    the validator, and nobody runs it against posts published last year.
  * `--check-links` proves a cited URL *resolves*. A vendor can change a price
    and leave that URL answering 200 forever, so the post is then wrong beneath
    a badge saying it was checked.
  * A vendor moving its docs to a new host 301s the old URL, which satisfies a
    link check silently while every post keeps citing a redirect.

This script is meant to run on a schedule, unattended, for years.

## Why the report is capped rather than complete

The obvious design -- list every post older than 180 days -- works for one year
and fails afterwards. At a post a day, year two has ~500 posts and nearly all of
them are past the threshold, so the report flags almost everything, and a report
that always says "400 problems" is one nobody opens.

So findings are bucketed by whether they are *actionable now*:

  BROKEN  a cited page is gone, or cites a host outside the series allowlist.
          Always listed in full. These are real defects and they are rare.
  MOVED   a cited URL redirects elsewhere. Always listed in full; cheap to fix
          and it is how a vendor's doc migration gets noticed.
  STALE   the badge is simply old. Listed **oldest first, capped at N** -- a
          rolling worklist of constant size.

The cap is the point. Ten re-checks a week is about 500 posts a year, so the
whole archive rotates through roughly annually regardless of how large it grows,
and the weekly report stays the same size whether the site has 100 posts or
5,000.
"""
import argparse
import concurrent.futures
import datetime
import glob
import io
import os
import re
import sys
import urllib.error
import urllib.request

import yaml

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

# Reuse the series definitions rather than restating them -- the doc-host
# allowlist and the shell-host quirk are decided in one place, and a new series
# added there is picked up here with no edit.
from validate_arch_post import SERIES, STALE_DAYS, DOCS_SHELL_BYTES  # noqa: E402

UA = "katta698-freshness-check/1.0 (+https://jayanthkatta.com)"
TIMEOUT = 20
WORKERS = 6


def posts_with_badges():
    """Every post carrying a verification badge, with its series spec."""
    out = []
    for key, spec in SERIES.items():
        for path in sorted(glob.glob(os.path.join(
                ROOT, "posts", spec["file_prefix"] + "*.html"))):
            raw = io.open(path, encoding="utf-8").read()
            if not raw.startswith("---"):
                continue
            try:
                _, fm_text, _ = raw.split("---", 2)
                fm = yaml.safe_load(fm_text) or {}
            except Exception:
                continue
            if not fm.get("verified"):
                continue
            out.append({
                "name": os.path.basename(path),
                "series": key,
                "vendor": spec.get("vendor", key),
                "doc_hosts": spec["doc_hosts"],
                "shell_hosts": spec.get("shell_hosts", ()),
                "verified": fm["verified"],
                "claims": fm.get("verified_claims") or [],
            })
    return out


def fetch(url):
    """GET a URL, reporting status, final location and body size.

    Redirects are followed (urllib does that by default) but the final URL is
    compared against the requested one, because a silent 301 is exactly the
    signal this script exists to surface.
    """
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read(200000)
            return {"status": resp.status, "final": resp.geturl(),
                    "bytes": len(body), "error": None}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "final": url, "bytes": 0, "error": None}
    except Exception as e:                       # DNS, TLS, timeout, reset
        return {"status": None, "final": url, "bytes": 0, "error": str(e)[:120]}


def host_of(url):
    m = re.match(r"https?://([^/]+)", url or "")
    return m.group(1).lower() if m else ""


def same_page(a, b):
    """Ignore trailing slashes, query strings and fragments when comparing."""
    strip = lambda u: re.sub(r"[?#].*$", "", (u or "")).rstrip("/")
    return strip(a) == strip(b)


def audit(check_network=True):
    posts = posts_with_badges()
    today = datetime.date.today()
    broken, moved, stale = [], [], []

    jobs = []
    for p in posts:
        v = p["verified"]
        vdate = (v if isinstance(v, datetime.date)
                 else datetime.datetime.strptime(str(v).strip(), "%Y-%m-%d").date())
        p["age"] = (today - vdate).days
        p["vdate"] = vdate
        if p["age"] > STALE_DAYS:
            stale.append(p)
        for c in p["claims"]:
            if isinstance(c, dict) and c.get("source"):
                jobs.append((p, c["source"]))

    if check_network and jobs:
        with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
            results = list(ex.map(lambda j: fetch(j[1]), jobs))
    else:
        results = [None] * len(jobs)

    for (p, url), r in zip(jobs, results):
        host = host_of(url)
        allowed = any(host == h or host.endswith("." + h) for h in p["doc_hosts"])
        if not allowed:
            broken.append((p["name"], url, "host %s is outside the %s allowlist"
                           % (host, p["vendor"])))
            continue
        if r is None:
            continue
        if r["error"]:
            broken.append((p["name"], url, "unreachable: %s" % r["error"]))
        elif r["status"] and r["status"] >= 400:
            broken.append((p["name"], url, "HTTP %d" % r["status"]))
        elif host in p["shell_hosts"] and r["bytes"] < DOCS_SHELL_BYTES:
            # This host answers 200 for pages that do not exist, returning a
            # small shell. Body size is the only usable signal.
            broken.append((p["name"], url,
                           "HTTP 200 but only %d bytes -- %s answers 200 for "
                           "missing pages, so this is a dead link"
                           % (r["bytes"], host)))
        elif not same_page(url, r["final"]):
            moved.append((p["name"], url, r["final"]))

    stale.sort(key=lambda p: p["age"], reverse=True)
    return posts, broken, moved, stale


def report(posts, broken, moved, stale, batch):
    L = []
    add = L.append
    add("# Documentation freshness report")
    add("")
    add("Generated %s. %d badged post(s) across %d series."
        % (datetime.date.today(), len(posts), len(SERIES)))
    add("")
    add("| | Count |")
    add("| --- | --- |")
    add("| Broken citations | %d |" % len(broken))
    add("| Moved (redirecting) | %d |" % len(moved))
    add("| Badges older than %d days | %d |" % (STALE_DAYS, len(stale)))
    add("")

    if broken:
        add("## Broken — fix these")
        add("")
        add("A cited page no longer resolves, or is not the vendor's own "
            "documentation. The post asserts a figure a reader can no longer check.")
        add("")
        for name, url, why in broken:
            add("- **%s** — %s" % (name, why))
            add("  - %s" % url)
        add("")

    if moved:
        add("## Moved — the cited URL redirects")
        add("")
        add("Still reachable, so nothing is broken for a reader today. But a "
            "vendor migrating its docs shows up here first, and citing a "
            "redirect is how a post quietly ends up pointing at the wrong page.")
        add("")
        for name, url, final in moved:
            add("- **%s**" % name)
            add("  - cited: %s" % url)
            add("  - lands: %s" % final)
        add("")

    if stale:
        shown = stale[:batch]
        add("## Stale — this week's re-check queue")
        add("")
        add("%d post(s) are past %d days. The **%d oldest** are listed; the rest "
            "appear in later runs. Re-checking this batch weekly rotates the "
            "whole archive roughly annually, and keeps this report the same "
            "size however large the site gets."
            % (len(stale), STALE_DAYS, len(shown)))
        add("")
        add("| Post | Verified | Days |")
        add("| --- | --- | ---: |")
        for p in shown:
            add("| %s | %s | %d |" % (p["name"], p["vdate"], p["age"]))
        add("")
        add("To clear one: re-fetch its cited pages, confirm every figure the "
            "post prints still matches, update `verified:` to today, and fix "
            "any figure that moved. Do not just bump the date — that is the "
            "auto-stamping the badge rules forbid.")
        add("")

    if not broken and not moved and not stale:
        add("Nothing to do. Every badged post cites live vendor pages and no "
            "badge is older than %d days." % STALE_DAYS)
        add("")

    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stale-batch", type=int, default=10,
                    help="how many stale posts to surface per run (default 10)")
    ap.add_argument("--no-network", action="store_true",
                    help="skip fetching; report staleness only")
    ap.add_argument("--out", help="also write the report to this file")
    ap.add_argument("--fail-on-broken", action="store_true",
                    help="exit non-zero when a citation is broken")
    args = ap.parse_args()

    posts, broken, moved, stale = audit(check_network=not args.no_network)
    text = report(posts, broken, moved, stale, args.stale_batch)
    print(text)
    if args.out:
        io.open(args.out, "w", encoding="utf-8", newline="\n").write(text)

    # Staleness is expected and must never fail a run -- it is a worklist, not a
    # defect. A dead citation is a defect.
    if args.fail_on_broken and broken:
        sys.exit(1)


if __name__ == "__main__":
    main()
