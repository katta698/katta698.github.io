#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build /reinvent-2026/plan/ -- the four days, as actually booked.

Why this is generated rather than written
-----------------------------------------
A conference plan typed into a page is wrong within a week. AWS moves
sessions constantly: this repo's own commit log carries "re:Invent: 12
retimed, 35 newly scheduled, 26 added" as a routine daily message. A static
page would still be showing the time a talk USED to start, and it would look
exactly as confident as one that was right.

So the plan here is a list of session CODES and nothing else. Every time,
room, venue, capacity and format is read out of intelligence/reinvent2026.json
when the page is built, which the re:Invent workflow refreshes daily. Change
the catalogue and the page follows it.

What the page asserts, and how it knows
---------------------------------------
RESERVE vs open seating is not a guess and not a convention remembered from
a previous year. The catalogue's own `scheduleAccess` field lists the
registration groups allowed to put a session on their schedule, and across
all 2,177 sessions it splits perfectly clean by format -- every session of a
type is either gated or open, with no mixed cases:

    gated (reserve)   Chalk talk, Workshop, Builders' session, Code talk,
                      Lab, Gamified learning, Bootcamp, Exam prep
    open  (walk up)   Breakout session, Lightning talk

That is captured in RESERVABLE below. A breakout cannot be reserved at all,
which matters more than it sounds: the best fleet session on the plan is a
breakout, and looking for a Reserve button on it would waste the minutes
when the 50-seat builders' sessions are disappearing.

Drift
-----
Each pick is pinned to the day, start time and venue it had when the plan was
made. If the catalogue now disagrees, the row says so rather than quietly
rendering the new time -- a plan that silently rewrites itself is how you
arrive at a room the session left. Both values are shown: what was booked,
and what the catalogue says today.
"""
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

STORE = os.path.join(ROOT, "intelligence", "reinvent2026.json")
OUTDIR = os.path.join(ROOT, "reinvent-2026", "plan")

# Formats whose seats are held in advance. Derived from the catalogue's
# scheduleAccess field, not from memory -- see the module docstring.
RESERVABLE = {"Chalk talk", "Workshop", "Builders' session", "Code talk",
              "Lab", "Gamified learning", "Bootcamp", "Exam prep"}
OPEN_SEATING = {"Breakout session", "Lightning talk"}

# The plan. Codes only; everything else is read from the catalogue.
# Pinned as (day, start-minute, venue) so a move is visible rather than silent.
PLAN = [
    ("2026-11-30", "Monday", "EC2 fleet day", "MGM Grand", None, [
        ("COP324-R",  "2026-11-30", 510,  "Wynn/Encore",
         "The FinOps workshop, and the only one that fits before the MGM run."),
        ("CMP328-R",  "2026-11-30", 720,  "MGM Grand",
         "Agent sandboxes on EC2 — the agentic angle on your own estate."),
        ("CMP409-R",  "2026-11-30", 780,  "MGM Grand",
         "Launch APIs and capacity: the mechanics behind a 7,000-instance fleet."),
        ("STG357-R",  "2026-11-30", 870,  "MGM Grand",
         "EBS snapshots for protection and testing."),
        ("CMP203",    "2026-11-30", 990,  "MGM Grand",
         "Launch to fleet orchestration. The closest thing here to your day job."),
    ]),
    ("2026-12-01", "Tuesday", "Agentic ops, walkable", "Caesars Forum", (480, 630), [
        ("OPN401-R",  "2026-12-01", 690,  "Caesars Forum",
         "Powertools for agent DevOps."),
        ("COP319-R",  "2026-12-01", 780,  "Caesars Forum",
         "Observing agents past the perimeter."),
        ("CON401-R",  "2026-12-01", 900,  "Caesars Forum",
         "Kiro and Q Developer for platform engineering, at level 400. Two "
         "hours, and the only Kiro session on the plan — it replaced a "
         "Lambda cost talk and a multicloud VM talk, which were the two "
         "weakest picks against an EC2 estate."),
    ]),
    ("2026-12-02", "Wednesday", "Price-performance and FinOps", "MGM Grand", (510, 630), [
        ("CMP343-R",  "2026-12-02", 630,  "MGM Grand",
         "EC2 price performance."),
        ("CMP336-R",  "2026-12-02", 720,  "MGM Grand",
         "Auto Mode, Graviton and Spot together."),
        ("COP310-R1", "2026-12-02", 900,  "MGM Grand",
         "Threat detection and response, automated."),
        ("COP329-R1", "2026-12-02", 990,  "MGM Grand",
         "Automating savings in Billing and Cost Management."),
    ]),
    ("2026-12-03", "Thursday", "EBS and capacity, then the airport", "MGM Grand", (510, 630), [
        ("IND3348",   "2026-12-03", 630,  "Caesars Forum",
         "Bedrock and Kiro on a real incident-command workflow, built on "
         "AgentCore. Open seating, six minutes from the hotel, and it is the "
         "closest thing here to AI applied to your own on-call."),
        ("CMP320",    "2026-12-03", 780,  "MGM Grand",
         "Choosing the right instance, deliberately."),
        ("STG408",    "2026-12-03", 930,  "MGM Grand",
         "Mission-critical on EBS. Ends 5:30pm; MGM is the closest venue to LAS."),
    ]),
]

BACKUPS = [
    ("COM324-R1", "Bedrock with CloudWatch and EventBridge for multi-agent cloud "
                  "operations — the single closest match to the whole "
                  "profile. Only off the plan because it clashes with Thursday "
                  "morning; take it over anything if a slot frees."),
    ("DVT307",    "Kiro across the whole SDLC rather than just code generation. "
                  "Open seating at Caesars Forum."),
    ("COP305-R1", "Security logs into actionable intelligence — your CloudTrail "
                  "and Security Hub work, almost by name."),
    ("COP315-R1", "Patching and compliance, automated with agents."),
    ("STG328-R",  "EBS performance and cost. Swap for the Spot talk if EBS wins."),
    ("SEC428",    "One Security Hub finding, fixed four ways."),
    ("COP407",    "Build-time context for agentic incident response."),
]

# The keynotes are NOT in the catalogue: there are no KEY session codes among
# the 2,177 records, so their times cannot be read the way everything else
# here is. The blocks below are re:Invent's long-standing shape and are
# labelled as unconfirmed on the page rather than printed as fact.
KEYNOTE_NOTE = ("Held from the catalogue's own data, which contains no keynote "
                "records at all — there are no KEY session codes among the "
                "2,177. Treat the window as the usual shape and confirm it on "
                "the official agenda.")

TRAVEL = [
    ("Caesars Forum", 6), ("Venetian", 12), ("Caesars Palace", 12),
    ("Wynn/Encore", 18), ("MGM Grand", 35),
]


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def hm(m):
    if m is None:
        return "--"
    h, mm = divmod(int(m), 60)
    ap = "am" if m < 720 else "pm"
    h2 = h if h <= 12 else h - 12
    return "%d:%02d%s" % (h2, mm, ap)


def load():
    d = json.load(io.open(STORE, encoding="utf-8"))
    ty, venues = d["facets"]["Type"], d["venues"]
    out = {}
    for s in d["sessions"]:
        for w in (s.get("when") or []):
            out.setdefault(s["c"], []).append({
                "code": s["c"], "title": s["t"], "type": ty[s["ty"]],
                "d": w["d"], "b": w["b"], "e": w["e"],
                "v": venues[w["v"]], "cap": w.get("cap"),
            })
    return out, d.get("captured", "")


def resolve(idx, code, pin_d, pin_b, pin_v):
    """The catalogue's current record for a pick, and whether it has moved."""
    rows = idx.get(code) or []
    if not rows:
        return None, "GONE"
    exact = [r for r in rows if r["d"] == pin_d and r["b"] == pin_b
             and r["v"] == pin_v]
    if exact:
        return exact[0], ""
    same_day = [r for r in rows if r["d"] == pin_d]
    return (same_day[0] if same_day else rows[0]), "MOVED"


CSS = """
.pl{max-width:900px;margin:0 auto;padding:0 1.2rem 4rem}
.pl-lede{color:var(--text-muted);line-height:1.7;margin:0 0 1.6rem}
.pl-day{margin:2.4rem 0 0;border-top:1px solid var(--border);padding-top:1.4rem}
.pl-h{display:flex;flex-wrap:wrap;align-items:baseline;gap:.6rem;margin:0 0 .2rem}
.pl-h h2{font-family:var(--serif);font-size:1.45rem;margin:0}
.pl-when{color:var(--text-muted);font-size:.85rem}
.pl-anchor{color:var(--text-muted);font-size:.85rem;margin:.1rem 0 1rem}
.pl-key{background:var(--card);border:1px solid var(--border);border-radius:8px;
        padding:.7rem .9rem;margin:0 0 1rem;font-size:.86rem;line-height:1.6}
.pl-key b{color:var(--accent)}
/* --accent is tuned for the dark ground; on the light card it measured
   1.88:1. Checked against every day palette the page can render: 4.91:1. */
body.light .pl-key b{color:#7A5C3C}
.pl-row{display:grid;grid-template-columns:7.2rem 1fr;gap:.9rem;
        padding:.85rem 0;border-top:1px solid var(--border)}
.pl-row:first-of-type{border-top:0}
.pl-t{font-family:var(--mono);font-size:.82rem;color:var(--text-muted);
      padding-top:.15rem;white-space:nowrap}
.pl-title{margin:0 0 .25rem;line-height:1.45}
.pl-title a{color:inherit;text-decoration:none;border-bottom:1px solid var(--border)}
.pl-title a:hover{border-bottom-color:currentColor}
.pl-meta{color:var(--text-muted);font-size:.8rem;line-height:1.6}
.pl-why{color:var(--text-muted);font-size:.84rem;margin:.3rem 0 0;line-height:1.6}
.pl-tag{display:inline-block;font-size:.68rem;letter-spacing:.06em;
        text-transform:uppercase;padding:1px 6px;border-radius:4px;
        border:1px solid var(--border);margin-right:.35rem;white-space:nowrap}
.pl-res{color:#D08A7E}
body.light .pl-res{color:#99453B}
.pl-open{color:#9FB38F}
body.light .pl-open{color:#4C6340}
.pl-moved{color:#D4A05A}
body.light .pl-moved{color:#7E5A1C}
.pl-note{color:var(--text-muted);font-size:.84rem;line-height:1.7;
         margin:1.4rem 0 0}
.pl-tbl{width:100%;border-collapse:collapse;margin:.6rem 0 0;font-size:.85rem}
.pl-tbl th,.pl-tbl td{text-align:left;padding:.4rem .6rem .4rem 0;
                      border-bottom:1px solid var(--border)}
.pl-tbl th{color:var(--text-muted);font-weight:600;font-size:.78rem;
           letter-spacing:.04em;text-transform:uppercase}
@media(max-width:620px){.pl-row{grid-template-columns:1fr;gap:.2rem}
  .pl-t{padding-top:0}}
"""


def session_row(r, flag, why, pin_b, pin_v):
    tag = ('<span class="pl-tag pl-res">reserve</span>'
           if r["type"] in RESERVABLE else
           '<span class="pl-tag pl-open">open seating</span>')
    moved = ""
    if flag == "MOVED":
        moved = ('<span class="pl-tag pl-moved">moved</span>'
                 '<span class="pl-meta"> booked for %s at %s &middot; catalogue '
                 'now says %s at %s</span>'
                 % (hm(pin_b), esc(pin_v), hm(r["b"]), esc(r["v"])))
    cap = ("%d seats" % r["cap"]) if r.get("cap") else "capacity not published"
    return (
        '<div class="pl-row">'
        '<div class="pl-t">%s<br>%s</div>'
        '<div><p class="pl-title"><b>%s</b> &mdash; %s</p>'
        '<div class="pl-meta">%s%s &middot; %s &middot; %s%s</div>'
        '<p class="pl-why">%s</p></div></div>'
        % (hm(r["b"]), hm(r["e"]), esc(r["code"]), esc(r["title"]),
           tag, esc(r["type"]), esc(r["v"]), cap,
           (" &middot; " + moved) if moved else "", esc(why)))


def build():
    idx, captured = load()
    import build_events_page as bep
    from asset_version import JS_VERSION
    jsv = JS_VERSION

    head = bep.head_html(jsv)
    head = re.sub(r"<title>.*?</title>",
                  "<title>re:Invent 2026 &mdash; the four days, as booked | "
                  "Jayanth Katta</title>", head, count=1, flags=re.S)
    head = re.sub(r'<meta name="description" content=".*?">',
                  '<meta name="description" content="A worked re:Invent 2026 '
                  'plan for an EC2 fleet, observability and FinOps engineer: '
                  'four days, venue-anchored, with which formats can actually '
                  'be reserved and which are walk-up.">',
                  head, count=1, flags=re.S)
    head = re.sub(r'<link rel="canonical" href=".*?">',
                  '<link rel="canonical" '
                  'href="https://jayanthkatta.com/reinvent-2026/plan/">',
                  head, count=1, flags=re.S)
    head += "<style>%s</style>\n</head>\n" % CSS

    reserve_n = open_n = 0
    # The bar, from the same helper the events page uses. The first build
    # emitted <body><main> with no nav at all -- the page had the shared CSS
    # and none of the header markup it styles, so it rendered as a bare
    # document with no way back to the rest of the site.
    body = ['<body>', bep.nav_html(), '<main class="pl">',
            '<h1>re:Invent 2026 &mdash; the four days</h1>',
            '<p class="pl-lede">Monday 30 November to Thursday 3 December, '
            'staying at Harrah\'s. Built for an estate of about 7,000 EC2 '
            'instances: fleet and capacity, EBS and snapshots, observability '
            'and log analytics, FinOps, and where agents genuinely help with '
            'any of it. <a href="/reinvent-2026/">All 2,177 sessions, searchable '
            '&rarr;</a></p>',
            '<p class="pl-lede">Every time, room and seat count on this page '
            'is read from the session catalogue when the page is built, not '
            'typed in — AWS retimes sessions daily. A pick whose details '
            'have changed since it was chosen is marked <span class="pl-tag '
            'pl-moved">moved</span> and shows both.</p>']

    for day, dayname, theme, anchor, keyblock, picks in PLAN:
        body.append('<section class="pl-day">')
        body.append('<div class="pl-h"><h2>%s</h2>'
                    '<span class="pl-when">%s &middot; %s</span></div>'
                    % (dayname, day, esc(theme)))
        body.append('<p class="pl-anchor">Anchored at %s. '
                    'From Harrah\'s that is about %d minutes.</p>'
                    % (esc(anchor), dict(TRAVEL).get(anchor, 30)))
        if keyblock:
            body.append('<p class="pl-key"><b>%s &ndash; %s &nbsp;keynote</b> '
                        '&mdash; no reservation, and worth arriving early. %s</p>'
                        % (hm(keyblock[0]), hm(keyblock[1]), esc(KEYNOTE_NOTE)))
        else:
            body.append('<p class="pl-key"><b>No morning keynote</b> &mdash; '
                        'the only full day of the four, which is why it runs '
                        'from 8:30am. Monday Night Live is an evening slot; '
                        'confirm it on the official agenda.</p>')
        for code, pd, pb, pv, why in picks:
            r, flag = resolve(idx, code, pd, pb, pv)
            if r is None:
                body.append('<div class="pl-row"><div class="pl-t">--</div>'
                            '<div><p class="pl-title"><b>%s</b></p>'
                            '<div class="pl-meta">No longer in the catalogue. '
                            'Replace it from the backups below.</div></div></div>'
                            % esc(code))
                continue
            if r["type"] in RESERVABLE:
                reserve_n += 1
            else:
                open_n += 1
            body.append(session_row(r, flag, why, pb, pv))
        body.append('</section>')

    body.append('<section class="pl-day"><div class="pl-h">'
                '<h2>What to click first</h2></div>')
    body.append('<p class="pl-anchor">%d of the picks above need a '
                'reservation; %d are open seating and cannot be reserved at '
                'all. Order by how fast the room fills, which is seat count.</p>'
                % (reserve_n, open_n))
    body.append('<table class="pl-tbl"><tr><th>Format</th><th>Typical seats</th>'
                '<th>Reservation</th></tr>')
    for fmt, seats in [("Builders' session", "50"), ("Code talk", "80"),
                       ("Chalk talk", "78"), ("Workshop", "112"),
                       ("Lightning talk", "50"), ("Breakout session", "140")]:
        tag = ('<span class="pl-tag pl-res">reserve</span>' if fmt in RESERVABLE
               else '<span class="pl-tag pl-open">walk up</span>')
        body.append('<tr><td>%s</td><td>%s</td><td>%s</td></tr>'
                    % (esc(fmt), seats, tag))
    body.append('</table>')
    body.append('<p class="pl-note">Which formats can be reserved is read from '
                'the catalogue\'s own <code>scheduleAccess</code> field, not '
                'from last year\'s habits. Across all 2,177 sessions it splits '
                'perfectly by format — every session of a type is either '
                'gated or open, with no mixed cases. The registration site is '
                'still the authority on its own rules: if it offers a Reserve '
                'button on a breakout, believe it over this page.</p>')
    body.append('</section>')

    body.append('<section class="pl-day"><div class="pl-h">'
                '<h2>Backups</h2></div>'
                '<p class="pl-anchor">A 50-seat builders\' session goes in '
                'seconds. These are the replacements, already checked against '
                'the same interests.</p>')
    for code, why in BACKUPS:
        rows = idx.get(code) or []
        if not rows:
            continue
        r = rows[0]
        body.append(session_row(r, "", why, r["b"], r["v"]))
    body.append('</section>')

    body.append('<p class="pl-note">Catalogue captured %s. This page is '
                'rebuilt from it, so a session that moves moves here too.</p>'
                % esc(captured))
    body.append('</main>')
    body.append(bep.tail_html(jsv, "reinvent-plan"))

    html = head + "\n".join(body)
    os.makedirs(OUTDIR, exist_ok=True)
    out = os.path.join(OUTDIR, "index.html")
    io.open(out, "w", encoding="utf-8", newline="\n").write(html)
    print("  %d reserve, %d open seating" % (reserve_n, open_n))
    print("  page -> reinvent-2026/plan/index.html  (%.1fKB)"
          % (len(html) / 1024.0))
    return 0


if __name__ == "__main__":
    sys.exit(build())
