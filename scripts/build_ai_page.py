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
import math
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
                  "<title>j.AI &mdash; AI releases and models from OpenAI, "
                  "Anthropic, Google and xAI | Jayanth Katta</title>",
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
  /* --ai-muted, because there is no --muted on this page.
     Measured after a light-mode screenshot read as washed out: the shell
     defines --bg, --text, --border, --accent and nothing else, so every
     var(--muted,#A9A49C) and var(--bd,#33302C) in here was using its
     DARK-MODE fallback in both themes. Body copy came out at 2.30:1 on
     cream -- below the 4.5:1 floor and exactly the "very light" in the
     report -- and the pill borders were a dark-theme charcoal on a pale
     page.
     Derived from --text rather than picked, so it cannot drift from the
     theme it belongs to. */
  .ai-wrap { --ai-muted: color-mix(in srgb, var(--text,#EDEBE6) 66%,
                                   transparent); }
  .ai-wrap { max-width: 1120px; margin: 0 auto; padding: 1.5rem 1rem 4rem; }
  /* line-height 1.12, not 1: the "j" is italic and its tail drops well
     below the baseline, so at a flat 1 it grazed the line beneath. */
  .ai-mark { margin: .2rem 0 .3rem; line-height: 1.12;
             font-size: clamp(2.6rem,8vw,3.6rem); letter-spacing: -.015em; }
  .ai-mark .jm { font-size: .46em; color: var(--acc-ink,var(--accent,#C4A484));
                 font-style: italic; }
  .ai-mark .dot { font-size: .38em; color: var(--ai-muted);
                  margin: 0 .04em; }
  .ai-mark .ai { letter-spacing: .01em; }
  .ai-sub { margin: 0 0 .8rem; font-size: .92rem; letter-spacing: .02em;
            color: var(--ai-muted); }
  .ai-lede { color: var(--ai-muted); max-width: 62ch; line-height: 1.65; }
  .ai-stats { display: flex; flex-wrap: wrap; gap: .6rem; margin: 1.1rem 0; }
  .ai-stat { border: 1px solid var(--border,#33302C); border-radius: 10px;
             padding: .5rem .75rem; min-width: 7rem; }
  .ai-stat b { display: block; font-size: 1.15rem; }
  .ai-stat span { font-size: .68rem; letter-spacing: .06em;
                  text-transform: uppercase; color: var(--ai-muted); }
  .ai-jump { display: flex; flex-wrap: wrap; gap: .4rem; margin: .2rem 0 1rem; }
  .ai-jump a { border: 1px solid var(--border,#33302C); border-radius: 999px;
               padding: .3rem .72rem; font-size: .74rem; text-decoration: none;
               color: inherit; opacity: .85; }
  .ai-jump a:hover, .ai-jump a:focus-visible {
      border-color: var(--acc-ink,var(--accent,#C4A484)); color: var(--acc-ink,var(--accent,#C4A484));
      opacity: 1; }
  /* scroll-margin-top, or the heading lands under the sticky header.
     The bar is 64px and sticks at the top, so an anchor jump puts the
     target's first line behind it -- the page moves, the heading is not
     there, and it reads as a link that went to the wrong place. */
  .ai-sec { margin-top: 2.2rem; scroll-margin-top: 82px; }
  html { scroll-behavior: smooth; }
  @media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } }
  .ai-sec h2 { font-size: 1.15rem; margin: 0 0 .3rem; }
  .ai-note { color: var(--ai-muted); font-size: .84rem;
             line-height: 1.6; max-width: 70ch; margin: 0 0 .9rem; }
  .ai-pills { display: flex; flex-wrap: wrap; gap: .4rem; margin: .8rem 0; }
  .ai-pill { border: 1px solid var(--border,#33302C); background: transparent;
             color: inherit; border-radius: 999px; padding: .28rem .7rem;
             font-size: .76rem; cursor: pointer; }
  /* The chosen pill uses --accent, not --acc-ink.
     --acc-ink is #6E5236 in light mode, a colour tuned for small TEXT on
     pale, and as a filled pill it gave #1F1D1B on #6E5236 = 2.34:1. The
     same inversion the play button had on the walkthrough: a text colour
     doing a fill's job. --accent is #C4A484 in both themes, so the pill
     looks like itself either way and the label sits at 5.05:1. */
  .ai-pill[aria-pressed="true"] { background: var(--accent,#C4A484);
                                  border-color: var(--accent,#C4A484);
                                  color: #1F1D1B; }
  .ai-q { width: 100%; max-width: 22rem; padding: .45rem .6rem;
          border-radius: 8px; border: 1px solid var(--border,#33302C);
          background: transparent; color: inherit; font: inherit; }
  .ai-field-wrap { margin: 0; }
  .ai-field { width: 100%; height: auto; display: block;
              border: 1px solid var(--border,#33302C); border-radius: 12px;
              background: color-mix(in srgb, var(--bg,#1D1E1B) 88%, #000); }
  /* Light mode gets a WARM panel, not a darkened one.
     color-mix(cream, black) is grey, and a grey slab in the middle of a
     warm cream page is the "clumsy" in the report -- it reads as a
     different site's component dropped in. Mixed toward the accent instead,
     it sits in the palette. The dots also need help: a pastel tuned for a
     dark background is washed out on a pale one, so they are deepened
     rather than recoloured, which keeps one vendor one colour in both
     themes. */
  body.light .ai-field { background: color-mix(in srgb,
                         var(--bg,#F5F7F2) 94%, #C4A484); }
  body.light .ai-field .fd { filter: saturate(1.5) brightness(.68); }
  body.light .ai-field .fold { filter: saturate(.2) brightness(1.15); }
  .ai-field .fg { stroke: currentColor; stroke-width: .5; opacity: .16; }
  .ai-field .fl { fill: currentColor; opacity: .55;
                  font: 10px 'DM Mono', ui-monospace, monospace; }
  .ai-field .fa { fill: currentColor; opacity: .4; letter-spacing: .08em;
                  font: 9px 'DM Mono', ui-monospace, monospace;
                  text-transform: uppercase; }
  .ai-field .ffree { stroke-dasharray: 3 4; opacity: .28; }
  /* Old models are background, not data you are meant to read. */
  .ai-field .fold { opacity: .3; }
  .ai-field .fm { stroke: var(--acc-ink,var(--accent,#C4A484)); stroke-width: 1;
                  stroke-dasharray: 2 4; opacity: .5; }
  .ai-field .fmold { opacity: .3; }
  .ai-field .fml { fill: currentColor; opacity: .5; letter-spacing: .04em;
                   font: 9px 'DM Mono', ui-monospace, monospace; }
  .ai-field .fd { opacity: .85; cursor: pointer;
                  transition: opacity .15s ease, r .15s ease; }
  .ai-field .fd:hover, .ai-field .fd.on { opacity: 1; r: 6.5; }
  /* Bigger dots where there are fingers.
     The chart keeps its 900-unit viewBox at every width, so on a 412px
     phone it renders 380px wide and a 3-unit dot is 1.3 SCREEN PIXELS.
     Measured, not guessed -- and 1.3px is not a target, it is a rumour.
     At 5.5 units it lands near 2.3px drawn and a far more forgiving tap
     area, because an SVG shape's hit region scales with it. */
  @media (pointer: coarse) {
    .ai-field .fd { r: 5.5; }
    .ai-field .fnew { r: 7; }
    .ai-field .fd:hover, .ai-field .fd.on { r: 9; }
  }
  /* The new ones breathe. Nothing else on the chart moves, so the eye goes
     to what changed this month without anything being labelled "new". */
  .ai-field .fnew { animation: aipulse 2.8s ease-in-out infinite; }
  @keyframes aipulse { 0%, 100% { opacity: .55; } 50% { opacity: 1; } }
  /* A dimmed dot is scenery, not a target.
     Reported with a screenshot: Google selected, and the readout naming
     "Tencent: Hy3". Dimming changed how the other vendors LOOKED and left
     them fully clickable, so a finger anywhere in the crowd still named
     whatever happened to be under it -- usually not the vendor just
     chosen. Filtering that only changes opacity is a filter in appearance
     only. */
  .ai-field.dimmed .fd { opacity: .1; pointer-events: none; }
  .ai-field.dimmed .fd.keep { opacity: 1; pointer-events: auto; }
  .ai-readout-row { display: flex; align-items: center; gap: .7rem;
                    margin: .55rem 0 0; }
  .ai-bot { flex: 0 0 auto; width: 42px; height: 47px; color: inherit;
            opacity: .85; }
  .ai-bot .bl { fill: none; stroke: currentColor; stroke-width: 2;
                stroke-linecap: round; stroke-linejoin: round; opacity: .55; }
  .ai-bot .bdot { fill: var(--acc-ink,var(--accent,#C4A484)); stroke: none; opacity: .9;
                  animation: aiblip 3.4s ease-in-out infinite; }
  .ai-bot .bp { fill: var(--acc-ink,var(--accent,#C4A484)); opacity: .9;
                transition: transform .22s cubic-bezier(.2,.7,.3,1); }
  /* The blink is a scale, not an opacity: an eye that fades looks broken,
     an eye that squashes looks alive. 6.4s apart, because a blink every
     couple of seconds reads as a nervous tic rather than a pause. */
  .ai-bot .beyes { animation: aiblink 6.4s infinite; transform-origin: 32px 31px; }
  @keyframes aiblink { 0%, 94%, 100% { transform: scaleY(1); }
                       96.5% { transform: scaleY(.08); } }
  @keyframes aiblip { 0%, 100% { opacity: .35; } 50% { opacity: 1; } }
  @media (prefers-reduced-motion: reduce) {
    .ai-bot .beyes, .ai-bot .bdot, .ai-field .fnew { animation: none; }
  }
  .ai-readout { min-height: 1.4rem; font-size: .82rem;
                font-family: 'DM Mono', ui-monospace, monospace;
                color: var(--ai-muted); }
  .ai-readout b { color: inherit; }
  .ai-readout .ph { opacity: .7; }
  .ai-hint { display: none; margin: .4rem 0 0; font-size: .68rem;
             letter-spacing: .08em; text-transform: uppercase;
             color: var(--ai-muted); opacity: .75; }
  @media (max-width: 760px) { .ai-hint { display: block; } }
  .ai-legend { color: var(--ai-muted); font-size: .78rem;
               line-height: 1.6; max-width: 72ch; margin: 0 0 .7rem; }
  .ai-legend b { color: inherit; opacity: .95; }
  .ai-table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
  table.ai-models { width: 100%; border-collapse: collapse; font-size: .85rem; }
  table.ai-models th, table.ai-models td {
      text-align: left; padding: .45rem .55rem; white-space: nowrap;
      border-bottom: 1px solid var(--border,#33302C); }
  table.ai-models th { font-size: .7rem; letter-spacing: .06em;
                       text-transform: uppercase; color: var(--ai-muted); }
  table.ai-models td.num { text-align: right; font-variant-numeric: tabular-nums; }
  /* [hidden] has to win, and here it did not.
     `.ai-rel li { display: flex }` is more specific than the browser's own
     `[hidden] { display: none }`, so every row the filter "hid" was still
     laid out and still on screen. Measured: 341 of 401 rows carried the
     attribute, 0 were actually display:none, and the page ran to 37,949px
     -- 42 screens -- which is what made scrolling to the sources table feel
     endless. The cap and the filters had been drawing a chart of their own
     intentions.
     Scoped to this page rather than global, and !important because the rule
     it has to beat is the one being set two lines below. */
  .ai-wrap [hidden] { display: none !important; }
  .ai-rel { list-style: none; margin: 0; padding: 0; }
  .ai-rel li { padding: .6rem 0; border-bottom: 1px solid var(--border,#33302C);
               display: flex; gap: .7rem; align-items: baseline; }
  .ai-rel time { flex: 0 0 5.5rem; font-size: .76rem; color: var(--ai-muted);
                 font-variant-numeric: tabular-nums; }
  .ai-rel .v { flex: 0 0 8.5rem; font-size: .74rem; color: var(--acc-ink,var(--accent,#C4A484)); }
  .ai-rel a { color: inherit; }
  .ai-rel .badge { font-size: .62rem; letter-spacing: .05em;
                   text-transform: uppercase; border: 1px solid var(--border,#33302C);
                   border-radius: 4px; padding: .05rem .3rem; margin-left: .4rem;
                   color: var(--ai-muted); }
  .ai-more { margin: 1rem 0 0; }
  .ai-more button { border: 1px solid var(--border,#33302C); background: transparent;
                    color: inherit; border-radius: 8px; padding: .45rem .9rem;
                    font: inherit; cursor: pointer; }
  table.ai-src { width: 100%; border-collapse: collapse; font-size: .8rem; }
  table.ai-src th, table.ai-src td { text-align: left; padding: .4rem .5rem;
      border-bottom: 1px solid var(--border,#33302C); vertical-align: top; }
  table.ai-src th { font-size: .68rem; letter-spacing: .06em;
                    text-transform: uppercase; color: var(--ai-muted); }
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
    var noModels = document.getElementById('ai-nomodels');
    if (noModels) {
      var anyModel = rows.some(function (el) {
        return el.dataset.kind === 'model' && !el.hidden;
      });
      noModels.hidden = anyModel;
    }
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

  /* The refresh time, restated in the reader's own zone.
     Server-rendered it is UTC and says so; a browser knows better and can
     name the zone it is in. The "ago" is the part that answers the real
     question, which is not what time it was but whether it is stale. */
  var when = document.querySelector('[data-when]');
  if (when && when.dateTime) {
    var d = new Date(when.dateTime);
    if (!isNaN(d)) {
      var mins = Math.round((Date.now() - d.getTime()) / 60000);
      var ago = mins < 2 ? 'just now'
        : mins < 60 ? mins + ' minutes ago'
        : mins < 120 ? 'an hour ago'
        : mins < 1440 ? Math.round(mins / 60) + ' hours ago'
        : Math.round(mins / 1440) + ' days ago';
      var zone = '';
      try {
        zone = new Intl.DateTimeFormat(undefined, {timeZoneName: 'short'})
          .formatToParts(d).filter(function (p) {
            return p.type === 'timeZoneName';
          })[0].value;
      } catch (e) { zone = ''; }
      var local = d.toLocaleString(undefined, {
        year: 'numeric', month: 'short', day: 'numeric',
        hour: 'numeric', minute: '2-digit'
      });
      when.innerHTML = '<b>' + local + (zone ? ' ' + zone : '') + '</b> (' +
                       ago + ')';
      when.title = when.dateTime;
    }
  }

  /* The field answers to the same pills, and to a finger.
     A dot names itself on hover for a mouse and on tap for a phone, where
     there is no hover at all -- a chart that only speaks to a pointer says
     nothing on the device most people are holding. */
  var field = document.querySelector('.ai-field');
  var readout = document.getElementById('ai-readout');
  if (field && readout) {
    var dots = [].slice.call(field.querySelectorAll('.fd'));
    var placeholder = readout.innerHTML;
    var last = null;
    // What it rests on: the newest model on the chart, which is the thing a
    // reader arriving at an AI page most likely came to see.
    var newest = dots.slice().sort(function (a, b) {
      return (b.dataset.d || '').localeCompare(a.dataset.d || '');
    })[0] || null;

    /* Where the watcher is looking. The dot's x across the chart maps to a
       small shift of the pupils, and its y to a smaller one -- a couple of
       pixels is enough to read as a glance, and more looks like a fault. */
    var eyes = document.querySelectorAll('.ai-bot .bp');
    function gaze(el) {
      if (!eyes.length) { return; }
      var dx = 0, dy = 0;
      if (el) {
        var box = field.viewBox.baseVal;
        dx = ((+el.getAttribute('cx') / box.width) - 0.5) * 4.4;
        dy = ((+el.getAttribute('cy') / box.height) - 0.5) * 3.0;
      }
      eyes.forEach(function (e) {
        e.style.transform = 'translate(' + dx.toFixed(2) + 'px,' +
                            dy.toFixed(2) + 'px)';
      });
    }

    function name(el) {
      if (last) { last.classList.remove('on'); }
      last = el;
      gaze(el || newest);
      if (!el) { readout.innerHTML = placeholder; return; }
      el.classList.add('on');
      /* Spelled out, not abbreviated. This is the first line most people
         read on the page, and "1.0M context - $0.40 per million out" is
         legible only to somebody who already knows both terms. */
      readout.innerHTML = '<b>' + el.dataset.n + '</b> &middot; ' +
        el.dataset.vendor + ' &middot; holds ' + el.dataset.c + ' tokens' +
        (el.dataset.w ? ' (about ' + el.dataset.w + ' words)' : '') +
        ' &middot; ' + el.dataset.p +
        ' per million tokens it writes &middot; appeared ' + el.dataset.d;
    }

    dots.forEach(function (el) {
      el.addEventListener('mouseenter', function () { name(el); });
      el.addEventListener('click', function (e) { e.stopPropagation(); name(el); });
    });
    field.addEventListener('mouseleave', function () { name(null); });
    gaze(newest);

    /* Dimming, driven by the vendor already chosen above. The pills were
       filtering two lists and leaving the picture alone, which made the
       chart look like it belonged to a different page. */
    var paintField = function () {
      if (vendor === 'all') {
        field.classList.remove('dimmed');
        dots.forEach(function (d) { d.classList.remove('keep'); });
        return;
      }
      field.classList.add('dimmed');
      /* Painted last, so they are on top.
         SVG has no z-index: order in the document IS depth. At 1M context
         the dots stack dozens deep, so the vendor just chosen was often
         underneath somebody else's -- lit up, and still losing the tap to
         the dimmed dot drawn after it. Moving the kept ones to the end of
         the parent puts them in front, which is also where the pointer
         finds them first. */
      var parent = dots.length ? dots[0].parentNode : null;
      dots.forEach(function (d) {
        var keep = d.dataset.vendor === vendor;
        d.classList.toggle('keep', keep);
        if (keep && parent) { parent.appendChild(d); }
      });
    };
    pills.forEach(function (b) { b.addEventListener('click', paintField); });
    paintField();
  }
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


def words(tokens):
    """A token is about three quarters of a word in English.

    Rounded hard, because the ratio is a rule of thumb: "about 195,000
    words" invites a precision the conversion does not have, and the number
    exists to give a reader something to picture rather than to be added up.
    """
    if not tokens:
        return ""
    w = int(tokens) * 0.75
    if w >= 1000000:
        return "%.1f million" % (w / 1000000.0)
    if w >= 1000:
        return "%d,000" % round(w / 1000.0)
    return str(int(w))


def ctx(n):
    if not n:
        return "&mdash;"
    if n >= 1000000:
        return "%.1fM" % (n / 1000000.0)
    if n >= 1000:
        return "%dK" % (n // 1000)
    return str(n)




# A watcher, drawn in the walkthrough's line style.
#
# Asked for as: "some sort of robot, like Optimus from Tesla -- since this is
# an AI page I was wondering we could add something more creative."
#
# A robot that only stands there is a sticker. This one has a job: its eyes
# follow the dot being pointed at, and when nothing is pointed at they rest
# on the newest model in the field. So it is always looking at the thing the
# page is actually about, and a reader can tell at a glance whether the
# chart is idle or answering them.
#
# Line art rather than a render: it is 1.3KB of SVG that takes its colour
# from the theme and needs no image, no font and no request. The same choice
# the walkthrough made, and for the same reason -- a PNG of a robot would be
# a 200KB decision about somebody else's taste in robots.
WATCHER = """
<svg class="ai-bot" viewBox="0 0 64 72" aria-hidden="true" focusable="false">
  <path class="bl" d="M32 8 V16"/>
  <circle class="bl bdot" cx="32" cy="6" r="2.4"/>
  <rect class="bl" x="12" y="16" width="40" height="32" rx="9"/>
  <g class="beyes">
    <ellipse class="bp" cx="24" cy="31" rx="4.6" ry="5.2"/>
    <ellipse class="bp" cx="40" cy="31" rx="4.6" ry="5.2"/>
  </g>
  <path class="bl bmouth" d="M25 41 q7 4 14 0"/>
  <path class="bl" d="M12 30 H6 M52 30 H58"/>
  <path class="bl" d="M20 48 V56 q0 6 6 6 h12 q6 0 6 -6 V48"/>
</svg>
"""

# ---------------------------------------------------------------- the field
#
# Asked for as: "the globe blinks and it's interactive -- people can look for
# regions and see incidents there. Is there anything creative like that for
# this page? Something animated, or a robot like Optimus."
#
# The globe works because it is not decoration: every dot is an incident a
# vendor published, in the place the vendor named. A robot would be a picture
# of a robot. So this is the same idea with this page's own data -- every
# model in the catalogue, placed where its numbers put it.
#
#     across   context window, 4K to 2M, logarithmic
#     up       what a million output tokens costs, 3 cents to $600, logarithmic
#     colour   the vendor
#     pulsing  appeared in the last 30 days
#
# Both axes have to be logarithmic or the picture is a smear: contexts run
# over three orders of magnitude and prices over four. Grid lines are labelled
# at the powers so the scale is legible rather than implied.
#
# The five router models that quote no price are NOT plotted, and the count is
# printed under the chart. Same rule the incident map follows for a region
# with no published location: dropping it silently would make the picture
# claim a completeness it does not have.
VCOLOR = {
    "OpenAI": "#7FB3A3", "Anthropic": "#C4A484", "Google": "#8FA8C8",
    "xAI": "#B98C9A", "Meta": "#8A9A5B", "Microsoft": "#9A8FC8",
    "Mistral": "#CFA06B", "DeepSeek": "#6FA8B8", "Qwen": "#B0A06B",
}
FIELD_W, FIELD_H = 900.0, 430.0
PAD_L, PAD_R, PAD_T, PAD_B = 58.0, 18.0, 20.0, 40.0


def _lx(ctx_tokens):
    lo, hi = math.log10(4000.0), math.log10(2200000.0)
    v = (math.log10(max(4000.0, float(ctx_tokens))) - lo) / (hi - lo)
    return PAD_L + v * (FIELD_W - PAD_L - PAD_R)


def _ly(price):
    lo, hi = math.log10(0.02), math.log10(700.0)
    v = (math.log10(max(0.02, float(price))) - lo) / (hi - lo)
    return (FIELD_H - PAD_B) - v * (FIELD_H - PAD_T - PAD_B)


def field_svg(models, today):
    # Free is a price, not a missing one.
    #
    # The first version treated "0" as falsy and swept 29 free models in with
    # the 5 routers that genuinely quote nothing, then told the reader all 34
    # "quote no fixed price". Two different facts, one wrong sentence. Zero
    # cannot sit on a logarithmic axis, so free models get a lane of their
    # own along the floor, labelled -- and only the routers, which really do
    # charge whatever they route to, are left off and counted.
    plotted, freebies, skipped = [], [], []
    for m in models:
        if not m.get("context") or m.get("out_per_m") is None:
            skipped.append(m)
        elif m.get("out_per_m") == 0:
            freebies.append(m)
        else:
            plotted.append(m)

    g = ['<svg class="ai-field" viewBox="0 0 %d %d" '
         'preserveAspectRatio="xMidYMid meet" role="img" '
         'aria-label="Every model in the catalogue, placed by context window '
         'across and price per million output tokens up. %d models are '
         'plotted.">' % (FIELD_W, FIELD_H, len(plotted))]

    for tokens, label in ((4000, "4K"), (32000, "32K"), (128000, "128K"),
                          (1000000, "1M"), (2000000, "2M")):
        x = _lx(tokens)
        g.append('<line class="fg" x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>'
                 % (x, PAD_T, x, FIELD_H - PAD_B))
        g.append('<text class="fl" x="%.1f" y="%.1f" text-anchor="middle">%s'
                 "</text>" % (x, FIELD_H - PAD_B + 16, label))
    for price, label in ((0.05, "$0.05"), (1, "$1"), (10, "$10"),
                         (100, "$100"), (600, "$600")):
        y = _ly(price)
        g.append('<line class="fg" x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>'
                 % (PAD_L, y, FIELD_W - PAD_R, y))
        g.append('<text class="fl" x="%.1f" y="%.1f" text-anchor="end">%s'
                 "</text>" % (PAD_L - 8, y + 3, label))
    free_y = FIELD_H - PAD_B + 4
    g.append('<line class="fg ffree" x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>'
             % (PAD_L, free_y, FIELD_W - PAD_R, free_y))
    g.append('<text class="fl" x="%.1f" y="%.1f" text-anchor="end">free</text>'
             % (PAD_L - 8, free_y + 3))
    # The two medians, drawn, because a number in prose under a chart is a
    # number nobody maps back onto it.
    st = field_story(models, today) or {}
    for tokens, label, cls in (
            (st.get("from_ctx") or 131072,
             "median " + (st.get("from_q") or ""), "fmold"),
            (st.get("to_ctx") or 1048576,
             "median " + (st.get("to_q") or "now"), "fmnow")):
        x = _lx(tokens)
        g.append('<line class="fm %s" x1="%.1f" y1="%.1f" x2="%.1f" '
                 'y2="%.1f"/>' % (cls, x, PAD_T + 6, x, FIELD_H - PAD_B))
        g.append('<text class="fml %s" x="%.1f" y="%.1f" text-anchor="%s">%s'
                 "</text>" % (cls, x + (5 if cls == "fmold" else -5), PAD_T + 14,
                              "start" if cls == "fmold" else "end", label))
    g.append('<text class="fa" x="%.1f" y="%.1f">context window &#8594;</text>'
             % (PAD_L, FIELD_H - 6))
    g.append('<text class="fa" x="13" y="%.1f" transform="rotate(-90 13 %.1f)">'
             "cost per million out</text>" % (FIELD_H - PAD_B, FIELD_H - PAD_B))

    # Newest last, so a fresh model is drawn on top of the crowd it joins.
    for m in sorted(plotted + freebies, key=lambda x: x.get("created") or ""):
        created = m.get("created") or ""
        new = False
        try:
            new = (today - dt.date.fromisoformat(created)).days <= 30
        except ValueError:
            pass
        # A model older than a year is drawn as grey background.
        #
        # 441 dots of equal weight hid the one thing this chart knows:
        # measured from the same data, the median context window went from
        # 131,072 in late 2024 to 1,048,576 now, while the median price only
        # doubled. The field MOVED, and a flat scatter cannot show movement.
        # Fading what is old leaves the recent models standing in colour on
        # the right of a grey crowd, which is the shift, drawn.
        old = False
        try:
            old = (today - dt.date.fromisoformat(created)).days > 365
        except ValueError:
            pass
        colour = "#7C766E" if old else VCOLOR.get(m["vendor"], "#8A857E")
        g.append('<circle class="fd%s%s" cx="%.1f" cy="%.1f" r="%s" '
                 'fill="%s" data-vendor="%s" data-n="%s" data-c="%s" '
                 'data-p="%s" data-d="%s" data-w="%s"/>'
                 % (" fnew" if new else "", " fold" if old else "",
                    _lx(m["context"]),
                    free_y if m["out_per_m"] == 0 else _ly(m["out_per_m"]),
                    "4.2" if new else "3",
                    colour, esc(m["vendor"]), esc(m.get("name", "")),
                    ctx(m.get("context")), money(m.get("out_per_m")),
                    esc(created), words(m.get("context"))))
    g.append("</svg>")
    return chr(10).join(g), len(plotted) + len(freebies), skipped



def field_story(models, today):
    """The shift, measured, every build.

    The first version of the sentence under the chart carried the numbers I
    had just measured by hand -- 131,072 to 1,048,576, $0.82 to $2.20. True
    that evening, and the same mistake the narration made: a figure typed
    into prose is a figure that goes stale while the page keeps rendering.
    The colophon has a check for exactly this, and this page would have
    walked into it from the other side.

    So both ends are computed. The old end is the earliest quarter that has
    at least eight models in it -- fewer than that and a median is an
    anecdote -- and the new end is the most recent quarter with the same
    floor.
    """
    import statistics
    rows = [m for m in models
            if m.get("context") and m.get("out_per_m") and m.get("created")]
    buckets = {}
    for m in rows:
        y, mo, _ = m["created"].split("-")
        buckets.setdefault("%s-Q%d" % (y, (int(mo) - 1) // 3 + 1), []).append(m)
    full = sorted(k for k, v in buckets.items() if len(v) >= 8)
    if len(full) < 2:
        return None
    first, last = buckets[full[0]], buckets[full[-1]]

    def med(group, key):
        return statistics.median(x[key] for x in group)

    big = [m for m in rows if m["context"] >= 1000000]
    cheap = min(big, key=lambda m: m["out_per_m"]) if big else None
    return {
        "from_q": full[0], "to_q": full[-1],
        "from_ctx": int(med(first, "context")),
        "to_ctx": int(med(last, "context")),
        "from_price": med(first, "out_per_m"),
        "to_price": med(last, "out_per_m"),
        "big": len(big),
        "cheap_price": cheap["out_per_m"] if cheap else None,
        "cheap_name": cheap["name"] if cheap else "",
    }


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
    # j.AI -- a small quiet "j", the AI carrying the weight.
    #
    # Asked for as: "since my name is Jay, I like my AI page as jAI, or j in
    # small highlighting AI -- something like j.AI."
    #
    # The dot is what makes it a mark rather than a typo: "jAI" reads as the
    # name Jai and loses the AI entirely, where "j.AI" reads as a namespace
    # and puts the emphasis exactly where it was asked to go. The <h1> is
    # the mark, and the sentence under it carries the words a search engine
    # and a screen reader need -- an aria-label on the mark says "j dot A I"
    # so it is not read as a word.
    b.append('<h1 class="ai-mark" aria-label="j dot A I">'
             '<span class="jm">j</span><span class="dot">.</span>'
             '<span class="ai">AI</span></h1>')
    b.append('<p class="ai-sub">AI releases and models &mdash; what the '
             'vendors shipped, and what is running</p>')
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

    # Four ways in, at the top.
    #
    # Asked for as: "if I have to see where this comes from, I have to
    # scroll down completely. Up is fine -- I can press the up arrow -- but
    # going down I have to scroll all the way."
    #
    # Fair: the page is one screen of chart followed by 401 announcements,
    # and the sources table is behind all of them. The back-to-top button
    # solved one direction and nothing solved the other.
    #
    # Real anchors rather than a script, so they work with JavaScript off,
    # can be opened in a new tab, and survive being shared.
    b.append('<nav class="ai-jump" aria-label="Sections on this page">'
             '<a href="#field">The field</a>'
             '<a href="#models">New models</a>'
             '<a href="#shipped">What shipped</a>'
             '<a href="#sources">Where this comes from</a></nav>')

    # ---- the field ---------------------------------------------------
    field, plotted, skipped = field_svg(models, today)
    b.append('<section class="ai-sec ai-field-sec" id="field">')
    b.append("<h2>The field, tonight</h2>")
    # Define the words where they are FIRST met, not in a legend further
    # down the page.
    #
    # Asked as: "what is context and million out? I didn't understand." The
    # legend was written above the TABLE, and the chart -- whose readout
    # speaks both terms -- comes before it. Explaining a word after its
    # third use is not explaining it.
    #
    # A token is the unit under both, so it goes first, with a size a person
    # can picture rather than a number they have to trust.
    b.append('<p class="ai-note"><b>Two words first.</b> Models read and '
             'write in <b>tokens</b> &mdash; roughly three quarters of a '
             'word each. <b>Context</b> is how much it can hold in mind at '
             'once: a 1M-token context is about 750,000 words, or War and '
             'Peace twice over. <b>Per million out</b> is what you pay for a '
             'million tokens it writes back &mdash; output usually costs '
             'three to five times more than what you send in.</p>')
    b.append('<p class="ai-note">So: every model in the catalogue, placed by '
             'how much it can hold (across, 4K to 2M) and what its writing '
             'costs (up, three cents to six hundred dollars per million). '
             'Both scales are logarithmic or the picture is a smear. Models '
             'older than a year are grey; the pulsing ones arrived in the '
             'last 30 days. Point at any of them.</p>')
    story = field_story(models, today)
    if story:
        b.append('<p class="ai-note"><b>What it shows:</b> the field has '
                 'moved right. A model published in %s had a median context '
                 'window of %s tokens; one published in %s has %s &mdash; '
                 '%.1f times larger, while the median price of a million '
                 'output tokens went from $%.2f to $%.2f. %d models now hold '
                 'a million tokens or more, the cheapest at $%.2f per '
                 'million out (%s).</p>'
                 % (story["from_q"], "{:,}".format(story["from_ctx"]),
                    story["to_q"], "{:,}".format(story["to_ctx"]),
                    story["to_ctx"] / float(story["from_ctx"] or 1),
                    story["from_price"], story["to_price"], story["big"],
                    story["cheap_price"] or 0, esc(story["cheap_name"])))
    b.append('<figure class="ai-field-wrap">')
    b.append(field)
    b.append('<figcaption class="ai-readout-row">%s'
             '<span class="ai-readout" id="ai-readout">'
             '<span class="ph">%d models plotted &mdash; hover or tap a dot '
             'to name it</span></span></figcaption>' % (WATCHER, plotted))
    b.append("</figure>")
    if skipped:
        b.append('<p class="ai-note">%d router%s quote no price at all '
                 '&mdash; they charge whatever the model they pick charges '
                 '&mdash; so they are the only things missing from the '
                 'picture: %s. They are counted everywhere else on this page. '
                 'Leaving them out quietly would let the chart claim a '
                 'completeness it does not have.</p>'
                 % (len(skipped), "" if len(skipped) == 1 else "s",
                    ", ".join(esc(m.get("name", "")) for m in skipped[:6])))
    b.append("</section>")

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
    b.append('<section class="ai-sec" id="models">')
    b.append("<h2>New models, last %d days</h2>" % NEW_DAYS)
    b.append('<p class="ai-note">Dated by when the model first appeared in '
             'the catalogue, not by when it was announced &mdash; an '
             'aggregator sees a launch hours to days late. Prices are per '
             'million tokens, in and out, as OpenRouter charges them; a '
             'vendor&rsquo;s direct rate can differ.</p>')
    b.append('<div class="ai-table-wrap"><table class="ai-models">')
    # Headers a reader does not have to decode.
    #
    # Asked as: "what do these headers mean? Appeared, model, etc." Fair --
    # "In" and "Out" are jargon for the two halves of a token bill, and
    # "Context" and "Cutoff" mean nothing unless you already know. The
    # column names carry their unit now, and the line below says what each
    # one is in a sentence.
    b.append('<p class="ai-legend"><b>Appeared</b> when the model first '
             'showed up in the catalogue &middot; <b>Context</b> how much '
             'text it can read at once, in tokens &middot; <b>In</b> and '
             '<b>Out</b> what a million tokens cost &mdash; what you send, '
             'and what it writes back &middot; <b>Cutoff</b> how recent its '
             'training data is.</p>')
    b.append("<thead><tr><th>Appeared</th><th>Model</th><th>Vendor</th>"
             "<th>Context</th><th>In $/M</th><th>Out $/M</th>"
             "<th>Data cutoff</th></tr></thead><tbody>")
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
    # The same hint the architecture diagram carries, for the same reason:
    # at 412px only two of the seven columns fit, and a table that scrolls
    # sideways with nothing saying so is a table whose other columns do not
    # exist as far as a reader is concerned.
    b.append('<p class="ai-hint">scroll the table sideways &rarr;</p>')
    # Five vendors publish announcements here and have no models in the
    # catalogue at all -- AWS, Google DeepMind, Hugging Face, Microsoft and
    # Microsoft Azure ship services and research rather than models you can
    # call by name. Filtering to one of them emptied this table to a row of
    # bare headers with nothing underneath and no explanation, which reads
    # as a broken page rather than an honest absence.
    b.append('<p id="ai-nomodels" hidden class="ai-note">No model from this '
             'vendor appeared in the last %d days. Some of the vendors here '
             '&mdash; AWS, Google DeepMind, Hugging Face and Microsoft '
             '&mdash; publish research and services rather than models the '
             'catalogue lists, so they show up under What shipped and not in '
             'this table.</p>' % NEW_DAYS)
    b.append("</section>")

    # ---- what shipped ------------------------------------------------
    b.append('<section class="ai-sec" id="shipped">')
    b.append("<h2>What shipped</h2>")
    b.append('<p class="ai-note">Every headline links to the vendor&rsquo;s '
             'own page. Entries marked <span class="badge">sitemap</span> '
             'come from a vendor that publishes no feed &mdash; the page was '
             'found by its timestamp and its title read from the page '
             'itself.</p>')
    b.append('<ul class="ai-rel">')
    for r in releases:
        # The haystack is the headline, the vendor and the first line of
        # the summary -- not the whole summary. Carrying all of it put the
        # page at 342KB, most of it duplicated prose nobody reads, in an
        # attribute. 120 characters keeps a search for "agentcore" or
        # "context window" working and gives back a fifth of the page.
        hay = ((r.get("title") or "") + " " + (r.get("vendor") or "") + " "
               + (r.get("summary") or "")[:120]).lower()
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
    b.append('<section class="ai-sec" id="sources">')
    b.append("<h2>Where this comes from</h2>")
    # The timestamp says which clock it is on, and then says it again in
    # the reader's own.
    #
    # Asked as: "why is it 8:44 -- what time zone is it?" It was UTC, on a
    # page being read at 5pm Central, so it looked like a time in the
    # future. A bare wall-clock time is only unambiguous to whoever wrote
    # it. The site's own convention is an explicit UTC suffix, which the
    # status page has carried all along, so that is the server-rendered
    # text -- and a <time> element lets the browser restate it in the
    # reader's zone, with how long ago it was, which is the thing a refresh
    # stamp is actually asked.
    b.append('<p class="ai-note">A job on a clock reads these once a day and '
             'commits what it finds, so the page is current whether or not I '
             'open a laptop. Last refreshed '
             '<time class="ai-when" data-when datetime="%s"><b>%s UTC</b>'
             '</time>. The store only grows: Google&rsquo;s AI feed holds 20 '
             'items and Microsoft&rsquo;s 10, so anything not written down '
             'within a fortnight would be gone for good.</p>'
             % (esc(fetched or ""),
                esc((fetched or "")[:16].replace("T", " "))))
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

    # The theme is set on the FIRST line of the body, not the last.
    #
    # Reported as: "if I refresh j.AI it keeps changing -- first it was dark
    # and then it became light." Not a persistence bug: the preference is
    # stored correctly and read correctly. It was read too late.
    #
    # applyTheme lives at the foot of the page, which is fine on a 40KB page
    # and not on a 345KB one over a phone connection -- the browser paints
    # the header, the chart and the first screen of text long before the
    # parser reaches the bottom. Measured on a throttled connection, 400kbps
    # with 400ms latency:
    #
    #     content painted while body class was '' and the background was
    #     rgb(29,30,27) -- dark, for as long as the rest took to arrive
    #
    # Four lines at the top of the body cost nothing and the page is the
    # right colour from its first paint. The call at the foot stays; it also
    # sets the icon and the label, which is work that can wait.
    theme_first = ("<script>try{if(localStorage.getItem('theme')==='light')"
                   "document.body.classList.add('light')}catch(e){}"
                   "</script>")
    html = (head_html(jsv) + STYLE + "</head>\n<body>\n" + theme_first
            + nav_html()
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
