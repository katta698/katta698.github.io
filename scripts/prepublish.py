#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run every pre-publish check, in order, for any series on this site.

    python scripts/prepublish.py --series az          # before publishing Azure
    python scripts/prepublish.py --series gcpweekly
    python scripts/prepublish.py az-002               # one post
    python scripts/prepublish.py                      # everything, all series
    python scripts/prepublish.py --offline            # skip network checks

Why this exists
---------------
The checks were built one at a time, each in response to something that shipped
broken, and each ended up as its own command. By the time there were four, the
real failure mode was no longer a missing check -- it was a person publishing
after running two of them.

That is not hypothetical here: `verify_claims.py` and `check_prose.py` both
found real defects in already-published posts the moment they were first run,
in posts that had passed every check that existed at the time.

So this is the one command to remember, and the answer to "what do I run before
publishing" is now the same sentence for AWS, Azure and GCP.

What it runs, and why in this order
-----------------------------------
1. `validate_arch_post.py`  structure, nav, diagrams, badge/source parity, and
                            (unless --offline) that every cited page resolves.
                            First because a post with a swallowed body or a
                            missing section is not worth checking the prose of.
2. `verify_claims.py`       every figure a claim attributes to a page is
                            actually on that page. Network; skipped by
                            --offline.
3. `check_prose.py`         retired product names, misspellings, doubled words.
4. `audit_claims.py`        which printed figures appear in no claim at all.
                            Reports rather than fails -- deciding which numbers
                            matter is a judgement, so it never blocks.

Exit code is non-zero if any blocking check failed, so it can gate a workflow.
`audit_claims.py` is advisory and never changes the exit code.
"""
import argparse
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# (script, blocking, needs_network, passes_series, passes_posts)
CHECKS = [
    ("validate_arch_post.py", True,  True,  True,  True),
    ("verify_claims.py",      True,  True,  True,  True),
    ("check_prose.py",        True,  False, True,  True),
    ("audit_claims.py",       False, False, False, True),
]


def run(script, args):
    print("\n" + "=" * 74)
    print("  %s %s" % (script, " ".join(args)))
    print("=" * 74)
    proc = subprocess.run([sys.executable, os.path.join(HERE, script)] + args,
                          cwd=ROOT)
    return proc.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("posts", nargs="*", help="substring of a post filename")
    ap.add_argument("--series", help="restrict to one series key")
    ap.add_argument("--offline", action="store_true",
                    help="skip the checks that fetch vendor pages")
    args = ap.parse_args()

    results, blocked = [], False
    for script, blocking, network, takes_series, takes_posts in CHECKS:
        if network and args.offline:
            results.append((script, "skipped (offline)"))
            continue

        argv = []
        if takes_series and args.series:
            argv += ["--series", args.series]
        if takes_posts and args.posts:
            argv += list(args.posts)
        # Only validate_arch_post.py knows how to fetch cited pages itself; the
        # rest fetch unconditionally or not at all.
        if script == "validate_arch_post.py" and not args.offline:
            argv.append("--check-links")

        code = run(script, argv)
        if code == 0:
            results.append((script, "pass"))
        elif not blocking:
            results.append((script, "advisory findings (does not block)"))
        else:
            results.append((script, "FAILED (exit %d)" % code))
            blocked = True

    print("\n" + "=" * 74)
    print("  PRE-PUBLISH SUMMARY%s" % (" — %s" % args.series if args.series else ""))
    print("=" * 74)
    for script, status in results:
        print("  %-26s %s" % (script, status))
    print()
    print("  %s" % ("DO NOT PUBLISH — fix the failures above." if blocked
                    else "All blocking checks passed."))
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
