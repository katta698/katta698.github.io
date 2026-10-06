#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build /reinvent-2026/planner/ -- a planner the reader drives themselves.

Asked as: "is there any way you can have some sort of an LLM option on my
page, so if a reader asks how should they plan their whole week based on the
topics they have chosen..."

The answer turned out to need less than it sounded. /reinvent-2026/ already
ships the entire catalogue to the browser -- 2.0 MB raw, about 0.5 MB gzipped
-- so "plan my week around these topics" is a scoring and scheduling problem
over data the page already holds. No model, no API, no key, nothing to
rate-limit and no bill that a scraper can run up.

It is also the more correct answer, not merely the cheaper one. This site's
rule is that if a figure is on a page, something measured it. A model writing
a schedule can state a room it is not in and a time the catalogue does not
carry, confidently, and this page would be the one place on the site where a
reader could not check what they were told. Everything the planner prints is
read out of the store.

What it cannot do is read intent out of a sentence. That is the one job worth
a model, and it is a later, smaller change: a free-text box that returns
WEIGHTS rather than sessions, with the scheduling still done here. The
scheduler is the part that would be reused, so it is the part built first.

The page carries the shared bar from the same helper the events page uses,
and is in check_contrast's STRICT list -- it is clean in both themes from the
first build, so it is held there rather than being allowed to drift.
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
OUTDIR = os.path.join(ROOT, "reinvent-2026", "planner")

CSS = """
.pq{max-width:900px;margin:0 auto;padding:0 1.2rem 4rem}
.pq-lede{color:var(--text-muted);line-height:1.7;margin:0 0 1.4rem}
.pq-form{background:var(--card);border:1px solid var(--border);border-radius:10px;
         padding:1.1rem 1.1rem .9rem;margin:0 0 1.4rem}
.pq-lab{display:block;font-size:.76rem;letter-spacing:.07em;text-transform:uppercase;
        color:var(--text-muted);margin:0 0 .5rem}
.pq-chips{display:flex;flex-wrap:wrap;gap:.45rem;margin:0 0 1.1rem}
.pq-chip{display:inline-flex;align-items:center;gap:.4rem;border:1px solid var(--border);
         border-radius:999px;padding:.32rem .7rem;font-size:.85rem;cursor:pointer;
         background:transparent}
.pq-chip:hover{border-color:var(--accent)}
.pq-chip input{margin:0;accent-color:var(--accent)}
.pq-opts{display:flex;flex-wrap:wrap;gap:1.1rem;align-items:flex-end;margin:0 0 .9rem}
.pq-opt{display:flex;flex-direction:column;gap:.3rem;font-size:.85rem}
.pq-opt select{background:var(--bg);color:var(--text);border:1px solid var(--border);
               border-radius:6px;padding:.35rem .5rem;font:inherit;font-size:.85rem}
.pq-togs{display:flex;flex-wrap:wrap;gap:.9rem;margin:.2rem 0 1rem;font-size:.85rem}
.pq-togs label{display:inline-flex;align-items:center;gap:.4rem;cursor:pointer}
.pq-togs input{accent-color:var(--accent)}
.pq-go{font:inherit;font-size:.9rem;font-weight:600;padding:.5rem 1.1rem;
       border-radius:7px;border:1px solid var(--accent);background:var(--accent);
       color:#1D2322;cursor:pointer}
.pq-go:disabled{opacity:.5;cursor:not-allowed}
.pq-state{color:var(--text-muted);font-size:.8rem;margin:.6rem 0 0}
/* These two sit on the CARD, which is lighter than the page, so the shared
   --text-muted lands at 4.33:1 there while passing everywhere else on the
   page. Measured against every day palette the card can take: 5.12:1. */
body.light .pq-lab,body.light .pq-state{color:#605F5B}
.pq-sum{border-top:1px solid var(--border);padding-top:1rem;margin-top:1.6rem;
        line-height:1.7}
.pq-day{margin:1.8rem 0 0;border-top:1px solid var(--border);padding-top:1.1rem}
.pq-h{display:flex;flex-wrap:wrap;align-items:baseline;gap:.6rem}
.pq-h h3{font-family:var(--serif);font-size:1.25rem;margin:0 0 .3rem}
.pq-anchor{color:var(--text-muted);font-size:.82rem}
.pq-key{background:var(--card);border:1px solid var(--border);border-radius:8px;
        padding:.6rem .8rem;margin:.3rem 0 .8rem;font-size:.84rem;line-height:1.6}
.pq-key b{color:var(--accent)}
body.light .pq-key b{color:#7A5C3C}
.pq-row{display:grid;grid-template-columns:6.6rem 1fr;gap:.9rem;padding:.8rem 0;
        border-top:1px solid var(--border)}
.pq-row:first-of-type{border-top:0}
.pq-t{font-family:var(--mono);font-size:.8rem;color:var(--text-muted);padding-top:.15rem}
.pq-title{margin:0 0 .25rem;line-height:1.45}
.pq-meta{color:var(--text-muted);font-size:.8rem;line-height:1.6}
.pq-why{color:var(--text-muted);font-size:.8rem;margin:.25rem 0 0;font-style:italic}
/* Whether a session runs again is the most actionable line on the page at
   reservation time: a missed 50-seat builders' session is only lost if it
   never repeats, and most do. The one-shots are called out, not the repeats,
   because the exception is what changes a decision. */
.pq-again{font-size:.8rem;margin:.25rem 0 0;color:var(--text-muted)}
.pq-once{color:#D08A7E;font-weight:600}
body.light .pq-once{color:#99453B}
.pq-tag{display:inline-block;font-size:.67rem;letter-spacing:.06em;text-transform:uppercase;
        padding:1px 6px;border-radius:4px;border:1px solid var(--border);margin-right:.4rem}
.pq-res{color:#D08A7E}
body.light .pq-res{color:#99453B}
.pq-open{color:#9FB38F}
body.light .pq-open{color:#4C6340}
.pq-note{color:var(--text-muted);font-size:.82rem;line-height:1.7;margin:1.6rem 0 0}
.pq-empty{color:var(--text-muted);line-height:1.7}
@media(max-width:620px){.pq-row{grid-template-columns:1fr;gap:.15rem}
  .pq-t{padding-top:0}}
"""

BODY = """<main class="pq">
<h1>Plan your re:Invent</h1>
<p class="pq-lede">Tick what you care about and this builds a day-by-day plan
from the official catalogue: every session scored against your interests,
repeats collapsed, sponsored sessions dropped, and anything you could not
physically walk to in the gap refused.</p>
<p class="pq-lede">It runs entirely in your browser against the catalogue this
site already carries. There is no model writing your schedule, which is the
point &mdash; every session code, time, room and seat count below is read from
the catalogue, so none of it can be invented.
<a href="/reinvent-2026/">Browse all sessions &rarr;</a></p>

<div class="pq-form">
  <span class="pq-lab">What are you there for? Pick as many as apply</span>
  <div class="pq-chips" id="pq-chips"></div>

  <span class="pq-lab">Which days</span>
  <div class="pq-chips" id="pq-days"></div>

  <div class="pq-opts">
    <label class="pq-opt"><span>Staying at</span>
      <select id="pq-hotel"></select></label>
    <label class="pq-opt"><span>Sessions a day</span>
      <select id="pq-per">
        <option value="2">2 &mdash; light</option>
        <option value="3" selected>3 &mdash; comfortable</option>
        <option value="4">4 &mdash; full</option>
        <option value="5">5 &mdash; relentless</option>
      </select></label>
    <label class="pq-opt"><span>Depth</span>
      <select id="pq-level">
        <option value="deep" selected>Prefer 300/400</option>
        <option value="broad">Prefer 100/200</option>
        <option value="any">No preference</option>
      </select></label>
  </div>

  <div class="pq-togs">
    <label><input type="checkbox" id="pq-hands" checked>
      Favour hands-on (workshops, builders&rsquo;, chalk talks)</label>
    <label><input type="checkbox" id="pq-near">
      Keep it close to my hotel</label>
  </div>

  <button class="pq-go" id="pq-go" disabled>Build my plan</button>
  <p class="pq-state" id="pq-state">Loading the session catalogue&hellip;</p>
</div>

<div id="pq-out"></div>
</main>
"""


def build():
    import build_events_page as bep
    from asset_version import JS_VERSION
    jsv = JS_VERSION

    head = bep.head_html(jsv)
    head = re.sub(r"<title>.*?</title>",
                  "<title>Plan your re:Invent 2026 | Jayanth Katta</title>",
                  head, count=1, flags=re.S)
    head = re.sub(r'<meta name="description" content=".*?">',
                  '<meta name="description" content="Pick your interests and '
                  'get a day-by-day re:Invent 2026 plan built from the official '
                  'catalogue, in your browser. Venue-aware, repeat-free, and it '
                  'tells you which sessions can actually be reserved.">',
                  head, count=1, flags=re.S)
    head = re.sub(r'<link rel="canonical" href=".*?">',
                  '<link rel="canonical" '
                  'href="https://jayanthkatta.com/reinvent-2026/planner/">',
                  head, count=1, flags=re.S)
    head += "<style>%s</style>\n</head>\n" % CSS

    # planner.js is versioned off the shared token so a change to it is not
    # served from a stale cache, the same way every other asset here is.
    html = (head + "<body>\n" + bep.nav_html() + "\n" + BODY +
            '<script src="/reinvent-2026/planner/planner.js?v=%s"></script>\n'
            % jsv + bep.tail_html(jsv, "reinvent-planner"))

    os.makedirs(OUTDIR, exist_ok=True)
    out = os.path.join(OUTDIR, "index.html")
    io.open(out, "w", encoding="utf-8", newline="\n").write(html)
    print("  page -> reinvent-2026/planner/index.html  (%.1fKB)"
          % (len(html) / 1024.0))
    js = os.path.join(OUTDIR, "planner.js")
    if os.path.exists(js):
        print("  planner.js %.1fKB (hand-written, not generated)"
              % (os.path.getsize(js) / 1024.0))
    return 0


if __name__ == "__main__":
    sys.exit(build())
