#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The walkthrough player for /how-this-was-made/.

Asked for: "just show something like a YouTube video -- pause, a scrolling
option, start again, and an expand symbol in the corner of the video. As soon
as we play it has to narrate by default; a user can mute it. Don't overkill
it."

So the controls are the ones a reader already knows, in the order they expect,
directly under the picture: play/pause, a seek bar, a position count, mute,
replay -- and expand as an icon on the picture itself.

What was taken out, and why:

    the list of eight steps   Its words ARE the subtitles now. The same
                              sentences printed twice, once as a list and once
                              as a caption, is one thought in two places -- and
                              the architecture diagram below is the map, so
                              nothing is lost by dropping the list.
    previous / next buttons   A seek bar says where you are and where you can
                              go. Two step buttons say neither.
    "Play with narration"     The voice is the point, so it is simply on when
                              you press play. Mute is where anyone looks to
                              stop a sound.
    the "Expand" text button  A corner icon, the way video players have done
                              it for fifteen years.

The voice drives the timing: a scene lasts exactly as long as its sentence
takes to say, so the picture and the words cannot drift apart. Muted, or on a
device with no speech at all, a timer takes over at a readable pace -- the
subtitles are the whole content then, so they are given time to be read.
"""

PLAYER_JS = """
<script>
(function () {
  var stage = document.querySelector('[data-stage]');
  if (!stage) return;
  var scenes  = [].slice.call(stage.querySelectorAll('.sc'));
  var capEl   = stage.querySelector('[data-caption]');
  var playBt  = stage.querySelector('[data-journey-play]');
  var seek    = stage.querySelector('[data-seek]');
  var countEl = stage.querySelector('[data-count]');
  var muteBt  = stage.querySelector('[data-journey-mute]');
  var againBt = stage.querySelector('[data-journey-replay]');
  var zoomBt  = stage.querySelector('[data-journey-zoom]');
  var ccBt    = stage.querySelector('[data-journey-cc]');
  var ICON = {};
  try {
    var ib = document.querySelector('[data-icons]');
    if (ib) ICON = JSON.parse(ib.textContent);
  } catch (e) { ICON = {}; }
  var bigBt   = stage.querySelector('[data-journey-big]');
  if (!scenes.length) return;

  var script = [];
  try {
    var raw = document.querySelector('[data-narration]');
    if (raw) script = JSON.parse(raw.textContent);
  } catch (e) { script = []; }

  var synth = window.speechSynthesis;
  var canSpeak = !!(synth && window.SpeechSynthesisUtterance && script.length);
  var still = window.matchMedia &&
              window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  var at = 0, playing = false, muted = false, timer = null, bed = null;
  var zoomed = false, backdrop = null, resumeAudio = false;
  var READ_MS = 5200;

  try { muted = localStorage.getItem('jk-mute') === '1'; } catch (e) {}
  // Subtitles carry the whole script, so they are on unless a reader has
  // said otherwise. Only an explicit '0' turns them off -- an empty value
  // means they have never touched it.
  // Subtitles OFF unless asked for.
  //
  // They were on by default and, on a phone, three lines of caption covered
  // the entire drawing -- the picture was a background for a wall of text.
  // "Subtitles has to be optional, users have to click subtitles if needed."
  // Correct: a caption over a 16:9 frame on a 390px screen is most of the
  // frame, and nobody asked for it.
  var cc = false;
  try { cc = localStorage.getItem('jk-cc') === '1'; } catch (e) {}

  function paint() {
    scenes.forEach(function (g, n) { g.classList.toggle('is-on', n === at); });
    // Wrapped in a span so the dark box hugs the words rather than drawing
    // a full-width bar across the picture on a short line.
    if (capEl) {
      var line = cc ? (script[at] || '') : '';
      capEl.innerHTML = line ? '<span>' + line.replace(/&/g, '&amp;')
                                             .replace(/</g, '&lt;') + '</span>'
                             : '';
    }
    if (seek && String(seek.value) !== String(at)) { seek.value = at; }
    if (seek) {
      var pct = scenes.length < 2 ? 0 : (at / (scenes.length - 1)) * 100;
      seek.style.setProperty('--cf-pct', pct + '%');
    }
    if (countEl) countEl.textContent = (at + 1) + ' / ' + scenes.length;
  }

  function setPlayIcon() {
    if (!playBt) return;
    playBt.innerHTML = playing ? (ICON.pause || '') : (ICON.play || '');
    playBt.setAttribute('aria-label', playing ? 'Pause' : 'Play');
  }

  function bedOn(on) {
    if (on && !muted) {
      if (!bed) {
        // mountains-1: bansuri flute over a tarana rhythm.
        //
        // The first bed was sunset-1, a soft clavier piece, and the note was
        // "I want something more creative, funny, festive instead of soft
        // music." This one has a rhythm section and a melody going somewhere,
        // it matches the instruments the music button already rotates through
        // -- tabla, nadaswaram, harmonium -- and at 150 seconds against a
        // ~75 second narration a single pass never reaches the loop point,
        // so it never audibly restarts.
        //
        // Already in the repository and already credited: no new file, no new
        // licence, nothing extra to download beyond this one.
        bed = new Audio('/blog/assets/audio/mountains-1.mp3');
        bed.loop = true;
        bed.volume = 0.14;
      }
      var b = bed.play();
      if (b && b.catch) { b.catch(function () {}); }
    } else if (bed) {
      try { bed.pause(); } catch (e) {}
    }
  }

  function siteAudio(quiet) {
    var a = document.getElementById('beach-audio');
    if (!a) return;
    if (quiet) {
      resumeAudio = !a.paused;
      if (resumeAudio) { a.pause(); }
    } else if (resumeAudio) {
      resumeAudio = false;
      var t = a.play();
      if (t && t.catch) { t.catch(function () {}); }
    }
  }

  function clearTimer() {
    if (timer) { window.clearTimeout(timer); timer = null; }
  }

  function pickVoice() {
    var vs = (synth && synth.getVoices()) || [];
    var want = ['aria', 'jenny', 'michelle', 'ava',
                'google us english', 'google uk english female',
                'samantha', 'siri', 'karen', 'moira', 'tessa', 'fiona',
                'serena', 'sonia', 'libby', 'female', 'zira'];
    var en = vs.filter(function (v) { return /^en/i.test(v.lang || ''); });
    for (var i = 0; i < want.length; i++) {
      for (var j = 0; j < en.length; j++) {
        if ((en[j].name || '').toLowerCase().indexOf(want[i]) !== -1) {
          return en[j];
        }
      }
    }
    for (var k = 0; k < en.length; k++) {
      if (en[k].localService === false) { return en[k]; }
    }
    return en[0] || null;
  }
  if (synth && synth.onvoiceschanged !== undefined) {
    synth.onvoiceschanged = function () { pickVoice(); };
  }

  function speakCurrent() {
    if (!canSpeak || muted) { return false; }
    var u = new SpeechSynthesisUtterance(script[at]);
    try {
      var v = pickVoice();
      if (v) { u.voice = v; u.lang = v.lang || 'en-US'; }
    } catch (e) {}
    u.rate = 0.92;
    u.pitch = 1.04;
    u.onend = function () {
      if (!playing) return;
      window.setTimeout(advance, 420);
    };
    u.onerror = function () {
      if (!playing) return;
      clearTimer();
      timer = window.setTimeout(advance, READ_MS);
    };
    try { synth.cancel(); synth.speak(u); } catch (e) { return false; }
    return true;
  }

  function advance() {
    if (!playing) return;
    if (at >= scenes.length - 1) { stop(); return; }
    at += 1;
    paint();
    run();
  }

  function run() {
    clearTimer();
    if (!speakCurrent()) { timer = window.setTimeout(advance, READ_MS); }
  }

  function play() {
    if (playing) return;
    playing = true;
    // is-started stays on once pressed: it is what reveals the subtitle and
    // retires the big centre button. is-playing is what lets the drawing
    // animate, so a page nobody has pressed play on holds perfectly still.
    stage.classList.add('is-started', 'is-playing');
    setPlayIcon();
    siteAudio(true);
    bedOn(true);
    run();
  }

  function stop() {
    playing = false;
    stage.classList.remove('is-playing');
    setPlayIcon();
    clearTimer();
    try { if (synth) synth.cancel(); } catch (e) {}
    bedOn(false);
    siteAudio(false);
  }

  if (playBt) {
    playBt.addEventListener('click', function () {
      if (playing) { stop(); } else { play(); }
    });
  }
  if (bigBt) {
    bigBt.addEventListener('click', function () { play(); });
  }

  // Dragging moves the picture WHILE dragging, so it behaves like a scrubber
  // rather than like a form control you submit.
  if (seek) {
    seek.addEventListener('input', function () {
      var v = parseInt(seek.value, 10) || 0;
      at = Math.max(0, Math.min(scenes.length - 1, v));
      paint();
      if (playing) { run(); }
    });
  }

  function paintMute() {
    if (!muteBt) return;
    muteBt.innerHTML = muted ? (ICON.muted || '') : (ICON.sound || '');
    muteBt.setAttribute('aria-pressed', String(muted));
    muteBt.setAttribute('aria-label', muted ? 'Unmute' : 'Mute');
  }
  if (muteBt) {
    paintMute();
    muteBt.addEventListener('click', function () {
      muted = !muted;
      try { localStorage.setItem('jk-mute', muted ? '1' : '0'); } catch (e) {}
      paintMute();
      if (muted) {
        try { if (synth) synth.cancel(); } catch (e) {}
        bedOn(false);
        if (playing) {
          clearTimer();
          timer = window.setTimeout(advance, READ_MS);
        }
      } else if (playing) {
        bedOn(true);
        run();
      }
    });
  }

  function paintCC() {
    if (!ccBt) return;
    ccBt.setAttribute('aria-pressed', String(cc));
    ccBt.setAttribute('aria-label',
      cc ? 'Turn subtitles off' : 'Turn subtitles on');
  }
  if (ccBt) {
    paintCC();
    ccBt.addEventListener('click', function () {
      cc = !cc;
      try { localStorage.setItem('jk-cc', cc ? '1' : '0'); } catch (e) {}
      paintCC();
      paint();
    });
  }

  if (againBt) {
    againBt.addEventListener('click', function () {
      at = 0;
      paint();
      if (playing) { run(); } else { play(); }
    });
  }

  function zoom(on) {
    zoomed = on;
    if (on) {
      // Hold the height while the picture leaves the flow, so the paragraphs
      // below do not jump up and then back down again.
      stage.style.minHeight = stage.getBoundingClientRect().height + 'px';
      backdrop = document.createElement('div');
      backdrop.className = 'cf-backdrop';
      backdrop.addEventListener('click', function () { zoom(false); });
      document.body.appendChild(backdrop);
      document.body.classList.add('cf-zoomed');
      stage.classList.add('is-zoomed');
    } else {
      stage.classList.remove('is-zoomed');
      document.body.classList.remove('cf-zoomed');
      if (backdrop) { backdrop.remove(); backdrop = null; }
      stage.style.minHeight = '';
    }
    if (zoomBt) {
      zoomBt.innerHTML = on ? (ICON.shrink || '') : (ICON.expand || '');
      zoomBt.setAttribute('aria-label', on ? 'Minimise' : 'Expand');
    }
  }
  if (zoomBt) {
    zoomBt.addEventListener('click', function () { zoom(!zoomed); });
  }
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && zoomed) { zoom(false); }
  });

  // Nothing starts on its own. A page that begins talking because it scrolled
  // into view is the rudest thing on the internet.
  paint();
  setPlayIcon();
  // prefers-reduced-motion: the scenes never animate (the CSS stops every
  // keyframe), the subtitles still carry the whole script, and the reader
  // steps through with the bar. Nothing is lost and nothing moves.
  if (still && capEl) { capEl.style.opacity = '1'; }

  document.addEventListener('visibilitychange', function () {
    if (document.hidden && playing) { stop(); }
  });
  window.addEventListener('pagehide', function () { stop(); });
})();
</script>
"""
