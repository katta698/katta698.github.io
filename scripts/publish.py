#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One command that runs the publishing sequence, in the order that is correct.

    python scripts/publish.py                 # the whole thing
    python scripts/publish.py --offline       # skip the checks that fetch vendor pages
    python scripts/publish.py arch-025        # scope the per-post checks to one post
    python scripts/publish.py --no-rebase     # already rebased by hand

It stops before committing. It never commits and never pushes, because Jayanth
pushes himself -- see CLAUDE.md, which this script exists to stop people
interpreting differently.

Why this exists
---------------
Four windows publish to one branch, each following the same six paragraphs of
prose, and they drift. Observed in a single week:

  * one window pushed without being asked, while the other three waited;
  * one published in a shape that never triggered the RAG re-index, so its posts
    silently had no "At a glance" summary for days;
  * one ran prepublish BEFORE its final rebase, which checks a tree that is not
    the tree being pushed -- corrected in 43ef899, a commit whose entire subject
    is "Run prepublish after the final rebase, not before".

None of that is carelessness. It is what happens when a procedure lives in prose:
every session re-derives it, and a re-derivation is a chance to differ.

prepublish.py already proved the fix. It turned "run these four checks" into one
command and the checks stopped drifting. The sequence AROUND the checks never got
the same treatment, so this is that.

The order, and why each step is where it is
-------------------------------------------
1. FETCH, and report how far behind. Cheap, and it decides everything after.

2. REBASE onto origin/main, stashing tracked changes first if the tree is dirty
   -- which it always is, because the post being published is uncommitted. Must
   come before sync: sync_blog.py rebuilds the index from posts/, and posts/ in
   this worktree does not contain another window's post until the rebase brings
   it in. Syncing first regenerates the whole index without it, which removes a
   published post from the site with no error anywhere.

3. SYNC. Regenerates every served page, the index, cards.json, rss.xml,
   stats.json and sw.js from posts/.

4. PREPUBLISH, after the rebase and after the sync, never before either. Rebasing
   pulls in other windows' posts and Previous/Next is a function of every post on
   the site, so a post arriving between the build and the push invalidates the
   nav on all the hand-built pages. Checking the pre-rebase tree checks something
   that will not be pushed.

5. RE-CHECK the remote. If origin moved while steps 2-4 were running -- and with
   four daily writers it does; ten commits landed in twenty-eight minutes on
   2026-08-18 -- the tree just verified is already stale, and the honest answer
   is to run again rather than to push it.

6. REPORT what changed and print the exact git add line. Then stop.
"""
import argparse
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def run(*cmd, **kw):
    """Run a command, returning (code, stdout). Never raises on a non-zero exit.

    encoding is forced: the default platform codec on Windows cannot represent
    the em dashes in these commit subjects and post titles, and the crash it
    produces looks like a git failure rather than a decoding one.
    """
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kw)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def step(n, title):
    print("\n" + "=" * 74)
    print("  %d. %s" % (n, title))
    print("=" * 74)


def git_lines(*cmd):
    _, out = run("git", *cmd)
    return [l for l in out.splitlines() if l.strip()]


def behind_ahead():
    _, out = run("git", "rev-list", "--left-right", "--count",
                 "HEAD...origin/main")
    try:
        ahead, behind = out.split()[:2]
        return int(behind), int(ahead)
    except ValueError:
        return 0, 0


def dirty_tracked():
    """Tracked files with changes. Untracked are ignored on purpose.

    A stash of untracked files would sweep up another window's half-written post
    and this window's scratch files alike, and popping it back is exactly the
    kind of surprise that makes people stop trusting a script.
    """
    return [l for l in git_lines("status", "--porcelain") if not l.startswith("??")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("posts", nargs="*",
                    help="substring of a post filename, passed to prepublish")
    ap.add_argument("--series", help="restrict the per-post checks to one series")
    ap.add_argument("--offline", action="store_true",
                    help="skip the checks that fetch vendor pages")
    ap.add_argument("--no-rebase", action="store_true",
                    help="skip the fetch and rebase; you have already done it")
    args = ap.parse_args()

    if not args.no_rebase:
        step(1, "Fetch")
        code, out = run("git", "fetch", "origin")
        if code:
            print(out.strip())
            print("\nCould not reach origin. Nothing has been changed.")
            return 2
        behind, ahead = behind_ahead()
        print("  behind origin/main by %d, ahead by %d" % (behind, ahead))

        step(2, "Rebase onto origin/main")
        if behind == 0:
            print("  already up to date, nothing to rebase")
        else:
            tracked = dirty_tracked()
            stashed = False
            if tracked:
                print("  stashing %d tracked change(s) first:" % len(tracked))
                for t in tracked[:8]:
                    print("     %s" % t)
                if len(tracked) > 8:
                    print("     ... and %d more" % (len(tracked) - 8))
                code, out = run("git", "stash", "push", "--",
                                *[l[3:] for l in tracked])
                stashed = code == 0 and "No local changes" not in out
            code, out = run("git", "rebase", "origin/main")
            if code:
                print(out.strip())
                print("\nRebase failed. Your work is %s." %
                      ("in `git stash`" if stashed else "still in the tree"))
                print("Resolve it, then run this again with --no-rebase.")
                return 1
            print("  rebased; picked up %d commit(s)" % behind)
            if stashed:
                code, out = run("git", "stash", "pop")
                if code:
                    print(out.strip())
                    print("\nRebase succeeded but restoring your changes hit a "
                          "conflict. They are safe in `git stash`.")
                    return 1
                print("  restored your changes")

    step(3, "Sync")
    code = subprocess.call([sys.executable, os.path.join(HERE, "sync_blog.py")],
                           cwd=ROOT)
    if code:
        print("\nsync_blog.py failed. Nothing has been committed.")
        return 1

    step(4, "Pre-publish checks")
    argv = [sys.executable, os.path.join(HERE, "prepublish.py")]
    if args.offline:
        argv.append("--offline")
    if args.series:
        argv += ["--series", args.series]
    argv += args.posts
    checks = subprocess.call(argv, cwd=ROOT)

    step(5, "Did origin move while we worked?")
    run("git", "fetch", "origin")
    behind, ahead = behind_ahead()
    if behind:
        print("  origin/main gained %d commit(s) DURING this run." % behind)
        print("  The tree just checked is already stale: Previous/Next and the")
        print("  index are functions of every post on the site, so run this")
        print("  again before committing.")
    else:
        print("  no, still level with origin/main")

    step(6, "What changed")
    changed = git_lines("status", "--porcelain")
    if not changed:
        print("  nothing. Sync produced no changes and there is nothing to commit.")
    else:
        posts = [l for l in changed if l[3:].startswith("posts/")]
        blog = [l for l in changed if l[3:].startswith("blog/")]
        other = [l for l in changed if l not in posts and l not in blog]
        print("  %d post file(s), %d blog file(s), %d other" %
              (len(posts), len(blog), len(other)))
        for l in posts + other:
            print("     %s" % l)
        if len(blog) > 6:
            print("     ... plus %d regenerated file(s) under blog/" % len(blog))

    print("\n" + "=" * 74)
    if checks or behind:
        print("  NOT READY. %s" % ("Checks failed." if checks
                                   else "origin moved; run again."))
        print("=" * 74)
        return 1
    print("  Ready. Nothing has been committed or pushed -- that is deliberate.")
    print("=" * 74)
    print("\n  git add blog/ posts/ scripts/ index.html resume.html now.html sw.js")
    print("  git commit")
    print("\n  Then ask Jayanth to push.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
