#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The daily instrument is a glyph every device can actually draw.

    python scripts/check_instrument_glyphs.py

Why this exists
---------------
Reported as: "in the blog page, the music icon is missing. What's going on?"

It was not missing. The button was in the markup, 32x32, visible, opacity
.85, with nothing above it -- measured on the live site at his own screen
width. It was drawing NOTHING, and the reason is a two-part design that has
no failure mode between them:

    #audio-toggle { font-size: 0 !important; }
    #audio-toggle::before { content: var(--jk-ins, '<violin>'); }

The button's own text is sized to nothing on purpose, so the glyph cannot
flicker from one instrument to another as scripts load. The glyph therefore
comes entirely from ::before, and --jk-ins is set in <head> to one of ten
instruments chosen by the day.

Four of those ten were recent Unicode additions -- flute (U+1FA88, Emoji
15.0, 2022), banjo, long drum, accordion. On a device whose emoji font does
not carry the day's instrument, ::before renders nothing, the text underneath
it is already font-size:0, and the reader gets an empty 32px gap. The
var(--jk-ins, ...) fallback cannot help: --jk-ins IS set, correctly, to a
character the device cannot draw.

So the bug appears and disappears BY DATE. Four days in ten it is invisible
to some devices, six days in ten nobody can reproduce it, and nothing in any
log or check says a word. That is why this is a check and not a fix alone:
the next person adding a nicer instrument to that list would put it straight
back, and would not find out for up to ten days.

The rotation is now six instruments, all Emoji 1.0 (2015) or Emoji 3.0
(2016): violin, guitar, drum, trumpet, saxophone, musical keyboard. This
refuses anything outside the allowed set, and checks every copy of the
rotation -- it is inlined in four files, and four copies drifting apart is
its own failure.
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Emoji 1.0 (2015) and 3.0 (2016). Old enough that any device still in use
# has them: they predate the phones, not just the software.
ALLOWED = {
    "\U0001F3BB": "violin (Emoji 1.0)",
    "\U0001F3B8": "guitar (Emoji 1.0)",
    "\U0001F941": "drum (Emoji 3.0)",
    "\U0001F3BA": "trumpet (Emoji 1.0)",
    "\U0001F3B7": "saxophone (Emoji 1.0)",
    "\U0001F3B9": "musical keyboard (Emoji 1.0)",
}

# The ones this actually shipped with, and what they cost.
KNOWN_BAD = {
    "\U0001FA88": "flute, Emoji 15.0 (2022) -- the one that was reported",
    "\U0001FA95": "banjo, Emoji 12.0 (2019)",
    "\U0001FA98": "long drum, Emoji 13.0 (2020)",
    "\U0001FA97": "accordion, Emoji 15.0 (2022)",
}

FILES = ["scripts/build_news_page.py", "scripts/build_status_page.py",
         "scripts/sync_blog.py", "index.html"]

ROT = re.compile(r"var I=\[([^\]]*)\]")
MOD = re.compile(r"I\[\(\(n%(\d+)\)\+\d+\)%(\d+)\]")


def main():
    problems = []
    seen = {}

    for rel in FILES:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            problems.append("%s is missing; the rotation cannot be checked"
                            % rel)
            continue
        src = io.open(path, encoding="utf-8").read()
        m = ROT.search(src)
        if not m:
            problems.append(
                "%s no longer contains a `var I=[...]` rotation -- either it "
                "moved or this check has stopped looking at anything" % rel)
            continue
        glyphs = re.findall(r"'([^']+)'", m.group(1))
        seen[rel] = glyphs
        print("  %-32s %s" % (rel, " ".join(glyphs)))

        for g in glyphs:
            if g in ALLOWED:
                continue
            why = KNOWN_BAD.get(g, "not in the allowed set")
            problems.append(
                "%s rotates in %r (%s). A device without it draws nothing, "
                "and the button's own text is font-size:0 -- so the reader "
                "gets an empty 32px gap on the days this one comes up, and "
                "a button that works perfectly on the other days" % (rel, g, why))

        mm = MOD.search(src)
        if not mm:
            problems.append("%s has a rotation but no index expression to "
                            "match it against" % rel)
        elif int(mm.group(1)) != len(glyphs) or int(mm.group(2)) != len(glyphs):
            problems.append(
                "%s picks the day's instrument with %%%s from a list of %d. "
                "The list and the modulo must agree or some instruments never "
                "appear and the index can run off the end (undefined -- which "
                "is, again, an empty button)"
                % (rel, mm.group(1), len(glyphs)))

    # Four inlined copies is four chances to drift.
    if len(set(tuple(v) for v in seen.values())) > 1:
        problems.append(
            "the four copies of the rotation do not match: %s. The instrument "
            "would change as a reader moves between pages on the same day"
            % "; ".join("%s=%s" % (k, "".join(v)) for k, v in seen.items()))

    print()
    if problems:
        print("  %d PROBLEM(S)\n" % len(problems))
        for p in problems:
            print("  - %s" % p)
        print()
        print("  An emoji the device cannot draw is not a missing icon in any")
        print("  log. It is a blank button, on some days, on some phones.")
        return 1
    print("  All %d copies rotate the same %d instruments, and every one of "
          "them\n  predates the devices that have to draw it."
          % (len(seen), len(next(iter(seen.values())))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
