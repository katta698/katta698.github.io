#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render intelligence/status/ from the fetched status data.

    python scripts/build_status_page.py

Everything on this page has to survive the question "how do you know?".
--------------------------------------------------------------------
So three rules run through it:

1. Every figure names its source and when that source was read. A status page
   that looks live but is six hours stale is worse than one that admits its
   age, because a reader will act on it.

2. "Could not check" is never rendered as "operational". An unreachable feed
   and a healthy cloud both produce an empty incident list, and collapsing
   them turns a monitoring failure into false reassurance.

3. A statistic states its sample size. The acknowledgement median currently
   rests on six incidents; presenting "209 minutes" without "from 6" would
   dress an anecdote up as a measurement.
"""
import datetime
import datetime as _dt
import html
import io
import json
import os
import re

import region_map  # noqa: E402

from feedback_star import star_html  # noqa: E402
from back_to_top import TOP_HTML, TOP_JS, SRC_HTML  # noqa: E402

import statistics
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STATUS = os.path.join(ROOT, "intelligence", "status.json")
HISTORY = os.path.join(ROOT, "intelligence", "status-history.json")
RUNS = os.path.join(ROOT, "intelligence", "status-runs.json")
OUT_DIR = os.path.join(ROOT, "intelligence", "status")

e = html.escape
LABEL = {"aws": "AWS", "azure": "Azure", "gcp": "Google Cloud"}
ORDER = ["aws", "azure", "gcp"]

# The human-readable status page for each cloud, which is NOT the endpoint the
# data is read from. Making the endpoint itself a link sent readers to raw JSON
# and raw XML -- correct provenance, useless destination. The endpoint stays on
# the page as text because it IS the claim; the link goes somewhere a person
# can read.
HUMAN = {
    "aws":   "https://health.aws.amazon.com/health/status",
    "azure": "https://azure.status.microsoft/en-us/status",
    "gcp":   "https://status.cloud.google.com/",
}

# How old the data may be before the page says so out loud. The workflow runs
# every 15 minutes, so anything past an hour means several runs have failed
# and the reader should not trust the green ticks.
# Two and a half missed hourly runs. This was 60, calibrated for a
# 15-minute cron that turned out never to fire at all -- on an hourly
# schedule 60 minutes is one ordinary interval, so the page would have
# announced itself stale almost permanently. A staleness warning that is
# always on is a warning a reader learns to ignore, which costs more than
# not having one.
STALE_MINUTES = 150


def t(s):
    """Parse a timestamp, always in UTC.

    A bare date -- "2024-03-15", which is what Google's product history gives
    -- parses to a NAIVE datetime, and subtracting one of those from an
    aware one raises. That surfaced the moment 794 date-only incidents
    arrived: the build died, and because the failure came before the summary
    line, a tail of the output still looked like a successful run.

    Everything else here is UTC, so a naive value is assumed to be UTC rather
    than rejected. The alternative -- dropping date-only incidents -- would
    discard the entire Google archive to avoid an assumption that is true of
    every source feeding this page.
    """
    try:
        d = datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:                                          # noqa: BLE001
        return None
    return d if d.tzinfo else d.replace(tzinfo=datetime.timezone.utc)


def since(dt):
    if not dt:
        return "?"
    secs = (datetime.datetime.now(datetime.timezone.utc) - dt).total_seconds()
    if secs < 90:
        return "just now"
    mins = secs / 60
    if mins < 90:
        return "%d min ago" % mins
    hours = mins / 60
    if hours < 36:
        return "%d hours ago" % hours
    return "%d days ago" % (hours / 24)


def dur(hours):
    """Hours as something a person reads.

    4597 hours is technically correct and unreadable; the AWS Middle East
    incidents have been open since March, and "191 days" is the fact a reader
    can actually use.
    """
    if hours is None:
        return "?"
    if hours < 1:
        return "%d min" % round(hours * 60)
    if hours < 48:
        return "%dh %dm" % (int(hours), round((hours % 1) * 60))
    return "%d days" % round(hours / 24)


def aws_begin(v):
    """AWS gives a unix timestamp; the other two give ISO 8601."""
    try:
        return datetime.datetime.fromtimestamp(int(v), datetime.timezone.utc)
    except Exception:                                          # noqa: BLE001
        return t(v)


def track_record(history):
    """Acknowledgement and resolution timings, Google only, and say why.

    AWS's `date` field IS its first announcement, so the gap between incident
    start and first word is structurally zero -- ranking AWS best precisely
    because it discloses less. Azure's feed carries no start time at all.
    Publishing a three-way comparison from that would be actively misleading,
    so only the cloud that provides the inputs is measured.
    """
    rows = [i for i in history.values() if i.get("cloud") == "gcp"]
    acks, durs = [], []
    for i in rows:
        b, f, end = t(i.get("begin")), t(i.get("first_update")), t(i.get("end"))
        if b and f:
            acks.append((f - b).total_seconds() / 60)
        if b and end:
            durs.append((end - b).total_seconds() / 3600)
    return {
        "n": len(rows),
        "acks": sorted(acks),
        "durs": sorted(durs),
        "ack_median": statistics.median(acks) if acks else None,
        "dur_median": statistics.median(durs) if durs else None,
    }



MONTH_ABBR = ("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec").split()

WHYUNK = {
    "aws": "Outside the window AWS's service history reaches.",
    "azure": "Outside the window Azure's status history reaches.",
    "gcp": "Outside the window Google's feed still carries.",
}


_INC_KEYS = {}
_INC_DATA = []


def inc_key(inc):
    """A stable index for one incident, so a cell can name it in the DOM.

    Keyed on id() because the same dict object is what mark() stored, and the
    vendors' own ids are ARNs and URLs -- long enough that repeating one on
    every cell of a 90-day strip would add more bytes than the whole payload.
    """
    k = id(inc)
    if k not in _INC_KEYS:
        _INC_KEYS[k] = len(_INC_DATA)
        _INC_DATA.append(inc)
    return _INC_KEYS[k]


def incident_payload():
    """Everything a day dialog shows, for the incidents actually referenced."""
    out = []
    for i in _INC_DATA:
        cloud = i.get("cloud", "")
        url = i.get("url", "")
        # Only offer a link that goes somewhere specific. AWS's dashboard has
        # no per-incident URL, so its incidents all share one address; sending
        # a reader to a generic page dressed as "the incident" is worse than
        # telling them it does not exist.
        generic = url in ("https://health.aws.amazon.com/health/status",
                          "https://azure.status.microsoft/en-us/status")
        # Where the incident has no page of its own, still name the page it
        # was READ from. "No link" reads as "unsourced" on a page whose whole
        # claim is that every line is traceable -- the vendor's status page is
        # not the incident, but it is where this came from, and a reader who
        # wants to check has to be told where to look.
        out.append({
            "g": url if generic else "",
            "c": cloud,
            "t": detag(i.get("title"))[:240],
            "s": (i.get("service") or "")[:120],
            "r": i.get("region_code") or i.get("region") or "",
            "b": str(i.get("begin") or ""),
            "e": str(i.get("end") or ""),
            "u": "" if generic else url,
            "m": (i.get("update") or "")[:700],
            "k": i.get("tracking") or "",
        })
    return json.dumps(out, ensure_ascii=False).replace("</", "<\/")


INDEX_OUT = os.path.join(ROOT, "intelligence", "timeline-index.json")


def region_payload(history, live):
    """Every region a vendor named, with where it is and what happened there.

    Written into the index so the map and the archive read the same file. A
    region without a published location still appears in the payload with a
    null position -- the map lists those beneath itself rather than dropping
    them, because a map that quietly omits what it cannot draw is claiming a
    completeness it does not have.
    """
    # The same 90 days the strip above the map covers.
    #
    # Counting all recorded history sized a place by how much its vendors
    # publish rather than by how much broke: Google's records reach back
    # furthest, so anywhere Google runs a region grew a bigger light for a
    # disclosure reason. Over 90 days all three publish from live feeds and
    # the counts are comparable, which is the only footing on which putting
    # them on one map is fair. The full history is still carried, and still
    # readable in the archive, where the year filter says how far each
    # vendor's record actually goes.
    cut90 = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=90)
    seen = {}
    for i in list(history.values()) + [dict(x, cloud=c)
                                       for c, v in live.items() for x in v]:
        cloud = i.get("cloud")
        if cloud not in ORDER:
            continue
        regs = [x for x in (i.get("regions") or []) if x]
        if not regs:
            one = i.get("region_code") or i.get("region")
            regs = [one] if one else []
        if not regs:
            regs = region_map.regions_in(cloud, i.get("title") or "")
        b = (aws_begin if cloud == "aws" else t)(i.get("begin"))
        for r in regs:
            rec = seen.setdefault(r, {"r": r, "n": 0, "n90": 0, "by": {},
                                      "by90": {}, "last": "",
                                      "p": region_map.place(r)})
            rec["n"] += 1
            rec["by"][cloud] = rec["by"].get(cloud, 0) + 1
            if b and b >= cut90:
                rec["n90"] += 1
                rec["by90"][cloud] = rec["by90"].get(cloud, 0) + 1
            if b and b.date().isoformat() > rec["last"]:
                rec["last"] = b.date().isoformat()
    return sorted(seen.values(), key=lambda x: -x["n"])


def detag(text):
    """Entity-decoded text, for records fetched before ingest decoded them."""
    return html.unescape(text or "")


def write_timeline_index(history, live):
    """A trimmed index of every incident held, for the year views.

    The strip on the page covers 90 days. The store holds 904 incidents back
    to 2021, so "what broke in 2026" was answerable from the data and not from
    the page -- the most basic question of the three it tries to answer.

    This is a separate file rather than more markup because the trimmed index
    is about 180 KB against a 108 KB page: embedding it would double the cost
    of a visit for a view most readers never open. Fetched on demand, the way
    the write-up dialogs already fetch theirs.

    Trimmed hard on purpose -- date, cloud, title, link. The full text stays in
    status-history.json for anyone who wants it; a year strip needs only
    enough to draw a cell and name what is under it.
    """
    rows = []
    seen = set()
    for i in list(history.values()) + [dict(x, cloud=c)
                                       for c, v in live.items() for x in v]:
        cloud = i.get("cloud")
        if cloud not in ORDER:
            continue
        b = (aws_begin if cloud == "aws" else t)(i.get("begin"))
        if not b:
            continue
        end = (aws_begin if cloud == "aws" else t)(i.get("end"))
        key = (cloud, i.get("id") or i.get("title", "")[:60])
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "c": cloud,
            "i": i.get("id") or "",
            "b": b.date().isoformat(),
            # An open incident has no end. Null rather than today's date, so a
            # strip drawn tomorrow does not quietly claim it ended yesterday.
            "e": end.date().isoformat() if end else None,
            "t": detag(i.get("title"))[:110],
            "u": i.get("url") or "",
        })
    # Flag the ones with a published write-up, and add write-ups that have no
    # incident record at all.
    #
    # These were two separate stores feeding two separate views: the timeline
    # from status-history.json and the archive from postmortems.json. So the
    # timeline showed 210 Google incidents in 2022 and the archive showed
    # none, on the same page, for the same year. Same question, two answers.
    #
    # AWS's older post-event summaries are the reason for the second half:
    # they describe outages from 2011 onwards that its incident feed, which
    # starts in 2025, has no record of. Dropping them to keep one clean key
    # would lose the oldest material on the page.
    pm_path = os.path.join(ROOT, "intelligence", "postmortems.json")
    have = {}
    if os.path.exists(pm_path):
        try:
            for w in (json.load(io.open(pm_path, encoding="utf-8"))
                      .get("postmortems") or []):
                have[(w.get("cloud"), w.get("id"))] = w
        except ValueError:
            have = {}

    for r in rows:
        if (r["c"], r["i"]) in have:
            r["w"] = 1
            have.pop((r["c"], r["i"]), None)

    for (cloud, wid), w in have.items():
        rows.append({
            "c": cloud, "i": wid, "b": w.get("date") or "",
            "e": w.get("date") or None, "t": detag(w.get("title"))[:110],
            "u": w.get("url") or "", "w": 1,
        })

    rows.sort(key=lambda r: r["b"] or "", reverse=True)
    years = sorted({r["b"][:4] for r in rows if r["b"]}, reverse=True)
    payload = {"updated": stamp_now(), "years": years, "incidents": rows,
               "regions": region_payload(history, live)}
    tmp = INDEX_OUT + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write("\n")
    os.replace(tmp, INDEX_OUT)
    return years, len(rows)


def stamp_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds").replace("+00:00", "Z")


def timeline(history, live, hist_meta=None):
    """Ninety days, one cell per day, per cloud.

    The thing a list of cards cannot show. Two AWS regions have been degraded
    since March; as two rows of text that is something a reader scrolls past,
    and as an unbroken red line across the whole strip it is the first thing
    they see.

    A cell is marked only where a vendor published an incident open on that
    day. An unmarked cell means nothing was reported -- NOT that anything was
    verified healthy. That distinction is the entire reason this page does not
    copy Google's green-tick product matrix: those ticks mean Google checked,
    and ours would mean we did not know.
    """
    hist_meta = hist_meta or {}
    today = datetime.datetime.now(datetime.timezone.utc).date()
    days = [today - datetime.timedelta(days=i) for i in range(89, -1, -1)]
    dayset = set(days)
    # Each marked day remembers WHICH incident marked it. A red cell that will
    # not say why is decoration: a reader who spots one immediately wants to
    # know what happened, and a bare date does not answer that.
    bad = {c: {} for c in ORDER}
    # The day each incident began, so a start can be told from a continuation.
    # Keyed by id() because these dicts are not hashable and are never copied
    # between here and the render loop below.
    startday = {}

    # How far back each cloud's record actually reaches.
    #
    # AWS and Azure expose only what is open right now, so nothing that closed
    # before this store's first run exists anywhere -- their horizon is the day
    # the store began. Google publishes resolved incidents, so its first run
    # backfilled to the oldest incident the feed still carries.
    since_d = (t(hist_meta.get("since")) or datetime.datetime.now(
        datetime.timezone.utc)).date()

    # How far back each cloud's record reaches, measured from what is actually
    # held rather than assumed per vendor.
    #
    # This used to hardcode "AWS and Azure start when this log started",
    # because their live feeds carry only open incidents. That was true of the
    # feeds and false of the vendors: AWS publishes resolved events through the
    # history endpoint behind its dashboard, and Azure through the API behind
    # its history page. Both were found later, and the hardcoded assumption
    # would have gone on drawing hatched "not recorded" cells over days that
    # were, by then, perfectly well recorded.
    #
    # So the horizon is now derived: the oldest incident held for a cloud, or
    # the day this log began if that is earlier. Add a new source and the
    # strip extends on its own.
    oldest = {}
    for i in list(history.values()) + [dict(x, cloud=c)
                                       for c, v in live.items() for x in v]:
        c = i.get("cloud")
        if c not in bad:
            continue
        b = (aws_begin if c == "aws" else t)(i.get("begin"))
        if b and (c not in oldest or b.date() < oldest[c]):
            oldest[c] = b.date()
    horizon = {c: min(oldest.get(c, since_d), since_d) for c in ORDER}

    def mark(cloud, begin, end, inc):
        if not begin:
            return
        startday[id(inc)] = begin.date()
        d, last = begin.date(), (end or datetime.datetime.now(datetime.timezone.utc)).date()
        # Clip to the window before walking. The Middle East incidents have
        # been open 190+ days, and counting every one of them produced
        # "193 of 90 days" -- true about the incident, nonsense about the strip.
        d = max(d, days[0])
        while d <= min(last, today):
            bad[cloud].setdefault(d, []).append(inc)
            d += datetime.timedelta(days=1)

    for i in history.values():
        c = i.get("cloud")
        if c in bad:
            # AWS timestamps are epoch seconds in the history feed too, not
            # just in the live one. Parsing them with the ISO reader returned
            # None, mark() bailed out, and all 31 resolved AWS incidents were
            # silently absent from the strip -- present in the store, counted
            # in the region grid, and invisible on the one chart meant to show
            # when things broke.
            when = aws_begin if c == "aws" else t
            mark(c, when(i.get("begin")), when(i.get("end")), i)
    for c, rows in live.items():
        for i in rows:
            # Stamp the cloud on live incidents. Only history records carry
            # one, so the day dialog rendered "has no address for a single
            # incident" with the vendor's name missing from the front of the
            # sentence -- for the two incidents that are open right now, which
            # are the ones most likely to be read.
            i.setdefault("cloud", c)
            mark(c, aws_begin(i.get("begin")) if c == "aws" else t(i.get("begin")), None, i)

    out = []
    for c in ORDER:
        # A row that is almost entirely unrecorded is not a timeline, it is an
        # empty row with texture on it. Azure's read "0 of 90 - 89 unrecorded"
        # over 89 hatched cells and one green one, which is accurate and tells
        # a reader nothing. Where the record simply has not started yet, the
        # leading gap collapses into one labelled band and only the days that
        # ARE recorded get drawn as days.
        lead = 0
        for d in days:
            if d < horizon[c] and not bad[c].get(d):
                lead += 1
            else:
                break
        collapse = lead >= 14
        cells = ""
        if collapse:
            # Formatted BEFORE the % expression below. Written inline it was
            # double-escaped and strftime received "%%d %%b" literally, so the
            # band read "no record before %d %b".
            hd = horizon[c]
            pretty = "%d %s" % (hd.day, MONTH_ABBR[hd.month - 1])
            cells += ('<span class="tl-gap" style="--n:%d" title="No record '
                      'before %s. %s">no record before %s</span>'
                      % (lead, e(hd.isoformat()), e(WHYUNK[c]), e(pretty)))
        for d in (days[lead:] if collapse else days):
            incs = bad[c].get(d)
            if not incs:
                # Unknown is not clear, and drawing them the same way is the
                # false reassurance this whole page exists to avoid. AWS and
                # Azure publish only incidents that are OPEN RIGHT NOW, so a
                # problem that started and finished before this store began
                # left no trace in any feed and never can. Those days are
                # blanks in the record, not clean bills of health.
                if d < horizon[c]:
                    cells += ('<i class="d unk" title="%s — not recorded. %s"></i>'
                              % (d.isoformat(), e(WHYUNK[c])))
                else:
                    cells += ('<i class="d ok" title="%s — nothing reported '
                              '(not the same as verified healthy)"></i>'
                              % d.isoformat())
                continue
            titles = " | ".join(dict.fromkeys(
                (x.get("title") or "").strip()[:90] for x in incs if x.get("title")))
            more = "" if len(incs) == 1 else "  (%d open)" % len(incs)
            # An anchor, not a div: the cell links to the vendor's own page for
            # that incident, so "what was this?" is one tap rather than a hunt
            # through the card list below.
            # A day an incident BEGAN is a different fact from a day one
            # merely continued. AWS has two incidents open since 1 March, so
            # every cell in its strip was solid red -- ninety days that look
            # like ninety events and are two. Continuation days are drawn
            # faintly so the starts stand out as the things that happened.
            started = any(startday.get(id(x)) == d for x in incs)
            kind = "bad" if started else "bad cont"
            # NOT `lead`: that name already holds the count of leading
            # unrecorded days in this row, and assigning a string to it
            # here made `90 - lead` a TypeError. It only surfaced when
            # Azure gained its first marked cell -- the collapse path is
            # the only place the count is read, and Azure was the only
            # row that collapses.
            pre = "" if started else "ongoing — "
            # A BUTTON that opens the day, not a link straight out.
            #
            # A cell can cover several incidents at once, and a link can only
            # go to one of them -- so it opens a panel listing each, with the
            # vendor's own text and a link per incident. All three publish a
            # per-incident address: Google in its feed, Azure as aka.ms/AzPIR,
            # and AWS via ?eventID=<arn> on its dashboard.
            ids = ",".join(str(inc_key(x)) for x in incs)
            cells += ('<button class="d %s" data-day="%s" data-inc="%s" '
                      'type="button" title="%s%s&#10;%s%s"></button>'
                      % (kind, d.isoformat(), e(ids), d.isoformat(), more,
                         pre, e(titles)))
        n = len(set(bad[c]) & dayset)
        starts = sum(1 for d in days
                     if any(startday.get(id(x)) == d for x in bad[c].get(d, [])))
        unknown = sum(1 for d in days if d < horizon[c] and not bad[c].get(d))
        if collapse:
            # "0 of 90" leads with a zero that reads as ninety verified-clear
            # days. Say how much record there actually is instead.
            rec = 90 - lead
            label = "%d day%s of record" % (rec, "" if rec == 1 else "s")
            if n:
                label = "%d of %d recorded day(s)" % (n, rec)
        else:
            label = "%d of 90" % n
            if unknown:
                label += " · %d unrecorded" % unknown
        out.append('<div class="tl-row"><div class="tl-n">%s</div>'
                   '<div class="tl-cells">%s</div>'
                   '<div class="tl-s" title="%d incident(s) began in this '
                   'window">%s</div></div>'
                   % (e(LABEL[c]), cells, starts, e(label)))

    # The index still gets written -- the archive below uses it -- but the
    # strip stays at 90 days.
    #
    # Year chips here were the wrong answer to the right question. This
    # section asks whether anything is broken now; nobody arrives at it
    # wanting a 2022 calendar, and offering one made the page look like it
    # could not decide what it was for. The history belongs in the archive,
    # which is built for browsing.
    write_timeline_index(history, live)

    key = ('<div class="tl-key">'
           '<span><i class="d bad"></i>incident began</span>'
           '<span><i class="d bad cont"></i>still open</span>'
           '<span><i class="d ok"></i>nothing reported</span>'
           '<span><i class="d unk"></i>not recorded</span>'
           '<span class="tl-tz">days are UTC</span></div>')
    reach = ", ".join("%s to %s" % (LABEL[c], horizon[c].isoformat())
                       for c in ORDER)
    note = ('<p class="note-sm">Days here are counted in <b>UTC</b>, while the '
            'vendors’ own dashboards show your local time — so an '
            'incident late in your evening can sit on the next day here than '
            'on theirs. Open a cell and it prints both. '
            'A grey cell is a gap in the record, not a good day — it '
            'means the vendor’s own history does not reach that far back, '
            'not that nothing happened. Each record reaches to: %s.</p>'
            % (e(reach)))
    return ('<div class="tl">%s</div>%s%s'
            '<script type="application/json" id="tl-data">%s</script>'
            % ("".join(out), key, note, incident_payload()))


def blast(inc, cloud):
    """How far an incident reaches, from what the vendor published.

    A single zone degrading and three regions degrading read identically in a
    list of cards, and they are not remotely the same problem. Google names
    zones as region-plus-letter, so the suffix distinguishes the two.
    """
    if cloud == "gcp":
        regs = inc.get("regions") or []
        zones = [r for r in regs if re.search(r"-[a-f]$", r)]
        if len(regs) > 1:
            return ("multi-region", "%d regions" % len(regs), 3)
        if zones:
            return ("zonal", zones[0], 1)
        if regs:
            return ("regional", regs[0], 2)
        return ("not stated", "the vendor did not say", 0)
    reg = inc.get("region") or ""
    return ("regional", reg, 2) if reg else ("not stated", "the vendor did not say", 0)


def region_label(i):
    """"UAE (me-central-1)" -- the place name and the code that goes with it."""
    name, code = i.get("region", ""), i.get("region_code", "")
    if name and code and code.lower() != name.lower():
        return "%s <span class=\"rc\">%s</span>" % (e(name), e(code))
    return e(code or name)


SHORT = {"aws": "AWS", "azure": "Azure", "gcp": "Google"}

DISCLOSURE = [
    ("Incident start",      {"aws": 0,   "azure": 0,   "gcp": 1}),
    ("First-update time",   {"aws": 0,   "azure": 0,   "gcp": 1}),
    ("Timestamped updates", {"aws": 1,   "azure": 0,   "gcp": 1}),
    ("Affected services",   {"aws": 0.5, "azure": 0.5, "gcp": 1}),
    ("Affected regions",    {"aws": 1,   "azure": 0.5, "gcp": 1}),
    ("Severity",            {"aws": 0,   "azure": 0,   "gcp": 1}),
]


def disclosure():
    """The same six facts, drawn two ways, because one layout cannot do both.

    The wide layout is cloud-major: a row per cloud, six bars across. That only
    works while the column headers are visible, and on a phone six labels will
    not fit above 6 bars in a 360px column. They used to be display:none there,
    which left six unlabelled bars and a score -- a reader could see that Azure
    scored 1.0 and had no way to learn what it scored 1.0 AT. That is
    decoration, and worse than omitting the chart, because it looks like
    information.

    So narrow screens get a criterion-major list instead: one row per fact,
    named in full, with three labelled chips. Taller, but every mark says what
    it means. Both are generated; CSS picks one.

    A key is now shown in both. Three fill states that nothing explained was
    the same failure in miniature.
    """
    key = ('<div class="dv-key">'
           '<span><i class="f full"></i>published as a field</span>'
           '<span><i class="f part"></i>in prose, not a field</span>'
           '<span><i class="f none"></i>absent</span></div>')

    def cls(v):
        return "full" if v == 1 else ("part" if v else "none")

    # Wide: a row per cloud.
    head = "".join("<span>%s</span>" % e(f) for f, _ in DISCLOSURE)
    rows = ""
    for c in ORDER:
        vals = [d[c] for _, d in DISCLOSURE]
        bars = "".join('<i class="f %s" title="%s"></i>' % (cls(v), e(f))
                       for (f, _), v in zip(DISCLOSURE, vals))
        rows += ('<div class="dv-row"><div class="dv-n">%s</div>'
                 '<div class="dv-bars">%s</div><div class="dv-s">%.1f / 6</div></div>'
                 % (e(LABEL[c]), bars, sum(vals)))
    wide = ('<div class="dv-w"><div class="dv-head">%s</div>%s</div>' % (head, rows))

    # Narrow: a row per criterion, every one named.
    mrows = ""
    for field, d in DISCLOSURE:
        chips = "".join('<span class="dv-c"><i class="f %s"></i>%s</span>'
                        % (cls(d[c]), e(SHORT[c])) for c in ORDER)
        mrows += ('<div class="dv-mrow"><div class="dv-mn">%s</div>'
                  '<div class="dv-cs">%s</div></div>' % (e(field), chips))
    totals = " · ".join("%s %.1f/6" % (SHORT[c], sum(d[c] for _, d in DISCLOSURE))
                        for c in ORDER)
    narrow = ('<div class="dv-m">%s<p class="dv-tot">%s</p></div>'
              % (mrows, e(totals)))

    return '<div class="dv">%s%s%s</div>' % (wide, narrow, key)



POSTMORTEMS = os.path.join(ROOT, "intelligence", "postmortems.json")

VENDOR_OF = {"aws": "AWS", "azure": "Microsoft", "gcp": "Google"}


HOOK_ORDER = ("root cause", "preliminary root cause", "what went wrong and why",
              "what happened", "summary")

# Openers that say nothing about the incident: apologies, survey links, and the
# standing caveat every Google preliminary report carries. A hook is meant to
# be the one line worth stopping for, so a card that opens "We sincerely
# apologize" is a wasted slot.
HOOK_SKIP = ("sincerely apolog", "we apolog", "survey", "rate this pir",
             "please note", "subject to change", "if you have experienced",
             "we wanted to provide")


def first_sentence(t):
    t = re.sub(r"\s+", " ", (t or "").strip())
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z(])", t)
    for p in parts:
        p = p.strip()
        if len(p) < 60 or len(p) > 320:
            continue
        if any(k in p.lower() for k in HOOK_SKIP):
            continue
        return p
    return ""


def hooks():
    """One quoted line per write-up, for the "did you know" card.

    The line is the vendor's own first sentence from whichever section they
    labelled as the cause -- never a sentence assembled here, and never a
    paraphrase. Picking WHICH sentence is the only editorial act, and it is
    made mechanical on purpose: the first sentence of the first section that
    matches HOOK_ORDER, skipping openers that carry no information.

    AWS is largely absent from this rotation and that is the honest outcome:
    it publishes essays with no labelled cause section, so there is nothing to
    take a first sentence FROM without me deciding which sentence of a
    four-thousand-word narrative is the interesting one. That decision is
    exactly where a quote stops being the vendor's and starts being mine.
    """
    if not os.path.exists(POSTMORTEMS):
        return []
    try:
        rows = (json.load(io.open(POSTMORTEMS, encoding="utf-8"))
                .get("postmortems") or [])
    except ValueError:
        return []
    out = []
    for r in rows:
        secs = r.get("sections") or []
        chosen, head = "", ""
        for want in HOOK_ORDER:
            for s in secs:
                if s.get("heading", "").strip().lower() == want:
                    line = first_sentence(s.get("text"))
                    if line:
                        chosen, head = line, s["heading"]
                        break
            if chosen:
                break
        if not chosen:
            continue
        out.append({
            "q": chosen, "sec": head, "cloud": r.get("cloud", ""),
            "date": r.get("date", ""), "title": r.get("title", ""),
            "id": "%s:%s" % (r.get("cloud", ""), r.get("id", "")),
            "url": r.get("url", ""),
        })
    return out




def cadence():
    """The refresh rate this page ACHIEVED, measured, not the one intended.

    The page spent a day claiming "refreshed every 15 minutes" while the
    scheduled job had never run at all -- the cron was silently dropped and
    nothing said so. A freshness claim a reader cannot check is just a nicer
    way of saying trust me.

    So this counts actual runs from the log every refresh writes. If the
    scheduler dies again the number drops on its own, in public, without
    anyone having to notice.
    """
    if not os.path.exists(RUNS):
        return ""
    try:
        runs = (json.load(io.open(RUNS, encoding="utf-8")) or {}).get("runs") or []
    except ValueError:
        return ""
    if not runs:
        return ""
    now = datetime.datetime.now(datetime.timezone.utc)
    day = [r for r in runs if (t(r.get("at")) or now) > now - datetime.timedelta(hours=24)]
    week = [r for r in runs if (t(r.get("at")) or now) > now - datetime.timedelta(days=7)]
    failed = sum(1 for r in day if r.get("failed"))

    # Below about 18 in 24 hours the hourly schedule is missing runs, which is
    # exactly the failure that went unnoticed before. Say so rather than
    # printing a number and leaving the reader to judge it.
    verdict = ("on schedule" if len(day) >= 18 else
               "fewer than the hourly schedule intends")
    bits = ("<b>%d</b> refresh%s in the last 24 hours (%s), "
            "<b>%d</b> in the last 7 days."
            % (len(day), "" if len(day) == 1 else "es", e(verdict), len(week)))
    if failed:
        bits += (" %d run%s had a source that did not answer; those keep the "
                 "previous data rather than showing a blank."
                 % (failed, "" if failed == 1 else "s"))
    # Link the COMMIT HISTORY, not the raw log.
    #
    # This pointed at /intelligence/status-runs.json, which is the evidence but
    # not in a form that evidences anything to a reader: clicking it produces a
    # wall of JSON, and "here is my machine-readable file" is developer
    # furniture on a page written for people. The commit list shows the same
    # runs as dated entries, each with what changed, on a host the reader
    # already trusts more than this page.
    last = t(runs[-1].get("at"))
    when = (" Most recent: %s UTC." % last.strftime("%d %b, %H:%M")) if last else ""
    return ('<p class="note-sm">Counted, not claimed: %s%s '
            'Every refresh is a commit, so the record is '
            '<a href="https://github.com/katta698/katta698.github.io/'
            'commits/main/intelligence/status.json" target="_blank" '
            'rel="noopener">public and dated</a>.</p>' % (bits, when))


def postmortems(cssv="1"):
    """The archive: every past incident held, browsable by year and cloud.

    This used to render only the 73 vendor write-ups, from a different store
    than the timeline above it -- so the strip reported 210 Google incidents in
    2022 while the archive below reported none. One page, one year, two
    answers, because one view was built from postmortems.json and the other
    from status-history.json.

    Both now read the same index, so the counts cannot disagree. An entry with
    a published write-up opens the vendor's full text; one without opens what
    is actually known -- title, dates, and a link to the vendor's record. The
    difference is marked rather than hidden, because "AWS wrote 4,000 words
    about this" and "AWS logged a line" are different facts and a reader
    deciding what to open deserves to know which is which.

    Cards are rendered in the browser from the index rather than baked in:
    922 of them is roughly 200 KB of markup, against a page that is currently
    108 KB in total.
    """
    idx_path = os.path.join(ROOT, "intelligence", "timeline-index.json")
    if not os.path.exists(idx_path):
        return ""
    try:
        idx = json.load(io.open(idx_path, encoding="utf-8"))
    except ValueError:
        return ""
    rows = idx.get("incidents") or []
    if not rows:
        return ""

    by_year, by_cloud = {}, {}
    for r in rows:
        y = (r.get("b") or "")[:4] or "Undated"
        by_year[y] = by_year.get(y, 0) + 1
        by_cloud[r.get("c")] = by_cloud.get(r.get("c"), 0) + 1

    def yr_key(y):
        return (0, 0) if y == "Undated" else (1, int(y))

    years = sorted(by_year, key=yr_key, reverse=True)
    newest = years[0] if years else ""

    chips = ('<button class="pm-yr" data-yr="all" type="button">All years '
             '<span class="pm-yn">%d</span></button>' % len(rows))
    chips += "".join(
        '<button class="pm-yr%s" data-yr="%s" type="button">%s '
        '<span class="pm-yn">%d</span></button>'
        % (" is-on" if y == newest else "", e(y), e(y), by_year[y])
        for y in years)

    cchips = ('<button class="pm-cl is-on" data-cl="all" type="button">All '
              '<span class="pm-yn">%d</span></button>' % len(rows))
    cchips += "".join(
        '<button class="pm-cl %s" data-cl="%s" type="button">%s '
        '<span class="pm-yn">%d</span></button>'
        % (c, c, e(LABEL[c]), by_cloud.get(c, 0))
        for c in ORDER if by_cloud.get(c))

    wrote = sum(1 for r in rows if r.get("w"))
    span = {}
    for r in rows:
        if not r.get("b"):
            continue
        c = r.get("c")
        lo, hi = span.get(c, (r["b"], r["b"]))
        span[c] = (min(lo, r["b"]), max(hi, r["b"]))
    reach_txt = "; ".join("%s back to %s" % (LABEL[c], span[c][0][:4])
                          for c in ORDER if c in span)
    note = ('<p class="note-sm">%d outage%s recorded across the three clouds, '
            'the same set the timeline above is drawn from. %d of them have a '
            'full incident report from the vendor; the rest carry what the '
            'vendor recorded — what it was, when, and a link to their page '
            'for it. Nothing is left out for being minor. How far back each '
            'goes is their choice, not a filter here: %s. A missing year means '
            'nothing was published for it — and %d AWS summaries state a '
            'month and day with no year anywhere in the text, so they sit under '
            'Undated rather than being guessed into one.</p>'
            % (len(rows), "" if len(rows) == 1 else "s", wrote, e(reach_txt),
                 sum(1 for r in rows if not r.get("b"))))

    dialog = ('<dialog id="pm-dialog" aria-labelledby="pm-title">'
              '<button class="pm-x" data-pm-close aria-label="Close">×</button>'
              '<div class="pm-body"></div></dialog>')

    return ('<div class="pm-yrs">%s</div>'
            '<div class="pm-yrs pm-cls" id="pm-clouds">%s</div>'
            '<div class="pm" id="pm-list"></div>'
            '<p class="pm-none note-sm" hidden></p>%s%s'
            '<script src="/intelligence/status/pm.js?v=%s" defer></script>'
            % (chips, cchips, note, dialog, e(cssv)))


def cloud_card(cloud, incidents, source):
    if not source.get("ok"):
        state, cls, note = "Could not check", "err", e(source.get("error", "")[:60])
    elif incidents:
        n = len(incidents)
        state, cls = "%d incident%s" % (n, "" if n == 1 else "s"), "bad"
        note = "as reported by the vendor"
    else:
        state, cls, note = "No active incidents", "ok", "vendor reports none"
    return ('<div class="scard"><div class="sc-n">%s</div>'
            '<div class="sc-v"><span class="pill %s"></span>%s</div>'
            '<div class="sc-s">%s</div>'
            '<div class="sc-t">read %s</div></div>'
            % (e(LABEL[cloud]), cls, e(state), note,
               e(since(t(source.get("fetched"))))))


def incident_card(cloud, i):
    rows = []
    if cloud == "aws":
        b = aws_begin(i.get("begin"))
        rows += [("Service", e(i.get("service", ""))),
                 # Both names: AWS publishes the place ("UAE") but a reader
                 # matches infrastructure on the code, and the region grid is
                 # keyed on the code. Showing one without the other leaves the
                 # card and the grid looking like they describe different
                 # places.
                 ("Region", region_label(i))]
        if b:
            hrs = (datetime.datetime.now(datetime.timezone.utc) - b).total_seconds() / 3600
            rows += [("Announced", b.strftime("%d %b %Y %H:%M") + " UTC"),
                     ("Open for", dur(hrs))]
    else:
        if i.get("products"):
            rows.append(("Products", '<div class="tags">%s</div>'
                         % "".join('<span class="tag">%s</span>' % e(p)
                                   for p in i["products"])))
        if i.get("regions"):
            rows.append(("Regions", '<div class="tags">%s</div>'
                         % "".join('<span class="tag">%s</span>' % e(r)
                                   for r in i["regions"])))
        if i.get("impact"):
            rows.append(("Impact", e(i["impact"].replace("_", " ").title())))
        b = t(i.get("begin"))
        if b:
            hrs = (datetime.datetime.now(datetime.timezone.utc) - b).total_seconds() / 3600
            rows += [("Started", b.strftime("%d %b %Y %H:%M") + " UTC"),
                     ("Open for", dur(hrs))]

    kind, where, level = blast(i, cloud)
    if level:
        rows.append(("Reach", '<span class="br-bars">%s</span>'
                     '<span class="br-w">%s &middot; %s</span>'
                     % ("".join('<i class="%s"></i>' % ("b on" if n < level else "b")
                                for n in range(3)), e(kind), e(where))))

    chips = '<span class="chip %s">%s</span>' % (cloud, e(LABEL[cloud]))
    if i.get("severity"):
        chips += '<span class="chip sev">%s</span>' % e(i["severity"])
    chips += '<span class="chip sev">Ongoing</span>'

    meta = "".join('<div class="k">%s</div><div>%s</div>' % (k, v) for k, v in rows)
    upd = ('<div class="upd"><span class="lab">Latest update, in the vendor’s '
           'words</span>%s</div>' % e(i["update"])) if i.get("update") else ""
    return ('<article class="inc"><div class="top">%s</div>'
            '<h3 class="ttl">%s</h3><div class="meta">%s</div>%s'
            '<div class="foot"><span>%d update%s published by the vendor</span>'
            '<a href="%s" target="_blank" rel="noopener">Vendor status page &rarr;</a>'
            '</div></article>'
            % (chips, e(i.get("title", "")), meta, upd,
               i.get("updates", 0), "" if i.get("updates") == 1 else "s",
               e(i.get("url", "#"))))


PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cloud status &mdash; AWS, Azure and Google Cloud | Jayanth Katta</title>
<meta name="description" content="Live incident status for AWS, Azure and Google Cloud, read from each vendor own status feed, with the time each source was last checked."/>
<link rel="canonical" href="https://jayanthkatta.com/intelligence/status/"/>
<link rel="icon" href="/favicon-transparent.png" type="image/png">
<link rel="apple-touch-icon" href="/blog/assets/icons/apple-touch-icon.png"/>
<!-- The same request the other Intelligence pages make. This asked for DM
     Sans at 400 and 600 only, and the navigation links are set at 500 --
     so the browser synthesised the weight it had not been given and every
     word in the bar came out 2px narrower than the same word on the same
     bar on every other page. Nothing looked wrong on this page alone; the
     five links simply never lined up with the other four. -->
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700&amp;family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400&amp;family=DM+Mono:wght@400;500&amp;display=swap" rel="stylesheet">
<link rel="stylesheet" href="/intelligence/status/status.css?v=__CSSV__">
<script>
/* Byte-identical to the setter in index.html, now.html and the other
   intelligence pages. It runs before first paint deliberately: setting the
   palette after the stylesheet has applied produces a visible flash of the
   default ground colour on every load. */
(function(){var D=["sun","mon","tue","wed","thu","fri","sat"],p;
try{p=new URLSearchParams(location.search).get("palette")||localStorage.getItem("paletteDay");}catch(e){p=null;}
if(D.indexOf(p)===-1)p=D[new Date().getDay()];
document.documentElement.setAttribute("data-palette",p);})();
</script>
<!-- The shared bar's stylesheet, linked rather than injected.
     site-footer.js appended this <link> at runtime, so on every load the
     navigation was laid out twice: once by the page's own rules and again,
     visibly, when the shared file arrived. Filmed at 200ms into a hard
     refresh the icons were still in the pre-shared order and jumped into
     place afterwards -- which is what "shaky on refresh" is. In the head it
     is render-blocking, which is the point: the bar is painted once, right.
     ensureStyles() finds this and skips, so nothing is loaded twice. -->
<!-- Marks that JavaScript is running, before anything is painted, so the
     stylesheet can hide the five site links on a phone from the FIRST
     frame rather than after the cairn is built. Without this the blog --
     the largest document on the site, so the slowest to reach its
     scripts -- rendered all five overflowing the bar and overlapping the
     icons for four seconds, which reads as garbled characters.
     A class rather than a plain CSS rule so that a reader with no
     JavaScript keeps the links: the cairn that replaces them is built in
     JS, and hiding them unconditionally would leave that reader with no
     navigation at all. -->
<script>document.documentElement.className+=' ck-js';</script>
<link rel="preload" as="font" type="font/woff2" crossorigin
      href="/blog/assets/fonts/dm-sans-latin.woff2">
<link rel="preload" as="font" type="font/woff2" crossorigin
      href="/blog/assets/fonts/playfair-latin.woff2">
<link rel="stylesheet" data-site-footer-style href="/blog/assets/site-footer.css?v=__JSV__">
</head><body>
<nav>
  <a class="nav-logo" href="/intelligence/" aria-label="Cloud intelligence home">
    <img class="brand-mark" src="/brand-mark-96.png" alt="" width="30" height="30" aria-hidden="true">
    <span class="brand-name">Jayanth Katta</span>
  </a>
  <ul class="nav-links">
    <li><a href="/">Portfolio</a></li>
    <li><a href="/blog/">Blog</a></li>
    <li><a href="/intelligence/">Intelligence</a></li>
    <li><a href="/intelligence/whats-new/">What&rsquo;s new</a></li>
    <li><a href="/intelligence/status/" class="active" aria-current="page">Live status</a></li>
    <li class="nav-ctl"><button class="audio-toggle" id="audio-toggle" type="button"
        title="Toggle beach sounds" aria-label="Toggle beach sounds">&#127907;</button></li>
    <li class="nav-ctl"><button class="theme-toggle" onclick="toggleTheme()" id="theme-btn" type="button">
      <span id="theme-icon">&#9681;</span><span id="theme-label">Light</span>
    </button></li>
  </ul>
</nav>
<header class="hero">
  <div class="inner">
    <p class="eyebrow"><span class="dot"></span>Cloud status</p>
    <h1>Is anything broken right now?</h1>
    <p class="sub">Live incidents across AWS, Azure and Google Cloud, read from each
       vendor&rsquo;s own status feed. Nothing here is summarised or inferred &mdash;
       the wording is theirs.</p>
    <p class="fresh__STALE__">Last checked __AGE__ &middot; refresh is scheduled hourly and can run late, so this timestamp is the one to trust__WARN__</p>
  </div>
</header>
<div class="wrap">
  __CARDS__
  __BODY__
  <h2>Last 90 days</h2>
  <p class="sub">One cell per day. A cell is marked only where a vendor published an
     incident that was open on that day &mdash; an unmarked cell means nothing was
     reported, not that anything was verified healthy.</p>
  __TIMELINE__

  <h2>Where the clouds are, and where they break</h2>
  <div class="pm-cls om-cls" id="om-clouds">
    <button class="pm-cl is-on" data-cl="all" type="button">All clouds</button>
    <button class="pm-cl aws" data-cl="aws" type="button">AWS</button>
    <button class="pm-cl azure" data-cl="azure" type="button">Azure</button>
    <button class="pm-cl gcp" data-cl="gcp" type="button">Google Cloud</button>
  </div>
  <div id="outage-map" class="om"></div>

  <h2>What the vendors do and don&rsquo;t tell you</h2>
  <p class="sub">The three publish very different amounts, and that difference is
     itself worth knowing when you decide how far to trust a status page.</p>
  __DISCLOSURE__

  <div class="note"><strong>Why the timings below are Google&rsquo;s only.</strong>
     Google publishes when an incident <em>began</em> and, separately, when it first
     said something publicly, so the gap between the two is a real number. AWS&rsquo;s
     status data carries no start time distinct from its first announcement, making
     that gap structurally zero; Azure&rsquo;s feed carries no start time at all.
     Ranking all three would put AWS first for disclosing less, so only the cloud
     that supplies the inputs is measured.</div>
  __STATS__
</section>

<section class="sec">
  <h2>Past outages</h2>
  <p class="lede">Every outage the three clouds have recorded, by year and by
  cloud. Open one for what the vendor said about it and a link to their own
  page for it. Where they published a full incident report, you get the whole
  thing.</p>
  __POSTMORTEMS__
  <h2 id="sources">Sources</h2>
  <div class="tw"><table><tr><th>Status page</th><th>Endpoint we read</th><th>Last response</th><th>Read</th></tr>__SRC__</table></div>
  __CADENCE__
  <p class="src">No ETA appears anywhere on this page. None of the three publishes one
     as structured data, and lifting &ldquo;we expect recovery shortly&rdquo; out of an
     update would manufacture a commitment the vendor never made.</p>
</div>
<footer></footer>
<script>
function applyTheme(dark){
  document.body.classList.toggle("light", !dark);
  var i=document.getElementById("theme-icon"), l=document.getElementById("theme-label");
  if(i) i.textContent = dark ? "◑" : "◐";
  if(l) l.textContent = dark ? "Light" : "Dark";
}
function toggleTheme(){
  var goingDark = document.body.classList.contains("light");
  localStorage.setItem("theme", goingDark ? "dark" : "light");
  applyTheme(goingDark);
}
applyTheme(localStorage.getItem("theme") !== "light");
</script>
<script src="/blog/assets/site-footer.js?v=__JSV__" data-site-footer></script>
__STAR__
__TOP__
<!-- Beach sounds, the same control the portfolio and the blog carry.
     Audio only: these pages have no hero video and are not getting one.
     hero-media.js picks the track -- the same file, so the three surfaces
     cannot drift onto different music -- and it no-ops for video here
     because it looks for #hero-video and there is none. -->
<audio id="beach-audio" loop preload="none"></audio>
<script src="/blog/assets/hero-media.js?v=__JSV__"></script>
</body></html>
"""



def _shared_js_version():
    """The same token sync_blog stamps on the blog and What's New.

    Imported rather than recomputed: three builders each hashing their own idea
    of "the shared assets" is how one page ends up pinned to a stale copy while
    the others move on, which is exactly what happened here.
    """
    try:
        import sync_blog
        return sync_blog.JS_VERSION
    except Exception:                                           # noqa: BLE001
        return "0"


def main():
    if not os.path.exists(STATUS):
        print("  no %s -- run scripts/fetch_status.py first" % STATUS)
        return 1
    data = json.load(io.open(STATUS, encoding="utf-8"))
    hist, hist_meta = {}, {}
    if os.path.exists(HISTORY):
        hist_meta = json.load(io.open(HISTORY, encoding="utf-8")) or {}
        hist = hist_meta.get("incidents", {})

    clouds = data.get("clouds", {})
    sources = data.get("sources", {})
    checked = t(data.get("checked"))
    age = ((datetime.datetime.now(datetime.timezone.utc) - checked).total_seconds() / 60
           if checked else 99999)
    stale = age > STALE_MINUTES

    cards = '<div class="sum">%s</div>' % "".join(
        cloud_card(c, clouds.get(c, []), sources.get(c, {})) for c in ORDER)

    inc = [incident_card(c, i) for c in ORDER for i in clouds.get(c, [])]
    body = "".join(inc) if inc else (
        '<div class="allclear">No active incidents reported by any of the three '
        'vendors as of the last check.</div>')

    tr = track_record(hist)
    # Timings as a single sentence, not three display cards.
    #
    # They were the headline: three big figures for median acknowledgement,
    # worst case and median resolution. That is the wrong emphasis for a page
    # whose job is "is anything broken right now" -- how long a past incident
    # took is trivia next to what is happening, and it invites the reader to
    # treat it as a prediction, which six data points cannot support.
    #
    # It stays because the disclosure argument needs it: the numbers exist for
    # Google and cannot exist for the other two. One line, in the note.
    stats = ""
    if tr["ack_median"] is not None:
        stats = ('<p class="note-sm">For what it is worth, across %d recorded '
                 'Google incidents the median gap between an incident starting '
                 'and the first public word was %d minutes, and the widest was '
                 '%s. Too few to predict anything &mdash; shown because the '
                 'numbers exist for Google and cannot for the other two.</p>'
                 % (len(tr["acks"]), round(tr["ack_median"]), dur(max(tr["acks"]) / 60)))

    # EVERY source, not just the three live feeds.
    #
    # The table listed the three status endpoints while the fetcher was also
    # reading AWS's history events and Azure's status-history API -- which by
    # then supplied most of the timeline. So the page named three sources and
    # ran on five, on the one section whose entire job is saying where things
    # came from. Iterating `sources` rather than ORDER means a source added to
    # the fetcher appears here without anyone remembering to add it.
    HUMAN_HISTORY = {
        "aws_history": "https://health.aws.amazon.com/health/status",
        "azure_history": "https://azure.status.microsoft/en-us/status/history/",
        "gcp_history": "https://status.cloud.google.com/summary",
    }
    EXTRA = {
        "aws_history": ("AWS", "service history"),
        "azure_history": ("Azure", "status history"),
        "gcp_history": ("Google Cloud", "product history"),
    }
    src = ""
    for key in list(ORDER) + [k for k in sources if k not in ORDER]:
        s = sources.get(key, {})
        if not s:
            continue
        resp = ("HTTP %s" % s.get("http")) if s.get("ok") else                '<span style="color:#D4A05A">failed</span>'
        if s.get("ok") and s.get("http") is None:
            resp = "read %d" % s.get("count", 0)
        u = s.get("url", "")
        if key in EXTRA:
            label, kind = EXTRA[key]
            name = "%s <span class=\"src-kind\">%s</span>" % (e(label), e(kind))
            # Link the PAGE, not the endpoint.
            #
            # These pointed at the raw feeds, and none of them is a thing a
            # browser can show: the AWS one is gzip and downloads as a file,
            # the Azure one is an HTML fragment that renders as a broken
            # half-page, and the Google one is a wall of JSON. The endpoint
            # still appears in the column beside it, as text, because naming
            # what was read is the point of the table -- but the link has to
            # go somewhere a person can read.
            human = HUMAN_HISTORY.get(key, u)
        else:
            name = e(LABEL[key])
            human = HUMAN.get(key, u)
        src += ('<tr><td><a href="%s" target="_blank" rel="noopener">%s</a></td>'
                '<td>%s</td><td>%s</td><td>%s</td></tr>'
                % (e(human), name, e(u[:56]), resp,
                   e(since(t(s.get("fetched"))))))

    cssv = "1"
    p = os.path.join(OUT_DIR, "status.css")
    if os.path.exists(p):
        import hashlib
        cssv = hashlib.md5(io.open(p, "rb").read()).hexdigest()[:8]

    page = (PAGE.replace("__CSSV__", cssv)
                .replace("__STALE__", " stale" if stale else "")
                .replace("__AGE__", e(since(checked)))
                .replace("__WARN__", " &middot; older than expected — the scheduled refresh has missed at least two runs"
                         if stale else "")
                .replace("__CARDS__", cards)
                .replace("__BODY__", body)
                .replace("__TIMELINE__", timeline(hist, clouds, hist_meta))
                .replace("__DISCLOSURE__", disclosure())
                .replace("__POSTMORTEMS__", postmortems(cssv))
                .replace("__CADENCE__", cadence())
                .replace("__STATS__", stats)
                .replace("__SRC__", src)
                .replace("__STAR__", star_html("intelligence-status"))
                .replace("__TOP__", TOP_HTML + SRC_HTML + TOP_JS)
                # Cache-bust the shared script the same way every
                # other page does. This page linked it with no
                # version at all, so a returning reader kept
                # running whatever copy their browser had -- which
                # is the whole nav, the menu and the palette.
                .replace("__JSV__", _shared_js_version()))

    os.makedirs(OUT_DIR, exist_ok=True)
    io.open(os.path.join(OUT_DIR, "index.html"), "w",
            encoding="utf-8", newline="\n").write(page)
    n = sum(len(v) for v in clouds.values())
    print("  %d active incident(s), %d in history -> intelligence/status/index.html"
          % (n, len(hist)))
    print("  data age %.0f min%s" % (age, "   STALE" if stale else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
