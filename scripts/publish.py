#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One command that runs the publishing sequence, in the order that is correct.

    python scripts/publish.py                 # the whole thing
    python scripts/publish.py --offline       # skip the checks that fetch vendor pages
    python scripts/publish.py arch-025        # scope the per-post checks to one post
    python scripts/publish.py --no-rebase     # already rebased by hand
    python scripts/publish.py --attempts 6    # allow more re-converge rounds

The per-post checks are scoped automatically to whatever is uncommitted under
posts/, so naming a post is only needed to check something already committed.

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

   Untracked generated files that origin/main has since started tracking are
   removed first, because git will not check out over an untracked file and the
   rebase would abort having done nothing. See clear_regenerated_collisions().

3. SYNC. Regenerates every served page, the index, cards.json, rss.xml,
   stats.json and sw.js from posts/.

4. PREPUBLISH, after the rebase and after the sync, never before either. Rebasing
   pulls in other windows' posts and Previous/Next is a function of every post on
   the site, so a post arriving between the build and the push invalidates the
   nav on all the hand-built pages. Checking the pre-rebase tree checks something
   that will not be pushed.

5. RE-CONVERGE. If origin moved while steps 2-4 were running -- and with four
   daily writers it does; ten commits landed in twenty-eight minutes on
   2026-08-18 -- the tree just verified is already stale.

   This used to print "run again" and exit 1. That could not converge: a full
   run takes five to six minutes at 138 posts, mostly re-fetching every cited
   page on the site, so by the time the human re-ran it origin had moved again.
   On 2026-08-22 five consecutive attempts were outrun and the roundup was
   published by running the checks by hand instead -- which is the drift this
   script exists to prevent, arriving through the script rather than around it.

   So it now converges by itself. On finding origin has moved it rebases,
   re-syncs, and re-runs ONLY the site-wide checks, because only those can have
   changed: whether this post's cited pages resolve does not depend on what
   another window published. That loop body is a sync plus three fast local
   checks rather than a full network pass, which is short enough to win the race,
   and it repeats up to --attempts times before giving up honestly.

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


def untracked_files():
    """Untracked paths as files, never as directories.

    Plain `--porcelain` collapses a wholly-untracked directory into one entry
    ending in a slash, so `blog/page/7/index.html` is reported as
    `blog/page/7/` and never matches a path in origin/main's tree. `-uall`
    is what makes the collision check below see the actual files.
    """
    return [l[3:].strip().strip('"')
            for l in git_lines("status", "--porcelain", "-uall")
            if l.startswith("??")]


def clear_regenerated_collisions():
    """Delete untracked generated files that origin/main has started tracking.

    git refuses to check out a commit that would overwrite an untracked file,
    so the rebase in step 2 aborts with "untracked working tree files would be
    overwritten" and does nothing at all. It only names the first colliding
    path, which makes it read like a merge problem rather than what it is.

    The trigger is the site crossing a pagination boundary. This window's sync
    produces blog/page/7/index.html as a new untracked file; another window
    publishes first and commits that same path; now the rebase that would pick
    up their post cannot run. Nothing is at stake in the file -- step 3 rebuilds
    every one of these from posts/ a moment later -- but the rebase never gets
    that far, and it happened on 2026-08-24 when Azure #11 landed mid-run.

    Untracked files are still not stashed, for the reason dirty_tracked()
    gives. This is narrower: a path that is untracked here AND already tracked
    on origin/main is a file another window has published, so the copy in this
    tree is regenerated output by definition. Removal is limited to blog/ on
    top of that. A collision anywhere else -- two windows writing the same
    posts/ file -- is a real conflict and stops the run for a human.

    Returns (ok, removed_paths).
    """
    _, out = run("git", "ls-tree", "-r", "--name-only", "origin/main")
    upstream = set(out.splitlines())
    colliding = [p for p in untracked_files() if p in upstream]
    if not colliding:
        return True, []

    outside = [p for p in colliding if not p.startswith("blog/")]
    if outside:
        print("  These files are untracked here and already tracked on")
        print("  origin/main, and they are not generated output:")
        for p in outside:
            print("     %s" % p)
        print("  Another window has published them. Resolve by hand.")
        return False, []

    for p in colliding:
        os.remove(os.path.join(ROOT, p))
        parent = os.path.dirname(os.path.join(ROOT, p))
        if os.path.isdir(parent) and not os.listdir(parent):
            os.rmdir(parent)
    return True, colliding


def report_cleared(removed):
    if not removed:
        return
    print("  removed %d regenerated file(s) origin now tracks; sync rebuilds "
          "them:" % len(removed))
    for p in removed[:5]:
        print("     %s" % p)
    if len(removed) > 5:
        print("     ... and %d more" % (len(removed) - 5))


def changed_post_names():
    """Post filenames this tree is about to publish, for scoping the checks.

    Derived from git rather than passed in. Naming the post by hand was optional,
    so forgetting it silently ran the expensive network checks across all 138
    posts -- which is most of why a full run could not finish before another
    window pushed.
    """
    out = []
    for line in git_lines("status", "--porcelain"):
        path = line[3:].strip().strip('"')
        if path.startswith("posts/") and path.endswith(".html"):
            out.append(os.path.basename(path)[:-len(".html")])
    return out


def prepublish_argv(args, scoped):
    argv = [sys.executable, os.path.join(HERE, "prepublish.py")]
    if args.offline:
        argv.append("--offline")
    if args.series:
        argv += ["--series", args.series]
    return argv + list(scoped)


def rebase_onto_origin():
    """Rebase, stashing tracked changes first. Returns (code, message)."""
    tracked = dirty_tracked()
    stashed = False
    if tracked:
        code, out = run("git", "stash", "push", "--", *[l[3:] for l in tracked])
        stashed = code == 0 and "No local changes" not in out
    ok, removed = clear_regenerated_collisions()
    if not ok:
        return 1, ("  Rebase not attempted. Your work is %s." %
                   ("in `git stash`" if stashed else "still in the tree"))
    report_cleared(removed)
    code, out = run("git", "rebase", "origin/main")
    if code:
        return 1, ("  Rebase failed. Your work is %s.\n  Resolve it, then run "
                   "again with --no-rebase." %
                   ("in `git stash`" if stashed else "still in the tree"))
    if stashed:
        code, out = run("git", "stash", "pop")
        if code:
            return 1, ("  Rebase succeeded but restoring your changes hit a "
                       "conflict.\n  They are safe in `git stash`.")
    return 0, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("posts", nargs="*",
                    help="substring of a post filename, passed to prepublish")
    ap.add_argument("--series", help="restrict the per-post checks to one series")
    ap.add_argument("--offline", action="store_true",
                    help="skip the checks that fetch vendor pages")
    ap.add_argument("--no-rebase", action="store_true",
                    help="skip the fetch and rebase; you have already done it")
    ap.add_argument("--attempts", type=int, default=4,
                    help="how many times to re-converge when origin moves "
                         "mid-run (default 4)")
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
            ok, removed = clear_regenerated_collisions()
            if not ok:
                print("\nRebase not attempted. Your work is %s." %
                      ("in `git stash`" if stashed else "still in the tree"))
                return 1
            report_cleared(removed)
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
    scoped = args.posts or changed_post_names()
    if scoped and not args.posts:
        print("  scoping the per-post checks to: %s" % ", ".join(scoped))
    checks = subprocess.call(prepublish_argv(args, scoped), cwd=ROOT)

    step(5, "Re-converge if origin moved")
    behind = 0
    for attempt in range(1, max(1, args.attempts) + 1):
        run("git", "fetch", "origin")
        behind, _ahead = behind_ahead()
        if not behind:
            print("  level with origin/main"
                  + (" after %d round(s)" % (attempt - 1) if attempt > 1 else ""))
            break
        if attempt == args.attempts:
            print("  origin/main gained %d commit(s) again on the final "
                  "attempt." % behind)
            print("  Giving up rather than pushing a stale tree. Run again when "
                  "the other windows are quiet.")
            break
        print("  origin/main gained %d commit(s) during this run "
              "(round %d of %d)." % (behind, attempt, args.attempts - 1))
        print("  Rebasing and re-checking the site-wide invariants; the per-post")
        print("  checks already passed and cannot be changed by another window.")
        code, out = rebase_onto_origin()
        if code:
            print(out)
            return 1
        code = subprocess.call([sys.executable, os.path.join(HERE, "sync_blog.py")],
                               cwd=ROOT)
        if code:
            print("\n  sync_blog.py failed during re-converge.")
            return 1
        again = subprocess.call([sys.executable, os.path.join(HERE, "prepublish.py"),
                                 "--sitewide-only"], cwd=ROOT)
        if again:
            checks = again
            print("  site-wide checks FAILED after re-converging.")
            break

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
                                   else "origin still moving; run again."))
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
