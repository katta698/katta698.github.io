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
import html
import io
import json
import os
import re
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
    try:
        return datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:                                          # noqa: BLE001
        return None


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
    "aws": "AWS publishes only incidents that are open now, so anything "
           "resolved before this log began left no trace.",
    "azure": "Azure's feed carries items only while something is wrong, so "
             "anything resolved before this log began left no trace.",
    "gcp": "Outside the window Google's feed still carries.",
}


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
    gcp_d = (t(hist_meta.get("gcp_horizon")) or since_d if
             hist_meta.get("gcp_horizon") else since_d)
    if hasattr(gcp_d, "date"):
        gcp_d = gcp_d.date()
    horizon = {"aws": since_d, "azure": since_d, "gcp": min(gcp_d, since_d)}

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
            mark(c, t(i.get("begin")), t(i.get("end")), i)
    for c, rows in live.items():
        for i in rows:
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
            lead = "" if started else "ongoing — "
            cells += ('<a class="d %s" href="%s" target="_blank" rel="noopener" '
                      'title="%s%s&#10;%s%s"></a>'
                      % (kind, e(incs[0].get("url", "#")), d.isoformat(), more,
                         lead, e(titles)))
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

    key = ('<div class="tl-key">'
           '<span><i class="d bad"></i>incident began</span>'
           '<span><i class="d bad cont"></i>still open</span>'
           '<span><i class="d ok"></i>nothing reported</span>'
           '<span><i class="d unk"></i>not recorded</span></div>')
    note = ('<p class="note-sm">A grey cell is a gap in the record, not a good '
            'day. AWS and Azure publish only incidents that are open at the '
            'moment you ask, so anything that started and finished before this '
            'log began on %s is invisible to it and always will be — an '
            'unmarked AWS or Azure day is not evidence of a quiet one. Google '
            'publishes resolved incidents too, so its record reaches back to '
            '%s.</p>'
            % (e(since_d.isoformat()), e(gcp_d.isoformat())))
    return '<div class="tl">%s</div>%s%s' % ("".join(out), key, note)


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


def region_grid(history, live):
    """Every region named in an incident, weighted by how often.

    Three things this has to get right, all of them about not implying more
    than the feeds actually say.

    Vocabulary. Google publishes machine region IDs (us-central1); AWS
    publishes place names ("UAE", "Bahrain"). Side by side those read as the
    same kind of label and are not, and "UAE" matches nothing a reader has in
    a Terraform file. fetch_status pulls the real code out of the ARN, so
    region_code is preferred and the place name is only a fallback.

    "global" is not a region. It is Google's marker for a non-regional
    service, and rendering it as a chip beside real regions invents a place.
    It is counted and reported separately.

    And the distribution is not what it looks like. Google names affected
    regions on every incident, AWS names one, Azure names none at all -- so
    the grid is overwhelmingly Google for the sole reason that Google
    discloses most. Read as a map of where things break, it punishes the
    vendor that tells you the most, which is the same trap as ranking clouds
    by how fast they acknowledge. Hence the caption: it says what the grid
    measures, and names Azure's absence rather than leaving a silent gap.
    """
    counts, glob, named = {}, {}, {}
    rows = list(history.values()) + [(dict(x, cloud=c))
                                     for c, v in live.items() for x in v]
    for i in rows:
        c = i.get("cloud") or "gcp"
        names = i.get("regions") or []
        if not names:
            # Prefer the ARN's region code over the published place name.
            one = i.get("region_code") or i.get("region")
            names = [one] if one else []
        if names:
            named[c] = named.get(c, 0) + 1
        for r in names:
            if r == "global":
                glob[c] = glob.get(c, 0) + 1
                continue
            counts[(c, r)] = counts.get((c, r), 0) + 1
    if not counts and not glob:
        return ""

    mx = max(counts.values()) if counts else 1
    cells = "".join('<div class="reg %s" style="--w:%.2f">'
                    '<span class="reg-n">%s</span><span class="reg-c">%d</span></div>'
                    % (c, n / mx, e(r), n)
                    for (c, r), n in sorted(counts.items(), key=lambda kv: -kv[1]))

    key = ('<div class="reg-key">'
           '<span><i class="aws"></i>AWS</span>'
           '<span><i class="azure"></i>Azure</span>'
           '<span><i class="gcp"></i>Google Cloud</span></div>')

    extra = ""
    if glob:
        bits = ", ".join("%s (%d)" % (LABEL[c], n) for c, n in sorted(glob.items()))
        extra = ('<p class="note-sm">Plus %d incident(s) marked <b>global</b> '
                 '— not a region, but Google’s label for a service that is '
                 'not regional: %s.</p>'
                 % (sum(glob.values()), e(bits)))

    said = ", ".join("%s %d" % (LABEL[c], named.get(c, 0)) for c in ORDER)
    caption = ('<p class="note-sm">This shows <b>where each vendor said an '
               'incident was</b>, not where incidents happen. Incidents naming '
               'any location: %s. Google publishes affected regions on every '
               'incident and Azure’s feed carries none at all, so a cloud '
               'appearing more often here is disclosing more, not breaking '
               'more.</p>' % e(said))
    return ('<div class="regs">%s</div>%s%s%s'
            % (cells, key, extra, caption))



# What each vendor publishes, scored against six things a reader needs.
# 1 = published as a field, 0.5 = present but buried in prose, 0 = absent.
# Derived by reading each feed, not by reputation: see the parsers above.
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




def postmortems(cssv="1"):
    """The vendors' own post-incident write-ups, as a wall of years.

    What this is NOT: a set of outage descriptions written here. Every word a
    reader sees in the dialog is the vendor's, quoted whole and linked back.
    Writing "what happened" in my own words from memory would produce exactly
    the kind of confident, unverifiable account this site exists to refuse --
    and an outage post-mortem is the worst possible place for it, because the
    details a reader wants (which region, which trigger, what changed
    afterwards) are precisely the ones that are easy to half-remember.

    Grouped by year rather than by cloud on purpose. By cloud it is three lists
    of different lengths, which reads as a scoreboard; by year it reads as what
    it is -- fifteen years of the industry writing down what broke, with the
    gaps and the density both visible.
    """
    if not os.path.exists(POSTMORTEMS):
        return ""
    try:
        data = json.load(io.open(POSTMORTEMS, encoding="utf-8"))
    except ValueError:
        return ""
    rows = data.get("postmortems") or []
    if not rows:
        return ""

    by_year = {}
    for r in rows:
        y = (r.get("date") or "")[:4] or "Undated"
        by_year.setdefault(y, []).append(r)

    def yr_key(y):
        return (0, 0) if y == "Undated" else (1, int(y))

    out = ""
    for y in sorted(by_year, key=yr_key, reverse=True):
        items = sorted(by_year[y], key=lambda r: r.get("date") or "", reverse=True)
        cards = ""
        hook_by_id = {h["id"]: h for h in hooks()}
        for r in items:
            # The shape of the disclosure is itself information: a vendor that
            # publishes headed sections has committed to answering the same
            # questions every time, and one that publishes an essay has not.
            n = len(r.get("sections") or [])
            shape = ("%d sections" % n) if n else "narrative"
            # The quoted line lives on the card itself rather than in a
            # separate "did you know" panel above. That panel showed 6 of these
            # 24 and every one of them was already here -- a strict subset,
            # duplicated. It could not replace the wall either, because the 18
            # AWS write-ups have no labelled cause section to quote from and
            # would have vanished. One component, every write-up, and the
            # interesting sentence where the thing it describes already is.
            key = "%s:%s" % (r.get("cloud", ""), r.get("id", ""))
            hk = hook_by_id.get(key)
            quote = ('<span class="pm-c-q">%s</span>' % e(hk["q"])) if hk else ""
            cards += (
                '<button class="pm-card %s" data-pm="%s" type="button">'
                '<span class="pm-c-cloud">%s</span>'
                '<span class="pm-c-title">%s</span>'
                '%s'
                '<span class="pm-c-shape">%s</span></button>'
                % (e(r.get("cloud", "")), e(key),
                   e(LABEL.get(r.get("cloud"), r.get("cloud", ""))),
                   e(r.get("title", ""))[:150], quote, e(shape)))
        out += ('<div class="pm-year"><div class="pm-y">%s</div>'
                '<div class="pm-cards">%s</div></div>' % (e(y), cards))

    counts = {}
    for r in rows:
        counts[r["cloud"]] = counts.get(r["cloud"], 0) + 1
    tally = ", ".join("%s %d" % (LABEL[c], counts.get(c, 0)) for c in ORDER)

    # Azure's single entry is not a quiet record, and saying so matters: its
    # history page shows one review at a time, so this grows only as new ones
    # appear. Left unexplained, "Microsoft 1" next to "AWS 18" reads as a claim
    # about reliability instead of a fact about a scraper's starting date.
    note = ('<p class="note-sm">Every word in these is the vendor’s own, '
            'quoted whole and linked back — nothing here is summarised or '
            'rewritten. Holding %s. AWS keeps a permanent index of its '
            'post-event summaries, which is why its record reaches back to '
            '2011. Azure publishes one review at a time and retains the rest '
            'behind its own navigation, so that count grows from the day this '
            'started rather than reaching backwards.</p>' % e(tally))

    dialog = (
        '<dialog id="pm-dialog" aria-labelledby="pm-title">'
        '<button class="pm-x" data-pm-close aria-label="Close">×</button>'
        '<div class="pm-body"></div></dialog>')

    return ('<div class="pm">%s</div>%s%s'
            '<script src="/intelligence/status/pm.js?v=%s" defer></script>'
            % (out, note, dialog, e(cssv)))


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
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600&amp;family=DM+Sans:wght@400;600&amp;family=DM+Mono&amp;display=swap" rel="stylesheet">
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
</head><body>
<nav>
  <a class="nav-logo" href="/intelligence/" aria-label="Cloud intelligence home">
    <img src="/favicon-transparent.png" alt="" width="30" height="30" aria-hidden="true">
    <span class="brand-name">Jayanth Katta</span>
  </a>
  <ul class="nav-links">
    <li><a href="/">Portfolio</a></li>
    <li><a href="/blog/">Blog</a></li>
    <li><a href="/intelligence/">Intelligence</a></li>
    <li><button class="theme-toggle" onclick="toggleTheme()" id="theme-btn" type="button">
      <span id="theme-icon">&#9681;</span><span id="theme-label">Light</span>
    </button></li>
  </ul>
</nav>
<div class="wrap">
  <p class="eyebrow"><span class="dot"></span>Cloud status</p>
  <h1>Is anything broken right now?</h1>
  <p class="sub">Live incidents across AWS, Azure and Google Cloud, read from each
     vendor&rsquo;s own status feed. Nothing here is summarised or inferred &mdash;
     the wording is theirs.</p>
  <p class="fresh__STALE__">Last checked __AGE__ &middot; refresh is scheduled hourly and can run late, so this timestamp is the one to trust__WARN__</p>
  __CARDS__
  __BODY__
  <h2>Last 90 days</h2>
  <p class="sub">One cell per day. A cell is marked only where a vendor published an
     incident that was open on that day &mdash; an unmarked cell means nothing was
     reported, not that anything was verified healthy.</p>
  __TIMELINE__

  <h2>Where incidents happened</h2>
  <p class="sub">Every region named in an incident since this started recording.
     Depth of colour is the count. A region that is not listed has had nothing
     reported, which is not the same as nothing happening.</p>
  __REGIONS__

  <h2>What the vendors do and don&rsquo;t tell you</h2>
  <p class="sub">The three publish very different amounts, and that difference is
     itself worth knowing when you decide how far to trust a status page.</p>
  __DISCLOSURE__
</section>

<section class="sec">
  <h2>When it broke, what did they say afterwards?</h2>
  <p class="lede">The write-ups the three clouds published after their own
  outages &mdash; what happened, what caused it, and what they changed. Their
  words, not mine: open one and you get the published text in full, with a
  link to the original.</p>
  __POSTMORTEMS__
  <div class="note"><strong>Why the timings below are Google&rsquo;s only.</strong>
     Google publishes when an incident <em>began</em> and, separately, when it first
     said something publicly, so the gap between the two is a real number. AWS&rsquo;s
     status data carries no start time distinct from its first announcement, making
     that gap structurally zero; Azure&rsquo;s feed carries no start time at all.
     Ranking all three would put AWS first for disclosing less, so only the cloud
     that supplies the inputs is measured.</div>
  __CADENCE__
  __STATS__
  <h2>Sources</h2>
  <div class="tw"><table><tr><th>Status page</th><th>Endpoint we read</th><th>Last response</th><th>Read</th></tr>__SRC__</table></div>
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
<script src="/blog/assets/site-footer.js" data-site-footer></script>
</body></html>
"""


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

    src = ""
    for c in ORDER:
        s = sources.get(c, {})
        resp = ("HTTP %s" % s.get("http")) if s.get("ok") else                '<span style="color:#D4A05A">failed</span>'
        u = s.get("url", "")
        src += ('<tr><td><a href="%s" target="_blank" rel="noopener">%s</a></td>'
                '<td>%s</td><td>%s</td><td>%s</td></tr>'
                % (e(HUMAN.get(c, u)), e(LABEL[c]), e(u[:56]), resp,
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
                .replace("__REGIONS__", region_grid(hist, clouds))
                .replace("__DISCLOSURE__", disclosure())
                .replace("__POSTMORTEMS__", postmortems(cssv))
                .replace("__CADENCE__", cadence())
                .replace("__STATS__", stats)
                .replace("__SRC__", src))

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
