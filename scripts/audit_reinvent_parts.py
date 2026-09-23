#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The map, the Now split, the announcement join and the calendar.

    python scripts/audit_reinvent_parts.py

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
import io, json, re, subprocess, sys, time, datetime
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

STORE = json.load(io.open("intelligence/reinvent2026.json", encoding="utf-8"))
S = {x["c"]: x for x in STORE["sessions"]}
SVC = STORE["facets"]["Services"]
VEN = STORE["venues"]
ROOMS = STORE["rooms"]

srv = subprocess.Popen([sys.executable, "-m", "http.server", "8909"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(2)
problems = []

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1400, "height": 1100})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto("http://localhost:8909/reinvent-2026/", wait_until="networkidle")
        pg.wait_for_selector(".card", state="attached", timeout=30000)
        CFG = pg.evaluate("window.RI_CONFIG")
        MAT, OVER = CFG["travel"]["matrix"], CFG["travel"]["overhead"]
        DET, PX = CFG["travel"]["detour"], CFG["travel"]["pace"]

        def need(a, b):
            if a == b:
                return OVER
            c = MAT.get(a, {}).get(b)
            return OVER + int(round(c["m"] * DET / PX)) if c else OVER

        # ---- 1. map heat numbers ---------------------------------------
        print("=== 1. MAP: are the per-venue numbers right?")
        pg.evaluate("document.getElementById('tab-map').click()")
        pg.wait_for_timeout(2600)
        nums = pg.eval_on_selector_all(
            ".rimap .pin", """es => es.map(g => [
              g.querySelector('.vname').textContent,
              g.querySelector('.vnum').textContent])""")
        for venue, shown in nums:
            want = len({x["c"] for x in STORE["sessions"]
                        if any(VEN[w["v"]] == venue for w in x["when"])})
            ok = int(shown) == want
            print("   %-4s %-16s page %-5s truth %d"
                  % ("ok" if ok else "FAIL", venue, shown, want))
            if not ok:
                problems.append("map: %s shows %s, truth %d"
                                % (venue, shown, want))

        # with a lane applied the heat must follow it
        pg.evaluate("document.getElementById('tab-browse').click()")
        pg.click('[data-lane="connectivity"]')
        pg.wait_for_timeout(500)
        pg.evaluate("document.getElementById('tab-map').click()")
        pg.wait_for_timeout(2200)
        lane_ids = set(CFG["lanes"][0]["services"])
        nums2 = pg.eval_on_selector_all(
            ".rimap .pin", """es => es.map(g => [
              g.querySelector('.vname').textContent,
              g.querySelector('.vnum').textContent])""")
        for venue, shown in nums2:
            want = len({x["c"] for x in STORE["sessions"]
                        if lane_ids & set(x["sv"])
                        and any(VEN[w["v"]] == venue for w in x["when"])})
            ok = int(shown) == want
            print("   %-4s %-16s connectivity lane: page %-4s truth %d"
                  % ("ok" if ok else "FAIL", venue, shown, want))
            if not ok:
                problems.append("map lane: %s shows %s, truth %d"
                                % (venue, shown, want))
        pg.evaluate("document.getElementById('tab-browse').click()")
        pg.click('[data-lane="all"]')
        pg.wait_for_timeout(400)

        # ---- 2. Now view -----------------------------------------------
        print()
        print("=== 2. NOW: is the reachable/unreachable split correct?")
        pg.evaluate("document.getElementById('tab-now').click()")
        pg.wait_for_timeout(800)
        pg.select_option("#now-day", "2026-12-02")
        pg.eval_on_selector("#now-time",
                            "e => { e.value='12:45'; "
                            "e.dispatchEvent(new Event('change')); }")
        pg.select_option("#now-at", "MGM Grand")
        pg.wait_for_timeout(1200)
        groups = pg.eval_on_selector_all(
            "#nowbody .daygroup", """es => es.map(g => [
              g.querySelector('.dayhead').textContent,
              Array.from(g.querySelectorAll('.card .code'))
                   .map(e => e.textContent.trim())])""")
        here, now_min, WINDOW = "MGM Grand", 12 * 60 + 45, 90
        for head, codes in groups:
            reach_group = head.lower().startswith("reachable")
            for code in codes:
                x = S.get(code)
                w = next((w for w in x["when"] if w["d"] == "2026-12-02"), None)
                if not w:
                    problems.append("now: %s is not on that day" % code)
                    continue
                mins = w["b"] - now_min
                if mins < -5 or mins > WINDOW:
                    problems.append("now: %s starts %+d min, outside the "
                                    "window" % (code, mins))
                reachable = mins >= need(here, VEN[w["v"]])
                if reachable != reach_group:
                    problems.append(
                        "now: %s in %r but %s reachable (%d min, needs %d)"
                        % (code, head, "is" if reachable else "is not",
                           mins, need(here, VEN[w["v"]])))
            print("   %-22s %d card(s) checked" % (head, len(codes)))

        # ---- 3. announcements ------------------------------------------
        print()
        print("=== 3. JUST ANNOUNCED: do the linked sessions carry it?")
        pg.evaluate("document.getElementById('tab-news').click()")
        pg.wait_for_timeout(900)
        items = pg.eval_on_selector_all(
            ".newsitem", """es => es.map(n => [
              Array.from(n.querySelectorAll('.top .tag')).map(t=>t.textContent),
              Array.from(n.querySelectorAll('.where a.code')).map(a=>a.textContent)])""")
        bad = 0
        for tags, codes in items:
            want = {SVC.index(t) for t in tags if t in SVC}
            for code in codes:
                x = S.get(code)
                if not x or not (want & set(x["sv"])):
                    bad += 1
                    problems.append("news: %s linked under %s but does not "
                                    "carry it" % (code, ", ".join(tags)[:30]))
        print("   %d announcement(s), %d linked session(s), %d wrong"
              % (len(items), sum(len(c) for _, c in items), bad))

        # ---- 4. .ics times ---------------------------------------------
        print()
        print("=== 4. CALENDAR: do exported times match the store?")
        pg.goto("http://localhost:8909/reinvent-2026/"
                "#plan=NET305,CMP202,BIZ318", wait_until="networkidle")
        pg.wait_for_selector("#plan .card", timeout=25000)
        with pg.expect_download() as dl:
            pg.click("#ics")
        ics = io.open(dl.value.path(), encoding="utf-8", newline="").read()
        for m in re.finditer(
                r"UID:([A-Z0-9-]+)-(\d{4}-\d{2}-\d{2})@[^\r]*\r\n"
                r"DTSTAMP:[^\r]*\r\nDTSTART:(\S+)\r\nDTEND:(\S+)", ics):
            code, day, st, en = m.groups()
            w = next((w for w in S[code]["when"] if w["d"] == day), None)
            utc = datetime.datetime.strptime(st, "%Y%m%dT%H%M%SZ")
            local = utc - datetime.timedelta(hours=8)
            want = datetime.datetime.strptime(day, "%Y-%m-%d") \
                 + datetime.timedelta(minutes=w["b"])
            ok = local == want
            print("   %-4s %-9s %s local -> %s UTC"
                  % ("ok" if ok else "FAIL", code,
                     local.strftime("%H:%M"), utc.strftime("%H:%M")))
            if not ok:
                problems.append("ics: %s exported %s, store says %s"
                                % (code, local, want))
        print()
        print("   page errors:", errs if errs else "none")
        if errs:
            problems.append("page errors during the sweep")
        b.close()
finally:
    srv.terminate()

print()
print("=" * 62)
if problems:
    print("  %d PROBLEM(S)" % len(problems))
    for p_ in problems[:20]:
        print("   -", p_)
    sys.exit(1)
print("  Map counts, the Now split, the announcement join and the calendar")
print("  export all agree with the store.")
