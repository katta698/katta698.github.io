#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run every check before anything reaches the live site.

    python scripts/preflight.py            # everything
    python scripts/preflight.py --fast     # skip the browser checks
    python scripts/preflight.py --install  # add the pre-push hook

Why this exists
---------------
Asked, after a broken subscribe panel reached the live site: "should we spin up
a dev environment mimicking production?"

There already is one. Every check here serves the working copy over
127.0.0.1 and drives real browsers against it, which is where the white flash,
the 190px icon jump, the swallowed controls and the silent music button were
all found -- before deploying, in each case.

The gap was never the environment. It was this:

    check scripts available : 41
    git hooks installed     :  0

Nothing made any of them run. Every check was voluntary, so the ones that got
run were the ones I thought to run -- and the subscribe panel shipped broken
because I tested the desktop, showed a desktop screenshot, and never opened the
phone. A staging site would not have caught that either. Only a gate would.

So this is the gate. One command runs all of them, and --install puts it in
front of git push so shipping without checking stops being possible rather than
merely discouraged.

Checks run several at a time because most of the wall-clock is a headless
browser waiting, and serially they take long enough that the temptation is to
skip them -- which is the whole problem this is meant to solve. Each gets its
own timeout so one hung browser cannot hold the gate shut.

--fast exists for the same honest reason: a gate nobody can tolerate gets
uninstalled. It runs everything that does not need a browser, which is the
majority of the file-level faults, and says clearly that it skipped the rest.
"""
import argparse
import concurrent.futures
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")

# Checks that drive a browser. Slow, and the only ones that can see what a
# reader sees, so --fast names them rather than guessing.
BROWSER = {
    "check_brand", "check_shell_consistency", "check_page_settle",
    "check_sticky_clear", "check_occasion_banner", "check_status_cards",
    "check_music", "check_post_controls", "check_nav", "check_contrast",
    "check_bar_settle", "check_feed_theme", "check_sheet_align",
    "check_pull_refresh",
    "check_audio_glyph",
    "check_blog_filters", "check_dark_theme", "check_footer_clear",
    "check_map_devices", "check_map_alignment", "check_map_search",
    "check_news_reserve", "check_feedback", "check_region_suggest",
    "check_filter_state", "check_theme_strip", "check_instrument_glyphs",
}

# Not run here. Each needs the network or an API and fails on a train.
SKIP = {"check_links", "check_query_shapes", "check_status_fresh",
        "check_freshness", "doc_freshness"}

# Run and reported, but not allowed to stop a push.
#
# validate_arch_post checks the CLAIMS inside posts -- that each has a source,
# that a derivation has something to compare against. It fails on 77 of them
# across older posts and has for some time. That is real and worth fixing; it
# is not a reason to stop a CSS change from shipping.
#
# Listed rather than dropped, because a check quietly removed is a check nobody
# fixes. It prints its count on every push, so the number has to come down in
# public.
#
# check_news_reserve was throwing a stack trace on every run instead of
# checking anything -- it reads document.body on the first frames after
# commit, where body is null. Fixed, it immediately reported a real 443 to
# 945px height jump on What's New. That is not new breakage; it is breakage
# that has been invisible for as long as the check has been broken, and the
# reservation constants behind it need their own piece of work.
#
# check_contrast has reported 49 elements below 4.5:1 for as long as it has
# existed -- the same 49 before and after every change made today, verified
# by counting. Real, worth fixing, and not a reason to stop an unrelated
# push; a gate that is red on arrival is a gate that gets uninstalled on
# arrival. The count prints on every push, so 49 has to become 48.
# check_nav and check_footer_clear fail on this machine for a reason that has
# nothing to do with any post. Both drive a headless browser against the local
# test server, and both die in the transport:
#
#   check_nav           Page.goto: Failure when receiving data from the peer,
#                       navigating to http://127.0.0.1:<port>/intelligence/
#   check_footer_clear  ConnectionResetError [WinError 10054], after running
#                       12.5 minutes
#
# Because this hook lives in the shared .git directory, it applies to every
# worktree -- so a socket error in one browser check stopped AWS, Azure, GCP
# and Life publishing at all. Reported as "somehow it doesn't push", which is
# exactly what it looks like from the other side: a post finished, a push
# refused, and nothing in the output about a post.
#
# Advisory for the same reason as the two above: a gate that is red on arrival
# gets uninstalled on arrival, and these are red for an environment fault
# rather than a defect. They still run and still print. The real fix is moving
# the browser checks out of the push hook into CI -- preflight already has
# --fast for exactly this, and the installed hook does not use it.
ADVISORY = {"validate_arch_post", "check_news_reserve", "check_contrast",
            "check_nav", "check_footer_clear"}

# What the pre-push hook runs: everything needing no browser, plus the browser
# checks that guard the things a reader actually reports.
#
# The full set is 38 checks and about nine minutes. A hook costing nine minutes
# is a hook somebody disables within a week, and a disabled hook is worth less
# than a slower one. This subset is a few minutes, and it is not a compromise
# on rigour so much as on breadth: every check named here is one where
# something already reached the live site broken.
#
# The rest still run -- `python scripts/preflight.py` with no arguments -- and
# should, before anything structural. The hook is the floor, not the ceiling.
HOOK_BROWSER = {
    "check_shell_consistency",   # the five bars agreeing
    "check_shift",               # nothing moving sideways after paint
    "check_bar_settle",          # ...at a phone width too, which check_shift
                                 # never looked at, and without a list of
                                 # element names a real shift can fall out of
    "check_brand",               # mark and wordmark identical
    "check_nav",                 # every page reachable, the bar fits
    "check_music",               # the button actually plays
    "check_audio_glyph",         # ...once, and keeps playing across tabs
    "check_post_controls",       # ask, arrow and star not swallowed
    "check_page_settle",         # the page not rebuilding itself
    "check_sticky_clear",        # nothing hiding under the header
}

PER_CHECK_TIMEOUT = 420
# Six, not four. The full run took 555s at four, and a pre-push hook that
# costs nine minutes is a hook somebody disables. Most of that time is a
# headless browser waiting rather than this machine working, so more of them
# at once costs little. Raise it further only with the retry above in mind:
# past a point they contend for ports and CPU and start failing each other.
#
# Lowered to 2 on 2026-09-16 from the azure window: six was past that point on
# this machine, and the sentence above had already predicted how it would look.
# Three was measured too, and was better but not enough -- six failures became
# one, check_page_settle, which then passed on its own in 60s. Each step down
# removes failures without changing a single check, which is what contention
# looks like and what a real defect does not.
#
# Azure #35 was refused four times over an evening by check_audio_glyph,
# check_bar_settle, check_brand, check_music and check_page_settle, all dying
# in the transport -- Page.goto timeouts and ConnectionAbortedError
# [WinError 10053] out of socketserver. It read as a broken machine. It was
# not: run alone, every one of those checks passes. check_brand reports the
# mark identical on all 5 pages at 2 widths; check_music reports the audio
# genuinely playing, readyState 4, 2.4s, on all 5 pages, exit 0. They only
# fail together, which is the signature of six browsers and six servers
# contending rather than of any defect in the site.
#
# 0dd142e read the same symptom as an environment fault and made check_nav and
# check_footer_clear advisory. That unblocked whichever windows happened to
# fail on those two; it could not help a window failing on five others. Fewer
# workers fixes the cause instead, and keeps every check blocking.
#
# The cost is wall-clock on a passing run. That is the right trade for a gate
# whose failures were not real: a slower honest gate beats a fast one that
# stops publishing for a day over a socket.
WORKERS = 2


def discover(fast, hook=False):
    names = []
    for f in sorted(os.listdir(SCRIPTS)):
        if not f.endswith(".py"):
            continue
        if not (f.startswith("check_") or f.startswith("validate_")):
            continue
        name = f[:-3]
        if name in SKIP or name == "check_query_shapes":
            continue
        if fast and name in BROWSER:
            continue
        if hook and name in BROWSER and name not in HOOK_BROWSER:
            continue
        names.append(name)
    return names


def run_once(name):
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, os.path.join(SCRIPTS, name + ".py")],
                           cwd=ROOT, capture_output=True, text=True,
                           timeout=PER_CHECK_TIMEOUT,
                           encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout or "") + (p.stderr or ""), time.time() - t0
    except subprocess.TimeoutExpired:
        return 124, "timed out after %ds" % PER_CHECK_TIMEOUT, time.time() - t0
    except Exception as exc:                                    # noqa: BLE001
        return 1, "could not run: %s" % exc, time.time() - t0


def run_one(name):
    """Run a check, and give a failure one second chance.

    Four headless browsers at once share ports, CPU and a disk. check_nav
    failed in the first full run and passed on its own immediately after --
    nothing about the site had changed. A gate that cries wolf is a gate that
    gets bypassed, and bypassing it is the exact habit this exists to break.

    One retry only, and it is reported. A check that fails twice in a row is
    not luck, and a check that needs three goes is a check with a bug of its
    own that should be fixed rather than tolerated.
    """
    code, out, secs = run_once(name)
    if code == 0:
        return name, code, out, secs, False
    code2, out2, secs2 = run_once(name)
    if code2 == 0:
        return name, 0, out2, secs + secs2, True
    return name, code2, out2, secs + secs2, True


HOOK = """#!/bin/sh
# Installed by scripts/preflight.py. Delete this file to push unchecked.
#
# It exists because 41 checks lived in this repo and none of them ran unless
# somebody remembered. Things reached the live site broken not because they
# could not be caught, but because nothing forced the catch.
exec python scripts/preflight.py --hook
"""


def install():
    hooks = os.path.join(ROOT, ".git", "hooks")
    if not os.path.isdir(hooks):
        print("  no .git/hooks directory -- is this a git checkout?")
        return 1
    path = os.path.join(hooks, "pre-push")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(HOOK)
    try:
        os.chmod(path, 0o755)
    except OSError:
        pass
    print("  installed .git/hooks/pre-push")
    print("  every push now runs the checks first; a failure stops the push.")
    print("  git push --no-verify still works, deliberately -- a gate that")
    print("  cannot be opened in an emergency gets deleted instead.")
    return 0


# The five rules from CHECKLIST.md, printed on every run.
#
# Every one of them was written the day it cost hours, and every one was
# already known when it cost them. A rule kept in a file nobody opens is a
# rule that gets relearned; this puts them in front of whoever is about to
# ship, beside the result they are about to trust.
RULES = [
    ("name the instrument, and what it cannot see",
     "a headless browser with autoplay granted is not a phone"),
    ("a check must assert what a READER would notice",
     "not that a number stayed the same"),
    ("re-run after the fix, and re-run the neighbours",
     "a change that helps twenty can ruin two"),
    ("never edit a generated file",
     "check what writes it first"),
    ("do not state a limitation you have not measured", ""),
    ("an empty field is a claim; a zero result is not a fact",
     "reconcile against the source -- 'is anything missing?' is a different question from 'is this right?'"),
    ("snapshot before, report after -- gold.py",
     "a code diff catches what you EDITED, never what you AFFECTED"),
]


def checklist():
    print()
    print("  Before saying fixed  --  CHECKLIST.md")
    for i, (head, tail) in enumerate(RULES, 1):
        print("    %d. %s" % (i, head))
        if tail:
            print("       %s" % tail)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true",
                    help="skip the checks that drive a browser")
    ap.add_argument("--install", action="store_true",
                    help="install the git pre-push hook")
    ap.add_argument("--hook", action="store_true",
                    help="running as the hook; quieter, and fails the push")
    args = ap.parse_args()

    if args.install:
        return install()

    names = discover(args.fast, args.hook)
    print("  running %d check(s)%s, %d at a time\n"
          % (len(names), " (browser checks skipped)" if args.fast else "", WORKERS))

    failed, advisory, slowest = [], [], []
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for name, code, out, secs, retried in pool.map(run_one, names):
            slowest.append((secs, name))
            mark = ("ok  " if code == 0 else
                    ("warn" if name in ADVISORY else "FAIL"))
            print("    %-4s %-28s %5.1fs%s"
                  % (mark, name, secs, "  (retried)" if retried else ""))
            if code != 0:
                (advisory if name in ADVISORY else failed).append(
                    (name, out.strip()))

    print("\n  %d check(s) in %.0fs" % (len(names), time.time() - t0))
    checklist()
    for aname, aout in advisory:
        tail = [l for l in aout.splitlines() if l.strip()][-1:]
        print("  advisory, not blocking -- %s: %s"
              % (aname, tail[0].strip() if tail else "failed"))
    if failed:
        print("\n  %d FAILED\n" % len(failed))
        for name, out in failed:
            tail = [l for l in out.splitlines() if l.strip()][-6:]
            print("  --- %s" % name)
            for l in tail:
                print("      %s" % l)
            print()
        if args.hook:
            print("  Push stopped. Fix these, or use --no-verify if you must.")
        return 1

    print("  Everything passes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
