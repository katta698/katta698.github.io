#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build /intelligence/whats-new/ from the announcement store.

A STATIC page, on purpose. The obvious way to put this in front of readers is an
API and a Lambda, and it is the wrong first move: it costs money per question,
it needs a schema locked in before the data model has settled, and it puts a
model between the reader and a set of facts that are already exact.

Everything a reader actually asks -- which cloud, which service, how recently --
is a filter over a few hundred rows. The blog index already proves the pattern
works: pills, a text box, and client-side filtering over cards. This is that,
over announcements instead of posts.

So: no API, no Bedrock call, no per-question cost, works offline through the
service worker, and it cannot invent an announcement that does not exist.

Emits two files:
    intelligence/news.json          the data, trimmed to what the page shows
    intelligence/whats-new/index.html
"""
import io
import json
import os
import sys
import collections
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import news_store as store          # noqa: E402
import news_tag                     # noqa: E402

OUT_DIR = os.path.join(ROOT, "intelligence", "whats-new")
JSON_OUT = os.path.join(ROOT, "intelligence", "news.json")
MORE_OUT = os.path.join(ROOT, "intelligence", "news-more.json")

# Announcements and releases are the default view. Blogs are marketing and CVEs
# are a different question -- showing them by default is what buried the Azure
# results under 4,353 MSRC notices.
KEEP_CLASSES = ("announcement", "release")

# ...but they are NOT excluded from the site. Searching SSM on the page returned
# "Nothing matches. Try a wider date range" while the AWS Systems Manager agent
# CVE sat in the store classed `security` and an Amazon Linux SSM item sat there
# classed `blog`. Neither was in news.json at all, so no date range and no
# filter change could ever have found them, and the page said the opposite.
#
# They go in a SECOND file, fetched only when the reader asks for them. All
# 6,810 records in one payload is roughly 1.5 MB, which is not a thing to send
# to a phone on the chance it is wanted; the default view stays ~300 KB.
MORE_CLASSES = ("blog", "security")

CLOUD_NAME = {"aws": "AWS", "azure": "Azure", "gcp": "Google Cloud"}


def collect(classes):
    rows = []
    for cloud in store.CLOUDS:
        for ym in store.all_months(cloud):
            for r in store.load_month(cloud, ym).values():
                if r.get("class") not in classes:
                    continue
                headline = r["headline"]
                status = ""
                if cloud == "gcp" and r.get("summary"):
                    # The stored headline is "product: summary", and Google's own
                    # note text usually opens with the product again -- so the
                    # page rendered "VPC Service Controls: VPC Service Controls
                    # feature ... : VPC Service Controls supports ...", naming it
                    # three times in one line. The product is already shown as
                    # the service label underneath, so the body alone is enough.
                    headline = r["summary"]
                if cloud == "azure" and r.get("class") == "release":
                    # A GitHub release feed's title is a bare tag: "v5.4.0" on
                    # its own says nothing about what was released.
                    src = r.get("source", "").replace(" releases", "")
                    if src and not headline.lower().startswith(src.lower()):
                        headline = "%s %s" % (src, headline)
                if cloud == "azure":
                    # The lifecycle state is worth showing as a badge, and the
                    # prefix is worth removing: "[Launched] Generally Available:"
                    # in front of every Azure row is noise a reader has to read
                    # past on all 200 of them.
                    headline, status = news_tag.azure_strip(headline)
                rows.append({
                    "d": r["date"],
                    "c": cloud,
                    "t": headline,
                    "u": r.get("url", ""),
                    "s": r.get("services") or [],
                    "st": status,
                    "k": r.get("class", ""),
                })
    rows = merge_cross_posted(rows)
    rows.sort(key=lambda r: (r["d"], r["t"]), reverse=True)
    return rows


def merge_cross_posted(rows):
    """Collapse one announcement that a vendor filed under several products.

    Google and Microsoft publish the same note in every product release-note
    section it touches. "Privileged Access Manager is generally available"
    arrived twice on 7 September 2026, once under Access Approval and once
    under Access Transparency, and the page showed two rows whose visible text
    was character-for-character identical -- the only difference being the
    small service label underneath, which is exactly where a reader is not
    looking when deciding whether they have already read a line.

    249 of 6,900 rows are redundant this way (3.6%), and it clusters: one GCP
    day carried the same sentence thirteen times and an Azure day twelve. A
    reader scrolling that sees a broken page, not a busy release day.

    The services are unioned rather than one row being dropped, so filtering by
    either product still finds the announcement. Merging on the rendered text
    and not on the stored headline is deliberate: the stored form carries a
    "Product: " prefix that the page has already moved into the label, so the
    duplicates are only identical after that transformation.
    """
    by_key = {}
    order = []
    for r in rows:
        key = (r["c"], r["d"], r["t"], r["u"])
        if key in by_key:
            seen = by_key[key]["s"]
            for svc in r["s"]:
                if svc not in seen:
                    seen.append(svc)
        else:
            by_key[key] = r
            order.append(key)
    return [by_key[k] for k in order]


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>What's new in the cloud &mdash; AWS, Azure and Google Cloud | Jayanth Katta</title>
<meta name="description" content="Every AWS, Azure and Google Cloud announcement, filterable by service and date. Built from the vendors' own feeds, with a link to every original."/>
<meta property="og:type" content="website"/>
<meta property="og:title" content="What's new in the cloud &mdash; AWS, Azure and Google Cloud"/>
<meta property="og:description" content="Every announcement from all three clouds, filterable by service and date, each linked to the vendor's own page."/>
<meta property="og:url" content="https://jayanthkatta.com/intelligence/whats-new/"/>
<meta property="og:image" content="https://jayanthkatta.com/blog/assets/intelligence-card.png"/>
<meta name="twitter:card" content="summary_large_image"/>
<link rel="canonical" href="https://jayanthkatta.com/intelligence/whats-new/"/>
<link rel="icon" href="/favicon-transparent.png" type="image/png">
<link rel="manifest" href="/manifest.webmanifest"/>
<meta name="theme-color" content="#1D2322"/>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700&family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<script>
/* Byte-identical to the setter in index.html, now.html and ../index.html. */
(function(){var D=['sun','mon','tue','wed','thu','fri','sat'],p;
try{p=new URLSearchParams(location.search).get('palette')||localStorage.getItem('paletteDay');}catch(e){p=null;}
if(D.indexOf(p)===-1)p=D[new Date().getDay()];
document.documentElement.setAttribute('data-palette',p);})();
</script>
<style>
  :root{
    --ink:#1D2322; --accent:#C4A484; --accent-dim:#B09173;
    --bg:#1F1D1B; --card:#262421; --text:#EDEBE6; --text-muted:#9C9A94; --border:#2F3131;
    --aws:#C4A484; --azure:#5B7B9A; --gcp:#8A9A5B;
    --serif:'Playfair Display',Georgia,serif;
    --sans:'DM Sans',system-ui,-apple-system,sans-serif;
    --mono:'DM Mono','Cascadia Code',monospace;
  }
  html[data-palette="mon"]{--bg:#191E20;--card:#1F2528}
  html[data-palette="tue"]{--bg:#1F1D1B;--card:#262421}
  html[data-palette="wed"]{--bg:#191F1E;--card:#1F2625}
  html[data-palette="thu"]{--bg:#211C1C;--card:#292323}
  html[data-palette="fri"]{--bg:#1B1E1B;--card:#212622}
  html[data-palette="sat"]{--bg:#1D1D21;--card:#242429}
  html[data-palette="sun"]{--bg:#1D1E1B;--card:#232521}
  body.light .chip.aws{color:#705539}
  body.light .chip.azure{color:#3C5570}
  body.light .chip.gcp{color:#515C32}
  body.light{--text:#2C2A29;--text-muted:#6B6A66;--border:#CFCFCE;--bg:#F7F4EF;--card:#E9E6E0}
  html[data-palette="mon"] body.light{--bg:#EFF7FB;--card:#E0E9ED}
  html[data-palette="tue"] body.light{--bg:#F7F4EF;--card:#E9E6E0}
  html[data-palette="wed"] body.light{--bg:#EFF8F7;--card:#DFEAE9}
  html[data-palette="thu"] body.light{--bg:#FAF2F2;--card:#EDE4E3}
  html[data-palette="fri"] body.light{--bg:#F2F8F3;--card:#E3EAE4}
  html[data-palette="sat"] body.light{--bg:#F4F4FA;--card:#E6E6ED}
  html[data-palette="sun"] body.light{--bg:#F5F7F2;--card:#E7E9E3}

  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--text);font-family:var(--sans);
       -webkit-font-smoothing:antialiased;transition:background .25s,color .25s}
  a{color:inherit}
  nav{display:flex;align-items:center;justify-content:space-between;padding:1rem 2rem;
      position:sticky;top:0;z-index:100;background:var(--ink);color:#EDEBE6}
  .nav-logo{display:flex;align-items:center;gap:.6rem;text-decoration:none;color:#EDEBE6}
  .brand-name{font-family:var(--serif);font-weight:600;font-size:1rem}
  .nav-links{display:flex;gap:1.5rem;list-style:none;align-items:center;margin:0;padding:0}
  .nav-links a{font-size:14px;font-weight:500;color:rgba(237,235,230,.72);text-decoration:none;transition:color .2s}
  .nav-links a:hover{color:var(--accent)}
  .theme-toggle{display:flex;align-items:center;justify-content:center;background:transparent;
    border:none;border-radius:50%;padding:0;width:32px;height:32px;flex-shrink:0;line-height:1;
    color:rgba(237,235,230,.72);font-family:var(--sans);opacity:.85;cursor:pointer;
    transition:opacity .15s,transform .15s}
  .theme-toggle:hover{opacity:1;transform:scale(1.1)}
  #theme-label{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
  #theme-icon{font-size:1.25rem;line-height:1}
  /* Do not delete the navigation on a phone.
     This used to be `.nav-links li:not(:last-child){display:none}`, which hid
     EVERY item except the last -- so Portfolio, Blog, Intelligence and the
     palette control all vanished and the only thing left in the bar was the
     theme toggle. The blog and home page solve this with a hamburger; these two
     pages just had no navigation at all below 720px.
     Measured: the links need 319px, and the whole bar fits in 390 once the
     brand NAME is dropped and the gaps tighten -- the mark still carries the
     link home, so nothing is lost but the wordmark. */
  @media(max-width:720px){
    nav{padding:.9rem 1rem}
    .nav-logo .brand-name{display:none}
    .nav-links{gap:.8rem}
    .nav-links a{font-size:13px}
  }
  @media(max-width:360px){
    .nav-links{gap:.55rem}
    .nav-links a{font-size:12px}
  }

  /* The nav follows the theme. It was fixed dark in both, while home, blog
     and now all theme theirs -- so switching to light mode left a black slab
     above a cream page, and moving between sections looked like moving
     between sites. Derived from --bg the same way blog.css derives --nav-bg
     from --surface, so it tracks the daily palette too. */
  /* Opaque, in both themes, deliberately.
     This bar has been reported see-through twice. It was 94% with no blur at
     all, then 88% WITH a blur -- and a blur softens what scrolls behind it
     without hiding it, so in light mode dark body text still read straight
     through the bar. Frosted glass only works when what is behind it is
     low-contrast, and a page of black-on-cream text never is.
     So: no alpha. The bar is the page background, solid. */
  nav{background:rgb(29,35,34);
      background:var(--bg);
      color:var(--text);border-bottom:1px solid var(--border)}
  .nav-logo{color:var(--text)}
  .nav-links a{color:var(--text-muted)}
  .nav-links a:hover{color:var(--accent)}
  body.light nav{color:#1C2120}
  body.light .nav-logo{color:#1C2120}
  body.light .nav-links a{color:rgba(28,33,32,.78)}
  body.light .theme-toggle,
  body.light #theme-icon,
  body.light #theme-label{color:#1C2120}
  header.hero{background:var(--ink);color:#EDEBE6;padding:3rem 2rem 2.4rem}
  .inner{max-width:1000px;margin:0 auto}
  .eyebrow{font-family:var(--mono);font-size:.68rem;letter-spacing:.22em;text-transform:uppercase;
           color:var(--accent);margin-bottom:.9rem;display:flex;align-items:center;gap:.5rem}
  /* A slow pulse on the eyebrow dot. The page is rebuilt every morning by the
     ingest workflow, and nothing on it said so -- a reader could not tell a
     live feed from a static list. The dot is the only thing here that moves
     continuously, which is what makes it read as "still running" rather than
     as decoration. */
  .eyebrow .live{width:6px;height:6px;border-radius:50%;background:var(--accent);
                 flex-shrink:0;animation:livePulse 2.6s ease-in-out infinite}
  @keyframes livePulse{
    0%,100%{opacity:.35;box-shadow:0 0 0 0 rgba(196,164,132,.45)}
    50%    {opacity:1;  box-shadow:0 0 0 4px rgba(196,164,132,0)}
  }
  /* One sweep, on load, then it stops. A looping shimmer on a heading reads as
     a broken gradient after the second pass; a single pass reads as arrival. */
  .eyebrow .label{background:linear-gradient(90deg,
      var(--accent) 0%, var(--accent) 40%, #FFF3E0 50%, var(--accent) 60%, var(--accent) 100%);
    background-size:250% 100%;background-position:100% 0;
    -webkit-background-clip:text;background-clip:text;color:transparent;
    animation:eyebrowSweep 1.5s ease-out .25s 1 forwards}
  @keyframes eyebrowSweep{to{background-position:0 0}}
  /* Everything above is ornament. Under reduced-motion it all resolves to the
     finished state rather than a slower version of itself. */
  @media(prefers-reduced-motion:reduce){
    .eyebrow .live{animation:none;opacity:.85}
    .eyebrow .label{animation:none;background:none;-webkit-text-fill-color:var(--accent);color:var(--accent)}
  }
  h1{font-family:var(--serif);font-size:2.1rem;line-height:1.16;margin:0 0 1.4rem;font-weight:600}
  .lede{font-size:.98rem;line-height:1.7;color:rgba(237,235,230,.76);max-width:66ch;margin:0}

  /* The count, pulled out of the sentence and made the largest thing in the
     hero. It is the whole proposition of the page -- how much is actually in
     here -- and as body text it read as a footnote to the headline. */
  .tally{display:flex;align-items:baseline;gap:.7rem;margin:0 0 1.1rem;flex-wrap:wrap}
  .tally .n{font-family:var(--serif);font-size:3.1rem;line-height:1;font-weight:600;
            color:var(--accent);font-variant-numeric:tabular-nums;
            letter-spacing:-.01em}
  .tally .of{font-size:.95rem;color:rgba(237,235,230,.7);line-height:1.4;max-width:26ch}
  @media(max-width:640px){
    h1{font-size:1.65rem}header.hero{padding:2.2rem 1.2rem 1.8rem}
    .tally .n{font-size:2.5rem}
  }

  /* Staggered arrival. Each element starts 14px low and transparent, and the
     delay is set per element rather than by nth-child so the order stays
     obvious when the markup moves. */
  .rise{opacity:0;transform:translateY(14px);
        animation:riseIn .7s cubic-bezier(.22,.61,.36,1) forwards}
  .rise-1{animation-delay:.05s} .rise-2{animation-delay:.18s} .rise-3{animation-delay:.31s}
  @keyframes riseIn{to{opacity:1;transform:translateY(0)}}
  /* Reduced motion resolves everything to its finished state. Not a slower
     version of the same movement -- no movement at all. */
  @media(prefers-reduced-motion:reduce){
    .rise{opacity:1;transform:none;animation:none}
  }

  main{max-width:1000px;margin:0 auto;padding:1.6rem 2rem 4rem}
  @media(max-width:640px){main{padding:1.2rem 1.1rem 3rem}}

  .controls{position:sticky;top:56px;z-index:50;background:var(--bg);
            padding:.9rem 0 .7rem;border-bottom:1px solid var(--border);margin-bottom:1.2rem}
  .row{display:flex;flex-wrap:wrap;gap:.4rem;align-items:center;margin-bottom:.55rem}
  .row:last-child{margin-bottom:0}
  .pill{font-family:var(--sans);font-size:.78rem;font-weight:500;padding:.3rem .72rem;
        border-radius:20px;border:1px solid var(--border);background:transparent;
        color:var(--text-muted);cursor:pointer;transition:all .15s;white-space:nowrap}
  .pill:hover{color:var(--text);border-color:var(--text-muted)}
  .pill.on{color:var(--text);border-color:transparent}
  .pill.on[data-cloud="aws"]{background:rgba(196,164,132,.22);color:var(--aws)}
  .pill.on[data-cloud="azure"]{background:rgba(91,123,154,.22);color:var(--azure)}
  .pill.on[data-cloud="gcp"]{background:rgba(138,154,91,.22);color:var(--gcp)}
  .pill.on[data-cloud="all"],.pill.on[data-days]{background:rgba(196,164,132,.2);color:var(--accent)}
  .pill.on[data-svc]{background:var(--card);color:var(--text);border-color:var(--border)}
  #q{flex:1;min-width:180px;font-family:var(--sans);font-size:.85rem;padding:.42rem .8rem;
     border-radius:8px;border:1px solid var(--border);background:var(--card);color:var(--text)}
  #q:focus{outline:none;border-color:var(--accent)}
  .count{font-family:var(--mono);font-size:.72rem;color:var(--text-muted);margin-left:auto;white-space:nowrap}

  /* The control block is sticky, which is right on a desktop and wrong on a
     phone. Measured on 2026-09-04: 574px tall on an iPhone 14, eating 75% of
     the viewport and leaving THREE results visible while scrolling. On a
     1280px desktop the same block is 234px, 32%, and eleven results.
     Two causes, both fixed here.

     One: it stops being sticky on a narrow screen. Scrolling back to the top
     for the filters is the normal phone gesture, and it is a far smaller cost
     than surrendering three quarters of every screenful.

     Two: nineteen service pills wrap to about thirteen rows at 390px. They
     become a single horizontally-scrollable row, which is the usual mobile
     pattern and keeps the block short when you do scroll up to it. */
  @media(max-width:820px){
    .controls{position:static;top:auto;padding-bottom:.5rem}
    /* The search box and the count stop sharing a line. Fighting for one row
       cost both: the input squeezed to 242px of a 390 screen and truncated its
       own placeholder to "Filter by service or words in t", while the count ran
       flush to the edge with its last letter against the boundary. Stacked,
       the input gets the full width and the count gets a line it fits on. */
    .controls .row:has(#q){flex-direction:column;align-items:stretch;gap:.4rem}
    #q{width:100%;min-width:0}
    .count{margin-left:0;text-align:left}
    #svcs{flex-wrap:nowrap;overflow-x:auto;-webkit-overflow-scrolling:touch;
          scrollbar-width:none;padding-bottom:.3rem}
    #svcs::-webkit-scrollbar{display:none}
    .count{margin-left:0}
  }

  .day{font-family:var(--mono);font-size:.7rem;letter-spacing:.12em;text-transform:uppercase;
       color:var(--text-muted);margin:1.4rem 0 .5rem;padding-bottom:.3rem;border-bottom:1px solid var(--border)}
  .item{display:flex;gap:.7rem;padding:.55rem 0;border-bottom:1px solid transparent}
  .item:hover{border-bottom-color:var(--border)}
  .chip{flex:0 0 auto;font-family:var(--mono);font-size:.6rem;letter-spacing:.06em;
        text-transform:uppercase;padding:.2rem .45rem;border-radius:4px;height:fit-content;margin-top:.15rem}
  /* Chip text, solved per theme rather than shared. One colour cannot sit on
     both a dark card and a light one: AWS measured 1.87:1 in light and Azure
     3.04:1 in dark. The hue is kept -- the chips are how a reader tells the
     clouds apart at a glance -- and only the lightness moves, to the first
     value clearing 5:1 against the chip's own translucent layer composited
     over the card beneath it.

     Set HERE rather than in a later block: an added `.chip.azure{color}` rule
     has the same specificity as this one, so source order decides, and a rule
     placed above this lost silently. */
  .chip.aws{background:rgba(196,164,132,.18);color:#D6B896}
  .chip.azure{background:rgba(91,123,154,.2);color:#9DB6CE}
  .chip.gcp{background:rgba(138,154,91,.2);color:#BCC98E}
  .body{min-width:0}
  .title{font-size:.92rem;line-height:1.45;text-decoration:none;color:var(--text)}
  .title:hover{color:var(--accent);text-decoration:underline}
  .meta{font-family:var(--mono);font-size:.66rem;color:var(--text-muted);margin-top:.2rem}
  .status{color:var(--accent);font-weight:500}
  .kind{color:var(--text-muted);border:1px solid var(--border);border-radius:3px;
        padding:0 .3rem;margin-right:.15rem}
  .empty{padding:2.5rem 0;color:var(--text-muted);font-size:.9rem}
  .note{margin-top:2rem;padding-top:1rem;border-top:1px solid var(--border);
        font-size:.78rem;line-height:1.7;color:var(--text-muted)}
  .note code{font-family:var(--mono);font-size:.72rem}
  #more{display:block;margin:1.6rem auto 0;padding:.5rem 1.4rem;font-family:var(--sans);
        font-size:.82rem;border-radius:20px;border:1px solid var(--border);
        background:transparent;color:var(--text-muted);cursor:pointer}
  #more:hover{color:var(--text);border-color:var(--text-muted)}
</style>
</head>
<body>
<nav>
  <!-- The logo stays in its own section, the way the blog's does
       (/blog/ there, /intelligence/ here). It used to jump to the
       portfolio, which is what the Portfolio tab beside it is for --
       so clicking the mark threw the reader out of the section they
       were reading. -->
  <a class="nav-logo" href="/intelligence/" aria-label="Cloud intelligence home">
    <img src="/favicon-transparent.png" alt="" width="30" height="30" aria-hidden="true">
    <span class="brand-name">Jayanth Katta</span>
  </a>
  <ul class="nav-links">
    <li><a href="/">Portfolio</a></li>
    <li><a href="/blog/">Blog</a></li>
    <li><a href="/intelligence/">Intelligence</a></li>
    <li>
      <button class="theme-toggle" onclick="toggleTheme()" id="theme-btn" type="button">
        <span id="theme-icon">&#9681;</span><span id="theme-label">Light</span>
      </button>
    </li>
  </ul>
</nav>

<header class="hero">
  <div class="inner">
    <p class="eyebrow"><span class="live" aria-hidden="true"></span><span class="label">What's new</span></p>
    <h1 class="rise rise-1">Every announcement from all three clouds</h1>
    <div class="tally rise rise-2">
      <span class="n" id="news-count" data-n="__COUNT__">__COUNT_FMT__</span>
      <span class="of">announcements from AWS, Azure and Google Cloud</span>
    </div>
    <p class="lede rise rise-3">__LEDE__ <a href="/intelligence/status/"
     style="color:var(--accent);font-weight:600;white-space:nowrap">Anything broken
     right now? &rarr;</a></p>
  </div>
</header>

<main>
  <div class="controls">
    <div class="row" id="clouds"></div>
    <div class="row">
      <input id="q" type="search" placeholder="Filter by service or words in the title&hellip;" autocomplete="off">
      <span class="count" id="count"></span>
    </div>
    <div class="row" id="svcs"></div>
  </div>
  <div id="list"></div>
  <button id="more" hidden>Show more</button>
  <p class="note">__NOTE__</p>
</main>

<script>
/* Count the headline number up on load.
   The element already contains the correct, formatted number when it ships --
   this only replaces it if the animation can actually run. So JS off, an error
   here, or prefers-reduced-motion all leave the real figure on screen rather
   than a zero that never moves, which is the usual way this effect fails. */
(function(){
  var el = document.getElementById('news-count');
  if(!el) return;
  if(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  var target = parseInt(el.getAttribute('data-n'), 10);
  if(!isFinite(target) || target <= 0) return;
  var DUR = 1100, t0 = null;
  /* Start from ~55% rather than 0. Counting 1,375 numbers from zero spends
     most of the animation on figures that are not the answer; starting close
     reads as the number settling rather than as a slot machine. */
  var from = Math.round(target * 0.55);
  function frame(ts){
    if(t0 === null) t0 = ts;
    var p = Math.min((ts - t0) / DUR, 1);
    var eased = 1 - Math.pow(1 - p, 3);
    el.textContent = Math.round(from + (target - from) * eased).toLocaleString();
    if(p < 1) requestAnimationFrame(frame);
    else el.textContent = target.toLocaleString();
  }
  el.textContent = from.toLocaleString();
  requestAnimationFrame(frame);
  /* Hard backstop. requestAnimationFrame is not guaranteed to run to
     completion -- a backgrounded tab pauses it, and headless Chrome under a
     virtual-time budget stalls it partway. Either way the element would be
     left showing a number that is not the count, which is worse than showing
     no animation at all. This lands the true value regardless. */
  setTimeout(function(){ el.textContent = target.toLocaleString(); }, DUR + 400);
})();

function applyTheme(dark){
  document.body.classList.toggle('light', !dark);
  var i=document.getElementById('theme-icon'), l=document.getElementById('theme-label');
  if(i) i.textContent = dark ? '\\u25D1' : '\\u25D0';
  if(l) l.textContent = dark ? 'Light' : 'Dark';
}
function toggleTheme(){
  var goingDark = document.body.classList.contains('light');
  localStorage.setItem('theme', goingDark ? 'dark' : 'light');
  applyTheme(goingDark);
}
applyTheme(localStorage.getItem('theme') !== 'light');

var DATA = [], cloud = 'all', days = 30, svc = '', shown = 60;
var allSvcs = false;   // is the service pill row expanded?
var more = false, MORE = null, moreLoading = false;
var NAMES = {aws:'AWS', azure:'Azure', gcp:'Google Cloud'};
// Short form for the per-row chip only. "GOOGLE CLOUD" spelled out is
// ~180px of a 390px phone screen on EVERY row, forcing the headline to
// wrap harder for no information -- the filter pill above still says the
// full name, so nothing is lost.
var SHORT = {aws:'AWS', azure:'Azure', gcp:'GCP'};

function esc(s){return String(s).replace(/[&<>"]/g,function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}

function cutoff(){
  if(days === 0) return '0000-00-00';
  var d = new Date(); d.setDate(d.getDate() - days);
  return d.toISOString().slice(0,10);
}

/* Whole-word containment, done WITHOUT building a regex from the query.
   Two layers of escaping (Python template -> JS source -> RegExp) turned the
   boundary into a literal backspace and mangled the character class -- the
   escaping trap this repo keeps hitting. Scanning by hand needs no escaping at
   all, cannot be broken by a query containing regex metacharacters, and treats
   a hyphen as a boundary: "ssm" still finds "amazon-ssm-agent" while refusing
   "assessments", which is what indexOf was matching. */
function hasWord(hay, w){
  if(!w) return true;
  var H = hay.toLowerCase(), W = w.toLowerCase(), i = -1;
  while((i = H.indexOf(W, i + 1)) !== -1){
    var before = i === 0 ? '' : H.charAt(i - 1);
    var after = H.charAt(i + W.length);
    if(!/[a-z0-9]/.test(before) && !/[a-z0-9]/.test(after)) return true;
  }
  return false;
}

function qWords(q){ return q.split(/\s+/).filter(Boolean); }

function pool(){ return (more && MORE) ? DATA.concat(MORE) : DATA; }

function filtered(){
  var lo = cutoff(), q = document.getElementById('q').value.trim().toLowerCase();
  return pool().filter(function(r){
    if(r.d < lo) return false;
    if(cloud !== 'all' && r.c !== cloud) return false;
    if(svc && r.s.indexOf(svc) === -1) return false;
    if(q){
      // Whole words, not substrings. indexOf matched INSIDE words, so a search
      // for SSM answered with "Use assessments (Preview) in Database Center"
      // -- a-s-s-e-S-S-M-ents. \\b is the right tool here where Python needed a
      // lookbehind: JavaScript counts a hyphen as a non-word character, so
      // \\bssm\\b still finds "amazon-ssm-agent" while refusing "assessments".
      var hay = r.t + ' ' + r.s.join(' ') + ' ' + (r.st || '');
      if(!qWords(q).every(function(w){ return hasWord(hay, w); })) return false;
    }
    return true;
  });
}

function render(){
  var rows = filtered(), list = document.getElementById('list');
  document.getElementById('count').textContent =
    rows.length + (rows.length === 1 ? ' announcement' : ' announcements');
  if(!rows.length){
    // Say what is NOT being searched. "Try a wider date range" was actively
    // misleading for SSM: the records existed but were blog and security, so no
    // date range could ever have reached them.
    list.innerHTML = '<p class="empty">Nothing matches.'
      + (more ? ' Try a wider date range, or clear the service filter.'
              : ' This view covers announcements and releases only &mdash; try'
                + ' <b>Blogs &amp; bulletins</b> above, or a wider date range.')
      + '</p>';
    document.getElementById('more').hidden = true;
    return;
  }
  var slice = rows.slice(0, shown), html = '', lastDay = '';
  slice.forEach(function(r){
    if(r.d !== lastDay){
      lastDay = r.d;
      var dt = new Date(r.d + 'T00:00:00');
      html += '<p class="day">' + dt.toLocaleDateString('en-GB',
        {weekday:'short', day:'numeric', month:'long', year:'numeric'}) + '</p>';
    }
    var meta = [];
    if(r.k === 'blog' || r.k === 'security')
      meta.push('<span class="kind">' + esc(r.k === 'blog' ? 'blog post'
                                            : 'security bulletin') + '</span>');
    if(r.st) meta.push('<span class="status">' + esc(r.st) + '</span>');
    // Join with the character, not the entity. This used to join with
    // ' &middot; ' and then .replace(/&amp;middot;/g, ...) -- but the replace
    // ran BEFORE esc(), searching for the escaped form inside an unescaped
    // string. It matched nothing, esc() then turned the & into &amp;, and
    // "&middot;" shipped as visible text between the service names. Invisible
    // until announcements began being merged across products, because a
    // single-service row has no separator to get wrong.
    if(r.s.length) meta.push(esc(r.s.join(' \\u00b7 ')));
    html += '<div class="item">'
      + '<span class="chip ' + r.c + '">' + esc(SHORT[r.c] || r.c) + '</span>'
      + '<div class="body">'
      + '<a class="title" href="' + esc(r.u) + '" target="_blank" rel="noopener">' + esc(r.t) + '</a>'
      + (meta.length ? '<div class="meta">' + meta.join(' &middot; ') + '</div>' : '')
      + '</div></div>';
  });
  list.innerHTML = html;
  document.getElementById('more').hidden = rows.length <= shown;
}

function buildPills(){
  var cs = document.getElementById('clouds');
  cs.innerHTML = ['all','aws','azure','gcp'].map(function(c){
    return '<button class="pill' + (c===cloud?' on':'') + '" data-cloud="' + c + '">'
      + (c==='all' ? 'All clouds' : NAMES[c]) + '</button>';
  }).join('') + '<span style="width:.6rem"></span>'
   + [[7,'7 days'],[30,'30 days'],[90,'90 days'],[0,'All time']].map(function(p){
    return '<button class="pill' + (p[0]===days?' on':'') + '" data-days="' + p[0] + '">'
      + p[1] + '</button>';}).join('')
   + '<span style="width:.6rem"></span>'
   + '<button class="pill' + (more?' on':'') + '" data-more-src="' + (more?'0':'1') + '">'
   + (moreLoading ? 'loading…' : 'Blogs &amp; bulletins') + '</button>';

  var counts = {};
  filtered().forEach(function(r){ r.s.forEach(function(s){ counts[s]=(counts[s]||0)+1; }); });
  var names = Object.keys(counts).sort(function(a,b){
    return counts[b]-counts[a] || a.localeCompare(b); });

  // Showing the busiest 18 and stopping silently made the row read as the
  // complete list of services. It was not close: AWS over 7 days has 52, and
  // all three clouds over 30 days have 208 -- so 190 were hidden with nothing
  // on the page admitting it. A reader filtering by service would conclude
  // their service had no news, which is the confidently-incomplete answer this
  // whole thing exists to avoid.
  var CAP = 18;
  var shownNames = allSvcs ? names : names.slice(0, CAP);
  var rest = names.length - shownNames.length;

  document.getElementById('svcs').innerHTML =
    (svc ? '<button class="pill on" data-svc="">&times; ' + esc(svc) + '</button>' : '')
    + shownNames.filter(function(s){return s!==svc;}).map(function(s){
        return '<button class="pill" data-svc="' + esc(s) + '">' + esc(s)
             + ' <span style="opacity:.55">' + counts[s] + '</span></button>';}).join('')
    + (rest > 0
        ? '<button class="pill" data-more="1">+' + rest + ' more service'
          + (rest === 1 ? '' : 's') + '</button>'
        : (allSvcs && names.length > CAP
            ? '<button class="pill" data-more="0">show fewer</button>' : ''));
}

document.addEventListener('click', function(e){
  var b = e.target.closest('.pill'); if(!b) return;
  if(b.dataset.moreSrc !== undefined){
    var want = b.dataset.moreSrc === '1';
    if(want && !MORE){
      // Fetched on demand: the blog and bulletin records are ~1.2 MB, which is
      // not something to push at a phone unless it has been asked for.
      if(moreLoading) return;
      moreLoading = true; buildPills();
      fetch('/intelligence/news-more.json').then(function(r){return r.json();})
        .then(function(d){ MORE = d.items || []; more = true; })
        .catch(function(){ MORE = []; })
        .then(function(){ moreLoading = false; shown = 60; buildPills(); render(); });
      return;
    }
    more = want; shown = 60; buildPills(); render();
    return;
  }
  if(b.dataset.more !== undefined){
    // Expand/collapse only -- must not reset the result list or the reader
    // loses their place just for looking at what else is available.
    allSvcs = b.dataset.more === '1';
    buildPills();
    return;
  }
  if(b.dataset.cloud) { cloud = b.dataset.cloud; svc = ''; allSvcs = false; }
  else if(b.dataset.days !== undefined) days = parseInt(b.dataset.days, 10);
  else if(b.dataset.svc !== undefined) svc = b.dataset.svc;
  shown = 60; buildPills(); render();
});
document.getElementById('q').addEventListener('input', function(){
  shown = 60; buildPills(); render(); });
document.getElementById('more').addEventListener('click', function(){
  shown += 120; render(); });

fetch('/intelligence/news.json').then(function(r){return r.json();}).then(function(d){
  DATA = d.items || []; buildPills(); render();
}).catch(function(){
  document.getElementById('list').innerHTML =
    '<p class="empty">Could not load the announcement data.</p>';
});
</script>
<script src="/blog/assets/site-footer.js?v=__JSV__" data-site-footer></script>
</body>
</html>
"""


def build():
    rows = collect(KEEP_CLASSES)
    more = collect(MORE_CLASSES)
    per = collections.Counter(r["c"] for r in rows)
    earliest = {c: min((r["d"] for r in rows if r["c"] == c), default="-")
                for c in store.CLOUDS}

    os.makedirs(OUT_DIR, exist_ok=True)
    for path, payload in ((JSON_OUT, rows), (MORE_OUT, more)):
        io.open(path, "w", encoding="utf-8", newline="\n").write(
            json.dumps({"generated": datetime.date.today().isoformat(),
                        "items": payload},
                       ensure_ascii=False, separators=(",", ":")))

    # The count is wrapped so it can animate up on load. data-n carries the
    # real value and the element ships with the final text already in it, so a
    # reader with JS off, or with reduced motion, sees the correct number and
    # never a zero.
    # The count moved into its own element above this, so the sentence no
    # longer opens with it.
    lede = ("Filterable by service and date. Each one links to the vendor's "
            "own page &mdash; nothing here is summarised or rewritten.")

    note = ("Built from the three clouds' own release feeds, not from a summary "
            "of them. Coverage begins %s for AWS, %s for Azure and %s for Google "
            "Cloud &mdash; anything earlier was already off the vendors' feeds "
            "before this archive existed. Blog posts and CVE bulletins are "
            "collected too but deliberately kept out of this view: they answer a "
            "different question. Service labels come from each vendor's own "
            "naming, so a few will be imprecise; the link is always the "
            "authority."
            % (earliest["aws"], earliest["azure"], earliest["gcp"]))

    # Reuse sync's JS token so the shared footer script busts cache in step with
    # every other page; falling back to the literal keeps the page valid if the
    # import is ever unavailable.
    try:
        import sync_blog
        jsv = sync_blog.JS_VERSION
    except Exception:                                        # noqa: BLE001
        jsv = "1"

    html = (PAGE.replace("__LEDE__", lede)
                .replace("__COUNT_FMT__", "{:,}".format(len(rows)))
                .replace("__COUNT__", str(len(rows)))
                .replace("__NOTE__", note)
                .replace("__JSV__", jsv))
    io.open(os.path.join(OUT_DIR, "index.html"), "w",
            encoding="utf-8", newline="\n").write(html)

    print("  %d announcements -> intelligence/news.json (%.0f KB)"
          % (len(rows), os.path.getsize(JSON_OUT) / 1024.0))
    print("  %d blog/security -> intelligence/news-more.json (%.0f KB, lazy)"
          % (len(more), os.path.getsize(MORE_OUT) / 1024.0))
    for c in store.CLOUDS:
        print("     %-6s %5d  from %s" % (c, per[c], earliest[c]))
    print("  page -> intelligence/whats-new/index.html")


if __name__ == "__main__":
    build()
