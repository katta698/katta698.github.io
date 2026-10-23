# -*- coding: utf-8 -*-
"""Build connect/sirivennela-preview.html.

A copy of the connect card with Sirivennela Seetharama Sastry in the mist
behind the tree, so it can be seen on a real phone before anything touches
the live card.

    python scripts/build_sirivennela_preview.py

No text. An earlier pass carried a line of his verse in the sky and a panel
of it behind the seal; asked on 2026-10-22 to drop both -- "no need of
words". What is left is what was actually asked for: him, present in the
picture, for anyone who looks closely enough to find him.

He sits at z-index -2, BEHIND the ink scene at -1, so the pine and the
seated figure are drawn over him and he reads as part of the wash rather
than as a photograph laid on top. .wrap isolates, so -2 still sits above
the paper grain on <html> and cannot fall out of the card.

The alt text names him. It is not visible, it costs the design nothing, and
without it he is an unattributed photograph of a real person to every
screen reader that meets this page.

Two placement faults found by rendering rather than by reading, recorded so
they are not repeated:

  * Anything positioned next to .hero lands inside .bottom, whose top edge
    IS the button line -- an earlier version rendered across "Connect on
    LinkedIn". It belongs to .wrap, the card itself.

  * The mist image first showed a faint RECTANGLE around him: the alpha
    falloff ran past the image edge and never reached zero. See
    build_sirivennela_art.py, which checks the edges are clear.
"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'connect', 'index.html')
OUT = os.path.join(ROOT, 'connect', 'sirivennela-preview.html')

CSS = """
/* Sirivennela, in the mist.  PREVIEW ONLY. */
.siri-mist {
  position: absolute;
  z-index: -2;
  right: 2%;
  top: 15svh;
  width: 46%;
  max-width: 196px;
  height: auto;
  opacity: .26;
  pointer-events: none;
  -webkit-user-select: none;
  user-select: none;
}
/* Higher in the dark, not lower. The card picks its theme from the
   sun, so it is dark for half of every day, and at .18 against the
   night wash he was not faint -- he was absent. */
[data-theme="dark"] .siri-mist { opacity: .32; }
"""

IMG = ('\n  <img class="siri-mist" src="/connect/siri-mist.webp"'
       ' width="380" height="489" decoding="async"'
       ' alt="Sirivennela Seetharama Sastry">')


def main():
    s = io.open(SRC, encoding='utf-8').read()

    # Not in the sitemap, not in search. A preview is for one pair of eyes.
    s = s.replace(
        '<link rel="canonical" href="https://jayanthkatta.com/connect/">',
        '<meta name="robots" content="noindex,nofollow">\n'
        '<link rel="canonical" href="https://jayanthkatta.com/connect/">')
    s = s.replace(
        '<title>Jayanth Katta &mdash; Connect</title>',
        '<title>Jayanth Katta &mdash; Connect (Sirivennela preview)</title>')

    i = s.rindex('</style>')
    s = s[:i] + CSS + s[i:]

    m = re.search(r'<main class="wrap"[^>]*>', s)
    assert m, 'wrap not found'
    s = s[:m.end()] + IMG + s[m.end():]

    io.open(OUT, 'w', encoding='utf-8', newline='').write(s)
    print('wrote %s  %d bytes' % (os.path.relpath(OUT, ROOT), len(s)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
