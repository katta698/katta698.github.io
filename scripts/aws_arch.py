#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compose an architecture diagram in AWS's own reference-architecture style.

    from aws_arch import Diagram
    d = Diagram(900, 420, "...accessible description...")
    d.cloud(16, 16, 868, 388)
    d.group(40, 60, 500, 320, "Region: us-east-2")
    d.icon(80, 120, "lambda", "AWS Lambda", "checkout")
    d.arrow(160, 150, 240, 150, step="1")
    print(d.render())

WHY THIS EXISTS (2026-10-30)
----------------------------
Every lab post carried a hand-drawn schematic: boxes, labels and arrows in
whatever shapes that week's author reached for. They read fine and they looked
nothing like the diagrams AWS publishes, so a reader moving between this series
and AWS's own documentation had to re-learn the visual language each time.

Jay asked for AWS's convention instead, for this week and every week after: the
official service icons, an AWS Cloud boundary, account and Region groupings,
numbered steps on the flow, and the service name printed under each icon.

The icons in _assets/aws-icons/ are the official ones, extracted from the AWS
Architecture Icons package (Icon-package_07312026) whose terms permit exactly
this use. They are NOT redrawn -- a redrawn icon is a wrong icon, and the
colours carry meaning: orange is Compute, purple Networking, magenta Databases.
See _assets/aws-icons/SOURCE.json for the release and date.

Each icon is placed with a transformed <g>, so a finished diagram is a single
self-contained element with no external references. It survives being inlined
in a post, rendered in a feed reader, or opened straight from the repository.

The first version nested an <svg> per icon. That is valid, and it rendered
perfectly on its own -- then every icon vanished once the post was built,
because the site stylesheet selects `svg` and those selectors reach inside a
diagram. Only looking at the built page caught it. A <g> is untouchable by
them.
"""
from __future__ import annotations

import io
import os
import re

ICONS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "_assets", "aws-icons")

# AWS's own palette for diagram furniture.
SQUID = "#232F3E"      # boundary lines and label text
ORANGE = "#FF9900"     # the AWS Cloud mark
LINE = "#5A6B7B"       # connectors
MUTED = "#687078"      # secondary text
RED = "#D13212"        # the thing that went wrong
GREEN = "#1A7F37"      # the thing that held


def _icon_body(slug: str) -> tuple:
    """The inner markup of an official icon, plus its viewBox."""
    path = os.path.join(ICONS, slug + ".svg")
    if not os.path.exists(path):
        raise SystemExit(
            "no official icon for %r. Available: %s\nExtract it from the AWS "
            "Architecture Icons package rather than drawing one."
            % (slug, ", ".join(sorted(
                f[:-4] for f in os.listdir(ICONS) if f.endswith(".svg")))))
    s = io.open(path, encoding="utf-8").read()
    vb = re.search(r'viewBox="([^"]+)"', s)
    inner = re.sub(r"^.*?<svg[^>]*>", "", s, flags=re.S)
    inner = re.sub(r"</svg>\s*$", "", inner, flags=re.S)
    box = vb.group(1) if vb else "0 0 80 80"
    return inner.strip(), float(box.split()[2])


class Diagram:
    def __init__(self, width: int, height: int, description: str):
        self.w, self.h, self.desc = width, height, description
        self.parts = []
        # Everything that must not collide with anything else, as
        # (x1, y1, x2, y2, what). Checked by assert_clean() before render.
        self.claims = []
        self.containers = []   # boxes that text is ALLOWED to sit inside

    # -- containers ---------------------------------------------------------
    def cloud(self, x, y, w, h, label="AWS Cloud"):
        """The outer AWS Cloud boundary, with its tab label."""
        self.parts.append(
            '<rect x="%d" y="%d" width="%d" height="%d" rx="2" fill="none" '
            'stroke="%s" stroke-width="2"/>' % (x, y, w, h, SQUID))
        self.parts.append(
            '<rect x="%d" y="%d" width="34" height="30" fill="%s"/>'
            % (x, y, SQUID))
        # the AWS smile, drawn small inside the tab
        self.parts.append(
            '<text x="%d" y="%d" font-family="Arial,sans-serif" '
            'font-size="11" font-weight="700" fill="%s">aws</text>'
            % (x + 7, y + 20, "#FFFFFF"))
        self.parts.append(
            '<text x="%d" y="%d" font-family="Arial,sans-serif" font-size="13" '
            'fill="%s">%s</text>' % (x + 44, y + 20, SQUID, label))

    def group(self, x, y, w, h, label, colour=None, dashed=False):
        """An account, Region or logical grouping box."""
        c = colour or LINE
        self.parts.append(
            '<rect x="%d" y="%d" width="%d" height="%d" rx="2" fill="none" '
            'stroke="%s" stroke-width="1.5"%s/>'
            % (x, y, w, h, c, ' stroke-dasharray="6 4"' if dashed else ""))
        self.parts.append(
            '<text x="%d" y="%d" font-family="Arial,sans-serif" font-size="12" '
            'font-weight="600" fill="%s">%s</text>' % (x + 12, y + 20, c, label))

    # -- content ------------------------------------------------------------
    def icon(self, x, y, slug, label, sub=None, size=48):
        """An official service icon with its name printed underneath.

        Placed with a transformed <g>, NOT a nested <svg>. A nested <svg> is
        valid and renders correctly on its own, and it disappeared the moment
        the post was built, because the site stylesheet carries rules that
        select `svg` and reach every nested one inside a diagram. A <g> cannot
        be hit by those selectors, so the diagram looks the same in the source,
        in the built page, and in anything that re-renders it later.
        """
        inner, vbw = _icon_body(slug)
        k = size / vbw
        self.parts.append(
            '<g transform="translate(%d,%d) scale(%.5f)">%s</g>'
            % (x, y, k, inner))
        self._claim(x, y, x + size, y + size, "icon:" + slug, group=label)
        lw = self._text_w(label, 11.5)
        self.parts.append(
            '<text x="%d" y="%d" text-anchor="middle" font-family="Arial,sans-serif" '
            'font-size="11.5" fill="%s">%s</text>'
            % (x + size // 2, y + size + 16, SQUID, label))
        self._claim(x + size // 2 - lw / 2, y + size + 5,
                    x + size // 2 + lw / 2, y + size + 20, "label:" + label, group=label)
        if sub:
            sw = self._text_w(sub, 10.5)
            self.parts.append(
                '<text x="%d" y="%d" text-anchor="middle" '
                'font-family="Arial,sans-serif" font-size="10.5" fill="%s">%s</text>'
                % (x + size // 2, y + size + 31, MUTED, sub))
            self._claim(x + size // 2 - sw / 2, y + size + 21,
                        x + size // 2 + sw / 2, y + size + 35, "sub:" + sub, group=label)

    def arrow(self, x1, y1, x2, y2, step=None, colour=None, dashed=False):
        c = colour or LINE
        self.parts.append(
            '<path d="M%d %d L%d %d" fill="none" stroke="%s" stroke-width="1.6" '
            'marker-end="url(#ah)"%s/>'
            % (x1, y1, x2, y2, c, ' stroke-dasharray="5 4"' if dashed else ""))
        if step:
            self.step(((x1 + x2) // 2), ((y1 + y2) // 2) - 12, step)

    def elbow(self, x1, y1, x2, y2, colour=None, step=None):
        """A right-angled connector, the way AWS draws them."""
        c = colour or LINE
        self.parts.append(
            '<path d="M%d %d L%d %d L%d %d" fill="none" stroke="%s" '
            'stroke-width="1.6" marker-end="url(#ah)"/>'
            % (x1, y1, x2, y1, x2, y2, c))
        if step:
            self.step(x2, y1 - 14, step)

    def step(self, cx, cy, n):
        """A numbered circle on the flow."""
        self._claim(cx - 11, cy - 11, cx + 11, cy + 11, "step " + str(n))
        self.parts.append(
            '<circle cx="%d" cy="%d" r="11" fill="%s"/>' % (cx, cy, SQUID))
        self.parts.append(
            '<text x="%d" y="%d" text-anchor="middle" font-family="Arial,sans-serif" '
            'font-size="11.5" font-weight="700" fill="#FFFFFF">%s</text>'
            % (cx, cy + 4, n))

    def note(self, x, y, text, colour=None, weight="400", size=11.5, anchor="start"):
        self.parts.append(
            '<text x="%d" y="%d" text-anchor="%s" font-family="Arial,sans-serif" '
            'font-size="%s" font-weight="%s" fill="%s">%s</text>'
            % (x, y, anchor, size, weight, colour or SQUID, text))

    def box(self, x, y, w, h, fill="#F2F3F3", stroke=None):
        self.parts.append(
            '<rect x="%d" y="%d" width="%d" height="%d" rx="3" fill="%s" '
            'stroke="%s" stroke-width="1.4"/>'
            % (x, y, w, h, fill, stroke or "#D5DBDB"))

    # -- the check -----------------------------------------------------------
    @staticmethod
    def _text_w(text, size, weight="400"):
        """Approximate Arial advance width. Deliberately generous: this check
        exists to catch collisions, so it should over-estimate rather than
        pass something that will touch."""
        per = 0.60 if str(weight) >= "600" else 0.56
        return len(text) * size * per

    def _claim(self, x1, y1, x2, y2, what, group=None):
        # `group` ties an icon to its own label and sub-label. Those are
        # stacked deliberately and must not be reported against each other.
        self.claims.append((x1, y1, x2, y2, what, group))

    def assert_clean(self, pad=2):
        """Refuse to render a diagram whose labels collide.

        Added 2026-10-30 after a review found a step circle sitting on top of a
        service's sub-label and a connector ending in empty space. Reading a
        diagram for overlaps by eye does not scale and does not survive edits:
        move one icon and two labels you were not looking at can touch.
        """
        bad = []
        n = len(self.claims)
        for i in range(n):
            ax1, ay1, ax2, ay2, aw, ag = self.claims[i]
            for j in range(i + 1, n):
                bx1, by1, bx2, by2, bw, bg = self.claims[j]
                if ag is not None and ag == bg:
                    continue
                if (ax1 - pad < bx2 and bx1 - pad < ax2
                        and ay1 - pad < by2 and by1 - pad < ay2):
                    bad.append("%s  <->  %s" % (aw, bw))
        # text must also stay inside the box it was placed in
        for (bx1, by1, bx2, by2, label, tw) in self.containers:
            if tw > (bx2 - bx1) - 16:
                bad.append("text overflows its box: %r needs %dpx, box is %dpx"
                           % (label, int(tw), bx2 - bx1))
        if bad:
            raise SystemExit(
                "diagram is not clean -- %d collision(s):%s%s"
                % (len(bad), chr(10) + "  ",
                   (chr(10) + "  ").join(bad)))
        return self

    # -- output -------------------------------------------------------------
    def render(self, indent="      ") -> str:
        head = (
            '<svg viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg" role="img"\n'
            '%s     aria-label="%s"\n'
            '%s     style="width:100%%;height:auto;background:#fff;border:1px solid '
            '#e6e8eb;border-radius:8px">\n'
            '%s  <rect width="%d" height="%d" fill="#ffffff"/>\n'
            '%s  <defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" '
            'markerWidth="7" markerHeight="7" orient="auto">'
            '<path d="M0 0 L10 5 L0 10 z" fill="%s"/></marker></defs>\n'
            % (self.w, self.h, indent, self.desc, indent, indent, self.w, self.h,
               indent, LINE))
        body = "\n".join(indent + "  " + p for p in self.parts)
        return head + body + "\n" + indent + "</svg>"
