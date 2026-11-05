#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Find text that collides or escapes its box in a post's architecture diagram.

    python scripts/check_diagram_layout.py              # every AWS lab post
    python scripts/check_diagram_layout.py week-18      # one post
    python scripts/check_diagram_layout.py --self-test

WHY THIS EXISTS (2026-10-30)
----------------------------
Jay reviewed week 25's diagram at full size and found a step circle sitting on
a service's sub-label and a connector ending in empty space. aws_arch.py grew
an assert_clean() for diagrams it generates -- but sixteen published lab posts
carry diagrams drawn by hand, before that existed, and nobody has looked at
them at full size since the day they were written.

This reads the SVG rather than the picture. For every <text> it estimates a
box from the font size, the string, and the anchor, then reports:

  * two texts overlapping each other
  * a text crossing the edge of a <rect> it is NOT inside -- the "words coming
    out of the box" case
  * a text outside the diagram's own viewBox

It is deliberately approximate. Character widths vary by glyph and the real
answer needs a renderer, so the estimate runs slightly WIDE: a check for
collisions should rather name a near-miss than stay quiet about a hit. Treat
the output as a list of places to look, not a verdict.
"""
from __future__ import annotations

import argparse
import html
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
POSTS = os.path.join(os.path.dirname(HERE), "posts")

# Average advance width as a fraction of font-size, for the sans-serif stacks
# these diagrams use. Measured against the rendered week-25 card: "API Gateway"
# at 11.5px occupies 63px, which is 0.55. Bold runs a little wider.
NARROW, BOLD = 0.55, 0.60


def _f(s, default=0.0):
    try:
        return float(s)
    except (TypeError, ValueError):
        return default


def texts(svg: str):
    """Every <text> as (x1, y1, x2, y2, content)."""
    out = []
    for m in re.finditer(r"<text\b([^>]*)>(.*?)</text>", svg, re.S):
        attrs, body = m.group(1), m.group(2)
        # Decode entities FIRST. Measuring the source text counts "&#183;" as
        # six characters and "&nbsp;" as six, which inflated every estimate and
        # produced a page of collisions that do not exist on screen.
        content = html.unescape(re.sub(r"<[^>]+>", "", body))
        content = re.sub(r"\s+", " ", content).strip()
        if not content:
            continue
        x = _f((re.search(r'\bx="([^"]+)"', attrs) or [None, "0"])[1])
        y = _f((re.search(r'\by="([^"]+)"', attrs) or [None, "0"])[1])

        size = 12.0
        fs = re.search(r"font-size[:=]\"?\s*([0-9.]+)", attrs)
        if fs:
            size = _f(fs.group(1), 12.0)
        else:
            cls = re.search(r'class="([^"]+)"', attrs)
            if cls:
                # Both spellings are in use across the series: the "font:"
                # shorthand and a plain "font-size:". Reading only the first
                # left every class-styled label at the 12px default, which
                # over-measured them by up to 15% and reported strikes that
                # are not on the page.
                rule = re.search(r"\.%s\s*\{([^}]*)\}" % re.escape(cls.group(1)), svg)
                if rule:
                    fs2 = re.search(r"font-size:\s*([0-9.]+)px", rule.group(1))                         or re.search(r"font:[^;]*?([0-9.]+)px", rule.group(1))
                    if fs2:
                        size = _f(fs2.group(1), 12.0)

        bold = "font-weight" in attrs and re.search(r"font-weight[:=]\"?\s*(6|7|8|9|bold)", attrs)
        w = len(content) * size * (BOLD if bold else NARROW)

        anchor = (re.search(r'text-anchor[:=]"?\s*(\w+)', attrs) or [None, "start"])[1]
        if anchor == "middle":
            x1 = x - w / 2
        elif anchor == "end":
            x1 = x - w
        else:
            x1 = x
        # y is the baseline; a line box sits roughly from -0.78em to +0.22em
        out.append((x1, y - size * 0.78, x1 + w, y + size * 0.22, content))
    return out


def rects(svg: str):
    out = []
    for m in re.finditer(r"<rect\b([^>]*)>", svg):
        a = m.group(1)
        x, y = _f((re.search(r'\bx="([^"]+)"', a) or [None, "0"])[1]), \
               _f((re.search(r'\by="([^"]+)"', a) or [None, "0"])[1])
        w, h = _f((re.search(r'\bwidth="([^"]+)"', a) or [None, "0"])[1]), \
               _f((re.search(r'\bheight="([^"]+)"', a) or [None, "0"])[1])
        if w > 0 and h > 0:
            out.append((x, y, x + w, y + h))
    return out


def overlap(a, b, pad=1.0):
    return (a[0] + pad < b[2] and b[0] + pad < a[2]
            and a[1] + pad < b[3] and b[1] + pad < a[3])


def inside(t, r, slack=1.0):
    return (t[0] >= r[0] - slack and t[2] <= r[2] + slack
            and t[1] >= r[1] - slack and t[3] <= r[3] + slack)



def connectors(svg: str):
    """Connector geometry as a list of segments [(x1,y1,x2,y2), ...].

    Only <line> and the straight/elbow <path> forms these diagrams use. Curves
    are approximated by the polyline through their control points, which is
    close enough to tell whether a stroke runs across a word.

    Icon artwork is excluded: an AWS icon is dozens of tiny filled paths and
    none of them is a connector. They are the paths WITHOUT a stroke colour.
    """
    segs = []
    for m in re.finditer(r"<line\b([^>]*)>", svg):
        a = m.group(1)
        if "stroke" not in a:
            continue
        g = lambda k: _f((re.search(r'\b%s="([^"]+)"' % k, a) or [None, "0"])[1])
        segs.append((g("x1"), g("y1"), g("x2"), g("y2")))

    for m in re.finditer(r"<path\b([^>]*)>", svg):
        a = m.group(1)
        if "stroke=" not in a or 'fill="none"' not in a.replace("'", '"'):
            continue
        d = re.search(r'\bd="([^"]+)"', a)
        if not d:
            continue
        pts = [float(v) for v in re.findall(r"-?\d+\.?\d*", d.group(1))]
        xy = list(zip(pts[0::2], pts[1::2]))
        for i in range(len(xy) - 1):
            segs.append((xy[i][0], xy[i][1], xy[i + 1][0], xy[i + 1][1]))
    return segs


def _seg_hits_box(seg, box, inset=2.0):
    """Does a segment pass through a box, ignoring a mere touch at the edge?"""
    x1, y1, x2, y2 = seg
    bx1, by1, bx2, by2 = box[0] + inset, box[1] + inset, box[2] - inset, box[3] - inset
    if bx1 >= bx2 or by1 >= by2:
        return False
    # Liang-Barsky
    dx, dy = x2 - x1, y2 - y1
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x1 - bx1), (dx, bx2 - x1), (-dy, y1 - by1), (dy, by2 - y1)):
        if p == 0:
            if q < 0:
                return False
        else:
            r = q / p
            if p < 0:
                if r > t1:
                    return False
                t0 = max(t0, r)
            else:
                if r < t0:
                    return False
                t1 = min(t1, r)
    return t0 <= t1


def analyse(svg: str):
    """(collisions, escapes, out_of_canvas) for one diagram."""
    ts, rs = texts(svg), rects(svg)

    collisions = []
    for i in range(len(ts)):
        for j in range(i + 1, len(ts)):
            if overlap(ts[i], ts[j]):
                collisions.append((ts[i][4], ts[j][4]))

    # A text "escapes" when it straddles a rect's edge: partly in, partly out.
    # Fully inside is correct, fully outside is simply elsewhere on the canvas.
    canvas = None
    vb0 = re.search(r'viewBox="([^"]+)"', svg)
    if vb0:
        p0 = [_f(v) for v in vb0.group(1).split()]
        if len(p0) == 4:
            canvas = (p0[0], p0[1], p0[0] + p0[2], p0[1] + p0[3])

    def is_background(r):
        return canvas is not None and inside(canvas, r, slack=2.0)

    # A frame that spans nearly the whole canvas is the background or the AWS
    # Cloud border. Captions sit under those on purpose, so they are never the
    # box a label "fell out of".
    cw = (canvas[2] - canvas[0]) if canvas else 0

    def is_frame(r):
        return is_background(r) or (cw and (r[2] - r[0]) > 0.85 * cw)

    def is_title_of(t, r):
        """A frame's own name, printed just inside its top-left corner."""
        return (r[2] - r[0] >= 200 and t[2] <= r[2] + 1
                and r[0] - 1 <= t[0] <= r[0] + 60
                and r[1] - 1 <= t[1] <= r[1] + 34)

    escapes = []
    for t in ts:
        if any(inside(t, r) for r in rs if not is_frame(r)):
            continue
        if any(is_title_of(t, r) for r in rs):
            continue
        hit = None
        for r in rs:
            if inside(t, r):
                continue
            # A label that sits squarely within a box's width, just outside its
            # top or bottom line, has fallen out of that box. The old rule here
            # looked for an overlap with a SMALL box, and caught neither half of
            # week 12's bottom row: the frame was a 448-wide group, and the
            # three sub-labels cleared its border entirely rather than
            # straddling it, so there was no overlap to find.
            # Only the bottom edge, and only a frame wide enough to be holding
            # a row: a heading printed ABOVE a box is how these diagrams label
            # a section, and counting that as an escape reported eleven places
            # that are correct on screen.
            if (not is_frame(r) and (r[2] - r[0]) >= 260
                    and t[0] >= r[0] - 1 and t[2] <= r[2] + 1
                    and r[3] - 6 <= t[1] <= r[3] + 24):
                hit = (t[4], (r[2] - r[0], r[3] - r[1]))
                break
            if overlap(t, r) and (r[2] - r[0]) < 420 and (r[3] - r[1]) < 220:
                hit = (t[4], (r[2] - r[0], r[3] - r[1]))
                break
        if hit:
            escapes.append(hit)

    # A connector running across a word is the defect Jay actually sees, and
    # the first version of this file could not detect it: every one of the five
    # diagrams fixed on 2026-10-30 was found by eye, not by this check.
    struck = []
    segs = connectors(svg)
    for t_ in ts:
        for s in segs:
            if _seg_hits_box(s, t_[:4]):
                struck.append(t_[4])
                break

    vb = re.search(r'viewBox="([^"]+)"', svg)
    out = []
    if vb:
        p = [_f(v) for v in vb.group(1).split()]
        if len(p) == 4:
            for t in ts:
                if t[0] < p[0] - 1 or t[2] > p[0] + p[2] + 1 \
                        or t[1] < p[1] - 1 or t[3] > p[1] + p[3] + 1:
                    out.append(t[4])
    return collisions, escapes, out, struck


def biggest_svg(text: str):
    svgs = re.findall(r"<svg.*?</svg>", text, re.S)
    if not svgs:
        return None
    s = max(svgs, key=len)
    return s if len(s) > 800 else None


def self_test() -> int:
    good = ('<svg viewBox="0 0 200 100">'
            '<rect x="10" y="10" width="120" height="40"/>'
            '<text x="20" y="35" font-size="10">short</text></svg>')
    clash = ('<svg viewBox="0 0 200 100">'
             '<text x="20" y="35" font-size="10">overlapping one</text>'
             '<text x="24" y="37" font-size="10">overlapping two</text></svg>')
    spill = ('<svg viewBox="0 0 200 100">'
             '<rect x="10" y="10" width="60" height="30"/>'
             '<text x="20" y="30" font-size="12">far too long for that box</text></svg>')
    off = ('<svg viewBox="0 0 200 100">'
           '<text x="190" y="35" font-size="12">runs past the edge</text></svg>')
    struck = ('<svg viewBox="0 0 200 100">'
              '<text x="20" y="35" font-size="10">a label with a line through it</text>'
              '<line x1="60" y1="10" x2="60" y2="90" stroke="#333"/></svg>')
    beside = ('<svg viewBox="0 0 200 100">'
              '<text x="20" y="35" font-size="10">a label with a line beside it</text>'
              '<line x1="190" y1="10" x2="190" y2="90" stroke="#333"/></svg>')

    # The fault that shipped: a sub-label hanging below a GROUP frame. The box
    # is 600 wide, so the old size filter skipped it and the row rendered with
    # three captions sitting under the border.
    dropped = ('<svg viewBox="0 0 900 300">'
               '<rect x="20" y="20" width="600" height="200" fill="none"/>'
               '<text x="60" y="228" font-size="11">hangs below the group line</text>'
               '</svg>')
    seated = ('<svg viewBox="0 0 900 300">'
              '<rect x="20" y="20" width="600" height="200" fill="none"/>'
              '<text x="60" y="150" font-size="11">sits inside the group</text>'
              '</svg>')

    cases = [
        ("a sub-label hanging below a group frame", dropped, (0, 1, 0, 0)),
        ("a label seated inside a group frame", seated, (0, 0, 0, 0)),
        ("a clean diagram", good, (0, 0, 0, 0)),
        ("two texts on top of each other", clash, (1, 0, 0, 0)),
        ("text wider than its box", spill, (0, 1, 0, 0)),
        ("text past the canvas edge", off, (0, 0, 1, 0)),
        ("a connector drawn through a label", struck, (0, 0, 0, 1)),
        ("a connector that merely passes nearby", beside, (0, 0, 0, 0)),
    ]
    bad = 0
    for label, svg, want in cases:
        got = tuple(len(x) for x in analyse(svg))
        ok = got == want
        bad += not ok
        print("  [%s] %s -> %s, want %s" % (" ok " if ok else "FAIL", label, got, want))
    if bad:
        print("\nSELF-TEST FAILED")
        return 1
    print("\nself-test passed: collisions, box overflow and canvas overflow all detected.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("posts", nargs="*")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()

    names = [fn for fn in sorted(os.listdir(POSTS))
             if fn.startswith("week-") and fn.endswith(".html")
             and (not args.posts or any(a in fn for a in args.posts))]
    if not names:
        print("NOTHING MATCHED %s -- a run that inspected no diagram has not passed."
              % ", ".join(args.posts or ["posts/"]))
        return 1

    checked = dirty = 0
    for fn in names:
        text = io.open(os.path.join(POSTS, fn), encoding="utf-8").read()
        fm = text.split("---", 2)[1] if text.count("---") >= 2 else ""
        if "AWS Weekly Lab" not in fm:
            continue
        svg = biggest_svg(text)
        if not svg:
            continue
        checked += 1
        col, esc, out, hit = analyse(svg)
        if not (col or esc or out or hit):
            print("  [ ok ] %s" % fn.replace(".html", ""))
            continue
        dirty += 1
        print("  [LOOK] %-34s %d overlap, %d out-of-box, %d off-canvas, %d struck"
              % (fn.replace(".html", ""), len(col), len(esc), len(out), len(hit)))
        for a, b in col[:4]:
            print("           overlap : %r  <->  %r" % (a[:38], b[:38]))
        for s, box in esc[:4]:
            print("           out-of-box: %r  (box %dx%d)" % (s[:38], box[0], box[1]))
        for s in out[:3]:
            print("           off-canvas: %r" % s[:46])
        for s in hit[:5]:
            print("           LINE THROUGH: %r" % s[:46])

    if not checked:
        print("no lab diagrams found -- a run that inspected nothing has not passed.")
        return 1
    print("\n%d diagram(s) inspected, %d worth looking at." % (checked, dirty))
    return 0


if __name__ == "__main__":
    sys.exit(main())
