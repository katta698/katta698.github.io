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
/* Short plates on purpose. Every pixel this board is tall is a pixel the
   model names cannot rise into -- they come off the robots' heads, and the
   gap between the board and those heads is all the room they get. */
.plate { display: flex; align-items: center; gap: 4px;
  padding: 1px 5px 1px 4px; border-radius: 3px;
  border: 1px solid var(--line, rgba(90,74,56,.30));
  background: color-mix(in srgb, var(--paper) 88%, var(--ink) 5%); }
[data-theme="dark"] .plate { border-color: rgba(220,226,211,.22);
  background: color-mix(in srgb, var(--paper) 78%, #dce2d3 6%); }
.drop { width: 1.2px; flex: 1 0 6px; background: var(--muted); opacity: .42; }
.plate .pin { width: 9px; height: 9px; display: block; flex: none; }
.plate b { font: inherit; color: currentColor; }
.g-azu { color: #3a5570; } .g-aws { color: #6f5336; } .g-gcp { color: #4f5b30; }
[data-theme="dark"] .g-azu { color: #9ab8d4; }
[data-theme="dark"] .g-aws { color: #c49a68; }
[data-theme="dark"] .g-gcp { color: #9aad72; }
.g-azu .pin { fill: #1a7cc0; stroke: none; }
.g-aws .pin { fill: none; stroke: #d97f12; width: 10px; height: 10px; }
.g-gcp .pin { fill: none;
  --g-blue: #3d76c8; --g-red: #c8483c; --g-yellow: #d9a222; --g-green: #3d8f52; }
[data-theme="dark"] .g-azu .pin { fill: #6fb3e4; }
[data-theme="dark"] .g-aws .pin { stroke: #efa444; }
[data-theme="dark"] .g-gcp .pin {
  --g-blue: #7fa9e0; --g-red: #d97f76; --g-yellow: #e0be6a; --g-green: #79b58c; }
/* He is in front of all six; the formation's back row is behind
   the front row, which is what makes it read as a ring rather
   than a queue. The boards stay behind everybody at 0. */
.hiker { z-index: 4; }

.hiker, .follow { position: absolute; left: 0; }
.follow > span { display: block; }
/* 11, so his feet land on 42 -- the same line the robots stand on.
     He was on 44 and they were on 33. */
.hiker { top: 11px; width: 17px; }
.jump { display: block; }
.walker { width: 17px; height: 32px; display: block; fill: #241f1a; stroke: none; }
.bot { width: 11px; height: 19px; display: block; fill: #241f1a; stroke: none; }
.walker .far, .bot .far { opacity: .88; }
.walker .pack { fill: inherit; opacity: 1; }
[data-theme="dark"] .walker, [data-theme="dark"] .bot { fill: #a7b2a0; }
.wcheer, .wstand { display: none; }
.walker > g > g, .bot > g > g { display: none; }

@media (prefers-reduced-motion: no-preference) {
  .hiker { animation: trek 26s linear infinite; }
  .jump { animation: hop 26s ease-out infinite; }
  .walker { animation: face 26s steps(1) infinite; }
  /* steps(1), not linear. Adjacent keyframe stops still interpolate
     across the gap between them -- a tenth of a per cent of 26s is 26ms
     of both poses part-lit, which is a cross-fade however short. With
     steps(1) each interval holds its opening value and jumps at the
     end, so the windows tile exactly and nothing is ever part-drawn. */
  .wcyc { display: block; animation: showwalk 26s steps(1) infinite; }
  .wcheer { display: block; opacity: 0; animation: showjump 26s steps(1) infinite; }
  .wstand { display: block; opacity: 0; animation: showstand 26s steps(1) infinite; }
  /* Every pose in every group is laid out and transparent; which one is
     drawn is decided entirely by the group it sits in and the keyframes
     above. Only the two cycling groups step through their poses -- the
     standing pose is a single frame and holds. */
  .walker > g > g, .bot > g > g { display: inline; opacity: 0; }
  .wcyc > g { animation: cyc .72s steps(1) infinite; }
  .bot .rcyc > g { animation: rcyc .48s steps(1) infinite; }
  /* .walker .wstand, not .wstand: two classes and a type beats the
     one class and two types of the rule above it, and without the
     extra class the standing figure was laid out, switched on, and
     drawn at zero opacity -- a man who stopped by vanishing. The
     robots' rule already had the class and already worked, which is
     what made the difference visible. */
  .walker .wstand > g, .bot .rstand > g { opacity: 1; }
  .wcyc .k0 { animation-delay: 0s; }   .wcyc .k1 { animation-delay: .09s; }
  .wcyc .k2 { animation-delay: .18s; } .wcyc .k3 { animation-delay: .27s; }
  .wcyc .k4 { animation-delay: .36s; } .wcyc .k5 { animation-delay: .45s; }
  .wcyc .k6 { animation-delay: .54s; } .wcyc .k7 { animation-delay: .63s; }
  /* The two jump poses cut, they do not blend -- see showcrouch. */
  .wcheer .c0 { animation: showcrouch 26s steps(1) infinite; }
  .wcheer .c1 { animation: showair 26s steps(1) infinite; }
  .g-aws .pin { animation: breathe 2.4s ease-in-out infinite; }
}
@media (prefers-reduced-motion: reduce) {
  .hiker { transform: translateX(112px); }
  .wstand, .bot .rstand { display: block; }
  .wstand > g, .bot .rstand > g { display: inline; }
  .wcyc, .wcheer, .bot .rcyc { display: none; }
}
/* One round trip, then the team stands at AWS and works ---------------
   Out to Azure and straight back, out to GCP and straight back, then
   eight seconds at AWS -- three of them the six of them filing in around
   him, and five stood in formation. The two clouds he only reaches and
   turns at; AWS is the only place anybody stops, and the length of that
   stop is the whole point of the picture. Both legs are the same length,
   Azure being 73px off and GCP 74, so neither reads as further away than
   it is. The followers are not written here: they run a pursuit against
   this timeline in make_connect_chain.py, which is why they reflect off
   each turn one at a time instead of pivoting together. */
@keyframes trek {
  0% { transform: translateX(112px); }    15% { transform: translateX(39px); }
  18% { transform: translateX(39px); }    33% { transform: translateX(112px); }
  36% { transform: translateX(112px); }   51% { transform: translateX(186px); }
  54% { transform: translateX(186px); }   69%, 100% { transform: translateX(112px); }
}
/* The jump waits for the formation. He is home at 69% but the tail is
   still walking in until 81%, and a leader celebrating alone while his
   team is still arriving is not the picture -- they all go up together,
   him first and the rest in a wave behind him. */
@keyframes hop {
  0%, 86.5% { transform: translateY(0); }  88% { transform: translateY(-9px); }
  89.5%, 100% { transform: translateY(0); }
}
/* He never turns his back on the model. Coming home from GCP he is
   already facing left, which is the side f1 takes in the formation, so
   the huddle asks no turn of him at all -- and left is also the way he
   sets off for Azure on the next loop. */
@keyframes face { 0%, 17% { transform: scaleX(-1); }
                  18%, 53% { transform: scaleX(1); }
                  54%, 100% { transform: scaleX(-1); } }
/* Why there are three jump poses and no cross-fade.
   Two earlier goes at this both failed, and both failed for the same
   reason: the figure changed silhouette faster than a body can. First
   the swap was misaligned -- arms went up at 20.1% while the lift did
   not start until 21%, so for a beat he stood on the road with both
   arms overhead. Aligning it left a hard cut from mid-stride to
   both-arms-up, which at 27px still reads as a blink. So the cut was
   softened into a two-tenths cross-fade, and that was worse in a way
   that does not show up in a measurement of opacity: two silhouettes
   at half opacity do not add back up to one solid figure. Where they
   overlap you get 75%, where they do not you get 50%, so mid-fade he
   is genuinely see-through. Summing the two groups' opacity said
   0.5 + 0.5 = 1 and reported no problem, which is why it took a third
   report to find.
   The fix is the beat that was missing rather than a way to hide its
   absence: a crouch, held for a tenth of a second either side of the
   lift, so he gathers, leaves, lands and gathers again. Every change
   is now between neighbouring poses and every one of them is a hard
   cut -- nothing is ever partly transparent. */
/* Gather, and land. Bracketing the airborne pose on both sides. */
@keyframes showcrouch { 0%, 86.5% { opacity: 1; } 86.6%, 89.4% { opacity: 0; }
                        89.5%, 100% { opacity: 1; } }
@keyframes showair { 0%, 86.5% { opacity: 0; } 86.6%, 89.4% { opacity: 1; }
                     89.5%, 100% { opacity: 0; } }
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



# His gait, on the same footing as theirs -----------------------------------
# walk while he is going somewhere, stand while he is not, and the jump
# carved out of the stand at AWS. Generated from the timeline rather than
# typed, because it moved once already -- the round trip turned one stop
# into four -- and four hand-written windows that have to tile exactly is
# four chances to leave a gap nothing would report.
MAN_JUMP = (85.5, 90.5)
MAN_GAIT = ([(0.0, "walk"), (C.AT_AZ, "stand"), (C.OFF_AZ, "walk"),
             (C.HOME_1, "stand"), (C.OFF_HOME, "walk"),
             (C.AT_GCP, "stand"), (C.OFF_GCP, "walk"),
             (C.HOME_2, "stand"), (MAN_JUMP[0], "jump"), (MAN_JUMP[1], "stand")])


def gait_css():
    out = []
    for kind, want in (("showwalk", "walk"), ("showstand", "stand"),
                       ("showjump", "jump")):
        rows = ["@keyframes %s {" % kind]
        for i, (t, state) in enumerate(MAN_GAIT):
            nxt = MAN_GAIT[i + 1][0] if i + 1 < len(MAN_GAIT) else 100.0
            rows.append("  %.2f%%, %.2f%% { opacity: %d; }"
                        % (t, max(t, nxt - 0.01), 1 if state == want else 0))
        rows.append("}")
        out.append(chr(10).join(rows))
    return chr(10).join(out)


def css():
    return (BASE + chr(10) + gait_css() + chr(10) + C.css() + chr(10)
            + C.puff_css() + chr(10))


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
