#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""What is due today, across all four windows, with the feed work already done.

    python scripts/morning.py              # the whole brief
    python scripts/morning.py --offline    # skip everything that touches a network
    python scripts/morning.py --no-rebase  # report worktree state, change nothing

Writes the same text to MORNING.md in the repo root so a scheduled task can run
it at logon and leave the brief waiting.

Why this exists
---------------
Seven posts land on a Saturday: three architecture posts, one AWS Daily
Intelligence, and three Weekly Intelligence roundups. Every one of them starts
with the same mechanical half-hour -- rebase the worktree, work out which number
comes next, find the topic in the roadmap, fetch the feeds, audit them for
staleness and truncation. None of that is writing. All of it is forgettable, and
the failure mode when it is forgotten is silent: a roundup built from a
truncated feed looks exactly like a complete one.

So this does the mechanical half and stops. It does not write posts, and it
deliberately does not touch the verification badge -- CLAUDE.md is explicit that
a badge asserts a human checked the figures, and a script that stamped one would
be making that claim on nobody's behalf.

What it will not do
-------------------
* Commit or push anything. Jayanth pushes himself.
* Rebase a worktree with uncommitted changes. It reports and moves on; sweeping
  up a half-written post into a stash is not a thing a background task should do.
* Resolve an ambiguous roadmap entry. Where the next number matches more than
  one line, it prints all of them rather than guessing.
"""
import argparse
import datetime as dt
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENG = os.path.dirname(ROOT)

# One window, one worktree -- see CLAUDE.md. The site window owns this script
# because it owns everything shared; the three cloud windows are where the posts
# are actually written.
WORKTREES = [
    ("site",  os.path.join(ENG, "katta698.github.io"), "main"),
    ("aws",   os.path.join(ENG, "katta698-aws"),       "aws"),
    ("azure", os.path.join(ENG, "katta698-azure"),     "azure"),
    ("gcp",   os.path.join(ENG, "katta698-gcp"),       "gcp"),
]

# prefix in posts/, roadmap file, human name, which window writes it
ARCH_SERIES = [
    ("arch", "ROADMAP.md",       "AWS Architecture",   "aws"),
    ("az",   "AZURE-ROADMAP.md", "Azure Architecture", "azure"),
    ("gcp",  "GCP-ROADMAP.md",   "GCP Architecture",   "gcp"),
]

# Saturday roundups. Each covers Monday-Friday of the week just finished and is
# composed from a FRESH Saturday fetch -- CLAUDE.md is explicit that Friday's
# release notes are still landing on Friday, so an inventory built the day
# before can be missing items from the window the post claims to cover.
WEEKLIES = [
    ("weekly",    "fetch_week.py",       "AWS Weekly Intelligence",   "aws",   ["--audit"]),
    ("azw",       "fetch_azure_week.py", "Azure Weekly Intelligence", "azure", ["--audit"]),
    ("gcpweekly", "fetch_week_gcp.py",   "GCP Weekly Intelligence",   "gcp",   ["--audit", "--products"]),
]

OUT = []


def say(line=""):
    OUT.append(line)
    print(line)


def head(title):
    say("")
    say("=" * 74)
    say("  " + title)
    say("=" * 74)


def run(*cmd, cwd=None, timeout=300):
    """Never raises. A morning brief that dies on one bad step is worse than one
    that reports the bad step and carries on to the other three windows."""
    try:
        p = subprocess.run(cmd, cwd=cwd or ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "timed out after %ds" % timeout
    except OSError as e:
        return 1, str(e)


# --- what is due -------------------------------------------------------------

def whats_due(today):
    """Monday=0 .. Sunday=6.

    Architecture posts run every day on all three clouds. AWS Daily Intelligence
    runs Tuesday to Saturday -- it reports on the previous day's news, and AWS
    does not publish at the weekend, so Sunday and Monday have nothing to report.
    The three weekly roundups are Saturday only.
    """
    due = [(name, window) for _, _, name, window in ARCH_SERIES]
    if today.weekday() in (1, 2, 3, 4, 5):        # Tue-Sat
        due.append(("AWS Daily Intelligence", "aws"))
    if today.weekday() == 5:                       # Saturday
        due += [(name, window) for _, _, name, window, _ in WEEKLIES]
    return due


# --- worktrees ---------------------------------------------------------------

def worktree_report(rebase):
    head("Worktrees")
    for name, path, branch in WORKTREES:
        if not os.path.isdir(path):
            say("  %-6s MISSING  %s" % (name, path))
            continue

        run("git", "fetch", "origin", cwd=path, timeout=120)
        _, out = run("git", "rev-list", "--left-right", "--count",
                     "HEAD...origin/main", cwd=path)
        try:
            ahead, behind = (int(x) for x in out.split()[:2])
        except ValueError:
            ahead = behind = -1

        _, st = run("git", "status", "--porcelain", cwd=path)
        dirty = [l for l in st.splitlines() if l.strip() and not l.startswith("??")]

        note = ""
        if behind and not dirty and rebase:
            code, msg = run("git", "rebase", "origin/main", cwd=path)
            if code == 0:
                note = "-> rebased, picked up %d" % behind
                behind = 0
            else:
                run("git", "rebase", "--abort", cwd=path)
                note = "-> rebase FAILED, aborted cleanly"
        elif behind and dirty:
            # Deliberate: a background task must not stash somebody's draft.
            note = "-> behind, but %d uncommitted change(s); rebase by hand" % len(dirty)
        elif dirty:
            note = "-> %d uncommitted change(s)" % len(dirty)

        say("  %-6s %-7s behind %-3s ahead %-3s %s"
            % (name, branch, behind, ahead, note))


# --- next numbers ------------------------------------------------------------

def next_numbers(today):
    head("Next up")
    for prefix, roadmap, label, window in ARCH_SERIES:
        posts = os.path.join(ROOT, "posts")
        pat = re.compile(r"^%s-(\d{3})" % re.escape(prefix))
        nums = sorted(int(m.group(1)) for f in os.listdir(posts)
                      for m in [pat.match(f)] if m)
        nxt = (nums[-1] + 1) if nums else 1

        say("")
        say("  %s  ->  #%d   (%s window)" % (label, nxt, window))

        rp = os.path.join(ROOT, roadmap)
        if not os.path.isfile(rp):
            say("     roadmap %s not found" % roadmap)
            continue

        # Topics are listed as "N. Title". The AWS roadmap restarts numbering
        # per phase, so a number can match more than one line -- print every
        # match rather than picking one, because picking wrong costs a post.
        lines = io.open(rp, encoding="utf-8").read().split("\n")
        hits = [l.strip() for l in lines
                if re.match(r"^\s*%d\.\s" % nxt, l)]
        if not hits:
            say("     no '%d.' entry in %s -- check the roadmap" % (nxt, roadmap))
        elif len(hits) == 1:
            say("     %s" % _trim(hits[0]))
        else:
            say("     %d candidates in %s -- pick one:" % (len(hits), roadmap))
            for h in hits:
                say("       %s" % _trim(h))


def _trim(s, n=140):
    s = re.sub(r"\s+", " ", s)
    return s if len(s) <= n else s[:n - 1] + "…"


# --- feeds -------------------------------------------------------------------

def feeds(today, offline):
    if today.weekday() != 5:
        return
    head("Saturday feeds")
    if offline:
        say("  --offline: skipped. Run again without it before writing a roundup.")
        return

    # Monday to Friday of the week that just finished.
    monday = today - dt.timedelta(days=5)
    friday = today - dt.timedelta(days=1)
    say("  news window: %s to %s" % (monday, friday))

    for prefix, script, label, window, extra in WEEKLIES:
        posts = os.path.join(ROOT, "posts")
        nums = sorted(int(m.group(1)) for f in os.listdir(posts)
                      for m in [re.match(r"^%s-(\d{3})" % prefix, f)] if m)
        nxt = (nums[-1] + 1) if nums else 1

        say("")
        say("  %s #%d  (%s window)" % (label, nxt, window))
        code, out = run(sys.executable, os.path.join(HERE, script),
                        str(monday), str(friday), *extra, timeout=420)
        if code:
            say("     FETCH FAILED (exit %d) -- do not publish a roundup from this" % code)

        # Surface only the lines that change a decision. The full audit is long
        # and belongs on screen when you run the fetcher yourself, not here.
        #
        # The per-product staleness list is deliberately NOT surfaced. CLAUDE.md
        # records that GCP's per-product feeds are not the source list and that
        # several are years behind by design -- compute-engine has been frozen
        # since 2020 while the combined feed carries its notes throughout. Ten
        # lines saying so every Saturday trains you to skim the section that also
        # carries the truncation warning, which is the one that matters.
        for l in out.splitlines():
            s = l.strip()
            if re.search(r"<-- STALE|probed feeds are more than", s):
                continue
            if re.search(r"TRUNCATION|WARNING|PARSE QUALITY|total|items", s, re.I):
                say("     %s" % _trim(s, 110))


def aws_daily(today, offline):
    """AWS Daily Intelligence reports on the previous day's news."""
    if today.weekday() not in (1, 2, 3, 4, 5):
        return
    head("AWS Daily Intelligence")
    yesterday = today - dt.timedelta(days=1)
    say("  news date: %s" % yesterday)
    say("  read DAILY-BACKLOG.md first -- a held item can beat today's news,")
    say("  and anything near a week old is about to age out of the feed.")
    if offline:
        say("  --offline: feed not fetched.")
        return
    code, out = run(sys.executable, os.path.join(HERE, "fetch_week.py"),
                    str(yesterday), str(yesterday), timeout=300)
    if code:
        say("  FETCH FAILED (exit %d)" % code)
        return
    lines = [l for l in out.splitlines() if l.strip()]
    say("  %d line(s) from the feed; full output: python scripts/fetch_week.py %s %s"
        % (len(lines), yesterday, yesterday))
    for l in lines:
        if re.search(r"TRUNCATION|WARNING", l, re.I):
            say("  %s" % _trim(l.strip(), 110))


# --- main --------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true",
                    help="skip everything that touches a network")
    ap.add_argument("--no-rebase", action="store_true",
                    help="report worktree state without rebasing")
    ap.add_argument("--date", help="pretend it is this date (YYYY-MM-DD)")
    args = ap.parse_args()

    today = (dt.date.fromisoformat(args.date) if args.date else dt.date.today())

    say("")
    say("  %s" % today.strftime("%A %d %B %Y"))
    due = whats_due(today)
    say("  %d post(s) due:" % len(due))
    for name, window in due:
        say("     %-28s %s window" % (name, window))

    worktree_report(rebase=not args.no_rebase and not args.offline)
    next_numbers(today)
    aws_daily(today, args.offline)
    feeds(today, args.offline)

    head("Then")
    say("  Write each post in its own window. When one is ready:")
    say("     python scripts/publish.py")
    say("  It rebases, syncs, checks, re-checks the remote, and stops before")
    say("  committing. Nothing here has committed or pushed anything.")
    say("")

    # One copy per worktree, not one in the site folder. A window can only be in
    # one directory at a time -- CLAUDE.md, one window one folder -- so a brief
    # that exists only here is a brief the three cloud windows cannot read
    # without being told a path they have no reason to know. It is gitignored,
    # and .gitignore is shared across the worktrees, so all four are covered by
    # the one entry.
    written = 0
    for name, path, _ in WORKTREES:
        if not os.path.isdir(path):
            continue
        try:
            io.open(os.path.join(path, "MORNING.md"), "w",
                    encoding="utf-8").write("\n".join(OUT) + "\n")
            written += 1
        except OSError as e:
            print("  could not write brief to %s: %s" % (name, e))
    print("  (brief written to MORNING.md in %d worktree(s))" % written)
    return 0


if __name__ == "__main__":
    sys.exit(main())
