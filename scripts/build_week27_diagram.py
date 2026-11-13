# -*- coding: utf-8 -*-
"""Week 27 architecture diagram: one request count, three payload sizes.

    python scripts/build_week27_diagram.py > frag.svg
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aws_arch import Diagram, RED, GREEN, MUTED, SQUID   # noqa: E402

DESC = (
    "An AWS Lambda function in a VPC issues 20,000 reads against an Amazon "
    "ElastiCache Serverless cache for Valkey, three times, at value sizes of "
    "1 KB, 10 KB and 100 KB. The request count is identical each time. The "
    "ECPUs billed are 20,803, 200,830 and 2,000,960 respectively, because an "
    "ECPU is charged per kilobyte transferred rather than per request."
)


def build():
    d = Diagram(960, 430, DESC)

    d.cloud(14, 14, 932, 400)
    d.group(44, 56, 872, 340, "Region: us-east-1")
    d.group(72, 92, 500, 280,
            "VPC — a serverless cache has no public endpoint")

    d.icon(120, 200, "lambda", "load client", "20,000 reads, each run",
           size=52)
    d.icon(400, 200, "elasticache", "Valkey 9.0", "serverless", size=52)

    # Three runs, same request count, different payload.
    d.arrow(184, 196, 392, 176, step="1")
    d.arrow(184, 216, 392, 216, step="2")
    d.arrow(184, 236, 392, 256, step="3")

    # Label each arrow at its own end, so a reader can tell which run is
    # which. Floating captions near a bundle of arrows cannot say that.
    d.note(322, 164, "1 KB", colour=MUTED, size=11)
    d.note(322, 206, "10 KB", colour=MUTED, size=11)
    d.note(322, 272, "100 KB", colour=MUTED, size=11)

    # The result, outside the VPC box so it reads as the conclusion.
    d.note(620, 140, "SAME REQUEST COUNT, BILLED:", weight="700", size=10.5,
           colour=MUTED)
    # Columns are positioned, not spaced: runs of spaces collapse in SVG
    # text, so a padded string does not line up.
    for i, (y, size, ecpus, colour, weight, fill, stroke) in enumerate([
            (156, "1 KB", "20,803", GREEN, "400", "#F2F3F3", None),
            (196, "10 KB", "200,830", SQUID, "400", "#F2F3F3", None),
            (236, "100 KB", "2,000,960", RED, "600", "#FDF3F2", RED)]):
        d.box(620, y, 290, 34, fill=fill, stroke=stroke)
        d.step(640, y + 17, str(i + 1))
        d.note(664, y + 22, size, size=11.5, colour=colour, weight=weight)
        d.note(760, y + 22, ecpus + " ECPUs", size=11.5, colour=colour,
               weight=weight)
    d.note(620, 296, "96x the cost. 20,000 requests either way.",
           size=11, colour=MUTED)

    d.note(72, 388,
           "An ECPU is charged per kilobyte moved, not per request.",
           colour=SQUID, weight="600", size=12.5)

    d.assert_clean()
    return d


if __name__ == "__main__":
    print(build().render())
