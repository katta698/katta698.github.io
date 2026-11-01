#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Re-wrap a restructured post's sections so the div ids match the headings.

    python scripts/normalise_section_divs.py 7 --write

check_lab_post_shape.section() locates a section by
<div class="section" id="..."> first, and only falls back to <h2 id="...">.
The early posts carry nine of those divs under their ORIGINAL ids -- why,
what, how, challenges, references, takeaways -- and the restructure moves the
h2s without touching them. The result reads correctly in a browser and lies to
every check: asking for the "cleanup" section returns the old div of that name,
which ends at the next section div, so the takeaways sitting after it are
invisible.

This removes the stale wrappers and puts one back around each real section,
keyed on the h2 that opens it, which is the markup weeks 10-25 already use.
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

OPEN_RE = re.compile(r'<div class="section"[^>]*>')


def _matching_close(text, open_start, open_end):
    depth, i = 1, open_end
    while i < len(text):
        if text.startswith("<div", i):
            depth += 1
            i += 4
        elif text.startswith("</div>", i):
            depth -= 1
            if depth == 0:
                return i
            i += 6
        else:
            i += 1
    return -1


def unwrap(text):
    """Remove every section div, keeping its contents."""
    n = 0
    while True:
        m = OPEN_RE.search(text)
        if not m:
            return text, n
        close = _matching_close(text, m.start(), m.end())
        if close < 0:
            # Unbalanced: drop the opening tag alone rather than guess.
            text = text[:m.start()] + text[m.end():]
            n += 1
            continue
        text = text[:m.start()] + text[m.end():close] + text[close + 6:]
        n += 1


def rewrap(text):
    """Wrap each <h2 id="..."> ... up-to-next-<h2 in its own section div."""
    starts = [(m.start(), m.group(1))
              for m in re.finditer(r'<h2[^>]*id="([^"]+)"[^>]*>', text)]
    if not starts:
        return text, 0
    # The last section ends where the post wrapper starts closing: the first
    # point after which nothing remains but </div>s, comments and whitespace.
    # Using rfind("</div>") instead swallowed the wrapper's own closers into
    # the section and emitted one </div> too many.
    tail_at = len(text)
    for m in re.finditer(r"</div>", text):
        rest = text[m.start():]
        if re.fullmatch(r"(?:</div>|<!--.*?-->|\s)*", rest, re.S):
            tail_at = m.start()
            break
    out, prev_end, count = [], 0, 0
    for idx, (pos, sid) in enumerate(starts):
        out.append(text[prev_end:pos])
        end = starts[idx + 1][0] if idx + 1 < len(starts) else (
            tail_at if tail_at > pos else len(text))
        body = text[pos:end]
        out.append('<div class="section" id="%s">\n%s\n</div>\n'
                   % (sid, body.strip()))
        prev_end = end
        count += 1
    out.append(text[prev_end:])
    return "".join(out), count


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("weeks", nargs="+", type=int)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    for wk in a.weeks:
        p = paths.for_week(wk)
        t = io.open(p, encoding="utf-8").read()
        before = re.findall(r'<div class="section"[^>]*id="([^"]+)"', t)
        t2, removed = unwrap(t)
        t3, added = rewrap(t2)
        after = re.findall(r'<div class="section"[^>]*id="([^"]+)"', t3)
        # A post whose divs do not balance renders with sections nested inside
        # one another, and nothing downstream notices. Refuse rather than write.
        depth = 0
        for m in re.finditer(r"<div\b|</div>", t3):
            depth += 1 if m.group(0).startswith("<div") else -1
        if depth != 0:
            print("  week %-2d REFUSED - div depth %+d after normalising"
                  % (wk, depth))
            continue
        if a.write:
            io.open(p, "w", encoding="utf-8", newline="\n").write(t3)
        print("  week %-2d %s  %d removed, %d added" %
              (wk, "normalised" if a.write else "would normalise",
               removed, added))
        print("      was: %s" % ", ".join(before))
        print("      now: %s" % ", ".join(after))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
