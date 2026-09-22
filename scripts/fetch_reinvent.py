#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The re:Invent 2026 session catalog, from AWS's own catalog API.

    python scripts/fetch_reinvent.py             # fetch, slim, write the store
    python scripts/fetch_reinvent.py --audit     # probe and report, write nothing
    python scripts/fetch_reinvent.py --raw FILE  # re-slim a saved raw payload

Why this exists
---------------
Asked for as: "we are going to AWS re:Invent 2026 at Vegas, Nov 30 to Dec 4.
I want a unified web page I can share with my team -- connectivity, platform,
and the managed-AWS folks who run compute. They should be able to search for a
specific service, and the sessions are across multiple venues within Vegas,
MGM Grand and all those. Some creative way that adds value during the event."

The page that already existed said "Open catalog" six times. Everything it
offered, catalog.awsevents.com does better, so it added nothing a bookmark
would not. A page worth sharing with a team has to hold the data.

WHERE THE DATA COMES FROM. The public catalog is a RainFocus app. Its
browser calls POST https://catalog.awsevents.com/api/sessions with a form
body, and it will not answer without two headers -- `rfapiprofileid` and
`rfwidgetid` -- which are minted into the page at load. There is no
documented way to obtain them offline, so this loads the catalog once in a
headless browser, watches for the request the app makes anyway, and lifts
the pair from it. After that it is plain HTTP with `from=N` pagination.

That is a reverse-engineered endpoint, not a supported API, and it is
treated as one: nothing here retries hard, the page records the date it was
captured, and every session keeps its `code` so a reader can find it in the
official catalog and confirm. If AWS changes the shape, --audit says so
rather than this silently writing a thinner file.

THE FIRST PAGE IS SHAPED DIFFERENTLY FROM THE REST. At `from=0` the items
arrive under `sectionList[0].items`; at `from>0` they arrive under `items`.
Reading only one of those loses either the first 50 sessions or all the
others, and in both cases the result is a plausible-looking file. Both are
read, and the total is reconciled against the API's own `totalSearchItems`.

WHAT IS KEPT, AND WHY IT IS INTERNED. Facet values repeat across 1,500+
sessions -- "Breakout session" alone appears hundreds of times -- so every
facet is written once into a table and referenced by index. The store is
substantially smaller that way, which matters for a page people will open
on conference wifi.

`room` is kept in full ("Caesars Palace | Promenade Level | Roman I")
because the part before the first pipe is the property, and the gap between
two properties is the thing the official catalog will not compute for you.

A REFRESH MUST NOT BE ABLE TO MAKE THE PAGE WORSE. This runs unattended on
a schedule, so the dangerous case is not a crash -- a crash is loud and
commits nothing. The dangerous case is a run that succeeds and writes a
thinner, staler or emptier catalog over a good one, because that publishes
silently and looks exactly like a normal day.

So a refresh that would shrink the catalog by more than MAX_SHRINK is
refused rather than written. AWS does cancel sessions, and the catalog does
grow and shrink a little; what it does not do is lose a fifth of itself
overnight. A drop that large means a partial fetch or a changed response
shape, and the right response is to keep yesterday's good data and say so
loudly. --force exists for the day the drop is real.

Every run also reports what changed -- added, removed, retimed, moved --
because "the job ran" is not the same claim as "the data is current", and
only the second one matters to somebody planning a week around it.
"""
import argparse
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "intelligence", "reinvent2026.json")

CATALOG = "https://catalog.awsevents.com/api/sessions"
PORTAL = ("https://registration.awsevents.com/flow/awsevents/reinvent2026"
          "/eventcatalog/page/eventcatalog")

# The facets worth carrying. The catalog publishes more; these are the ones
# the page actually filters on, and an unused facet is weight on a phone.
KEEP_FACETS = ("Type", "Level", "Role", "Services", "Topic",
               "Area of Interest", "Industry")

# Short keys in the store, one per facet. Written down rather than derived
# so that renaming a facet cannot silently change the on-disk schema.
FACET_KEY = {
    "Type": "ty", "Level": "lv", "Role": "ro", "Services": "sv",
    "Topic": "tp", "Area of Interest": "ai", "Industry": "in",
}
# These carry exactly one value per session, so they are stored as a bare
# index rather than a one-element list.
SINGULAR = ("Type", "Level")

PAGE = 50            # the app's own page size; larger is not honoured

# A refresh may not shrink the catalog by more than this without --force.
# Set from the shape of the thing being measured: sessions get cancelled in
# ones and twos, not in hundreds, so anything past a fifth is a fetch fault
# rather than news about the conference.
MAX_SHRINK = 0.20

# The kinds of change a refresh can produce, in the order a reader cares
# about them: things that break a plan first, things that enable one last.
ORDER = ("removed", "unscheduled", "moved", "retimed", "scheduled", "added")
LABEL = {"added": "added", "removed": "removed", "moved": "moved venue",
         "retimed": "retimed", "scheduled": "newly scheduled",
         "unscheduled": "lost their slot"}
EVENT_DAYS = ("2026-11-30", "2026-12-01", "2026-12-02",
              "2026-12-03", "2026-12-04")


# ---------------------------------------------------------------- transport

def credentials():
    """Lift the two required headers from the catalog app's own first call.

    Playwright is a heavy dependency for two strings, and it is used because
    the alternative is hardcoding values that rotate. If it is not installed
    the error says exactly that rather than failing somewhere downstream.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit(
            "  playwright is needed to mint the catalog headers:\n"
            "      pip install playwright && playwright install chromium\n"
            "  or pass --raw with a payload captured earlier.")

    got = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        def on_request(req):
            if "catalog.awsevents.com/api/sessions" in req.url and not got:
                h = req.all_headers()
                for k in ("rfapiprofileid", "rfwidgetid"):
                    if k in h:
                        got[k] = h[k]

        page.on("request", on_request)
        page.goto(PORTAL, wait_until="networkidle", timeout=90000)
        page.wait_for_timeout(6000)
        browser.close()

    if len(got) < 2:
        raise SystemExit(
            "  the catalog page loaded but never made the API call this reads "
            "its headers from.\n  AWS has probably changed the app; nothing "
            "was written.")
    return got


def post(headers, extra=None):
    body = {"type": "session", "browserTimezone": "America/Chicago",
            "catalogDisplay": "list"}
    body.update(extra or {})
    merged = dict(headers)
    merged.update({
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "https://registration.awsevents.com",
        "Referer": "https://registration.awsevents.com/",
    })
    req = urllib.request.Request(
        CATALOG, data=urllib.parse.urlencode(body).encode(), headers=merged)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def items_of(payload):
    """Both response shapes, because the first page differs from the rest."""
    if payload.get("items"):
        return payload["items"]
    sections = payload.get("sectionList") or []
    return (sections[0].get("items") or []) if sections else []


def fetch_all():
    """Every session, reconciled against the API's own total.

    Returns the credentials it minted as well, so the store can carry them
    and the page can make its own live call. Measured 2026-09-22: they are
    identical across independent browser sessions, and the catalog reflects
    any Origin back in Access-Control-Allow-Origin -- so a browser on
    jayanthkatta.com can call it directly, and a real one did, returning all
    1,582 sessions.

    These are NOT secrets. AWS hands the same two strings to every browser
    that loads the public catalog page; they identify the widget, not a
    user, and nothing here authenticates as anybody. They are recorded so
    the daily job keeps them current on its own: if AWS rotates them, the
    next run picks up the new pair and the page keeps working.
    """
    head = credentials()
    first = post(head)
    total = int(first.get("totalSearchItems") or 0)
    out = list(items_of(first))
    if not out:
        raise SystemExit("  the catalog answered with no sessions at all -- "
                         "the response shape has changed. Nothing written.")

    print("  catalog reports %d session(s)" % total)
    frm = PAGE
    while frm < total:
        got = items_of(post(head, {"from": frm}))
        if not got:
            print("  page at from=%d came back empty; stopping early" % frm)
            break
        out += got
        frm += PAGE
        time.sleep(0.25)

    print("  fetched %d of %d" % (len(out), total))
    if total and len(out) < total:
        print("  SHORT by %d -- the store will be incomplete"
              % (total - len(out)))
    return out, total, head


# ------------------------------------------------------------------ slimming

def facets_of(session):
    """{facet name: [values]} straight off the session record."""
    out = {}
    for av in (session.get("attributevalues") or []):
        name, value = av.get("attribute"), av.get("value")
        if name in KEEP_FACETS and value:
            bucket = out.setdefault(name, [])
            if value not in bucket:
                bucket.append(value)
    return out


def venue_of(room):
    """The property, which is everything before the first pipe.

    "Caesars Palace | Promenade Level | Roman I" -> "Caesars Palace".
    A room with no pipe is its own venue; that happens for a handful of
    off-property and virtual entries and is not an error.
    """
    return (room or "").split("|")[0].strip()


class Table(object):
    """Intern a repeated string to an index, preserving first-seen order."""

    def __init__(self):
        self.seen, self.list = {}, []

    def __call__(self, value):
        if value not in self.seen:
            self.seen[value] = len(self.list)
            self.list.append(value)
        return self.seen[value]


def speakers_of(session):
    """[(name, company, title)] for a session, in the order AWS lists them."""
    out = []
    for p in (session.get("participants") or []):
        name = (p.get("fullName")
                or ((p.get("firstName") or "") + " "
                    + (p.get("lastName") or ""))).strip()
        if not name:
            continue
        out.append((name,
                    (p.get("companyName") or "").strip(),
                    (p.get("jobTitle") or "").strip()))
    return out


def slim(sessions):
    facet_tables = {name: Table() for name in KEEP_FACETS}
    venues, rooms = Table(), Table()
    # 2,007 distinct people across 1,154 sessions, so the same principal
    # engineer appears on several. Interned like the facets, and stored as
    # one joined string rather than three fields: the page searches it and
    # prints it, and never needs the parts separately.
    people = Table()
    out, unscheduled = [], 0
    no_end = [0]

    for s in sessions:
        if s.get("testRecord") or not s.get("published"):
            continue

        f = facets_of(s)
        slots = []
        for t in (s.get("times") or []):
            room = t.get("room") or ""
            start, end = t.get("startTimeMin"), t.get("endTimeMin")
            if start is None or end is None:
                continue
            start, end = int(start), int(end)
            # A handful of sponsored sessions are published with the end
            # equal to the start and no length at all -- AWS simply has not
            # said how long they run. Carrying that through as a real end
            # time would be worse than useless here: the next session's gap
            # would be measured from a moment this one has not finished, so
            # the page would under-warn precisely where it claims to help.
            # Unknown is recorded as unknown, and the page says so.
            if end <= start:
                end = None
                no_end[0] += 1
            slots.append({
                "d": t.get("date") or "",
                "b": start,
                "e": end,
                "v": venues(venue_of(room)),
                "r": rooms(room),
                "cap": int(t["capacity"]) if str(
                    t.get("capacity") or "").isdigit() else None,
            })
        if not slots:
            unscheduled += 1

        rec = {
            "c": s.get("code") or "",
            "t": (s.get("title") or "").strip(),
            "a": re.sub(r"\s+", " ", s.get("abstract") or "").strip(),
            "len": int(s["length"]) if s.get("length") else None,
            "when": slots,
            "sp": [people(" · ".join(x for x in who if x))
                   for who in speakers_of(s)],
        }
        for name in KEEP_FACETS:
            idx = [facet_tables[name](v) for v in (f.get(name) or [])]
            if name in SINGULAR:
                rec[FACET_KEY[name]] = idx[0] if idx else None
            else:
                rec[FACET_KEY[name]] = idx
        out.append(rec)

    return {
        "sessions": out,
        "facets": {n: facet_tables[n].list for n in KEEP_FACETS},
        "facet_keys": dict(FACET_KEY),
        "venues": venues.list,
        "rooms": rooms.list,
        "speakers": people.list,
        "unscheduled": unscheduled,
        "no_end": no_end[0],
    }


# --------------------------------------------------- what changed, and is it sane

def previous():
    """The store as it stands, or None on the very first run."""
    if not os.path.exists(OUT):
        return None
    try:
        return json.load(io.open(OUT, encoding="utf-8"))
    except (ValueError, OSError):
        return None


def slot_key(store, w):
    """A slot as a reader would recognise it: when, and where."""
    return (w["d"], w["b"], w["e"], store["venues"][w["v"]],
            store["rooms"][w["r"]])


def compare(old, new):
    """What a person planning a week would notice between two captures.

    Counts, not just a diff, because the question this answers is "is the
    page still telling the truth", and the answers that matter are: did
    sessions vanish, and did any of them move. A session that moved room
    or time is the one that quietly invalidates somebody's plan.
    """
    if not old:
        return None
    was = {s["c"]: s for s in old["sessions"]}
    now = {s["c"]: s for s in new["sessions"]}

    added = sorted(set(now) - set(was))
    removed = sorted(set(was) - set(now))
    scheduled, pulled, moved, retimed = [], [], [], []
    for code in sorted(set(was) & set(now)):
        a = [slot_key(old, w) for w in was[code]["when"]]
        b = [slot_key(new, w) for w in now[code]["when"]]
        if a == b:
            continue
        # Getting a room for the first time is not the same event as being
        # moved, and calling it one is a small lie in a commit message that
        # is supposed to be the trustworthy part. Measured on 2026-09-22:
        # six SNR sessions went from no time at all to the Venetian Theatre
        # inside two hours, and were reported as "moved venue".
        if not a:
            scheduled.append(code)
        elif not b:
            pulled.append(code)
        elif {k[3] for k in a} != {k[3] for k in b}:
            moved.append(code)
        else:
            retimed.append(code)
    return {"added": added, "removed": removed, "scheduled": scheduled,
            "unscheduled": pulled, "moved": moved, "retimed": retimed}


def report_change(delta):
    if delta is None:
        print("  first capture -- nothing to compare against")
        return
    if not any(delta.values()):
        print("  no change since the last capture")
        return
    print("  since the last capture: %s"
          % ", ".join("%d %s" % (len(delta[k]), LABEL[k])
                      for k in ORDER if delta[k]))
    for label in ("removed", "unscheduled", "moved", "retimed", "scheduled"):
        if delta[label]:
            shown = ", ".join(delta[label][:10])
            more = "" if len(delta[label]) <= 10 else ", ..."
            print("    %-8s %s%s" % (label, shown, more))


def refuse_if_shrunk(old, new, force):
    """Keep good data rather than overwrite it with a suspicious fetch."""
    if not old:
        return
    before, after = len(old["sessions"]), len(new["sessions"])
    if before == 0 or after >= before * (1 - MAX_SHRINK):
        return
    lost = before - after
    if force:
        print("  --force: writing anyway, though the catalog lost %d of %d "
              "session(s)" % (lost, before))
        return
    raise SystemExit(
        "\n".join((
            "  REFUSING TO WRITE. The catalog held %d session(s) and this "
            "fetch returned %d -- %d fewer, a %.0f%% drop."
            % (before, after, lost, 100.0 * lost / before),
            "  Sessions get cancelled in ones and twos, not in hundreds, so "
            "this is far more likely a partial fetch or a",
            "  changed response shape than news about the conference. The "
            "existing store is left untouched, and the page",
            "  keeps serving data that was known good.",
            "  Re-run to see whether it was transient. If the drop is real, "
            "pass --force.")))


# -------------------------------------------------------------------- audit

def audit(sessions):
    """What the catalog actually contains, so a thin file is visible."""
    data = slim(sessions)
    S = data["sessions"]
    print()
    print("  %d published session(s), %d with no time yet"
          % (len(S), data["unscheduled"]))
    if data["no_end"]:
        print("  %d slot(s) carry a start but no published duration; their "
              "end is recorded as unknown" % data["no_end"])
    print()
    for name in KEEP_FACETS:
        print("  %-18s %d distinct value(s)"
              % (name, len(data["facets"][name])))
    print("  %-18s %d distinct, on %d session(s)"
          % ("Speakers", len(data["speakers"]),
             sum(1 for x in S if x["sp"])))
    print()
    counts = {}
    for s in S:
        for w in s["when"]:
            name = data["venues"][w["v"]]
            counts[name] = counts.get(name, 0) + 1
    print("  venues (%d):" % len(data["venues"]))
    for v, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print("    %-26s %4d slot(s)" % (v[:26], n))
    print()
    print("  days:")
    per_day = {}
    for s in S:
        for w in s["when"]:
            per_day[w["d"]] = per_day.get(w["d"], 0) + 1
    for d in sorted(per_day):
        flag = "" if d in EVENT_DAYS else "   <- outside the announced dates"
        print("    %s  %4d slot(s)%s" % (d, per_day[d], flag))
    return data


# --------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", action="store_true",
                    help="probe and report, write nothing")
    ap.add_argument("--raw", metavar="FILE",
                    help="re-slim a previously saved raw payload")
    ap.add_argument("--save-raw", metavar="FILE",
                    help="also write the unslimmed payload here")
    ap.add_argument("--force", action="store_true",
                    help="write even if the catalog shrank past the guard")
    args = ap.parse_args()

    if args.raw:
        blob = json.load(io.open(args.raw, encoding="utf-8"))
        sessions = blob["sessions"] if isinstance(blob, dict) else blob
        total = len(sessions)
        head = None
        print("  re-slimming %d session(s) from %s" % (total, args.raw))
    else:
        sessions, total, head = fetch_all()
        if args.save_raw:
            with io.open(args.save_raw, "w", encoding="utf-8") as fh:
                json.dump({"sessions": sessions}, fh, ensure_ascii=False)

    data = audit(sessions) if args.audit else slim(sessions)

    if args.audit:
        print()
        print("  --audit: nothing written")
        return 0

    payload = dict(data)
    # Date and full timestamp both. The date is what the page shows a
    # reader; the timestamp is what a freshness check measures, and a
    # date alone cannot distinguish this morning from this time last week.
    payload["captured"] = time.strftime("%Y-%m-%d", time.gmtime())
    payload["captured_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                            time.gmtime())
    payload["source"] = CATALOG
    payload["catalog_total"] = total

    old = previous()
    # The page uses this to ask the catalog, on load, whether anything has
    # changed since this capture. Carried forward on a --raw re-slim so
    # re-processing an old payload does not strip the page's live check.
    if head:
        payload["api"] = {"url": CATALOG, "headers": head}
    elif old and old.get("api"):
        payload["api"] = old["api"]
    refuse_if_shrunk(old, payload, args.force)
    delta = compare(old, payload)
    print()
    report_change(delta)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
    print()
    print("  wrote %s  (%.2f MB, %d sessions, captured %s)"
          % (os.path.relpath(OUT, ROOT), os.path.getsize(OUT) / 1e6,
             len(payload["sessions"]), payload["captured_utc"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
