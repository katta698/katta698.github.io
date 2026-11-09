# -*- coding: utf-8 -*-
"""Week 26 architecture diagram: one table, two paths, one of them unchecked.

    python scripts/build_week26_diagram.py > frag.svg

The AWS icon package has no standalone DAX mark -- AWS draws DAX as a
DynamoDB resource -- so the cluster carries the DynamoDB icon, labelled.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aws_arch import Diagram, RED, GREEN, MUTED, SQUID   # noqa: E402

DESC = (
    "An AWS Lambda function whose IAM role is scoped to one tenant reads one "
    "pooled Amazon DynamoDB table by two paths. Going direct, the role's "
    "dynamodb:LeadingKeys condition is evaluated and a request for another "
    "tenant's item is refused with AccessDeniedException. Going through the "
    "Amazon DynamoDB Accelerator cluster, the condition is never evaluated "
    "because the cluster's own service role authorises the read, and the same "
    "request returns the other tenant's data."
)


def build():
    d = Diagram(960, 470, DESC)

    d.cloud(14, 14, 932, 440)
    d.group(44, 56, 872, 380, "Region: us-east-1")

    d.group(72, 92, 452, 318,
            "VPC — DAX has no public endpoint, so the function lives here too")

    # The caller. One role, one policy, scoped to tenant-alpha.
    d.icon(134, 208, "lambda", "tenant-alpha", "scoped to tenant-alpha",
           size=52)

    # Path 1: direct. The condition is on this path and it holds.
    d.component(250, 116, 236, 64, "IAM condition evaluated",
                "dynamodb:LeadingKeys + Null", accent=GREEN)
    d.arrow(192, 214, 244, 176, step="1")
    d.note(250, 198, "AccessDeniedException — refused", colour=GREEN,
           weight="600")

    # Path 2: through the cache. No condition exists on this path at all.
    d.icon(300, 276, "dynamodb", "DAX cluster", "3 nodes · 3 AZs", size=52)
    d.arrow(192, 250, 294, 288, step="2")
    d.note(250, 392, "role's conditions never evaluated", colour=RED,
           weight="600")

    # The one table both paths reach.
    d.icon(700, 206, "dynamodb", "Pooled table", "partition: tenant_id",
           size=56)

    # Direct path reaches the table through a gateway endpoint (free).
    d.arrow(492, 158, 694, 212)
    # DAX reaches it under its OWN service role, which is table-wide.
    d.arrow(368, 292, 694, 258)
    # Two notes rather than one two-line string: an SVG <text> element does
    # not break on a newline character, it renders the whole string on a
    # single baseline and lets it run off the edge.
    d.note(556, 344, "DAX service role authorises this read:", colour=RED,
           size=11)
    d.note(556, 360, "table-wide, with no tenant in it.", colour=RED, size=11)

    d.note(72, 428,
           "Same caller. Same table. The condition exists on one path only.",
           colour=SQUID, weight="600", size=12.5)

    d.assert_clean()
    return d


if __name__ == "__main__":
    print(build().render())
