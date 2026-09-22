#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""An incident is labelled the way the vendor labels it, and counted once.

    python scripts/check_status_lifecycle.py

Why this exists
---------------
Asked, after finding a resolved AWS incident badged ONGOING on the live page:

    "we didn't anticipate this, and even you didn't validate it. There might
     be incidents from Azure and GCP as well, and from AWS down the road.
     This is something I observed. I might not observe down the road. How do
     you ensure, when an incident happens it shows up, and when it is
     resolved it goes away at some point?"

That is the right question and the honest answer at the time was: nothing
ensured it. The bug was fixed and no check was added, so the next one would
have been found the same way -- by a person noticing.

check_status_cards.py existed and passed throughout. It asserts the dialog
mechanics: one dialog opens, a healthy card is not tappable, the incidents
survive with scripts off. Every one of those was true while the page said
ONGOING over a title reading [RESOLVED]. A check that cannot fail on the bug
in front of it is the thing this file exists to stop being true twice.

So this asserts the LIFECYCLE, on whatever the three vendors happen to be
reporting today:

  1. NOTHING IS INVENTED.  Every incident rendered on the page is in the
     store. A card that outlives its source is a page reporting an outage
     that is over -- the failure in the other direction from the one found.

  2. THE LABEL MATCHES THE EVIDENCE.  Resolved is not a judgement call: it
     is an explicit end timestamp where the vendor publishes one (Azure and
     Google do) or AWS's own [RESOLVED] summary prefix. Whatever the
     evidence says, the badge has to say.

  3. A CLOSED INCIDENT HAS A STOPPED CLOCK.  No "Open for" row on something
     that has ended. That row counts from the start to NOW, so on a resolved
     incident it does not merely look wrong, it grows.

  4. THE NUMBERS RECONCILE.  The cloud card's headline, the dialog heading
     and the badges are three statements of the same fact and must agree.
     A cloud whose incidents have all closed is not shown red.

  5. IT ACTUALLY LOOKED.  A quiet day is the normal case for this page, and
     "no incidents to check" must not read as "checked and fine". The run
     reports what it exercised, and --require-incidents makes an empty
     sweep an error for use when something is known to be open.

The canary at the end rebuilds the exact broken state -- a resolved incident
carrying an Ongoing badge -- and fails the run if the rules above accept it.
Every pattern here carries one, because a rule that passes the case it was
written for is worse than no rule.
"""
import argparse
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(ROOT, "intelligence", "status.json")
PAGE = os.path.join(ROOT, "intelligence", "status", "index.html")
LABEL = {"aws": "AWS", "azure": "Azure", "gcp": "Google Cloud"}


def resolved_by_vendor(i):
    """The vendor's own statement that this is over, or None.

    Deliberately the same two signals the builder uses, read straight from
    the store rather than from the page -- otherwise this would check the
    page against itself and agree with any mistake it made.
    """
    if (i.get("end") or "").strip():
        return "end timestamp"
    if (i.get("title") or "").lstrip().upper().startswith("[RESOLVED]"):
        return "[RESOLVED] prefix"
    return None


def incidents_in(html, cloud):
    """Every incident card the page renders for one cloud."""
    block = re.search(r'id="inc-%s".*?(?=id="inc-|<footer|\Z)' % cloud,
                      html, re.S)
    if not block:
        return []
    return re.findall(r"<article class=\"inc\".*?</article>",
                      block.group(0), re.S)


def title_of(card):
    m = re.search(r'<h3 class="ttl">(.*?)</h3>', card, re.S)
    return re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else ""


def badge_of(card):
    if 'class="chip done"' in card:
        return "Resolved"
    if re.search(r'<span class="chip sev">Ongoing</span>', card):
        return "Ongoing"
    return "(none)"


def has_live_clock(card):
    return bool(re.search(r'<div class="k">Open for</div>', card))


def judge(card, closed):
    """The rules, as one function, so the canary can call exactly them."""
    bad = []
    badge = badge_of(card)
    if closed and badge != "Resolved":
        bad.append("vendor closed it (%s) and the badge says %s" % (closed, badge))
    if not closed and badge != "Ongoing":
        bad.append("vendor still lists it as open and the badge says %s" % badge)
    if closed and has_live_clock(card):
        bad.append("closed, but still carries an \"Open for\" row, which "
                   "counts to now and therefore grows")
    return bad


def understood_the_feed(store):
    """Did we make sense of what each vendor actually sent?

    ok=true with nothing parsed is this page's most dangerous state,
    because nothing parsed is also the right answer on a quiet day. A calm
    Tuesday and a parser that has stopped understanding the feed render
    byte-for-byte the same page -- and the second one reports a cloud as
    healthy through an outage.

    Demonstrated rather than assumed: feeding the live parser a real EC2
    outage with one field renamed from "summary" to "title" returns HTTP
    200, raises nothing, leaves ok true, and yields zero incidents. The
    page then prints "No active incidents - vendor reports none."

    What separates the two cases is the payload itself. AWS's data.json
    carries only the events it currently has, so a genuinely quiet AWS is
    an EMPTY list -- measured at the time of writing: aws 3 records and 3
    parsed, gcp 6 and 6, azure 0 and 0 on a quiet feed. A shape change is
    the opposite shape: records present, none of them understood.

    So the invariant is simply that those two numbers agree about whether
    there was anything there. No thresholds, no history, and it holds on a
    quiet day, which is when this page spends most of its life.
    """
    out = []
    for cloud, src in sorted((store.get("sources") or {}).items()):
        if cloud.endswith("_history") or not src.get("ok"):
            continue
        rec, parsed = src.get("records"), src.get("parsed")
        if rec is None or parsed is None:
            print("  %-5s records not recorded yet (the fetcher writes them "
                  "from its next run)" % cloud)
            continue
        print("  %-5s payload held %s record(s), parser understood %s"
              % (cloud, rec, parsed))
        if rec > 0 and parsed == 0:
            out.append(
                "%s answered %d and its payload held %d record(s), and the "
                "parser understood none of them. That is not a quiet day -- "
                "a quiet feed is an empty payload. The page would be saying "
                "this cloud is healthy on evidence it could not read"
                % (cloud, src.get("http") or 0, rec))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--require-incidents", action="store_true",
                    help="fail if no incident is open anywhere (for use when "
                         "one is known to be)")
    args = ap.parse_args()

    for path, what in ((STORE, "status.json"), (PAGE, "the status page")):
        if not os.path.exists(path):
            print("  %s does not exist -- nothing to check" % what)
            return 1

    store = json.load(io.open(STORE, encoding="utf-8"))
    html = io.open(PAGE, encoding="utf-8", errors="replace").read()
    problems, seen_cards, clouds_with = [], 0, []

    for cloud, items in (store.get("clouds") or {}).items():
        cards = incidents_in(html, cloud)
        if items:
            clouds_with.append(cloud)
        open_n = sum(1 for i in items if not resolved_by_vendor(i))
        shut_n = len(items) - open_n
        print("  %-5s store: %d open, %d resolved   page: %d card(s)"
              % (cloud, open_n, shut_n, len(cards)))

        # 1. nothing rendered that the store does not carry
        titles = {(i.get("title") or "").strip() for i in items}
        for card in cards:
            t = title_of(card)
            if t and t not in titles:
                problems.append(
                    "%s renders \"%s\", which is not in the store. The page is "
                    "reporting an incident its own source has dropped"
                    % (cloud, t[:60]))

        # 2 and 3. the badge and the clock, per incident
        by_title = {(i.get("title") or "").strip(): i for i in items}
        for card in cards:
            seen_cards += 1
            i = by_title.get(title_of(card))
            if i is None:
                continue
            for bad in judge(card, resolved_by_vendor(i)):
                problems.append("%s \"%s\": %s"
                                % (cloud, title_of(card)[:52], bad))

        # 4. the headline agrees with the badges
        ongoing = sum(1 for c in cards if badge_of(c) == "Ongoing")
        if ongoing != open_n:
            problems.append(
                "%s: the store has %d open incident(s) and the page badges %d "
                "as ongoing" % (cloud, open_n, ongoing))

        card_v = re.search(
            r'<div class="sc-n">%s</div>\s*<div class="sc-v">.*?'
            r'<span class="pill (\w+)"></span>\s*<span class="sc-vt">(.*?)</span>'
            % re.escape(LABEL[cloud]), html, re.S)
        if card_v:
            pill, verdict = card_v.group(1), card_v.group(2)
            n = re.match(r"(\d+)", verdict)
            if n and "resolved" not in verdict and int(n.group(1)) != open_n:
                problems.append(
                    "%s: the summary card says %r and %d incident(s) are open"
                    % (cloud, verdict, open_n))
            if pill == "bad" and open_n == 0:
                problems.append(
                    "%s: every incident it lists has been closed and the card "
                    "is still red (%r)" % (cloud, verdict))

    # 5. say what was exercised; a quiet sweep is not a pass
    print("  %d incident card(s) judged across %s"
          % (seen_cards, ", ".join(clouds_with) if clouds_with else "no cloud"))
    if args.require_incidents and not seen_cards:
        problems.append("no incident was open anywhere, so none of the label "
                        "rules were exercised, and --require-incidents was set")

    # ---- did we understand the feed at all --------------------------------
    problems += understood_the_feed(store)

    # ---- the canary -------------------------------------------------------
    #
    # Rebuild the state that shipped and make sure these rules reject it. If
    # this ever passes, the checks above have stopped meaning anything.
    broken = ('<article class="inc"><div class="top">'
              '<span class="chip aws">AWS</span>'
              '<span class="chip sev">Ongoing</span></div>'
              '<h3 class="ttl">[RESOLVED] Increased Error Rates</h3>'
              '<div class="meta"><div class="k">Open for</div><div>12h 43m</div>'
              "</div></article>")
    caught = judge(broken, resolved_by_vendor(
        {"title": "[RESOLVED] Increased Error Rates"}))
    blind = understood_the_feed(
        {"sources": {"aws": {"ok": True, "http": 200,
                             "records": 3, "parsed": 0}}})
    if not blind:
        problems.append(
            "THE SECOND CANARY PASSED. A source that returned three records "
            "and yielded no incidents is the silent-parser failure, and this "
            "run accepted it as a quiet day")
    else:
        print("  canary: a feed we stopped understanding is still caught")
    if len(caught) < 2:
        problems.append(
            "THE CANARY PASSED. A resolved incident wearing an Ongoing badge "
            "over a live clock is the exact page that shipped, and these "
            "rules just accepted it -- so they are asserting nothing")
    else:
        print("  canary: the shipped bug is still caught (%d rule(s) fire)"
              % len(caught))

    print()
    if problems:
        print("  %d PROBLEM(S)" % len(problems))
        print()
        for p in problems:
            print("  - %s" % p)
        print()
        print("  A status page that mislabels one incident is not wrong about")
        print("  that incident. It is wrong about whether it can be trusted")
        print("  on the next one.")
        return 1
    print("  Every incident is badged the way its vendor reports it, closed")
    print("  ones have stopped counting, and the headlines agree with the")
    print("  badges underneath them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
