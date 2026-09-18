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

# Every file carrying a rotation, FOUND rather than listed.
#
# This check shipped with a list of four: three builders and index.html. It
# passed, and two pages kept the old ten-instrument rotation --
# intelligence/index.html and now.html, both hand-maintained, neither on the
# list. Reported as: "the toggle keeps changing when I change the tabs. When I
# click blog I see one, when I click intelligence I see one, when I click
# what's new it comes back to the blog."
#
# So the bug this file exists to prevent walked straight past it, because a
# hardcoded list is only ever as complete as the afternoon it was written in.
# It now walks the repository: anything that sets --jk-ins has to agree with
# everything else that does.
SKIP_DIRS = {".git", "node_modules", "_archive", "_templates", "__pycache__"}

ROT = re.compile(r"var I=\[([^\]]*)\]")


def rotation_files():
    """Every file that sets --jk-ins, wherever it happens to live."""
    out = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS
                   and not d.startswith(".")]
        for name in files:
            if not name.endswith((".html", ".py")):
                continue
            # A check never sets the rotation; it only ever talks about one.
            # This file quotes both the setProperty call and the regex in its
            # own comments, so every "does the text appear" rule I tried found
            # this file and reported it as the page that disagrees. Excluding
            # checks by name is blunt and it is also simply true.
            if name.startswith("check_"):
                continue
            path = os.path.join(base, name)
            try:
                src = io.open(path, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            # setProperty, not merely a mention. This check itself talks
            # about --jk-ins at length and quotes the rotation regex, so
            # "contains the string" made it find its own source and report
            # itself as the odd one out. What matters is the files that SET
            # the property; everything else is only describing it.
            if "setProperty('--jk-ins'" in src and ROT.search(src):
                out.append(os.path.relpath(path, ROOT).replace("\\", "/"))
    return sorted(out)
MOD = re.compile(r"I\[\(\(n%(\d+)\)\+\d+\)%(\d+)\]")


def main():
    problems = []
    seen = {}

    found = rotation_files()
    if not found:
        print("  nothing on this site sets --jk-ins. Either the instrument "
              "moved\n  or this check has stopped looking at anything.")
        return 1

    for rel in found:
        path = os.path.join(ROOT, rel)
        src = io.open(path, encoding="utf-8", errors="replace").read()
        m = ROT.search(src)
        if not m:
            continue
        glyphs = re.findall(r"'([^']+)'", m.group(1))
        seen[rel] = glyphs
        # 150 pages carry this. Printing every one buries the answer, so the
        # first few stand as a sample and any disagreement is named in full
        # below -- a difference is the thing worth reading, not a list.
        if len(seen) <= 4:
            print("  %-44s %s" % (rel[-44:], " ".join(glyphs)))

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

    # The OTHER list: the names in the tooltip.
    #
    # site-footer.js holds its own INSTRUMENTS array -- glyph plus name --
    # and paints btn.title from it, while the <head> script paints the glyph
    # through --jk-ins. Two lists, one button, indexed by the same day
    # arithmetic: they agree only if they hold the same instruments in the
    # same order.
    #
    # This check could not see that list at all, because it looks for
    # `var I=[...]`. So when the head list was cut from ten to six, this
    # passed on 152 files while the glyph and the tooltip disagreed on every
    # day of the following week -- the drum shown, "Mridangam" in the
    # tooltip. Found because check_audio_glyph failed and its error message
    # happened to quote the button's title attribute.
    js_path = os.path.join(ROOT, "blog", "assets", "site-footer.js")
    if os.path.exists(js_path) and seen:
        js = io.open(js_path, encoding="utf-8", errors="replace").read()
        jm = re.search(r"var INSTRUMENTS = \[(.*?)\];", js, re.S)
        if not jm:
            problems.append(
                "site-footer.js no longer has an INSTRUMENTS list. It paints "
                "the tooltip name on the music button, so either it moved or "
                "this half of the check is looking at nothing")
        else:
            pairs = re.findall(r"\['([^']+)',\s*'([^']+)'\]", jm.group(1))
            names = [g for g, _n in pairs]
            head = next(iter(seen.values()))
            print("  tooltip list: %s" % " ".join(
                "%s=%s" % (g, n) for g, n in pairs))
            if names != head:
                problems.append(
                    "the glyph list and the tooltip list do not match. The "
                    "button would draw %s while its tooltip named %s. "
                    "head=%s  tooltip=%s"
                    % (head[0], pairs[0][1] if pairs else "?",
                       "".join(head), "".join(names)))
            for g in names:
                if g not in ALLOWED:
                    problems.append(
                        "site-footer.js names %r in the tooltip list (%s)"
                        % (g, KNOWN_BAD.get(g, "not in the allowed set")))

    # Every inlined copy is another chance to drift, and this is the branch
    # that fires on the reported bug: two pages holding different rotations,
    # so the instrument changes as a reader moves between tabs.
    #
    # It had three placeholders and one argument, so reaching it raised
    # TypeError instead of reporting anything -- the check would have crashed
    # on the one failure it was written to describe. Found by making it fail
    # on purpose rather than by reading it.
    variants = {}
    for rel, glyphs in seen.items():
        variants.setdefault(tuple(glyphs), []).append(rel)
    if len(variants) > 1:
        big = max(variants.values(), key=len)
        odd = [r for group in variants.values() if group is not big
               for r in group]
        problems.append(
            "%d of the %d files disagree about the rotation, so the "
            "instrument changes as a reader moves between pages on the same "
            "day. The odd ones out: %s"
            % (len(odd), len(seen), ", ".join(sorted(odd)[:6])
               + (" ..." if len(odd) > 6 else "")))

    print()
    if problems:
        print("  %d PROBLEM(S)\n" % len(problems))
        for p in problems:
            print("  - %s" % p)
        print()
        print("  An emoji the device cannot draw is not a missing icon in any")
        print("  log. It is a blank button, on some days, on some phones.")
        return 1
    if len(seen) > 5:
        print("  ...and %d more" % (len(seen) - 5))
    print()
    print("  All %d files that set the instrument rotate the same %d, and "
          "every one\n  of them predates the devices that have to draw it."
          % (len(seen), len(next(iter(seen.values())))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
