#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Put the early posts' images into the figure markup the standard expects.

    python scripts/wrap_screenshots.py 2 3 --write
    python scripts/wrap_screenshots.py 5 --write

Weeks 1-3 place a bare <img> with an inline style and no <figure> at all.
Week 5 has <figure> but without the class. Either way the shape check counts
zero screenshots and fails the post for having none, while the images sit
right there on the page.

Two jobs:

  * a bare <figure> gains class="screenshot"
  * a bare <img> is wrapped in <figure class="screenshot"> with a caption

The caption comes from the image's own alt text, which in weeks 2 and 3 is
already a description of what the screenshot proves. An image with no usable
alt is REFUSED rather than given an empty <figcaption>: the standard asks what
the picture demonstrates, and a caption invented from a filename answers a
different question. Supply those through --caption.
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
sys.path.insert(0, HERE)

import aws_post_path as paths            # noqa: E402

IMG = re.compile(r"<img\b[^>]*?>", re.S)


def _attr(tag, name):
    m = re.search(r'\b%s="([^"]*)"' % name, tag)
    return m.group(1) if m else ""


def wrap(text, captions):
    """-> (text, wrapped, refused)"""
    # A <figure> that is simply missing the class.
    text = re.sub(r"<figure>(\s*<img)", r'<figure class="screenshot">\1', text)

    wrapped, refused = 0, []
    out, pos = [], 0
    for m in IMG.finditer(text):
        tag = m.group(0)
        before = text[:m.start()]
        # Already inside a figure? Look back a short way for an unclosed one.
        tail = before[-400:]
        if "<figure" in tail and "</figure>" not in tail.split("<figure")[-1]:
            continue
        src = _attr(tag, "src").split("/")[-1]
        cap = captions.get(src) or html.unescape(_attr(tag, "alt")).strip()
        if not cap:
            refused.append(src)
            continue
        clean = re.sub(r'\s*style="[^"]*"', "", tag)
        block = ('<figure class="screenshot">\n  %s\n  <figcaption>%s</figcaption>\n'
                 "</figure>" % (clean, html.escape(cap, quote=False)))
        # Swallow a <p> or <div> that exists only to hold the image.
        start, end = m.start(), m.end()
        pm = re.search(r"<(p|div)[^>]*>\s*$", text[:start])
        if pm:
            after = text[end:end + 60]
            cm = re.match(r"\s*</%s>" % pm.group(1), after)
            if cm:
                start = pm.start()
                end = end + cm.end()
        out.append(text[pos:start])
        out.append(block)
        pos = end
        wrapped += 1
    out.append(text[pos:])
    return "".join(out), wrapped, refused


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("weeks", nargs="+", type=int)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--caption", action="append", default=[],
                    metavar="FILENAME=TEXT")
    a = ap.parse_args()

    captions = {}
    for c in a.caption:
        k, _, v = c.partition("=")
        captions[k.strip()] = v.strip()

    rc = 0
    for wk in a.weeks:
        p = paths.for_week(wk)
        t = io.open(p, encoding="utf-8").read()
        new, n, refused = wrap(t, captions)
        if refused:
            rc = 1
            print("  week %-2d REFUSED - no alt text and no --caption for: %s"
                  % (wk, ", ".join(refused)))
            continue
        if a.write:
            io.open(p, "w", encoding="utf-8", newline="\n").write(new)
        print("  week %-2d %s  %d image(s) wrapped, %d figure(s) now classed"
              % (wk, "wrapped" if a.write else "would wrap", n,
                 new.count('class="screenshot"')))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
