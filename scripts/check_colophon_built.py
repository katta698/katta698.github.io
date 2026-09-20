#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The served colophon is what its builder would produce today.

    python scripts/check_colophon_built.py

Why this exists
---------------
Three times now, a fix has landed in `scripts/` and never reached the page.
Each time it looked like a failed deploy and was not:

    the source   scripts/colophon_scene_css.py   has the fix
    the page     how-this-was-made/index.html    does not
    the site     serves the page

`/how-this-was-made/` is generated, and several windows regenerate parts of
this site on their own schedule. A window whose checkout predates a fix
rebuilds the page from the code it has and commits the result over the top.
Nothing errors. The source and the page it generates simply disagree on the
remote, and the page is the thing readers get.

It costs an hour every time, because the symptom is indistinguishable from a
slow deploy: on the first occurrence I polled the live site for twenty-five
minutes before checking whether the committed HTML contained the fix at all.

So this asks the only question that settles it: run the builder, and see
whether the file changes. If it does, what is committed is not what the
builder makes, and the push would ship a stale page.

It deliberately leaves the rebuilt file in place. The fix for a failure here
is to commit that file, and regenerating it is exactly what the next step
needs anyway.
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "how-this-was-made", "index.html")
BUILDER = os.path.join(ROOT, "scripts", "build_colophon.py")


def main():
    os.chdir(ROOT)
    if not os.path.exists(PAGE):
        print("  the colophon has never been built")
        return 1

    before = io.open(PAGE, encoding="utf-8", errors="replace").read()
    run = subprocess.run([sys.executable, BUILDER],
                         capture_output=True, text=True)
    if run.returncode != 0:
        print("  the builder failed, so the page cannot be trusted either")
        print((run.stderr or run.stdout or "")[-600:])
        return 1
    after = io.open(PAGE, encoding="utf-8", errors="replace").read()

    if before == after:
        print("  The served colophon matches what build_colophon.py produces "
              "today\n  (%d bytes)." % len(after))
        return 0

    # Say WHAT differs, not merely that something does. A byte count tells
    # nobody which fix went missing.
    import difflib
    diff = list(difflib.unified_diff(before.splitlines(), after.splitlines(),
                                     lineterm="", n=0))
    adds = [l[1:].strip() for l in diff
            if l.startswith("+") and not l.startswith("+++")]
    dels = [l[1:].strip() for l in diff
            if l.startswith("-") and not l.startswith("---")]

    print("  THE COMMITTED PAGE IS NOT WHAT THE BUILDER MAKES")
    print()
    print("  %d line(s) would be added, %d removed. The page has been "
          "rebuilt\n  in place; commit it." % (len(adds), len(dels)))
    print()
    for line in adds[:4]:
        print("    + %s" % line[:96])
    for line in dels[:4]:
        print("    - %s" % line[:96])
    print()
    print("  This is usually another window rebuilding the page from a")
    print("  checkout that predates a change to scripts/, and committing")
    print("  the result over it. The source and the page disagree, nothing")
    print("  errors, and the site serves the page.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
