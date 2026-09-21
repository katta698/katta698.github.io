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

  /* The drawing stops where the controls start.
     Reported with a screenshot: the "Intelligence" box in scene 7 sitting
     behind the CC and mute buttons. It was not one label and not one scene
     -- the artwork filled the whole frame and the bar is an overlay across
     the bottom of it, so on EVERY scene the lowest band of the picture was
     underneath the controls. Measured against the bar's own rectangle:

         412px   37px of artwork covered
         390px   37px
        1180px   39px, including the words "one file, by hand"

     YouTube gets away with an overlay because its bar fades out. This one
     is always there, so the picture gets the space above it and nothing
     else. preserveAspectRatio="xMidYMid meet" does the rest: the art scales
     down and stays centred rather than being cropped.

     The height is stated, not left to `bottom`. An <svg> is a REPLACED
     element: with height:auto it takes its own intrinsic ratio from the
     viewBox and `bottom` is ignored as over-constrained. Measured after
     trying exactly that -- computed bottom 40px, and the box still ran the
     full 208px to the floor of the frame, 370 x 180/320 to the pixel. So
     the height says what it means. */
  .cf-player .cf-scene { --cf-bar-h: 44px; --cf-cap-h: 0px; }
  /* 58px, not 46: a two-line caption at .92rem/1.7 plus its own padding
     is 56px, and 46 left scene 1 with 9px of the horizon drawn under it.
     Measured rather than guessed, with subtitles on AND off, because with
     them off this reserve is zero and the drawing takes the whole frame. */
  .cf-player.cc-on .cf-scene { --cf-cap-h: 58px; }
  .cf-player .cf-scene > svg {
    height: calc(100% - var(--cf-bar-h) - var(--cf-cap-h)); }

  .sc { opacity: 0; transition: opacity .45s ease; }
  .sc.is-on { opacity: 1; }
  /* Paused unless on screen and current. */
  .sc * { animation-play-state: paused; }
  .sc.is-on * { animation-play-state: running; }

  .cf-scene svg { color: var(--tx, var(--text, #EDEBE6)); }
  /* ...but not the icons in the control bar.
     That rule sets a colour on EVERY svg inside the frame, and the bar sits
     inside the frame, so the control icons -- which are stroke="currentColor"
     -- resolved their colour against the SCENE's ink rather than their own
     button's. Measured in light mode: the button computed to #3B3733 as
     asked, and its glyph still drew at #2C2A29. Two rules disagreeing about
     one icon, with the louder one winning by accident of nesting. */
  .cf-bar svg { color: inherit; }
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
  /* Hovering a box says what that component does. The sentence for a
     script is its own docstring, so the two cannot drift apart.

     Hover alone would leave out every phone, every keyboard and every
     screen reader, so the boxes are focusable, the panel is a live region,
     and the same sentences are listed in full underneath. */
  .cf-arch { position: relative; }
  .cf-tip { position: absolute; z-index: 4; max-width: 340px;
            padding: 9px 12px; border-radius: 8px;
            background: var(--card, #23211F);
            border: 1px solid var(--line, rgba(255,255,255,.14));
            box-shadow: 0 10px 28px rgba(0,0,0,.38);
            font-size: .82rem; line-height: 1.45;
            color: var(--text, #E8E6E1); pointer-events: none; }
  .cf-arch-svg [data-note] { cursor: help; }
  .cf-arch-svg [data-note]:hover rect,
  .cf-arch-svg [data-note]:focus-visible rect {
      stroke-width: 2; opacity: 1; }
  .cf-arch-svg [data-note]:focus { outline: none; }
  .cf-arch-svg [data-note]:focus-visible rect {
      stroke: var(--acc, #C4A484); }

  .cf-parts { margin: 14px 0 6px; }
  .cf-parts summary { cursor: pointer; font-size: .86rem;
                      color: var(--mut, var(--text-muted, #9C9A94));
                      letter-spacing: .02em; }
  .cf-parts dl { margin: 12px 0 0; display: grid; gap: 10px 18px;
                 grid-template-columns: minmax(9rem, 13rem) 1fr; }
  .cf-parts dt { font-family: 'DM Mono', ui-monospace, monospace;
                 font-size: .8rem; color: var(--acc-ink, var(--acc, #C4A484));
                 overflow-wrap: anywhere; }
  .cf-parts dd { margin: 0; font-size: .86rem; line-height: 1.5;
                 color: var(--mut, var(--text-muted, #9C9A94)); }
  @media (max-width: 640px) {
      /* Two columns at 9rem leaves the description four words a line. */
      .cf-parts dl { grid-template-columns: 1fr; gap: 3px; }
      .cf-parts dd { margin: 0 0 10px; }
      .cf-tip { max-width: calc(100vw - 48px); }
  }

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

  /* Pause has to stop the PICTURE, not just the sound.
     Reported as: "I paused the video, the sound stops, but the video still
     continues at the back end."

     Exactly right, and it was a specificity defeat. The rule further up --
     `.sc.is-on *` -- says `running` with no condition attached, and it is
     two classes. The gated rule above it is `.cf-player.is-playing .sc.is-on
     *`, which only ever ADDS running; nothing said paused with enough weight
     to win when is-playing went away. So the scrim went quiet and the
     drawing carried on animating underneath it.

     Four classes, so it beats the ungated rule, and it says the thing that
     actually needs saying: not playing means not moving. */
  .cf-player:not(.is-playing) .sc.is-on * { animation-play-state: paused; }

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
  /* Hidden while PLAYING, not once started.
     It used to hide itself permanently on the first press, which left the
     picture with no visible state at all: paused and playing looked the
     same. Now the big symbol in the middle means paused, whether that is
     before the first press or halfway through -- which also answers "as
     soon as I refresh it shows the play button in the centre, is that
     deliberate?" It is: it is the poster state, and it is the press that
     lets a phone play sound at all. */
  .cf-player.is-playing .cf-big { opacity: 0; pointer-events: none; }
  /* The frame is a control. */
  .cf-player .cf-scene { cursor: pointer; }
  .cf-player .cf-bar { cursor: default; }

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
  /* z-index 3, inside the player -- not 901, which outranked the site.
     Reported as: "when I scroll down and the video goes up, I see this" --
     the control bar painting on top of the sticky header, over the logo and
     PORTFOLIO. Measured:

         nav          position: sticky    z-index 100
         control bar  position: absolute  z-index 901

     901 was chosen to beat the feedback star at 900, which was covering the
     Expand button. That fixed one overlap by starting a bigger one: a page
     control has no business outranking the site's own chrome.

     The star is moved on this page instead, below, so the bar does not need
     to outrank anything. */
  .cf-bar { position: absolute; left: 0; right: 0; bottom: 0; z-index: 3;
            display: flex; align-items: center; gap: .55rem;
            max-width: 100%; box-sizing: border-box;
            padding: .5rem .7rem .55rem;
            background: linear-gradient(to top,
              rgba(0,0,0,.72), rgba(0,0,0,.42) 60%, rgba(0,0,0,0));
            border-radius: 0 0 11px 11px; }
  /* The scrim follows the theme.
     Sent a light-mode screenshot: a black band across the bottom of a pale
     card, with the icons -- which take their colour from the page text, so
     dark in light mode -- sitting on top of it. Dark on dark. The scrim was
     hard-coded rgba(0,0,0,.72) and had never been looked at outside the
     dark theme it was designed in. */
  /* The total stays; it is the half that answers "when does this end".
     It folds away only under 380px, where the row genuinely runs out.

     OLD NOTE, kept because the measurement is the point: 
     "I have a hard time scrolling it forward and rewind." Measured, that
     is precision rather than smoothness: on a phone the bar is ~116px for a
     123-second track, so ONE PIXEL of finger travel is a whole second, and
     a fingertip covers about thirty of them. The elapsed time answers
     "where am I"; the total is printed twice over anyway, once here and
     once at the end of the bar itself. Giving its 39px to the scrubber is
     the cheapest width on the row -- but it was the wrong 39px to take.
     The slash's two spaces gave back 16 of them for nothing. */
  .cf-time .cf-of { margin-left: .1em; }
  @media (max-width: 380px) { .cf-time .cf-of { display: none; } }

  body.light .cf-bar {
    background: linear-gradient(to top,
      rgba(247,244,239,.94), rgba(247,244,239,.72) 60%, rgba(247,244,239,0)); }
  /* And the groove the thumb runs in. rgba(237,235,230,.30) is a pale line
     for a dark frame; on a light one it is the same colour as the frame, so
     the bar looked like it stopped at the thumb and there was nothing left
     to drag along.

     Two rules, not one selector list: a browser drops an ENTIRE rule if any
     selector in the list is one it does not recognise, and ::-moz-range-track
     is unknown to Chrome. Listed together, the light track silently did
     nothing -- which is exactly what the first attempt did. */
  /* One tan for the filled controls, in BOTH themes.
     Asked as: "are these colours OK in light mode? Isn't it too dark."

     They were, and the cause was an inversion rather than a bug. Everything
     stayed legible -- the glyph never dropped below 6.5:1 -- but the
     RELATIONSHIP flipped. Measured off the rendered pixels:

         dark    plate #C4A484 on bar #121211   8.02:1   plate LIGHTER
         light   plate #6E5236 on bar #F6F4EF   6.54:1   plate DARKER

     In dark mode the primary control is a soft highlight; in light mode it
     became the heaviest, darkest object on a pale card. `--acc-ink` is
     #6E5236 in light mode because it is tuned for SMALL TEXT on pale, where
     4.5:1 is the floor -- and a colour chosen to be legible at 12px is far
     too much weight as a 28px filled disc.

     So the light theme borrows the dark theme's plate. The same tan, the
     same dark glyph, in both:

         plate on bar   2.13:1   present as a tinted chip, not a black disc
         ink on plate   5.05:1   comfortably above the 4.5:1 floor

     And the outline icons come down from #2C2A29 to the page's own text
     colour. At 12.88:1 they were darker than the prose around them, which
     is backwards for a control that should sit quietly until wanted. */
  body.light .cf-player { --cf-chip: #C4A484; }
  body.light .cf-play { background: var(--cf-chip); color: #1F1D1B; }
  body.light .cf-cc[aria-pressed="true"] { background: var(--cf-chip);
                                           border-color: var(--cf-chip);
                                           color: #1F1D1B; }
  body.light .cf-icon { color: #3B3733; border-color: rgba(59,55,51,.30); }
  body.light .cf-icon:hover { color: #6E5236; border-color: #6E5236; }

  body.light .cf-player .cf-scene { --cf-notch: #F2EFE9; }
  body.light .cf-seek::-webkit-slider-runnable-track {
    background-image: var(--cf-ticks, none),
      linear-gradient(to right,
        var(--cf-chip, #C4A484) 0 var(--cf-pct, 0%),
        rgba(31,29,27,.20) var(--cf-pct, 0%) 100%); }
  body.light .cf-seek::-webkit-slider-thumb { background: var(--cf-chip); }
  body.light .cf-seek::-moz-range-thumb { background: var(--cf-chip); }
  body.light .cf-seek::-moz-range-track {
    background-image: var(--cf-ticks, none),
      linear-gradient(to right,
        var(--cf-chip, #C4A484) 0 var(--cf-pct, 0%),
        rgba(31,29,27,.20) var(--cf-pct, 0%) 100%); }
  .cf-play { width: 28px; height: 28px; flex: 0 0 auto; cursor: pointer;
             display: grid; place-items: center; font-size: .72rem;
             border-radius: 50%; border: none; color: #1F1D1B;
             background: var(--acc-ink, #C4A484); }
  /* padding: 0 is load-bearing.
     Reported as: "the mute icon and the CC icon are not in the middle of
     that box, they are kind of towards the right."

     Measured, and it was 4px: the glyph sat 7px from the left edge and 3px
     from the right. The buttons inherit `padding: 1px 6px`, and at 24px
     border-box that leaves a content box 10px wide for a 14px icon. A grid
     item WIDER than its track is not centred -- the browser falls back to
     start alignment, on purpose, so that overflow cuts off the end rather
     than both sides. So place-items:center was being quietly ignored, and
     only on the small buttons: .cf-play is 28px, which leaves exactly 14,
     and it was perfectly centred. */
  .cf-icon { width: 26px; height: 26px; flex: 0 0 auto; cursor: pointer;
             display: grid; place-items: center; font-size: .76rem;
             padding: 0;
             border-radius: 6px; background: transparent; color: #EDEBE6;
             border: 1px solid rgba(237,235,230,.28); }
  .cf-icon:hover { border-color: var(--acc-ink, #C4A484);
                   color: var(--acc-ink, #C4A484); }
  .cf-time { font-family: 'DM Mono', ui-monospace, monospace;
             font-size: .66rem; flex: 0 0 auto; color: #D8D4CC;
             font-variant-numeric: tabular-nums; letter-spacing: -.01em; }
  body.light .cf-time { color: #3B3733; }
  .cf-time .cf-of { opacity: .62; }

  /* The chapter you are in, named. Hidden on a phone, where the row has
     about 116px for the scrub bar and a title would take most of it -- the
     notches still show the shape of the journey there, and the caption is
     already saying what this part is about. */
  /* The chapter name only where there is room for it, which is expanded.
     The frame is capped at 30rem, and that row already carries the play
     button, the scrub bar, a clock and four icons. Giving a title a fixed
     9.5rem of it left the scrub bar 38 PIXELS wide -- measured, after the
     variable-width version had been rejected for resizing the bar under the
     thumb. A control that has to shrink the main control to fit does not
     belong in that row.
     Expanded, the frame is the window, and the name earns its place. The
     notches carry the same information everywhere else: eight marks, so
     eight parts, and the caption is already naming what this one is. */
  .cf-chap { display: none; font-size: .68rem; letter-spacing: .04em;
             color: #D8D4CC; opacity: .8;
             flex: 0 0 11rem; width: 11rem; text-align: right;
             white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  body.light .cf-chap { color: #3B3733; }
  /* ...and only when the bar is genuinely wide.
     "Expanded" was taken as proof there was room, and on a phone expanded
     is still 94vw: the 11rem label took 176px of a 385px bar and left the
     SCRUB BAR 0 PIXELS WIDE, with the expand button pushed to x=406 on a
     412px screen. The label is worth having on a laptop and never worth
     the scrubber. */
  @media (min-width: 700px) {
    .cf-player.is-zoomed .cf-chap { display: block; }
  }
  /* CC reads as a label, not a glyph, so it is wider and set in mono --
     and the OFF state has to be visibly off at a glance, which a pressed
     state alone is not. */
  /* text-indent cancels the tracking's trailing space.
     letter-spacing puts a gap after EVERY letter including the last, so the
     ink sits half a pixel left of centre in a box that is otherwise exact.
     Indenting by the same amount puts it back. */
  .cf-cc { width: auto; padding: 0 .42rem;
           font-family: 'DM Mono', ui-monospace, monospace;
           font-size: .62rem; letter-spacing: .06em;
           text-indent: .06em; }
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
  /* The element is 22px tall; the LINE inside it is 4px.
     Reported as: "I can't forward it, I really can't do anything."
     The bar was 4px tall and that 4px was the whole hit area -- a range
     input only accepts a pointer inside its own box, so the 12px thumb
     drawn overflowing it was decoration. Measured: a real drag at 390px
     landed, a real drag at 1180px missed by two pixels and the video sat
     there. A finger is about 9mm; it was being asked for 4 device pixels.
     So the box grows to 22px (Apple's minimum is 44 for a button, and this
     is a drag, not a tap) and the visible 4px line moves to the TRACK
     pseudo-element, which is paint only and has no bearing on hit testing.
     Nothing about the look changes. Everything about grabbing it does. */
  /* min-width 72px, not 0. 0 let the bar solve its overflow by deleting
     the main control -- measured at 0px wide and 14px wide in the two
     expanded layouts. Anything that has to shrink now shrinks around it. */
  /* touch-action: pan-y is why a finger can drag this at all.
     Reported as: "to forward I have to click instead of scroll -- can't it
     be seamless." It could not: at the default `auto` the browser claims a
     horizontal drag that starts on the slider for panning the page, so the
     control never receives the gesture. Measured on the same path:

         mouse drag   22000 -> 121200   tracks the pointer
         touch drag   ends at 2200      never moved at all

     pan-y rather than none, so a finger that starts on the bar and moves
     DOWN still scrolls the page -- the bar spans most of the frame's width
     and swallowing every vertical swipe that begins on it would trade one
     stuck gesture for another. */
  .cf-seek { flex: 1 1 auto; min-width: 72px; -webkit-appearance: none;
             touch-action: pan-y;
             appearance: none; height: 22px; cursor: pointer; margin: 0;
             background: transparent; }
  /* Two layers: the chapter notches on top, the progress underneath.
     The notch colour is the bar's own background, so a mark reads as a gap
     cut through the track -- equally visible on the played side, which is
     the accent, and the unplayed side, which is grey. A line drawn ON the
     track needs one colour that contrasts with both, and there isn't one. */
  .cf-player .cf-scene { --cf-notch: #1A1817; }
  .cf-seek::-webkit-slider-runnable-track {
             height: 4px; border-radius: 4px;
             background-image: var(--cf-ticks, none),
               linear-gradient(to right,
                 var(--acc-ink, #C4A484) 0 var(--cf-pct, 0%),
                 rgba(237,235,230,.30) var(--cf-pct, 0%) 100%); }
  .cf-seek::-moz-range-track {
             height: 4px; border-radius: 4px;
             background-image: var(--cf-ticks, none),
               linear-gradient(to right,
                 var(--acc-ink, #C4A484) 0 var(--cf-pct, 0%),
                 rgba(237,235,230,.30) var(--cf-pct, 0%) 100%); }
  .cf-seek::-webkit-slider-thumb { -webkit-appearance: none; appearance: none;
             width: 12px; height: 12px; border-radius: 50%; border: none;
             margin-top: -4px;  /* centre the thumb on the 4px track */
             background: var(--acc-ink, #C4A484); }
  .cf-seek::-moz-range-thumb { width: 12px; height: 12px; border: none;
             border-radius: 50%; background: var(--acc-ink, #C4A484); }
  .cf-seek:focus-visible { outline: 2px solid var(--acc-ink, #C4A484);
                           outline-offset: 3px; }

  /* A bigger grip where there are fingers rather than a pointer.
     22px of height and a 12px thumb are comfortable under a mouse and mean
     and fiddly under a thumb -- and this control is dragged, not clicked,
     so it has to be held for the length of the gesture. pointer: coarse
     asks the device rather than guessing from width: a phone gets this, a
     laptop with a narrow window does not. */
  @media (pointer: coarse) {
    .cf-seek { height: 30px; }
    .cf-seek::-webkit-slider-thumb { width: 17px; height: 17px;
                                     margin-top: -6.5px; }
    .cf-seek::-moz-range-thumb { width: 17px; height: 17px; }
  }

  body.cf-zoomed { overflow: hidden; }
  .cf-backdrop { position: fixed; inset: 0; z-index: 2000;
                 background: var(--bg, var(--surface, #1F1D1B)); }
  /* max-width: none is the whole fix.
     Reported as: "something is wrong with the expand tool -- when I expand
     I see this, and it doesn't make any sense."

     Expanding set a width of min(94vw, 1180px) and the base rule's
     `max-width: 30rem` quietly capped it at 480px, so the frame came out
     the size it already was. Measured while expanded:

         desktop   frame 480x270   -- identical to unexpanded
         phone     frame 387x218   -- 94vw, so no gain either

     A width that loses to a max-width is not a bug you can see in the
     stylesheet; it looks exactly like a rule that is working. */
  .cf-player.is-zoomed .cf-scene {
    position: fixed; z-index: 2001; left: 50%; top: 50%;
    transform: translate(-50%, -50%);
    max-width: none;
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
  /* Expanded: the caption STAYS on the picture, at the bottom, the way a
     video player does it. It was moved underneath for a while, which put it
     in the middle of empty black and looked like a separate paragraph. Two
     short lines over the foot of the frame is what a subtitle is. */
  .cf-player.is-zoomed .cf-cap-unused {
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
    /* The clock stays on a phone -- it is the answer to "how long has
       this been running and when does it end". Only the total folds away,
       and only under 380px, where the row genuinely runs out of room. */
    .cf-time { font-size: .6rem; }
    /* Clear of the feedback star.
       .fb-btn is fixed at right:14px, top:50% -- so on a phone it floats in
       the same column as the last control in this bar, and hit-testing
       showed it covering Expand completely. The button was there, styled and
       enabled, and a tap went to the star instead. Extra right padding moves
       the controls out from under it rather than moving a site-wide control
       for one page. */
    /* Tighter gaps and edges on a phone, because every pixel taken from
       the row's whitespace is a pixel the scrub bar gets, and the scrub bar
       is the control that was hard to use. The icons keep their size --
       they are already at 24px, which is below Apple's 44px guidance, and
       shrinking a tap target to widen a drag target trades one complaint
       for another. */
    .cf-bar { gap: .3rem; padding: .4rem .4rem .45rem; }
    .cf-player .cf-scene { --cf-bar-h: 48px; }
    .cf-player.cc-on .cf-scene { --cf-cap-h: 40px; }
    .cf-icon { width: 24px; height: 24px; }
    /* CC is a LABEL and has to keep sizing itself.
       This query sets every .cf-icon to a fixed 24px, and CC is one -- so it
       lost its width:auto and became a 24px box holding 13.1px of text
       inside 13.4px of its own padding. Overflowing, and therefore
       start-aligned: measured 7.7px of space on the left and 3.2 on the
       right, while the same button on a laptop, where it is 29px and fits,
       was a perfect 7.7/7.7. Asked as "is CC alignment right?" -- it was
       not, and only on phones. */
    .cf-cc { width: auto; min-width: 24px; padding: 0 .3rem; }
  }


  /* Asked for less movement: every scene sits in its finished state. */
  @media (prefers-reduced-motion: reduce) {
    .sc *, .sc.is-on * { animation: none !important; }
    .sc .l1, .sc .l2, .sc .l3, .sc .l4, .sc .ans, .sc .cite, .sc .pull,
    .sc .ray, .sc .tk { stroke-dashoffset: 0; }
    .sc .out, .sc .chk { opacity: .85; }
    .sc .steam { opacity: .5; }
  }

  /* The feedback star, out of the control bar's column -- on this page only.
     It is fixed at right:14px, top:50%, so on a phone it floats exactly
     where the player's last button sits, which is why the bar was given
     z-index 901 in the first place. Moving it is page-scoped through
     :has(), so no other page's star moves and no site-wide z-index has to
     be raised to accommodate one page. */
  body:has(.cf-player) .fb-btn { top: 72%; }

  /* The trip, stop by stop.
     A numbered strip rather than a second diagram: the picture above says
     what connects to what, and this says what each step costs and who does
     it. Hand steps carry the accent; machine steps stay in the page's own
     ink, so the eye can see at a glance how little of this is hand work --
     three stops of eight, and one of those is pressing commit. */
  .cf-trip { list-style: none; margin: 1rem 0 .4rem; padding: 0;
             counter-reset: none; }
  .cf-stop { display: grid; grid-template-columns: 2rem 4.4rem 1fr;
             gap: .7rem; align-items: start; padding: .7rem 0;
             border-top: 1px solid var(--bd, var(--border, #33302C)); }
  .cf-stop:last-child { border-bottom: 1px solid
                        var(--bd, var(--border, #33302C)); }
  .cf-num { font-family: 'DM Mono', ui-monospace, monospace; font-size: .8rem;
            opacity: .5; padding-top: .15rem; }
  .cf-by { font-family: 'DM Mono', ui-monospace, monospace; font-size: .62rem;
           letter-spacing: .08em; text-transform: uppercase;
           padding-top: .25rem; }
  .cf-hand .cf-by { color: var(--acc-ink, var(--accent, #C4A484)); }
  .cf-machine .cf-by { opacity: .45; }
  .cf-what b { display: block; font-size: .98rem; }
  .cf-what code { display: block; font-size: .76rem; opacity: .8;
                  margin: .1rem 0 .15rem; word-break: break-word; }
  .cf-why { display: block; font-size: .82rem; line-height: 1.55;
            opacity: .72; }
  /* A stop that does not apply is dimmed, not deleted: the shape of the
     journey is the same and the reader can see what is being skipped. */
  /* Four panels, one shown. The greying is gone: a path that has steps
     the others do not cannot be drawn by dimming a shared list. */
  .cf-trip[hidden] { display: none; }
  .cf-path-n { display: block; font-size: .64rem; opacity: .6;
               letter-spacing: .04em; }
  .cf-path[aria-selected="true"] { background: var(--accent, #C4A484);
                                   border-color: var(--accent, #C4A484);
                                   color: #1F1D1B; }
  .cf-path[aria-selected="true"] .cf-path-n { opacity: .75; }
  .cf-trip-paths { display: flex; flex-wrap: wrap; gap: .4rem;
                   margin: .8rem 0 .2rem; }
  .cf-path { border: 1px solid var(--bd, var(--border, #33302C));
             background: transparent; color: inherit; border-radius: 999px;
             padding: .3rem .8rem; font: inherit; font-size: .78rem;
             cursor: pointer; }
  /* On a phone the number and the HAND/MACHINE label share one meta line
     and the rest sits under them.
     The first version gave each of the three its own grid cell, which on a
     narrow screen meant the title landed two rows below its own number with
     a hole beside it -- airy, disconnected, and taller than the content. */
  @media (max-width: 560px) {
    .cf-stop { grid-template-columns: auto 1fr; gap: .35rem .5rem;
               padding: .65rem 0; }
    .cf-num { grid-column: 1; grid-row: 1; padding-top: 0; }
    .cf-by { grid-column: 2; grid-row: 1; padding-top: .1rem; }
    .cf-what { grid-column: 1 / -1; grid-row: 2; }
    .cf-what b { font-size: .94rem; }
  }

  @media (max-width: 560px) {
    .cf-scene { max-width: 100%; }
  }
"""
