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
import statistics
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STATUS = os.path.join(ROOT, "intelligence", "status.json")
HISTORY = os.path.join(ROOT, "intelligence", "status-history.json")
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
STALE_MINUTES = 60


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
                 ("Region", e(i.get("region", "")))]
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
  <p class="fresh__STALE__">Last checked __AGE__ &middot; refreshed every 15 minutes__WARN__</p>
  __CARDS__
  __BODY__
  <h2>What the vendors do and don&rsquo;t tell you</h2>
  <p class="sub">The three publish very different amounts, and that difference is
     itself worth knowing when you decide how far to trust a status page.</p>
  <div class="tw"><table><tr><th>Cloud</th><th>Incident start</th><th>Update history</th>
  <th>Affected services</th><th>Regions</th></tr>
  <tr><td>AWS</td><td>Not published separately</td><td>Yes</td>
      <td>Coarse (&ldquo;Multiple services&rdquo;)</td><td>Yes</td></tr>
  <tr><td>Azure</td><td>No</td><td>Feed item only</td><td>In prose</td><td>In prose</td></tr>
  <tr><td>Google Cloud</td><td>Yes</td><td>Yes, timestamped</td>
      <td>Yes, itemised</td><td>Yes, itemised</td></tr></table></div>
  <div class="note"><strong>Why the timings below are Google&rsquo;s only.</strong>
     Google publishes when an incident <em>began</em> and, separately, when it first
     said something publicly, so the gap between the two is a real number. AWS&rsquo;s
     status data carries no start time distinct from its first announcement, making
     that gap structurally zero; Azure&rsquo;s feed carries no start time at all.
     Ranking all three would put AWS first for disclosing less, so only the cloud
     that supplies the inputs is measured.</div>
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
    hist = {}
    if os.path.exists(HISTORY):
        hist = (json.load(io.open(HISTORY, encoding="utf-8")) or {}).get("incidents", {})

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
    stats = ""
    if tr["ack_median"] is not None:
        stats = ('<div class="stat">'
                 '<div class="st"><div class="n">Median time to first word</div>'
                 '<div class="v">%d min</div><div class="w">across %d Google incident%s</div></div>'
                 '<div class="st"><div class="n">Slowest acknowledgement</div>'
                 '<div class="v">%s</div><div class="w">the worst in that set</div></div>'
                 '<div class="st"><div class="n">Median time to resolve</div>'
                 '<div class="v">%s</div><div class="w">start to resolution</div></div>'
                 '</div>' % (round(tr["ack_median"]), len(tr["acks"]),
                             "" if len(tr["acks"]) == 1 else "s",
                             dur(max(tr["acks"]) / 60), dur(tr["dur_median"])))

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
                .replace("__WARN__", " &middot; older than expected, several refreshes may have failed"
                         if stale else "")
                .replace("__CARDS__", cards)
                .replace("__BODY__", body)
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
