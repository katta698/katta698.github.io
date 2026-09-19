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
  var timeEl  = stage.querySelector('[data-time]');
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
  var TOTAL = 0;
  try {
    var cbb = document.querySelector('[data-cues]');
    if (cbb) TOTAL = (JSON.parse(cbb.textContent) || {}).duration || 0;
  } catch (e) { TOTAL = 0; }
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

  // Which scene a given moment belongs to. One definition, used by the
  // scrubber, the clock and the tick that follows the audio -- they cannot
  // disagree about where we are if they all ask the same question.
  function sceneFor(ms) {
    for (var i = TRACKS.length - 1; i >= 0; i--) {
      if (ms >= (TRACKS[i].start || 0) - 40) { return i; }
    }
    return 0;
  }

  function atMs() {
    if (voice && !isNaN(voice.currentTime)) { return voice.currentTime * 1000; }
    var t = TRACKS[at];
    return t ? (t.start || 0) : 0;
  }

  function mmss(ms) {
    var s = Math.max(0, Math.round(ms / 1000));
    return Math.floor(s / 60) + ':' + (s % 60 < 10 ? '0' : '') + (s % 60);
  }

  // The bar and the clock, from a moment in the audio rather than from a
  // scene number. Called on every tick, so the thumb moves the way a video
  // player's does instead of jumping once per scene.
  function paintBar(ms) {
    if (seek && document.activeElement !== seek) {
      var v = String(Math.round(ms));
      if (seek.value !== v) { seek.value = v; }
    }
    if (seek) {
      var pct = TOTAL > 0 ? Math.max(0, Math.min(100, (ms / TOTAL) * 100)) : 0;
      seek.style.setProperty('--cf-pct', pct + '%');
    }
    if (timeEl) {
      var of = timeEl.querySelector('.cf-of');
      timeEl.textContent = mmss(ms);
      if (of) { timeEl.appendChild(of); }
    }
  }

  function paint() {
    scenes.forEach(function (g, n) { g.classList.toggle('is-on', n === at); });
    cue = -1;
    var list = cuesFor(at);
    setCaption(list[0] ? list[0].text : '');
    paintBar(atMs());
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
  /* Reported from an Android phone: "I don't hear background music."
   *
   * Not a playback fault -- the element was playing, at the level it was
   * told to. The level was the fault. Measured mid-playback:
   *
   *     mountains-1.mp3  vol 0.025   narration.mp3  vol 1.0
   *
   * 0.025 against 1.0 is about -32dB. That is not subtle, it is gone: below
   * the noise floor of a phone speaker in a room. I had taken "reduce the
   * background to subtle" and kept halving until there was nothing left.
   *
   * Broadcast practice for music under speech is 15 to 20dB down, not 32.
   * 0.22 open and 0.11 ducked is -13 and -19: present in the gaps, clearly
   * behind the voice while it speaks, and audible on a phone.
   */
  var BED_OPEN = 0.14;      // the moment between pressing play and the
                            // first word, and nothing else
  var BED_UNDER = 0.09;     // while the voice is actually sounding

  /* The music is allowed to sound only while the VOICE is sounding.
   *
   * Reported four times, in the same words every time: "the voiceover
   * stops, but the music in the background still continues." I kept fixing
   * the end of the track, which was the one place this was NOT happening.
   *
   * The real fault was structural: the bed played whenever the PLAYER
   * thought it was playing, and the player thought so in three situations
   * where there is no voice at all --
   *
   *   voice.onerror       set voice = null and carried on with a timer
   *   play() rejected     same silent timer, same music
   *   a stall mid-track   no handler at all; the clock stops, the pictures
   *                       freeze, and the bed -- a separate, smaller, fully
   *                       buffered file on loop -- keeps going
   *
   * All three sound identical from the outside, and all three are what he
   * heard. So the bed no longer has a life of its own: its level is derived
   * from whether the narration clock has moved recently, checked four times
   * a second. No progress for 1.2s and the music is gone, whatever the
   * reason -- stall, error, refusal, end of file. It comes back by itself
   * when the voice does.
   */
  var STALL_MS = 1200;
  var lastProgress = 0;     // when the narration clock last moved
  var voiceStarted = false; // has a first word ever been spoken
  var bedWatch = null;
  var lastMs = -1;        // the clock reading at the previous tick
  // Measured: the gap between scenes is 380ms and the lift ramps over 500,
  // so in practice the bed never climbs much above BED_DUCK once the
  // narration starts -- it reached 0.028 at the one transition sampled. That
  // is the right outcome for "focus mostly on the voiceover": the music is
  // effectively a constant floor under the speech, and BED_OPEN only really
  // shapes the first second and the last.
  var bedRamp = null;

  function bedLevel() {
    if (!playing || muted) return 0;
    if (Date.now() - lastProgress > STALL_MS) return 0;
    return voiceStarted ? BED_UNDER : BED_OPEN;
  }

  // The single place the bed's volume is decided. Everything else just
  // calls this and lets it work the answer out.
  function syncBed() {
    var want = bedLevel();
    if (!bed) return;
    if (want <= 0) {
      if (bed.volume > 0.001 || !bed.paused) {
        rampBed(0, 260);
        window.setTimeout(function () {
          if (bed && bedLevel() <= 0) { try { bed.pause(); } catch (e) {} }
        }, 300);
      }
      return;
    }
    if (bed.paused) {
      var r = bed.play();
      if (r && r.catch) { r.catch(function () {}); }
    }
    if (Math.abs(bed.volume - want) > 0.005) { rampBed(want, 360); }
  }

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
      syncBed();
      if (!bedWatch) { bedWatch = window.setInterval(syncBed, 250); }
    } else if (bed) {
      if (bedWatch) { window.clearInterval(bedWatch); bedWatch = null; }
      rampBed(0, 300);
      window.setTimeout(function () {
        try { bed.pause(); } catch (e) {}
      }, 340);
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
  }

  /* One element for the whole narration.
   *
   * It is created on the first press -- inside the gesture, which is what
   * iOS requires -- and never replaced. Scenes are offsets into it, so
   * changing scene is a seek, not a download: there is nothing to buffer
   * mid-sentence and nothing for the platform to refuse.
   *
   * Reported as: "in the middle of the video the music just continues,
   * there's no voice, and maybe after a minute the voice continues." That
   * was eight separate files, each fetched when its scene began, and on iOS
   * some of them silently declined to play because they had been created
   * long after the tap.
   */
  function ensureVoice() {
    if (voice || !TRACKS.length) return voice;
    voice = new Audio(BASE + 'narration.mp3');
    voice.preload = 'auto';
    voice.ontimeupdate = function () {
      var ms = Math.round(voice.currentTime * 1000);
      // Proof the narration is really sounding, not merely un-paused. The
      // music's level is derived from this and nothing else.
      if (ms !== lastMs) { lastMs = ms; lastProgress = Date.now();
                           voiceStarted = true; syncBed(); }
      captionAt(ms);
      // The scene follows the audio, not a timer: whatever the clock says
      // is being spoken is what is on screen.
      // The picture is wherever the AUDIO is -- derived, never assumed.
      //
      // Reported as: "the video is done, the audio keeps continuing." The
      // scrub bar was at the end, the last caption was on screen, and the
      // narration was still talking from somewhere near the beginning.
      //
      // Scrubbing used to set the scene directly and then ask the audio to
      // follow. When the audio did not -- a seek past what is buffered, a
      // slow connection, a platform declining it -- nothing ever corrected
      // it. The old rule here only stepped FORWARD one scene at a time, and
      // only at a scene boundary, so a picture that was wrong stayed wrong
      // for good. Measured on a server without range support, which is
      // exactly what a failed seek looks like:
      //
      //     after jumping to the end:  scene 8 / 8,  voice at 1.2s, playing
      //
      // Now the index is computed from the clock on every tick, so a seek
      // that does not land is corrected within about 250ms and the pictures
      // cannot claim to be finished while the voice is still reading.
      if (!playing || voice.seeking) { return; }
      paintBar(ms);
      var want = sceneFor(ms);
      if (want !== at) { at = want; paint(); }
    };
    voice.onended = function () { stop(); };
    voice.onerror = function () {
      voice = null;
      // Whatever happens to the pictures, the music goes with the voice.
      lastProgress = 0;
      syncBed();
      if (playing) { clearTimer(); timer = window.setTimeout(advance, READ_MS); }
    };
    // Buffering, stalled, or paused by the platform: silence the bed now
    // rather than waiting out the watchdog, so there is no second of music
    // alone. onplaying does not lift it -- only the clock moving does.
    voice.onwaiting = voice.onstalled = voice.onpause = function () {
      lastProgress = 0;
      syncBed();
    };
    return voice;
  }

  function speak() {
    if (muted || !TRACKS.length) { return false; }
    var a = ensureVoice();
    if (!a) return false;
    var t = TRACKS[at];
    var want = (t && t.start ? t.start : 0) / 1000;
    // Only seek when the clock is not already inside this scene, so playing
    // straight through never interrupts itself.
    var now = a.currentTime;
    if (!t || now < (t.start / 1000) - 0.25 || now > (t.end / 1000)) {
      try { a.currentTime = want; } catch (e) {}
    }
    var p = a.play();
    if (p && p.catch) {
      p.catch(function () {
        if (playing) {
          clearTimer();
          timer = window.setTimeout(advance, READ_MS);
        }
      });
    }
    syncBed();
    return true;
  }

  // Only used when there is no audio -- muted, or the file would not play.
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
    // The grace window: BED_OPEN is allowed for STALL_MS after the press,
    // and then only if a word has actually been spoken. If the narration
    // never starts, the music stops on its own rather than playing alone.
    lastProgress = Date.now();
    lastMs = -1;
    stage.classList.add('is-started', 'is-playing');
    setPlayIcon();
    siteAudio(true);
    bedOn(true);
    run();
  }

  function stop() {
    playing = false;
    lastProgress = 0;
    voiceStarted = false;
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
      var ms = Math.max(0, Math.min(TOTAL, parseInt(seek.value, 10) || 0));
      at = sceneFor(ms);
      // Move the audio first, so paint() reads the position it is going to
      // and the bar does not flick back to where the voice used to be.
      if (voice) { try { voice.currentTime = ms / 1000; } catch (e) {} }
      paint();
      paintBar(ms);
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
    // The picture gives up a strip for the caption, but only while there
    // IS a caption. With subtitles off the drawing gets the whole frame.
    stage.classList.toggle('cc-on', !!cc);
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
