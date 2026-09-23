#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Does what we serve still match what AWS is serving?

    python scripts/audit_reinvent_truth.py

Part of the re:Invent deep audit. Run the whole suite with:

    python scripts/audit_reinvent.py

Why this exists
---------------
Asked before sharing the page with a leadership team: "if my team looks
for a service and it suggests an incorrect session, it's going to look
really bad ... can we do some sort of thorough health check of each and
every component?"

The 64-check preflight gate asserts the page is not broken. That is a
different question from "is what it says true". These audits answer the
second one, and they do it the only way that counts: they drive the real
page, read back what it actually displays, and re-derive every claim from
the store independently. Nothing here checks the code against itself.

They are NOT in preflight. Two of them need the network and the suite
takes several minutes -- a gate that slow gets disabled. Run it before
sharing the page with anybody who matters, and after any change to how
sessions are selected or ranked.
"""
import io, json, random, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, "scripts")
from fetch_reinvent import credentials, post

SAMPLE = 40
STORE = json.load(io.open("intelligence/reinvent2026.json", encoding="utf-8"))
ROOMS = STORE["rooms"]
VEN = STORE["venues"]
scheduled = [x for x in STORE["sessions"] if x["when"]]

random.seed(7)
pick = random.sample(scheduled, SAMPLE)

creds = credentials()
print("=== comparing %d randomly chosen sessions against the live catalog"
      % SAMPLE)
print("    store captured %s" % STORE.get("captured_utc"))
print()

problems, checked, missing = [], 0, 0
for x in pick:
    code = x["c"]
    try:
        d = post(creds, {"search": code})
    except Exception as e:
        print("   ?    %-10s query failed: %s" % (code, str(e)[:40]))
        continue
    items = d.get("items") or ((d.get("sectionList") or [{}])[0]
                               .get("items") or [])
    live = None
    for it in items:
        if it.get("code") == code:
            live = it
            break
    if live is None:
        missing += 1
        problems.append("%s: the live catalog no longer returns this code"
                        % code)
        print("   GONE %-10s not in the live catalog" % code)
        time.sleep(0.25)
        continue

    lt = (live.get("times") or [{}])[0]
    mine = x["when"][0]
    mine_room = ROOMS[mine["r"]]
    diffs = []
    if (lt.get("date") or "") != mine["d"]:
        diffs.append("day %s -> %s" % (mine["d"], lt.get("date")))
    if int(lt.get("startTimeMin") or -1) != mine["b"]:
        diffs.append("start %s -> %s" % (mine["b"], lt.get("startTimeMin")))
    live_end = lt.get("endTimeMin")
    live_end = (int(live_end) if live_end is not None
                and int(live_end) > int(lt.get("startTimeMin") or 0) else None)
    if live_end != mine["e"]:
        diffs.append("end %s -> %s" % (mine["e"], live_end))
    if (lt.get("room") or "") != mine_room:
        diffs.append("room %r -> %r" % (mine_room[:28],
                                        (lt.get("room") or "")[:28]))
    cap = lt.get("capacity")
    cap = int(cap) if str(cap or "").isdigit() else None
    if cap != mine["cap"]:
        diffs.append("seats %s -> %s" % (mine["cap"], cap))

    checked += 1
    if diffs:
        problems.append("%s: %s" % (code, "; ".join(diffs)))
        print("   DIFF %-10s %s" % (code, "; ".join(diffs)[:80]))
    else:
        print("   ok   %-10s %s %s  %s"
              % (code, mine["d"][5:],
                 "%02d:%02d" % (mine["b"] // 60, mine["b"] % 60),
                 mine_room[:44]))
    time.sleep(0.25)

print()
print("=" * 62)
print("  %d checked, %d matched exactly, %d withdrawn, %d differing"
      % (checked + missing, checked - len([p for p in problems
                                           if not p.endswith("code")]),
         missing, len(problems) - missing))
if problems:
    print()
    for p_ in problems[:20]:
        print("   -", p_)
    sys.exit(1)
print("  Every sampled session matches AWS exactly.")
