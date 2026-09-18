#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Every page that wears the shell carries all of the shell.

    python scripts/check_shell_parts.py

Why this exists
---------------
Reported as: "there's no feedback star in cloud events page, make sure that
pattern is consistent for any page I open moving forward."

He was right, and the interesting part is why nothing said so. The events page
already had the star's STYLESHEET -- it inherits the whole head from
build_news_page -- so it carried every rule for a button it never rendered.
And check_feedback.py, which exists to test exactly this, holds a hardcoded
list of five pages written before the events page existed. It passed, happily,
for a page it had never heard of.

The instrument rotation failed the same way on the same day: check
_instrument_glyphs listed four files, two hand-maintained pages kept the old
ten-glyph rotation, and the music icon changed as a reader moved between tabs.

Two different features, one shape of mistake: a check that enumerates what to
look at can only ever be as complete as the afternoon somebody wrote the list.
So this one enumerates nothing. It finds every page that loads the shared
stylesheet -- that is the definition of "a page on this site" -- and requires
each one to carry the parts a reader expects to find everywhere.

What it does NOT do is judge whether the part works; check_feedback drives the
star in a real browser and check_music presses the button. This only asks the
cheaper question that nobody was asking: is it there at all.
"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SKIP_DIRS = {".git", "node_modules", "_archive", "_templates", "__pycache__",
             "drafts"}

# Pages that wear the shell but are deliberately not full site pages.
#
# Kept short and each one justified. This is the only list here, and it is a
# list of EXCEPTIONS -- which fails safe: forgetting to add something to it
# makes a check noisier, not blinder.
EXEMPT = {
    "offline.html",          # served when there is no network; nothing to send
    "palette-preview.html",  # an internal swatch sheet, not linked anywhere
    "rag-diagram.html",      # a diagram embedded inside a post
}

# What every page is expected to carry, and what a reader loses without it.
PARTS = [
    ("the feedback star", 'id="fb-btn"', None,
     "no way to tell me anything from that page"),
    ("the shared script", "site-footer.js", None,
     "no theme switch, no menu, no music, no pull-to-refresh"),
    # Conditional, and the condition is the whole point.
    #
    # The first version of this required #beach-audio on every page and
    # reported 261 failures -- all of them blog posts, which carry no music
    # button at all. Posts were not broken; the rule was. A check that fails
    # on 261 correct pages is a check somebody switches off, and it would have
    # buried the four real findings underneath it.
    #
    # The honest question is not "does every page have the audio element" but
    # "does every page that OFFERS music have something to play" -- which is
    # the failure that actually happened here once: the button present,
    # styled, pressable and silent, on two pages, with nothing reporting it.
    ("the music element", 'id="beach-audio"', 'id="audio-toggle"',
     "the music button is on the page, and there is nothing for it to play"),
]


def pages():
    """Every page that loads the shared stylesheet."""
    out = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS
                   and not d.startswith(".")]
        for name in files:
            if not name.endswith(".html"):
                continue
            path = os.path.join(base, name)
            rel = os.path.relpath(path, ROOT).replace("\\", "/")
            if rel in EXEMPT or os.path.basename(rel) in EXEMPT:
                continue
            try:
                src = io.open(path, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            if "site-footer.css" in src:
                out.append((rel, src))
    return sorted(out)


def main():
    found = pages()
    if not found:
        print("  no page on this site loads the shared stylesheet. Either the "
              "shell\n  moved or this check has stopped looking at anything.")
        return 1

    missing = {}
    for rel, src in found:
        for label, needle, only_if, cost in PARTS:
            if only_if and only_if not in src:
                continue          # the page does not offer it; nothing owed
            if needle not in src:
                missing.setdefault(label, []).append(rel)

    print("  %d page(s) wear the shell." % len(found))
    for label, _needle, _only, _cost in PARTS:
        gone = missing.get(label, [])
        print("     %-20s %s" % (label,
              "all of them" if not gone else "MISSING on %d" % len(gone)))

    print()
    if missing:
        n = sum(len(v) for v in missing.values())
        print("  %d MISSING PART(S)\n" % n)
        for label, needle, _only, cost in PARTS:
            gone = missing.get(label)
            if not gone:
                continue
            print("  - %s is absent from %d page(s) -- %s:"
                  % (label, len(gone), cost))
            for rel in sorted(gone)[:8]:
                print("      %s" % rel)
            if len(gone) > 8:
                print("      ...and %d more" % (len(gone) - 8))
        print()
        print("  A page can carry the CSS for a control and never render it.")
        print("  That is how this one shipped: styled, and not there.")
        return 1

    print("  Every one carries the star, the shared script and the audio "
          "element.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
