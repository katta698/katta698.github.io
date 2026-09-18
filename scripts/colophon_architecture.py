#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The whole site as one picture, for /how-this-was-made/.

Asked for: "a workflow architecture diagram and all the components attached to
it, so that users can not only read it but also listen -- the whole workflow,
how does it work."

The eight scenes tell the story one step at a time, which is the right shape
for a walkthrough and the wrong shape for "show me the whole thing". This is
the other view: every component on the site at once, and the arrows between
them.

Drawn rather than generated, deliberately. A diagram laid out by an algorithm
from the file listing would be technically current and unreadable; this one is
arranged so a person can follow it left to right, and check_architecture_map
asserts that every box on it still names something that exists. The picture is
hand-arranged, the FACTS in it are checked.

It is one <svg> with a 760x470 viewBox, so it scales to any width. It carries
role="img" and a label, because unlike the eight scenes this one is not a
decoration restating nearby text -- it is information, and a reader who cannot
see it should be told what it says.
"""

VIEWBOX = "0 0 760 470"

# Every box that names a real thing, so a check can verify them.
#
# path -> the file or directory the box refers to. A box naming a file that
# has been renamed is a diagram lying quietly, which is worse than no diagram.
CLAIMS = {
    "posts/": "posts",
    "sync_blog.py": "scripts/sync_blog.py",
    "build_arch_post.py": "scripts/build_arch_post.py",
    "build_sitemap.py": "scripts/build_sitemap.py",
    "build_news_page.py": "scripts/build_news_page.py",
    "build_status_page.py": "scripts/build_status_page.py",
    "build_events_page.py": "scripts/build_events_page.py",
    "preflight.py": "scripts/preflight.py",
    "site-footer.css": "blog/assets/site-footer.css",
    "site-footer.js": "blog/assets/site-footer.js",
    "news.json": "intelligence/news.json",
    "status.json": "intelligence/status.json",
    "events.json": "intelligence/events.json",
    ".github/workflows": ".github/workflows",
}

ARCHITECTURE = """
<svg viewBox="%s" preserveAspectRatio="xMidYMid meet" class="cf-arch-svg"
     role="img" aria-label="How the site fits together: hand-written posts and
     three JSON data stores feed six Python builders; the builders write every
     published page; all pages share one stylesheet and one script; a
     pre-push gate of fifty browser checks stands between the builders and
     GitHub Pages; and seven scheduled jobs re-read the clouds' own feeds to
     keep the data stores current.">

  <!-- ================= column headings ================= -->
  <text class="ah" x="86"  y="26">WRITTEN BY HAND</text>
  <text class="ah" x="300" y="26">BUILT BY PYTHON</text>
  <text class="ah" x="560" y="26">WHAT A READER OPENS</text>

  <!-- ================= sources ================= -->
  <g class="ab src">
    <rect x="16" y="44" width="140" height="42" rx="6"/>
    <text class="at" x="30" y="66">posts/</text>
    <text class="as" x="30" y="79">one file per post</text>
  </g>

  <text class="ah" x="16" y="118">DATA STORES</text>
  <g class="ab store">
    <rect x="16" y="128" width="140" height="34" rx="6"/>
    <text class="at" x="30" y="149">news.json</text>
  </g>
  <g class="ab store">
    <rect x="16" y="170" width="140" height="34" rx="6"/>
    <text class="at" x="30" y="191">status.json</text>
  </g>
  <g class="ab store">
    <rect x="16" y="212" width="140" height="34" rx="6"/>
    <text class="at" x="30" y="233">events.json</text>
  </g>

  <!-- the clouds, and the jobs that read them -->
  <g class="ab vendor">
    <rect x="16" y="300" width="140" height="58" rx="6"/>
    <text class="at" x="30" y="322">AWS · Azure · GCP</text>
    <text class="as" x="30" y="337">their own feeds</text>
    <text class="as" x="30" y="350">status · releases · events</text>
  </g>
  <g class="ab job">
    <rect x="16" y="382" width="140" height="48" rx="6"/>
    <text class="at" x="30" y="403">.github/workflows</text>
    <text class="as" x="30" y="418">7 jobs on a clock</text>
  </g>

  <path class="aw up1" d="M86 300 V254"/>
  <path class="aw up2" d="M86 382 V362"/>
  <text class="as" x="94" y="278">re-read, rebuilt,</text>
  <text class="as" x="94" y="290">committed</text>

  <!-- ================= builders ================= -->
  <g class="ab bld">
    <rect x="236" y="44" width="176" height="42" rx="6"/>
    <text class="at" x="250" y="66">sync_blog.py</text>
    <text class="as" x="250" y="79">posts, index, feed, sitemap</text>
  </g>
  <g class="ab bld">
    <rect x="236" y="90" width="176" height="30" rx="6"/>
    <text class="at" x="250" y="110">build_arch_post.py</text>
  </g>
  <g class="ab bld">
    <rect x="236" y="128" width="176" height="34" rx="6"/>
    <text class="at" x="250" y="149">build_news_page.py</text>
  </g>
  <g class="ab bld">
    <rect x="236" y="170" width="176" height="34" rx="6"/>
    <text class="at" x="250" y="191">build_status_page.py</text>
  </g>
  <g class="ab bld">
    <rect x="236" y="212" width="176" height="34" rx="6"/>
    <text class="at" x="250" y="233">build_events_page.py</text>
  </g>

  <path class="aa a1" d="M156 65 H236"/>
  <path class="aa a1b" d="M156 75 V105 H236"/>
  <path class="aa a2" d="M156 145 H236"/>
  <path class="aa a3" d="M156 187 H236"/>
  <path class="aa a4" d="M156 229 H236"/>

  <g class="ab bld">
    <rect x="236" y="254" width="176" height="30" rx="6"/>
    <text class="at" x="250" y="274">build_sitemap.py</text>
  </g>
  <text class="as" x="424" y="274">sitemap.xml &#183; robots.txt</text>

  <!-- ================= the gate ================= -->
  <g class="ab gate">
    <rect x="236" y="300" width="176" height="62" rx="6"/>
    <text class="at" x="250" y="322">preflight.py</text>
    <text class="as" x="250" y="337">50 checks, a real browser</text>
    <text class="as" x="250" y="351">a failure refuses the push</text>
  </g>
  <path class="aw down" d="M324 284 V300"/>

  <!-- ================= pages ================= -->
  <g class="ab page">
    <rect x="492" y="44" width="180" height="30" rx="6"/>
    <text class="at" x="506" y="63">Portfolio</text>
  </g>
  <g class="ab page">
    <rect x="492" y="80" width="180" height="30" rx="6"/>
    <text class="at" x="506" y="99">Blog · 255 posts</text>
  </g>
  <g class="ab page">
    <rect x="492" y="116" width="180" height="30" rx="6"/>
    <text class="at" x="506" y="135">Intelligence</text>
  </g>
  <g class="ab page">
    <rect x="492" y="152" width="180" height="30" rx="6"/>
    <text class="at" x="506" y="171">What&#8217;s new</text>
  </g>
  <g class="ab page">
    <rect x="492" y="188" width="180" height="30" rx="6"/>
    <text class="at" x="506" y="207">Live status</text>
  </g>
  <g class="ab page">
    <rect x="492" y="224" width="180" height="30" rx="6"/>
    <text class="at" x="506" y="243">Cloud events</text>
  </g>

  <path class="aa b1" d="M412 65 H492"/>
  <path class="aa b2" d="M412 145 H470 V161 H492"/>
  <path class="aa b3" d="M412 187 H470 V203 H492"/>
  <path class="aa b4" d="M412 229 H470 V239 H492"/>

  <!-- ================= shipping ================= -->
  <g class="ab ship">
    <rect x="492" y="300" width="180" height="62" rx="6"/>
    <text class="at" x="506" y="322">GitHub Pages</text>
    <text class="as" x="506" y="337">static files, no server</text>
    <text class="as" x="506" y="351">nothing to restart</text>
  </g>
  <path class="aw pass" d="M412 331 H492"/>
  <text class="as" x="424" y="324">passes</text>

  <!-- ================= the shared shell ================= -->
  <g class="ab shell">
    <rect x="492" y="382" width="252" height="62" rx="6"/>
    <text class="at" x="506" y="403">site-footer.css · site-footer.js</text>
    <text class="as" x="506" y="418">one bar, one theme, one menu</text>
    <text class="as" x="506" y="432">on all 278 pages</text>
  </g>
  <path class="aw shellup" d="M582 382 V362"/>

  <!-- ================= the reader ================= -->
  <g class="ab reader">
    <rect x="692" y="128" width="52" height="126" rx="6"/>
    <text class="at ar" x="718" y="196" text-anchor="middle">reader</text>
  </g>
  <path class="aa r1" d="M672 191 H692"/>
</svg>
""" % VIEWBOX
