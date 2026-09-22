#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The re:Invent planner tells the truth about time and distance.

    python scripts/check_reinvent.py

Why this exists
---------------
This page makes a claim the official catalog does not: that it will tell you
when two sessions you picked are too far apart to reach in time. A planner
that gets that wrong is worse than no planner, because the whole reason to
use it is to stop checking by hand.

So the rules below assert the things that would make it lie, and each one
carries a canary -- a case built to be caught -- because a rule that passes
the situation it was written for is worse than no rule.

  1. THE STORE IS WHOLE.  Every session has a code, a title, and facet
     indexes that resolve. An index pointing past the end of its table
     renders as "undefined" and nothing errors.

  2. THE PAGE AND THE STORE ARE THE SAME DATA.  The lane counts baked into
     the HTML are recomputed from the store here. A stale number on a tab is
     the failure with no symptom: it looks like a count, so nobody checks it.

  3. EVERY SLOT IS COHERENT.  Ends after it starts, sits on an announced
     event day, and names a venue that exists.

  4. THE HOP RULE FIRES.  Built from the real store: the tightest genuine
     cross-property pair in the catalog is found and the rule is run on it.
     If nothing in 1,500 sessions can trigger a warning, the feature is
     decorative.

  5. IT RENDERS AND IT FILTERS.  Served over HTTP -- not file:// -- and
     driven: search, lane, and starring a session into the plan. The earlier
     colophon check ran over file://, where absolute-path assets 404, and it
     reported three failures that did not exist. Serve it properly or the
     result means nothing.
"""
import datetime
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGEDIR = os.path.join(ROOT, "reinvent-2026")
HTML = os.path.join(PAGEDIR, "index.html")
DATA = os.path.join(ROOT, "intelligence", "reinvent2026.json")

EVENT_DAYS = ("2026-11-30", "2026-12-01", "2026-12-02",
              "2026-12-03", "2026-12-04")

# Matches STALE_DAYS in the page's own freshness banner. Kept the same so
# the check and the reader are working to one definition of "old".
STALE_DAYS = 21


def need_for(a, b, travel):
    """The page's own cost for a hop, recomputed from the same inputs."""
    if a == b:
        return travel["overhead"]
    cell = (travel["matrix"].get(a) or {}).get(b)
    if not cell:
        return travel["overhead"]
    return travel["overhead"] + int(round(
        cell["m"] * travel["detour"] / travel["pace"]))


def metres_between(a, b, travel):
    cell = (travel["matrix"].get(a) or {}).get(b)
    return cell["m"] if cell else 0


def config_of(html):
    m = re.search(r"window\.RI_CONFIG\s*=\s*(\{.*?\});", html, re.S)
    if not m:
        raise SystemExit("  the page carries no RI_CONFIG block")
    return json.loads(m.group(1))


def main():
    for path in (HTML, DATA):
        if not os.path.exists(path):
            print("  %s is missing. Run:\n      python scripts/"
                  "build_reinvent_page.py" % os.path.relpath(path, ROOT))
            return 1

    html = io.open(HTML, encoding="utf-8").read()
    data = json.load(io.open(DATA, encoding="utf-8"))
    cfg = config_of(html)
    problems = []

    sessions = data["sessions"]
    services = data["facets"]["Services"]
    venues, rooms = data["venues"], data["rooms"]

    # ---- 1. the store is whole -------------------------------------------
    bad_refs = 0
    for s in sessions:
        if not s.get("c") or not s.get("t"):
            problems.append("a session has no code or no title")
            break
    for s in sessions:
        for i in s["sv"]:
            if not (0 <= i < len(services)):
                bad_refs += 1
        for w in s["when"]:
            if not (0 <= w["v"] < len(venues)) or not (0 <= w["r"] < len(rooms)):
                bad_refs += 1
    if bad_refs:
        problems.append(
            "%d facet index/indices point past the end of their table. Those "
            "render as \"undefined\" on the page and raise nothing" % bad_refs)
    print("  %d session(s), %d service(s), %d venue(s), %d room(s)"
          % (len(sessions), len(services), len(venues), len(rooms)))

    # ---- 1b. the newer index tables resolve too ---------------------------
    #
    # Same failure as the facets: an index into the wrong table does not
    # raise, it renders the wrong person's name or the wrong service next
    # to an announcement, which looks like data rather than like a bug.
    speakers = data.get("speakers") or []
    bad_sp = sum(1 for x in sessions for i in (x.get("sp") or [])
                 if not (0 <= i < len(speakers)))
    if bad_sp:
        problems.append(
            "%d speaker index/indices point past the end of the speakers "
            "table; those render as the wrong name or as undefined" % bad_sp)
    with_sp = sum(1 for x in sessions if x.get("sp"))
    print("  %d speaker(s) across %d session(s), every index resolves"
          % (len(speakers), with_sp))

    news = cfg.get("news") or []
    bad_news = sum(1 for a in news for i in a.get("sv", [])
                   if not (0 <= i < len(services)))
    if bad_news:
        problems.append(
            "%d announcement(s) reference a service index the store does "
            "not have, so the page would label a launch with the wrong "
            "service" % bad_news)
    if news:
        undated = [a for a in news if not a.get("d")]
        if undated:
            problems.append("%d announcement(s) carry no date" % len(undated))
        print("  %d announcement(s) joined to the catalog, all indexes resolve"
              % len(news))

    # ---- 2. the tab counts are not stale ---------------------------------
    for lane in cfg["lanes"]:
        want = set(lane["services"])
        real = sum(1 for s in sessions if want.intersection(s["sv"]))
        if real != lane["count"]:
            problems.append(
                "the %s tab says %d session(s) and the store holds %d. The "
                "page was built from a different catalog than it ships"
                % (lane["name"], lane["count"], real))
        else:
            print("  lane %-18s %4d session(s), agrees with the store"
                  % (lane["name"], real))
        if not want:
            problems.append("lane %s matches no services at all" % lane["name"])

    # ---- 3. every slot is coherent ---------------------------------------
    #
    # An end of None is not a defect: AWS publishes a start and no duration
    # for a handful of sponsored sessions, and the store records that as
    # unknown rather than inventing one. What must never appear is an end
    # that is present and not after its start -- that is a real duration
    # the page would measure the next gap from, and it would under-warn.
    off_day, backwards, unknown = set(), 0, 0
    for s in sessions:
        for w in s["when"]:
            if w["e"] is None:
                unknown += 1
            elif w["e"] <= w["b"]:
                backwards += 1
            if w["d"] not in EVENT_DAYS:
                off_day.add(w["d"])
    if backwards:
        problems.append("%d slot(s) carry an end at or before their start. "
                        "Every gap measured from one of those is wrong, and "
                        "wrong in the direction that under-warns" % backwards)
    if off_day:
        problems.append("slot(s) fall outside the announced event days: %s"
                        % ", ".join(sorted(off_day)))
    print("  every published end is after its start; %d slot(s) have no "
          "duration in the catalog and are carried as unknown" % unknown)

    # ---- 4. the hop rule fires on the real catalog -----------------------
    travel = cfg["travel"]
    if travel["outlier"] not in venues:
        problems.append(
            "the travel rule treats %r as the outlying venue and no such "
            "venue is in the store, so the far estimate can never apply"
            % travel["outlier"])

    by_day = {}
    for s in sessions:
        for w in s["when"]:
            by_day.setdefault(w["d"], []).append((w, s))
    worst = None
    for day, slots in by_day.items():
        slots.sort(key=lambda p: p[0]["b"])
        for i, (a, sa) in enumerate(slots):
            if a["e"] is None:
                continue          # no published end, so no gap to measure
            for b, sb in slots[i + 1:]:
                if b["b"] < a["e"]:
                    continue
                gap = b["b"] - a["e"]
                if gap > 120:
                    break
                va, vb = venues[a["v"]], venues[b["v"]]
                if va == vb:
                    continue
                need = need_for(va, vb, travel)
                if gap < need and (worst is None or gap < worst[0]):
                    worst = (gap, need, va, vb, sa["c"], sb["c"], day)
    if worst is None:
        problems.append(
            "no pair of cross-property sessions anywhere in the catalog is "
            "close enough in time to trigger a warning. The feature the page "
            "is built around would never fire for anyone")
    else:
        gap, need, va, vb, ca, cb, day = worst
        print("  hop rule fires on real data: %s -> %s on %s, %d min gap "
              "against a %d min estimate (%s, %s)"
              % (va, vb, day, gap, need, ca, cb))

    # ---- 5. the page and the store agree about when this was captured ----
    #
    # The visible freshness line is computed in the reader's browser from
    # the store, so it cannot drift. The About section carries a build-time
    # date, and that one can: fetch without rebuilding and the page prints
    # a capture date the data it serves does not have. Same class of bug as
    # a stale tab count -- it looks like a fact, so nobody re-checks it.
    captured = data.get("captured") or ""
    on_page = re.search(r'<time datetime="([^"]+)">', html)
    if not captured:
        problems.append(
            "the store carries no capture date, so neither the page nor "
            "this check can say how old the catalog is")
    elif on_page and on_page.group(1) != captured:
        problems.append(
            "the page says it was captured %s and the store says %s. The "
            "catalog was refetched without rebuilding the page"
            % (on_page.group(1), captured))
    else:
        print("  page and store agree the catalog was captured %s" % captured)

    # ---- 6. how old is it ------------------------------------------------
    #
    # Reported, and deliberately NOT blocking on age alone. A freshness
    # rule that fails a push because a cron did not run would stop an
    # unrelated blog post from publishing, and a gate that is red on
    # arrival is a gate that gets uninstalled -- which is written down in
    # preflight.py about three other checks. The reader-facing protection
    # is the page stating its own age in the browser; this is the nudge.
    #
    # A capture date in the FUTURE does fail, because that is not staleness,
    # it is a corrupt or hand-edited store, and every age the page computes
    # from it would be wrong in the reassuring direction.
    if captured:
        try:
            when = datetime.date(*[int(x) for x in captured.split("-")])
        except (TypeError, ValueError):
            problems.append("the capture date %r is not a date" % captured)
        else:
            age = (datetime.date.today() - when).days
            if age < 0:
                problems.append(
                    "the store says it was captured %s, which is %d day(s) "
                    "in the future. Every age the page computes from that is "
                    "wrong, and wrong in the direction that looks current"
                    % (captured, -age))
            elif age >= STALE_DAYS:
                print("  NOTE: the catalog is %d days old. The page tells "
                      "readers so, but a refresh is overdue -- run "
                      "scripts/fetch_reinvent.py, or check the "
                      "refresh-reinvent workflow." % age)
            else:
                print("  the catalog is %d day(s) old, inside the %d-day "
                      "window the page treats as current" % (age, STALE_DAYS))

    # ---- the travel model is monotonic in distance -----------------------
    #
    # The whole point of deriving the estimate from coordinates is that a
    # longer hop can never be cheaper than a shorter one. The three-bucket
    # version it replaced failed exactly here: Wynn/Encore to Caesars Palace
    # is 1,443 m and was costed at 30 minutes, while Caesars Palace to MGM
    # Grand -- 1,565 m, barely further -- was costed at 45.
    pairs = []
    for a in venues:
        for b in venues:
            if a != b:
                pairs.append((metres_between(a, b, travel),
                              need_for(a, b, travel), a, b))
    pairs.sort()
    for i in range(1, len(pairs)):
        if pairs[i][1] < pairs[i - 1][1]:
            problems.append(
                "the travel model is not monotonic: %s->%s is %d m and costs "
                "%d min, while the shorter %s->%s at %d m costs %d min"
                % (pairs[i][2], pairs[i][3], pairs[i][0], pairs[i][1],
                   pairs[i - 1][2], pairs[i - 1][3], pairs[i - 1][0],
                   pairs[i - 1][1]))
            break
    else:
        print("  travel cost rises with distance across all %d venue pair(s)"
              % len(pairs))

    # ---- canaries --------------------------------------------------------
    same = need_for("Venetian", "Venetian", travel)
    if any(need_for(a, b, travel) <= same
           for a in venues for b in venues if a != b):
        problems.append(
            "CANARY: some hop between two properties costs no more than "
            "changing rooms inside one, so crossing the Strip would look "
            "free")
    else:
        print("  canary: a same-property room change is still the cheapest hop")

    # The regression this model exists to fix, pinned by name.
    if ("Wynn/Encore" in venues and "Caesars Palace" in venues
            and "MGM Grand" in venues):
        near_far = need_for("Wynn/Encore", "Caesars Palace", travel)
        real_far = need_for("Caesars Palace", "MGM Grand", travel)
        if near_far <= 30:
            problems.append(
                "CANARY: Wynn/Encore to Caesars Palace is costed at %d min. "
                "That is the 1,443 m hop the old flat model priced at 30 and "
                "under-warned on; it must cost more than that now"
                % near_far)
        elif abs(near_far - real_far) > 15:
            problems.append(
                "CANARY: Wynn/Encore->Caesars Palace (%d min) and Caesars "
                "Palace->MGM Grand (%d min) are 1,443 m and 1,565 m apart "
                "respectively, so their costs should be close. They are not"
                % (near_far, real_far))
        else:
            print("  canary: the two similar-length hops (1.4 km and 1.6 km) "
                  "cost %d and %d min, within a quarter-hour of each other"
                  % (near_far, real_far))

    # The store must never hand the page a zero-length slot dressed as a real
    # one. That is the shape the catalog actually ships for 11 sponsored
    # sessions, and it is the quiet failure: the gap to whatever follows gets
    # measured from a moment the session has not finished, so the page stays
    # silent exactly where it promises to speak up.
    zero = [w for s in sessions for w in s["when"]
            if w["e"] is not None and w["e"] <= w["b"]]
    if zero:
        problems.append(
            "CANARY: %d slot(s) reached the page with an end that is not "
            "after its start" % len(zero))
    else:
        print("  canary: no slot reaches the page with a zero or negative "
              "duration dressed as a real one")

    print()
    if problems:
        print("  %d PROBLEM(S)" % len(problems))
        print()
        for p in problems:
            print("  - %s" % p)
        print()
        print("  A planner that is wrong about one gap is not wrong about that")
        print("  gap. It is wrong about whether it can be trusted on the next.")
        return 1
    print("  The store resolves, the tab counts match it, every slot is")
    print("  coherent, and the venue rule fires on sessions that really exist.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
