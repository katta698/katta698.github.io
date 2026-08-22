#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Who is working on what, across all four worktrees.

    python scripts/who.py

Why this exists
---------------
On 2026-08-22 two windows fixed the same three verification badges at the same
time. Both did the work; one of them found out only when `publish.py` hit a
merge conflict on three files it had just edited. Nothing was lost -- git caught
it, which is what git is for -- but an hour went into the same task twice.

MORNING.md reports what is DUE. It cannot report what somebody is DOING, because
in-flight work is uncommitted and lives in another worktree's working directory.
That is the gap this closes.

It reads the other worktrees' working state directly. There is no daemon, no
lock file and no claim protocol: a window that is writing a post has modified or
untracked files in its own posts/ directory, and that is a fact on disk any
window can read without cooperation from the others.

What the columns mean
---------------------
  ahead    commits made here that origin/main does not have yet -- written,
           not pushed. Another window will collide with these on its next
           rebase, and will not see them until then.
  behind   commits on origin/main this worktree has not picked up.
  editing  uncommitted changes. This is the column the collision would have
           been visible in: the AWS window had posts/week-13, -14 and -15
           modified for some time before it committed.

It never writes, commits, fetches destructively, or touches another worktree.
Fetch is read-only and is what makes ahead/behind meaningful at all.
"""
import io
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WORKTREES = [
    ("site",  "katta698.github.io"),
    ("aws",   "katta698-aws"),
    ("azure", "katta698-azure"),
    ("gcp",   "katta698-gcp"),
]


def git(path, *args, timeout=60):
    try:
        p = subprocess.run(("git",) + args, cwd=path, capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    base = os.path.dirname(root)

    print("")
    print("  %-6s %-6s %-6s  %s" % ("window", "ahead", "behind", "editing"))
    print("  " + "-" * 68)

    busy = []
    for name, folder in WORKTREES:
        path = os.path.join(base, folder)
        if not os.path.isdir(path):
            print("  %-6s missing: %s" % (name, path))
            continue

        git(path, "fetch", "origin", "--quiet", timeout=90)
        _, out = git(path, "rev-list", "--left-right", "--count",
                     "HEAD...origin/main")
        try:
            ahead, behind = (int(x) for x in out.split()[:2])
        except ValueError:
            ahead = behind = -1

        _, st = git(path, "status", "--porcelain")
        # MORNING.md is written into every worktree by the scheduled task and is
        # gitignored there once the ignore rule has been rebased in. Until then
        # it shows as untracked in three of the four, which is noise.
        changed = [l for l in st.splitlines()
                   if l.strip() and "MORNING.md" not in l]

        note = "-" if not changed else "%d file(s)" % len(changed)
        print("  %-6s %-6s %-6s  %s" % (name, ahead, behind, note))

        for l in changed[:6]:
            flag, p = l[:2].strip() or "??", l[3:]
            age = ""
            full = os.path.join(path, p.strip('"'))
            if os.path.isfile(full):
                mins = (time.time() - os.path.getmtime(full)) / 60
                age = "%dm ago" % mins if mins < 90 else "%.0fh ago" % (mins / 60)
            print("           %-3s %-46s %s" % (flag, p[:46], age))
        if len(changed) > 6:
            print("           ... and %d more" % (len(changed) - 6))

        if ahead > 0 or changed:
            busy.append(name)

        # Unpushed commits are the other half of invisible work: written,
        # committed, and still not on origin, so no other window can see them.
        if ahead > 0:
            _, log = git(path, "log", "--oneline", "origin/main..HEAD")
            for l in log.splitlines()[:4]:
                print("           unpushed  %s" % l[:60])

    print("")
    if busy:
        print("  In flight: %s" % ", ".join(busy))
        print("  Before starting on a post or a shared script, check it is not"
              " already above.")
    else:
        print("  Nothing in flight. Every worktree is clean and level with origin.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
