#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render /reinvent-2026/ from the catalog store.

    python scripts/build_reinvent_page.py

Why this exists
---------------
The page this replaces was a bookmark. It said "Open catalog" six times, and
everything it offered the official catalog does better -- so it added nothing
a browser favourite would not. Asked for instead:

    "a unified web page ... they can search for a specific service, and the
     sessions are across multiple venues within Vegas, MGM Grand and all
     those stuff ... based on the role or based on the service type ...
     some creative way that adds value to my team during that whole event."

So this page holds the data, and it is built around the one question the
official catalog cannot answer.

THE THING THE CATALOG WILL NOT DO. Every session carries a room string --
"Caesars Palace | Promenade Level | Roman I" -- and a start and end minute.
The catalog will let you favourite a session ending 10:00 at MGM Grand and
another starting 10:30 at the Venetian without a word, because it never
compares the two. Those are at opposite ends of the Strip. This page walks
each day of your plan in order and says so.

WHAT IS A FACT HERE AND WHAT IS AN ESTIMATE. The two are not mixed, because
only one of them is checkable:

  FACT      These two sessions are at different properties, and the gap
            between them is N minutes. That is arithmetic on AWS's own
            published times and rooms, and it is what the warning states.

  ESTIMATE  How long the hop actually takes. AWS was checked and does not
            publish per-venue minutes -- its FAQ says only "allow for
            additional travel time between venues" and that shuttles "run
            continuously during conference hours". So the defaults below
            come from the campus geography, they are labelled as estimates
            on the page, and the reader can change them.

That distinction is the whole reason to trust the warning. A page that
quietly invents a shuttle timetable and presents it as AWS's would be worse
than no page, and it is exactly the sort of claim this repo's checks exist
to stop.

ROLE LANES, NOT ROLE FACETS. The catalog publishes 18 roles and
"Solution / Systems Architect" returns 729 sessions, which is not a filter.
The three lanes below are service clusters instead, and they are sharp:
connectivity, platform and compute land at a size a person can actually read
through. They are a starting point, not a cage -- every lane is one tap away
from the full catalog.
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(ROOT, "intelligence", "reinvent2026.json")
OUTDIR = os.path.join(ROOT, "reinvent-2026")

EVENT = {
    "name": "AWS re:Invent 2026",
    "start": "2026-11-30",
    "end": "2026-12-04",
    "city": "Las Vegas, NV",
}

# Each lane is matched case-insensitively as a substring against the
# catalog's own service names, so "elastic compute" catches
# "Amazon Elastic Compute Cloud (Amazon EC2)" without hardcoding the
# parenthetical AWS likes to change.
LANES = [
    {
        "id": "connectivity",
        "name": "Connectivity",
        "blurb": "Hybrid links, transit, edge, DNS and the paths between them.",
        "match": ["transit gateway", "direct connect", "cloud wan", "vpn",
                  "privatelink", "virtual private cloud", "vpc lattice",
                  "route 53", "global accelerator", "cloudfront",
                  "network firewall"],
    },
    {
        "id": "platform",
        "name": "Platform",
        "blurb": "Landing zones, identity, governance, observability, config.",
        "match": ["identity and access", "organizations", "control tower",
                  "cloudformation", "cloudwatch", "aws config", "cloudtrail",
                  "systems manager", "service catalog", "appconfig",
                  "well-architected", "trusted advisor"],
    },
    {
        "id": "compute",
        "name": "Compute / managed",
        "blurb": "EC2, containers, serverless and day-2 operations.",
        "match": ["elastic compute", "elastic container", "elastic kubernetes",
                  "lambda", "auto scaling", "fargate", "batch", "outposts",
                  "graviton", "image builder", "lightsail", "app runner"],
    },
]

# Minutes to allow between two sessions. ESTIMATES -- see the module docstring;
# AWS publishes none. Five venues sit in one walkable-or-short-shuttle run from
# Encore down to Caesars Palace; MGM Grand is the outlier, south by Tropicana.
SAME_VENUE = 10       # these properties are large; room to room is not free
NEAR = 30             # within the northern cluster
FAR = 45              # anything involving MGM Grand
OUTLIER = "MGM Grand"


def read_store():
    if not os.path.exists(STORE):
        raise SystemExit(
            "  %s does not exist. Run:\n      python scripts/fetch_reinvent.py"
            % os.path.relpath(STORE, ROOT))
    return json.load(io.open(STORE, encoding="utf-8"))


def lane_indexes(store):
    """Resolve each lane's substrings to service indexes in this store.

    Done at build time rather than in the browser so that a lane which has
    stopped matching anything is a build failure here, not a silently empty
    tab for a reader.
    """
    services = store["facets"]["Services"]
    out = {}
    for lane in LANES:
        idx = [i for i, name in enumerate(services)
               if any(m in name.lower() for m in lane["match"])]
        if not idx:
            raise SystemExit(
                "  lane %r matched none of the %d service names in the store. "
                "AWS has renamed something; fix LANES rather than shipping an "
                "empty tab." % (lane["name"], len(services)))
        out[lane["id"]] = idx
    return out


def lane_counts(store, lanes):
    """How many sessions each lane holds, for the tab labels."""
    out = {}
    for lane_id, idx in lanes.items():
        want = set(idx)
        out[lane_id] = sum(1 for s in store["sessions"]
                           if want.intersection(s["sv"]))
    return out


def esc(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def pretty_date(iso):
    import datetime
    d = datetime.date(*[int(x) for x in iso.split("-")])
    return d.strftime("%a %-d %b") if os.name != "nt" else d.strftime(
        "%a %#d %b")


def build():
    store = read_store()
    lanes = lane_indexes(store)
    counts = lane_counts(store, lanes)
    sessions = store["sessions"]

    days = sorted({w["d"] for s in sessions for w in s["when"]})
    scheduled = sum(1 for s in sessions if s["when"])

    os.makedirs(OUTDIR, exist_ok=True)

    # The page reads the store in place, at its absolute path, rather
    # than getting a copy beside it. A copy meant the same 1.3 MB shipped
    # twice, and -- worse -- it could go stale against the store it was
    # copied from, which is the kind of drift nothing here would notice.

    config = {
        "lanes": [{"id": l["id"], "name": l["name"], "blurb": l["blurb"],
                   "services": lanes[l["id"]], "count": counts[l["id"]]}
                  for l in LANES],
        "travel": {"same": SAME_VENUE, "near": NEAR, "far": FAR,
                   "outlier": OUTLIER},
        "days": days,
        "event": EVENT,
    }

    html = PAGE.replace("__CONFIG__", json.dumps(config, separators=(",", ":")))
    html = html.replace("__TOTAL__", "{:,}".format(len(sessions)))
    html = html.replace("__SCHEDULED__", "{:,}".format(scheduled))
    html = html.replace("__CAPTURED__", esc(store.get("captured", "")))
    html = html.replace("__VENUES__", esc(", ".join(sorted(store["venues"]))))
    html = html.replace("__SERVICES__", str(len(store["facets"]["Services"])))
    html = html.replace("__LANETABS__", lane_tabs(config))
    html = html.replace("__FAR__", str(FAR))
    html = html.replace("__NEAR__", str(NEAR))
    html = html.replace("__SAME__", str(SAME_VENUE))
    html = html.replace("__OUTLIER__", esc(OUTLIER))

    write(os.path.join(OUTDIR, "index.html"), html)
    write(os.path.join(OUTDIR, "page.css"), CSS)
    write(os.path.join(OUTDIR, "app.js"), APP)

    print("  reinvent-2026/  %d sessions, %d scheduled, %d day(s)"
          % (len(sessions), scheduled, len(days)))
    for lane in LANES:
        print("    %-18s %4d session(s) across %d service(s)"
              % (lane["name"], counts[lane["id"]], len(lanes[lane["id"]])))
    for name in ("index.html", "page.css", "app.js"):
        p = os.path.join(OUTDIR, name)
        print("    %-12s %7.1f KB" % (name, os.path.getsize(p) / 1024.0))
    print("    %-12s %7.1f KB  (read in place, not copied)"
          % ("the store", os.path.getsize(STORE) / 1024.0))
    return 0


def lane_tabs(config):
    # The "Everything" count is filled in by the app once the store loads,
    # so the number and the data it describes can never disagree.
    out = ['<button class="lane" data-lane="all" aria-pressed="true">'
           '<span class="ln">Everything</span>'
           '<span class="lc" data-count="all">&nbsp;</span></button>']
    for lane in config["lanes"]:
        out.append(
            '<button class="lane" data-lane="%s" aria-pressed="false">'
            '<span class="ln">%s</span>'
            '<span class="lc" data-count="%s">%d</span>'
            '<span class="lb">%s</span></button>'
            % (esc(lane["id"]), esc(lane["name"]), esc(lane["id"]),
               lane["count"], esc(lane["blurb"])))
    return "\n ".join(out)


def write(path, text):
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


# ---------------------------------------------------------------- the page

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#121816">
<meta name="color-scheme" content="dark">
<title>re:Invent 2026 planner - Jayanth Katta</title>
<link rel="canonical" href="https://jayanthkatta.com/reinvent-2026/">
<meta name="description" content="All __TOTAL__ AWS re:Invent 2026 sessions, searchable by service and filtered into connectivity, platform and compute lanes - with a plan that checks whether you can actually get between venues in time.">
<meta property="og:title" content="re:Invent 2026 planner">
<meta property="og:description" content="All __TOTAL__ sessions, searchable by service, with venue-hop checking the official catalog does not do.">
<meta property="og:url" content="https://jayanthkatta.com/reinvent-2026/">
<link rel="icon" href="/favicon-transparent.png" type="image/png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="./page.css">
</head>
<body>
<main class="page">

 <header class="header">
  <p class="eyebrow">jayanthkatta.com</p>
  <h1>re:Invent 2026</h1>
  <p class="lede">Every session in the official catalog, searchable by service
   and grouped the way our teams actually split &mdash; with one thing the
   catalog will not do for you: tell you when two sessions you picked are at
   opposite ends of the Strip.</p>
  <ul class="facts">
   <li><span>When</span><strong>Nov 30 &ndash; Dec 4, 2026</strong></li>
   <li><span>Where</span><strong>Las Vegas, NV</strong></li>
   <li><span>Sessions</span><strong>__TOTAL__ <em>(__SCHEDULED__ scheduled)</em></strong></li>
   <li><span>Venues</span><strong>__VENUES__</strong></li>
  </ul>
 </header>

 <!-- Written by the page itself, in the reader's browser, from the capture
      timestamp in the store. Deliberately not baked in at build time: a
      build-time string says how old the data was when the page was made,
      which is the one number that is always reassuring and never true. -->
 <p id="fresh" class="fresh" role="status">Checking how current this is&hellip;</p>

 <nav class="lanes" aria-label="Team lanes">
 __LANETABS__
 </nav>

 <section class="controls" aria-label="Search and filters">
  <div class="searchrow">
   <input id="q" type="search" autocomplete="off"
    placeholder="Search title, abstract, session code, or one of __SERVICES__ services">
   <button id="clear" class="ghost" hidden>Clear</button>
  </div>
  <div id="filters" class="filters"></div>
  <div id="chips" class="chips"></div>
 </section>

 <section class="resultbar">
  <p id="count" class="count">Loading the catalog&hellip;</p>
  <div class="viewtabs" role="tablist">
   <button id="tab-browse" class="vt" role="tab" aria-selected="true">Browse</button>
   <button id="tab-plan" class="vt" role="tab" aria-selected="false">
    My plan <span id="planN" class="badge">0</span></button>
  </div>
 </section>

 <section id="browse" class="results"></section>

 <section id="plan" class="plan" hidden>
  <div id="planbody"></div>
  <div class="planfoot">
   <button id="share" class="ghost">Copy a link to this plan</button>
   <button id="wipe" class="ghost danger">Clear plan</button>
  </div>
 </section>

 <details class="about">
  <summary>How the venue warnings work, and what is a fact versus an estimate</summary>
  <p><strong>The fact.</strong> Every session in the catalog carries its room
   &mdash; <code>Caesars Palace | Promenade Level | Roman I</code> &mdash; and
   a start and end time. When two sessions in your plan are at different
   properties, the gap between them is arithmetic on AWS's own published data.
   That number is what the warning states, and you can check it against the
   official catalog using the session code on every card.</p>
  <p><strong>The estimate.</strong> How long the hop actually takes is not
   published. AWS's FAQ says only to &ldquo;allow for additional travel time
   between venues&rdquo; and that shuttles &ldquo;run continuously during
   conference hours&rdquo; &mdash; no minutes. So this page assumes
   <strong>__SAME__ min</strong> to change rooms inside one property,
   <strong>__NEAR__ min</strong> between properties in the northern run, and
   <strong>__FAR__ min</strong> for anything involving __OUTLIER__, which sits
   on its own to the south. Those are estimates from the campus layout, not
   AWS figures, and you can change them below.</p>
  <p class="tune">Adjust:
   <label>same property <input id="t-same" type="number" min="0" max="120" value="__SAME__"> min</label>
   <label>northern run <input id="t-near" type="number" min="0" max="120" value="__NEAR__"> min</label>
   <label>__OUTLIER__ <input id="t-far" type="number" min="0" max="120" value="__FAR__"> min</label>
  </p>
  <p><strong>The lanes</strong> are service clusters, not the catalog's Role
   facet. Role is too broad to filter on &mdash; &ldquo;Solution / Systems
   Architect&rdquo; alone returns hundreds of sessions. Each lane is a set of
   services, and every lane is one tap from the full catalog.</p>
  <p><strong>How current this is, and how you can tell.</strong> The catalog
   is re-fetched from AWS every day by a scheduled job, and the line at the
   top of this page works out its own age <em>in your browser</em> from the
   capture timestamp &mdash; so if the job ever stops running, the page says
   how old it is rather than quietly implying it is current. Three things
   guard the refresh: a fetch that comes back more than a fifth smaller than
   the stored catalog is refused rather than written, so a partial fetch
   cannot overwrite good data; the checks run before the commit, not after;
   and every session code on this page links to that session in AWS's own
   catalog, so nothing here has to be taken on trust. If a session you
   starred disappears from the catalog, your plan says so instead of quietly
   dropping it.</p>
  <p class="src">Session data captured from the official catalog on
   <time datetime="__CAPTURED__">__CAPTURED__</time>. This page is not
   affiliated with AWS and is not the system of record: sessions get added,
   moved and cancelled, and reserved seating happens in the
   <a href="https://registration.awsevents.com/flow/awsevents/reinvent2026/eventcatalog/page/eventcatalog" target="_blank" rel="noopener">official catalog</a>,
   not here.</p>
 </details>

 <footer class="footer">
  <p>Not affiliated with Amazon Web Services. Session data belongs to AWS.</p>
  <p><a href="/">jayanthkatta.com</a></p>
 </footer>
</main>

<script>window.RI_CONFIG = __CONFIG__;</script>
<script src="./app.js" defer></script>
</body>
</html>
"""


# ------------------------------------------------------------------- styles

CSS = """/* Generated by scripts/build_reinvent_page.py -- do not edit by hand. */
:root{
  --bg:#121816; --panel:#182220; --panel2:#1e2a27; --line:#2b3a36;
  --ink:#e8efec; --dim:#9fb3ad; --faint:#7d918c;
  --accent:#c4a484; --accent2:#8fb3a6;
  --warn:#e0a458; --bad:#d97757; --ok:#7fb069;
  --r:12px;
}
*{box-sizing:border-box}
/* A class that sets `display` outranks the user-agent rule for [hidden],
   so .lanes{display:grid} kept the lane tabs on screen in the plan view
   even with the attribute set. Anything hidden here must stay hidden. */
[hidden]{display:none!important}
html{-webkit-text-size-adjust:100%}
body{
  margin:0; background:var(--bg); color:var(--ink);
  font:400 16px/1.55 "DM Sans",system-ui,-apple-system,sans-serif;
}
.page{max-width:1080px; margin:0 auto; padding:28px 18px 64px}
a{color:var(--accent)}
code{font-family:"DM Mono",ui-monospace,monospace; font-size:.9em}

/* ---- header ---- */
.eyebrow{margin:0; font-size:12px; letter-spacing:.14em; text-transform:uppercase; color:var(--faint)}
h1{margin:.2em 0 .25em; font-size:clamp(30px,6vw,46px); line-height:1.05; letter-spacing:-.02em}
.lede{margin:0 0 20px; max-width:62ch; color:var(--dim)}
.facts{list-style:none; display:grid; gap:10px; padding:0; margin:0 0 26px;
  grid-template-columns:repeat(auto-fit,minmax(200px,1fr))}
.facts li{background:var(--panel); border:1px solid var(--line); border-radius:var(--r); padding:10px 13px}
.facts span{display:block; font-size:11px; letter-spacing:.1em; text-transform:uppercase; color:var(--faint)}
.facts strong{font-weight:600; font-size:15px}
.facts em{font-style:normal; color:var(--faint); font-weight:400}

/* ---- freshness ---- */
.fresh{
  margin:0 0 18px; padding:9px 13px; border-radius:var(--r);
  border:1px solid var(--line); background:var(--panel);
  font-size:13.5px; color:var(--dim);
}
.fresh b{color:var(--ink); font-weight:600}
.fresh.good{border-color:#2f4436}
.fresh.aging{border-color:#5c4626; background:#221b12; color:#f0d2a6}
.fresh.stale{border-color:#5e332a; background:#231613; color:#f2c3b4}
.fresh a{color:inherit; text-decoration:underline}

/* ---- lanes ---- */
.lanes{display:grid; gap:10px; margin:0 0 22px;
  grid-template-columns:repeat(auto-fit,minmax(210px,1fr))}
.lane{
  text-align:left; cursor:pointer; font:inherit; color:var(--ink);
  background:var(--panel); border:1px solid var(--line);
  border-radius:var(--r); padding:13px 15px; display:grid; gap:3px;
  transition:border-color .15s, background .15s;
}
.lane:hover{border-color:var(--accent)}
.lane[aria-pressed="true"]{background:var(--panel2); border-color:var(--accent); box-shadow:inset 0 0 0 1px var(--accent)}
.ln{font-weight:600}
.lc{font-family:"DM Mono",monospace; font-size:22px; color:var(--accent); line-height:1.1}
.lb{font-size:12.5px; color:var(--faint); line-height:1.4}

/* ---- controls ---- */
.controls{margin:0 0 18px}
.searchrow{display:flex; gap:8px}
#q{
  flex:1; font:inherit; color:var(--ink); background:var(--panel);
  border:1px solid var(--line); border-radius:var(--r); padding:12px 14px;
}
#q:focus{outline:2px solid var(--accent); outline-offset:1px; border-color:transparent}
#q::placeholder{color:var(--faint)}
.ghost{
  font:inherit; cursor:pointer; color:var(--dim); background:transparent;
  border:1px solid var(--line); border-radius:var(--r); padding:8px 14px;
}
.ghost:hover{border-color:var(--accent); color:var(--ink)}
.ghost.danger:hover{border-color:var(--bad); color:var(--bad)}
.filters{display:flex; flex-wrap:wrap; gap:8px; margin-top:10px}
.filters select{
  font:inherit; font-size:14px; color:var(--ink); background:var(--panel);
  border:1px solid var(--line); border-radius:10px; padding:8px 10px; max-width:100%;
}
.chips{display:flex; flex-wrap:wrap; gap:6px; margin-top:10px}
.chip{
  font-size:12.5px; border:1px solid var(--line); border-radius:999px;
  padding:4px 10px; color:var(--dim); background:var(--panel);
  display:inline-flex; gap:6px; align-items:center;
}
.chip button{background:none; border:0; color:var(--faint); cursor:pointer; font:inherit; padding:0 0 0 2px}
.chip button:hover{color:var(--bad)}

/* ---- result bar ---- */
.resultbar{display:flex; flex-wrap:wrap; gap:12px; align-items:center;
  justify-content:space-between; margin:0 0 14px; padding-top:6px;
  border-top:1px solid var(--line)}
.count{margin:0; color:var(--dim); font-size:14px}
.count b{color:var(--ink)}
.viewtabs{display:flex; gap:6px}
.vt{
  font:inherit; font-size:14px; cursor:pointer; color:var(--dim);
  background:transparent; border:1px solid var(--line);
  border-radius:999px; padding:6px 14px;
}
.vt[aria-selected="true"]{background:var(--panel2); color:var(--ink); border-color:var(--accent)}
.badge{
  display:inline-block; min-width:20px; text-align:center; margin-left:4px;
  background:var(--accent); color:#1b1410; border-radius:999px;
  font-size:12px; font-weight:600; padding:0 6px;
}

/* ---- results ---- */
.daygroup{margin:0 0 26px}
.dayhead{
  position:sticky; top:0; z-index:2; margin:0 0 10px; padding:8px 0;
  background:linear-gradient(var(--bg) 70%,transparent);
  font-size:13px; letter-spacing:.1em; text-transform:uppercase; color:var(--accent2);
}
.card{
  background:var(--panel); border:1px solid var(--line);
  border-radius:var(--r); padding:13px 15px; margin:0 0 9px;
  display:grid; grid-template-columns:1fr auto; gap:4px 12px;
}
.card .top{grid-column:1; display:flex; flex-wrap:wrap; gap:7px; align-items:center; font-size:12.5px}
.card .code{font-family:"DM Mono",monospace; color:var(--accent); font-weight:500;
  text-decoration:none; border-bottom:1px dotted transparent}
a.code:hover{border-bottom-color:var(--accent)}
.tag{border:1px solid var(--line); border-radius:999px; padding:1px 8px; color:var(--dim); font-size:11.5px}
.tag.lvl{color:var(--accent2); border-color:#31463f}
.card h3{grid-column:1; margin:2px 0 3px; font-size:16px; line-height:1.35; font-weight:600}
.card .where{grid-column:1; font-size:13px; color:var(--faint)}
.card .where b{color:var(--dim); font-weight:500}
.star{
  grid-column:2; grid-row:1/4; align-self:start;
  font:inherit; font-size:20px; line-height:1; cursor:pointer;
  background:transparent; border:1px solid var(--line); border-radius:10px;
  color:var(--faint); width:40px; height:40px;
}
.star:hover{border-color:var(--accent); color:var(--accent)}
.star[aria-pressed="true"]{color:var(--accent); border-color:var(--accent); background:var(--panel2)}
.abstract{grid-column:1/-1; margin:7px 0 0; font-size:14px; color:var(--dim); display:none}
.card.open .abstract{display:block}
.more{
  grid-column:1; justify-self:start; margin-top:5px; padding:0;
  background:none; border:0; color:var(--faint); font:inherit; font-size:13px; cursor:pointer;
}
.more:hover{color:var(--accent)}
.card.gone{border-color:#5e332a; background:#1f1512}
.card.gone .code{color:var(--bad)}
.card.gone h3{color:#f2c3b4; font-size:15px}
.empty{padding:34px 4px; color:var(--faint); text-align:center}
.pager{display:flex; justify-content:center; padding:10px 0 4px}

/* ---- plan ---- */
.plan .daygroup{margin-bottom:20px}
.gap{
  display:flex; gap:9px; align-items:baseline;
  margin:0 0 9px; padding:8px 13px; border-radius:var(--r);
  border:1px solid var(--line); background:var(--panel);
  font-size:13.5px; color:var(--dim);
}
.gap.ok{border-color:#2f4436}
.gap.warn{border-color:#5c4626; background:#221b12; color:#f0d2a6}
.gap.bad{border-color:#5e332a; background:#231613; color:#f2c3b4}
.gap .ic{font-size:14px}
.gap b{color:inherit}
.planfoot{display:flex; gap:8px; flex-wrap:wrap; margin-top:12px}

/* ---- about ---- */
.about{
  margin:34px 0 0; border:1px solid var(--line); border-radius:var(--r);
  background:var(--panel); padding:0 15px;
}
.about summary{cursor:pointer; padding:13px 0; font-weight:600; font-size:14.5px}
.about p{font-size:14px; color:var(--dim); max-width:72ch}
.about .tune{display:flex; flex-wrap:wrap; gap:12px; align-items:center}
.about .tune label{font-size:13px; color:var(--faint)}
.about .tune input{
  width:64px; font:inherit; font-size:13px; color:var(--ink);
  background:var(--bg); border:1px solid var(--line); border-radius:8px; padding:4px 6px;
}
.about .src{font-size:13px; color:var(--faint); border-top:1px solid var(--line); padding-top:12px}

.footer{margin-top:34px; padding-top:16px; border-top:1px solid var(--line);
  font-size:13px; color:var(--faint)}
.footer p{margin:.3em 0}

@media (max-width:560px){
  .page{padding:20px 13px 52px}
  .card{grid-template-columns:1fr auto}
  .dayhead{top:0}
  /* On a phone this page is used one-handed, standing up, to answer "what
     is near me now". Four stacked fact panels and four stacked lane cards
     put the search box a full screen and a half down, so both go to two
     columns and the lane blurbs -- which are orientation, not navigation --
     step aside. The desktop layout above is untouched. */
  h1{font-size:34px}
  .lede{font-size:15px; margin-bottom:16px}
  .facts{grid-template-columns:1fr 1fr; gap:8px}
  .facts li{padding:8px 10px}
  .facts strong{font-size:13.5px}
  .facts li:nth-child(4){grid-column:1/-1}
  .lanes{grid-template-columns:1fr 1fr; gap:8px}
  .lane{padding:10px 12px}
  .lb{display:none}
  .lc{font-size:19px}
  .filters select{flex:1 1 44%; min-width:0}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""


# ---------------------------------------------------------------- behaviour

APP = r"""/* Generated by scripts/build_reinvent_page.py -- do not edit by hand. */
(function () {
  "use strict";
  var CFG = window.RI_CONFIG, DATA = null;
  var PAGE_SIZE = 60, shown = PAGE_SIZE;
  var PLAN_KEY = "ri2026.plan", TUNE_KEY = "ri2026.travel";
  var CATALOG_URL = "https://registration.awsevents.com/flow/awsevents/"
                  + "reinvent2026/eventcatalog/page/eventcatalog";

  var state = { lane: "all", q: "", day: "", type: "", level: "",
                venue: "", service: "" };
  var plan = load(PLAN_KEY, []);
  var tune = load(TUNE_KEY, null) || {
    same: CFG.travel.same, near: CFG.travel.near, far: CFG.travel.far };

  function load(key, dflt) {
    try { var v = JSON.parse(localStorage.getItem(key)); return v || dflt; }
    catch (e) { return dflt; }
  }
  function save(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) {}
  }
  function $(sel) { return document.querySelector(sel); }
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function hhmm(min) {
    var h = Math.floor(min / 60), m = min % 60;
    return (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m;
  }
  function dayLabel(iso) {
    var d = new Date(iso + "T12:00:00");
    return d.toLocaleDateString(undefined,
      { weekday: "long", day: "numeric", month: "long" });
  }

  /* ---- the venue-hop rule -------------------------------------------
     The gap is a fact from AWS's own times. `need` is this page's
     estimate, and the two are reported separately in the wording. */
  function needFor(fromVenue, toVenue) {
    if (fromVenue === toVenue) return tune.same;
    var outlier = CFG.travel.outlier;
    if (fromVenue === outlier || toVenue === outlier) return tune.far;
    return tune.near;
  }

  /* ---- data --------------------------------------------------------- */
  function firstSlot(s) { return s.when && s.when.length ? s.when[0] : null; }
  function svcNames(s) {
    return s.sv.map(function (i) { return DATA.facets.Services[i]; });
  }
  function typeName(s) {
    return s.ty == null ? "" : DATA.facets.Type[s.ty];
  }
  function levelName(s) {
    return s.lv == null ? "" : DATA.facets.Level[s.lv];
  }
  function venueName(slot) { return DATA.venues[slot.v]; }
  function roomName(slot) { return DATA.rooms[slot.r]; }

  function laneServices(id) {
    for (var i = 0; i < CFG.lanes.length; i++)
      if (CFG.lanes[i].id === id) return CFG.lanes[i].services;
    return null;
  }

  function matches(s) {
    if (state.lane !== "all") {
      var want = laneServices(state.lane), hit = false;
      for (var i = 0; i < s.sv.length && !hit; i++)
        if (want.indexOf(s.sv[i]) !== -1) hit = true;
      if (!hit) return false;
    }
    if (state.type && typeName(s) !== state.type) return false;
    if (state.level && levelName(s) !== state.level) return false;
    if (state.service && s.sv.indexOf(+state.service) === -1) return false;
    if (state.day || state.venue) {
      var ok = false;
      for (var j = 0; j < s.when.length && !ok; j++) {
        var w = s.when[j];
        if (state.day && w.d !== state.day) continue;
        if (state.venue && venueName(w) !== state.venue) continue;
        ok = true;
      }
      if (!ok) return false;
    }
    if (state.q) {
      var hay = (s.c + " " + s.t + " " + s.a + " " +
                 svcNames(s).join(" ")).toLowerCase();
      var terms = state.q.toLowerCase().split(/\s+/);
      for (var k = 0; k < terms.length; k++)
        if (terms[k] && hay.indexOf(terms[k]) === -1) return false;
    }
    return true;
  }

  function filtered() { return DATA.sessions.filter(matches); }

  /* ---- rendering ----------------------------------------------------- */
  function card(s, slot) {
    var c = el("article", "card");
    c.dataset.code = s.c;

    var top = el("div", "top");
    /* The code is the link. ?search=<code> was verified against a control:
       the /sessionDetails?sessionId= form silently falls back to the full
       catalog list, which looks like it worked. This one resolves, and the
       code is stable and human-readable where the internal id is neither. */
    var code = el("a", "code", s.c);
    code.href = CATALOG_URL + "?search=" + encodeURIComponent(s.c);
    code.target = "_blank";
    code.rel = "noopener";
    code.title = "Open " + s.c + " in the official AWS catalog";
    top.appendChild(code);
    if (typeName(s)) top.appendChild(el("span", "tag", typeName(s)));
    if (levelName(s)) top.appendChild(el("span", "tag lvl", levelName(s)));
    if (slot && slot.e != null) {
      top.appendChild(el("span", "tag",
        hhmm(slot.b) + "–" + hhmm(slot.e)));
    } else if (slot) {
      /* AWS publishes a start and no duration for a few sponsored
         sessions. Saying so beats inventing an end time. */
      top.appendChild(el("span", "tag",
        hhmm(slot.b) + " · length not published"));
    } else {
      top.appendChild(el("span", "tag", "not yet scheduled"));
    }
    c.appendChild(top);

    c.appendChild(el("h3", null, s.t));

    var where = el("div", "where");
    if (slot) {
      var b = el("b", null, venueName(slot));
      where.appendChild(b);
      var rest = roomName(slot).split("|").slice(1).join(" · ").trim();
      where.appendChild(document.createTextNode(
        (rest ? " · " + rest : "") +
        (slot.cap ? " · " + slot.cap + " seats" : "")));
    } else {
      where.textContent = "Venue to be announced";
    }
    c.appendChild(where);

    var star = el("button", "star", inPlan(s.c) ? "★" : "☆");
    star.setAttribute("aria-pressed", inPlan(s.c) ? "true" : "false");
    star.title = inPlan(s.c) ? "Remove from my plan" : "Add to my plan";
    star.addEventListener("click", function () { toggle(s.c); });
    c.appendChild(star);

    if (s.a) {
      var more = el("button", "more", "What is in it ›");
      var abs = el("p", "abstract", s.a);
      if (svcNames(s).length)
        abs.appendChild(el("span", null, "\n\nServices: " +
          svcNames(s).join(", ")));
      more.addEventListener("click", function () {
        c.classList.toggle("open");
        more.textContent = c.classList.contains("open")
          ? "Hide ‹" : "What is in it ›";
      });
      c.appendChild(more);
      c.appendChild(abs);
    }
    return c;
  }

  function renderBrowse() {
    var box = $("#browse");
    box.textContent = "";
    var list = filtered();

    $("#count").innerHTML = "<b>" + list.length.toLocaleString() +
      "</b> session" + (list.length === 1 ? "" : "s") +
      (state.lane === "all" ? "" : " in " + laneName(state.lane));

    if (!list.length) {
      box.appendChild(el("p", "empty",
        "Nothing matches. Try clearing a filter."));
      return;
    }

    /* One row per scheduled slot, so a repeated session appears on each
       day it actually runs -- which is the thing you are choosing between. */
    var rows = [];
    list.forEach(function (s) {
      if (!s.when.length) { rows.push({ s: s, w: null, d: "zzz" }); return; }
      s.when.forEach(function (w) {
        if (state.day && w.d !== state.day) return;
        if (state.venue && venueName(w) !== state.venue) return;
        rows.push({ s: s, w: w, d: w.d });
      });
    });
    rows.sort(function (a, b) {
      if (a.d !== b.d) return a.d < b.d ? -1 : 1;
      if (!a.w || !b.w) return a.w ? -1 : 1;
      return a.w.b - b.w.b;
    });

    var slice = rows.slice(0, shown), group = null, host = null;
    slice.forEach(function (r) {
      if (r.d !== group) {
        group = r.d;
        var g = el("section", "daygroup");
        g.appendChild(el("h2", "dayhead",
          r.w ? dayLabel(r.d) : "Not yet scheduled"));
        box.appendChild(g);
        host = g;
      }
      host.appendChild(card(r.s, r.w));
    });

    if (rows.length > shown) {
      var pager = el("div", "pager");
      var btn = el("button", "ghost",
        "Show " + Math.min(PAGE_SIZE, rows.length - shown) + " more of " +
        (rows.length - shown).toLocaleString());
      btn.addEventListener("click", function () {
        shown += PAGE_SIZE; renderBrowse();
      });
      pager.appendChild(btn);
      box.appendChild(pager);
    }
  }

  /* ---- how old is this, really ---------------------------------------
     Computed here rather than written in at build time, because the
     honest number is the one the reader is looking at now. A page built
     in September and opened in November has not got fresher, and a
     baked-in "captured 22 Sep" invites it to be read as if it had. */
  var AGING_DAYS = 10, STALE_DAYS = 21;

  function daysSince(iso) {
    if (!iso) return null;
    var then = new Date(iso);
    if (isNaN(then.getTime())) return null;
    return Math.floor((Date.now() - then.getTime()) / 86400000);
  }

  function renderFreshness() {
    var box = $("#fresh");
    var age = daysSince(DATA.captured_utc || DATA.captured);
    var when = DATA.captured || "an unrecorded date";
    box.textContent = "";

    if (age === null) {
      box.className = "fresh stale";
      box.appendChild(el("span", null,
        "This copy of the catalog carries no capture date, so there is no "
        + "way to tell how old it is. Treat every time and room here as "
        + "unconfirmed and check the official catalog."));
      addCatalogLink(box);
      return;
    }

    var howLong = age === 0 ? "earlier today"
                : age === 1 ? "yesterday"
                : age + " days ago";
    var b = el("b", null, "Catalog checked " + howLong);
    box.appendChild(b);

    if (age >= STALE_DAYS) {
      box.className = "fresh stale";
      box.appendChild(el("span", null,
        " (" + when + "). That is old enough that sessions have probably "
        + "been added, moved or cancelled since. Confirm anything you are "
        + "relying on — every card links to its entry in the "));
      addCatalogLink(box);
    } else if (age >= AGING_DAYS) {
      box.className = "fresh aging";
      box.appendChild(el("span", null,
        " (" + when + "). Sessions move as the event gets closer, so check "
        + "anything you are relying on against the "));
      addCatalogLink(box);
    } else {
      box.className = "fresh good";
      box.appendChild(el("span", null,
        " (" + when + "), against " + DATA.sessions.length.toLocaleString()
        + " sessions. Seat reservations and last-minute changes still live "
        + "in the "));
      addCatalogLink(box);
    }
  }

  function addCatalogLink(box) {
    var a = el("a", null, "official catalog");
    a.href = CATALOG_URL;
    a.target = "_blank";
    a.rel = "noopener";
    box.appendChild(a);
    box.appendChild(document.createTextNode("."));
  }

  function laneName(id) {
    for (var i = 0; i < CFG.lanes.length; i++)
      if (CFG.lanes[i].id === id) return CFG.lanes[i].name;
    return id;
  }

  /* ---- the plan ------------------------------------------------------ */
  function inPlan(code) { return plan.indexOf(code) !== -1; }
  function toggle(code) {
    var i = plan.indexOf(code);
    if (i === -1) plan.push(code); else plan.splice(i, 1);
    save(PLAN_KEY, plan);
    syncStars(); renderPlan();
  }
  function syncStars() {
    $("#planN").textContent = plan.length;
    Array.prototype.forEach.call(
      document.querySelectorAll(".card"), function (c) {
        var on = inPlan(c.dataset.code), b = c.querySelector(".star");
        if (!b) return;
        b.textContent = on ? "★" : "☆";
        b.setAttribute("aria-pressed", on ? "true" : "false");
        b.title = on ? "Remove from my plan" : "Add to my plan";
      });
  }

  function planRows() {
    var by = {}, rows = [];
    DATA.sessions.forEach(function (s) { by[s.c] = s; });
    plan.forEach(function (code) {
      var s = by[code];
      if (!s) {
        /* The session is starred and is no longer in the catalog. Dropping
           it silently was the worst thing this page could do: the plan
           would simply be one session shorter than the person built, with
           nothing to say a talk they were counting on has gone. */
        rows.push({ gone: code, d: "zzzz" });
        return;
      }
      if (!s.when.length) { rows.push({ s: s, w: null, d: "zzz" }); return; }
      s.when.forEach(function (w) { rows.push({ s: s, w: w, d: w.d }); });
    });
    rows.sort(function (a, b) {
      if (a.d !== b.d) return a.d < b.d ? -1 : 1;
      if (!a.w || !b.w) return a.w ? -1 : 1;
      return a.w.b - b.w.b;
    });
    return rows;
  }

  function renderPlan() {
    var box = $("#planbody");
    box.textContent = "";
    var rows = planRows();
    if (!rows.length) {
      box.appendChild(el("p", "empty",
        "Nothing starred yet. Star a session in Browse and it lands here, "
        + "with the travel between them checked."));
      return;
    }

    var group = null, host = null, prev = null;
    rows.forEach(function (r) {
      if (r.d !== group) {
        group = r.d; prev = null;
        host = el("section", "daygroup");
        host.appendChild(el("h2", "dayhead",
          r.gone ? "No longer in the catalog"
                 : r.w ? dayLabel(r.d) : "Not yet scheduled"));
        box.appendChild(host);
      }
      if (r.gone) { host.appendChild(goneCard(r.gone)); prev = null; return; }
      if (prev && prev.w && r.w) host.appendChild(gapRow(prev, r));
      host.appendChild(card(r.s, r.w));
      prev = r;
    });
  }

  function goneCard(code) {
    var c = el("article", "card gone");
    c.dataset.code = code;
    var top = el("div", "top");
    top.appendChild(el("span", "code", code));
    top.appendChild(el("span", "tag", "withdrawn or renamed"));
    c.appendChild(top);
    c.appendChild(el("h3", null, "This session is no longer in the catalog"));
    var where = el("div", "where");
    where.appendChild(document.createTextNode(
      "You starred it, and the capture of " + (DATA.captured || "the catalog")
      + " does not contain it. AWS may have withdrawn, merged or renumbered "
      + "it. Check "));
    var a = el("a", null, code + " in the official catalog");
    a.href = CATALOG_URL + "?search=" + encodeURIComponent(code);
    a.target = "_blank"; a.rel = "noopener";
    where.appendChild(a);
    where.appendChild(document.createTextNode("."));
    c.appendChild(where);
    var drop = el("button", "star", "×");
    drop.title = "Remove it from my plan";
    drop.addEventListener("click", function () { toggle(code); });
    c.appendChild(drop);
    return c;
  }

  function gapRow(a, b) {
    var from = venueName(a.w), to = venueName(b.w);
    var need = needFor(from, to);
    var row = el("div", "gap"), msg;

    if (a.w.e == null) {
      /* No published end, so there is no gap to measure. The page says
         that rather than measuring from the start time and calling the
         result a gap -- which would under-warn on exactly the hop this
         feature exists to catch. */
      row.className = "gap warn";
      row.appendChild(el("span", "ic", "○"));
      row.appendChild(el("span", null,
        "AWS does not publish how long " + a.s.c + " runs, so the time "
        + "before " + b.s.c + " cannot be checked."
        + (from === to ? "" : " They are at different properties — "
           + from + " to " + to + " — so allow about " + need + " min.")));
      return row;
    }

    var gap = b.w.b - a.w.e;
    if (gap < 0) {
      row.className = "gap bad";
      row.appendChild(el("span", "ic", "●"));
      msg = "These overlap by " + (-gap) + " min. " +
        (from === to ? "Same property, but you cannot be in both."
                     : from + " and " + to + " at once is not possible.");
    } else if (gap < need) {
      row.className = "gap warn";
      row.appendChild(el("span", "ic", "●"));
      msg = gap + " min between them" +
        (from === to ? " inside " + from
                     : ", and they are at different properties — " +
                       from + " to " + to) +
        ". Allow about " + need + ". You would be late.";
    } else {
      row.className = "gap ok";
      row.appendChild(el("span", "ic", "○"));
      msg = gap + " min" +
        (from === to ? " to change rooms inside " + from
                     : " to get from " + from + " to " + to) + ".";
    }
    row.appendChild(el("span", null, msg));
    return row;
  }

  /* ---- filters ------------------------------------------------------- */
  function buildFilters() {
    var host = $("#filters");
    host.textContent = "";

    function pick(key, label, options, valueOf) {
      var sel = el("select");
      sel.setAttribute("aria-label", label);
      sel.appendChild(new Option(label, ""));
      options.forEach(function (o) {
        sel.appendChild(new Option(o.label, o.value));
      });
      sel.value = state[key];
      sel.addEventListener("change", function () {
        state[key] = sel.value; shown = PAGE_SIZE; render();
      });
      host.appendChild(sel);
    }

    pick("day", "Any day", CFG.days.map(function (d) {
      return { label: dayLabel(d), value: d };
    }));
    pick("type", "Any format", DATA.facets.Type.map(function (t) {
      return { label: t, value: t };
    }));
    pick("level", "Any level", DATA.facets.Level.slice().sort()
      .map(function (l) { return { label: l, value: l }; }));
    pick("venue", "Any venue", DATA.venues.slice().sort()
      .map(function (v) { return { label: v, value: v }; }));

    /* Services is the long one -- 169 entries -- so it is sorted by how
       many sessions carry it, not alphabetically. The head of that list
       is what people are actually looking for. */
    var count = {};
    DATA.sessions.forEach(function (s) {
      s.sv.forEach(function (i) { count[i] = (count[i] || 0) + 1; });
    });
    var svc = Object.keys(count).map(Number).sort(function (a, b) {
      return count[b] - count[a];
    }).map(function (i) {
      return { label: DATA.facets.Services[i] + "  (" + count[i] + ")",
               value: String(i) };
    });
    pick("service", "Any service", svc);
  }

  function renderChips() {
    var host = $("#chips");
    host.textContent = "";
    var live = [];
    if (state.lane !== "all")
      live.push(["lane", laneName(state.lane)]);
    [["day", state.day && dayLabel(state.day)],
     ["type", state.type], ["level", state.level], ["venue", state.venue],
     ["service", state.service &&
       DATA.facets.Services[+state.service]]].forEach(function (p) {
      if (p[1]) live.push(p);
    });
    live.forEach(function (p) {
      var chip = el("span", "chip", p[1]);
      var x = el("button", null, "×");
      x.title = "Remove this filter";
      x.addEventListener("click", function () {
        state[p[0]] = p[0] === "lane" ? "all" : "";
        shown = PAGE_SIZE; buildFilters(); render();
      });
      chip.appendChild(x);
      host.appendChild(chip);
    });
  }

  function syncLaneTabs() {
    Array.prototype.forEach.call(
      document.querySelectorAll(".lane"), function (b) {
        b.setAttribute("aria-pressed",
          b.dataset.lane === state.lane ? "true" : "false");
      });
  }

  function render() {
    syncLaneTabs(); renderChips(); renderBrowse(); syncStars();
    $("#clear").hidden = !state.q;
  }

  /* ---- wiring -------------------------------------------------------- */
  function wire() {
    Array.prototype.forEach.call(
      document.querySelectorAll(".lane"), function (b) {
        b.addEventListener("click", function () {
          state.lane = b.dataset.lane; shown = PAGE_SIZE; render();
          window.scrollTo({ top: $(".controls").offsetTop - 12,
                            behavior: "smooth" });
        });
      });

    var timer = null;
    $("#q").addEventListener("input", function (e) {
      clearTimeout(timer);
      var v = e.target.value;
      timer = setTimeout(function () {
        state.q = v.trim(); shown = PAGE_SIZE; render();
      }, 140);
    });
    $("#clear").addEventListener("click", function () {
      $("#q").value = ""; state.q = ""; shown = PAGE_SIZE; render();
    });

    $("#tab-browse").addEventListener("click", function () { view("browse"); });
    $("#tab-plan").addEventListener("click", function () { view("plan"); });

    $("#share").addEventListener("click", function () {
      var url = location.origin + location.pathname +
        "#plan=" + encodeURIComponent(plan.join(","));
      var done = function () { $("#share").textContent = "Link copied";
        setTimeout(function () {
          $("#share").textContent = "Copy a link to this plan"; }, 1800); };
      if (navigator.clipboard) navigator.clipboard.writeText(url).then(done, done);
      else { prompt("Copy this link", url); }
    });

    $("#wipe").addEventListener("click", function () {
      if (!plan.length) return;
      if (!confirm("Clear all " + plan.length + " starred sessions?")) return;
      plan = []; save(PLAN_KEY, plan); syncStars(); renderPlan();
    });

    [["#t-same", "same"], ["#t-near", "near"], ["#t-far", "far"]]
      .forEach(function (p) {
        var input = $(p[0]);
        input.value = tune[p[1]];
        input.addEventListener("change", function () {
          var v = parseInt(input.value, 10);
          if (isNaN(v) || v < 0) { input.value = tune[p[1]]; return; }
          tune[p[1]] = v; save(TUNE_KEY, tune); renderPlan();
        });
      });
  }

  function view(which) {
    var browsing = which === "browse";
    $("#browse").hidden = !browsing;
    $("#plan").hidden = browsing;
    /* Search, filters and lanes only act on Browse. Left visible in the
       plan they are dead controls that push the plan itself below the
       fold -- on a phone, past it entirely. */
    $(".controls").hidden = !browsing;
    document.querySelector(".lanes").hidden = !browsing;
    $("#tab-browse").setAttribute("aria-selected", browsing ? "true" : "false");
    $("#tab-plan").setAttribute("aria-selected", browsing ? "false" : "true");
    if (!browsing) renderPlan();
  }

  function adoptSharedPlan() {
    var m = /[#&]plan=([^&]*)/.exec(location.hash);
    if (!m) return false;
    var codes = decodeURIComponent(m[1]).split(",").filter(Boolean);
    if (!codes.length) return false;
    plan = codes; save(PLAN_KEY, plan);
    history.replaceState(null, "", location.pathname);
    return true;
  }

  /* ---- boot ---------------------------------------------------------- */
  fetch("/intelligence/reinvent2026.json")
    .then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    })
    .then(function (d) {
      DATA = d;
      var shared = adoptSharedPlan();
      /* A shared link opened while the page is already up changes only the
         fragment, which is a same-document navigation -- no reload, so the
         boot path below never runs again. Without this, a teammate clicking
         someone's plan link from this very page sees nothing happen. */
      window.addEventListener("hashchange", function () {
        if (adoptSharedPlan()) { syncStars(); renderPlan(); view("plan"); }
      });
      var all = document.querySelector('[data-count="all"]');
      if (all) all.textContent = DATA.sessions.length.toLocaleString();
      buildFilters(); wire(); renderFreshness(); render();
      if (shared) view("plan");
    })
    .catch(function (err) {
      $("#count").textContent =
        "The session data did not load (" + err.message +
        "). The official catalog still works.";
    });
})();
"""


if __name__ == "__main__":
    sys.exit(build())
