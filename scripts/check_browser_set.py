#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""preflight's BROWSER set agrees with which checks actually drive a browser.

    python scripts/check_browser_set.py

Why this exists
---------------
BROWSER in scripts/preflight.py decides what `--fast` skips. Membership is
asserted by hand, and until now nothing compared it against the code. The
same defect has now been written up in that file three times:

    check_shift           drove a browser, was not listed  -> --fast ran it
                                                               anyway: 198s
                                                               of a 434s push
    check_colophon_built  drove no browser, was listed     -> --fast AND the
                                                               push hook both
                                                               skipped it, so
                                                               nothing asked
                                                               whether the
                                                               served colophon
                                                               matched the repo.
                                                               It went stale for
                                                               weeks: 279 posts
                                                               live, 281 on main
    check_status_feed     drove a browser, was not listed  -> two 420s timeouts
    check_subscribe                                           per push, against
                                                               a hook meant to
                                                               finish in ~150s.
                                                               Every push from
                                                               every lab failed,
                                                               and the only
                                                               symptom git showed
                                                               was "failed to push
                                                               some refs"

Both directions cost real time, and neither announces itself: the omission
looks like a network problem and the surplus looks like nothing at all. The
third recurrence is the finding. A hand-maintained list that nothing checks
will drift again, so this asks the code instead.

How it decides
--------------
It parses each check with `ast` and looks for a playwright import -- never a
text search, because the files in this directory carry long prose comments
that mention playwright by name and would match. Local imports are followed
within scripts/, so a check that drives a browser through a helper module is
still counted as a browser check.

A deliberate exception goes in EXCEPTIONS below with a reason, so that the
one case somebody argued about is recorded rather than quietly tolerated.
"""

import ast
import os
import sys

SCRIPTS = os.path.dirname(os.path.abspath(__file__))

# name -> reason. A check listed here is exempt from the comparison.
# Keep this empty if you can; an entry is a claim that the code and the set
# disagree for a good reason, and it should say what that reason is.
EXCEPTIONS = {}


def _module_imports(path, _seen=None):
    """Every module name imported by `path`, following local imports."""
    if _seen is None:
        _seen = set()
    real = os.path.realpath(path)
    if real in _seen:
        return set()
    _seen.add(real)

    try:
        with open(path, "r", encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
    except (OSError, SyntaxError):
        return set()

    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                names.add(node.module)
            elif node.level:
                for a in node.names:
                    names.add(a.name)

    # Follow imports that resolve to a file in scripts/, so a check that
    # drives Playwright through a helper is still a browser check.
    for n in list(names):
        local = os.path.join(SCRIPTS, n.split(".")[0] + ".py")
        if os.path.isfile(local):
            names |= _module_imports(local, _seen)
    return names


def drives_browser(path):
    return any(n == "playwright" or n.startswith("playwright.")
               for n in _module_imports(path))


def main():
    sys.path.insert(0, SCRIPTS)
    try:
        import preflight
    except Exception as exc:                     # noqa: BLE001
        print("CANNOT RUN: scripts/preflight.py would not import: %r" % (exc,))
        return 2

    browser = set(preflight.BROWSER)
    skip = set(preflight.SKIP)

    missing, surplus = [], []
    for f in sorted(os.listdir(SCRIPTS)):
        if not f.endswith(".py"):
            continue
        if not (f.startswith("check_") or f.startswith("validate_")):
            continue
        name = f[:-3]
        if name in skip or name in EXCEPTIONS or name == "check_browser_set":
            continue
        uses = drives_browser(os.path.join(SCRIPTS, f))
        if uses and name not in browser:
            missing.append(name)
        elif not uses and name in browser:
            surplus.append(name)

    if not missing and not surplus:
        print("BROWSER matches the code: %d browser checks, %d exception(s)"
              % (len(browser), len(EXCEPTIONS)))
        return 0

    print("BROWSER in scripts/preflight.py does not match the code.")
    print()
    if missing:
        print("  Imports playwright, NOT in BROWSER -- `--fast` runs these,")
        print("  which is the one thing --fast exists to avoid. Each can cost")
        print("  up to PER_CHECK_TIMEOUT (%ds) on every push:"
              % preflight.PER_CHECK_TIMEOUT)
        for n in missing:
            print("      + %s" % n)
        print()
    if surplus:
        print("  In BROWSER, imports no playwright -- `--fast` and the push")
        print("  hook both skip these, so they never run and can go stale")
        print("  without anyone noticing:")
        for n in surplus:
            print("      - %s" % n)
        print()
    print("  Fix the set in scripts/preflight.py, or add a reasoned entry to")
    print("  EXCEPTIONS in scripts/check_browser_set.py.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
