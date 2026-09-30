#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail when a page asks for a version of the shared assets that is not current.

    python scripts/check_asset_stamps.py

Why this exists
---------------
The shared script and stylesheet are cache-busted with a content hash, and the
pages that link them are built by three different scripts. Change the assets
and rebuild only some of those pages, and the rest keep pointing at the old
hash -- so a returning reader keeps executing the copy their browser already
has, indefinitely, while the file on the server is correct.

That is the worst shape a bug can take: the fix is deployed, the code is right,
the reader still sees the old behaviour, and nothing anywhere reports a
problem. It cost an evening. What's New sat two versions behind on the nav
work, and the status page linked the script with no version at all, which meant
it was never busted for anyone.

So: every page that links the shared script must ask for the hash the shared
files currently produce.
"""
import io
import os
import subprocess
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP = {"node_modules", ".git", "_archive", "_templates"}

sys.path.insert(0, os.path.join(ROOT, "scripts"))



def publishable():
    """Paths git would actually publish: tracked, plus untracked-not-ignored.

    Why (2026-09-30): a push was blocked by a stale stamp in
    _sweep/publish/, a gitignored scratch page. Nothing in there can reach the
    site, so nothing in there can serve a stale asset to anybody -- but the
    directory walk found it and the shared hook stopped every worktree.

    Same fix, same reason, as check_css_balance: a gate that fails on files it
    is not responsible for teaches people to reach for --no-verify.

    None when git cannot answer, in which case everything is scanned.
    """
    try:
        out = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT, capture_output=True, text=True, timeout=120)
        if out.returncode != 0:
            return None
        return {l.strip().replace("\\", "/") for l in out.stdout.splitlines() if l.strip()}
    except Exception:                                           # noqa: BLE001
        return None



def main():
    try:
        import sync_blog
        want = sync_blog.JS_VERSION
    except Exception as exc:                                    # noqa: BLE001
        print("  cannot read the shared version (%s)" % str(exc)[:70])
        return 1

    print("  shared assets currently hash to %s" % want)

    linked = re.compile(r'site-footer\.js(\?v=([a-f0-9]+))?')
    stale, unversioned, ok = [], [], 0
    allowed = publishable()

    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP and not d.startswith(".")]
        for name in files:
            if not name.endswith(".html"):
                continue
            path = os.path.join(base, name)
            rel = os.path.relpath(path, ROOT).replace("\\", "/")
            if allowed is not None and rel not in allowed:
                continue
            try:
                text = io.open(path, encoding="utf-8").read()
            except (OSError, UnicodeDecodeError):
                continue
            # Only the actual script tag, not prose mentioning the file.
            for m in re.finditer(r'<script[^>]+src="[^"]*site-footer\.js([^"]*)"', text):
                q = m.group(1)
                got = re.search(r'\?v=([a-f0-9]+)', q or "")
                if not got:
                    unversioned.append(rel)
                elif got.group(1) != want:
                    stale.append((rel, got.group(1)))
                else:
                    ok += 1

    print("  %d page(s) current, %d stale, %d unversioned"
          % (ok, len(stale), len(unversioned)))

    if not stale and not unversioned:
        print("  every page asks for the current assets.")
        return 0

    print("\n  PAGES SERVING STALE ASSETS\n")
    for rel, got in stale[:20]:
        print("  - %-52s asks for %s" % (rel, got))
    if len(stale) > 20:
        print("    ...and %d more" % (len(stale) - 20))
    for rel in unversioned[:20]:
        print("  - %-52s no version at all" % rel)

    print("\n  Rebuild the pages that link them:")
    print("    python scripts/build_status_page.py")
    print("    python scripts/build_news_page.py")
    print("    python scripts/sync_blog.py")
    print("\n  A page pinned to an old hash does not look broken. It looks")
    print("  like the change was never made.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
