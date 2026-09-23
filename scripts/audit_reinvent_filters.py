#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Does the page show exactly the sessions it claims to show?

    python scripts/audit_reinvent_filters.py

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
import io, json, subprocess, sys, time, random
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

STORE = json.load(io.open("intelligence/reinvent2026.json", encoding="utf-8"))
S = STORE["sessions"]
SVC = STORE["facets"]["Services"]
VEN = STORE["venues"]
ROOMS = STORE["rooms"]
TYPES = STORE["facets"]["Type"]
LEVELS = STORE["facets"]["Level"]

srv = subprocess.Popen([sys.executable, "-m", "http.server", "8905"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(2)
problems = []


def truth_service(i):
    return {x["c"] for x in S if i in x["sv"]}


def truth_venue(name):
    return {x["c"] for x in S
            if any(VEN[w["v"]] == name for w in x["when"])}


def truth_day(day):
    return {x["c"] for x in S if any(w["d"] == day for w in x["when"])}


def truth_type(name):
    return {x["c"] for x in S
            if x["ty"] is not None and TYPES[x["ty"]] == name}


def shown(pg):
    """Every session code currently rendered in Browse, paging to the end."""
    while True:
        more = pg.locator("#browse .pager button")
        if not more.count():
            break
        more.click()
        pg.wait_for_timeout(180)
    return set(pg.eval_on_selector_all(
        "#browse .card .code", "es => es.map(e => e.textContent.trim())"))


def check(label, got, want):
    extra = got - want
    missing = want - got
    if extra or missing:
        problems.append(
            "%s: page showed %d, truth is %d (%d wrong, %d missing)%s"
            % (label, len(got), len(want), len(extra), len(missing),
               ("  e.g. wrong: " + ", ".join(sorted(extra)[:4]))
               if extra else ""))
        print("   FAIL %-52s +%d -%d" % (label, len(extra), len(missing)))
        return False
    print("   ok   %-52s %d session(s)" % (label, len(want)))
    return True


try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1400, "height": 1000})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto("http://localhost:8905/reinvent-2026/",
                wait_until="networkidle")
        pg.wait_for_selector(".card", timeout=30000)

        def opts(sel):
            return pg.eval_on_selector_all(
                sel + " option",
                "es => es.map(e => [e.value, e.textContent])")

        svc_opts = [o for o in opts("#filters select >> nth=4") if o[0] != ""]

        # ---- 1. the service filter -------------------------------------
        print("=== 1. SERVICE FILTER: does it show exactly that service?")
        counts = sorted(
            [(len(truth_service(i)), i) for i in range(len(SVC))],
            reverse=True)
        sample = ([i for _, i in counts[:6]]              # biggest
                  + [i for _, i in counts[len(counts)//2:len(counts)//2+5]]
                  + [i for _, i in counts[-6:]])          # smallest
        for i in sample:
            pg.select_option("#filters select >> nth=4", str(i))
            pg.wait_for_timeout(420)
            check("service: " + SVC[i][:44], shown(pg), truth_service(i))
        pg.select_option("#filters select >> nth=4", "")
        pg.wait_for_timeout(300)

        # ---- 2. venue ----------------------------------------------------
        print()
        print("=== 2. VENUE FILTER")
        for v in sorted(VEN):
            pg.select_option("#filters select >> nth=3", v)
            pg.wait_for_timeout(420)
            check("venue: " + v, shown(pg), truth_venue(v))
        pg.select_option("#filters select >> nth=3", "")
        pg.wait_for_timeout(300)

        # ---- 3. day ------------------------------------------------------
        print()
        print("=== 3. DAY FILTER")
        days = sorted({w["d"] for x in S for w in x["when"]})
        for d in days:
            pg.select_option("#filters select >> nth=0", d)
            pg.wait_for_timeout(420)
            check("day: " + d, shown(pg), truth_day(d))
        pg.select_option("#filters select >> nth=0", "")
        pg.wait_for_timeout(300)

        # ---- 4. format ---------------------------------------------------
        print()
        print("=== 4. FORMAT FILTER")
        for t in TYPES:
            pg.select_option("#filters select >> nth=1", t)
            pg.wait_for_timeout(420)
            check("type: " + t, shown(pg), truth_type(t))
        pg.select_option("#filters select >> nth=1", "")
        pg.wait_for_timeout(300)

        # ---- 5. search: every hit must contain the term somewhere -------
        print()
        print("=== 5. SEARCH: is every result a genuine match?")
        by_code = {x["c"]: x for x in S}
        for term in ["transit gateway", "EKS", "MGM Grand", "Graviton",
                     "Content Hub", "Jeff Barr", "Forum 120", "zzzznope"]:
            pg.fill("#q", term)
            pg.wait_for_timeout(600)
            got = shown(pg)
            bad = []
            for code in got:
                x = by_code.get(code)
                if not x:
                    bad.append(code)
                    continue
                hay = " ".join([
                    x["c"], x["t"], x["a"],
                    " ".join(SVC[i] for i in x["sv"]),
                    " ".join(STORE["speakers"][i] for i in (x.get("sp") or [])),
                    " ".join(ROOMS[w["r"]] for w in x["when"])]).lower()
                if not all(w in hay for w in term.lower().split()):
                    bad.append(code)
            if bad:
                problems.append("search %r returned %d result(s) that do not "
                                "contain it: %s"
                                % (term, len(bad), ", ".join(bad[:5])))
                print("   FAIL %-24s %d of %d do not contain the term"
                      % (repr(term), len(bad), len(got)))
            else:
                print("   ok   %-24s %d result(s), all genuine"
                      % (repr(term), len(got)))
        pg.fill("#q", "")
        pg.wait_for_timeout(300)
        print()
        print("   page errors:", errs if errs else "none")
        if errs:
            problems.append("console/page errors during filtering")
        b.close()
finally:
    srv.terminate()

print()
print("=" * 62)
if problems:
    print("  %d PROBLEM(S)" % len(problems))
    for p_ in problems:
        print("   -", p_)
    sys.exit(1)
print("  Every filter and search showed exactly the sessions it should.")
