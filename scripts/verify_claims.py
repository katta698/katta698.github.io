#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Confirm that each verified_claim's figures actually appear on the page it cites.

    python scripts/verify_claims.py                  # every series
    python scripts/verify_claims.py --series az      # one series
    python scripts/verify_claims.py az-002           # one post
    python scripts/verify_claims.py --verbose        # show every claim

Why this exists
---------------
`validate_arch_post.py` proves a citation is the vendor's own domain and that
the URL resolves. It cannot read the page, so a claim can cite a real, live,
authoritative document and still say something the document does not say.

That is not hypothetical, and it is not a small failure mode. AWS arch-018
shipped a wrong break-even citing two genuine AWS pricing pages: the sources
were real, the links resolved, every check of the day passed, and the
conclusion was wrong because the arithmetic was done across figures from
different years. `_check_derived` in the validator was the answer to the
arithmetic half. This is the answer to the other half -- does the cited page
actually contain the numbers the claim attributes to it?

What it checks, and what that is worth
--------------------------------------
For every claim it extracts the *falsifiable* tokens -- figures with units,
decimals, percentages, and numbers of three digits or more -- and confirms each
appears in the text of the cited page.

Presence is **necessary, not sufficient**. Finding "22" on a page about Azure
Firewall does not prove the page says Premium is rated at 22 Gbps in Deny mode.
So a pass here means "the page contains the figures this claim rests on", which
is a real and previously unchecked property, not "the claim is true". Reading
remains a human job; this removes the class of error where the figure was never
on the page at all.

Bare small integers are reported as WEAK and not enforced: "one parent", "four
scopes" and "two levels" would match almost any page and enforcing them would
train people to ignore the output.

Client-rendered pages
---------------------
Some vendor pages return a JavaScript shell with no readable text, so their
content cannot be checked by fetching. Those are reported UNCHECKABLE rather
than passed silently, because a check that quietly skips its hardest cases is
worse than no check.

Azure Updates is the important instance and has a real fix rather than an
exemption: `azure.microsoft.com/updates?id=NNN` is a shell, but the same record
is available as JSON from the release-communications API, so the description is
fetched from there and checked properly. Any future host with the same problem
should get the same treatment, not an exemption.

A defect and an outage are not the same finding
-----------------------------------------------
MISSING means a page loaded and did not contain the figure -- that is a defect
in the post, and it is what this script exists to catch. UNREACHABLE means the
fetch itself failed, which says nothing about the post: the vendor's edge was
down, DNS blipped, the runner had no egress.

Both used to exit 1. In an interactive run that is right -- an unreachable page
means you did not get the check you asked for, and you should know before you
publish. In CI it is wrong, and expensively so: a 503 from Microsoft's edge
(observed during testing, and gone on immediate retry) would redden a build on
a post with nothing whatever wrong with it. A gate that fails for reasons the
author cannot fix and cannot predict is a gate people switch off, and then the
MISSING findings stop being seen too.

So the caller says which it wants:

    --fail-on any       MISSING or UNREACHABLE fails  (default; hand runs)
    --fail-on missing   only MISSING fails            (CI)

Unreachable sources are still printed either way. `--fail-on missing` downgrades
them from a failure to a report; it never hides them.
"""
import argparse
import collections
import html
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import yaml

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS = os.path.join(ROOT, "posts")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validate_arch_post import SERIES                          # noqa: E402

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# A page whose readable text is shorter than this is a shell, not an article.
MIN_TEXT = 1200

AZURE_UPDATES_RE = re.compile(
    r"^https://azure\.microsoft\.com/(?:[a-z-]+/)?updates/?\?id=(\d+)", re.I)
AZURE_UPDATES_API = "https://www.microsoft.com/releasecommunications/api/v2/azure"

# Figures worth enforcing: anything with a unit, a decimal point, a percentage,
# a currency symbol, or three or more digits. Everything else is prose.
# Order matters: alternation is first-match-wins at each position, so the
# longest forms come first. Without the grouped-thousands branch ahead of the
# plain-digits one, "1,000,000" was read as "1,000" followed by a stray "000",
# and the stray was then reported as missing from a page that plainly contained
# the figure.
STRONG_RE = re.compile(r"""
    \$\s?\d{1,3}(?:,\d{3})+(?:\.\d+)?
  | \$\s?\d+(?:\.\d+)?
  | \d{1,3}(?:,\d{3})+(?:\.\d+)?\s?%
  | \d+(?:\.\d+)?\s?%
  | \d{1,3}(?:,\d{3})+(?:\.\d+)?\s?(?:x|×)\b
  | \d+(?:\.\d+)?\s?(?:x|×)\b
  | \d{1,3}(?:,\d{3})+(?:\.\d+)?\s?(?:Gbps|Mbps|Kbps|GB|TB|MB|KB|GiB|TiB|WCU|RCU|vCPU)\b
  | \d+(?:\.\d+)?\s?(?:Gbps|Mbps|Kbps|GB|TB|MB|KB|GiB|TiB|WCU|RCU|vCPU)\b
  | \d{1,3}(?:,\d{3})+\s?(?:ms|seconds?|minutes?|hours?|days?|weeks?|months?|years?)\b
  | \d+(?:\.\d+)?\s?(?:ms|seconds?|minutes?|hours?|days?|weeks?|months?|years?)\b
  | \d+\.\d+
  | \b\d{1,3}(?:,\d{3})+\b
  | \b\d{3,}\b
""", re.X | re.I)

TAG_RE = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)


def digits(text):
    """Comparable form of a figure: digits and decimal point only."""
    return re.sub(r"[^\d.]", "", str(text)).rstrip(".")


def fetch(url, attempts=3):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for i in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or i == attempts - 1:
                raise
        except (urllib.error.URLError, TimeoutError):
            if i == attempts - 1:
                raise
        time.sleep(2 * (i + 1))


def page_text(url):
    """Readable text of a cited page as (text, kind), or (None, None).

    `kind` is "html" for a fetched page and "api" for a record read from a
    vendor API. The distinction matters: the shell threshold below exists to
    catch a JavaScript stub masquerading as an article, and an API record is
    legitimately short -- an Azure Updates entry is a couple of hundred
    characters of real content. Applying the HTML threshold to it reported four
    perfectly checkable claims as uncheckable.

    Azure Updates is served as a client-rendered shell, so its content is taken
    from the release-communications API by id instead. That is the same record
    the page renders, not a substitute source.
    """
    m = AZURE_UPDATES_RE.match(url)
    if m:
        flt = "id eq '%s'" % m.group(1)
        api = AZURE_UPDATES_API + "?" + urllib.parse.urlencode({"$filter": flt})
        try:
            rec = (json.loads(fetch(api)).get("value") or [None])[0]
        except Exception:                                      # noqa: BLE001
            return None, None
        if not rec:
            return None, None
        raw = "%s %s" % (rec.get("title", ""), rec.get("description", ""))
        return clean(raw), "api"

    try:
        body = fetch(url)
    except Exception:                                          # noqa: BLE001
        return None, None
    return clean(body.decode("utf-8", "replace")), "html"


def clean(raw):
    raw = TAG_RE.sub(" ", raw)
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text)


# A bare year is when something happened, not a figure the cited page must
# contain. "the rates AWS halved in November 2024" is a true and useful thing to
# say on a pricing page that lists only today's prices, and enforcing it flagged
# arch-018 for its one accurate sentence while its actual defect was arithmetic.
YEAR_RE = re.compile(r"^(?:19|20)\d{2}$")


def tokens(claim):
    """Strong (enforced) and weak (reported only) figures in a claim."""
    strong, seen = [], set()
    for t in STRONG_RE.findall(claim):
        d = digits(t)
        if not d or d in seen:
            continue
        seen.add(d)
        if YEAR_RE.match(t.strip()):
            continue
        strong.append(t.strip())
    weak = []
    for t in re.findall(r"\b\d{1,2}\b", claim):
        if t not in seen and t not in weak:
            weak.append(t)
    return strong, weak


def present(token, text, text_digits):
    """Is this figure on the page, in any reasonable formatting?"""
    d = digits(token)
    if not d:
        return False
    if d in text_digits:
        return True
    # "1,200" on the page against "1200" in the claim, and vice versa.
    if len(d) > 3 and re.search(r"\b%s\b" % re.escape(
            "{:,}".format(int(float(d)))), text):
        return True
    # "22 Gbps" written "22Gbps" or "22 gbps"
    unit = re.sub(r"[\d,.\s]", "", token)
    if unit and re.search(r"%s\s*%s" % (re.escape(d), re.escape(unit)),
                          text, re.I):
        return True
    return False


def check_post(path, cache, verbose):
    raw = io.open(path, encoding="utf-8").read()
    if not raw.startswith("---"):
        return None
    fm = yaml.safe_load(raw.split("---", 2)[1]) or {}
    claims = fm.get("verified_claims") or []
    if not fm.get("verified") or not claims:
        return None

    name = os.path.basename(path)
    rows = []
    for i, c in enumerate(claims, 1):
        if not isinstance(c, dict):
            continue
        claim, src = str(c.get("claim", "")), str(c.get("source", "")).strip()
        strong, weak = tokens(claim)

        # A derived figure is computed by the author, so by definition it is not
        # on the cited page -- that is what `derive:` means. Requiring it would
        # fail every correctly-formed derived claim on the site and train people
        # to ignore this output, which is the same reason bare small integers are
        # reported WEAK rather than enforced. The arithmetic is not going
        # unchecked: validate_arch_post.py re-evaluates `derive:` against
        # `expect:` and fails on a mismatch, which is the stronger check.
        #
        # Only the result is exempt. Every other figure in the claim -- crucially
        # the inputs the arithmetic was done on -- must still be found on the
        # page. That is precisely the arch-018 failure: real sources, live links,
        # and a break-even computed from a price that was no longer on either
        # page.
        derived_only = False
        if c.get("derive") and c.get("expect") is not None:
            want = digits(str(c["expect"]))
            kept = [t for t in strong if digits(t) != want]
            # If the result was the claim's ONLY figure, exempting it leaves
            # nothing to check against the page, and the claim would quietly
            # report as having no figures at all. Say so instead: the fix is to
            # state the inputs in the claim ("1,000 keys at 1,000 values each
            # is ...") so the numbers the arithmetic rests on are the ones
            # verified against the source.
            derived_only = bool(strong) and not kept
            strong = kept

        if src not in cache:
            cache[src] = page_text(src)
        text, kind = cache[src]

        if text is None:
            rows.append(("UNREACHABLE", i, claim, src, strong, []))
            continue
        if kind == "html" and len(text) < MIN_TEXT:
            rows.append(("UNCHECKABLE", i, claim, src, strong, []))
            continue

        text_digits = set(digits(t) for t in re.findall(
            r"\d[\d,]*(?:\.\d+)?", text))
        missing = [t for t in strong if not present(t, text, text_digits)]
        if derived_only:
            rows.append(("DERIVED-ONLY", i, claim, src, strong, []))
        elif not strong:
            rows.append(("NO-FIGURES", i, claim, src, strong, []))
        elif missing:
            rows.append(("MISSING", i, claim, src, strong, missing))
        else:
            rows.append(("OK", i, claim, src, strong, []))
    return name, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("posts", nargs="*", help="substring of a post filename")
    ap.add_argument("--series", help="one series key: %s" % ", ".join(sorted(SERIES)))
    ap.add_argument("--verbose", action="store_true", help="print every claim")
    ap.add_argument("--fail-on", choices=("any", "missing"), default="any",
                    help="'any' (default) fails on MISSING or UNREACHABLE; "
                         "'missing' fails only on a figure absent from a page "
                         "that loaded, so a vendor outage reports without "
                         "blocking. Use 'missing' in CI.")
    args = ap.parse_args()

    specs = SERIES if not args.series else {args.series: SERIES[args.series]}
    files = []
    for key, spec in sorted(specs.items()):
        for f in sorted(os.listdir(POSTS)):
            if f.startswith(spec["file_prefix"]) and f.endswith(".html"):
                files.append((key, os.path.join(POSTS, f)))
    if args.posts:
        files = [(k, p) for k, p in files
                 if any(a in os.path.basename(p) for a in args.posts)]
    if not files:
        print("No badged posts matched.")
        return 0

    cache = {}
    totals = collections.Counter()
    problems = []
    print("%-46s %-6s %-5s %-6s %s"
          % ("post", "claims", "ok", "figs", "verdict"))
    print("-" * 92)
    for key, path in files:
        got = check_post(path, cache, args.verbose)
        if not got:
            continue
        name, rows = got
        ok = sum(1 for r in rows if r[0] == "OK")
        figs = sum(len(r[4]) for r in rows)
        bad = [r for r in rows if r[0] in ("MISSING", "UNREACHABLE")]
        unchk = [r for r in rows if r[0] == "UNCHECKABLE"]
        verdict = ("%d unverified" % len(bad) if bad
                   else ("%d uncheckable" % len(unchk) if unchk else "all figures found"))
        for r in rows:
            totals[r[0]] += 1
        print("%-46s %-6d %-5d %-6d %s" % (name[:46], len(rows), ok, figs, verdict))
        for r in rows:
            if r[0] in ("MISSING", "UNREACHABLE", "DERIVED-ONLY") or args.verbose:
                problems.append((name, r))

    if problems:
        print()
        for name, (status, i, claim, src, strong, missing) in problems:
            print("%s  claim %d  [%s]" % (name, i, status))
            print("   %s" % claim[:150])
            print("   source : %s" % src)
            if strong:
                print("   figures: %s" % ", ".join(strong))
            if missing:
                print("   NOT ON PAGE: %s" % ", ".join(missing))
            print()

    print("claims: %s" % ", ".join("%s=%d" % (k, v) for k, v in sorted(totals.items())))

    # An unreachable page is a check that did not happen, not a defect that did.
    # Say which of the two is being counted, so a green run under --fail-on
    # missing can never be mistaken for "every figure was confirmed".
    if totals["UNREACHABLE"] and args.fail_on == "missing":
        print("\n%d source(s) could not be fetched. Not failing the run: an "
              "unreachable page is a vendor or network problem, not a defect "
              "in the post. Those claims are UNCONFIRMED, not passed."
              % totals["UNREACHABLE"])

    if totals["MISSING"]:
        return 1
    return 1 if (totals["UNREACHABLE"] and args.fail_on == "any") else 0


if __name__ == "__main__":
    sys.exit(main())
