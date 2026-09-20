#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build /intelligence/ai/ -- what the AI vendors have shipped, and what runs.

    python scripts/build_ai_page.py

Why this page exists
--------------------
Asked for as: "a dedicated page for AI as well, like Intelligence and What's
New. AI is advancing in many areas and it's good to catch up -- what GPT has
to offer, what models they have, what's new, and the same for Anthropic,
Gemini, Grok, Copilot."

Two questions, answered separately because they have different half-lives:

    WHAT RUNS      the model catalogue. Names, context windows, prices and
                   the date each appeared. This changes weekly and is worth
                   a table you can sort your eye down.

    WHAT SHIPPED   the announcements. This changes daily, reads like news,
                   and belongs in a list with dates and links out.

Both come from fetch_ai.py, which reads the vendors' own feeds where they
publish one and their sitemaps where they do not. Nothing here is written by
hand and nothing is summarised by a model: every line is a title the vendor
published, a number the catalogue returned, or a count of those.

The honesty the page owes a reader
----------------------------------
The catalogue is OpenRouter's, an aggregator, and the page says so beside
the table rather than in a footnote. It lags a launch by hours to days, it
lists community models next to official ones, and its prices are what
OpenRouter charges, which is not always the vendor's direct rate.

Anthropic and xAI publish no feed at all, so their entries come from
timestamps in their sitemaps and each carries a "sitemap" badge. A reader
can see which vendors are watched well and which are watched at arm's
length, which is the difference between a page that tracks nine vendors and
a page that claims to.
"""
import datetime as dt
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
STORE = os.path.join(ROOT, "intelligence", "ai.json")
OUT_DIR = os.path.join(ROOT, "intelligence", "ai")

# A model counts as new for this long. Long enough that a quiet fortnight
# still shows something, short enough that "new" means it.
NEW_DAYS = 60

VENDOR_ORDER = ["OpenAI", "Anthropic", "Google", "Google DeepMind", "xAI",
                "Meta", "Microsoft", "Microsoft Azure", "Mistral", "DeepSeek",
                "Qwen", "Hugging Face", "AWS"]


def esc(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def slug(v):
    return re.sub(r"[^a-z0-9]+", "-", (v or "").lower()).strip("-")


def nav_html():
    """The bar, from the What's New builder, with Intelligence marked.

    Imported rather than copied: five headers drifted into four border
    colours once, and this is the fix that stopped it.
    """
    import build_news_page as bnp
    page = bnp.PAGE
    nav = page[page.index("<nav>"):page.index("</nav>") + len("</nav>")]
    nav = nav.replace(
        '<li><a href="/intelligence/whats-new/" class="active" '
        'aria-current="page">What&rsquo;s new</a></li>',
        '<li><a href="/intelligence/whats-new/">What&rsquo;s new</a></li>')
    nav = nav.replace(
        '<li><a href="/intelligence/">Intelligence</a></li>',
        '<li><a href="/intelligence/" class="active" '
        'aria-current="page">Intelligence</a></li>')
    return nav


def head_html(jsv):
    """The whole head from What's New, re-titled -- CSS included.

    The events page learned this the hard way: a head written from scratch
    carries the four pre-paint essentials and none of the header's own CSS,
    which lives in a per-page style block. The result renders as an
    unstyled bar with a 16px logo and the word "Ligh" where the theme
    control should be.
    """
    import build_news_page as bnp
    head = bnp.PAGE[:bnp.PAGE.index("</head>")]
    head = re.sub(r"<title>.*?</title>",
                  "<title>AI releases and models &mdash; OpenAI, Anthropic, "
                  "Google, xAI | Jayanth Katta</title>",
                  head, count=1, flags=re.S)
    head = re.sub(r'<meta name="description" content=".*?">',
                  '<meta name="description" content="What the AI vendors '
                  'shipped, from their own feeds, and the models that are '
                  'running: context windows, prices and the date each one '
                  'appeared. Refreshed daily.">',
                  head, count=1, flags=re.S)
    head = re.sub(r'<link rel="canonical" href=".*?">',
                  '<link rel="canonical" '
                  'href="https://jayanthkatta.com/intelligence/ai/">',
                  head, count=1, flags=re.S)
    head = head.replace("__JSV__", jsv)
    # Placeholders belonging to the page this head was taken from. One of
    # them shipped raw on the events page -- min-height:__RESERVE_WIDE__px --
    # so anything still unfilled is emptied rather than served.
    head = head.replace("__RESERVE_WIDE__", "0").replace("__RESERVE__", "0")
    head = re.sub(r"__[A-Z_]+__", "", head)
    return head


def tail_html(jsv):
    import build_events_page as bep
    return bep.tail_html(jsv, page_id="intelligence-ai")


STYLE = """
<style>
  .ai-wrap { max-width: 1120px; margin: 0 auto; padding: 1.5rem 1rem 4rem; }
  .ai-head h1 { margin: .2rem 0 .4rem; font-size: clamp(1.5rem,4vw,2.1rem); }
  .ai-lede { color: var(--muted,#A9A49C); max-width: 62ch; line-height: 1.65; }
  .ai-stats { display: flex; flex-wrap: wrap; gap: .6rem; margin: 1.1rem 0; }
  .ai-stat { border: 1px solid var(--bd,#33302C); border-radius: 10px;
             padding: .5rem .75rem; min-width: 7rem; }
  .ai-stat b { display: block; font-size: 1.15rem; }
  .ai-stat span { font-size: .68rem; letter-spacing: .06em;
                  text-transform: uppercase; color: var(--muted,#A9A49C); }
  .ai-sec { margin-top: 2.2rem; }
  .ai-sec h2 { font-size: 1.15rem; margin: 0 0 .3rem; }
  .ai-note { color: var(--muted,#A9A49C); font-size: .84rem;
             line-height: 1.6; max-width: 70ch; margin: 0 0 .9rem; }
  .ai-pills { display: flex; flex-wrap: wrap; gap: .4rem; margin: .8rem 0; }
  .ai-pill { border: 1px solid var(--bd,#33302C); background: transparent;
             color: inherit; border-radius: 999px; padding: .28rem .7rem;
             font-size: .76rem; cursor: pointer; }
  .ai-pill[aria-pressed="true"] { background: var(--acc-ink,#C4A484);
                                  border-color: var(--acc-ink,#C4A484);
                                  color: #1F1D1B; }
  .ai-q { width: 100%; max-width: 22rem; padding: .45rem .6rem;
          border-radius: 8px; border: 1px solid var(--bd,#33302C);
          background: transparent; color: inherit; font: inherit; }
  .ai-table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
  table.ai-models { width: 100%; border-collapse: collapse; font-size: .85rem; }
  table.ai-models th, table.ai-models td {
      text-align: left; padding: .45rem .55rem; white-space: nowrap;
      border-bottom: 1px solid var(--bd,#33302C); }
  table.ai-models th { font-size: .7rem; letter-spacing: .06em;
                       text-transform: uppercase; color: var(--muted,#A9A49C); }
  table.ai-models td.num { text-align: right; font-variant-numeric: tabular-nums; }
  .ai-rel { list-style: none; margin: 0; padding: 0; }
  .ai-rel li { padding: .6rem 0; border-bottom: 1px solid var(--bd,#33302C);
               display: flex; gap: .7rem; align-items: baseline; }
  .ai-rel time { flex: 0 0 5.5rem; font-size: .76rem; color: var(--muted,#A9A49C);
                 font-variant-numeric: tabular-nums; }
  .ai-rel .v { flex: 0 0 8.5rem; font-size: .74rem; color: var(--acc-ink,#C4A484); }
  .ai-rel a { color: inherit; }
  .ai-rel .badge { font-size: .62rem; letter-spacing: .05em;
                   text-transform: uppercase; border: 1px solid var(--bd,#33302C);
                   border-radius: 4px; padding: .05rem .3rem; margin-left: .4rem;
                   color: var(--muted,#A9A49C); }
  .ai-more { margin: 1rem 0 0; }
  .ai-more button { border: 1px solid var(--bd,#33302C); background: transparent;
                    color: inherit; border-radius: 8px; padding: .45rem .9rem;
                    font: inherit; cursor: pointer; }
  table.ai-src { width: 100%; border-collapse: collapse; font-size: .8rem; }
  table.ai-src th, table.ai-src td { text-align: left; padding: .4rem .5rem;
      border-bottom: 1px solid var(--bd,#33302C); vertical-align: top; }
  table.ai-src th { font-size: .68rem; letter-spacing: .06em;
                    text-transform: uppercase; color: var(--muted,#A9A49C); }
  @media (max-width: 620px) {
    .ai-rel li { flex-wrap: wrap; }
    .ai-rel time { flex: 0 0 5rem; }
    .ai-rel .v { flex: 0 0 auto; }
  }
</style>
"""

FILTER_JS = """
<script>
(function () {
  var pills = [].slice.call(document.querySelectorAll('.ai-pill'));
  var q = document.getElementById('ai-q');
  var rows = [].slice.call(document.querySelectorAll('[data-vendor]'));
  var none = document.getElementById('ai-none');
  var more = document.getElementById('ai-more');
  var vendor = 'all', text = '', shown = 60;

  /* The filters live in the URL.
     Same rule as What's New and the blog: open a link, press back, and the
     page you come back to is the page you left. It was asked for once and
     then asked for again as "keep the same behaviour everywhere", so a new
     page starting without it would be the third time. */
  function toUrl() {
    var p = new URLSearchParams(location.search);
    vendor === 'all' ? p.delete('v') : p.set('v', vendor);
    text ? p.set('q', text) : p.delete('q');
    var s = p.toString();
    history.replaceState(null, '', s ? '?' + s : location.pathname);
  }
  function fromUrl() {
    var p = new URLSearchParams(location.search);
    vendor = p.get('v') || 'all';
    text = p.get('q') || '';
    if (q) q.value = text;
    pills.forEach(function (b) {
      b.setAttribute('aria-pressed', String(b.dataset.v === vendor));
    });
  }

  function apply(writeUrl) {
    /* The cap counts RELEASES only.
       It counted every matching row, and the model table is rendered first
       -- so 77 new models used the whole budget of 60 and all 401
       announcements were hidden on first paint. The page looked like a
       model table with an empty news section under it, which is a perfectly
       plausible thing for a quiet week to look like. */
    var matched = 0, nRel = 0, hidden = 0;
    var needle = text.toLowerCase();
    rows.forEach(function (el) {
      var okV = vendor === 'all' || el.dataset.vendor === vendor;
      var okQ = !needle || (el.dataset.search || '').indexOf(needle) >= 0;
      var ok = okV && okQ;
      var over = false;
      if (ok) {
        matched += 1;
        if (el.dataset.kind === 'release') {
          nRel += 1;
          over = nRel > shown;
          if (over) { hidden += 1; }
        }
      }
      el.hidden = !ok || over;
    });
    var n = matched;
    if (none) none.hidden = n > 0;
    if (more) {
      more.hidden = hidden === 0;
      var b = more.querySelector('button');
      if (b) b.textContent = 'Show ' + Math.min(hidden, 60) + ' more';
    }
    if (writeUrl !== false) toUrl();
  }

  pills.forEach(function (b) {
    b.addEventListener('click', function () {
      vendor = b.dataset.v;
      pills.forEach(function (o) {
        o.setAttribute('aria-pressed', String(o === b));
      });
      shown = 60;
      apply();
    });
  });
  if (q) {
    q.addEventListener('input', function () { text = q.value.trim(); apply(); });
  }
  if (more) {
    more.addEventListener('click', function () { shown += 60; apply(); });
  }
  fromUrl();
  apply(false);
})();
</script>
"""


def money(v):
    if v is None:
        return "&mdash;"
    if v == 0:
        return "free"
    if v < 1:
        return "$%.2f" % v
    return "$%.2f" % v


def ctx(n):
    if not n:
        return "&mdash;"
    if n >= 1000000:
        return "%.1fM" % (n / 1000000.0)
    if n >= 1000:
        return "%dK" % (n // 1000)
    return str(n)


def build():
    from asset_version import JS_VERSION
    jsv = JS_VERSION

    data = json.load(io.open(STORE, encoding="utf-8"))
    releases = data.get("releases") or []
    models = data.get("models") or []
    sources = data.get("sources") or []
    fetched = data.get("fetched") or ""

    today = dt.date.today()
    cutoff = today - dt.timedelta(days=NEW_DAYS)

    def mdate(m):
        try:
            return dt.date.fromisoformat(m.get("created") or "")
        except ValueError:
            return None

    fresh = sorted([m for m in models if mdate(m) and mdate(m) >= cutoff],
                   key=lambda m: m["created"], reverse=True)

    # The pills are the vendors worth a button, not every publisher in the
    # catalogue. Taking them all gave 57 -- one per OpenRouter prefix,
    # including single-model community uploads -- which is a filter nobody
    # can use. A vendor earns a pill by publishing announcements here, or by
    # having enough models to be worth isolating in the table.
    counts = {}
    for m in models:
        counts[m.get("vendor")] = counts.get(m.get("vendor"), 0) + 1
    speaks = {r.get("vendor") for r in releases}
    vendors = [v for v in VENDOR_ORDER if v in speaks or counts.get(v, 0) >= 5]
    for v, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        if v and v not in vendors and (v in speaks or n >= 8):
            vendors.append(v)

    b = []
    b.append('<main class="ai-wrap">')
    b.append('<div class="ai-head">')
    b.append("<h1>AI, from the vendors&rsquo; own pages</h1>")
    b.append('<p class="ai-lede">What OpenAI, Anthropic, Google, xAI, Meta, '
             'Microsoft, Mistral and DeepSeek have announced, taken from '
             'their own feeds &mdash; and the models that are actually '
             'running, with context windows, prices and the date each one '
             'appeared. Nothing here is written by hand.</p>')
    b.append("</div>")

    b.append('<div class="ai-stats">')
    for big, small in (("{:,}".format(len(models)), "models tracked"),
                       ("{:,}".format(len(releases)), "announcements"),
                       (str(len(vendors)), "vendors"),
                       (str(len(fresh)), "new in %d days" % NEW_DAYS)):
        b.append('<div class="ai-stat"><b>%s</b><span>%s</span></div>'
                 % (big, small))
    b.append("</div>")

    # ---- filters -----------------------------------------------------
    b.append('<div class="ai-pills">')
    b.append('<button type="button" class="ai-pill" data-v="all" '
             'aria-pressed="true">All</button>')
    for v in vendors:
        b.append('<button type="button" class="ai-pill" data-v="%s" '
                 'aria-pressed="false">%s</button>' % (esc(v), esc(v)))
    b.append("</div>")
    # aria-label, not a visually-hidden <label>: .sr-only is not in the CSS
    # this page inherits, so the word "Search" rendered as body text beside
    # the box. A class that does not exist styles nothing and reports
    # nothing.
    b.append('<p><input id="ai-q" class="ai-q" type="search" '
             'aria-label="Search models and announcements" '
             'placeholder="Search models and announcements"></p>')

    # ---- what runs ---------------------------------------------------
    b.append('<section class="ai-sec">')
    b.append("<h2>New models, last %d days</h2>" % NEW_DAYS)
    b.append('<p class="ai-note">Dated by when the model first appeared in '
             'the catalogue, not by when it was announced &mdash; an '
             'aggregator sees a launch hours to days late. Prices are per '
             'million tokens, in and out, as OpenRouter charges them; a '
             'vendor&rsquo;s direct rate can differ.</p>')
    b.append('<div class="ai-table-wrap"><table class="ai-models">')
    b.append("<thead><tr><th>Appeared</th><th>Model</th><th>Vendor</th>"
             "<th>Context</th><th>In</th><th>Out</th><th>Cutoff</th>"
             "</tr></thead><tbody>")
    for m in fresh:
        hay = (m.get("name", "") + " " + m.get("id", "") + " " +
               m.get("vendor", "")).lower()
        b.append('<tr data-kind="model" data-vendor="%s" data-search="%s">'
                 '<td>%s</td><td>%s</td><td>%s</td>'
                 '<td class="num">%s</td><td class="num">%s</td>'
                 '<td class="num">%s</td><td>%s</td></tr>'
                 % (esc(m.get("vendor", "")), esc(hay), esc(m["created"]),
                    esc(m.get("name", "")), esc(m.get("vendor", "")),
                    ctx(m.get("context")), money(m.get("in_per_m")),
                    money(m.get("out_per_m")), esc(m.get("cutoff") or "—")))
    b.append("</tbody></table></div>")
    b.append("</section>")

    # ---- what shipped ------------------------------------------------
    b.append('<section class="ai-sec">')
    b.append("<h2>What shipped</h2>")
    b.append('<p class="ai-note">Every headline links to the vendor&rsquo;s '
             'own page. Entries marked <span class="badge">sitemap</span> '
             'come from a vendor that publishes no feed &mdash; the page was '
             'found by its timestamp and its title read from the page '
             'itself.</p>')
    b.append('<ul class="ai-rel">')
    for r in releases:
        hay = ((r.get("title") or "") + " " + (r.get("summary") or "") + " "
               + (r.get("vendor") or "")).lower()
        badge = ('<span class="badge">sitemap</span>'
                 if r.get("via") == "sitemap" else "")
        b.append('<li data-kind="release" data-vendor="%s" data-search="%s">'
                 '<time>%s</time><span class="v">%s</span>'
                 '<span><a href="%s" rel="noopener">%s</a>%s</span></li>'
                 % (esc(r.get("vendor", "")), esc(hay),
                    esc(r.get("date") or ""), esc(r.get("vendor", "")),
                    esc(r.get("url", "")), esc(r.get("title", "")), badge))
    b.append("</ul>")
    b.append('<p id="ai-none" hidden class="ai-note">Nothing matches those '
             'filters.</p>')
    b.append('<p class="ai-more" id="ai-more" hidden>'
             '<button type="button">Show more</button></p>')
    b.append("</section>")

    # ---- where it comes from ----------------------------------------
    b.append('<section class="ai-sec">')
    b.append("<h2>Where this comes from</h2>")
    b.append('<p class="ai-note">A job on a clock reads these once a day and '
             'commits what it finds, so the page is current whether or not I '
             'open a laptop. Last refreshed <b>%s</b>. The store only grows: '
             'Google&rsquo;s AI feed holds 20 items and Microsoft&rsquo;s '
             '10, so anything not written down within a fortnight would be '
             'gone for good.</p>' % esc((fetched or "")[:16].replace("T", " ")))
    b.append('<div class="ai-table-wrap"><table class="ai-src">')
    b.append("<thead><tr><th>Vendor</th><th>How</th><th>Source</th></tr>"
             "</thead><tbody>")
    for s in sources:
        kind = s.get("kind", "")
        how = {"feed": "their RSS feed",
               "sitemap": "sitemap timestamps (no feed published)",
               "api": "model catalogue API"}.get(kind, kind)
        b.append("<tr><td>%s</td><td>%s</td>"
                 '<td><a href="%s" rel="noopener nofollow">%s</a></td></tr>'
                 % (esc(s.get("vendor", "")), esc(how), esc(s.get("url", "")),
                    esc(s.get("url", "").replace("https://", "")[:58])))
    b.append("</tbody></table></div>")
    b.append('<p class="ai-note">The catalogue is OpenRouter&rsquo;s, which '
             'is an aggregator rather than each vendor&rsquo;s own API: it '
             'lists community models beside official ones and its prices are '
             'its own. It is used because it is the one source that answers '
             'for every vendor at once &mdash; three of them publish no '
             'model API at all.</p>')
    b.append("</section>")
    b.append("</main>")

    html = (head_html(jsv) + STYLE + "</head>\n<body>\n" + nav_html()
            + "\n" + "\n".join(b) + tail_html(jsv) + FILTER_JS)

    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)
    out = os.path.join(OUT_DIR, "index.html")
    with io.open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html)
    print("  %d models (%d new), %d announcements, %d vendors -> %s"
          % (len(models), len(fresh), len(releases), len(vendors),
             os.path.relpath(out, ROOT)))
    print("  %.1fKB" % (os.path.getsize(out) / 1024.0))


if __name__ == "__main__":
    build()
