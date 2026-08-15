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
  el.setAttribute('style', 'display:none; position:fixed; top:0; left:0; width:100%; z-index:1001; text-align:center; padding:0.5rem 1rem; font-size:0.8rem; font-family:\'Inter\',sans-serif; letter-spacing:0.02em;');
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
      { month: 0,  day: 1,  text: '🎉 Happy New Year!',                                         gradient: 'linear-gradient(90deg,#1D2322 0%,#876943 100%)' },
      { month: 0,  day: 26, text: '🎊 Happy Republic Day!',                                     gradient: 'linear-gradient(90deg,#8B5A3C 0%,#5A6B4A 100%)' },
      { month: 5,  day: 19, text: '✊ Juneteenth — commemorating emancipation.',                 gradient: 'linear-gradient(90deg,#3E2A2A 0%,#8B4A3F 100%)' },
      { month: 6,  day: 4,  text: '🎆 Happy 4th of July — wishing you a great Independence Day!', gradient: 'linear-gradient(90deg,#2E3A4A 0%,#8B4A3F 100%)' },
      { month: 7,  day: 15, text: '🎊 Happy Independence Day! Jai Hind.',                        gradient: 'linear-gradient(90deg,#8B5A3C 0%,#5A6B4A 100%)' },
      { month: 4,  day: 25, text: '🎉 Feliz Día de la Revolución de Mayo!',      gradient: 'linear-gradient(90deg,#33505F 0%,#56707E 100%)' },
      { month: 6,  day: 9,  text: '🎉 Feliz Día de la Independencia, Argentina!', gradient: 'linear-gradient(90deg,#33505F 0%,#56707E 100%)' },
      { month: 7,  day: 31, text: '🎉 Selamat Hari Merdeka, Malaysia!',            gradient: 'linear-gradient(90deg,#2E3A4A 0%,#8B6B3F 100%)' },
      { month: 8,  day: 16, text: '🤝 Happy Malaysia Day!',                        gradient: 'linear-gradient(90deg,#2E3A4A 0%,#7A6A55 100%)' },
      { month: 9,  day: 2,  text: '🕊️ Gandhi Jayanti — remembering the Mahatma.',                gradient: 'linear-gradient(90deg,#3A4A3F 0%,#627358 100%)' },
      { month: 9,  day: 31, text: '🎃 Happy Halloween!',                                         gradient: 'linear-gradient(90deg,#6B3A1F 0%,#241E1A 100%)' },
      { month: 10, day: 11, text: '🎖️ Veterans Day — thank you to all who served.',              gradient: 'linear-gradient(90deg,#2E3A4A 0%,#6B5A47 100%)' },
      // Days that mark what this site is about rather than a holiday:
      // forests, oceans, mountains, music, photography, and two that are
      // not celebrations at all. Worded soberly for that reason.
      { month: 2 , day: 21, text: '🌲 International Day of Forests.', gradient: 'linear-gradient(90deg,#3A4A3F 0%,#5A6B4A 100%)' },
      { month: 3 , day: 22, text: '🌍 Earth Day — one planet, borrowed.', gradient: 'linear-gradient(90deg,#2E4A3A 0%,#627358 100%)' },
      { month: 5 , day: 8 , text: '🌊 World Oceans Day.', gradient: 'linear-gradient(90deg,#2E3A4A 0%,#3E6070 100%)' },
      { month: 5 , day: 21, text: '🎻 World Music Day.', gradient: 'linear-gradient(90deg,#4A3A5C 0%,#876943 100%)' },
      { month: 6 , day: 30, text: '🕯️ World Day Against Trafficking in Persons.', gradient: 'linear-gradient(90deg,#2A2A35 0%,#5A4A6B 100%)' },
      { month: 7 , day: 19, text: '📷 World Photography Day.', gradient: 'linear-gradient(90deg,#2E3635 0%,#6B5A47 100%)' },
      { month: 11, day: 10, text: '⚖️ Human Rights Day.', gradient: 'linear-gradient(90deg,#3E2A2A 0%,#8B4A3F 100%)' },
      { month: 11, day: 11, text: '⛰️ International Mountain Day.', gradient: 'linear-gradient(90deg,#2E3A4A 0%,#55677E 100%)' },
      { month: 11, day: 25, text: '🎄 Merry Christmas & Happy Holidays!',                        gradient: 'linear-gradient(90deg,#2E4A3A 0%,#7A3B34 100%)' }
    ];

    // month, weekday (0=Sun), nth (-1 = last of the month)
    var NTH_WEEKDAY = [
      { month: 0,  weekday: 1, nth: 3,  text: '✊ Martin Luther King Jr. Day.',                   gradient: 'linear-gradient(90deg,#2A2A35 0%,#5A4A6B 100%)' },
      { month: 1,  weekday: 1, nth: 3,  text: '🏛️ Presidents Day.',                              gradient: 'linear-gradient(90deg,#2E3A4A 0%,#55677E 100%)' },
      { month: 4,  weekday: 1, nth: -1, text: '🌺 Memorial Day — remembering those who served.',  gradient: 'linear-gradient(90deg,#2E3A4A 0%,#5A6B4A 100%)' },
      { month: 8,  weekday: 1, nth: 1,  text: '🛠️ Happy Labor Day!',                              gradient: 'linear-gradient(90deg,#2E3635 0%,#826A4F 100%)' },
      { month: 10, weekday: 4, nth: 4,  text: '🦃 Happy Thanksgiving!',                           gradient: 'linear-gradient(90deg,#6B3F24 0%,#876943 100%)' }
    ];

    // year -> [month, day]. month is 0-indexed, matching JS Date.
    var LUNAR = {
      'Chinese New Year': { text: '🧧 Gong Xi Fa Cai — Happy Lunar New Year!', gradient: 'linear-gradient(90deg,#6B2E2A 0%,#93653B 100%)',
                            dates: { 2026:[1,17], 2027:[1,6],  2028:[0,26], 2029:[1,13], 2030:[1,3],  2031:[0,23] } },
      'Holi':             { text: '🎨 Happy Holi! Wishing you a year full of colour.',    gradient: 'linear-gradient(90deg,#8B4A3F 0%,#876943 50%,#5A6B4A 100%)',
                            dates: { 2026:[2,4],  2027:[2,22], 2028:[2,11], 2029:[2,1],  2030:[2,20], 2031:[2,9] } },
      'Ugadi':            { text: '🌿 Happy Ugadi! A new year, and a fresh start.',       gradient: 'linear-gradient(90deg,#4A5A3A 0%,#876943 100%)',
                            dates: { 2026:[2,19], 2027:[3,7],  2028:[2,27], 2029:[2,15], 2030:[3,3],  2031:[2,24] } },
      'Raksha Bandhan':   { text: '🧵 Happy Raksha Bandhan.',                             gradient: 'linear-gradient(90deg,#8B4A3F 0%,#876943 100%)',
                            dates: { 2026:[7,28], 2027:[7,17], 2028:[7,5],  2029:[7,23], 2030:[7,13], 2031:[7,2] } },
      // 2031 Janmashtami is observed on 9 Aug (Smarta) and 10 Aug (ISKCON);
      // the Smarta date is used here.
      'Janmashtami':      { text: '🦚 Happy Krishna Janmashtami.',                        gradient: 'linear-gradient(90deg,#2E3A4A 0%,#527281 100%)',
                            dates: { 2026:[8,4],  2027:[7,25], 2028:[7,13], 2029:[8,1],  2030:[7,21], 2031:[7,9] } },
      'Ganesh Chaturthi': { text: '🐘 Happy Ganesh Chaturthi! Ganpati Bappa Morya.',      gradient: 'linear-gradient(90deg,#8B4A3F 0%,#93653B 100%)',
                            dates: { 2026:[8,14], 2027:[8,4],  2028:[7,23], 2029:[8,11], 2030:[8,1],  2031:[8,20] } },
      'Dussehra':         { text: '🏹 Happy Dussehra — may good prevail.',                gradient: 'linear-gradient(90deg,#6B2E2A 0%,#876943 100%)',
                            dates: { 2026:[9,20], 2027:[9,9],  2028:[8,27], 2029:[9,16], 2030:[9,6],  2031:[9,25] } },
      'Diwali':           { text: '🪔 Happy Diwali! Wishing you light and prosperity.',   gradient: 'linear-gradient(90deg,#3A2A4A 0%,#876943 100%)',
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
          match = { text: f.text, gradient: f.gradient };
          return true;
        }
        return false;
      });
    }

    if (match) {
      var banner = document.getElementById('occasion-banner');
      banner.style.background = match.gradient;
      banner.style.color = '#F5F5F3';
      banner.textContent = match.text;
      banner.style.display = 'block';
      var setOffset = function () {
        document.documentElement.style.setProperty('--occasion-banner-h', banner.offsetHeight + 'px');
      };
      // Measured once immediately and then again after layout settles. The
      // first reading is taken before the webfont has swapped, and the banner
      // text wraps at the fallback metrics -- it measured 143px against a real
      // height of 37px, which pushed the nav a hundred pixels down until the
      // reader happened to resize the window.
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
