#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Check diagram SVGs for text that runs outside the canvas.

SVG <text> does not wrap. A line longer than the space available does not
reflow — it runs straight off the edge and is clipped by the viewBox, silently.
It renders fine in an editor at full width and breaks on the published page,
which is exactly how it reaches production unnoticed.

    python scripts/validate_diagrams.py            # all diagrams
    python scripts/validate_diagrams.py <file>...  # specific ones

Width is estimated, not measured: there is no font engine here, so each glyph
is charged a fixed fraction of the font size taken from the class's declared
font shorthand. That is accurate to roughly a few percent for the two families
used on this site, which is enough to separate "comfortably inside" from "half
a sentence over the edge". Because it is an estimate, findings are graded:

    ERROR   estimated to exceed the canvas by more than TOLERANCE — real
    WARN    within TOLERANCE of the edge — cannot be called either way by
            estimate alone, so look at it

Exits non-zero only on ERROR, so it can gate CI without failing on the
borderline cases that estimation cannot resolve.
"""
import io
import os
import re
import sys
import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIAGRAMS = os.path.join(ROOT, 'blog', 'assets', 'diagrams')

# Fraction of font-size consumed per character, by weight. Derived by fitting
# against the DM Sans / system-ui stack actually used in these files.
FACTOR = {'400': 0.505, '500': 0.520, '600': 0.545, '700': 0.565}
MONO_FACTOR = 0.601          # Courier New is metrically fixed at 0.6em
RIGHT_MARGIN = 8             # px of gutter a line must leave at the right edge
TOLERANCE = 0.04             # within 4% of the edge is unresolvable by estimate

errors = []
warnings = []


def class_metrics(svg):
    """Map CSS class name -> (font_size, weight, is_monospace).

    Only the `font:` shorthand is parsed, because that is what these diagrams
    use. A class without one falls back to the caller's default.
    """
    out = {}
    for m in re.finditer(r'\.([A-Za-z0-9_-]+)\s*\{([^}]*)\}', svg):
        name, body = m.group(1), m.group(2)
        f = re.search(r'font:\s*(\d+)?\s*([\d.]+)px\s*([^;}]*)', body)
        if not f:
            continue
        weight = f.group(1) or '400'
        size = float(f.group(2))
        family = f.group(3)
        mono = 'monospace' in family or 'Courier' in family
        out[name] = (size, weight, mono)
    return out


def visible_text(inner):
    """Strip markup and normalise entities to one glyph each.

    Entities matter: '&#8212;' is seven characters of source and one glyph on
    screen. Counting the source would overstate every line containing a dash.
    """
    txt = re.sub(r'<[^>]+>', '', inner)
    txt = re.sub(r'&#\d+;', 'X', txt)
    txt = re.sub(r'&[a-zA-Z]+;', 'X', txt)
    return ' '.join(txt.split())


def check(path):
    name = os.path.basename(path)
    svg = io.open(path, encoding='utf-8').read()

    vb = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
    if not vb:
        errors.append('%s: no viewBox — cannot size the canvas' % name)
        return
    width = float(vb.group(1))
    metrics = class_metrics(svg)
    limit = width - RIGHT_MARGIN

    for m in re.finditer(r'<text([^>]*)>(.*?)</text>', svg, re.S):
        attrs, inner = m.group(1), m.group(2)
        xm = re.search(r'\bx="([\d.]+)"', attrs)
        if not xm:
            continue                      # positioned some other way; skip
        x = float(xm.group(1))
        anchor = 'start'
        am = re.search(r'text-anchor="(middle|end)"', attrs)
        if am:
            anchor = am.group(1)

        cm = re.search(r'class="([^"]+)"', attrs)
        size, weight, mono = metrics.get(cm.group(1) if cm else '', (11.0, '400', False))

        # Inline presentation attributes win over the class. The older diagrams
        # set font-size on the element rather than in a class, and assuming the
        # 11px default for those overstates their width by a fifth — enough to
        # invent overflows that are not there.
        fs = re.search(r'\bfont-size="([\d.]+)"', attrs)
        if fs:
            size = float(fs.group(1))
        fw = re.search(r'\bfont-weight="(\d+|bold)"', attrs)
        if fw:
            weight = '700' if fw.group(1) == 'bold' else fw.group(1)
        ff = re.search(r'\bfont-family="([^"]+)"', attrs)
        if ff:
            mono = 'monospace' in ff.group(1) or 'Courier' in ff.group(1)

        factor = MONO_FACTOR if mono else FACTOR.get(weight, 0.505)

        txt = visible_text(inner)
        if not txt:
            continue
        w = len(txt) * size * factor

        # The anchor decides which end of the run x refers to. Centred labels
        # can overflow on the left as readily as the right, and an end-anchored
        # one only ever overflows left, so both edges have to be checked.
        if anchor == 'middle':
            left, right = x - w / 2.0, x + w / 2.0
        elif anchor == 'end':
            left, right = x - w, x
        else:
            left, right = x, x + w

        overshoot = max(right - limit, RIGHT_MARGIN - left)
        if overshoot <= 0:
            continue

        edge = 'right' if (right - limit) >= (RIGHT_MARGIN - left) else 'left'
        over = overshoot / width
        msg = ('%s: text overruns the %s edge by ~%dpx on a %dpx canvas '
               '(%+.0f%%) — "%s"' % (name, edge, overshoot, width, over * 100, txt[:60]))
        (errors if over > TOLERANCE else warnings).append(msg)


def main():
    # Findings quote the diagram text, which contains em dashes and arrows.
    # The default Windows console codepage is cp1252 and raises on those, so
    # the script would die printing its own results.
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    args = sys.argv[1:]
    paths = args if args else sorted(glob.glob(os.path.join(DIAGRAMS, '*.svg')))
    if not paths:
        print('No diagrams found.')
        return 0

    for p in paths:
        check(p)

    for w in warnings:
        print('WARN  %s' % w)
    for e in errors:
        print('ERROR %s' % e)

    print('\nChecked %d diagram(s): %d error(s), %d warning(s)'
          % (len(paths), len(errors), len(warnings)))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
