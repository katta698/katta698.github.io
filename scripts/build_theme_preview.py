#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build a reference page showing every hero clip and audio track.

    python scripts/build_theme_preview.py

Output: _schedule/hero-themes.html

Companion to build_hero_schedule.js. That one answers "what plays when"; this
one answers "what have I actually got". Regenerate after adding or removing
clips or tracks — it reads COUNTS and AUDIO_COUNTS from hero-media.js and the
original filenames from CREDITS.md, so it cannot list something that is not
really there.

Media is referenced with relative paths (../blog/assets/...) so the page works
opened straight off disk, without a local server.

_schedule/ is underscore-prefixed and therefore ignored by GitHub Pages' Jekyll
build, so this is committed for reference but never published.
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERO = os.path.join(ROOT, 'blog', 'assets', 'hero-media.js')
CRED = os.path.join(ROOT, 'CREDITS.md')
OUT = os.path.join(ROOT, '_schedule', 'hero-themes.html')

ORDER = ['ocean', 'mountains', 'forest', 'rain', 'sunset', 'boho']
COL = {'ocean': '#3a5a6b', 'mountains': '#4a5568', 'forest': '#4a5a3a',
       'rain': '#3e4a5c', 'sunset': '#8b5a3c', 'boho': '#6b5a47'}


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    js = io.open(HERO, encoding='utf-8').read()

    def counts(name):
        m = re.search(r'var %s = \{([^}]*)\}' % name, js)
        return {k: int(v) for k, v in re.findall(r'(\w+)\s*:\s*(\d+)', m.group(1))}

    C, A = counts('COUNTS'), counts('AUDIO_COUNTS')
    plan = re.findall(r"'(\w+)'", re.search(r'var PLAN = \[(.*?)\];', js, re.S).group(1))
    weeks = {t: plan.count(t) for t in C}

    # Original filenames, so a track is identifiable as "sitar" rather than
    # "boho-1" — the whole point of looking at this page.
    cred = io.open(CRED, encoding='utf-8').read()
    orig = dict(re.findall(r'\| `([a-z]+-\d)\.mp3` \| [^|]+ \| `([^`]+)` \|', cred))

    def nice(key):
        s = re.sub(r'^\d+-|-\d+\.mp3$|\.mp3$', '', orig.get(key, ''))
        return s.replace('-', ' ')[:46] or key

    sections = []
    for t in ORDER:
        clips = ''.join(
            '<div class="clip"><video src="../blog/assets/videos/{t}-{i}.mp4" autoplay muted '
            'loop playsinline preload="metadata"></video><span>{t}-{i}</span></div>'.format(t=t, i=i)
            for i in range(1, C[t] + 1))
        tracks = ''.join(
            '<div class="tr"><span class="nm">{t}-{i}</span><span class="src">{d}</span>'
            '<audio controls preload="none" src="../blog/assets/audio/{t}-{i}.mp3"></audio></div>'
            .format(t=t, i=i, d=nice('%s-%d' % (t, i)))
            for i in range(1, A[t] + 1))
        sections.append(
            '\n<section>\n  <div class="head"><h2 style="color:{c}">{t}</h2>'
            '<div class="stat"><b>{nc}</b> clips &nbsp;·&nbsp; <b>{na}</b> track{s} &nbsp;·&nbsp; '
            '<b>{w}</b> weeks a year</div></div>\n'
            '  <div class="clips">{clips}</div>\n  <div class="auds">{tracks}</div>\n</section>'
            .format(c=COL[t], t=t, nc=C[t], na=A[t], s='' if A[t] == 1 else 's',
                    w=weeks[t], clips=clips, tracks=tracks))

    html = """<!doctype html><meta charset="utf-8"><title>Hero themes — what is live</title>
<style>
 body{margin:0;padding:26px;background:#1D2322;color:#F5F5F3;font:15px/1.5 'DM Sans',system-ui,sans-serif}
 h1{font-size:1.3rem;margin:0 0 .2rem}
 .sub{color:#A3ABA9;font-size:.83rem;margin-bottom:1.4rem;max-width:78ch}
 section{background:#242B2A;border-radius:6px;padding:16px;margin-bottom:14px}
 .head{display:flex;align-items:baseline;gap:16px;flex-wrap:wrap;margin-bottom:.8rem}
 h2{font-size:1rem;margin:0;text-transform:capitalize}
 .stat{font-size:.8rem;color:#A3ABA9} .stat b{color:#C9CDC9}
 .clips{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:.9rem}
 .clip{position:relative;width:184px;line-height:0;border-radius:4px;overflow:hidden;background:#11140F}
 .clip video{width:100%;display:block;aspect-ratio:16/9;object-fit:cover}
 .clip span{position:absolute;left:6px;bottom:5px;font:600 .66rem 'Courier New',monospace;color:#F5F5F3;
   background:rgba(29,35,34,.78);padding:1px 6px;border-radius:2px;line-height:1.5}
 .auds{border-top:1px solid #2E3635;padding-top:.7rem;display:flex;flex-direction:column;gap:6px}
 .tr{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
 .nm{font:600 .72rem 'Courier New',monospace;color:#C4A484;width:92px}
 .src{font-size:.75rem;color:#7E8584;width:290px}
 audio{height:30px;width:250px}
</style>
<h1>Hero themes &mdash; what is live</h1>
<div class="sub">Every clip and every track currently deployed. Clips autoplay; the observer below
pauses whatever scrolls out of view so fifty videos do not decode at once. Audio is off by default on
the site &mdash; these players are for auditioning. Video changes daily within a theme week; audio
changes each time the theme comes round. Regenerate with
<code>python scripts/build_theme_preview.py</code>.</div>
__SECTIONS__
<script>
// Autoplay is set on the elements themselves, and this only pauses what has
// scrolled away. Written this way round on purpose: if the observer never fires
// the clips still play, whereas observer-to-start would leave the page black.
if ('IntersectionObserver' in window) {
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting) { e.target.play().catch(function () {}); }
      else { e.target.pause(); }
    });
  }, { rootMargin: '300px 0px', threshold: 0.01 });
  document.querySelectorAll('.clip video').forEach(function (v) { io.observe(v); });
}
</script>""".replace('__SECTIONS__', ''.join(sections))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, 'w', encoding='utf-8', newline='\n').write(html)

    missing = [p for t in ORDER for p in
               ([os.path.join(ROOT, 'blog', 'assets', 'videos', '%s-%d.mp4' % (t, i)) for i in range(1, C[t] + 1)] +
                [os.path.join(ROOT, 'blog', 'assets', 'audio', '%s-%d.mp3' % (t, i)) for i in range(1, A[t] + 1)])
               if not os.path.isfile(p)]
    print('_schedule/hero-themes.html — %d clips, %d tracks across %d themes'
          % (sum(C.values()), sum(A.values()), len(ORDER)))
    if missing:
        print('ERROR referenced but not on disk:')
        for p in missing:
            print('   ' + os.path.relpath(p, ROOT))
        return 1
    print('  every referenced file exists')
    return 0


if __name__ == '__main__':
    sys.exit(main())
