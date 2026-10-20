/* Occasion banner + seasonal snow — shared by every surface.
 *
 * This was inline in index.html, which meant it only ever showed on the home
 * page: a reader arriving straight at a post on Independence Day saw nothing,
 * and the site looked like two different sites on the same day. hero-media.js
 * and site-footer.js already live here for the same reason.
 *
 * The banner element is created here rather than shipped as markup in each
 * page, so a surface only has to load this file — there is no <div> to keep in
 * step across index.html, the blog index and ~110 post pages.
 *
 * Pages that position content below the banner read --occasion-banner-h, which
 * is set from the rendered height rather than assumed, because the text wraps
 * to two lines on a narrow screen.
 */
(function () {
  if (document.getElementById('occasion-banner')) return;
  var el = document.createElement('div');
  el.id = 'occasion-banner';
  // line-height is pinned, not inherited.
  //
  // Reported as: the festival strip is taller on the portfolio than on every
  // other tab, on desktop and on mobile. Measured -- portfolio 37px, the other
  // four 33px, with identical font-size and identical padding. This element
  // sets neither line-height nor anything to stop inheritance, so it took the
  // portfolio's body line-height of 1.65 (21.12px, against a normal of about
  // 17px) and grew by four pixels. Nothing was wrong with the banner; it was
  // wearing whatever the page underneath it wore.
  //
  // 1.33 is what the other four already computed, so they do not move and the
  // portfolio joins them. Unitless, so it still scales with the root size.
  el.setAttribute('style', 'display:none; position:fixed; top:0; left:0; width:100%; z-index:1001; text-align:center; padding:0.5rem 1rem; font-size:0.8rem; font-family:\'Inter\',sans-serif; letter-spacing:0.02em; line-height:1.33;');
  // Before everything else in the body, so it reads first for a screen reader.
  (document.body || document.documentElement).insertBefore(
    el, (document.body || document.documentElement).firstChild);
})();

(function () {
    // ── OCCASION BANNER ────────────────────────────────────────────────
    // Three kinds of date, because three kinds of holiday exist.
    //
    // FIXED       same Gregorian date every year. Never expires.
    // NTH_WEEKDAY "4th Thursday in November". Computed, so it never expires
    //             either — no table to maintain for US federal holidays.
    // LUNAR       Hindu festivals follow a lunisolar calendar and land on a
    //             different Gregorian date each year, so they can only be
    //             tabled. Dates verified against drikpanchang.com on
    //             2026-08-11 and cross-checked: every festival moves 10-12
    //             days earlier each year, jumping ~+19 in an adhika-masa
    //             (leap month) year, and all five Diwali dates match the
    //             pre-existing table that was already here.
    //
    // ⚠ The LUNAR table runs out after the last year listed. When it does,
    //   those banners silently stop appearing — nothing breaks, they just
    //   never show. Top it up from drikpanchang.com; do not extrapolate the
    //   pattern by hand, because leap months make it irregular.
    var FIXED = [
      { month: 0,  day: 1,  text: '🎉 Happy New Year!', link: 'https://en.wikipedia.org/wiki/New_Year',                                         gradient: 'linear-gradient(90deg,#1D2322 0%,#876943 100%)' },
      { month: 0,  day: 26, text: '🎊 Happy Republic Day!', link: 'https://en.wikipedia.org/wiki/Republic_Day_(India)',                                     gradient: 'linear-gradient(90deg,#8B5A3C 0%,#5A6B4A 100%)' },
      { month: 5,  day: 19, text: '✊ Juneteenth — commemorating emancipation.', link: 'https://en.wikipedia.org/wiki/Juneteenth',                 gradient: 'linear-gradient(90deg,#3E2A2A 0%,#8B4A3F 100%)' },
      { month: 6,  day: 4,  text: '🎆 Happy 4th of July — wishing you a great Independence Day!', link: 'https://en.wikipedia.org/wiki/Independence_Day_(United_States)', gradient: 'linear-gradient(90deg,#2E3A4A 0%,#8B4A3F 100%)' },
      { month: 7,  day: 15, text: '🎊 Happy Independence Day! Jai Hind.', link: 'https://en.wikipedia.org/wiki/Independence_Day_(India)',                        gradient: 'linear-gradient(90deg,#8B5A3C 0%,#5A6B4A 100%)' },
      { month: 4,  day: 25, text: '🎉 Feliz Día de la Revolución de Mayo!', link: 'https://en.wikipedia.org/wiki/May_Revolution',      gradient: 'linear-gradient(90deg,#33505F 0%,#56707E 100%)' },
      { month: 6,  day: 9,  text: '🎉 Feliz Día de la Independencia, Argentina!', link: 'https://en.wikipedia.org/wiki/Argentine_Declaration_of_Independence', gradient: 'linear-gradient(90deg,#33505F 0%,#56707E 100%)' },
      { month: 7,  day: 31, text: '🎉 Selamat Hari Merdeka, Malaysia!', link: 'https://en.wikipedia.org/wiki/Hari_Merdeka',            gradient: 'linear-gradient(90deg,#2E3A4A 0%,#8B6B3F 100%)' },
      { month: 8,  day: 16, text: '🤝 Happy Malaysia Day!', link: 'https://en.wikipedia.org/wiki/Malaysia_Day',                        gradient: 'linear-gradient(90deg,#2E3A4A 0%,#7A6A55 100%)' },
      { month: 9,  day: 2,  text: '🕊️ Gandhi Jayanti — remembering the Mahatma.', link: 'https://en.wikipedia.org/wiki/Gandhi_Jayanti',                gradient: 'linear-gradient(90deg,#3A4A3F 0%,#627358 100%)' },
      { month: 9,  day: 31, text: '🎃 Happy Halloween!', link: 'https://en.wikipedia.org/wiki/Halloween',                                         gradient: 'linear-gradient(90deg,#6B3A1F 0%,#241E1A 100%)' },
      { month: 10, day: 11, text: '🎖️ Veterans Day — thank you to all who served.', link: 'https://en.wikipedia.org/wiki/Veterans_Day',              gradient: 'linear-gradient(90deg,#2E3A4A 0%,#6B5A47 100%)' },
      // Days that mark what this site is about rather than a holiday:
      // forests, oceans, mountains, music, photography, and two that are
      // not celebrations at all. Worded soberly for that reason.
      { month: 2 , day: 21, text: '🌲 International Day of Forests.', link: 'https://en.wikipedia.org/wiki/International_Day_of_Forests', gradient: 'linear-gradient(90deg,#3A4A3F 0%,#5A6B4A 100%)' },
      { month: 3 , day: 22, text: '🌍 Earth Day — one planet, borrowed.', link: 'https://en.wikipedia.org/wiki/Earth_Day', gradient: 'linear-gradient(90deg,#2E4A3A 0%,#627358 100%)' },
      { month: 5 , day: 8 , text: '🌊 World Oceans Day.', link: 'https://en.wikipedia.org/wiki/World_Oceans_Day', gradient: 'linear-gradient(90deg,#2E3A4A 0%,#3E6070 100%)' },
      { month: 5 , day: 21, text: '🎻 World Music Day.', link: 'https://en.wikipedia.org/wiki/F%C3%AAte_de_la_Musique', gradient: 'linear-gradient(90deg,#4A3A5C 0%,#876943 100%)' },
      { month: 6 , day: 30, text: '🕯️ World Day Against Trafficking in Persons.', link: 'https://www.un.org/en/observances/end-human-trafficking-day', gradient: 'linear-gradient(90deg,#2A2A35 0%,#5A4A6B 100%)' },
      { month: 7 , day: 19, text: '📷 World Photography Day.', link: 'https://www.worldphotographyday.com/', gradient: 'linear-gradient(90deg,#2E3635 0%,#6B5A47 100%)' },
      { month: 11, day: 10, text: '⚖️ Human Rights Day.', link: 'https://en.wikipedia.org/wiki/Human_Rights_Day', gradient: 'linear-gradient(90deg,#3E2A2A 0%,#8B4A3F 100%)' },
      { month: 11, day: 11, text: '⛰️ International Mountain Day.', link: 'https://www.un.org/en/observances/mountain-day', gradient: 'linear-gradient(90deg,#2E3A4A 0%,#55677E 100%)' },
      { month: 11, day: 25, text: '🎄 Merry Christmas & Happy Holidays!', link: 'https://en.wikipedia.org/wiki/Christmas',                        gradient: 'linear-gradient(90deg,#2E4A3A 0%,#7A3B34 100%)' }
    ];

    // month, weekday (0=Sun), nth (-1 = last of the month)
    var NTH_WEEKDAY = [
      { month: 0,  weekday: 1, nth: 3,  text: '✊ Martin Luther King Jr. Day.', link: 'https://en.wikipedia.org/wiki/Martin_Luther_King_Jr._Day',                   gradient: 'linear-gradient(90deg,#2A2A35 0%,#5A4A6B 100%)' },
      { month: 1,  weekday: 1, nth: 3,  text: '🏛️ Presidents Day.', link: 'https://en.wikipedia.org/wiki/Washington%27s_Birthday',                              gradient: 'linear-gradient(90deg,#2E3A4A 0%,#55677E 100%)' },
      { month: 4,  weekday: 1, nth: -1, text: '🌺 Memorial Day — remembering those who served.', link: 'https://en.wikipedia.org/wiki/Memorial_Day',  gradient: 'linear-gradient(90deg,#2E3A4A 0%,#5A6B4A 100%)' },
      { month: 8,  weekday: 1, nth: 1,  text: '🛠️ Happy Labor Day!', link: 'https://en.wikipedia.org/wiki/Labor_Day_(United_States)',                              gradient: 'linear-gradient(90deg,#2E3635 0%,#826A4F 100%)' },
      { month: 10, weekday: 4, nth: 4,  text: '🦃 Happy Thanksgiving!', link: 'https://en.wikipedia.org/wiki/Thanksgiving_(United_States)',                           gradient: 'linear-gradient(90deg,#6B3F24 0%,#876943 100%)' }
    ];

    // year -> [month, day]. month is 0-indexed, matching JS Date.
    var LUNAR = {
      'Chinese New Year': { text: '🧧 Gong Xi Fa Cai — Happy Lunar New Year!', link: 'https://en.wikipedia.org/wiki/Chinese_New_Year', gradient: 'linear-gradient(90deg,#6B2E2A 0%,#93653B 100%)',
                            dates: { 2026:[1,17], 2027:[1,6],  2028:[0,26], 2029:[1,13], 2030:[1,3],  2031:[0,23] } },
      'Holi':             { text: '🎨 Happy Holi! Wishing you a year full of colour.', link: 'https://en.wikipedia.org/wiki/Holi',    gradient: 'linear-gradient(90deg,#8B4A3F 0%,#876943 50%,#5A6B4A 100%)',
                            dates: { 2026:[2,4],  2027:[2,22], 2028:[2,11], 2029:[2,1],  2030:[2,20], 2031:[2,9] } },
      'Ugadi':            { text: '🌿 Happy Ugadi! A new year, and a fresh start.', link: 'https://en.wikipedia.org/wiki/Ugadi',       gradient: 'linear-gradient(90deg,#4A5A3A 0%,#876943 100%)',
                            dates: { 2026:[2,19], 2027:[3,7],  2028:[2,27], 2029:[2,15], 2030:[3,3],  2031:[2,24] } },
      'Raksha Bandhan':   { text: '🧵 Happy Raksha Bandhan.', link: 'https://en.wikipedia.org/wiki/Raksha_Bandhan',                             gradient: 'linear-gradient(90deg,#8B4A3F 0%,#876943 100%)',
                            dates: { 2026:[7,28], 2027:[7,17], 2028:[7,5],  2029:[7,23], 2030:[7,13], 2031:[7,2] } },
      // 2031 Janmashtami is observed on 9 Aug (Smarta) and 10 Aug (ISKCON);
      // the Smarta date is used here.
      'Janmashtami':      { text: '🦚 Happy Krishna Janmashtami.', link: 'https://en.wikipedia.org/wiki/Krishna_Janmashtami',                        gradient: 'linear-gradient(90deg,#2E3A4A 0%,#527281 100%)',
                            dates: { 2026:[8,4],  2027:[7,25], 2028:[7,13], 2029:[8,1],  2030:[7,21], 2031:[7,9] } },
      'Ganesh Chaturthi': { text: '🐘 Happy Ganesh Chaturthi! Ganpati Bappa Morya.', link: 'https://en.wikipedia.org/wiki/Ganesh_Chaturthi',      gradient: 'linear-gradient(90deg,#8B4A3F 0%,#93653B 100%)',
                            dates: { 2026:[8,14], 2027:[8,4],  2028:[7,23], 2029:[8,11], 2030:[8,1],  2031:[8,20] } },
      'Dussehra':         { text: '🏹 Happy Dussehra — may good prevail.', link: 'https://en.wikipedia.org/wiki/Vijayadashami',                gradient: 'linear-gradient(90deg,#6B2E2A 0%,#876943 100%)',
                            dates: { 2026:[9,20], 2027:[9,9],  2028:[8,27], 2029:[9,16], 2030:[9,6],  2031:[9,25] } },
      'Diwali':           { text: '🪔 Happy Diwali! Wishing you light and prosperity.', link: 'https://en.wikipedia.org/wiki/Diwali',   gradient: 'linear-gradient(90deg,#3A2A4A 0%,#876943 100%)',
                            dates: { 2023:[10,12], 2024:[10,1],  2025:[9,21],  2026:[10,8],  2027:[9,29],
                                     2028:[9,17],  2029:[10,5],  2030:[9,26],  2031:[10,14], 2032:[10,2],
                                     2033:[9,22],  2034:[10,10], 2035:[9,30],  2036:[9,19],  2037:[10,7],
                                     2038:[9,27],  2039:[9,17],  2040:[10,4],  2041:[9,25],  2042:[10,12],
                                     2043:[10,1] } }
    };

    function nthWeekdayDate(year, month, weekday, nth) {
      if (nth === -1) {
        var last = new Date(year, month + 1, 0);          // last day of month
        return last.getDate() - ((last.getDay() - weekday + 7) % 7);
      }
      var first = new Date(year, month, 1);
      return 1 + ((weekday - first.getDay() + 7) % 7) + (nth - 1) * 7;
    }

    /* Date-ranged events, with a link. Months are 0-based, like the
       tables above. `to` is the last day the banner shows. */
    var EVENTS = [
      { from: [2026, 9, 6], to: [2026, 11, 4],
        html: '\u26A1 AWS re:Invent 2026 is coming \u2014 ' +
              '<a href="/reinvent-2026/planner/">plan your days</a> ' +
              'from the full session catalog',
        gradient: 'linear-gradient(90deg,#3A4A3F 0%,#8B6A43 100%)' }
    ];

    function inRange(e, y2, mo2, dy2) {
      var t = y2 * 10000 + mo2 * 100 + dy2;
      var a = e.from[0] * 10000 + e.from[1] * 100 + e.from[2];
      var b = e.to[0] * 10000 + e.to[1] * 100 + e.to[2];
      return t >= a && t <= b;
    }

    var today = new Date();
    var y = today.getFullYear(), mo = today.getMonth(), dy = today.getDate();

    var match = FIXED.find(function (o) { return o.month === mo && o.day === dy; });

    if (!match) {
      match = NTH_WEEKDAY.find(function (o) {
        return o.month === mo && nthWeekdayDate(y, o.month, o.weekday, o.nth) === dy;
      });
    }

    if (!match) {
      Object.keys(LUNAR).some(function (name) {
        var f = LUNAR[name], d = f.dates[y];
        if (d && d[0] === mo && d[1] === dy) {
          // link included: this branch rebuilds the match object
          // rather than passing the entry through, so a field added
          // to the table is dropped here unless it is named. That is
          // how all eight lunar festivals -- Diwali and Dussehra
          // among them -- came out with no link on the first pass.
          match = { text: f.text, gradient: f.gradient, link: f.link };
          return true;
        }
        return false;
      });
    }

    // Festivals win. A greeting on somebody's festival should not be
    // replaced by a conference link, and this event overlaps Thanksgiving
    // and the first days of the Christmas run.
    if (!match) {
      match = EVENTS.find(function (e) { return inRange(e, y, mo, dy); });
    }

    if (match) {
      var banner = document.getElementById('occasion-banner');
      banner.style.background = match.gradient;
      banner.style.color = '#F5F5F3';
      // An event carries markup because it carries a link; a festival is a
      // greeting and stays textContent, which is the safer default and is
      // what every entry above relies on.
      if (match.html) {
        banner.innerHTML = match.html;
        // The div's colour does not reach the anchor: an <a> with no colour
        // of its own renders the browser default blue, which on this
        // gradient is both ugly and barely readable. Underlined so it still
        // reads as a link once it is the same colour as the text.
        var link = banner.querySelector('a');
        if (link) {
          link.style.color = 'inherit';
          link.style.textDecoration = 'underline';
          link.style.textUnderlineOffset = '2px';
          link.style.fontWeight = '600';
        }
      } else {
        banner.textContent = match.text;
        // ...and a way to find out what the day actually is.
        //
        // Asked for 2026-10-20: "some sort of hyperlink attached to it so
        // that people can just click it and know significance of that
        // festival". A greeting assumes the reader already knows; roughly
        // half of these are specific to one country, so for most readers
        // most days it is a word they do not have.
        //
        // Built with createElement and textContent rather than by switching
        // this branch to innerHTML. Every entry in the three tables above is
        // written as plain text and relies on being escaped -- an em dash, an
        // apostrophe in "Gong Xi Fa Cai", accented Spanish -- and turning
        // that into markup for the sake of one anchor would make the safe
        // path the unusual one.
        if (match.link) {
          var sep = document.createTextNode('  ');
          var a = document.createElement('a');
          a.href = match.link;
          a.target = '_blank';
          a.rel = 'noopener';
          // Names the subject rather than saying "learn more", which tells a
          // screen-reader user cycling links nothing about where it goes.
          a.textContent = 'why today?';
          a.setAttribute('aria-label', 'Read about this occasion');
          a.style.color = 'inherit';
          a.style.textDecoration = 'underline';
          a.style.textUnderlineOffset = '2px';
          a.style.opacity = '0.85';
          a.style.whiteSpace = 'nowrap';
          banner.appendChild(sep);
          banner.appendChild(a);
        }
      }
      banner.style.display = 'block';

      /* ── Fold it away, for this tab only ────────────────────────────────
         Asked for 2026-10-20: "some sort of option where people can just
         minimize for the time being ... but when they open a different
         window, it has to show default".

         That last clause decides the storage. sessionStorage is per TAB:
         it survives navigating between pages and reloading, and a new tab
         or window starts clean. localStorage would remember the choice
         forever on that device, which is the opposite of what was asked --
         a reader who folded the banner once in March would never see the
         Diwali greeting at all.

         MINIMISE, not dismiss. The banner collapses to a thin strip of its
         own gradient with a chevron on it, so the colour that says "today
         is something" is still there and there is still something to click.
         A close button that removes the element leaves a reader who taps it
         by accident with no way back inside that tab.

         The existing content is moved into a wrapper rather than rebuilt,
         so this knows nothing about whether the banner holds plain text, a
         link, or both. */
      var FOLD_KEY = 'jk-occasion-folded';
      var folded = false;
      try { folded = sessionStorage.getItem(FOLD_KEY) === '1'; } catch (e) {}

      var content = document.createElement('span');
      while (banner.firstChild) content.appendChild(banner.firstChild);
      banner.appendChild(content);

      var chev = document.createElement('button');
      chev.type = 'button';
      chev.setAttribute('style',
        'background:none; border:0; color:inherit; font:inherit; ' +
        'cursor:pointer; padding:0 0 0 .6rem; opacity:.75; ' +
        'line-height:1; vertical-align:baseline;');
      banner.appendChild(chev);

      // The whole strip is the target once it is folded -- a 5px chevron is
      // not a touch target, and there is nothing else on the strip to hit.
      banner.style.cursor = 'pointer';

      var apply = function () {
        content.style.display = folded ? 'none' : '';
        chev.textContent = folded ? '\u25BE' : '\u25B4';
        chev.setAttribute('aria-expanded', folded ? 'false' : 'true');
        chev.setAttribute('aria-label',
          folded ? 'Show today\u2019s occasion' : 'Hide today\u2019s occasion');
        chev.title = chev.getAttribute('aria-label');
        // Thin enough to read as "there is something here, folded", tall
        // enough to stay a touch target.
        banner.style.padding = folded ? '0.15rem 1rem' : '0.5rem 1rem';
        setOffset();
      };

      var setFolded = function (v) {
        folded = v;
        try { sessionStorage.setItem(FOLD_KEY, v ? '1' : '0'); } catch (e) {}
        apply();
      };

      chev.addEventListener('click', function (ev) {
        ev.stopPropagation();
        setFolded(!folded);
      });

      banner.addEventListener('click', function (ev) {
        // A click on the greeting's own link is a click on the link.
        if (ev.target.closest && ev.target.closest('a')) return;
        setFolded(!folded);
      });

      var setOffset = function () {
        document.documentElement.style.setProperty('--occasion-banner-h', banner.offsetHeight + 'px');
      };
      // Measured once immediately and then again after layout settles. The
      // first reading is taken before the webfont has swapped, and the banner
      // text wraps at the fallback metrics -- it measured 143px against a real
      // height of 37px, which pushed the nav a hundred pixels down until the
      // reader happened to resize the window.
      apply();
      setOffset();
      requestAnimationFrame(setOffset);
      if (document.fonts && document.fonts.ready) document.fonts.ready.then(setOffset);
      window.addEventListener('load', setOffset);
      window.addEventListener('resize', setOffset);
    }

    // Falling snow effect during Christmas season (Dec 1 - Dec 26).
    if (today.getMonth() === 11 && today.getDate() <= 26) {
      var snowContainer = document.createElement('div');
      snowContainer.id = 'snowfall';
      snowContainer.setAttribute('aria-hidden', 'true');
      snowContainer.style.position = 'fixed';
      snowContainer.style.top = '0';
      snowContainer.style.left = '0';
      snowContainer.style.width = '100%';
      snowContainer.style.height = '100%';
      snowContainer.style.overflow = 'hidden';
      snowContainer.style.pointerEvents = 'none';
      snowContainer.style.zIndex = '999';
      // Decoration must never break the page. If this runs before the
      // body exists -- which it can, because site-footer.js injects
      // this file and a deferred script can get there first -- there is
      // nothing to attach to and nothing worth throwing over.
      if (!document.body) { return; }
      document.body.appendChild(snowContainer);

      var FLAKE_COUNT = 40;
      for (var i = 0; i < FLAKE_COUNT; i++) {
        var flake = document.createElement('span');
        flake.className = 'snowflake';
        flake.textContent = '❄';
        flake.style.left = (Math.random() * 100) + 'vw';
        flake.style.fontSize = (0.6 + Math.random() * 1.2) + 'rem';
        flake.style.opacity = (0.4 + Math.random() * 0.6).toFixed(2);
        var fallDuration = 8 + Math.random() * 10;
        var swayDuration = 3 + Math.random() * 4;
        flake.style.animation =
          'snowfall-fall ' + fallDuration + 's linear ' + (-Math.random() * fallDuration) + 's infinite, ' +
          'snowfall-sway ' + swayDuration + 's ease-in-out ' + (-Math.random() * swayDuration) + 's infinite alternate';
        snowContainer.appendChild(flake);
      }
    }
  })();
