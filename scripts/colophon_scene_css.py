#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Styling and motion for the eight drawings on /how-this-was-made/.

Three rules hold this together, and all three are about not doing damage:

1. Nothing here changes layout. The frame's height comes from an aspect
   ratio, the viewBox never changes, and scenes cross-fade in place. A
   picture that resizes is a picture that shoves the paragraph below it
   while somebody is reading it.

2. Only the active scene animates. `.sc` is opacity 0 and
   `animation-play-state: paused`; the active one runs. Otherwise eight
   scenes' worth of keyframes run forever on a phone for seven pictures
   nobody is looking at.

3. Colour comes from the page. Strokes are currentColor and the accent is
   --acc-ink, so the drawings follow the theme instead of being a dark
   rectangle on a cream page.

prefers-reduced-motion stops every keyframe and leaves each scene in its
finished state -- drawn, complete, still.
"""

SCENE_CSS = """
  /* The frame reserves its own height from the ratio, so the words below it
     never move when the picture changes. */
  .cf-scene { position: relative; width: 100%; max-width: 30rem;
              margin: 0 0 1.2rem; aspect-ratio: 320 / 180;
              border: 1px solid var(--bd, var(--border, #33302C));
              border-radius: 12px; overflow: hidden;
              background: color-mix(in srgb,
                          var(--tx, var(--text, #EDEBE6)) 3%, transparent); }
  .cf-scene svg { position: absolute; inset: 0; width: 100%; height: 100%; }

  .sc { opacity: 0; transition: opacity .45s ease; }
  .sc.is-on { opacity: 1; }
  /* Paused unless on screen and current. */
  .sc * { animation-play-state: paused; }
  .sc.is-on * { animation-play-state: running; }

  .cf-scene svg { color: var(--tx, var(--text, #EDEBE6)); }
  .sc path, .sc circle, .sc rect, .sc line {
    fill: none; stroke: currentColor; stroke-width: 2;
    stroke-linecap: round; stroke-linejoin: round;
    vector-effect: non-scaling-stroke; }
  .sc text { fill: var(--mut, var(--text-muted, #9C9A94)); stroke: none;
             font-family: 'DM Mono', ui-monospace, monospace; font-size: 9px;
             letter-spacing: .04em; }
  .sc .cap { font-size: 8.5px; }

  /* ---- 1. the idea ---- */
  .sc .sun { stroke: var(--acc-ink, var(--acc, #C4A484));
             fill: color-mix(in srgb, var(--acc-ink, #C4A484) 22%, transparent);
             animation: cf-breathe 5s ease-in-out infinite; }
  .sc .wave { opacity: .5; animation: cf-drift 7s ease-in-out infinite; }
  .sc .w2 { animation-duration: 9s; animation-direction: reverse; }
  .sc .horizon { opacity: .35; }
  /* Filled, so the figure has ground under it rather than floating on a
     line nobody can see. */
  .sc .sand { opacity: .5; stroke: none;
              fill: color-mix(in srgb, var(--acc-ink, #C4A484) 12%,
                              transparent); }
  .sc .chair path { opacity: .6; }
  .sc .figure .head, .sc .figure .body, .sc .figure .legs,
  .sc .figure .arm { stroke-width: 2.2; }
  .sc .lid, .sc .lap { stroke: var(--acc-ink, var(--acc, #C4A484)); }
  .sc .steam { opacity: 0; animation: cf-steam 3.2s ease-out infinite; }
  .sc .s2 { animation-delay: 1.1s; }
  .sc .spark .bulb { stroke: var(--acc-ink, var(--acc, #C4A484));
                     fill: color-mix(in srgb, var(--acc-ink, #C4A484) 25%,
                                     transparent);
                     animation: cf-pop 3.4s ease-out infinite; }
  .sc .spark .ray { stroke: var(--acc-ink, var(--acc, #C4A484));
                    animation: cf-pop 3.4s ease-out infinite; }
  /* Two dots between the head and the idea, so it reads as a thought
     someone is having rather than a second sun in the sky. */
  .sc .think { stroke: var(--acc-ink, var(--acc, #C4A484));
               fill: var(--acc-ink, var(--acc, #C4A484));
               opacity: 0; animation: cf-pop 3.4s ease-out infinite; }
  .sc .t-a { animation-delay: -.5s; }
  .sc .t-b { animation-delay: -.25s; }

  /* ---- 2. write it ---- */
  .sc .ln { opacity: .55; }
  .sc .l1, .sc .l2, .sc .l3, .sc .l4 {
    stroke-dasharray: 90; stroke-dashoffset: 90; opacity: .75;
    animation: cf-type 4.4s ease-out infinite; }
  .sc .l2 { animation-delay: .35s; }
  .sc .l3 { animation-delay: .7s; }
  .sc .l4 { animation-delay: 1.05s; }
  .sc .caret { stroke: var(--acc-ink, var(--acc, #C4A484));
               animation: cf-blink 1.1s steps(1) infinite; }

  /* ---- 3. check the draft ---- */
  .sc .lens circle, .sc .lens path {
    stroke: var(--acc-ink, var(--acc, #C4A484));
    animation: cf-sweep 5s ease-in-out infinite; }
  .sc .lens circle { fill: color-mix(in srgb,
                     var(--acc-ink, #C4A484) 8%, transparent); }
  .sc .tk { stroke: var(--acc-ink, var(--acc, #C4A484)); stroke-width: 2.4;
            stroke-dasharray: 30; stroke-dashoffset: 30;
            animation: cf-tick 5s ease-out infinite; }
  .sc .t2 { animation-delay: .5s; }
  .sc .t3 { animation-delay: 1s; }

  /* ---- 4. build ---- */
  .sc .src { stroke: var(--acc-ink, var(--acc, #C4A484)); }
  .sc .ray { opacity: .45; stroke-dasharray: 130; stroke-dashoffset: 130;
             animation: cf-flow 3.4s ease-out infinite; }
  .sc .r2 { animation-delay: .25s; }
  .sc .r3 { animation-delay: .5s; }
  .sc .out { opacity: 0; animation: cf-land 3.4s ease-out infinite; }
  .sc .o2 { animation-delay: .2s; }
  .sc .o3 { animation-delay: .4s; }
  .sc .o4 { animation-delay: .6s; }
  .sc .o5 { animation-delay: .8s; }

  /* ---- 5. the gate ---- */
  .sc .win { fill: color-mix(in srgb,
             var(--tx, var(--text, #EDEBE6)) 4%, transparent); }
  .sc .bar { opacity: .5; }
  .sc .dotw { opacity: .45; stroke-width: 1.6; }
  .sc .chk { opacity: .3; animation: cf-pass 4.6s ease-out infinite; }
  .sc .c2 { animation-delay: .12s; }  .sc .c3 { animation-delay: .24s; }
  .sc .c4 { animation-delay: .36s; }  .sc .c5 { animation-delay: .48s; }
  .sc .c6 { animation-delay: .60s; }  .sc .c7 { animation-delay: .72s; }
  .sc .c8 { animation-delay: .84s; }  .sc .c9 { animation-delay: .96s; }
  .sc .c10 { animation-delay: 1.08s; }

  /* ---- 6. ship it ---- */
  .sc .cloud { stroke: var(--acc-ink, var(--acc, #C4A484));
               fill: color-mix(in srgb,
                     var(--acc-ink, #C4A484) 10%, transparent); }
  .sc .pg { animation: cf-rise 3.6s ease-in-out infinite; }
  .sc .p2 { animation-delay: .3s; }
  .sc .p3 { animation-delay: .6s; }
  .sc .up { opacity: .4; stroke-dasharray: 4 5;
            animation: cf-up 1.6s linear infinite; }
  .sc .u2 { animation-delay: .3s; }
  .sc .u3 { animation-delay: .6s; }

  /* ---- 7. it runs without me ---- */
  /* The three clouds, because the narration names them: the jobs read
     the vendors' own feeds. A clock with nothing feeding it would be a
     picture of a schedule, not of where the data comes from. */
  .sc .vc { opacity: .55; }
  .sc .pipe { opacity: .45; stroke-dasharray: 4 5;
              animation: cf-up 2s linear infinite; }
  .sc .g2 { animation-delay: .25s; }
  .sc .g3 { animation-delay: .5s; }
  .sc .clock circle { stroke: var(--acc-ink, var(--acc, #C4A484)); }
  .sc .hh { transform-origin: 92px 90px;
            animation: cf-spin 8s linear infinite; }
  .sc .mh { transform-origin: 92px 90px;
            animation: cf-spin 2s linear infinite; }
  .sc .feed { opacity: .5; stroke-dasharray: 5 6;
              animation: cf-up 2.4s linear infinite; }
  .sc .f2 { animation-delay: .3s; }
  .sc .f3 { animation-delay: .6s; }
  .sc .f4 { animation-delay: .9s; }
  .sc .cd { animation: cf-glow 4.8s ease-in-out infinite; }
  .sc .d2 { animation-delay: .6s; }
  .sc .d3 { animation-delay: 1.2s; }
  .sc .d4 { animation-delay: 1.8s; }

  /* ---- 8. ask it ---- */
  .sc .bk { opacity: .5; }
  .sc .b2 { animation: cf-lift 4.4s ease-in-out infinite; }
  .sc .pull { stroke: var(--acc-ink, var(--acc, #C4A484)); opacity: .55;
              stroke-dasharray: 60; stroke-dashoffset: 60;
              animation: cf-flow 4.4s ease-out infinite; }
  .sc .q2 { animation-delay: .2s; }
  .sc .qmark { stroke: var(--acc-ink, var(--acc, #C4A484)); opacity: .8; }
  .sc .ans { opacity: .55; stroke-dasharray: 90; stroke-dashoffset: 90;
             animation: cf-type 4.4s ease-out infinite;
             animation-delay: 1s; }
  .sc .a2 { animation-delay: 1.3s; }
  .sc .cite { stroke: var(--acc-ink, var(--acc, #C4A484));
              stroke-dasharray: 40; stroke-dashoffset: 40;
              animation: cf-type 4.4s ease-out infinite;
              animation-delay: 1.7s; }

  @keyframes cf-breathe { 0%,100% { opacity: .85 } 50% { opacity: 1 } }
  @keyframes cf-drift   { 0%,100% { transform: translateX(0) }
                          50% { transform: translateX(-10px) } }
  @keyframes cf-steam   { 0% { opacity: 0; transform: translateY(2px) }
                          35% { opacity: .7 }
                          100% { opacity: 0; transform: translateY(-9px) } }
  @keyframes cf-pop     { 0%,60%,100% { opacity: .45 }
                          75% { opacity: 1 } }
  @keyframes cf-type    { 0% { stroke-dashoffset: 90 }
                          45%,100% { stroke-dashoffset: 0 } }
  @keyframes cf-blink   { 0%,49% { opacity: 1 } 50%,100% { opacity: 0 } }
  @keyframes cf-sweep   { 0%,100% { transform: translate(0,0) }
                          50% { transform: translate(34px, 26px) } }
  @keyframes cf-tick    { 0%,10% { stroke-dashoffset: 30 }
                          35%,100% { stroke-dashoffset: 0 } }
  @keyframes cf-flow    { 0% { stroke-dashoffset: 130 }
                          55%,100% { stroke-dashoffset: 0 } }
  @keyframes cf-land    { 0%,20% { opacity: 0; transform: translateX(-6px) }
                          55%,100% { opacity: .85; transform: translateX(0) } }
  @keyframes cf-pass    { 0%,15% { opacity: .25 }
                          40%,100% { opacity: 1 } }
  @keyframes cf-rise    { 0%,100% { transform: translateY(0) }
                          50% { transform: translateY(-5px) } }
  @keyframes cf-up      { to { stroke-dashoffset: -18 } }
  @keyframes cf-spin    { to { transform: rotate(360deg) } }
  @keyframes cf-glow    { 0%,70%,100% { opacity: .5 } 85% { opacity: 1 } }
  @keyframes cf-lift    { 0%,100% { transform: translateY(0) }
                          50% { transform: translateY(-5px) } }

  /* ---- the whole-architecture diagram ----------------------------------
     A different job from the eight scenes: those illustrate one step each,
     this one has to be READ. So the boxes are labelled, the type is set at a
     size that survives being scaled down, and it scrolls sideways on a phone
     rather than shrinking to nothing -- 760px of diagram squeezed into 340
     would be a picture of a diagram, not a diagram.

     The only motion is the flow along the arrows. Everything else holds
     still, because the point here is to be studied, not watched. */
  .cf-arch { margin: 1.2rem 0 0; overflow-x: auto; overflow-y: hidden;
             -webkit-overflow-scrolling: touch;
             border: 1px solid var(--bd, var(--border, #33302C));
             border-radius: 12px; padding: .6rem;
             background: color-mix(in srgb,
                         var(--tx, var(--text, #EDEBE6)) 3%, transparent); }
  .cf-arch-svg { display: block; width: 100%; min-width: 660px;
                 height: auto; color: var(--tx, var(--text, #EDEBE6)); }
  .cf-arch-hint { font-family: 'DM Mono', ui-monospace, monospace;
                  font-size: .64rem; letter-spacing: .08em;
                  text-transform: uppercase; margin: .5rem 0 0;
                  color: var(--mut, var(--text-muted, #9C9A94)); }
  @media (min-width: 700px) { .cf-arch-hint { display: none; } }

  .cf-arch-svg .ab rect { fill: none; stroke: currentColor; stroke-width: 1.4;
                          opacity: .45; vector-effect: non-scaling-stroke; }
  .cf-arch-svg .at { fill: currentColor; font-family: 'DM Sans', system-ui,
                     sans-serif; font-size: 13px; font-weight: 500; }
  .cf-arch-svg .as { fill: var(--mut, var(--text-muted, #9C9A94));
                     font-family: 'DM Mono', ui-monospace, monospace;
                     font-size: 9.5px; }
  .cf-arch-svg .ah { fill: var(--mut, var(--text-muted, #9C9A94));
                     font-family: 'DM Mono', ui-monospace, monospace;
                     font-size: 9px; letter-spacing: .12em; }
  .cf-arch-svg .ar { font-size: 12px; }

  /* The three things worth finding at a glance get the accent: what you
     write, what refuses a bad push, and what every page shares. */
  .cf-arch-svg .src rect, .cf-arch-svg .gate rect,
  .cf-arch-svg .shell rect { stroke: var(--acc-ink, var(--acc, #C4A484));
                             opacity: .85; }
  .cf-arch-svg .src .at, .cf-arch-svg .gate .at,
  .cf-arch-svg .shell .at { fill: var(--acc-ink, var(--acc, #C4A484)); }

  .cf-arch-svg .aa, .cf-arch-svg .aw {
    fill: none; stroke: currentColor; stroke-width: 1.4; opacity: .4;
    vector-effect: non-scaling-stroke; }
  .cf-arch-svg .aa { stroke-dasharray: 4 5;
                     animation: cf-up 2.4s linear infinite; }
  .cf-arch-svg .aw { stroke: var(--acc-ink, var(--acc, #C4A484)); opacity: .55;
                     stroke-dasharray: 4 5;
                     animation: cf-up 2.4s linear infinite; }
  .cf-arch-svg .a2 { animation-delay: .2s; }
  .cf-arch-svg .a3 { animation-delay: .4s; }
  .cf-arch-svg .a4 { animation-delay: .6s; }
  .cf-arch-svg .b2 { animation-delay: .3s; }
  .cf-arch-svg .b3 { animation-delay: .5s; }
  .cf-arch-svg .b4 { animation-delay: .7s; }

  @media (prefers-reduced-motion: reduce) {
    .cf-arch-svg .aa, .cf-arch-svg .aw { animation: none; }
  }

  /* ---- the player -------------------------------------------------------
     Shaped like a video player because that is what it is: picture, caption,
     then the controls, in that order and touching. They used to sit after
     the whole list of steps, which is the one place a reader would not think
     to look.

     Expanding does not MOVE the picture in the document -- the player keeps
     its own height while the scene inside goes position:fixed -- so the words
     below never jump up to fill a gap and back down again. */
  .cf-player { position: relative; max-width: 30rem; margin: 1.2rem 0 0; }
  .cf-player .cf-scene { position: relative; margin: 0; }

  /* Expand lives on the picture, not in a row of words. */
  .cf-corner { position: absolute; right: 8px; bottom: 8px; z-index: 3;
               width: 30px; height: 30px; display: grid; place-items: center;
               font-size: .92rem; line-height: 1; cursor: pointer;
               border-radius: 8px;
               color: var(--tx, var(--text, #EDEBE6));
               background: color-mix(in srgb,
                           var(--bg, var(--surface, #1F1D1B)) 72%, transparent);
               border: 1px solid var(--bd, var(--border, #33302C)); }
  .cf-corner:hover { color: var(--acc-ink, var(--acc, #C4A484)); }

  /* Always present, so muting the sound costs a reader nothing. */
  .cf-cap { margin: .6rem 0 .1rem; min-height: 3.2rem; font-size: .92rem;
            line-height: 1.6; color: var(--tx, var(--text, #EDEBE6)); }

  .cf-bar { display: flex; align-items: center; gap: .6rem;
            padding: .4rem 0 0; }
  .cf-play { width: 34px; height: 34px; flex: 0 0 auto; cursor: pointer;
             display: grid; place-items: center; font-size: .8rem;
             border-radius: 50%;
             color: var(--bg, var(--surface, #1F1D1B));
             background: var(--acc-ink, var(--acc, #C4A484));
             border: none; }
  .cf-icon { width: 30px; height: 30px; flex: 0 0 auto; cursor: pointer;
             display: grid; place-items: center; font-size: .82rem;
             border-radius: 8px; background: transparent;
             color: var(--mut, var(--text-muted, #9C9A94));
             border: 1px solid var(--bd, var(--border, #33302C)); }
  .cf-icon:hover { color: var(--tx, var(--text, #EDEBE6)); }
  .cf-count { font-family: 'DM Mono', ui-monospace, monospace;
              font-size: .7rem; flex: 0 0 auto;
              color: var(--mut, var(--text-muted, #9C9A94)); }

  /* The scrubber. Track filled to --cf-pct behind the thumb, which is what
     makes a range input read as progress rather than as a slider. */
  .cf-seek { flex: 1 1 auto; -webkit-appearance: none; appearance: none;
             height: 4px; border-radius: 4px; cursor: pointer; margin: 0;
             background: linear-gradient(to right,
               var(--acc-ink, #C4A484) 0 var(--cf-pct, 0%),
               var(--bd, var(--border, #33302C)) var(--cf-pct, 0%) 100%); }
  .cf-seek::-webkit-slider-thumb { -webkit-appearance: none; appearance: none;
             width: 13px; height: 13px; border-radius: 50%; border: none;
             background: var(--acc-ink, var(--acc, #C4A484)); }
  .cf-seek::-moz-range-thumb { width: 13px; height: 13px; border: none;
             border-radius: 50%;
             background: var(--acc-ink, var(--acc, #C4A484)); }
  .cf-seek:focus-visible { outline: 2px solid var(--acc-ink, #C4A484);
                           outline-offset: 4px; }

  body.cf-zoomed { overflow: hidden; }
  .cf-backdrop { position: fixed; inset: 0; z-index: 2000;
                 background: var(--bg, var(--surface, #1F1D1B)); }
  .cf-player.is-zoomed { z-index: 2001; }
  .cf-player.is-zoomed .cf-scene {
    position: fixed; z-index: 2001; left: 50%; top: 46%;
    transform: translate(-50%, -50%);
    width: min(92vw, 1100px); margin: 0; }
  .cf-player.is-zoomed .cf-cap,
  .cf-player.is-zoomed .cf-bar {
    position: fixed; z-index: 2002; left: 50%; transform: translateX(-50%);
    width: min(92vw, 1100px); max-width: none; }
  .cf-player.is-zoomed .cf-cap { bottom: 13vh; text-align: center;
                                 font-size: 1.05rem; }
  .cf-player.is-zoomed .cf-bar { bottom: 5vh; }

  @media (max-width: 560px) { .cf-player { max-width: 100%; } }


  /* Asked for less movement: every scene sits in its finished state. */
  @media (prefers-reduced-motion: reduce) {
    .sc *, .sc.is-on * { animation: none !important; }
    .sc .l1, .sc .l2, .sc .l3, .sc .l4, .sc .ans, .sc .cite, .sc .pull,
    .sc .ray, .sc .tk { stroke-dashoffset: 0; }
    .sc .out, .sc .chk { opacity: .85; }
    .sc .steam { opacity: .5; }
  }

  @media (max-width: 560px) {
    .cf-scene { max-width: 100%; }
  }
"""
