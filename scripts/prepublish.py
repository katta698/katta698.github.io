#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run every pre-publish check, in order, for any series on this site.

    python scripts/prepublish.py --series az          # before publishing Azure
    python scripts/prepublish.py --series gcpweekly
    python scripts/prepublish.py az-002               # one post
    python scripts/prepublish.py                      # everything, all series
    python scripts/prepublish.py --offline            # skip network checks
    python scripts/prepublish.py --ci                 # what prepublish.yml runs

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
4. `check_page_structure.py` where things sit on the served page, not what
                            colour they are: post navigation inside the site
                            header, two Next links, unbalanced tags or comments,
                            an empty post-nav, a page that is not valid UTF-8.
5. `check_index_complete.py` that every post in posts/ actually reached the
                            index, cards.json and rss.xml. This is the failure
                            with no symptom: four worktrees publish to one
                            branch, and a window that syncs before rebasing
                            rebuilds the index without another window's post.
                            The post's own page serves fine; its card, filter
                            count, RSS item and cards.json entry are absent, and
                            nothing errors. It happened on 2026-08-17 -- a9bbdd6
                            shipped an index missing an Azure post published
                            fifteen minutes earlier, and was noticed only
                            because a person went looking for it.
6. `fix_series_nav.py --check` that Previous/Next on the hand-built pages still
                            agrees with strict date order across every series.
7. `audit_claims.py`        which printed figures appear in no claim at all.
                            Reports rather than fails -- deciding which numbers
                            matter is a judgement, so it never blocks.

Checks 4, 5 and 6 are site-wide, not per-post, and ignore the post arguments.
They are cheap and they are exactly the checks a scoped run would miss:
publishing a post changes its NEIGHBOUR's nav and rewrites the shared index, so
the page that breaks is one this push does not touch -- and in the index case,
the post that disappears belongs to a different window entirely.

Both were written after the bug they catch and then left unwired, which is the
same failure this file exists to prevent -- a check nobody runs. `fix_series_nav`
scoped Previous/Next per series at first, making the 32 hand-built architecture
pages the only ones on the site that navigated differently from the ~110 pages
sync_blog.py generates; with three series publishing daily that put a dead end at
the front of each. Nothing failed. It was noticed by a person looking at a page.

Exit code is non-zero if any blocking check failed, so it can gate a workflow.
`audit_claims.py` is advisory and never changes the exit code.

--ci, and why it is not just --offline
--------------------------------------
Checks 1 and 2 fetch vendor documentation, so both can fail for reasons that
have nothing to do with the post: an edge returning 503, a DNS blip, a runner
without egress. Left alone, that makes the gate in `prepublish.yml` fail on
good posts at random, and a gate that cries wolf gets disabled -- at which
point the findings that *were* real stop being read.

`--offline` is the wrong answer to that. It does not run the network checks at
all, so a claim citing a figure that is not on the page sails through, and the
most valuable check in the set is the one CI never performs.

`--ci` keeps them running and narrows what they are allowed to fail on: a
finding blocks when the page loaded and the post was wrong about it, and
reports without blocking when the page could not be read. Structure and prose
are unaffected -- they need no network, so they block unconditionally.

Mechanically: `verify_claims.py --fail-on missing`, plus the transient-status
retry in `validate_arch_post.py`, which downgrades 429/5xx to a warning after
three attempts while leaving 404 an error. Both still print everything they
found; only the exit code changes.
"""
import argparse
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# (script, blocking, needs_network, passes_series, passes_posts)
#
# check_page_structure.py and fix_series_nav.py take neither --series nor post
# names: both look at every served page. That is deliberate rather than an
# omission -- publishing a post rewrites its neighbour's Previous/Next, so the
# page a scoped run would need to check is the one the push did not touch.
CHECKS = [
    ("validate_arch_post.py",   True,  True,  True,  True),
    ("verify_claims.py",        True,  True,  True,  True),
    ("check_prose.py",          True,  False, True,  True),
    ("check_page_structure.py", True,  False, False, False),
    # Diagrams, not prose: an inline SVG that leans on currentColor renders
    # correctly inline and vanishes once blog.js lightboxes it. Every other
    # check here is about content, so nothing caught that until a reader did.
    ("check_theme_render.py",   True,  False, True,  True),
    # The stylesheet half of the same problem. check_theme_render.py asks
    # whether a diagram survives being re-coloured; this asks whether dark mode
    # ever reaches an element at all. `code.inline` sat inside the dark
    # blanket's :not(code) exclusion and kept a white chip on a dark page, on
    # every post using inline code, until a reader asked about it on
    # 2026-08-28. Nothing caught it because every other check reads posts and
    # this lived in blog.css.
    ("check_dark_theme.py",     True,  False, True,  True),
    ("check_index_complete.py", True,  False, False, False),
    ("fix_series_nav.py",       True,  False, False, False),
    ("audit_claims.py",         False, False, False, True),
]


def git_state_is_clean_enough():
    """Refuse to publish out of a half-finished or stale rebase.

    **Ask git where its directory is; never test a literal `.git/rebase-merge`.**
    In a worktree `.git` is a *file* pointing elsewhere, so the real state lives
    under `<repo>/.git/worktrees/<name>/`. Testing the literal path reports "no
    rebase in progress" while one is stuck.

    That is not hypothetical. On 2026-08-19 a `git rebase` hit a command
    timeout and died mid-run, leaving a stale `rebase-merge` directory. Every
    later rebase refused to start, and the hand-rolled check that should have
    caught it was looking at a path that does not exist in a worktree, so it
    reported the tree as clean. Recovery cost a detached HEAD and a branch
    pointer that had to be moved by hand.

    Returns (ok, message).
    """
    try:
        git_dir = subprocess.run(
            ["git", "rev-parse", "--git-dir"], cwd=ROOT,
            capture_output=True, text=True, check=True).stdout.strip()
    except Exception as exc:                                  # noqa: BLE001
        # Not fatal: a source tree without git still publishes fine.
        return True, "could not determine the git dir (%s); skipping" % exc

    if not os.path.isabs(git_dir):
        git_dir = os.path.join(ROOT, git_dir)

    for name in ("rebase-merge", "rebase-apply"):
        path = os.path.join(git_dir, name)
        if os.path.isdir(path):
            return False, (
                "a rebase is in progress or was left behind:\n"
                "  %s\n"
                "Finish it with `git rebase --continue`, abandon it with "
                "`git rebase --abort`, or if neither applies, remove that "
                "directory. Publishing from this state pushes a tree git does "
                "not consider settled." % path)
    return True, ""


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
    ap.add_argument("--ci", action="store_true",
                    help="run the network checks but let them fail only on a "
                         "real defect, not on an unreachable page")
    ap.add_argument("--sitewide-only", action="store_true",
                    help="run only the checks that another window's push can "
                         "invalidate; skip the per-post ones")
    args = ap.parse_args()

    if args.ci and args.offline:
        print("--ci and --offline are contradictory: --offline does not run "
              "the network checks at all, so there is nothing for --ci to "
              "narrow. Pick one.")
        return 2

    ok, why = git_state_is_clean_enough()
    if not ok:
        print("\n" + "=" * 74)
        print("  GIT STATE")
        print("=" * 74)
        print("  " + why.replace("\n", "\n  "))
        print("\n  DO NOT PUBLISH — resolve the rebase first.")
        return 1

    results, blocked = [], False
    for script, blocking, network, takes_series, takes_posts in CHECKS:
        # --sitewide-only exists for publish.py's convergence loop. When another
        # window pushes mid-run, the tree changes underneath us and has to be
        # re-verified -- but only the site-wide invariants can actually have
        # changed. Whether THIS post's cited pages resolve does not depend on
        # what else landed, and re-fetching every link on every retry is what
        # made the full run slower than the interval between pushes, so it could
        # never finish against a tree that was still current.
        #
        # The site-wide checks are exactly those that take neither --series nor
        # post names, because they look at every served page by design.
        if args.sitewide_only and (takes_series or takes_posts):
            continue
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
        # See "--ci" above: a page that would not load is not a defect in the
        # post, and must not fail an automated gate.
        if script == "verify_claims.py" and args.ci:
            argv += ["--fail-on", "missing"]
        # fix_series_nav.py REWRITES pages when run bare. A gate must report,
        # never edit -- a CI run that silently corrected the tree would make the
        # push pass while the committed pages stayed wrong.
        if script == "fix_series_nav.py":
            argv.append("--check")

        code = run(script, argv)
        if code == 0:
            results.append((script, "pass"))
        elif not blocking:
            results.append((script, "advisory findings (does not block)"))
        else:
            results.append((script, "FAILED (exit %d)" % code))
            blocked = True

    print("\n" + "=" * 74)
    print("  PRE-PUBLISH SUMMARY%s%s"
          % (" — %s" % args.series if args.series else "",
             "  [ci]" if args.ci else ""))
    print("=" * 74)
    for script, status in results:
        print("  %-26s %s" % (script, status))
    print()
    if args.ci:
        print("  ci mode: unreachable vendor pages reported, not failed.")
    print("  %s" % ("DO NOT PUBLISH — fix the failures above." if blocked
                    else "All blocking checks passed."))
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
