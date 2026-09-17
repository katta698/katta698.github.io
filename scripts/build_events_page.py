#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build /intelligence/events/ from intelligence/events.json.

    python scripts/build_events_page.py

Why this exists
---------------
Asked for "a single pane of glass across all the events, across all clouds,
across all regions, and all event types", always refreshed and always
trustworthy, linking only to the clouds' own pages.

The first thing that search turned up is that the clouds do not publish this
data. No RSS, no Atom, no schema.org Event markup, and -- checked -- AWS's own
directories API does not serve its events page. Microsoft's AI Tour renders
city dates a browser can read; Google's Next page still showed a date that had
passed; AWS published nothing extractable at all.

So this page is CURATED and the automation verifies rather than gathers.
check_events.py refuses a link that is not on a vendor domain, refuses dates
the vendor has not announced, refuses a row nobody has re-read in 30 days, and
refuses a link that no longer resolves. That is what makes the claim in the
lede defensible.

The nav comes from build_news_page.PAGE rather than being copied. Five files
each holding their own copy of that bar is how the five headers drifted into
four different border colours and three different logo weights, which took
two days to put back. One source, imported.
"""
import datetime as dt
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)

STORE = os.path.join(ROOT, "intelligence", "events.json")
OUT_DIR = os.path.join(ROOT, "intelligence", "events")

CLOUD_NAME = {"aws": "AWS", "azure": "Microsoft Azure", "gcp": "Google Cloud"}
REGION_NAME = {
    "apac": "Asia Pacific", "europe": "Europe",
    "north-america": "North America", "latam": "Latin America",
    "middle-east": "Middle East", "africa": "Africa", "online": "Online",
}
TYPE_NAME = {"conference": "Conference", "tour": "Tour",
             "summit": "Summit", "community": "Community"}


def nav_html():
    """The bar, taken from the What's New builder and re-pointed here.

    Imported rather than copied for the reason in the module docstring. The
    only edit is which link is current: this page is not in the bar, so
    Intelligence stays marked, the way a sub-page should behave.
    """
    import build_news_page as bnp
    page = bnp.PAGE
    start = page.index("<nav>")
    end = page.index("</nav>") + len("</nav>")
    nav = page[start:end]
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
    """The whole head from the What's New builder, re-titled.

    The first version wrote its own head and carried only the four pre-paint
    essentials. The header rendered UNSTYLED -- a 16px logo, underlined nav
    links, the theme control showing the word "Ligh" -- because the bar's CSS
    does not live in site-footer.css alone. Each page carries a large part of
    it in a style block of its own, which is the same duplication that let
    the five headers drift into four border colours and three logo
    weights.

    So this takes the head entire, CSS and all, and changes only what is
    genuinely per-page: the title, the description and the canonical URL. It
    carries some What's New CSS this page never uses -- a few KB -- and in
    exchange the header is not a copy of that bar, it IS that bar.
    """
    import build_news_page as bnp
    head = bnp.PAGE[:bnp.PAGE.index("</head>")]
    head = re.sub(r"<title>.*?</title>",
                  "<title>Cloud events &mdash; AWS, Azure and Google Cloud | "
                  "Jayanth Katta</title>", head, count=1, flags=re.S)
    head = re.sub(r'<meta name="description" content=".*?">',
                  '<meta name="description" content="Conferences, tours '
                  'and summits across AWS, Microsoft Azure and Google Cloud. '
                  'Every entry links to the vendor page and carries the date '
                  'it was last verified.">',
                  head, count=1, flags=re.S)
    head = re.sub(r'<link rel="canonical" href=".*?">',
                  '<link rel="canonical" '
                  'href="https://jayanthkatta.com/intelligence/events/">',
                  head, count=1, flags=re.S)
    head = head.replace("__JSV__", jsv)
    # The head belongs to another page, and that page's builder fills more
    # than one placeholder in it. check_reader_facing caught __RESERVE_WIDE__
    # shipping raw:
    #
    #     .list-reserved{min-height:__RESERVE_WIDE__px}
    #
    # Those reservations hold space for a list this page does not have, so 0
    # is the right value rather than a copied number. Anything else left over
    # is emptied rather than shipped, because a visible __NAME__ on a live
    # page is the single most obviously broken thing a reader can meet.
    head = re.sub(r"__RESERVE_[A-Z]+__", "0", head)
    head = re.sub(r"__[A-Z_]+__", "", head)
    return head


STYLE = """
<!-- This page's own rules, after the shell's.

     The token chain is --bg then --surface, not one or the other. The
     Intelligence family names its ground --bg and does not define --surface;
     the blog names it --surface. This page borrows Intelligence's head, so a
     bare var(--surface, #1F1D1B) fell through to the DARK fallback and the
     page stayed dark in light mode -- the theme class was being set correctly
     the whole time and nothing looked like it was listening. Same for --tx,
     --mut and --bd against --text, --text-muted and --border. -->
<style>
  :root { --ev-gap: 1rem; }
  body { margin: 0; background: var(--bg, var(--surface, #1F1D1B));
         color: var(--tx, var(--text, #EDEBE6));
         font-family: 'DM Sans', system-ui, sans-serif; }
  .ev-wrap { max-width: 62rem; margin: 0 auto; padding: 2rem 1.25rem 5rem; }
  .ev-head h1 { font-family: 'Playfair Display', Georgia, serif;
                font-size: 1.9rem; margin: 0 0 .4rem; font-weight: 600; }
  .ev-lede { color: var(--mut, var(--text-muted, #9C9A94)); margin: 0 0 .35rem;
             font-size: .95rem; line-height: 1.6; max-width: 46rem; }
  /* The honesty line, in the same place and the same words as Live status.
     A page claiming "always refreshed" has to say when it last was. */
  .ev-checked { font-family: 'DM Mono', ui-monospace, monospace;
                font-size: .68rem; letter-spacing: .08em;
                text-transform: uppercase; color: var(--mut, var(--text-muted, #9C9A94));
                margin: 0 0 1.75rem; }
  .ev-filters { display: flex; flex-wrap: wrap; gap: .5rem;
                margin: 0 0 .5rem; }
  .ev-group { display: flex; flex-wrap: wrap; gap: .4rem;
              margin: 0 0 .6rem; align-items: center; }
  .ev-group-label { font-family: 'DM Mono', ui-monospace, monospace;
                    font-size: .62rem; letter-spacing: .12em;
                    text-transform: uppercase;
                    color: var(--mut, var(--text-muted, #9C9A94));
                    min-width: 4.5rem; }
  .ev-pill { font: inherit; font-size: .82rem; cursor: pointer;
             padding: .3rem .8rem; border-radius: 999px;
             background: transparent; color: inherit;
             border: 1px solid var(--bd, var(--border, #2F3131)); }
  .ev-pill[aria-pressed="true"] { background: var(--acc, #C4A484);
                                  color: #1F1D1B; border-color: transparent;
                                  font-weight: 600; }
  .ev-count { font-size: .82rem; color: var(--mut, var(--text-muted, #9C9A94));
              margin: 1.25rem 0 .75rem; }
  .ev-month { font-family: 'DM Mono', ui-monospace, monospace;
              font-size: .66rem; letter-spacing: .14em;
              text-transform: uppercase; color: var(--mut, var(--text-muted, #9C9A94));
              margin: 1.75rem 0 .6rem;
              border-top: 1px solid var(--bd, var(--border, #2F3131));
              padding-top: .8rem; }
  .ev-row { display: block; text-decoration: none; color: inherit;
            padding: .85rem 0; border-bottom: 1px solid var(--bd, var(--border, #2F3131)); }
  .ev-row:hover .ev-name { color: var(--acc-ink, var(--acc, #C4A484)); }
  .ev-top { display: flex; flex-wrap: wrap; gap: .6rem;
            align-items: baseline; }
  .ev-when { font-family: 'DM Mono', ui-monospace, monospace;
             font-size: .76rem; color: var(--acc-ink, var(--acc, #C4A484));
             min-width: 7.5rem; }
  .ev-name { font-size: 1rem; font-weight: 500; }
  .ev-meta { font-size: .78rem; color: var(--mut, var(--text-muted, #9C9A94));
             margin-top: .2rem; }
  .ev-tag { font-family: 'DM Mono', ui-monospace, monospace;
            font-size: .6rem; letter-spacing: .1em; text-transform: uppercase;
            padding: .12rem .45rem; border-radius: 3px;
            border: 1px solid var(--bd, var(--border, #2F3131)); }
  .ev-aws   { color: #D6B896; }
  .ev-azure { color: #9DB6CE; }
  .ev-gcp   { color: #BCC98E; }
  body.light .ev-aws   { color: #705539; }
  body.light .ev-azure { color: #3C5570; }
  body.light .ev-gcp   { color: #515C32; }
  /* Announced-but-undated events are not hidden and not faked.
     A reader looking for re:Invent should find it here with a link to AWS,
     and should be told plainly that AWS has not published the dates. */
  .ev-tbd { opacity: .82; }
  .ev-tbd .ev-when { color: var(--mut, var(--text-muted, #9C9A94)); }
  .ev-none { color: var(--mut, var(--text-muted, #9C9A94)); font-size: .9rem;
             padding: 1.5rem 0; }
  .ev-note { font-size: .78rem; color: var(--mut, var(--text-muted, #9C9A94));
             margin-top: .25rem; font-style: italic; }
  @media (max-width: 600px) {
    .ev-when { min-width: 0; }
    .ev-group-label { min-width: 100%; }
    /* The first event was 1.2 screens down on an iPhone: two paragraphs of
       lede plus three rows of filter pills filled the viewport, so the page
       opened with none of the thing it exists for. The second paragraph is
       an explanation of the TBC rows -- it belongs where those rows are, not
       in front of everything. */
    .ev-lede.ev-lede-2 { display: none; }
    .ev-head h1 { font-size: 1.6rem; }
    /* No padding here for the floating button.
       The first attempt padded the RIGHT of every row. Measured afterwards,
       .back-top sits at left: 24px -- bottom LEFT -- so that added dead space
       on one side and did nothing about the overlap on the other. It is also
       not solvable with padding: the button is position:fixed, so whatever
       happens to be scrolled under it is covered, wherever the padding is.
       It behaves this way on every long page on the site, and is worth
       fixing there rather than papered over here. */
  }
  /* Shown under the list instead, on a phone. */
  .ev-tail-note { display: none; }
  @media (max-width: 600px) {
    .ev-tail-note { display: block; color: var(--mut, var(--text-muted, #9C9A94));
                    font-size: .85rem; line-height: 1.6; margin: 1.5rem 0 0; }
  }
</style>
"""


def fmt_when(e):
    if not e.get("start"):
        return "dates TBC"
    s = dt.date.fromisoformat(e["start"])
    en = dt.date.fromisoformat(e["end"]) if e.get("end") else s
    if s == en:
        return s.strftime("%-d %b %Y") if os.name != "nt" \
            else "%d %s %d" % (s.day, s.strftime("%b"), s.year)
    if (s.month, s.year) == (en.month, en.year):
        return "%d–%d %s %d" % (s.day, en.day, s.strftime("%b"), s.year)
    return "%d %s – %d %s %d" % (s.day, s.strftime("%b"),
                                      en.day, en.strftime("%b"), en.year)


def esc(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def row_html(e):
    cloud = e.get("cloud", "")
    bits = []
    if e.get("city"):
        bits.append(esc(e["city"]))
    if e.get("country") and e.get("country") != e.get("city"):
        bits.append(esc(e["country"]))
    if e.get("online"):
        bits.append("online")
    bits.append(TYPE_NAME.get(e.get("type"), e.get("type", "")))
    tbd = "" if e.get("announced") else " ev-tbd"
    note = ('<div class="ev-note">%s</div>' % esc(e["note"])) \
        if e.get("note") and not e.get("announced") else ""
    return (
        '<a class="ev-row%(tbd)s" href="%(url)s" target="_blank" '
        'rel="noopener" data-cloud="%(cloud)s" data-type="%(type)s" '
        'data-region="%(region)s" data-month="%(month)s">'
        '<div class="ev-top">'
        '<span class="ev-when">%(when)s</span>'
        '<span class="ev-name">%(name)s</span>'
        '<span class="ev-tag ev-%(tagcls)s">%(cloudname)s</span>'
        '</div>'
        '<div class="ev-meta">%(meta)s</div>%(note)s</a>'
    ) % {
        "tbd": tbd,
        "url": esc(e.get("url", "")),
        "cloud": esc(cloud),
        "type": esc(e.get("type", "")),
        "region": esc(e.get("region", "")),
        "month": (e.get("start") or "")[:7],
        "when": esc(fmt_when(e)),
        "name": esc(e.get("name", "")),
        "tagcls": "azure" if cloud == "azure" else esc(cloud),
        "cloudname": esc(CLOUD_NAME.get(cloud, cloud)),
        "meta": esc(" · ".join(b for b in bits if b)),
        "note": note,
    }


def tail_html(jsv):
    """The three things the bar needs that live at the FOOT of a page.

    Reported as: on this page the theme, the music and the rest do nothing.
    Measured -- palette and subscribe worked, theme silently did not (the
    class was never set), and there was no <audio> element on the page at all.

    Taking the head gave this page the bar's markup and its CSS. It did not
    give it the bar's CODE, because that lives at the bottom of each page:

      applyTheme / toggleTheme   an inline script. The nav button calls
                                 toggleTheme() by name, so without it the
                                 button is present, correctly styled, and
                                 inert -- which is exactly the failure the
                                 subscribe button had in September, and it
                                 looks like nothing is wrong.
      <audio id="beach-audio">   the element hero-media.js wires. No element,
                                 no sound, and nothing reports it.
      hero-media.js              the file that picks the track and wires it.

    Only the theme FUNCTIONS are lifted, not the block they sit in. That block
    is 11.5KB and most of it is What's New's own list and filter code, touching
    #list, #q and #svcs -- none of which exist here. Copying it whole would
    have traded a dead button for a console full of errors.

    The audio element comes before the scripts. hero-media.js waits for it
    now, so either order works, but the wrong order is what silenced the music
    button on two pages once already.
    """
    import build_news_page as bnp
    import re as _re
    page = bnp.PAGE
    i = page.rindex("<script>")
    blk = page[i + len("<script>"):page.index("</script>", i)]
    start = blk.index("function applyTheme")
    m = _re.search(r"applyTheme\(localStorage\.getItem\([^;]+;", blk[start:])
    theme = blk[start:start + m.end()]
    return (
        "\n<!-- The bar's own moving parts. See tail_html() for why these\n"
        "     three, and not the whole block they came from. -->\n"
        '<audio id="beach-audio" loop preload="none"></audio>\n'
        "<script>\n" + theme + "\n</script>\n"
        '<script src="/blog/assets/site-footer.js?v=' + jsv +
        '" data-site-footer></script>\n'
        '<script src="/blog/assets/hero-media.js?v=' + jsv + '"></script>\n'
    )


FILTER_JS = """<script>
/* Filtering, done on the rows that are already here.
 *
 * No fetch and no framework: the whole store is a few dozen events, so the
 * page ships with all of them and hides what does not match. That keeps the
 * filters instant, keeps them working with the service worker offline, and
 * means a reader who arrives with JavaScript disabled still sees every event
 * rather than an empty page waiting for a script.
 */
(function () {
  var rows = [].slice.call(document.querySelectorAll('.ev-row'));
  var state = { cloud: 'all', type: 'all', region: 'all' };

  function apply() {
    var shown = 0;
    rows.forEach(function (r) {
      var ok = (state.cloud === 'all' || r.dataset.cloud === state.cloud) &&
               (state.type === 'all' || r.dataset.type === state.type) &&
               (state.region === 'all' || r.dataset.region === state.region);
      r.style.display = ok ? '' : 'none';
      if (ok) shown += 1;
    });
    // Month headings with nothing under them are noise.
    [].slice.call(document.querySelectorAll('.ev-month')).forEach(function (h) {
      var any = false, n = h.nextElementSibling;
      while (n && !n.classList.contains('ev-month')) {
        if (n.classList.contains('ev-row') && n.style.display !== 'none') {
          any = true;
        }
        n = n.nextElementSibling;
      }
      h.style.display = any ? '' : 'none';
    });
    var c = document.getElementById('ev-count');
    if (c) {
      c.textContent = shown === rows.length
        ? shown + ' events'
        : shown + ' of ' + rows.length + ' events';
    }
    var none = document.getElementById('ev-none');
    if (none) none.hidden = shown > 0;
  }

  /* The chosen filters live in the URL, not only in memory.
   *
   * Reported as: "when I select AWS and refresh my screen, it goes back to
   * All." It did -- the selection was a JavaScript variable and nothing else,
   * so every reload threw it away. On a phone that matters more than it
   * sounds, because the installed app reloads on a pull.
   *
   * The URL rather than sessionStorage, because it also makes a filtered view
   * something you can send to somebody: /intelligence/events/?cloud=aws is a
   * link to AWS's events, not to a page they then have to filter themselves.
   *
   * replaceState rather than pushState: tapping four filters should not put
   * four entries in the back stack for a reader to walk out through.
   */
  function toUrl() {
    var q = [];
    ['cloud', 'type', 'region'].forEach(function (k) {
      if (state[k] && state[k] !== 'all') {
        q.push(k + '=' + encodeURIComponent(state[k]));
      }
    });
    var url = location.pathname + (q.length ? '?' + q.join('&') : '');
    try { history.replaceState(null, '', url + location.hash); } catch (e) {}
  }

  function fromUrl() {
    var p;
    try { p = new URLSearchParams(location.search); } catch (e) { return; }
    ['cloud', 'type', 'region'].forEach(function (k) {
      var v = p.get(k);
      if (!v) return;
      // Only a value this page actually offers. A hand-edited URL asking for
      // ?cloud=oracle should show everything, not nothing.
      var pill = document.querySelector(
        '.ev-pill[data-group="' + k + '"][data-value="' + v + '"]');
      if (!pill) return;
      state[k] = v;
      [].slice.call(document.querySelectorAll(
        '.ev-pill[data-group="' + k + '"]')).forEach(function (o) {
        o.setAttribute('aria-pressed', String(o === pill));
      });
    });
  }

  document.addEventListener('click', function (ev) {
    var b = ev.target.closest && ev.target.closest('.ev-pill');
    if (!b) return;
    var group = b.dataset.group;
    state[group] = b.dataset.value;
    [].slice.call(document.querySelectorAll(
      '.ev-pill[data-group="' + group + '"]')).forEach(function (o) {
      o.setAttribute('aria-pressed', String(o === b));
    });
    apply();
    toUrl();
  });

  fromUrl();
  apply();
})();
</script>
</body>
</html>
"""


def pills(group, label, values, names):
    out = ['<div class="ev-group"><span class="ev-group-label">%s</span>'
           % esc(label)]
    out.append('<button type="button" class="ev-pill" data-group="%s" '
               'data-value="all" aria-pressed="true">All</button>' % group)
    for v in values:
        out.append('<button type="button" class="ev-pill" data-group="%s" '
                   'data-value="%s" aria-pressed="false">%s</button>'
                   % (group, esc(v), esc(names.get(v, v))))
    out.append("</div>")
    return "".join(out)


def build():
    from asset_version import JS_VERSION
    jsv = JS_VERSION

    data = json.load(io.open(STORE, encoding="utf-8"))
    events = data.get("events", [])
    today = dt.date.today()

    # Past events are not deleted from the store -- that is the record of what
    # was verified -- but they do not belong on a page about what is coming.
    upcoming = []
    for e in events:
        if not e.get("start"):
            upcoming.append(e)
            continue
        try:
            if dt.date.fromisoformat(e.get("end") or e["start"]) >= today:
                upcoming.append(e)
        except ValueError:
            upcoming.append(e)

    dated = sorted([e for e in upcoming if e.get("start")],
                   key=lambda x: x["start"])
    undated = [e for e in upcoming if not e.get("start")]

    clouds = [c for c in ("aws", "azure", "gcp")
              if any(e.get("cloud") == c for e in upcoming)]
    types = sorted({e.get("type") for e in upcoming if e.get("type")})
    regions = [r for r in ("north-america", "europe", "apac", "latam",
                           "middle-east", "africa", "online")
               if any(e.get("region") == r for e in upcoming)]

    body = []
    body.append('<div class="ev-wrap"><div class="ev-head">')
    body.append("<h1>Cloud events</h1>")
    body.append(
        '<p class="ev-lede">Conferences, tours and summits across AWS, '
        'Microsoft Azure and Google Cloud. Every entry links to the cloud’s '
        'own page — nothing here is second-hand — and carries the date it '
        'was last read off that page.</p>')
    body.append(
        '<p class="ev-lede ev-lede-2">Where a cloud has announced an event '
        'but not its dates, it is listed without them. A date nobody '
        'published is worse than no date: people book flights around '
        'these.</p>')
    body.append('<p class="ev-checked">All %d links verified %s</p>'
                % (len(events), esc(data.get("verified", "—"))))
    body.append("</div>")

    body.append('<div class="ev-filters">')
    body.append(pills("cloud", "Cloud", clouds, CLOUD_NAME))
    body.append(pills("type", "Type", types, TYPE_NAME))
    body.append(pills("region", "Region", regions, REGION_NAME))
    body.append("</div>")
    body.append('<p class="ev-count" id="ev-count">%d events</p>'
                % len(upcoming))

    month = None
    for e in dated:
        m = e["start"][:7]
        if m != month:
            month = m
            body.append('<div class="ev-month">%s</div>'
                        % dt.date.fromisoformat(e["start"]).strftime("%B %Y"))
        body.append(row_html(e))

    if undated:
        body.append('<div class="ev-month">Announced, dates not yet '
                    'published</div>')
        for e in undated:
            body.append(row_html(e))

    body.append('<p class="ev-none" id="ev-none" hidden>Nothing matches '
                'those filters.</p>')
    body.append('<p class="ev-tail-note">Where a cloud has announced an event '
                'but not its dates, it is listed without them. A date nobody '
                'published is worse than no date: people book flights around '
                'these.</p>')
    body.append("</div>")

    html = (head_html(jsv) + STYLE + "</head>\n<body>\n" + nav_html()
            + "\n" + "\n".join(body) + tail_html(jsv)
            + FILTER_JS.replace("__JSV__", jsv))

    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)
    out = os.path.join(OUT_DIR, "index.html")
    with io.open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html)
    print("  %d upcoming (%d dated, %d awaiting dates) -> %s"
          % (len(upcoming), len(dated), len(undated),
             os.path.relpath(out, ROOT)))
    print("  %.1fKB" % (os.path.getsize(out) / 1024.0))


if __name__ == "__main__":
    build()
