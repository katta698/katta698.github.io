#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The walkthrough player for /how-this-was-made/.

It plays eight pre-rendered MP3s and keeps the picture and the subtitle in
step with them.

The voice used to come from the browser's speechSynthesis, and after three
rounds of picking better voices the verdict was still: "it's like a machine
reading, a robot reading, it's not natural at all." That was correct, and not
fixable from here -- on a phone that API is a 2010-era synthesiser, and
choosing between its voices only chooses between robots. The narration is
rendered once by build_narration_audio.py with a neural voice and shipped as
files, so everybody hears the same thing and it sounds like a person.

Which also fixes the subtitles, for a reason worth writing down: the service
returns sentence boundaries with real timings, so the caption can show THE
SENTENCE BEING SPOKEN rather than the whole paragraph. Reported as "the whole
lines appear in the video" -- 300 characters of caption is four lines on a
phone, and no type size rescues that. The cue list is on the page and the
caption follows the audio's own clock.

Everything else behaves the way a video player does: play/pause, a scrubber,
CC, mute, replay and expand, all inside the frame, none of it running until
somebody presses play.
"""

PLAYER_JS = """
<script>
(function () {
  var stage = document.querySelector('[data-stage]');
  if (!stage) return;
  var scenes  = [].slice.call(stage.querySelectorAll('.sc'));
  var capEl   = document.querySelector('[data-caption]');
  var playBt  = stage.querySelector('[data-journey-play]');
  var bigBt   = stage.querySelector('[data-journey-big]');
  var seek    = stage.querySelector('[data-seek]');
  var countEl = stage.querySelector('[data-count]');
  var muteBt  = stage.querySelector('[data-journey-mute]');
  var ccBt    = stage.querySelector('[data-journey-cc]');
  var againBt = stage.querySelector('[data-journey-replay]');
  var zoomBt  = stage.querySelector('[data-journey-zoom]');
  if (!scenes.length) return;

  var ICON = {};
  try {
    var ib = document.querySelector('[data-icons]');
    if (ib) ICON = JSON.parse(ib.textContent);
  } catch (e) { ICON = {}; }

  var TRACKS = [];
  try {
    var cb = document.querySelector('[data-cues]');
    if (cb) TRACKS = (JSON.parse(cb.textContent) || {}).lines || [];
  } catch (e) { TRACKS = []; }

  var BASE = '/blog/assets/audio/walkthrough/';

  var at = 0, playing = false, muted = false, cc = true;
  var voice = null, bed = null, timer = null, cue = -1;
  var zoomed = false, backdrop = null, resumeAudio = false;
  var READ_MS = 5200;                  // per scene when there is no audio

  try { muted = localStorage.getItem('jk-mute') === '1'; } catch (e) {}
  try { cc = localStorage.getItem('jk-cc') !== '0'; } catch (e) {}

  function cuesFor(i) {
    var t = TRACKS[i];
    return (t && t.cues) || [];
  }

  function setCaption(text) {
    if (!capEl) return;
    var line = cc ? (text || '') : '';
    capEl.innerHTML = line
      ? '<span>' + line.replace(/&/g, '&amp;').replace(/</g, '&lt;') + '</span>'
      : '';
  }

  // The caption is whichever cue has started and not yet been replaced.
  function captionAt(ms) {
    var list = cuesFor(at), pick = -1;
    for (var i = 0; i < list.length; i++) {
      if (list[i].t <= ms) { pick = i; } else { break; }
    }
    if (pick !== cue) {
      cue = pick;
      setCaption(pick >= 0 ? list[pick].text : (list[0] ? list[0].text : ''));
    }
  }

  function paint() {
    scenes.forEach(function (g, n) { g.classList.toggle('is-on', n === at); });
    cue = -1;
    var list = cuesFor(at);
    setCaption(list[0] ? list[0].text : '');
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

  /* The music ducks under the voice.
   *
   * Reported as: "the background is kind of dominating the voice... two
   * voices, both the voice and the background, is messing up." Right, and a
   * flat 10% was the wrong instrument for the job: mountains-1 is a tarana,
   * so it has a tabla in it, and percussion at any level fights a speaking
   * voice for the same attention.
   *
   * So it is ducked, the way narration has been mixed over music for eighty
   * years: the bed sits at 7% in the gaps and drops to 2.5% while a sentence
   * is being spoken -- about 9dB down, which is enough to make it disappear
   * behind speech and still be there when the speech stops.
   *
   * Ramped over 400ms rather than switched, because a level that jumps is
   * more noticeable than a level that is simply high: the ear hears the
   * MOVEMENT. And faded up from silence on play, so it arrives rather than
   * starts.
   */
  var BED_OPEN = 0.05;      // the intro, and the tail after the last line
  var BED_DUCK = 0.025;     // while the voice is speaking
  // Measured: the gap between scenes is 380ms and the lift ramps over 500,
  // so in practice the bed never climbs much above BED_DUCK once the
  // narration starts -- it reached 0.028 at the one transition sampled. That
  // is the right outcome for "focus mostly on the voiceover": the music is
  // effectively a constant floor under the speech, and BED_OPEN only really
  // shapes the first second and the last.
  var bedRamp = null;

  function rampBed(target, ms) {
    if (!bed) return;
    if (bedRamp) { window.clearInterval(bedRamp); bedRamp = null; }
    var from = bed.volume, steps = Math.max(1, Math.round(ms / 40)), i = 0;
    bedRamp = window.setInterval(function () {
      i += 1;
      var v = from + (target - from) * (i / steps);
      try { bed.volume = Math.max(0, Math.min(1, v)); } catch (e) {}
      if (i >= steps) { window.clearInterval(bedRamp); bedRamp = null; }
    }, 40);
  }

  function bedOn(on) {
    if (on && !muted) {
      if (!bed) {
        // mountains-1: bansuri over a tarana rhythm. Already in the repo and
        // already credited; 150s against a ~75s narration, so a single pass
        // never reaches the loop point.
        bed = new Audio('/blog/assets/audio/mountains-1.mp3');
        bed.loop = true;
        bed.volume = 0;
      }
      var b = bed.play();
      if (b && b.catch) { b.catch(function () {}); }
      rampBed(BED_OPEN, 900);
    } else if (bed) {
      rampBed(0, 300);
      window.setTimeout(function () {
        if (bed && bed.volume <= 0.01) { try { bed.pause(); } catch (e) {} }
      }, 360);
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

  function stopVoice() {
    if (!voice) return;
    try { voice.pause(); } catch (e) {}
    voice.onended = null;
    voice.ontimeupdate = null;
    voice.onerror = null;
    voice = null;
  }

  function speak() {
    var track = TRACKS[at];
    if (muted || !track || !track.file) { return false; }
    stopVoice();
    voice = new Audio(BASE + track.file);
    voice.ontimeupdate = function () {
      captionAt(Math.round(voice.currentTime * 1000));
    };
    voice.onplaying = function () { rampBed(BED_DUCK, 400); };
    voice.onended = function () {
      if (!playing) return;
      rampBed(BED_OPEN, 500);          // it comes back in the gap
      window.setTimeout(advance, 380);
    };
    // A missing or blocked file must not strand the walkthrough on one
    // picture with no explanation. Fall back to the timer.
    voice.onerror = function () {
      stopVoice();
      if (playing) { clearTimer(); timer = window.setTimeout(advance, READ_MS); }
    };
    var p = voice.play();
    if (p && p.catch) {
      p.catch(function () {
        stopVoice();
        if (playing) {
          clearTimer();
          timer = window.setTimeout(advance, READ_MS);
        }
      });
    }
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
    if (!speak()) { timer = window.setTimeout(advance, READ_MS); }
  }

  function play() {
    if (playing) return;
    playing = true;
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
    stopVoice();
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
        stopVoice();
        bedOn(false);
        // Muted, the captions are the whole content, so they take their own
        // pace rather than the voice's.
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
      var list = cuesFor(at);
      setCaption(cue >= 0 && list[cue] ? list[cue].text
                                       : (list[0] ? list[0].text : ''));
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

  // Nothing starts on its own, and nothing is fetched until it does: the
  // narration is 698KB that somebody who never presses play should never pay
  // for.
  paint();
  setPlayIcon();

  document.addEventListener('visibilitychange', function () {
    if (document.hidden && playing) { stop(); }
  });
  window.addEventListener('pagehide', function () { stop(); });
})();
</script>
"""
