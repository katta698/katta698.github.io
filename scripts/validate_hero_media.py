#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Check the hero's clip counts against the files that actually exist.

blog/assets/hero-media.js carries a COUNTS map — how many clips each theme has — because the
browser cannot list a directory. The day-of-week index wraps on that number, so
if it disagrees with reality the hero asks for a file that isn't there.

That failure is quiet. The video element falls back to ocean, the page looks
fine, and the only symptom is a theme silently never showing. This script makes
the drift loud instead.

    python scripts/validate_hero_media.py

Checks, per theme:
  * every clip from 1..COUNT exists, with no gaps
  * no extra clips sit on disk above COUNT (added but never counted)
  * clips are within a sane size — the sources are 4K masters and it is easy
    to commit one by accident

A theme declared 0 is intentional: it has no clips yet and falls back. Only a
mismatch is an error.
"""
import io
import os
import re
import sys
import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The rotation moved out of index.html into a shared file so the home page
# and the blog pages could not drift apart; COUNTS and PLAN live there now.
PAGE = os.path.join(ROOT, 'blog', 'assets', 'hero-media.js')
VIDEOS = os.path.join(ROOT, 'blog', 'assets', 'videos')

MAX_MB = 8.0        # a 12s 1080p CRF-28 loop lands well under this

errors, warnings = [], []


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    html = io.open(PAGE, encoding='utf-8').read()
    m = re.search(r'var COUNTS = \{([^}]*)\}', html)
    if not m:
        print('ERROR no COUNTS map found in blog/assets/hero-media.js')
        return 1
    counts = {k: int(v) for k, v in re.findall(r'(\w+)\s*:\s*(\d+)', m.group(1))}

    plan = re.search(r'var PLAN = \[(.*?)\];', html, re.DOTALL)
    planned = set(re.findall(r"'(\w+)'", plan.group(1))) if plan else set()

    print('%-11s %8s %8s   %s' % ('theme', 'declared', 'on disk', 'notes'))
    total = 0.0
    for theme in sorted(set(list(counts) + list(planned))):
        declared = counts.get(theme)
        found = sorted(int(re.search(r'-(\d+)\.mp4$', f).group(1))
                       for f in glob.glob(os.path.join(VIDEOS, '%s-*.mp4' % theme)))
        note = ''
        if declared is None:
            errors.append('%s appears in PLAN but has no COUNTS entry' % theme)
            note = 'MISSING from COUNTS'
        else:
            expected = list(range(1, declared + 1))
            missing = [n for n in expected if n not in found]
            extra = [n for n in found if n > declared]
            if missing:
                errors.append('%s: COUNTS says %d but %s missing'
                              % (theme, declared, ', '.join('%s-%d.mp4' % (theme, n) for n in missing)))
                note = 'missing %d' % len(missing)
            if extra:
                errors.append('%s: %d clip(s) on disk above the declared count — '
                              'bump COUNTS or they will never be shown'
                              % (theme, len(extra)))
                note = (note + ' ' if note else '') + 'uncounted %d' % len(extra)
            if declared == 0 and not found:
                note = 'intentionally empty, falls back'
        for f in glob.glob(os.path.join(VIDEOS, '%s-*.mp4' % theme)):
            mb = os.path.getsize(f) / 1048576
            total += mb
            if mb > MAX_MB:
                warnings.append('%s is %.1f MB — larger than a web loop should be'
                                % (os.path.basename(f), mb))
        print('%-11s %8s %8d   %s' % (theme, declared if declared is not None else '-',
                                      len(found), note))

    print('\ntotal hero video on disk: %.1f MB' % total)
    print('')
    for w in warnings:
        print('WARN  %s' % w)
    for e in errors:
        print('ERROR %s' % e)
    print('\n%d error(s), %d warning(s)' % (len(errors), len(warnings)))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
