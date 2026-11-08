#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build /intelligence/services/ -- what the three clouds are betting on.

    python scripts/build_services_page.py

Thirteen universal jobs down the side, three clouds across. The rows do the
comparing, which is the whole point: three separate top-ten lists tell a
reader what is big inside each cloud and nothing at all about how the three
answer the same question.

WHAT THIS MEASURES, AND WHAT IT DOES NOT
----------------------------------------
Vendor attention. Not adoption.

Bedrock at 7.4% means AWS shipped a lot of Bedrock in ninety days. It does
not mean anyone runs it, and the page says so in its own words rather than
leaving a reader to assume. The question people actually ask -- which
services do most companies use -- cannot be answered from any feed, and the
honest move is to leave that axis off rather than imply it. Adoption numbers
exist (Flexera, the CNCF survey, Datadog, Stack Overflow) but they are
annual, licensed and citable rather than fetchable, so they would be a
different kind of claim sitting next to this one, not blended into it.

THREE THINGS THAT WOULD MAKE THIS PAGE LIE, AND WHAT STOPS THEM
---------------------------------------------------------------
1. RAW COUNTS ARE NOT COMPARABLE ACROSS CLOUDS. GCP's combined feed is
   day-granular and explodes into one row per note, so a 90-day window holds
   about 2,300 GCP rows against 625 for AWS. That is the feed's shape, not
   Google shipping four times as much. Every number here is a share of its
   OWN cloud's output for that reason.

2. ONE NOTE REPEATED IS NOT FOUR NOTES. Container-Optimized OS alone would
   top the GCP column on raw rows -- one kernel CVE fixed across four
   milestones arrives as four separate notes. Counting is rolled up per
   service family on the normalised headline, so a repeated note counts once.

3. THE STORE IS YOUNGER THAN A YEAR. August 2026 is the first month with
   real volume (858 rows, against 82 in June). A twelve-month sparkline
   would draw a flat line and then a cliff, which reads as a service taking
   off when it is really the store starting. The series window is the
   store's own usable life and the page prints it.

THE TWELVE JOBS ARE EDITORIAL AND MUST BE VISIBLE AS SUCH
---------------------------------------------------------
The store tags service names. Nothing in the data says S3 and Cloud Storage
answer the same question -- that is a judgement, and the page labels it one.
It is also the part most likely to rot silently: a service rename empties a
cell, and an empty cell reads as "this cloud does not do that". That is what
check_services_jobs.py exists to refuse.
"""
import collections
import datetime
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

STORE = os.path.join(ROOT, "intelligence", "news.json")
OUT_DIR = os.path.join(ROOT, "intelligence", "services")

WINDOW_DAYS = 90

# The first month the store holds enough to plot. Everything before it is a
# handful of backfilled rows, and plotting them draws growth that did not
# happen. Raise this only when the early months stop being misleading.
SERIES_FROM = "2026-08"

CLOUDS = (("aws", "AWS", "#C4A484"),
          ("azure", "Azure", "#5B7B9A"),
          ("gcp", "Google Cloud", "#8A9A5B"))

# (job, aws aliases, azure aliases, gcp aliases)
#
# EVERY ALIAS MUST BE A NAME THE TAGGER ACTUALLY PRODUCES, and
# check_services_jobs.py refuses the build otherwise. The first alias is
# also the cell's label, so a dead one does not merely miss rows -- it
# prints a service name that does not exist next to a real number.
#
# That check found five dead aliases the first time it ran, in this very
# table: "Azure OpenAI" and "AI Foundry" (Microsoft renamed it to Microsoft
# Foundry), "Cloud IAM" (Google writes "Identity and Access Management"),
# "Fargate" and "SQS" (the store has never carried either as a tag, so the
# AWS messaging cell was labelled SQS while being counted entirely from
# EventBridge).
#
# Aliases, not names: the tagger fragments a family -- S3, S3 Tables,
# S3 Express and S3 Vectors are all S3 -- and Google writes Cloud SQL per
# engine. Matching is substring-on-tag, so the shortest distinctive form
# earns its place and the first alias is what the cell is labelled with.
JOBS = [
    # Compute first. The twelve-row draft went straight to object storage,
    # and a page about what the clouds ship with no row for the virtual
    # machine is a page missing the oldest thing any of them sells.
    ("Virtual machines",
     ["EC2"],
     ["Virtual Machines"],
     ["Compute Engine"]),
    ("Object storage",
     ["S3"],
     ["Azure Storage", "Azure Blob Storage", "Azure Data Lake Storage"],
     ["Cloud Storage", "Storage Transfer Service"]),
    ("Managed Postgres",
     ["RDS", "Aurora"],
     ["Azure Database for PostgreSQL", "Azure PostgreSQL"],
     ["Cloud SQL for PostgreSQL", "AlloyDB for PostgreSQL"]),
    ("Kubernetes",
     ["EKS"],
     ["AKS", "Azure Kubernetes"],
     ["Google Kubernetes Engine"]),
    ("Containers, serverless",
     ["ECS"],
     ["Azure Container Apps"],
     ["Cloud Run"]),
    ("Serverless functions",
     ["Lambda"],
     ["Azure Functions"],
     ["Cloud Run functions"]),
    ("Data warehouse",
     ["Redshift"],
     ["Microsoft Fabric", "Azure Synapse"],
     ["BigQuery"]),
    ("GenAI platform",
     ["Bedrock"],
     ["Microsoft Foundry"],
     ["Vertex AI", "Gemini Enterprise"]),
    ("Identity",
     ["IAM"],
     ["Microsoft Entra"],
     ["Identity and Access Management"]),
    ("CDN and edge",
     ["CloudFront"],
     ["Azure Front Door"],
     ["Cloud CDN", "Media CDN"]),
    ("Secrets",
     ["Secrets Manager"],
     ["Azure Key Vault"],
     ["Secret Manager"]),
    ("Observability",
     ["CloudWatch"],
     ["Azure Monitor"],
     ["Cloud Monitoring"]),
    ("Messaging",
     ["EventBridge"],
     ["Azure Service Bus"],
     ["Pub/Sub"]),
]


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def norm(t):
    """Normalise a headline so one note repeated is one note."""
    return re.sub(r"\s+", " ",
                  re.sub(r"[^a-z0-9 ]", "", (t or "").lower())).strip()


def matches(tag, aliases):
    t = (tag or "").lower()
    return any(t == a.lower() or t.startswith(a.lower() + " ")
               or a.lower() in t for a in aliases)


def months_from(first, today):
    out, y, m = [], int(first[:4]), int(first[5:7])
    while (y, m) <= (today.year, today.month):
        out.append("%04d-%02d" % (y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def load_items():
    d = json.load(io.open(STORE, encoding="utf-8"))
    return d.get("items", []), (d.get("generated") or "")


def measure(items, today):
    since = (today - datetime.timedelta(days=WINDOW_DAYS)).isoformat()
    months = months_from(SERIES_FROM, today)
    series_since = SERIES_FROM + "-01"

    # Denominator: that cloud's own rolled-up output in the window.
    totals = {}
    for cloud, _, _ in CLOUDS:
        seen = set()
        for i in items:
            if i.get("c") == cloud and i.get("d", "") >= since:
                seen.add(norm(i.get("t")))
        totals[cloud] = len(seen)

    rows = []
    for job, a, z, g in JOBS:
        cells = []
        for (cloud, _, colour), aliases in zip(CLOUDS, (a, z, g)):
            seen, win, per_month = set(), set(), collections.Counter()
            for i in items:
                if i.get("c") != cloud:
                    continue
                day = i.get("d", "")
                if day < series_since:
                    continue
                if not any(matches(s, aliases) for s in (i.get("s") or [])):
                    continue
                k = norm(i.get("t"))
                if k in seen:
                    continue
                seen.add(k)
                per_month[day[:7]] += 1
                if day >= since:
                    win.add(k)
            n = len(win)
            cells.append({
                "cloud": cloud, "colour": colour, "label": aliases[0],
                "n": n,
                "share": (100.0 * n / totals[cloud]) if totals[cloud] else 0.0,
                "series": [per_month.get(m, 0) for m in months],
            })
        rows.append({"job": job, "cells": cells})
    return rows, totals, months, since


def spark(series, colour, w=70, h=18):
    if not series or max(series) == 0:
        return ""
    m = float(max(series))
    step = w / float(max(len(series) - 1, 1))
    pts = " ".join("%.1f,%.1f" % (i * step, h - (v / m) * (h - 3) - 1.5)
                   for i, v in enumerate(series))
    return ('<svg class="sv-spk" viewBox="0 0 %d %d" '
            'preserveAspectRatio="none" aria-hidden="true">'
            '<polyline points="%s" fill="none" stroke="%s" stroke-width="1.4" '
            'stroke-linejoin="round"/></svg>' % (w, h, pts, colour))


def sources_html(items):
    """One row per domain the announcements actually came from.

    Derived from the stored rows, never a hand-kept list. A hand-kept list
    of feeds goes stale the first time one is added or retired, silently,
    and always in the direction of overstating coverage. The host here is
    the one the items themselves link to, the count is what is held, and
    the date is the newest thing seen -- so a feed that dies shows as a
    stale date instead of disappearing.

    This page had no sourcing at all when it shipped. It asks a reader to
    accept thirteen rows of percentages about three companies; "measured
    from the vendors' own feeds" is the kind of sentence that sounds like
    sourcing without being it.
    """
    dom = {}
    for i in items:
        u = i.get("u") or ""
        if not u.startswith("http"):
            continue
        host = u.split("/")[2]
        d = dom.setdefault(host, {"clouds": set(), "n": 0, "last": ""})
        d["clouds"].add({"aws": "AWS", "azure": "Azure",
                         "gcp": "Google Cloud"}.get(i.get("c"), i.get("c")))
        d["n"] += 1
        if (i.get("d") or "") > d["last"]:
            d["last"] = i.get("d") or ""
    rows = []
    for host, d in sorted(dom.items(), key=lambda kv: -kv[1]["n"]):
        if d["n"] < 5:
            continue
        rows.append("<tr><th>%s</th><td>%s</td><td>%s</td><td>%s</td></tr>"
                    % (esc(host), esc(", ".join(sorted(d["clouds"]))),
                       "{:,}".format(d["n"]), esc(d["last"])))
    return (
        '<h2 class="sv-h2" id="sources">Where this comes from</h2>'
        '<p class="sv-note">Every announcement counted here was read from a '
        'feed published by the cloud itself &mdash; its release notes, its '
        'product blogs, its security bulletins. Nothing is an analyst '
        'estimate and nothing is scraped from a third party, with one '
        'exception noted below. The table is built from the stored items, '
        'so a feed that stops publishing shows up as a stale date rather '
        'than quietly vanishing from the list.</p>'
        '<div class="sv-scroll"><table class="sv-src"><thead><tr>'
        '<th>Domain</th><th>Cloud</th><th>Items held</th><th>Newest</th>'
        '</tr></thead><tbody>%s</tbody></table></div>'
        '<p class="sv-note"><b>The exception:</b> the Azure side also reads '
        'release feeds from GitHub &mdash; the Azure organisation&rsquo;s own '
        'repositories, plus HashiCorp&rsquo;s Terraform AzureRM provider, '
        'which is the only source on this page not published by the cloud '
        'vendor. It is authoritative for its own releases and nothing '
        'else.</p>' % "".join(rows))


def grid_html(rows):
    b = ['<div class="sv-scroll"><table class="sv-grid">',
         "<thead><tr><th>The job</th>"]
    for _, name, _ in CLOUDS:
        b.append("<th>%s</th>" % esc(name))
    b.append("</tr></thead><tbody>")
    for r in rows:
        b.append("<tr><th>%s</th>" % esc(r["job"]))
        top = max(c["share"] for c in r["cells"]) or 1.0
        for c in r["cells"]:
            # A cell with one item or none is not a finding, and rendering
            # it at full strength invites a reader to treat it as one.
            thin = " thin" if c["n"] <= 1 else ""
            b.append('<td class="sv-cell%s">' % thin)
            b.append('<div class="sv-svc">%s</div>' % esc(c["label"]))
            b.append('<div class="sv-bar"><i style="width:%.0f%%;'
                     'background:%s"></i></div>'
                     % (100.0 * c["share"] / top, c["colour"]))
            b.append('<div class="sv-num"><b>%.1f%%</b><span>%d item%s</span>'
                     "%s</div>"
                     % (c["share"], c["n"], "" if c["n"] == 1 else "s",
                        spark(c["series"], c["colour"])))
            b.append("</td>")
        b.append("</tr>")
    b.append("</tbody></table></div>")
    return "\n".join(b)


STYLE = """
<style>
  .sv-wrap { max-width: 1120px; margin: 0 auto; padding: 0 1.1rem 3rem; }
  .sv-head { padding: 1.6rem 0 1rem; }
  .sv-head h1 { font-size: clamp(1.5rem, 4vw, 2.1rem); margin: 0 0 .35rem;
                font-weight: 500; }
  .sv-sub { color: var(--muted, #6C7671); margin: 0 0 .5rem;
            max-width: 60ch; }
  .sv-meta { font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
             font-size: .74rem; color: var(--muted, #6C7671); margin: 0; }
  .sv-scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; }
  .sv-grid { width: 100%; border-collapse: collapse; min-width: 680px; }
  .sv-grid th { text-align: left; font-weight: 400; font-size: .82rem;
                padding: .55rem .6rem; white-space: nowrap;
                border-bottom: 1px solid var(--bd, #2F3131);
                vertical-align: middle; }
  .sv-grid thead th { font-size: .68rem; letter-spacing: .07em;
                      text-transform: uppercase;
                      color: var(--muted, #6C7671); }
  .sv-cell { padding: .5rem .6rem; width: 26%; vertical-align: top;
             border-bottom: 1px solid var(--bd, #2F3131); }
  .sv-cell.thin { opacity: .45; }
  .sv-svc { font-size: .78rem; margin-bottom: .25rem; }
  .sv-bar { height: 4px; border-radius: 2px; overflow: hidden;
            background: rgba(128,128,128,.18); }
  .sv-bar i { display: block; height: 100%; }
  .sv-num { display: flex; align-items: center; gap: .45rem;
            margin-top: .25rem; font-size: .68rem;
            font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
            color: var(--muted, #6C7671); }
  .sv-num b { font-weight: 500; color: var(--fg, #E8E4DC); }
  .sv-spk { width: 70px; height: 18px; margin-left: auto; flex: none; }
  .sv-h2 { font-size: 1.05rem; font-weight: 500; margin: 2rem 0 .4rem; }
  .sv-src { width: 100%; border-collapse: collapse; min-width: 520px;
            font-size: .82rem; }
  .sv-src th, .sv-src td { text-align: left; font-weight: 400;
            padding: .45rem .6rem;
            border-bottom: 1px solid var(--bd, #2F3131); }
  .sv-src thead th { font-size: .68rem; letter-spacing: .07em;
            text-transform: uppercase; color: var(--muted, #6C7671); }
  .sv-note { margin: 1.4rem 0 0; padding: .9rem 1rem;
             border: 1px solid var(--bd, #2F3131); border-radius: 8px;
             background: rgba(128,128,128,.05); font-size: .82rem;
             line-height: 1.65; color: var(--muted, #6C7671); }
  .sv-note h2 { font-size: .95rem; font-weight: 500; margin: 0 0 .5rem;
                color: var(--fg, #E8E4DC); }
  .sv-note p { margin: 0 0 .6rem; }
  .sv-note p:last-child { margin-bottom: 0; }
  .sv-note b { color: var(--fg, #E8E4DC); font-weight: 500; }
  body.light .sv-num b, body.light .sv-note h2,
  body.light .sv-note b { color: #1C2120; }
</style>
"""


def build():
    from asset_version import JS_VERSION
    import build_news_page as bnp
    import build_events_page as bep

    items, generated = load_items()
    today = datetime.date.today()
    rows, totals, months, since = measure(items, today)

    head = bnp.PAGE[:bnp.PAGE.index("</head>")]
    head = re.sub(r"<title>.*?</title>",
                  "<title>What the three clouds are betting on &mdash; "
                  "AWS, Azure and Google Cloud service attention compared "
                  "| Jayanth Katta</title>", head, count=1, flags=re.S)
    head = re.sub(r'<meta name="description" content=".*?">',
                  '<meta name="description" content="Twelve jobs every '
                  'cloud has to answer, and how much of its own output AWS, '
                  'Azure and Google Cloud spend on each. Measured from the '
                  'vendors&rsquo; own announcement feeds, not from a survey.">',
                  head, count=1, flags=re.S)
    head = re.sub(r'<link rel="canonical" href=".*?">',
                  '<link rel="canonical" '
                  'href="https://jayanthkatta.com/intelligence/services/">',
                  head, count=1, flags=re.S)
    head = head.replace("__JSV__", JS_VERSION)
    head = head.replace("__RESERVE_WIDE__", "0").replace("__RESERVE__", "0")
    head = re.sub(r"__[A-Z_]+__", "", head)

    nav = bnp.PAGE[bnp.PAGE.index("<nav>"):
                   bnp.PAGE.index("</nav>") + len("</nav>")]
    nav = nav.replace(
        '<li><a href="/intelligence/whats-new/" class="active" '
        'aria-current="page">What&rsquo;s new</a></li>',
        '<li><a href="/intelligence/whats-new/">What&rsquo;s new</a></li>')
    nav = nav.replace(
        '<li><a href="/intelligence/">Intelligence</a></li>',
        '<li><a href="/intelligence/" class="active" '
        'aria-current="page">Intelligence</a></li>')

    b = ['<main class="sv-wrap">', '<div class="sv-head">',
         "<h1>What the three clouds are betting on</h1>",
         '<p class="sv-sub">Thirteen jobs every cloud has to answer, and how '
         'much of its own output each one spends on them. Measured from the '
         'vendors&rsquo; own announcement feeds &mdash; <b>what they '
         'shipped, not what anyone runs</b>.</p>',
         '<p class="sv-meta">%s-day window from %s &middot; store generated '
         "%s &middot; rolled-up announcements &mdash; AWS %s &middot; "
         "Azure %s &middot; Google Cloud %s</p>"
         % (WINDOW_DAYS, esc(since), esc(generated),
            "{:,}".format(totals["aws"]), "{:,}".format(totals["azure"]),
            "{:,}".format(totals["gcp"])),
         "</div>", grid_html(rows)]

    b.append('<div class="sv-note">')
    b.append("<h2>How to read this, and how it could mislead you</h2>")
    b.append("<p>The percentage is each service&rsquo;s share of <b>its own "
             "cloud&rsquo;s</b> output, never a count. Google&rsquo;s "
             "combined feed is day-granular and produces several times as "
             "many rows as AWS&rsquo;s, so raw totals would say Google ships "
             "four times as much. It does not; the feed is simply shaped "
             "differently.</p>")
    b.append("<p>One announcement repeated is counted once. Without that, "
             "Container-Optimized OS alone would top the Google column "
             "&mdash; a single kernel fix shipped across four releases "
             "arrives as four notes.</p>")
    b.append("<p><b>This is vendor attention, not adoption.</b> A high "
             "share means that cloud spent a lot of its announcements there. "
             "It says nothing about how many companies run the service. That "
             "question needs survey data, which is annual and citable rather "
             "than measurable from a feed, so it is left off rather than "
             "guessed at.</p>")
    b.append("<p>Faded cells carry one item or none &mdash; too thin to read "
             "as a finding. The thirteen jobs, and which service answers each, "
             "are an editorial judgement: nothing in the data says S3 and "
             "Cloud Storage are the same question.</p>")
    b.append("<p>The sparkline runs from %s, the first month the store holds "
             "enough to plot. A longer window would draw growth that belongs "
             "to this page, not to the services.</p>" % esc(months[0]))
    b.append("</div>")
    b.append(sources_html(items))
    b.append("</main>")

    theme_first = ("<script>try{if(localStorage.getItem('theme')==='light')"
                   "document.body.classList.add('light')}catch(e){}"
                   "</script>")
    html = (head + STYLE + "</head>\n<body>\n" + theme_first + nav
            + "\n" + "\n".join(b) + bep.tail_html(JS_VERSION,
                                                  page_id="intelligence-services"))

    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)
    out = os.path.join(OUT_DIR, "index.html")
    with io.open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html)
    filled = sum(1 for r in rows for c in r["cells"] if c["n"] > 1)
    print("  %d job(s), %d of %d cells carry more than one item -> %s"
          % (len(rows), filled, len(rows) * 3, os.path.relpath(out, ROOT)))
    print("  %.1fKB" % (os.path.getsize(out) / 1024.0))
    return 0


if __name__ == "__main__":
    sys.exit(build())
