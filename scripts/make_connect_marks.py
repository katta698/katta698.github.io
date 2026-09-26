# -*- coding: utf-8 -*-
"""Simplified provider marks, drawn rather than copied.

Not the official logo files: those are trademark-controlled artwork, and
at twenty pixels on a paper card a faithful reproduction is neither
legible nor appropriate. These are the recognisable SHAPE of each -- the
smile, the chevron, the cloud -- so the card reads at a glance without
passing off anyone's artwork as its own.
"""

# viewBox 0 0 24 24 each, drawn to sit on a common baseline
# Just the smile. The first attempt drew an arc over the top of it too,
# which turns the whole thing into a reload icon.
# Shifted up in its own box: the smile alone sits in the bottom third of
# a 24-square, so against a centred word it reads as sagging.
AWS = ('<g transform="translate(0,-3.2)">'
       '<path d="M2.6 13.4c5.9 4.6 13.1 4.6 19 0.2" fill="none" '
       'stroke-width="2.7" stroke-linecap="round"/>'
       '<path d="M17.3 11.9l4.6 1.5-1.2 4.5" fill="none" stroke-width="2.5" '
       'stroke-linecap="round" stroke-linejoin="round"/></g>')

# An A, because at nine pixels that is the only part of the Azure mark
# that survives. The first attempt traced the real logo's two offset
# shapes and the diagonal between them closed up at size, so it read as
# a bowtie -- an hourglass on top of a wedge, which is not a letter and
# not Azure. The notch keeps a nod to the cut through the real mark; the
# two tones keep its light-and-dark blue. Drawn, not copied: see the
# module docstring.
AZURE = ('<path d="M12.4 2.6 2.8 21.6 8.2 21.6 12.4 11.6Z" stroke="none"/>'
         '<path d="M12.4 2.6 22.0 21.6 16.6 21.6 12.4 11.6Z" stroke="none" '
         'opacity=".72"/>'
         '<path d="M9.7 15.4h5.4l1.5 3.4H8.2Z" stroke="none" opacity=".72"/>')

# The cloud in four arcs. Monochrome it is just a cloud -- and this card
# already has cloud shapes on it -- so the colour is the whole message.
GCP = ('<g fill="none" stroke-width="2.6" stroke-linecap="round">'
       '<path d="M5.1 17.7A5.3 5.3 0 0 1 4.2 9" stroke="var(--g-blue,#4285f4)"/>'
       '<path d="M4.2 9a6 6 0 0 1 5.2-4.6" stroke="var(--g-red,#ea4335)"/>'
       '<path d="M9.4 4.4a6 6 0 0 1 7.6 3.1" stroke="var(--g-yellow,#fbbc04)"/>'
       '<path d="M17 7.5a5.3 5.3 0 0 1 1.5 10.2H5.1" '
       'stroke="var(--g-green,#34a853)"/></g>')


def mark(which, cls):
    body = {"aws": AWS, "azu": AZURE, "gcp": GCP}[which]
    return ('<svg class="%s" viewBox="0 0 24 24" aria-hidden="true">%s</svg>'
            % (cls, body))
