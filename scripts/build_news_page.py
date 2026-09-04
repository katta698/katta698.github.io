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
    rows.sort(key=lambda r: (r["d"], r["t"]), reverse=True)
    return rows


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
  @media(max-width:720px){.nav-links li:not(:last-child){display:none}nav{padding:.9rem 1.1rem}}

  header.hero{background:var(--ink);color:#EDEBE6;padding:3rem 2rem 2.4rem}
  .inner{max-width:1000px;margin:0 auto}
  .eyebrow{font-family:var(--mono);font-size:.68rem;letter-spacing:.22em;text-transform:uppercase;
           color:var(--accent);margin-bottom:.9rem}
  h1{font-family:var(--serif);font-size:2.1rem;line-height:1.16;margin:0 0 .9rem;font-weight:600}
  .lede{font-size:.98rem;line-height:1.7;color:rgba(237,235,230,.76);max-width:66ch;margin:0}
  @media(max-width:640px){h1{font-size:1.65rem}header.hero{padding:2.2rem 1.2rem 1.8rem}}

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

  .day{font-family:var(--mono);font-size:.7rem;letter-spacing:.12em;text-transform:uppercase;
       color:var(--text-muted);margin:1.4rem 0 .5rem;padding-bottom:.3rem;border-bottom:1px solid var(--border)}
  .item{display:flex;gap:.7rem;padding:.55rem 0;border-bottom:1px solid transparent}
  .item:hover{border-bottom-color:var(--border)}
  .chip{flex:0 0 auto;font-family:var(--mono);font-size:.6rem;letter-spacing:.06em;
        text-transform:uppercase;padding:.2rem .45rem;border-radius:4px;height:fit-content;margin-top:.15rem}
  .chip.aws{background:rgba(196,164,132,.18);color:var(--aws)}
  .chip.azure{background:rgba(91,123,154,.2);color:var(--azure)}
  .chip.gcp{background:rgba(138,154,91,.2);color:var(--gcp)}
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
  <a class="nav-logo" href="/" aria-label="Jayanth Katta home">
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
    <p class="eyebrow">What's new</p>
    <h1>Every announcement from all three clouds</h1>
    <p class="lede">__LEDE__</p>
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
    if(r.s.length) meta.push(esc(r.s.join(' &middot; ').replace(/&amp;middot;/g,'\\u00b7')));
    html += '<div class="item">'
      + '<span class="chip ' + r.c + '">' + esc(NAMES[r.c] || r.c) + '</span>'
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

    lede = ("%s announcements from AWS, Azure and Google Cloud, filterable by "
            "service and date. Each one links to the vendor's own page &mdash; "
            "nothing here is summarised or rewritten."
            % "{:,}".format(len(rows)))

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
