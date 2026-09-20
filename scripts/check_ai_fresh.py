#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The AI page is current, and every vendor it names is really being read.

    python scripts/check_ai_fresh.py
    python scripts/check_ai_fresh.py --online   # also probe the live sources

Why this exists
---------------
A page that tracks nine vendors and a page that CLAIMS to track nine vendors
look identical. Both carry the names, both list announcements, and the second
one is just a little quieter than it used to be.

Every failure this family of pages has had is that shape. A feed moves and
answers 200 with an empty body. A sitemap's paths change and a prefix match
silently returns nothing -- which happened twice while building this, to
Anthropic and to xAI, and the audit output was the only thing that said so.
An aggregator changes a field name and every price becomes zero.

So this asks, of the data actually committed:

    1. IS IT FRESH? A store older than three days means the cron stopped,
       and a cron stops silently.

    2. IS EVERY VENDOR STILL SPEAKING? Each source has to have contributed
       something recent. A vendor present in the source list and absent from
       the data is the exact failure above.

    3. ARE THE NUMBERS NUMBERS? A catalogue where every price is zero, or
       every context window is missing, has changed shape underneath us.

    4. DOES THE PAGE MATCH THE STORE? The page is generated; if it was built
       from an older store, the counts it prints are not the data it shows.

--online adds a probe of the live sources, which is what the cron runs before
it fetches. It is not part of the push gate: a vendor's feed being down for
ten minutes is not a reason to refuse somebody's unrelated commit.
"""
import argparse
import datetime as dt
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
STORE = os.path.join(ROOT, "intelligence", "ai.json")
PAGE = os.path.join(ROOT, "intelligence", "ai", "index.html")

# How stale the store may be before the cron is assumed dead. The job runs
# daily; three days is two missed runs plus room for a slow Saturday.
MAX_AGE_DAYS = 3

# A source that has said nothing in this long is either quiet or broken, and
# the page cannot tell the difference -- so a human is told.
SILENT_DAYS = 60


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--online", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(STORE):
        print("  intelligence/ai.json does not exist -- nothing has been "
              "fetched")
        return 1

    data = json.load(io.open(STORE, encoding="utf-8"))
    releases = data.get("releases") or []
    models = data.get("models") or []
    sources = data.get("sources") or []
    problems = []
    today = dt.date.today()

    # ---- 1. freshness -------------------------------------------------
    fetched = (data.get("fetched") or "")[:10]
    try:
        age = (today - dt.date.fromisoformat(fetched)).days
    except ValueError:
        age = None
    if age is None:
        problems.append("the store carries no usable fetch date")
    else:
        print("  fetched %s (%d day(s) ago)" % (fetched, age))
        if age > MAX_AGE_DAYS:
            problems.append(
                "the store is %d days old and the job runs daily, so it has "
                "missed at least %d run(s). A cron that stops does not "
                "announce it -- the page simply keeps showing the last good "
                "day for ever" % (age, age - 1))

    # ---- 2. every vendor still speaking -------------------------------
    latest = {}
    for r in releases:
        v, d = r.get("vendor"), r.get("date")
        if v and d and d > latest.get(v, ""):
            latest[v] = d
    named = [s.get("vendor") for s in sources if s.get("kind") != "api"]
    for v in named:
        # Vendors on the same feed family report under one name; only
        # complain about a source that has contributed nothing at all.
        if v not in latest:
            problems.append(
                "%s is listed as a source and has contributed no "
                "announcements at all. Either the feed moved or the parser "
                "stopped matching -- both answer 200 and look like silence"
                % v)
            continue
        days = (today - dt.date.fromisoformat(latest[v])).days
        flag = "  SILENT" if days > SILENT_DAYS else ""
        print("  %-18s newest %s  (%3d days)%s" % (v, latest[v], days, flag))
        if days > SILENT_DAYS:
            problems.append(
                "%s has said nothing for %d days. That may be true, and it "
                "may be a parser matching nothing; the page cannot tell the "
                "difference and neither can a reader" % (v, days))

    # ---- 2b. every headline is a headline -----------------------------
    #
    # Reported as: "in what is being shipped I just see OpenAI and no news
    # associated to those." Every OpenAI title in the store was the single
    # byte 0x01 -- the CDATA unwrapper's replacement had been written as
    # "" rather than r"", so it substituted the SOH control character
    # for the headline. 207 links with nothing to click on, a store that
    # counted 401 items, and a page that rendered without an error.
    #
    # An empty string would have been caught by the parser's own guard. A
    # control character is a non-empty string, which is exactly why it got
    # through.
    broken = [r for r in releases
              if not "".join(ch for ch in (r.get("title") or "")
                             if ch.isprintable()).strip()]
    if broken:
        problems.append(
            "%d announcement(s) have a title that is empty or unprintable, "
            "so the page renders a link with nothing to click: %s"
            % (len(broken), ", ".join(r.get("url", "")[:48]
                                      for r in broken[:3])))
    else:
        print("  %d announcements, every one with a readable title"
              % len(releases))

    # An entity that never decoded is a typo nobody typed.
    #
    # "&#x27;" rendered on the page as those six characters, because the
    # decoder knew six entities by hand and the vendors between them used
    # four different spellings of an apostrophe. Cheap to assert, and it
    # fails on the next spelling as well as this one.
    entity = re.compile(r"&(#x?[0-9a-fA-F]+|[a-zA-Z][a-zA-Z0-9]{1,10});")
    raw = [r for r in releases if entity.search(r.get("title") or "")]
    if raw:
        problems.append(
            "%d title(s) still carry an undecoded HTML entity, which a "
            "reader sees literally: %s"
            % (len(raw), "; ".join((r.get("title") or "")[:52]
                                   for r in raw[:3])))

    # ---- 3. the numbers are numbers -----------------------------------
    if not models:
        problems.append("the model catalogue is empty")
    else:
        priced = [m for m in models if (m.get("in_per_m") or 0) > 0]
        sized = [m for m in models if m.get("context")]
        dated = [m for m in models if m.get("created")]
        print("  %d models: %d priced, %d with a context window, %d dated"
              % (len(models), len(priced), len(sized), len(dated)))
        if len(priced) < len(models) * 0.5:
            problems.append(
                "only %d of %d models carry a price. The catalogue's schema "
                "has probably changed: every one of them would render as "
                "free, which is a claim about somebody else's product"
                % (len(priced), len(models)))
        if len(sized) < len(models) * 0.8:
            problems.append("only %d of %d models carry a context window"
                            % (len(sized), len(models)))
        if len(dated) < len(models) * 0.5:
            problems.append(
                "only %d of %d models carry a creation date, and that field "
                "is what 'new this month' is computed from"
                % (len(dated), len(models)))

    # ---- 4. the page is built from this store -------------------------
    if os.path.exists(PAGE):
        html = io.open(PAGE, encoding="utf-8", errors="replace").read()
        pairs = [(len(models), "models tracked"),
                 (len(releases), "announcements")]
        for want, label in pairs:
            m = re.search(r"<b>([\d,]+)</b><span>" + re.escape(label), html)
            got = int(m.group(1).replace(",", "")) if m else None
            if got is None:
                problems.append("the page does not print a %s count, so it "
                                "cannot be compared with the store" % label)
            elif got != want:
                problems.append(
                    "the page says %s %s and the store holds %d. The page "
                    "was built from an older store than the one committed "
                    "beside it" % ("{:,}".format(got), label, want))
        if not problems:
            print("  the page's own counts match the store")
    else:
        problems.append("the page has never been built")

    # ---- optional: the live sources -----------------------------------
    if args.online:
        print()
        import fetch_ai
        if fetch_ai.audit() != 0:
            problems.append("at least one live source did not answer or has "
                            "gone stale (see the audit above)")

    print()
    if problems:
        print("  %d PROBLEM(S)" % len(problems))
        print()
        for p in problems:
            print("  - %s" % p)
        print()
        print("  A page that tracks nine vendors and a page that claims to")
        print("  look exactly alike. The difference is only ever visible in")
        print("  the data behind it.")
        return 1
    print("  The store is current, every source has spoken recently, the")
    print("  catalogue has real numbers, and the page matches the store.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
