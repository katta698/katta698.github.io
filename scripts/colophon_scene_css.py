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
  /* The direct child only.
     This rule exists to stretch the SCENE drawing across the frame. Once the
     controls moved inside the frame, `.cf-scene svg` also caught every icon
     in the bar: each button's 14px glyph became an absolutely positioned
     348x42 sheet covering the whole bar, stacked five deep. The topmost one
     -- Expand -- then swallowed every tap meant for CC, mute or replay.
     Nothing looked wrong; the buttons simply did nothing. */
  .cf-scene > svg { position: absolute; inset: 0; width: 100%; height: 100%; }

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
     Everything inside the frame, nothing after it.

     "Just have the video, have all those options within the video. Why do we
     have that line underneath? When users check subtitles it has all the
     information." So the subtitle and the controls are overlaid on the
     picture, and the frame is the whole component -- no caption paragraph
     below it, no button row after it, nothing to read in two places.

     Nothing moves until it is played, either. .sc animations are paused
     until the player carries .is-playing, so a reader who scrolls past sees
     a still picture and a play button, not a page that started without
     being asked. */
  .cf-player { position: relative; max-width: 34rem; margin: 1.2rem 0 0; }
  .cf-player .cf-scene { position: relative; margin: 0; }

  .sc * { animation-play-state: paused; }
  .cf-player.is-playing .sc.is-on * { animation-play-state: running; }

  /* The big one, over the middle, until the first play. */
  .cf-big { position: absolute; left: 50%; top: 50%; z-index: 4;
            transform: translate(-50%, -50%);
            width: 62px; height: 62px; border-radius: 50%;
            display: grid; place-items: center; cursor: pointer;
            font-size: 1.3rem; padding-left: 4px; border: none;
            color: var(--bg, var(--surface, #1F1D1B));
            background: color-mix(in srgb,
                        var(--acc-ink, #C4A484) 92%, transparent);
            transition: opacity .25s ease; }
  .cf-player.is-playing .cf-big,
  .cf-player.is-started .cf-big { opacity: 0; pointer-events: none; }

  /* Subtitle, on the picture, above the controls. */
  /* Subtitles sit ON the drawing, so they need something behind them.
     A text-shadow alone was not enough: the sentence ran straight through
     the figure and the laptop, and light strokes under light text is exactly
     where reading breaks down. A box behind the words -- and behind only the
     words, via box-decoration-break, so a short line does not draw a
     full-width bar -- is what every captioned video does, for this reason. */
  .cf-cap { position: absolute; left: 0; right: 0; bottom: 52px; z-index: 3;
            margin: 0; padding: 0 1rem; text-align: center;
            font-size: .92rem; line-height: 1.7; opacity: 0;
            transition: opacity .25s ease; color: #F4F1EC; }
  .cf-cap span {
    background: rgba(12, 11, 10, .74);
    padding: .18em .5em; border-radius: 4px;
    -webkit-box-decoration-break: clone; box-decoration-break: clone; }
  .cf-player.is-started .cf-cap { opacity: 1; }

  /* The control row, on the picture, over a scrim so it stays readable
     whatever the drawing is doing underneath it. */
  /* z-index 901, and the number is not arbitrary.
     The feedback star is fixed at right:14px, top:50% with z-index 900, so
     on a phone it floats in the same column as the last control here. The
     first fix padded this bar 58px clear of it -- which worked, and left the
     controls visibly shoved left with a hole at the right edge, permanently,
     to dodge an overlap that only happens at one scroll position. Sitting
     above it instead keeps the row balanced and keeps every tap landing on
     the button it was aimed at. */
  .cf-bar { position: absolute; left: 0; right: 0; bottom: 0; z-index: 901;
            display: flex; align-items: center; gap: .55rem;
            max-width: 100%; box-sizing: border-box;
            padding: .5rem .7rem .55rem;
            background: linear-gradient(to top,
              rgba(0,0,0,.72), rgba(0,0,0,.42) 60%, rgba(0,0,0,0));
            border-radius: 0 0 11px 11px; }
  .cf-play { width: 28px; height: 28px; flex: 0 0 auto; cursor: pointer;
             display: grid; place-items: center; font-size: .72rem;
             border-radius: 50%; border: none; color: #1F1D1B;
             background: var(--acc-ink, #C4A484); }
  .cf-icon { width: 26px; height: 26px; flex: 0 0 auto; cursor: pointer;
             display: grid; place-items: center; font-size: .76rem;
             border-radius: 6px; background: transparent; color: #EDEBE6;
             border: 1px solid rgba(237,235,230,.28); }
  .cf-icon:hover { border-color: var(--acc-ink, #C4A484);
                   color: var(--acc-ink, #C4A484); }
  .cf-count { font-family: 'DM Mono', ui-monospace, monospace;
              font-size: .66rem; flex: 0 0 auto; color: #D8D4CC; }
  /* CC reads as a label, not a glyph, so it is wider and set in mono --
     and the OFF state has to be visibly off at a glance, which a pressed
     state alone is not. */
  .cf-cc { width: auto; padding: 0 .42rem;
           font-family: 'DM Mono', ui-monospace, monospace;
           font-size: .62rem; letter-spacing: .06em; }
  .cf-cc[aria-pressed="true"] { color: #1F1D1B;
                                background: var(--acc-ink, #C4A484);
                                border-color: var(--acc-ink, #C4A484); }
  .cf-cc[aria-pressed="false"] { opacity: .62; }

  /* min-width: 0 is load-bearing.
     A range input has an intrinsic width near 129px and will not shrink
     below it, so at 390px the bar overflowed its own frame and the controls
     sat on top of each other -- Playwright caught it as the Expand button
     intercepting taps meant for CC. A reader would have called it "the
     subtitles button does nothing". */
  .cf-seek { flex: 1 1 auto; min-width: 0; -webkit-appearance: none;
             appearance: none;
             height: 4px; border-radius: 4px; cursor: pointer; margin: 0;
             background: linear-gradient(to right,
               var(--acc-ink, #C4A484) 0 var(--cf-pct, 0%),
               rgba(237,235,230,.30) var(--cf-pct, 0%) 100%); }
  .cf-seek::-webkit-slider-thumb { -webkit-appearance: none; appearance: none;
             width: 12px; height: 12px; border-radius: 50%; border: none;
             background: var(--acc-ink, #C4A484); }
  .cf-seek::-moz-range-thumb { width: 12px; height: 12px; border: none;
             border-radius: 50%; background: var(--acc-ink, #C4A484); }
  .cf-seek:focus-visible { outline: 2px solid var(--acc-ink, #C4A484);
                           outline-offset: 3px; }

  body.cf-zoomed { overflow: hidden; }
  .cf-backdrop { position: fixed; inset: 0; z-index: 2000;
                 background: var(--bg, var(--surface, #1F1D1B)); }
  .cf-player.is-zoomed .cf-scene {
    position: fixed; z-index: 2001; left: 50%; top: 50%;
    transform: translate(-50%, -50%);
    width: min(94vw, 1180px); margin: 0; }
  /* Expanded: the caption comes OFF the picture.
     -----------------------------------------------------------------------
     Reported as: "when I expand the video it doesn't show me anything, I
     only see text." Measured on a phone, and he was right twice over:

         normal     scene 350x197   caption 35px   18% of the frame
         expanded   scene 367x206   caption 79px   38% of the frame

     Expanding bought SEVENTEEN PIXELS -- min(94vw,1180px) on a 390px screen
     is 367px, and a 16:9 picture cannot get taller without getting wider --
     while the caption doubled. A slightly bigger frame with text across most
     of it, floating in a screen that is otherwise empty black.

     So in the expanded view the subtitle sits under the picture instead of
     on it, in the space that was going to waste. --cf-cap-top is measured
     from the scene when it opens, because the frame's height depends on the
     viewport and a guess would be wrong on every device but one. */
  .cf-player.is-zoomed .cf-cap {
    /* z-index 2002: above the backdrop at 2000 and the picture at 2001.
       Without it the caption was positioned perfectly and painted behind a
       full-screen sheet -- measurably on screen, and invisible. */
    position: fixed; z-index: 2002; left: 50%; transform: translateX(-50%);
    top: var(--cf-cap-top, 62%); bottom: auto;
    width: min(92vw, 900px); padding: 0;
    font-size: 1rem; line-height: 1.6; text-align: center; }

  /* On a phone the frame is about 200px tall, so a caption is competing
     with the drawing for the same space rather than sitting under it. It
     gets smaller, tighter and lower here -- and it is off unless asked for
     in the first place. The count goes: the scrubber already says where you
     are, and six controls on a 390px bar is a row of thumbnails. */
  @media (max-width: 560px) {
    .cf-player { max-width: 100%; }
    .cf-cap { font-size: .72rem; line-height: 1.5; bottom: 44px;
              padding: 0 .5rem; }
    .cf-cap span { padding: .14em .38em; }
    .cf-count { display: none; }
    /* Clear of the feedback star.
       .fb-btn is fixed at right:14px, top:50% -- so on a phone it floats in
       the same column as the last control in this bar, and hit-testing
       showed it covering Expand completely. The button was there, styled and
       enabled, and a tap went to the star instead. Extra right padding moves
       the controls out from under it rather than moving a site-wide control
       for one page. */
    .cf-bar { gap: .4rem; padding: .4rem .5rem .45rem; }
    .cf-icon { width: 24px; height: 24px; }
  }


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
