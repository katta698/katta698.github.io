#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail a stylesheet or post that leaves light colours reachable in dark mode.

Why this check exists
---------------------
blog.css repaints everything inside `#jk-post` for dark mode with a single
blanket `!important` rule, and carries a `:not()` exclusion list so that
syntax-highlighted `<pre>` keeps its own palette instead of being flattened to
the page colour. That exclusion list is the hazard, and it has produced two
opposite bugs:

  * **Excluded and light.** `:not(code)` was written for `<pre><code>`, but it
    also skips `code.inline`, which lives outside any `<pre>` and has no dark
    palette of its own. So it kept `#0f1111` text on an `#f5f5f5` chip on a
    `#181818` page -- a white box in dark mode, on every post using inline
    code, for as long as dark mode has existed. Reported by a reader on
    2026-08-28. Nothing caught it because every other check reads *posts*, and
    this lived entirely in the stylesheet.

  * **Not excluded and meaningful.** The code-block header dots are pure
    background with no text. The blanket flattening them to `transparent` did
    not recolour them, it deleted them. And no override could fix it: the
    blanket is specificity (1,3,5) *and* `!important`, so a normal
    `body.dark` rule loses. Excluding them is the only thing that works.

The invariant
-------------
A `#jk-post` rule that the blanket cannot reach, and that paints a light
background, MUST have a `body.dark` counterpart.

The exclusion list is read out of blog.css at run time rather than copied here,
so editing that list without handling the consequence fails this check instead
of shipping. Posts are checked too: the blanket is `!important` and therefore
beats an inline `style` on an ordinary element, but on an *excluded* element
there is no blanket rule to beat it and the inline style survives.

Usage:
  python scripts/check_dark_theme.py            # stylesheet + every post
  python scripts/check_dark_theme.py arch-035   # stylesheet + matching posts
"""

import argparse
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
POSTS = os.path.join(ROOT, "posts")
CSS = os.path.join(ROOT, "blog", "assets", "blog.css")
THEME_SRC = os.path.join(ROOT, "scripts", "sync_blog.py")

# The blanket rule, and the :not() list it carries.
BLANKET_RE = re.compile(r"body\.dark #jk-post \*((?::not\([^)]*\))+)\s*\{")
NOT_RE = re.compile(r":not\(([^)]*)\)")

# A #jk-post rule in the injected post theme.
RULE_RE = re.compile(r"^(#jk-post [^{\n]*?)\s*\{([^}]*)\}", re.M)
BG_DECL_RE = re.compile(r"(?:^|;)\s*background(?:-color)?\s*:\s*([^;]+)", re.I)
HEX_RE = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})")

# An inline style painting a background onto a TEXT element dark mode skips.
#
# Deliberately NOT <svg> or <img>. A diagram is a self-contained picture and is
# *required* to paint its own background -- check_theme_render.py fails one that
# does not, because a lightboxed SVG otherwise inherits whatever is behind it.
# A white diagram on a dark page is therefore correct and intended. Five lab
# posts have exactly that shape and all five are right; flagging them would put
# this check in direct conflict with check_theme_render.py, which is how a
# validator earns a reputation for crying wolf and gets switched off. Only text
# chrome is in scope here.
INLINE_RE = re.compile(
    r"<(code|pre)\b[^>]*\bstyle=\"([^\"]*)\"", re.I)

# Anything at or above this relative luminance reads as "light" on a dark page.
LIGHT = 0.5


def luminance(hex_colour):
    """Relative luminance, 0-1. Enough to tell a white chip from a dark one."""
    h = hex_colour.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))

    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def exclusions(css):
    """The tokens the dark blanket rule refuses to repaint."""
    m = BLANKET_RE.search(css)
    if not m:
        return None
    return {tok.strip() for tok in NOT_RE.findall(m.group(1))}


def subject_is_excluded(subject, excluded):
    """Does this rule's subject match one of the blanket's :not() tokens?

    `subject` is the last compound in the selector -- the thing actually
    painted. `code.inline` matches the `code` exclusion; `.code-dot:nth-child(1)`
    matches `.code-dot`.
    """
    base = subject.split(":")[0]
    parts = set()
    if base:
        parts.add(base.split(".")[0])
        parts.update("." + c for c in base.split(".")[1:] if c)
    for tok in excluded:
        if tok in parts:
            return tok
    return None


def check_stylesheet():
    problems = []
    if not (os.path.exists(CSS) and os.path.exists(THEME_SRC)):
        return problems
    css = open(CSS, encoding="utf-8").read()
    theme = open(THEME_SRC, encoding="utf-8").read()

    excluded = exclusions(css)
    if excluded is None:
        return ["blog.css: the `body.dark #jk-post *:not(...)` blanket rule is "
                "gone or was reshaped. This check reads its exclusion list to "
                "know what dark mode cannot reach, so re-point it before "
                "trusting a green run."]

    dark_lines = [ln for ln in css.splitlines() if "body.dark #jk-post" in ln]

    for sel, decls in RULE_RE.findall(theme):
        bg = BG_DECL_RE.search(decls)
        if not bg:
            continue
        hexes = HEX_RE.findall(bg.group(1))
        if not hexes:
            continue
        colour = "#" + hexes[0]
        if luminance(colour) < LIGHT:
            continue                       # already dark: not this bug

        subject = sel.split()[-1]
        tok = subject_is_excluded(subject, excluded)
        if not tok:
            continue                       # blanket reaches it and flattens it

        key = subject.split(":")[0]
        if any(key in ln for ln in dark_lines):
            continue                       # a dark counterpart exists

        problems.append(
            "blog.css: `%s` paints a light background (%s) and matches the dark "
            "blanket's :not(%s) exclusion, so dark mode never repaints it -- it "
            "stays a light box on a dark page. Add a `body.dark %s` rule, or "
            "remove %s from the exclusion list."
            % (sel, colour, tok, subject, tok))
    return problems


def check_post(path, excluded):
    """An inline light background on an element the blanket skips survives."""
    problems = []
    body = open(path, encoding="utf-8").read()
    for tag, style in INLINE_RE.findall(body):
        if tag not in excluded:
            continue                       # blanket is !important; it wins
        bg = BG_DECL_RE.search(style)
        if not bg:
            continue
        hexes = HEX_RE.findall(bg.group(1))
        if not hexes or luminance("#" + hexes[0]) < LIGHT:
            continue
        problems.append(
            "%s: inline <%s style=\"background:#%s\"> is light, and dark mode "
            "skips <%s>, so this survives onto a dark page. Use a class with a "
            "`body.dark` counterpart instead of an inline colour."
            % (os.path.basename(path), tag, hexes[0], tag))
    return problems


def posts_to_check(selectors):
    if not os.path.isdir(POSTS):
        return []
    names = sorted(f for f in os.listdir(POSTS) if f.endswith(".html"))
    if selectors:
        names = [n for n in names if any(s in n for s in selectors)]
    return [os.path.join(POSTS, n) for n in names]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("posts", nargs="*", help="substrings of post filenames")
    ap.add_argument("--series", default=None, help="accepted for symmetry; unused")
    args = ap.parse_args()

    problems = check_stylesheet()

    css = open(CSS, encoding="utf-8").read() if os.path.exists(CSS) else ""
    excluded = exclusions(css) or set()
    paths = posts_to_check(args.posts)
    for path in paths:
        problems += check_post(path, excluded)

    if problems:
        print("DARK THEME CHECK FAILED (%d problem(s)):" % len(problems))
        for p in problems:
            print("  - " + p)
        print("")
        print("  Dark mode repaints #jk-post with one blanket !important rule.")
        print("  Anything on its :not() list is invisible to that rule and keeps")
        print("  whatever light colour it was given.")
        return 1

    print("  dark-mode exclusions: %s" % ", ".join(sorted(excluded)))
    print("  %d post(s) checked: no light backgrounds survive into dark mode."
          % len(paths))
    return 0


if __name__ == "__main__":
    sys.exit(main())
