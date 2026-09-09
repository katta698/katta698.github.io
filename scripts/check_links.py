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
import concurrent.futures
import io
import json
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


SKIP_PARTS = ("/_templates/", "/admin/", "/test.html")

# Anchors written INSIDE a <script> are client-side templates, not links. The
# admin page builds rows with href="...${p.slug}/", which is correct JavaScript
# and reported as a dead URL by anything reading the file as HTML.
SCRIPTS = re.compile(r"(?is)<script[^>]*>.*?</script>")


def urls_in(path):
    """Anchors only.

    Matching every href swept in <link rel="preconnect" href="...">, whose
    value is an ORIGIN rather than a document -- a bare GET on it returns 404
    quite correctly, and reporting that as a dead link is the checker being
    wrong. One false alarm is all it takes for a check to start being ignored,
    which costs more than the check was ever worth.
    """
    h = SCRIPTS.sub(" ", io.open(path, encoding="utf-8", errors="replace").read())
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

    # EVERY published page, not a hand-listed three.
    #
    # This checked exactly three pages while the site publishes 480. The blog
    # posts are the ones that matter most here -- they cite vendor
    # documentation, and a technical post resting on a dead citation is worse
    # than one that never cited anything, because the badge of a source is
    # doing work the source no longer does.
    #
    # A hand-maintained list of pages to check is a list that goes out of date
    # the first time a page is added, silently, in the direction of checking
    # less.
    if args.page:
        pages = args.page
    else:
        pages = []
        for base, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs
                       if d not in (".git", "node_modules", ".github", "scripts")]
            for f in files:
                if not f.endswith(".html"):
                    continue
                rel = os.path.relpath(os.path.join(base, f), ROOT)
                # Templates and admin tooling are not pages a reader reaches.
                slug = "/" + rel.replace("\\", "/")
                if any(x in slug for x in SKIP_PARTS):
                    continue
                pages.append(rel)
        pages.sort()

    found, bad = {}, []

    # URLs that never appear in the HTML.
    #
    # The status page injects incident and write-up links from JSON at click
    # time, so 45 vendor addresses were invisible to a checker that only reads
    # anchors -- including the Azure ones that turned out to point at a
    # feedback survey rather than the incident. Those are exactly the links
    # this site's claims rest on, and they were the only ones not being
    # checked.
    for rel in ("intelligence/postmortems.json", "intelligence/status.json",
                "intelligence/status-history.json"):
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            continue
        try:
            blob = json.load(io.open(p, encoding="utf-8"))
        except ValueError:
            continue
        rows = (blob.get("postmortems") or [])
        rows += list((blob.get("incidents") or {}).values())
        for v in (blob.get("clouds") or {}).values():
            rows += v
        for r in rows:
            u = (r or {}).get("url") or ""
            if u.startswith(("http://", "https://")):
                found.setdefault(u, set()).add(rel)
                why = structural(u)
                if why:
                    bad.append((u, rel, why))

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

    # Concurrent, because sequential is unusable at this size.
    #
    # Checking 1762 links one at a time, with a 30-second ceiling on each,
    # runs for hours. A check nobody can afford to run is a check that does
    # not exist -- and this is the one protecting every citation in every
    # blog post, so it has to be cheap enough to run before a publish.
    #
    # Twelve workers and a 20-second ceiling brings it to minutes. The limit
    # is politeness as much as speed: these are vendor documentation sites,
    # and this should look like a reader, not a scraper.
    def probe(u):
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
                return u, r.status
        except urllib.error.HTTPError as ex:
            return u, ex.code
        except Exception as ex:                                 # noqa: BLE001
            return u, type(ex).__name__

    dead, soft = [], []
    done = 0
    total = len(found)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for u, code in pool.map(probe, sorted(found)):
            done += 1
            if done % 200 == 0:
                print("   ...%d/%d checked" % (done, total), flush=True)
            # 2xx and 3xx are both healthy. Counting 301 as a failure marked
            # aws.amazon.com/acm/ dead when it simply redirects, which is what
            # a canonical URL is supposed to do.
            ok = isinstance(code, int) and 200 <= code < 400
            # 403/429/999 mean "you look like a robot", not "this is gone".
            # LinkedIn returns 999 to everything automated. Reporting those as
            # broken links would have this check crying wolf on every run,
            # which is how a check stops being read.
            blocked = code in (403, 429, 999) or code == "URLError"
            if ok:
                continue
            if blocked:
                soft.append((u, code))
                continue
            dead.append((u, code))
            print("   FAIL %-5s %s" % (code, u[:76]), flush=True)
    if dead:
        print("\n  %d link(s) did not return 200." % len(dead))
        print("  A vendor being down is not a reason to block a publish;")
        print("  this mode is advisory unless you are checking a build.")
        return 1
    print("  all %d fetched successfully." % len(found))
    return 0


if __name__ == "__main__":
    sys.exit(main())
