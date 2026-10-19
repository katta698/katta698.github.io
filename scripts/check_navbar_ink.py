"""The nav bar must carry light-mode ink in light mode, on every page shape.

Why this exists
---------------
Reported 2026-10-19: "when I open a specific blog ... the subscribe button is
kind of grayed out in the light mode". Everything else on the site was fine.

The bar's ink is set by a short stack of selectors in site-footer.css, and the
one covering the pages where light mode is the ABSENCE of a class (rather than
`body.light`) was keyed on `nav:has(> .audio-toggle)` -- the blog index, and
nothing else. A post page has no audio toggle and no `body.light`, so it
matched none of them and kept the DARK-mode ink on a light bar:

    nav color  rgb(237,235,230)  on a bar of rgb(184,191,194)

Only the subscribe glyph inherits the bar's colour; every other control sets
its own. So ~340 pages had one washed-out control, and it read as a disabled
button rather than as a bug.

What it asserts, and why this shape
-----------------------------------
That the bar's COMPUTED colour is the light ink in light mode and the dark ink
in dark mode, on one page of every shape the site serves. Not a contrast
ratio: the first version of this file measured contrast, and it reported four
controls below 4.5:1 that were fine -- it was compositing each glyph against
whichever ancestor it found a background on, which is not the surface the
glyph is read against. A checker that cries wolf gets switched off, so it
asserts the thing that was actually wrong and can actually be read.

Transitions are disabled before sampling. Without that, two runs against an
identical stylesheet differ, because the probe catches colours mid-fade -- the
first before/after diff taken here was almost entirely that noise.

The canary
----------
`--canary` deletes the post-page rule from a COPY of the stylesheet, serves
that, and requires the check to fail. A check that cannot fail is worse than
no check, and this one guards a selector whose whole job is to match pages
that are easy to forget.

    python scripts/check_navbar_ink.py
    python scripts/check_navbar_ink.py --canary
"""
import functools
import http.server
import io
import os
import shutil
import socketserver
import sys
import tempfile
import threading

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS = os.path.join("blog", "assets", "site-footer.css")

LIGHT_INK = "rgb(28, 33, 32)"
DARK_INK = "rgb(237, 235, 230)"

# The rule the canary removes. Matched on the selector text so the canary
# breaks loudly if the rule is ever renamed, instead of quietly removing
# nothing and "passing".
RULE_HEAD = "body:not(.dark):has(.post-page-layout) nav,"
RULE_TAIL = "body:not(.dark):has(.post-page-layout) .nav { color: #1C2120; }"

# "light-class" pages default to DARK and add .light. The blog family defaults
# to LIGHT and adds .dark. Asking both the same question needs both spellings;
# this is the distinction the broken selector was trying to encode.
PAGES = [
    ("portfolio", "/index.html", "light-class"),
    # resume.html is deliberately absent: it carries no <nav> at all, only a
    # .resume-back-nav link, so it has no shared bar to get wrong. Listing it
    # made this check report two failures that were not faults, which is the
    # fastest way to get a check ignored.
    ("now", "/now.html", "light-class"),
    ("intelligence", "/intelligence/index.html", "light-class"),
    ("whats-new", "/intelligence/whats-new/index.html", "light-class"),
    ("live status", "/intelligence/status/index.html", "light-class"),
    ("blog index", "/blog/index.html", "no-dark"),
    ("post (sync-built)", "/blog/archive-mongodb-data-in-azure/index.html",
     "no-dark"),
    ("post (arch aws)", "/blog/aws-architecture-access-analyzer/index.html",
     "no-dark"),
    ("post (arch azure)", "/blog/azure-architecture-writeback/index.html",
     "no-dark"),
]

NO_TRANSITIONS = ("*,*::before,*::after{transition:none !important;"
                  "animation:none !important}")

PROBE = """() => {
  var nav = document.querySelector('nav, .nav');
  if (!nav) return null;
  var btn = nav.querySelector('#subnav-btn, .subnav-btn');
  return {
    nav: getComputedStyle(nav).color,
    btn: btn ? getComputedStyle(btn).color : null
  };
}"""


def serve(directory, port):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=directory)
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def run(directory, port, quiet=False):
    """Returns a list of (page, theme, what, got, want) failures."""
    httpd = serve(directory, port)
    fails = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            # .subnav-btn is display:none at <=1080px, so a narrow viewport
            # would "pass" by never rendering the control that broke.
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            for label, path, how in PAGES:
                page.goto("http://127.0.0.1:%d%s" % (port, path),
                          wait_until="networkidle")
                page.add_style_tag(content=NO_TRANSITIONS)
                for theme, want in (("light", LIGHT_INK), ("dark", DARK_INK)):
                    if how == "light-class":
                        page.evaluate(
                            "(d) => { document.body.classList.toggle('dark', d);"
                            " document.body.classList.toggle('light', !d); }",
                            theme == "dark")
                    else:
                        page.evaluate(
                            "(d) => document.body.classList.toggle('dark', d)",
                            theme == "dark")
                    page.wait_for_timeout(250)
                    got = page.evaluate(PROBE)
                    if got is None:
                        fails.append((label, theme, "nav", "NO NAV", want))
                        continue
                    ok = got["nav"] == want
                    if not quiet:
                        print("  %-19s %-5s nav=%-18s %s"
                              % (label, theme, got["nav"],
                                 "ok" if ok else "WRONG -- want " + want))
                    if not ok:
                        fails.append((label, theme, "nav", got["nav"], want))
                    # The glyph inherits, so it should equal the bar. If it
                    # ever stops doing that, this says so rather than letting
                    # a correct bar hide a wrong button.
                    if got["btn"] and got["btn"] != got["nav"]:
                        fails.append((label, theme, "subscribe glyph",
                                      got["btn"], got["nav"]))
            browser.close()
    finally:
        httpd.shutdown()
    return fails


def canary():
    """The check must FAIL when the post-page rule is gone."""
    tmp = tempfile.mkdtemp(prefix="navink-")
    try:
        # A copy of the site, minus the one rule. Symlinks would be lighter
        # but Windows needs a privilege for them, so this copies.
        shutil.copytree(ROOT, tmp, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns(
                            ".git", "node_modules", "_archive", ".navprobe"))
        p = os.path.join(tmp, CSS)
        s = io.open(p, encoding="utf-8").read()
        if RULE_HEAD not in s or RULE_TAIL not in s:
            print("CANARY BROKEN: the rule it removes is not in the "
                  "stylesheet under its expected selector.")
            print("  looked for: %s" % RULE_HEAD)
            return 1
        cut = s.replace(RULE_HEAD, "").replace(RULE_TAIL, "")
        io.open(p, "w", encoding="utf-8", newline="").write(cut)

        print("Canary: post-page rule removed; the check must now fail.\n")
        fails = run(tmp, 8757, quiet=True)
        posts = [f for f in fails if f[0].startswith("post") and f[1] == "light"]
        if not posts:
            print("CANARY FAILED -- the check passed without the rule, so it "
                  "is not testing what it claims to test.")
            return 1
        print("Canary OK: %d post-page/light failure(s) detected without the "
              "rule." % len(posts))
        for f in posts:
            print("  %s / %s -> %s (want %s)" % (f[0], f[1], f[3], f[4]))
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    if "--canary" in sys.argv:
        return canary()
    print("Nav-bar ink, light and dark, per page shape:\n")
    fails = run(ROOT, 8756)
    if fails:
        print("\n%d problem(s):" % len(fails))
        for label, theme, what, got, want in fails:
            print("  %s / %s / %s -> %s (want %s)"
                  % (label, theme, what, got, want))
        return 1
    print("\nEvery bar carries the right ink for its theme.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
