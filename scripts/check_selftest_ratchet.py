#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail if fewer checks can prove they work than last time.

    python scripts/check_selftest_ratchet.py
    python scripts/check_selftest_ratchet.py --accept    # after adding self-tests

Why this exists (2026-09-26)
----------------------------
Jay asked how to break a loop: something breaks, I fix it, I say it will not
recur, and it recurs. The honest answer was that my fixes are written against
the instance rather than the class, and that I state "this cannot happen again"
when what I have established is "this one input now fails the gate."

The measurable version of that, counted on the day he asked:

    73 checks in this repo. 3 could prove they work. 4%.

Seventy were in the position the sign-in guard had been in the day before --
green on every run, believed to work, never once demonstrated to catch
anything. That guard had a hole for weeks and passed the exact page it existed
to reject.

A check nobody has watched fail is an assumption wearing a checkmark.

Writing seventy self-tests at once is not realistic, and a gate that demands it
gets deleted. So this is a ratchet: the number may rise and must never fall.
New checks ship with a self-test because the count would otherwise drop below
the recorded floor on the run that adds them.

It deliberately does NOT measure quality. A self-test that only replays the bug
that prompted it proves very little -- the sign-in guard had one. Use a
different input than the one that broke. This file cannot check that for you.
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
BASELINE = os.path.join(SCRIPTS, ".selftest-floor")

SELFTEST = re.compile(r"--self-test|self_test\s*\(")


def survey():
    have, lack = [], []
    for name in sorted(os.listdir(SCRIPTS)):
        if not (name.startswith("check_") and name.endswith(".py")):
            continue
        if name == os.path.basename(__file__):
            continue
        try:
            body = open(os.path.join(SCRIPTS, name), encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        (have if SELFTEST.search(body) else lack).append(name)
    return have, lack


def read_floor():
    try:
        return int(open(BASELINE, encoding="utf-8").read().strip())
    except (OSError, ValueError):
        return None


def main():
    have, lack = survey()
    n, total = len(have), len(have) + len(lack)
    floor = read_floor()

    if "--accept" in sys.argv:
        with open(BASELINE, "w", encoding="utf-8") as fh:
            fh.write("%d\n" % n)
        print("  floor set to %d of %d" % (n, total))
        return 0

    print("  %d of %d check(s) can prove they work (%d%%)"
          % (n, total, round(100.0 * n / total) if total else 0))

    if floor is None:
        print("  no floor recorded yet -- run with --accept to set it at %d" % n)
        return 0

    if n < floor:
        print("  FLOOR BROKEN: was %d, now %d" % (floor, n))
        print()
        print("  A check was added without a self-test, or one lost the test it")
        print("  had. Either way the share of checks nobody has seen fail just")
        print("  went up, which is the direction this exists to prevent.")
        print()
        print("  Checks with no self-test (%d):" % len(lack))
        for name in lack[:12]:
            print("        %s" % name)
        if len(lack) > 12:
            print("        ... and %d more" % (len(lack) - 12))
        return 1

    if n > floor:
        print("  floor is %d and can be raised to %d -- run --accept and commit"
              % (floor, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
