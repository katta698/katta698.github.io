# -*- coding: utf-8 -*-
"""Week 28 architecture diagram: two regions, one irreversible promotion.

    python scripts/build_week28_diagram.py > frag.svg
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="strict")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aws_arch import Diagram, RED, GREEN, MUTED, SQUID   # noqa: E402

DESC = (
    "A PostgreSQL primary in us-east-1 replicates asynchronously to a "
    "cross-region read replica in us-west-2. A Lambda function in the "
    "primary's VPC writes load to the primary. An Amazon Application "
    "Recovery Controller Region switch plan, executed in us-west-2, promotes "
    "the replica to a standalone primary. Measured: replication lag of 4.2 "
    "seconds on average and 20 seconds at peak under load, and a promotion "
    "that completed in 726 seconds. After promotion the replica no longer "
    "replicates and cannot be returned to being a replica."
)


def build():
    d = Diagram(960, 450, DESC)

    d.cloud(14, 14, 932, 420)
    d.group(44, 56, 400, 236, "Region: us-east-1 (primary)")
    d.group(516, 56, 400, 236, "Region: us-west-2 (standby)")

    d.icon(110, 140, "lambda", "writer", "6.4M rows", size=48)
    d.icon(300, 140, "rds", "PostgreSQL 18.6", "db.t4g.micro", size=48)
    d.icon(700, 140, "rds", "read replica", "db.t4g.micro", size=48)

    # 1: the write load that makes lag mean anything.
    d.arrow(170, 166, 292, 166, step="1")

    # 2: replication, the only link between the two regions.
    d.arrow(364, 166, 692, 166, step="2")
    d.note(420, 206, "asynchronous — lag 4.2s avg, 20s peak",
           colour=SQUID, size=11, weight="600")

    # 3: the runbook. Drawn below both regions because it is not inside
    # either one -- ARC runs a data plane in every region, which is why
    # activating us-west-2 does not call into us-east-1.
    d.box(190, 318, 580, 44, fill="#F2F3F3", stroke=MUTED)
    d.step(216, 340, "3")
    d.note(240, 345,
           "ARC Region switch plan — activate us-west-2 → promote-replica",
           size=12, colour=SQUID, weight="600")

    d.arrow(790, 318, 790, 196, dashed=True)

    d.note(516, 390, "AFTER PROMOTION:", weight="700", size=10.5, colour=MUTED)
    d.note(516, 412, "standalone primary. There is no un-promote.",
           size=11.5, colour=RED, weight="600")

    d.note(44, 390, "DATABASE SERVING AGAIN:", weight="700", size=10.5, colour=MUTED)
    d.note(44, 412, "160 s after the promote call", size=13, colour=GREEN, weight="700")

    d.assert_clean()
    return d


if __name__ == "__main__":
    print(build().render())
