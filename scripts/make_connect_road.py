# -*- coding: utf-8 -*-
"""The whole road block -- CSS and markup -- from one place.

It had been assembled by splicing new rules in front of old ones, and the
card ended up carrying two complete copies: one from when a single robot
followed him, one from when four did. Later rules won so it looked right,
and every edit after that had to guess which copy it was hitting. This
emits the block entire, so there is one of it.

The road is a road now: a band with a dashed centre, fading at both ends.
He and the chain walk ON it. The three providers sit UNDER it, together,
because he works across all three rather than travelling between them --
as stops on a line they read as a route from one to the next, which was
never true and took four goes to stop saying.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_connect_walker as W          # noqa: E402
import make_connect_robot as R           # noqa: E402
import make_connect_chain as C           # noqa: E402
import make_connect_marks as M           # noqa: E402

BASE = """
/* The road, the walk, and the jump ---------------------------------------
   He walks the road with the model and its agents behind him, breaks
   stride in the middle and jumps with both arms up, and carries on. The
   three grounds sit underneath: AWS is the only one that breathes, and
   two of three staying still is what makes the third mean anything. */
.road { position: relative; margin: 8px 0 0;
  /* 53, not 56: the grounds row is absolutely positioned so it can
     hang a little past the box without moving anything, and the
     picture's head needs 12px of clear air under this block. */
  width: min(100%, 244px); height: 53px;
  font-size: .58rem; font-weight: 700; letter-spacing: .07em;
  text-transform: uppercase; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden;
      clip: rect(0 0 0 0); white-space: nowrap; margin: 0; }
.tarmac { position: absolute; left: 0; top: 33px; width: 100%; height: 11px;
  background: var(--muted); opacity: .28; border-radius: 1px;
  -webkit-mask-image: linear-gradient(90deg, transparent, #000 12%, #000 88%, transparent);
          mask-image: linear-gradient(90deg, transparent, #000 12%, #000 88%, transparent); }
.lane { position: absolute; left: 0; top: 38px; width: 100%; height: 1.4px;
  background: repeating-linear-gradient(90deg,
              var(--paper) 0 7px, transparent 7px 15px);
  opacity: .8;
  -webkit-mask-image: linear-gradient(90deg, transparent, #000 15%, #000 85%, transparent);
          mask-image: linear-gradient(90deg, transparent, #000 15%, #000 85%, transparent); }
/* Overhead boards ------------------------------------------------------
   One gantry per destination, hung over the carriageway on a short drop,
   spread to 20/50/80 so they are nowhere near each other.

   They sit BEHIND the walkers in the stacking order, so he and the chain
   pass in front of them rather than through them. That is the only way
   this works at all: a board needs the air above the road, and the air
   above the road is where he already is. In front of them it reads as a
   sign on the far side; drawn over him it would read as a mistake. */
/* 31 tall: the plate takes the top 13 and the drop runs the rest of the
     way down to the tarmac. The road had to move DOWN to make this work --
     with it where it was, the man's head was inside the boards and the
     whole chain sat on top of AZURE. Gantries need air, and the air above
     the road is where he walks. */
.sign { position: absolute; left: var(--at); top: 0; height: 33px; z-index: 0;
  transform: translateX(-50%);
  display: flex; flex-direction: column; align-items: center; line-height: 1; }
.plate { display: flex; align-items: center; gap: 4px;
  padding: 2px 5px 2px 4px; border-radius: 3px;
  border: 1px solid var(--line, rgba(90,74,56,.30));
  background: color-mix(in srgb, var(--paper) 88%, var(--ink) 5%); }
[data-theme="dark"] .plate { border-color: rgba(220,226,211,.22);
  background: color-mix(in srgb, var(--paper) 78%, #dce2d3 6%); }
.drop { width: 1.2px; flex: 1 0 6px; background: var(--muted); opacity: .42; }
.plate .pin { width: 11px; height: 11px; display: block; flex: none; }
.plate b { font: inherit; color: currentColor; }
.g-azu { color: #3a5570; } .g-aws { color: #6f5336; } .g-gcp { color: #4f5b30; }
[data-theme="dark"] .g-azu { color: #9ab8d4; }
[data-theme="dark"] .g-aws { color: #c49a68; }
[data-theme="dark"] .g-gcp { color: #9aad72; }
.g-azu .pin { fill: #1a7cc0; stroke: none; }
.g-aws .pin { fill: none; stroke: #d97f12; width: 12px; height: 12px; }
.g-gcp .pin { fill: none;
  --g-blue: #3d76c8; --g-red: #c8483c; --g-yellow: #d9a222; --g-green: #3d8f52; }
[data-theme="dark"] .g-azu .pin { fill: #6fb3e4; }
[data-theme="dark"] .g-aws .pin { stroke: #efa444; }
[data-theme="dark"] .g-gcp .pin {
  --g-blue: #7fa9e0; --g-red: #d97f76; --g-yellow: #e0be6a; --g-green: #79b58c; }
.hiker, .follow { z-index: 2; }

.hiker, .follow { position: absolute; left: 0; }
.follow > span { display: block; }
.hiker { top: 13px; width: 17px; }
.jump { display: block; }
.walker { width: 17px; height: 32px; display: block; fill: #241f1a; stroke: none; }
.bot { width: 11px; height: 19px; display: block; fill: #241f1a; stroke: none; }
.walker .far, .bot .far { opacity: .88; }
.walker .pack { fill: inherit; opacity: 1; }
[data-theme="dark"] .walker, [data-theme="dark"] .bot { fill: #a7b2a0; }
.wcheer { display: none; }
.walker > g > g, .bot > g { display: none; }

@media (prefers-reduced-motion: no-preference) {
  .hiker { animation: trek 26s linear infinite; }
  .jump { animation: hop 26s ease-out infinite; }
  .walker { animation: face 26s steps(1) infinite; }
  .wcyc { display: block; animation: showwalk 26s steps(1) infinite; }
  .wcheer { display: block; opacity: 0; animation: showjump 26s steps(1) infinite; }
  .walker > g > g { display: inline; opacity: 0; animation: cyc .72s steps(1) infinite; }
  .bot > g { display: inline; opacity: 0; animation: rcyc .48s steps(1) infinite; }
  .wcyc .k0 { animation-delay: 0s; }   .wcyc .k1 { animation-delay: .09s; }
  .wcyc .k2 { animation-delay: .18s; } .wcyc .k3 { animation-delay: .27s; }
  .wcyc .k4 { animation-delay: .36s; } .wcyc .k5 { animation-delay: .45s; }
  .wcyc .k6 { animation-delay: .54s; } .wcyc .k7 { animation-delay: .63s; }
  .wcheer .c1 { opacity: 1; }
  .g-aws .pin { animation: breathe 2.4s ease-in-out infinite; }
}
@media (prefers-reduced-motion: reduce) {
  .hiker { transform: translateX(112px); }
  .wcyc { display: block; } .wcyc .k0, .bot .r0 { display: inline; }
}
@keyframes trek {
  0%, 2% { transform: translateX(39px); }  20% { transform: translateX(112px); }
  28% { transform: translateX(112px); }    46% { transform: translateX(186px); }
  52% { transform: translateX(186px); }    70% { transform: translateX(112px); }
  78% { transform: translateX(112px); }    96%, 100% { transform: translateX(39px); }
}
@keyframes hop {
  0%, 21% { transform: translateY(0); }    23.5% { transform: translateY(-9px); }
  26%, 71% { transform: translateY(0); }   73.5% { transform: translateY(-9px); }
  76%, 100% { transform: translateY(0); }
}
@keyframes face { 0%, 47% { transform: scaleX(1); }
                  48%, 97% { transform: scaleX(-1); }
                  98%, 100% { transform: scaleX(1); } }
/* The pose swap has to land exactly on the airborne window. It used to
   start at 20.1% while the lift began at 21%, so for a beat he stood on
   the road with both arms in the air, and again after he came down --
   an instant change of silhouette with no motion to explain it, which
   reads as the figure blinking out and back rather than jumping. */
@keyframes showwalk { 0%, 21% { opacity: 1; } 21.1%, 25.9% { opacity: 0; }
                      26%, 71% { opacity: 1; } 71.1%, 75.9% { opacity: 0; }
                      76%, 100% { opacity: 1; } }
@keyframes showjump { 0%, 21% { opacity: 0; } 21.1%, 25.9% { opacity: 1; }
                      26%, 71% { opacity: 0; } 71.1%, 75.9% { opacity: 1; }
                      76%, 100% { opacity: 0; } }
@keyframes cheerA { 0%, 49.9% { opacity: 1; } 50%, 100% { opacity: 0; } }
@keyframes cheerB { 0%, 49.9% { opacity: 0; } 50%, 100% { opacity: 1; } }
@keyframes cyc { 0%, 12.4% { opacity: 1; } 12.5%, 100% { opacity: 0; } }
@keyframes rcyc { 0%, 24.9% { opacity: 1; } 25%, 100% { opacity: 0; } }
/* filter, not box-shadow: a box-shadow ring is the shape of the BOX, and
   the moment the dot became a logo that ring was a square drawn round it. */
@keyframes breathe {
  0%, 100% { transform: scale(1); filter: none; }
  50% { transform: scale(1.18); filter: drop-shadow(0 0 3px currentColor); }
}
"""

MARKUP = """    <div class="road">
      <p class="sr">I work across Azure, AWS and GCP &mdash; AWS most of all &mdash; with a model and the agents it runs alongside me.</p>
      <div class="tarmac"></div><div class="lane"></div>
      __CHAIN__
      <div class="hiker"><span class="jump">__MAN__</span></div>
      <span class="sign g-azu" style="--at:20%"><span class="plate">__AZU__<b>Azure</b></span><i class="drop"></i></span>
      <span class="sign g-aws" style="--at:50%"><span class="plate">__AWS__<b>AWS</b></span><i class="drop"></i></span>
      <span class="sign g-gcp" style="--at:80%"><span class="plate">__GCP__<b>GCP</b></span><i class="drop"></i></span>
    </div>"""


def css():
    return BASE + "\n" + C.css() + "\n" + C.puff_css() + "\n"


def _mark(kind):
    art = {"azu": M.AZURE, "aws": M.AWS, "gcp": M.GCP}[kind]
    return '<svg class="pin" viewBox="0 0 24 24" aria-hidden="true">%s</svg>' % art


def markup():
    return (MARKUP
            .replace("__AZU__", _mark("azu"))
            .replace("__AWS__", _mark("aws"))
            .replace("__GCP__", _mark("gcp"))
            .replace("__CHAIN__", C.markup(R.sprite()))
            .replace("__MAN__", W.sprite()))
