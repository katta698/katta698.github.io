#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Check that the occasion-banner date tables have not run out.

The banner greets visitors on holidays. Three kinds of date feed it, and only
one of them can go stale:

    FIXED        same Gregorian date every year (Republic Day, 4 July, ...)
    NTH_WEEKDAY  computed ("4th Thursday in November"), so US federal holidays
                 never need a table at all
    LUNAR        Hindu and Chinese festivals follow lunisolar calendars and
                 land on a different Gregorian date each year. These can only
                 be tabled, and a table has an end.

When a LUNAR table runs past its last year the banner simply stops appearing.
Nothing errors, nothing looks broken, and the first sign is someone noticing
there was no Diwali greeting — a year late. This script exists so that failure
is loud and early instead.

    python scripts/validate_occasions.py

WARN when a festival has fewer than WARN_YEARS of runway, ERROR when it has
less than one year. Exits non-zero only on ERROR, so it can gate CI while
still giving a season of notice first.

Top the tables up from drikpanchang.com (Hindu) and a published Chinese New
Year table. Do not extrapolate by hand: leap months make the intervals
irregular, which is exactly the trap that put a wrong Ugadi date in this file
during the first draft.
"""
import io
import os
import re
import sys
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The tables moved out of index.html in Aug 2026, when the banner was extracted
# so it could show on every surface rather than only the home page. This script
# kept reading index.html and printed its own "has the banner been
# restructured?" error on every run from that day -- which is the good outcome
# of the two available, but it means the runway warning it exists to give has
# not been given since. The check that guards a silent failure can fail
# silently too, if nothing reads its output.
PAGE = os.path.join(ROOT, 'blog', 'assets', 'occasion-banner.js')

WARN_YEARS = 3          # start nagging with this much runway left
ERROR_YEARS = 1         # fail the build below this


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    if not os.path.isfile(PAGE):
        print('ERROR occasion-banner.js not found at %s' % PAGE)
        return 1

    html = io.open(PAGE, encoding='utf-8').read()

    m = re.search(r'var LUNAR = \{(.*?)\n    \};', html, re.DOTALL)
    if not m:
        print('ERROR could not find the LUNAR table in %s — has the '
              'banner script been restructured? This check needs updating.'
              % os.path.relpath(PAGE, ROOT))
        return 1
    body = m.group(1)

    # Each festival is  'Name': { ... dates: { 2026:[1,17], 2027:[1,6] ... } }
    festivals = re.findall(r"'([^']+)':\s*\{.*?dates:\s*\{([^}]*)\}", body, re.DOTALL)
    if not festivals:
        print('ERROR the LUNAR table parsed but contained no festivals.')
        return 1

    this_year = datetime.date.today().year
    errors, warnings, rows = [], [], []

    for name, dates in festivals:
        years = sorted(int(y) for y in re.findall(r'(\d{4})\s*:', dates))
        if not years:
            errors.append('%s has no dates at all' % name)
            continue
        last = years[-1]
        runway = last - this_year
        rows.append((name, years[0], last, runway))
        if runway < ERROR_YEARS:
            errors.append('%s runs out after %d (this year is %d) — the banner '
                          'will stop appearing' % (name, last, this_year))
        elif runway < WARN_YEARS:
            warnings.append('%s runs out after %d — only %d year(s) of runway'
                            % (name, last, runway))

    width = max(len(r[0]) for r in rows)
    print('Occasion banner — lunar date tables (current year %d)\n' % this_year)
    for name, first, last, runway in rows:
        print('  %-*s  %d-%d   %2d year(s) left' % (width, name, first, last, runway))

    print('')
    for w in warnings:
        print('WARN  %s' % w)
    for e in errors:
        print('ERROR %s' % e)

    print('\nChecked %d festival(s): %d error(s), %d warning(s)'
          % (len(rows), len(errors), len(warnings)))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
