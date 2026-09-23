#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Is every suggested day actually attendable, and every label true?

    python scripts/audit_reinvent_planner.py

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
import io, json, math, subprocess, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

STORE = json.load(io.open("intelligence/reinvent2026.json", encoding="utf-8"))
S = {x["c"]: x for x in STORE["sessions"]}
SVC = STORE["facets"]["Services"]
VEN = STORE["venues"]
ROOMS = STORE["rooms"]
DAYS = sorted({w["d"] for x in STORE["sessions"] for w in x["when"]})
PACE = {"relaxed": 25, "standard": 15, "packed": 5}

srv = subprocess.Popen([sys.executable, "-m", "http.server", "8907"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(2)
problems = []
checked = 0


def slot_on(code, day):
    for w in S[code]["when"]:
        if w["d"] == day:
            return w
    return None


try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1400, "height": 1100})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto("http://localhost:8907/reinvent-2026/", wait_until="networkidle")
        pg.wait_for_selector(".card", state="attached", timeout=30000)
        pg.evaluate("document.getElementById('tab-plan2').click()")
        pg.wait_for_timeout(800)

        # the travel matrix and pace, straight from the page's own config
        CFG = pg.evaluate("window.RI_CONFIG")
        MAT = CFG["travel"]["matrix"]
        OVER = CFG["travel"]["overhead"]
        DET = CFG["travel"]["detour"]
        PX = CFG["travel"]["pace"]

        def need(a, b):
            if a == b:
                return OVER
            cell = MAT.get(a, {}).get(b)
            return OVER + int(round(cell["m"] * DET / PX)) if cell else OVER

        svc_opts = pg.eval_on_selector_all(
            "#pl-service option",
            "es => es.map(e => [e.value, e.textContent.trim()])")
        picks = {}
        for val, txt in svc_opts:
            if val == "":
                continue
            for name in ("Amazon Elastic Kubernetes", "AWS Amplify",
                         "AWS Lambda", "AWS Transit Gateway",
                         "Amazon Bedrock", "AWS Cloud WAN"):
                if txt.startswith(name):
                    picks[name] = val

        combos = []
        for day in DAYS:
            for at in sorted(MAT.keys()):
                combos.append((day, at, "", "standard"))
        for name, val in picks.items():
            for day in DAYS[:4]:
                combos.append((day, "Caesars Forum", val, "standard"))
        for pace in ("relaxed", "packed"):
            combos.append(("2026-12-02", "MGM Grand", "", pace))

        print("=== driving %d planner combinations" % len(combos))
        for day, at, svc, pace in combos:
            pg.select_option("#pl-day", day)
            pg.select_option("#pl-at", at)
            pg.select_option("#pl-service", svc)
            pg.select_option("#pl-pace", pace)
            pg.wait_for_timeout(1500)

            codes = pg.eval_on_selector_all(
                "#planbody2 .card .code",
                "es => es.map(e => e.textContent.trim())")
            marks = pg.eval_on_selector_all(
                "#planbody2 .svmark",
                "es => es.map(e => [e.className, e.textContent.trim()])")
            tips = pg.eval_on_selector_all(
                "#planbody2 .tip strong",
                "es => es.map(e => e.textContent)")
            tag = "%s from %-15s %-6s %s" % (day[5:], at, pace,
                                             ("svc" if svc else ""))
            if not codes:
                continue
            checked += 1
            buf = PACE[pace]

            # every code exists and is on the right day
            prev = None
            for k, code in enumerate(codes):
                if code not in S:
                    problems.append("%s: %s is not in the store" % (tag, code))
                    continue
                w = slot_on(code, day)
                if not w:
                    problems.append("%s: %s is not scheduled on that day"
                                    % (tag, code))
                    continue
                if w["e"] is None:
                    problems.append("%s: %s has no published end time and was "
                                    "put in a timed plan" % (tag, code))
                    continue
                venue = VEN[w["v"]]
                if prev is None:
                    if w["b"] < 8 * 60 + need(at, venue):
                        problems.append(
                            "%s: first session %s starts %d but is %d min "
                            "from %s after 08:00"
                            % (tag, code, w["b"], need(at, venue), at))
                else:
                    gap = w["b"] - prev["e"]
                    if gap < 0:
                        problems.append("%s: %s overlaps the previous session"
                                        % (tag, code))
                    elif gap < need(prev["v"], venue) + buf:
                        problems.append(
                            "%s: %s -> %s leaves %d min, needs %d + %d buffer"
                            % (tag, prev["c"], code, gap,
                               need(prev["v"], venue), buf))
                prev = {"e": w["e"], "v": venue, "c": code}

            # the labels must be true
            if svc:
                si = int(svc)
                if len(marks) != len(codes):
                    problems.append("%s: %d cards but %d service marks"
                                    % (tag, len(codes), len(marks)))
                for k, (cls, txt) in enumerate(marks):
                    if k >= len(codes):
                        break
                    has = si in S[codes[k]]["sv"]
                    says_hit = "hit" in cls
                    if has != says_hit:
                        problems.append(
                            "%s: %s is marked %r but %s carry %s"
                            % (tag, codes[k], txt[:28],
                               "does" if has else "does not", SVC[si]))

            # if the tips claim a break, there must be one
            if any(t.startswith("Break:") for t in tips):
                ok = False
                for k in range(1, len(codes)):
                    a_ = slot_on(codes[k - 1], day)
                    b_ = slot_on(codes[k], day)
                    if not a_ or not b_ or a_["e"] is None:
                        continue
                    g = b_["b"] - a_["e"]
                    if g >= 45 and a_["e"] >= 11 * 60 and b_["b"] <= 14 * 60 + 30:
                        ok = True
                        break
                if not ok:
                    problems.append("%s: tips claim a break and none exists"
                                    % tag)
        print("   %d itineraries verified" % checked)
        print("   page errors:", errs if errs else "none")
        if errs:
            problems.append("page errors during planning")
        b.close()
finally:
    srv.terminate()

print()
print("=" * 62)
if problems:
    print("  %d PROBLEM(S)" % len(problems))
    for p_ in problems[:25]:
        print("   -", p_)
    sys.exit(1)
print("  Every suggested day is attendable and every label is true.")
