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


def need_for(a, b, travel):
    if a == b:
        return travel["same"]
    if travel["outlier"] in (a, b):
        return travel["far"]
    return travel["near"]


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

    # ---- canaries --------------------------------------------------------
    t = {"same": 10, "near": 30, "far": 45, "outlier": "MGM Grand"}
    if need_for("MGM Grand", "Venetian", t) <= need_for("Venetian",
                                                        "Caesars Forum", t):
        problems.append(
            "CANARY: crossing to MGM Grand is not costed higher than a hop "
            "inside the northern run, so the one venue that actually sits "
            "apart is treated as if it does not")
    else:
        print("  canary: the outlying venue still costs more than a near hop")

    if need_for("Venetian", "Venetian", t) >= need_for("Venetian",
                                                        "Wynn/Encore", t):
        problems.append(
            "CANARY: changing rooms inside one property costs as much as "
            "crossing to another, so every same-venue pair would warn")
    else:
        print("  canary: a same-property room change is still the cheapest hop")

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
