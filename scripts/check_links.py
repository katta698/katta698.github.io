#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check that links on the generated pages are well-formed, and optionally live.

    python scripts/check_links.py           # structural only, offline, fast
    python scripts/check_links.py --live    # also fetch each unique URL

Why this exists
---------------
Every Google incident link on the status page pointed at

    https://status.cloud.google.comincidents/J5ia5t9p3g9Q5Wi7r8Ev

because the URL was built with "+" and Google's uri field carries no leading
slash. Two correct halves, joined wrongly at the single character where they
meet. It read as correct in the code, in the JSON, and very nearly in the
rendered link -- and it was found by a person clicking a bar and landing
nowhere.

Nothing here had ever checked that a link resolves. Contrast, page structure,
region codes and labelling were all verified; whether the hyperlinks actually
went anywhere was assumed, so the whole category was untested.

Two tiers, on purpose
---------------------
Structural checks run offline and always, because a malformed host is a bug in
this repo and never a network problem. The live fetch is opt-in: a vendor's
status site being slow is not a reason to fail a publish, so it must not be
able to block one by default.
"""
import argparse
import io
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The last label of a host must be a real TLD. This is what catches
# ".comincidents": a missing slash swallows the path into the hostname, which
# leaves a label that no allowlist will ever contain.
TLDS = {
    "com", "org", "net", "io", "dev", "ai", "gov", "edu", "co", "uk", "in",
    "me", "app", "cloud", "microsoft", "amazon", "google", "sh", "xyz", "info",
}


def urls_in(path):
    """Anchors only.

    Matching every href swept in <link rel="preconnect" href="...">, whose
    value is an ORIGIN rather than a document -- a bare GET on it returns 404
    quite correctly, and reporting that as a dead link is the checker being
    wrong. One false alarm is all it takes for a check to start being ignored,
    which costs more than the check was ever worth.
    """
    h = io.open(path, encoding="utf-8", errors="replace").read()
    return re.findall('<a [^>]*?href="(https?://[^"]+)"', h, re.I)


def structural(u):
    """Return a complaint, or None when the URL is shaped correctly."""
    p = urllib.parse.urlparse(u)
    if not p.scheme or not p.netloc:
        return "no scheme or host"
    host = p.netloc.split(":")[0].lower()
    if ".." in host or host.startswith(".") or host.endswith("."):
        return "malformed host"
    last = host.rsplit(".", 1)[-1]
    if last not in TLDS:
        # Almost always a join bug: the path got absorbed into the hostname.
        return ("host ends in .%s, which is not a known TLD -- a missing "
                "slash in a URL join looks exactly like this" % last)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--page", action="append")
    args = ap.parse_args()

    pages = args.page or [
        "intelligence/status/index.html",
        "intelligence/whats-new/index.html",
        "intelligence/index.html",
    ]

    found, bad = {}, []
    for rel in pages:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            continue
        for u in urls_in(p):
            u = u.replace("&amp;", "&")
            found.setdefault(u, set()).add(rel)
            why = structural(u)
            if why:
                bad.append((u, rel, why))

    if bad:
        print("\n  MALFORMED LINKS\n")
        for u, rel, why in bad:
            print("  %s\n    in %s\n    %s" % (u, rel, why))
        print("\n  %d malformed link(s)." % len(bad))
        return 1

    # A check that examined nothing must not report success. This very file
    # printed "all well-formed" over ZERO links after a mangled regex matched
    # nothing -- the same vacuous pass the contrast checker once shipped.
    # Silence and correctness look identical unless one of them is made loud.
    if not found:
        print("  NO LINKS FOUND across %d page(s)." % len(pages))
        print("  The pages have links, so this means the extractor is broken,")
        print("  not that the pages are clean.")
        return 1

    print("  %d unique link(s) across %d page(s): all well-formed."
          % (len(found), len(pages)))

    if not args.live:
        return 0

    ctx = ssl.create_default_context()
    dead = []
    for u in sorted(found):
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
                code = r.status
        except urllib.error.HTTPError as ex:
            code = ex.code
        except Exception as ex:                                 # noqa: BLE001
            code = type(ex).__name__
        if code != 200:
            dead.append((u, code))
            print("   FAIL %-5s %s" % (code, u[:76]))
    if dead:
        print("\n  %d link(s) did not return 200." % len(dead))
        print("  A vendor being down is not a reason to block a publish;")
        print("  this mode is advisory unless you are checking a build.")
        return 1
    print("  all %d fetched successfully." % len(found))
    return 0


if __name__ == "__main__":
    sys.exit(main())
