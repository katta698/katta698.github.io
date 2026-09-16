/* Hero background media — shared by index.html and every blog surface.
 *
 * This lives in one file on purpose. It used to exist twice: inline in
 * index.html and again inside sync_blog.py's blog-page template. Renaming the
 * clips updated one copy and not the other, and the blog hero silently
 * requested files that no longer existed for as long as nobody looked at it.
 * One copy cannot drift from itself.
 *
 * Preview without waiting for the calendar:
 *   ?theme=forest          a particular theme
 *   ?theme=ocean&clip=5    a particular clip within it
 *   ?theme=rain&audio=3    a particular track
 * Out-of-range values are ignored, so a bad number cannot blank the hero.
 */
// HERO MEDIA — theme by week of year, clip by day of week.
//
// Two dimensions so nothing repeats quickly: the week picks one of six
// themes, the day picks one of that theme's seven clips. A daily visitor
// sees a new clip each day; a weekly visitor sees a new theme each week.
// 42 files, 52 distinct clip-weeks a year.
//
// Files are /blog/assets/videos/<theme>-<1..7>.mp4 and the matching .mp3.
// Themes without their own clips yet fall back to ocean, so the hero is
// never blank while a theme is still being filled in.
(function () {
  // Seasonal, India-leaning: mountains in the clear winter air, forest
  // greening through spring, ocean in summer, rain through the monsoon,
  // sunset in the autumn light, boho warmth from Diwali into December.
  // Plain list, not an algorithm — edit any week by changing one word.
  var PLAN = [
    'mountains','boho','mountains','forest',        // Jan
    'mountains','forest','boho','mountains',        // Feb
    'forest','sunset','forest','ocean',             // Mar
    'forest','ocean','sunset','forest',             // Apr
    'ocean','sunset','ocean','sunset',              // May
    'ocean','sunset','ocean','rain',                // Jun
    'rain','forest','rain','rain',                  // Jul
    'rain','forest','rain','ocean',                 // Aug
    'rain','sunset','forest','sunset',              // Sep
    'sunset','boho','sunset','mountains',           // Oct
    'boho','sunset','boho','mountains',             // Nov
    'boho','mountains','boho','ocean',              // Dec
    'mountains','boho','ocean','forest'             // tail of the year
  ];
  var FALLBACK = 'ocean';

  // ISO-8601 week number: weeks start Monday, week 1 holds the first
  // Thursday of the year.
  function isoWeek(d) {
    var t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
    var dayNum = t.getUTCDay() || 7;               // Mon=1 ... Sun=7
    t.setUTCDate(t.getUTCDate() + 4 - dayNum);     // shift to that week's Thursday
    var yearStart = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
    return Math.ceil((((t - yearStart) / 86400000) + 1) / 7);
  }

  // How many clips each theme actually has. Themes are not all the same size
  // — forest absorbed a set of jungle clips, boho grew by two — so the day
  // index has to wrap on the real count rather than assume seven.
  //
  // A theme at 0 falls straight through to the fallback, which is how a
  // half-filled theme ships without breaking anything.
  // scripts/validate_hero_media.py fails if these numbers drift from what
  // is actually on disk.
  var COUNTS = { ocean: 7, mountains: 7, forest: 13, sunset: 7, boho: 9, rain: 7 };

  // Audio follows the clip, not the week. The track restarts on every page
  // load regardless — it is not a stream running across a week — so holding
  // one track for seven days bought nothing and cost variety: someone
  // visiting across a week heard the same piece every day.
  //
  // Where a theme has fewer tracks than clips the mapping simply wraps, so
  // most days still differ. boho is listed explicitly because there the
  // pairing is meaningful rather than incidental: clips 2 and 3 are the cats
  // and get the cat tracks; the rest get the sitar.
  var CLIP_AUDIO = { boho: [1, 2, 3, 1, 1, 1, 1, 1, 1] };

  // Audio is counted separately: there are far fewer tracks than clips, and
  // they rotate per theme-recurrence rather than per day.
  var AUDIO_COUNTS = { ocean: 3, mountains: 5, forest: 3, rain: 5, sunset: 2, boho: 3 };

  var now = new Date();
  // Some ISO years have 53 weeks — 2026 does, because 1 January was a
  // Thursday. Without this wrap, week 53 would index past the plan and the
  // hero would go blank for a week, once every five or six years.
  var theme = PLAN[(isoWeek(now) - 1) % PLAN.length];

  // There was a dusk rule here: between 17:00 and 21:00 local, sunset took the
  // evening whatever the week said. The intent was variety for someone
  // visiting morning and evening.
  //
  // It did the opposite for anyone whose habit is evening browsing. Four hours
  // is 17% of the day and 100% of their visits, so they saw sunset every
  // single time and never learned the other five themes existed. Removed: the
  // week picks the theme and the day picks the clip, at any hour.
  //
  // If something like it comes back, it must not be able to swallow a whole
  // audience's entire experience. A rule that fires for everyone briefly is
  // not the same as a rule that fires for some people always.

  // ?theme=forest forces a theme, for previewing without waiting for the
  // calendar. Ignored unless it names a theme that actually has clips.
  var forced = (location.search.match(/[?&]theme=([a-z]+)/) || [])[1];
  if (forced && COUNTS[forced]) theme = forced;

  if (!COUNTS[theme]) theme = FALLBACK;            // theme has no clips yet
  var count = COUNTS[theme] || 1;
  var n = (now.getDay() % count) + 1;              // wraps on the real count

  // ?clip=5 forces a particular clip, so any of a theme's clips can be seen
  // without waiting for the day of week to come round. Out-of-range values are
  // ignored rather than clamped — a wrong number should show the normal clip,
  // not silently a different one.
  var forcedClip = parseInt((location.search.match(/[?&]clip=(\d+)/) || [])[1], 10);
  if (forcedClip >= 1 && forcedClip <= count) n = forcedClip;

  // Video is one file per clip; audio is one file per theme. The picture
  // changes daily, the ambience holds for the week — restarting a music bed
  // at every midnight would be worse than letting it run.
  function videoSources() {
    // The fallback index wraps on ocean's own count. Without this, a theme
    // with more clips than ocean (forest has 13) could ask for ocean-12,
    // which does not exist, and the fallback would fail too.
    var fn = (now.getDay() % COUNTS[FALLBACK]) + 1;
    return {
      themed:   '/blog/assets/videos/' + theme + '-' + n + '.mp4',
      fallback: '/blog/assets/videos/' + FALLBACK + '-' + fn + '.mp4'
    };
  }
  // Audio rotates on the theme's *recurrence*, not the day. Forest comes round
  // eight or nine times a year; without this it would sound identical every
  // time. Counting how many times the theme has appeared in the plan up to
  // this week gives a stable index — the same week always resolves to the same
  // track, so it is not random, just varied.
  function audioSources() {
    // Kept as the starting value so a theme with an odd clip/track ratio still
    // varies between recurrences rather than repeating the same short cycle.
    var wk = (isoWeek(now) - 1) % PLAN.length;
    var occurrence = 0;
    for (var i = 0; i <= wk; i++) { if (PLAN[i] === theme) occurrence++; }
    var count = AUDIO_COUNTS[theme] || 1;
    var an = occurrence > 0 ? ((occurrence - 1) % count) + 1 : 1;

    // An explicit map wins where one exists; otherwise the clip index wraps
    // onto the available tracks, so the track changes with the picture.
    var byClip = CLIP_AUDIO[theme];
    if (byClip && byClip[n - 1] >= 1 && byClip[n - 1] <= count) an = byClip[n - 1];
    else if (!byClip) an = ((n - 1) % count) + 1;

    var forcedAudio = parseInt((location.search.match(/[?&]audio=(\d+)/) || [])[1], 10);
    if (forcedAudio >= 1 && forcedAudio <= count) an = forcedAudio;
    return {
      themed:   '/blog/assets/audio/' + theme + '-' + an + '.mp3',
      fallback: '/blog/assets/audio/' + FALLBACK + '-1.mp3'
    };
  }

  var v = document.getElementById('hero-video');
  if (v) {
    var vs = videoSources();
    var triedFallback = false;
    v.addEventListener('error', function () {
      if (!triedFallback && v.src.indexOf(vs.fallback) === -1) {
        triedFallback = true;
        v.src = vs.fallback;
        v.load();
      }
    });
    // The poster goes on BEFORE the src, and it is the whole point.
    //
    // The <video> ships with no src and no poster, so until video data
    // arrived the hero was a flat #1D2322 block -- 414px of it on the blog,
    // 890px on the portfolio -- and then the clip appeared. Reported, many
    // times, as the blog and the portfolio "refreshing" while Intelligence,
    // What's New and Live status are seamless. Those three simply have no
    // hero video, so nothing about them arrives late.
    //
    // A poster is one still from the same clip, about 20KB against 1.4MB of
    // mp4, so it paints almost immediately and the video fades in over an
    // image of itself rather than over a dark rectangle. Set first, because
    // assigning src starts the load and the poster is what covers that gap.
    //
    // Generated from the clips themselves by scripts/make_hero_posters.py, so
    // a new clip cannot end up with someone else's still.
    v.poster = vs.themed.replace('/videos/', '/videos/posters/')
                        .replace('.mp4', '.webp');
    v.src = vs.themed;

    // Coming back to the tab must not need a refresh.
    //
    // Reported: "in my iPhone when I switch to a different browser or a
    // different app and come back, the video is stuck unless I refresh".
    //
    // This used to be play() and nothing else, on the assumption that a
    // paused video only needs playing. iOS does more than pause: it frees the
    // decoded data of a backgrounded video to reclaim memory, and the element
    // comes back with readyState 0 -- HAVE_NOTHING. play() on an element with
    // no data does not refetch it, so it stays on the last painted frame and
    // looks frozen. load() is what puts the data back, and only a reload of
    // the page was doing that.
    //
    // Three events rather than one, because a return from another app is not
    // the same thing in every browser: visibilitychange fires on a tab
    // switch, pageshow on a back-forward restore, and focus on a return from
    // another application. They overlap, and overlapping is the point --
    // _tryPlay is a no-op when the video is already running.
    var _tryPlay = function (force) {
      if (!v.paused) return;
      // force, or nothing loaded, means reload before playing.
      //
      // The first version only reloaded at readyState 0, on the reasoning
      // that a video with data just needs playing. Safari came back from an
      // app switch paused WITH data still attached and play() did nothing --
      // reported again from a private window, where there is no cache and no
      // stale copy to blame. So the second attempt stops trusting readyState
      // and reloads regardless.
      //
      // load() restarts the clip from the beginning. That is a real cost and
      // it is the right trade: a hero that restarts is a hero that is
      // playing, and the alternative on that device is one frozen frame until
      // the reader refreshes the page themselves.
      if (force || v.readyState === 0) { try { v.load(); } catch (e) {} }
      var p = v.play();
      if (p && p.catch) p.catch(function () {});
    };
    // And a beat afterwards: iOS is not always ready the instant it says it
    // is visible, and a single attempt at that moment is quietly dropped.
    var _resume = function () {
      if (document.hidden) return;
      // Gently first: if it simply needs playing, play it and keep the
      // position. Only if it is still stopped a moment later is the clip
      // reloaded, which costs the position but always works.
      _tryPlay(false);
      setTimeout(function () { _tryPlay(false); }, 250);
      setTimeout(function () { _tryPlay(true); }, 900);
      setTimeout(function () { _tryPlay(true); }, 2200);
      // and the same again for a video that never stopped and never moved
      _clockStalled();
      setTimeout(_clockStalled, 1500);
    };
    // The case every line above misses: NOT paused, and not moving.
    //
    // Reported as the hero freezing after switching to another app and back,
    // needing a manual refresh. Everything above opens with
    //
    //     if (!v.paused) return;
    //
    // which is the right question for a video that stopped and the wrong one
    // for this. iOS frees the decoded frames of a backgrounded video; the
    // element can come back reporting paused === false, with a readyState it
    // is happy about, and simply never advance. It is not stopped. It is
    // playing nothing, forever, and every recovery path here exits on its
    // first line.
    //
    // So this asks the only question that cannot be answered wrongly: did the
    // clock move? Sample currentTime, wait, sample again. A video that is
    // genuinely playing has advanced; one that has been gutted has not, no
    // matter what it says about itself. Then load() puts the data back.
    //
    // 600ms because a real frame at 25fps arrives every 40ms, so anything
    // still identical after 600 is not slow, it is stopped. The comparison is
    // against a tolerance rather than equality: currentTime is a float and a
    // stalled element occasionally reports a hair of drift.
    var _clockStalled = function () {
      if (document.hidden) return;
      var t0 = v.currentTime;
      window.setTimeout(function () {
        if (document.hidden || v.paused) return;   // paused is handled above
        if (Math.abs(v.currentTime - t0) > 0.05) return;    // it is moving
        try { v.load(); } catch (e) {}
        var p = v.play();
        if (p && p.catch) p.catch(function () {});
      }, 600);
    };

    v.addEventListener('loadeddata', _tryPlay, { once: true });
    v.addEventListener('canplay', _tryPlay, { once: true });
    document.addEventListener('visibilitychange', _resume);
    window.addEventListener('pageshow', _resume);
    window.addEventListener('focus', _resume);
    document.addEventListener('touchstart', _tryPlay, { once: true });
    var _n = 0, _iv = setInterval(function () { _tryPlay(); if (++_n >= 4 || !v.paused) clearInterval(_iv); }, 2000);
  }

  // Wait for the element if it is not here yet.
  //
  // This file used to be loaded at the foot of every page, after
  // <audio id="beach-audio">, so the element was always present. Then it was
  // moved up beside the hero <video> on the portfolio and the blog -- the
  // video ships with no src and this script sets it, and at the foot of the
  // document that left the hero a flat rectangle until it got there.
  //
  // The audio element is still at the BOTTOM of those two pages. So this
  // lookup returned null, the whole block below was skipped, and the music
  // button did nothing at all: no src, readyState 0, no error, no sound.
  // Reported as "the music icon doesn't work". Live status, which still
  // loads this file at the foot, kept working -- which is what made it look
  // like a per-page problem rather than an ordering one.
  //
  // Retrying on DOMContentLoaded makes the file safe to load from anywhere,
  // which is the property it needed all along: nothing else here should have
  // to know where in the document it sits.
  function wireAudio() {
  var a = document.getElementById('beach-audio');
  if (a) {
    var as = audioSources();
    var audioFellBack = false;
    // The element is preload="none" on purpose — these files are megabytes and
    // most visitors never turn sound on. That means nothing is fetched until
    // the toggle is pressed, so a missing themed track cannot be detected in
    // advance: the error only fires on that first press. Retrying the play
    // after swapping to the fallback is what stops that press being silent.
    a.addEventListener('error', function () {
      if (!audioFellBack && a.src.indexOf(as.fallback) === -1) {
        audioFellBack = true;
        var wanted = a.dataset.wanted === '1';
        a.src = as.fallback;
        if (wanted) a.play().catch(function () {});
      }
    });
    a.src = as.themed;
  }

  }

  if (document.getElementById('beach-audio')) {
    wireAudio();
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wireAudio, { once: true });
  } else {
    wireAudio();
  }

  // Exposed so scripts/validate_hero_media.py and manual checks can see what
  // today resolves to without reading the clock by hand.
  window.__heroTheme = { theme: theme, clip: n, week: isoWeek(now) };
})();
