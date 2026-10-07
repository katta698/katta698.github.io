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
import atexit
import concurrent.futures
import io
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
    # Sits beside check_page_settle deliberately: that one watches the page's
    # shape, this one its visibility. See the note in its docstring.
    "check_entrance_blink",
    "check_sticky_clear", "check_occasion_banner", "check_status_cards",
    "check_music", "check_post_controls", "check_nav", "check_contrast",
    "check_bar_settle", "check_feed_theme", "check_sheet_align",
    "check_pull_refresh",
    "check_audio_glyph",
    "check_blog_filters", "check_dark_theme", "check_footer_clear",
    "check_map_devices", "check_map_alignment", "check_map_search",
    "check_news_reserve", "check_feedback", "check_region_suggest",
    "check_filter_state", "check_theme_strip", "check_instrument_glyphs",
    "check_shell_parts", "check_reachable",
    "check_player_overlays", "check_no_orphan_music",
    "check_narration_true",
    "check_ai_fresh",
    "check_reinvent_fits", "check_reinvent_clock",
    "check_reinvent_scroll",
    "check_tap_targets", "check_reinvent_counts",
    "check_reinvent_countdown", "check_reinvent_live",
    "check_connect_card", "check_one_panel", "check_solar_theme",
}

# check_colophon_built was in BROWSER and drives no browser at all -- it
# runs the builder and diffs the file, in seven seconds. Being listed here
# meant --fast skipped it AND the push hook skipped it, so nothing ever
# asked whether the served colophon matched the repository.
#
# It went stale exactly as you would expect: sync_blog.py regenerates the
# page on every publish, the documented `git add` line did not include
# how-this-was-made/, so four windows rebuilt it and left it unstaged for
# weeks. The live page said 279 posts while origin/main carried 281. Moved
# out, so it now runs on every push from every window.

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
#
# check_nav was removed from this set on 2026-09-27. It was in HOOK_BROWSER and
# in ADVISORY at the same time, which is the worst combination available: the
# hook ran it on every push from every worktree, run_one() retried it because it
# failed, and then its verdict was discarded because it is advisory. The comment
# above ADVISORY already records why it fails here -- a socket error in the
# transport against the local test server, an environment fault rather than a
# defect in the site -- so the cost was two PER_CHECK_TIMEOUT windows per push,
# spent to learn nothing.
#
# What it cost, measured: AWS Architecture #65 spent 44 minutes across repeated
# attempts before this change, and GCP Architecture #45 took 33 minutes the same
# morning. Both were commits that were clean, rebased, and a fast-forward away
# from landing. The gate was longer than the interval between commits on main,
# so pushes lost a race they then re-ran from the start.
#
# It still runs in a full `python scripts/preflight.py`, which is where an
# advisory check belongs: reported, not blocking a push and not costing one.
HOOK_BROWSER = {
    "check_shell_consistency",   # the five bars agreeing
    "check_shift",               # nothing moving sideways after paint
    "check_bar_settle",          # ...at a phone width too, which check_shift
                                 # never looked at, and without a list of
                                 # element names a real shift can fall out of
    "check_brand",               # mark and wordmark identical
    "check_music",               # the button actually plays
    "check_audio_glyph",         # ...once, and keeps playing across tabs
    "check_post_controls",       # ask, arrow and star not swallowed
    "check_page_settle",         # the page not rebuilding itself
    "check_sticky_clear",        # nothing hiding under the header
    "check_reinvent_fits",       # the page fits the phone, and every tab
                                 # can still be tapped -- it shipped 72px
                                 # too wide with a whole view unreachable
    "check_reinvent_clock",      # and still works on the days it is for:
                                 # the live-clock view had never been run
    "check_reinvent_scroll",     # and does not fight you when you scroll,
                                 # which took three goes to get right
    "check_tap_targets",         # and the mark and the way home are big
                                 # enough to hit with a thumb, which every
                                 # control beside them already was
    "check_reinvent_counts",     # and every count on the re:Invent page
                                 # follows the data it is showing rather
                                 # than the day it was built
    "check_reinvent_countdown",  # and the days-to-go is right on both
                                 # sides of the event, on the planner and
                                 # on the contact card, which agree
    "check_reinvent_live",       # and a live pull survives coming back,
                                 # while one the morning refresh has
                                 # superseded does not
    "check_connect_card",        # and the card's figure clears the pills
                                 # and the buttons at three widths, with
                                 # paper that scrolls with the page
    "check_one_panel",           # and opening one panel in the bar closes
                                 # the others, which a capture-phase
                                 # stopPropagation had quietly prevented
    "check_solar_theme",         # and the card is light where the sun is
                                 # up, in nine timezones, with the clock
                                 # pinned so the answer is not in doubt
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

# name -> extra argv. Empty for every check unless main() scopes them.
SCOPE = {}


def scopable_checks():
    """Checks that accept post names, read from prepublish rather than listed.

    prepublish.CHECKS already carries this as its fifth flag, and two
    copies of the same list is two copies that drift. Importing it keeps
    one source of truth; if the import fails for any reason we scope
    nothing, which is the old behaviour and safe.
    """
    try:
        import prepublish
        return {row[0][:-3] for row in prepublish.CHECKS if row[4]}
    except Exception:                                           # noqa: BLE001
        return set()


def pushed_posts():
    """Post slugs this push actually contains, or None if we cannot tell.

    None means "do not scope" -- a full unscoped run, exactly as before.
    That is the fail-safe direction: the cost of being wrong here is a
    slow push, and the cost of the other direction is an unchecked post.

    git hands a pre-push hook one line per ref on stdin:

        <local ref> <local sha> <remote ref> <remote sha>

    The remote sha is what the other end already has, so the range
    remote..local is precisely what is new. A remote sha of all zeroes
    means the branch is new over there and nothing can be assumed.
    """
    ranges = []
    try:
        if not sys.stdin.isatty():
            for line in sys.stdin.read().splitlines():
                bits = line.split()
                if len(bits) != 4:
                    continue
                local_sha, remote_sha = bits[1], bits[3]
                if set(local_sha) == {"0"}:
                    continue                    # a delete; nothing to check
                if set(remote_sha) == {"0"}:
                    return None                 # new branch: check everything
                ranges.append("%s..%s" % (remote_sha, local_sha))
    except Exception:                                           # noqa: BLE001
        return None

    if not ranges:
        # Run by hand rather than by git. Fall back to what the remote has.
        ranges = ["origin/main..HEAD"]

    slugs, saw_any = set(), False
    for rng in ranges:
        try:
            out = subprocess.run(["git", "diff", "--name-only", rng],
                                 cwd=ROOT, capture_output=True, text=True,
                                 timeout=30)
        except Exception:                                       # noqa: BLE001
            return None
        if out.returncode != 0:
            return None
        saw_any = True
        for path in out.stdout.splitlines():
            path = path.strip()
            if path.startswith("posts/") and path.endswith(".html"):
                slugs.add(os.path.basename(path)[:-len(".html")])
    return sorted(slugs) if saw_any else None


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
    args = SCOPE.get(name, [])
    try:
        p = subprocess.run([sys.executable, os.path.join(SCRIPTS, name + ".py")]
                           + args,
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

    ADVISORY checks are not retried, added 2026-09-27. The retry exists to stop
    a flaky failure blocking a push -- but an advisory check cannot block one,
    so the second run buys nothing and costs up to another PER_CHECK_TIMEOUT.
    Several of these are advisory precisely because they fail here for
    environment reasons, which is exactly the case that always pays the retry.
    They still run, and still print, on the first result.
    """
    code, out, secs = run_once(name)
    if code == 0:
        return name, code, out, secs, False
    if name in ADVISORY:
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


# ---------------------------------------------------------------- the gate lock
#
# Two preflight runs at once do not take twice as long each. They take far
# longer than that and then start failing, because every browser check spawns a
# headless browser and a local HTTP server, and the machine has eight cores.
#
# Measured 2026-09-30, one AWS push with the site window running its own gate:
#
#     total CPU 97%   chrome/chromium processes 27
#     check_connect_card        40.7s  ->  386.3s
#     check_audio_glyph         79.5s  ->  296.1s
#     check_shell_consistency  120.5s  ->  227.1s
#     52 checks                  469s  ->  1645s,  then check_tap_targets FAILED
#
# Same checks, same code, 3.5x slower, and then a failure that was nothing to do
# with the site. The comment above WORKERS already describes this shape for
# browsers contending inside one run; this is the same thing between two runs,
# and lowering WORKERS cannot fix it because the other run has its own.
#
# The cost of that landed on a person: three windows held back to avoid it, and
# a post still took 77 minutes from commit to live.
#
# So the gate takes a turn rather than competing. The lock lives in the SHARED
# git directory, which is what makes it work across all four worktrees -- the
# same reason the hook itself applies to all of them.
#
# Serialising is strictly cheaper than contending. Four windows at ~8 minutes
# each is ~32 minutes of gate in total; two contending runs already cost more
# than that and produced a false failure as well.
#
# On timeout it PROCEEDS rather than failing. A lock that can block a push
# forever is worse than the contention it prevents -- same reasoning as --fast
# and --no-verify existing at all. A stale lock from a killed process is
# detected and stolen rather than waited on, because pushes get interrupted.
LOCK_WAIT_SECONDS = 2700
LOCK_POLL_SECONDS = 5


def _lock_path():
    try:
        common = subprocess.run(["git", "rev-parse", "--git-common-dir"],
                                cwd=ROOT, capture_output=True, text=True,
                                timeout=30).stdout.strip()
    except Exception:                                           # noqa: BLE001
        return None
    if not common:
        return None
    if not os.path.isabs(common):
        common = os.path.join(ROOT, common)
    return os.path.join(common, "preflight.lock")


def _holder_alive(pid):
    """True if that pid is still running. Unknown counts as alive."""
    try:
        out = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid, "/NH"],
                             capture_output=True, text=True, timeout=30).stdout
        return str(pid) in out
    except Exception:                                           # noqa: BLE001
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
        except Exception:                                       # noqa: BLE001
            return True


def acquire_gate_lock():
    """Take the shared gate lock, or wait for whoever has it. Never blocks forever."""
    path = _lock_path()
    if path is None:
        print("  could not locate the shared git dir; running without the gate lock")
        return None

    waited, announced = 0, False
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, ("%d\n%s\n%s\n" % (os.getpid(), ROOT,
                                            time.strftime("%Y-%m-%d %H:%M:%S"))
                          ).encode("utf-8"))
            os.close(fd)
            if announced:
                print("  gate lock acquired after %ds\n" % waited)
            return path
        except FileExistsError:
            # utf-8-sig, because a lock file written by anything other than this
            # script may carry a BOM and int() does not forgive one. Found while
            # testing: a BOM made the pid unparseable, which took the branch
            # below and waited 45 minutes on a lock whose holder was long dead.
            pid, where = None, "?"
            try:
                parts = io.open(path, encoding="utf-8-sig").read().splitlines()
                pid = int(parts[0].strip())
                where = parts[1].strip() if len(parts) > 1 else "?"
            except Exception:                                   # noqa: BLE001
                pass

            # An unparseable lock is treated as stale, not as a live holder.
            # The alternative is what the comment above describes: a corrupted
            # or truncated lock file blocking every worktree for the full wait.
            # The race this risks -- stealing from a holder caught mid-write --
            # is a single os.write wide, against a 45-minute stall.
            if pid is None:
                print("  gate lock is unreadable; treating it as stale and taking it")
                try:
                    os.unlink(path)
                except OSError:
                    pass
                continue

            if not _holder_alive(pid):
                print("  stale gate lock from pid %d; taking it" % pid)
                try:
                    os.unlink(path)
                except OSError:
                    pass
                continue

            if not announced:
                print("  another gate is running (pid %s, %s)."
                      % (pid, os.path.basename(where.rstrip("\\/")) or where))
                print("  waiting for it rather than competing -- two gates at once "
                      "is slower than taking turns.")
                announced = True

            if waited >= LOCK_WAIT_SECONDS:
                print("  waited %ds and it is still held; proceeding anyway.\n"
                      "  a lock that blocks a push forever is worse than the "
                      "contention it prevents." % waited)
                return None

            time.sleep(LOCK_POLL_SECONDS)
            waited += LOCK_POLL_SECONDS


def release_gate_lock(path):
    if not path:
        return
    try:
        held = io.open(path, encoding="utf-8").read().splitlines()
        if held and int(held[0]) != os.getpid():
            return          # not ours; someone stole it as stale. Leave it.
    except Exception:                                           # noqa: BLE001
        pass
    try:
        os.unlink(path)
    except OSError:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true",
                    help="skip the checks that drive a browser")
    ap.add_argument("--install", action="store_true",
                    help="install the git pre-push hook")
    ap.add_argument("--hook", action="store_true",
                    help="running as the hook; quieter, and fails the push")
    ap.add_argument("--no-scope", action="store_true",
                    help="check every post, not only the ones this push carries")
    args = ap.parse_args()

    if args.install:
        return install()

    names = discover(args.fast, args.hook)

    # Scope the per-post checks to the posts this push actually carries.
    #
    # publish.py has done this for its own run since the day someone
    # forgot to name a post and sat through the network checks for every
    # post on the site. The hook never learned: it globs every check off
    # disk and runs each with no arguments, so a push re-read all 250
    # posts whatever it contained -- including a push that touched no
    # post at all.
    #
    # None means we could not work it out, and then nothing is scoped:
    # the old, slower, always-correct behaviour. The fallback only ever
    # goes that way, because the cost of guessing wrong here is a slow
    # push and the cost of the other direction is an unchecked post.
    posts = None if args.no_scope else pushed_posts()
    if posts is None:
        print("  could not tell what this push carries; checking everything")
    else:
        takes = scopable_checks()
        scoped = [n for n in names if n in takes]
        for n in scoped:
            SCOPE[n] = list(posts)
        if posts:
            print("  this push carries %d post(s): %s"
                  % (len(posts), ", ".join(posts)))
            print("  %d per-post check(s) scoped to them" % len(scoped))
        else:
            print("  this push carries no posts; %d per-post check(s) have "
                  "nothing to read" % len(scoped))
    # Take a turn rather than competing. Released on any exit path, including
    # the hook being killed mid-push, which happens.
    lock = acquire_gate_lock()
    atexit.register(release_gate_lock, lock)

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
