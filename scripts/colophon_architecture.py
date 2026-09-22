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

VIEWBOX = "0 0 760 580"

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
    "ai.json": "intelligence/ai.json",
    "build_ai_page.py": "scripts/build_ai_page.py",
    "reinvent2026.json": "intelligence/reinvent2026.json",
    "build_reinvent_page.py": "scripts/build_reinvent_page.py",
    ".github/workflows": ".github/workflows",
    "sitemap.xml": "sitemap.xml",
    "robots.txt": "robots.txt",
}

ARCHITECTURE = """
<svg viewBox="%s" preserveAspectRatio="xMidYMid meet" class="cf-arch-svg"
     role="img" aria-label="How the site fits together: hand-written posts and
     five JSON data stores feed eight Python builders; the builders write every
     published page and the sitemap; all pages share one stylesheet and one script; a
     pre-push gate of {{GATE}} browser checks stands between the builders and
     GitHub Pages; and {{JOBS}} scheduled jobs re-read the clouds' own feeds to
     keep four of those stores current -- the re:Invent catalog is fetched by
     hand, so no arrow reaches it from the jobs.">

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
  <g class="ab store">
    <rect x="16" y="254" width="140" height="34" rx="6"/>
    <text class="at" x="30" y="275">ai.json</text>
  </g>
  <g class="ab store">
    <rect x="16" y="296" width="140" height="34" rx="6"/>
    <text class="at" x="30" y="317">reinvent2026.json</text>
  </g>

  <!-- the clouds, and the jobs that read them -->
  <g class="ab vendor">
    <rect x="16" y="402" width="140" height="66" rx="6"/>
    <text class="at" x="30" y="424">AWS · Azure · GCP</text>
    <text class="as" x="30" y="439">their own feeds:</text>
    <text class="as" x="30" y="452">status, releases,</text>
    <text class="as" x="30" y="464">and events</text>
  </g>
  <g class="ab job">
    <rect x="16" y="492" width="140" height="48" rx="6"/>
    <text class="at" x="30" y="513">.github/workflows</text>
    <text class="as" x="30" y="528">{{JOBS}} jobs on a clock</text>
  </g>

  <!-- The jobs refresh all four stores, so the line reaches all four --
       up the outside of the column, with a stub into each. It used to be
       one straight line from the vendors to the top of the column, which
       meant it was drawn straight through ai.json on its way past. -->
  <path class="aw up1" d="M 86 402V 392H 8V 145H 16"/>
  <path class="aw up1b" d="M 8 187H 16"/>
  <path class="aw up1c" d="M 8 229H 16"/>
  <path class="aw up1d" d="M 8 271H 16"/>
  <path class="aw up2" d="M 86 492V 468"/>
  <text class="as" x="20" y="370">re-read, rebuilt,</text>
  <text class="as" x="20" y="382">committed</text>

  <!-- ================= builders ================= -->
  <g class="ab bld">
    <rect x="236" y="44" width="176" height="42" rx="6"/>
    <text class="at" x="250" y="66">sync_blog.py</text>
    <text class="as" x="250" y="79">posts, index, feed, archive</text>
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
  <g class="ab bld">
    <rect x="236" y="254" width="176" height="34" rx="6"/>
    <text class="at" x="250" y="275">build_ai_page.py</text>
  </g>
  <g class="ab bld">
    <rect x="236" y="296" width="176" height="46" rx="6"/>
    <text class="at" x="250" y="314">build_reinvent_page.py</text>
    <text class="as" x="250" y="327">the session catalog,</text>
    <text class="as" x="250" y="338">fetched by hand</text>
  </g>

  <path class="aa a1" d="M 156 65H 236"/>
  <path class="aa a1b" d="M 156 75V 105H 236"/>
  <path class="aa a2" d="M 156 145H 236"/>
  <path class="aa a3" d="M 156 187H 236"/>
  <path class="aa a4" d="M 156 229H 236"/>
  <path class="aa a5" d="M 156 271H 236"/>
  <path class="aa a6" d="M 156 313H 236"/>

  <g class="ab bld">
    <rect x="236" y="352" width="176" height="46" rx="6"/>
    <text class="at" x="250" y="370">build_sitemap.py</text>
    <text class="as" x="250" y="383">run by sync_blog.py,</text>
    <text class="as" x="250" y="394">walks the built site</text>
  </g>
  <g class="ab page crawl">
    <rect x="492" y="352" width="180" height="34" rx="6"/>
    <text class="at" x="506" y="367">sitemap.xml</text>
    <text class="as" x="506" y="380">robots.txt, for crawlers</text>
  </g>
  <path class="aa b6" d="M 412 369H 492"/>

  <!-- ================= the gate ================= -->
  <g class="ab gate">
    <rect x="236" y="418" width="176" height="74" rx="6"/>
    <text class="at" x="250" y="438">preflight.py</text>
    <text class="as" x="250" y="453">on everything just built:</text>
    <text class="as" x="250" y="466">{{GATE}} checks, a real browser</text>
    <text class="as" x="250" y="479">a failure refuses the push</text>
  </g>
  <path class="aw rail" d="M 240 406H 408"/>
  <path class="aw down" d="M 324 406V 418"/>

  <!-- ================= pages ================= -->
  <g class="ab page">
    <rect x="492" y="44" width="180" height="30" rx="6"/>
    <text class="at" x="506" y="63">Portfolio</text>
  </g>
  <g class="ab page">
    <rect x="492" y="80" width="180" height="30" rx="6"/>
    <text class="at" x="506" y="99">Blog · {{POSTS}} posts</text>
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
  <g class="ab page">
    <rect x="492" y="260" width="180" height="30" rx="6"/>
    <text class="at" x="506" y="279">j.AI</text>
  </g>
  <g class="ab page">
    <rect x="492" y="296" width="180" height="30" rx="6"/>
    <text class="at" x="506" y="315">re:Invent 2026</text>
  </g>

  <path class="aa b1" d="M 412 65H 492"/>
  <path class="aa b2" d="M 412 145H 470V 161H 492"/>
  <path class="aa b3" d="M 412 187H 470V 203H 492"/>
  <path class="aa b4" d="M 412 229H 470V 239H 492"/>
  <path class="aa b5" d="M 412 271H 470V 275H 492"/>
  <path class="aa b7" d="M 412 319H 470V 311H 492"/>

  <!-- ================= shipping ================= -->
  <g class="ab ship">
    <rect x="492" y="410" width="180" height="62" rx="6"/>
    <text class="at" x="506" y="432">GitHub Pages</text>
    <text class="as" x="506" y="447">static files, no server</text>
    <text class="as" x="506" y="461">nothing to restart</text>
  </g>
  <path class="aw pass" d="M 412 441H 492"/>
  <text class="as" x="424" y="434">passes</text>

  <!-- ================= the shared shell ================= -->
  <g class="ab shell">
    <rect x="492" y="492" width="252" height="62" rx="6"/>
    <text class="at" x="506" y="513">site-footer.css · site-footer.js</text>
    <text class="as" x="506" y="528">one bar, one theme, one menu</text>
    <text class="as" x="506" y="542">on all {{PAGES}} pages</text>
  </g>
  <path class="aw shellup" d="M 582 492V 472"/>

  <!-- ================= the reader ================= -->
  <g class="ab reader">
    <rect x="692" y="128" width="52" height="126" rx="6"/>
    <text class="at ar" x="718" y="196" text-anchor="middle">reader</text>
  </g>
  <path class="aa r1" d="M 672 191H 692"/>
</svg>
""" % VIEWBOX
