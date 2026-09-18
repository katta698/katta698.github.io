#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The eight drawings for /how-this-was-made/.

Asked for: "maybe I'm somewhere in my favourite place, around the beach, I'm
just opening my laptop, I got an idea, write a blog -- and then how did I
automate it, where I don't have to sit hours and hours in front of my laptop...
some sort of pictorial animation on what each step does."

Inline SVG, drawn here rather than fetched. Eight scenes cost about 6KB of
markup and no requests at all; they scale to any screen without a second file
for retina; and because they are drawn with the page's own colours they theme
themselves, instead of being a dark rectangle sitting on a cream page.

All eight live in one <svg> as sibling groups and only the active one is
opaque. Nothing is inserted or removed, the viewBox never changes, and the
frame holds its height from the aspect ratio -- so the picture cannot push the
words underneath it around while somebody is reading them. Only the ACTIVE
scene animates: an off-screen group with a running keyframe is a phone battery
being spent on something nobody can see.

Kept in its own file because build_colophon.py is about counting things, and
six kilobytes of path data in the middle of it would bury that.
"""

VIEWBOX = "0 0 320 180"

SCENES = {

    # 1. The idea. Sea behind, sand underneath, someone sitting on it with a
    #    laptop and a coffee, and the thought arriving overhead.
    #
    #    Redrawn once. The first attempt put the head at y=108 and the chair
    #    between y=120 and y=152, so the person floated above their own seat;
    #    the idea sat at y=92 in the middle of the sea, where it read as a
    #    second sun; and the sand was faint enough that nothing had a ground
    #    to stand on. Everything below is anchored to two lines -- the horizon
    #    at y=104 and the sand at y=150 -- and drawn in that order: sky, sea,
    #    sand, chair, person, laptop, mug, idea.
    0: """
  <g class="sc" data-scene="0">
    <circle class="sun" cx="266" cy="34" r="13"/>
    <path class="wave w1" d="M4 64 q22 -6 44 0 t44 0 t44 0 t44 0 t44 0 t44 0
                             t44 0"/>
    <path class="wave w2" d="M4 76 q22 -6 44 0 t44 0 t44 0 t44 0 t44 0 t44 0
                             t44 0"/>
    <path class="horizon" d="M4 88 h312"/>
    <path class="sand" d="M4 88 q78 8 156 5 t156 -5 V176 H4 Z"/>
    <g class="chair">
      <path d="M114 110 l14 38 h44"/>
      <path d="M128 148 l-9 16 M172 148 l7 16"/>
    </g>
    <g class="figure">
      <circle class="head" cx="126" cy="102" r="9"/>
      <path class="body" d="M126 111 q6 18 10 34"/>
      <path class="legs" d="M136 145 l34 4 l7 15"/>
      <path class="arm" d="M131 122 q12 6 18 12"/>
    </g>
    <g class="laptop">
      <rect class="lap" x="144" y="134" width="30" height="5" rx="1.5"/>
      <path class="lid" d="M148 134 l5 -16 h20 l3 16 Z"/>
    </g>
    <g class="mug">
      <rect x="200" y="148" width="14" height="13" rx="2"/>
      <path class="handle" d="M214 152 q6 3 0 6"/>
      <path class="steam s1" d="M204 146 q4 -6 0 -10"/>
      <path class="steam s2" d="M210 146 q4 -6 0 -10"/>
    </g>
    <g class="spark">
      <circle class="think t-a" cx="128" cy="84" r="1.8"/>
      <circle class="think t-b" cx="130" cy="72" r="2.6"/>
      <circle class="bulb" cx="132" cy="52" r="8"/>
      <path class="ray" d="M132 38 v-7 M117 46 l-7 -4 M147 46 l7 -4"/>
    </g>
  </g>""",

    # 2. Write it. One file, one blinking caret, lines arriving.
    1: """
  <g class="sc" data-scene="1">
    <rect class="doc" x="108" y="30" width="104" height="120" rx="5"/>
    <path class="fold" d="M182 30 v22 h30"/>
    <path class="ln l1" d="M124 66 h56"/>
    <path class="ln l2" d="M124 82 h72"/>
    <path class="ln l3" d="M124 98 h48"/>
    <path class="ln l4" d="M124 114 h66"/>
    <rect class="caret" x="124" y="124" width="2" height="14"/>
    <text class="cap" x="160" y="170" text-anchor="middle">one file, by hand</text>
  </g>""",

    # 3. Check the draft. A lens over it, three ticks landing in turn.
    2: """
  <g class="sc" data-scene="2">
    <rect class="doc" x="86" y="36" width="96" height="112" rx="5"/>
    <path class="ln" d="M100 64 h50 M100 80 h64 M100 96 h40 M100 112 h56"/>
    <g class="ticks">
      <path class="tk t1" d="M198 60 l7 8 14 -16"/>
      <path class="tk t2" d="M198 92 l7 8 14 -16"/>
      <path class="tk t3" d="M198 124 l7 8 14 -16"/>
    </g>
    <g class="lens">
      <circle cx="134" cy="92" r="30"/>
      <path d="M156 114 l20 20"/>
    </g>
  </g>""",

    # 4. Build the site. One file fans out into many pages.
    3: """
  <g class="sc" data-scene="3">
    <rect class="doc src" x="30" y="70" width="52" height="64" rx="4"/>
    <path class="ln" d="M40 88 h30 M40 100 h22 M40 112 h26"/>
    <g class="fan">
      <path class="ray r1" d="M88 102 q48 -36 96 -50"/>
      <path class="ray r2" d="M88 102 q48 -12 96 -12"/>
      <path class="ray r3" d="M88 102 q48 12 96 28"/>
    </g>
    <g class="outs">
      <rect class="out o1" x="188" y="38" width="44" height="32" rx="3"/>
      <rect class="out o2" x="188" y="82" width="44" height="32" rx="3"/>
      <rect class="out o3" x="188" y="126" width="44" height="32" rx="3"/>
      <rect class="out o4" x="242" y="60" width="44" height="32" rx="3"/>
      <rect class="out o5" x="242" y="104" width="44" height="32" rx="3"/>
    </g>
  </g>""",

    # 5. Open it in a browser. A window, ten checks going green in turn.
    4: """
  <g class="sc" data-scene="4">
    <rect class="win" x="62" y="30" width="196" height="120" rx="6"/>
    <path class="bar" d="M62 52 h196"/>
    <circle class="dotw" cx="76" cy="41" r="3.5"/>
    <circle class="dotw" cx="88" cy="41" r="3.5"/>
    <circle class="dotw" cx="100" cy="41" r="3.5"/>
    <g class="grid">
      <circle class="chk c1" cx="94" cy="78" r="6"/>
      <circle class="chk c2" cx="122" cy="78" r="6"/>
      <circle class="chk c3" cx="150" cy="78" r="6"/>
      <circle class="chk c4" cx="178" cy="78" r="6"/>
      <circle class="chk c5" cx="206" cy="78" r="6"/>
      <circle class="chk c6" cx="94" cy="106" r="6"/>
      <circle class="chk c7" cx="122" cy="106" r="6"/>
      <circle class="chk c8" cx="150" cy="106" r="6"/>
      <circle class="chk c9" cx="178" cy="106" r="6"/>
      <circle class="chk c10" cx="206" cy="106" r="6"/>
    </g>
    <path class="ln" d="M94 132 h112"/>
  </g>""",

    # 6. Ship it. Pages rising into the cloud.
    5: """
  <g class="sc" data-scene="5">
    <path class="cloud" d="M106 74 a26 26 0 0 1 50 -10 a20 20 0 0 1 34 12
                           a18 18 0 0 1 -4 35 h-74 a19 19 0 0 1 -6 -37 Z"/>
    <g class="lift">
      <rect class="pg p1" x="110" y="128" width="30" height="24" rx="3"/>
      <rect class="pg p2" x="146" y="136" width="30" height="24" rx="3"/>
      <rect class="pg p3" x="182" y="128" width="30" height="24" rx="3"/>
    </g>
    <path class="up u1" d="M125 124 v-12"/>
    <path class="up u2" d="M161 132 v-12"/>
    <path class="up u3" d="M197 124 v-12"/>
  </g>""",

    # 7. Then it runs without me. A clock feeding the four pages.
    6: """
  <g class="sc" data-scene="6">
    <g class="vendors">
      <path class="vc v1" d="M14 44 a9 9 0 0 1 17 -3 a7 7 0 0 1 11 4
                             a6 6 0 0 1 -1 12 h-25 a6 6 0 0 1 -2 -13 Z"/>
      <path class="vc v2" d="M14 86 a9 9 0 0 1 17 -3 a7 7 0 0 1 11 4
                             a6 6 0 0 1 -1 12 h-25 a6 6 0 0 1 -2 -13 Z"/>
      <path class="vc v3" d="M14 128 a9 9 0 0 1 17 -3 a7 7 0 0 1 11 4
                             a6 6 0 0 1 -1 12 h-25 a6 6 0 0 1 -2 -13 Z"/>
      <path class="pipe g1" d="M46 52 q14 18 28 28"/>
      <path class="pipe g2" d="M46 94 h28"/>
      <path class="pipe g3" d="M46 136 q14 -18 28 -28"/>
    </g>
    <g class="clock">
      <circle cx="92" cy="90" r="20"/>
      <path class="hand hh" d="M92 90 v-11"/>
      <path class="hand mh" d="M92 90 l9 6"/>
    </g>
    <path class="feed f1" d="M116 78 q20 -18 38 -20"/>
    <path class="feed f2" d="M116 86 q20 -4 38 -4"/>
    <path class="feed f3" d="M116 94 q20 10 38 14"/>
    <path class="feed f4" d="M116 102 q20 24 38 30"/>
    <g class="cards">
      <rect class="cd d1" x="154" y="42" width="112" height="24" rx="4"/>
      <text class="cdt" x="166" y="58">What&#8217;s new</text>
      <rect class="cd d2" x="154" y="74" width="112" height="24" rx="4"/>
      <text class="cdt" x="166" y="90">Live status</text>
      <rect class="cd d3" x="154" y="106" width="112" height="24" rx="4"/>
      <text class="cdt" x="166" y="122">Cloud events</text>
      <rect class="cd d4" x="154" y="138" width="112" height="24" rx="4"/>
      <text class="cdt" x="166" y="154">Intelligence</text>
    </g>
  </g>""",

    # 8. Ask it anything. The archive is read first, then the answer, then
    #    the citation -- in that order, because that is the claim.
    7: """
  <g class="sc" data-scene="7">
    <g class="shelf">
      <rect class="bk b1" x="26" y="74" width="12" height="52" rx="2"/>
      <rect class="bk b2" x="42" y="62" width="12" height="64" rx="2"/>
      <rect class="bk b3" x="58" y="82" width="12" height="44" rx="2"/>
      <rect class="bk b4" x="74" y="68" width="12" height="58" rx="2"/>
      <path class="ln" d="M22 128 h70"/>
      <text class="cap" x="57" y="148" text-anchor="middle">255 posts</text>
    </g>
    <path class="pull q1" d="M96 94 q28 -14 52 -16"/>
    <path class="pull q2" d="M96 100 q28 8 52 12"/>
    <g class="term">
      <rect class="win" x="150" y="42" width="120" height="98" rx="6"/>
      <path class="bar" d="M150 60 h120"/>
      <path class="qmark" d="M164 80 h44"/>
      <path class="ans a1" d="M164 98 h84"/>
      <path class="ans a2" d="M164 110 h62"/>
      <path class="cite" d="M164 126 h36"/>
    </g>
  </g>""",
}
