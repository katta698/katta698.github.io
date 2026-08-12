/* Hero background media — shared by index.html and every blog surface.
 *
 * This lives in one file on purpose. It used to exist twice: inline in
 * index.html and again inside sync_blog.py's blog-page template. Renaming the
 * clips updated one copy and not the other, and the blog hero silently
 * requested files that no longer existed for as long as nobody looked at it.
 * One copy cannot drift from itself.
 *
 * Preview any theme without waiting for its week: ?theme=forest
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

  // Audio is counted separately: there are far fewer tracks than clips, and
  // they rotate per theme-recurrence rather than per day.
  var AUDIO_COUNTS = { ocean: 3, mountains: 5, forest: 3, rain: 5, sunset: 2, boho: 2 };

  var now = new Date();
  // Some ISO years have 53 weeks — 2026 does, because 1 January was a
  // Thursday. Without this wrap, week 53 would index past the plan and the
  // hero would go blank for a week, once every five or six years.
  var theme = PLAN[(isoWeek(now) - 1) % PLAN.length];

  // ?theme=forest forces a theme, for previewing without waiting for the
  // calendar. Ignored unless it names a theme that actually has clips.
  var forced = (location.search.match(/[?&]theme=([a-z]+)/) || [])[1];
  if (forced && COUNTS[forced]) theme = forced;

  if (!COUNTS[theme]) theme = FALLBACK;            // theme has no clips yet
  var count = COUNTS[theme] || 1;
  var n = (now.getDay() % count) + 1;              // wraps on the real count

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
    var wk = (isoWeek(now) - 1) % PLAN.length;
    var occurrence = 0;
    for (var i = 0; i <= wk; i++) { if (PLAN[i] === theme) occurrence++; }
    var count = AUDIO_COUNTS[theme] || 1;
    var an = occurrence > 0 ? ((occurrence - 1) % count) + 1 : 1;
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
    v.src = vs.themed;

    var _tryPlay = function () { if (v.paused) v.play().catch(function () {}); };
    v.addEventListener('loadeddata', _tryPlay, { once: true });
    v.addEventListener('canplay', _tryPlay, { once: true });
    document.addEventListener('visibilitychange', function () { if (!document.hidden) _tryPlay(); });
    window.addEventListener('pageshow', _tryPlay);
    document.addEventListener('touchstart', _tryPlay, { once: true });
    var _n = 0, _iv = setInterval(function () { _tryPlay(); if (++_n >= 4 || !v.paused) clearInterval(_iv); }, 2000);
  }

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

  // Exposed so scripts/validate_hero_media.py and manual checks can see what
  // today resolves to without reading the clock by hand.
  window.__heroTheme = { theme: theme, clip: n, week: isoWeek(now) };
})();
