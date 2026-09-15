#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Assert the service worker still serves pages the way CLAUDE.md requires.

    python scripts/check_sw_strategy.py

Why this exists
---------------
CLAUDE.md carries a standing rule, under a heading that states it as a
prohibition rather than a preference:

    ### Caching strategy -- do not make HTML cache-first
    Navigations are network-first so a live fix to a post page takes effect on
    the next load, exactly as it does with no service worker.

On 2026-09-14 `scripts/sw.template.js` stopped doing that. Navigations became
stale-while-revalidate, with two paths exempted, to fix "navigating between
pages is not seamless". The change is reasoned and its own comment states the
cost honestly -- "a returning reader sees the copy from their last visit" --
but it is the thing the rule forbids, and the rule exists because of what
follows from it.

What followed: four days of a published post appearing to lack its widgets.
The widgets were in the deployed HTML the whole time. Every reload returned the
previous copy, so a fix that had shipped and deployed was invisible on the
author's own device, and the same symptom recurred on the next publish. A
reader's diagnostic said it plainly -- "entered by: reload / served from:
cache". A reload that returns the previous page is indistinguishable from a fix
that did not work, which is why this costs hours rather than minutes.

The exemption list already concedes the principle. Live status and What's New
keep network-first because serving yesterday's copy would make those pages
quietly wrong. A blog post on the day it publishes has exactly that property.

**This does not judge the caching strategy.** Stale-while-revalidate for
navigations may well be the right call for a reader moving between pages; that
is a design decision and not this file's to make. What it asserts is that the
decision and the written rule agree. Today they do not, and nothing said so --
which is how it survived four days and a second occurrence.

Advisory, deliberately. It reports a live divergence that this window does not
own the fix for: `sw.template.js` belongs to the `main` window, which is
actively editing it. Promote to blocking once the two agree, so the next
divergence fails a build instead of costing an evening.
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "scripts", "sw.template.js")
CLAUDE_MD = os.path.join(ROOT, "CLAUDE.md")

# The rule, matched in CLAUDE.md rather than restated here. If the rule is
# rewritten the check has to be revisited with it -- a checker asserting a rule
# nobody holds any more is worse than no checker, and a copy of the sentence in
# this file would drift silently.
RULE = re.compile(r"Navigations are network-first", re.I)

NAVIGATE_BLOCK = re.compile(
    r"if\s*\(\s*request\.mode\s*===\s*['\"]navigate['\"]\s*\)\s*\{([\s\S]*?)\n\s{2}\}",
    re.M)


def read(path):
    return io.open(path, encoding="utf-8").read()


def main():
    problems = []
    notes = []

    if not os.path.exists(TEMPLATE):
        print("sw.template.js is missing; nothing to check.")
        return 0

    template = read(TEMPLATE)
    rule_held = bool(RULE.search(read(CLAUDE_MD))) if os.path.exists(CLAUDE_MD) else False

    m = NAVIGATE_BLOCK.search(template)
    if not m:
        # Not a pass. The handler was found before and cannot be found now,
        # which means this check has stopped checking.
        problems.append(
            "could not find the request.mode === 'navigate' branch in "
            "sw.template.js -- this check can no longer see what it asserts")
        block = ""
    else:
        block = m.group(1)

    if block:
        swr = "staleWhileRevalidate" in block
        netfirst = "networkFirst" in block
        if swr and rule_held:
            problems.append(
                "navigations are served stale-while-revalidate, but CLAUDE.md "
                "says \"Navigations are network-first so a live fix to a post "
                "page takes effect on the next load\". A published post shows "
                "the reader their previous copy, and a reload returns the same "
                "one -- which reads as a fix that did not work.")
            if netfirst:
                exempt = re.search(r"const LIVE_DATA\s*=\s*\[([^\]]*)\]", template)
                listed = exempt.group(1).strip() if exempt else "(none)"
                notes.append(
                    "Some paths are exempted and do get network-first: %s. "
                    "That list concedes the principle -- those pages are "
                    "exempt because yesterday's copy would make them wrong. A "
                    "blog post has the same property on the day it publishes, "
                    "so adding the post paths there is the smallest fix."
                    % listed)
        elif swr and not rule_held:
            notes.append(
                "navigations are stale-while-revalidate and CLAUDE.md no "
                "longer states the network-first rule. Consistent, but check "
                "the rule was changed deliberately rather than dropped.")

    print("Service worker navigation strategy")
    print("-" * 72)
    if problems:
        for p in problems:
            print("  DIVERGENCE: %s" % p)
        for n in notes:
            print("\n  note: %s" % n)
        print("\nAdvisory: scripts/sw.template.js belongs to the main window.")
        print("Fix there, then promote this check to blocking so the next")
        print("divergence fails a build rather than costing an evening.")
    else:
        print("  ok -- the template and CLAUDE.md agree on how pages are served.")
    print("-" * 72)
    # Advisory by design; see the module docstring.
    return 0


if __name__ == "__main__":
    sys.exit(main())
