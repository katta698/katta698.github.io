#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Convert pre-standard markup in weeks 1-8 to what the migrated posts use.

    python scripts/convert_legacy_blocks.py 4 6 7 8 --write

Two blocks, both of which exist only in the early posts:

  flow / flow-step   A numbered explanation built from nested divs and an
                     <h4> per step. Migrated posts use an <ol>, which says the
                     same thing, needs no bespoke CSS, and is what a screen
                     reader announces as a list.

  post-footer        A hand-written "Week N of 52 | jayanthkatta.com" strip.
                     The site footer is injected at build time, so this is a
                     second footer above the real one.

Both carry classes the builder's injected stylesheet does not define, which is
what blocks removing the posts' inline <style> block. Converting them is
therefore not cosmetic: it is what lets about a thousand words of duplicated
CSS come out of each post's word budget.
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import aws_post_path as paths            # noqa: E402


def _balanced(text, start, tag="div"):
    depth, i = 0, start
    o, c = "<" + tag, "</" + tag + ">"
    while i < len(text):
        if text.startswith(o, i):
            depth += 1
            i += len(o)
        elif text.startswith(c, i):
            depth -= 1
            i += len(c)
            if depth == 0:
                return i
        else:
            i += 1
    return -1


def convert_flow(t):
    n = 0
    while True:
        m = re.search(r'<div class="flow">', t)
        if not m:
            break
        end = _balanced(t, m.start())
        if end < 0:
            break
        block = t[m.start():end]
        items = []
        for sm in re.finditer(r'<div class="flow-step">', block):
            send = _balanced(block, sm.start())
            step = block[sm.start():send]
            h4 = re.search(r"<h4>(.*?)</h4>", step, re.S)
            p = re.search(r"<p>(.*?)</p>", step, re.S)
            if not p:
                continue
            title = h4.group(1).strip() if h4 else ""
            body = p.group(1).strip()
            items.append("  <li><strong>%s</strong> %s</li>" % (title, body)
                         if title else "  <li>%s</li>" % body)
        t = t[:m.start()] + "<ol>\n" + "\n".join(items) + "\n</ol>" + t[end:]
        n += 1
    return t, n


def convert_numbered_cards(t, outer, inner, drop_classes):
    """<div class=outer><div class=inner>[<div class=drop>N</div>]<h4>..</h4><p>..</p>

    Week 5 renders its "why" list, and its security controls, as nested divs
    with an icon or an ordinal in one child and the content in another. Both
    are lists. An <ol>/<ul> says the same thing, needs no bespoke CSS, and is
    what a screen reader announces.
    """
    n = 0
    tag = "ol" if outer == "steps" else "ul"
    while True:
        m = re.search(r'<div class="%s">' % re.escape(outer), t)
        if not m:
            return t, n
        end = _balanced(t, m.start())
        if end < 0:
            return t, n
        block = t[m.start():end]
        items = []
        for im in re.finditer(r'<div class="%s">' % re.escape(inner), block):
            iend = _balanced(block, im.start())
            chunk = block[im.start():iend]
            for d in drop_classes:
                chunk = re.sub(r'<div class="%s">.*?</div>' % re.escape(d), "",
                               chunk, flags=re.S)
            h4 = re.search(r"<h4>(.*?)</h4>", chunk, re.S)
            ps = re.findall(r"<p>(.*?)</p>", chunk, re.S)
            if not ps:
                continue
            title = re.sub(r"<[^>]+>", "", h4.group(1)).strip() if h4 else ""
            body = " ".join(x.strip() for x in ps)
            items.append("  <li><strong>%s</strong> %s</li>" % (title, body)
                         if title else "  <li>%s</li>" % body)
        if not items:
            return t, n
        t = (t[:m.start()]
             + "<%s>\n%s\n</%s>" % (tag, "\n".join(items), tag)
             + t[end:])
        n += 1


def plain_ref_list(t):
    """Strip the decorative tag chip from each reference."""
    n = t.count('class="ref-list"') + t.count('class="ref-tag"')
    t = t.replace('<ul class="ref-list">', "<ul>")
    t = re.sub(r'<span class="ref-tag">.*?</span>\s*', "", t, flags=re.S)
    return t, n


def unwrap_class(t, cls):
    """Remove a purely presentational wrapper, keeping its contents."""
    n = 0
    while True:
        m = re.search(r'<div class="%s">' % re.escape(cls), t)
        if not m:
            return t, n
        end = _balanced(t, m.start())
        if end < 0:
            return t, n
        t = t[:m.start()] + t[m.end():end - 6] + t[end:]
        n += 1


def drop_post_footer(t):
    n = 0
    while True:
        m = re.search(r'<div class="post-footer">', t)
        if not m:
            break
        end = _balanced(t, m.start())
        if end < 0:
            break
        start = m.start()
        # Take the <hr/> immediately above it as well, if present.
        head = t[:start]
        hm = re.search(r"<hr\s*/?>\s*$", head)
        if hm:
            start = hm.start()
        t = t[:start] + t[end:]
        n += 1
    return t, n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("weeks", nargs="+", type=int)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    for wk in a.weeks:
        p = paths.for_week(wk)
        t = io.open(p, encoding="utf-8").read()
        t, nf = convert_flow(t)
        t, ns = convert_numbered_cards(t, "steps", "step", ("step-num",))
        t, nsec = convert_numbered_cards(t, "security-grid", "security-item",
                                         ("security-icon",))
        t, nr = plain_ref_list(t)
        t, nw = unwrap_class(t, "arch-wrap")
        t, nd = drop_post_footer(t)
        nf += ns + nsec + nw
        if not (nf or nd or nr):
            print("  week %-2d nothing to convert" % wk)
            continue
        if a.write:
            io.open(p, "w", encoding="utf-8", newline="\n").write(t)
        print("  week %-2d %s  %d flow block(s), %d post-footer(s)"
              % (wk, "converted" if a.write else "would convert", nf, nd))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
