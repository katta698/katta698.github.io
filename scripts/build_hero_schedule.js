/* Build a year's hero + banner schedule as a reference page.
 *
 *   node scripts/build_hero_schedule.js            # 365 days from today
 *   node scripts/build_hero_schedule.js 2027-01-01 # from a given date
 *
 * Output: _schedule/hero-schedule.html
 *
 * The point of this script is that it *runs* the real code rather than
 * re-implementing it. blog/assets/hero-media.js and the occasion-banner block
 * inside index.html are evaluated against a stubbed DOM with the clock moved
 * to each date in turn, so the page cannot drift from what the site actually
 * does. A hand-maintained schedule would be wrong the first time a clip count
 * or a plan entry changed.
 *
 * Underscore-prefixed directories are ignored by GitHub Pages' Jekyll build,
 * so _schedule/ is committed but never served — this is a reference for
 * Jayanth, not a page for readers.
 */
'use strict';
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const OUT_DIR = path.join(ROOT, '_schedule');
const RealDate = Date;
// Clip and audio names link to the live site so any of them can be seen in
// context — the schedule says what plays when, the link shows you it.
const LIVE = 'https://jayanthkatta.com';

const heroSrc = fs.readFileSync(path.join(ROOT, 'blog', 'assets', 'hero-media.js'), 'utf8');

// The banner still lives inline in index.html; pull just that IIFE out.
const indexHtml = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
const bStart = indexHtml.indexOf('<div id="occasion-banner"');
const bannerSrc = indexHtml.slice(indexHtml.indexOf('<script>', bStart) + 8,
                                 indexHtml.indexOf('</script>', bStart));

function withClock(y, m, d, fn) {
  class Frozen extends RealDate {
    constructor(...a) { if (!a.length) super(y, m, d, 12); else super(...a); }
    static now() { return new RealDate(y, m, d, 12).getTime(); }
  }
  global.Date = Frozen;
  try { return fn(); } catch (e) { return { err: e.message }; }
  finally { global.Date = RealDate; }
}

function hero(y, m, d) {
  const el = () => ({ _s: '', set src(v) { this._s = v; }, get src() { return this._s; },
                      dataset: {}, addEventListener() {}, load() {},
                      play() { return Promise.resolve(); }, paused: false });
  const v = el(), a = el();
  global.document = { getElementById: id => id === 'hero-video' ? v : (id === 'beach-audio' ? a : null),
                      addEventListener() {}, hidden: false };
  global.location = { search: '' };
  global.window = { addEventListener() {}, location: global.location };
  return withClock(y, m, d, () => {
    eval(heroSrc);
    return { theme: global.window.__heroTheme.theme, week: global.window.__heroTheme.week,
             clip: v.src.split('/').pop(), audio: a.src.split('/').pop() };
  });
}

function banner(y, m, d) {
  let shown = null;
  const el = { style: {}, offsetHeight: 30,
               set textContent(t) { shown = t; }, get textContent() { return shown; } };
  global.document = { getElementById: () => el,
                      createElement: () => ({ style: {}, setAttribute() {}, appendChild() {}, classList: { add() {} } }),
                      body: { appendChild() {} }, documentElement: { style: { setProperty() {} } },
                      head: { appendChild() {} } };
  global.window = { addEventListener() {}, matchMedia: () => ({ matches: false, addEventListener() {} }) };
  withClock(y, m, d, () => { eval(bannerSrc); });
  return shown;
}

const MON = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const DOW = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
const COL = { ocean:'#3a5a6b', mountains:'#4a5568', forest:'#4a5a3a',
              rain:'#3e4a5c', sunset:'#8b5a3c', boho:'#6b5a47' };

const arg = process.argv[2];
const start = arg ? new RealDate(arg + 'T12:00:00') : new RealDate();
const days = [];
for (let i = 0; i < 365; i++) {
  const dt = new RealDate(start.getTime() + i * 86400000);
  const h = hero(dt.getFullYear(), dt.getMonth(), dt.getDate());
  if (h.err) { console.error('hero failed on ' + dt.toDateString() + ': ' + h.err); process.exit(1); }
  days.push({ dow: DOW[dt.getDay()],
              label: dt.getDate() + ' ' + MON[dt.getMonth()],
              week: h.week, theme: h.theme,
              clip: h.clip.replace(/\.mp4$/, ''),   // full name, e.g. rain-4 — a bare
                                                    // index next to a named audio
                                                    // column reads as the wrong thing
              audio: h.audio.replace(/\.mp3$/, ''),
              banner: banner(dt.getFullYear(), dt.getMonth(), dt.getDate()) });
}

// group consecutive days that share a theme-week
const weeks = [];
let cur = null;
for (const d of days) {
  if (!cur || cur.theme !== d.theme || cur.week !== d.week) {
    cur = { week: d.week, theme: d.theme, days: [], audio: new Set() };
    weeks.push(cur);
  }
  cur.days.push(d); cur.audio.add(d.audio);
}

const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
const counts = {}; days.forEach(d => counts[d.theme] = (counts[d.theme] || 0) + 1);
const bannerDays = days.filter(d => d.banner).length;

const rows = weeks.map(w => `<tr>
    <td class="wk">${w.week}</td>
    <td class="dt">${w.days[0].label} &ndash; ${w.days[w.days.length - 1].label}</td>
    <td><span class="th" style="background:${COL[w.theme]}">${w.theme}</span></td>
    <td class="clips">${w.days.map(d => `<a class="d" target="_blank" href="${LIVE}/?theme=${w.theme}&clip=${d.clip.split('-')[1]}"><i>${d.dow}</i>${d.clip}</a>`).join('')}</td>
    <td class="au">${w.audio.size === 1
        ? `<a target="_blank" href="${LIVE}/?theme=${w.theme}&audio=${[...w.audio][0].split('-')[1]}">${[...w.audio][0]}.mp3</a>`
        : w.days.map(d => `<a class="d" target="_blank" href="${LIVE}/?theme=${w.theme}&audio=${d.audio.split('-')[1]}"><i>${d.dow}</i>${d.audio}</a>`).join('')}</td>
    <td class="bn">${w.days.filter(d => d.banner)
        .map(d => `<div class="ban"><b>${d.label}</b> ${esc(d.banner)}</div>`).join('') || '<span class="none">—</span>'}</td>
  </tr>`).join('');

const legend = Object.entries(counts).sort((a, b) => b[1] - a[1])
  .map(([t, n]) => `<span class="lg"><i style="background:${COL[t]}"></i>${t} <b>${n}</b> days</span>`).join('');

const from = days[0].label + ' ' + start.getFullYear();
const to = days[364].label + ' ' + new RealDate(start.getTime() + 364 * 86400000).getFullYear();

fs.mkdirSync(OUT_DIR, { recursive: true });
fs.writeFileSync(path.join(OUT_DIR, 'hero-schedule.html'), `<!doctype html><meta charset="utf-8">
<title>Hero schedule — ${from} to ${to}</title>
<style>
 body{margin:0;padding:26px;background:#1D2322;color:#F5F5F3;font:14px/1.5 'DM Sans',system-ui,sans-serif}
 h1{font-size:1.25rem;margin:0 0 .2rem}
 .sub{color:#A3ABA9;font-size:.83rem;margin-bottom:1rem;max-width:80ch}
 .legend{display:flex;flex-wrap:wrap;gap:14px;margin-bottom:1.2rem;font-size:.78rem;color:#C9CDC9}
 .lg i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:-1px}
 .lg b{color:#C4A484}
 table{border-collapse:collapse;width:100%;font-size:.8rem}
 th{text-align:left;color:#7E8584;font:600 .68rem 'Courier New',monospace;letter-spacing:.08em;
    text-transform:uppercase;padding:6px 8px;border-bottom:1px solid #2E3635;position:sticky;top:0;background:#1D2322}
 td{padding:7px 8px;border-bottom:1px solid #242B2A;vertical-align:top}
 tr:hover td{background:#242B2A}
 .wk{color:#7E8584;font:400 .74rem 'Courier New',monospace;width:34px}
 .dt{color:#C9CDC9;white-space:nowrap;width:112px}
 .th{display:inline-block;padding:2px 9px;border-radius:3px;font-size:.74rem;text-transform:capitalize}
 .clips{white-space:nowrap}
 .d{display:inline-block;text-align:center;margin-right:7px;font:400 .7rem 'Courier New',monospace;color:#C9CDC9;
    text-decoration:none;border-bottom:1px dotted #3a4342;padding-bottom:1px}
 .d:hover{color:#C4A484;border-bottom-color:#C4A484}
 .d i{display:block;font-style:normal;font-size:.6rem;color:#5c6360}
 .au{color:#A3ABA9;font:400 .72rem 'Courier New',monospace;white-space:nowrap}
 .au a{color:#A3ABA9;text-decoration:none;border-bottom:1px dotted #3a4342}
 .au a:hover{color:#C4A484;border-bottom-color:#C4A484}
 .bn{width:22%} .ban{margin-bottom:2px;font-size:.76rem;color:#C4A484}
 .ban b{color:#F5F5F3;font-weight:600;margin-right:4px}
 .none{color:#3a4342}
</style>
<h1>Hero schedule &mdash; ${from} to ${to}</h1>
<div class="sub">Generated by <code>scripts/build_hero_schedule.js</code>, which runs the real rotation and
banner code against every date rather than re-implementing them. Regenerate after changing clip counts,
the week plan, or the occasion list. The week picks the theme; the day picks the clip within it; audio
changes each time a theme comes round rather than daily. <b>Every clip and track name is a link</b> &mdash; it opens the live home page showing exactly that clip or playing that track.</div>
<div class="legend">${legend}<span class="lg">${bannerDays} banner days</span></div>
<table><thead><tr><th>wk</th><th>dates</th><th>theme</th><th>video &mdash; changes daily</th><th>audio &mdash; holds all week</th><th>occasion banner</th></tr></thead>
<tbody>${rows}</tbody></table>`);

console.log(`_schedule/hero-schedule.html — ${from} to ${to}`);
console.log(`  ${weeks.length} week rows · ${bannerDays} banner days`);
console.log(`  ${new Set(days.map(d => d.theme + d.clip)).size} distinct clips · ${new Set(days.map(d => d.audio)).size} distinct audio`);
