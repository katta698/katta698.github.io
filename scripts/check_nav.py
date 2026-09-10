#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Drive the navigation on every page at every width and check it holds.

    python scripts/check_nav.py

Why this exists
---------------
The nav has now broken four separate ways in one evening, each time from a
change that was correct for the page it was written against and wrong for one
of the others:

  the five links wrapped onto two and three rows, differently at every width
  the palette panel hung 160px off the left edge once the bar wrapped
  two orphan braces killed the brand mark rule on two pages, so the favicon
    rendered as a stretched square while the other three showed a circle
  the collapse matched links by href, and the brand mark is a link to "/",
    so the favicon disappeared from every page below 1080px

Every one of those was found by a reader looking at a phone, which is the
worst possible detector: it only fires on the pages someone happens to open,
and only after the change is live.

So this asserts the four things the bar has to do, on five page types at six
widths, and fails the build when one of them stops being true.
"""
import argparse
import http.server
import os
import re
import socketserver
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8941

PAGES = [
    ("portfolio", "/"),
    ("blog", "/blog/"),
    ("hub", "/intelligence/"),
    ("status", "/intelligence/status/"),
    ("whats-new", "/intelligence/whats-new/"),
]
WIDTHS = [320, 390, 768, 920, 1100, 1440]

DESTINATIONS = ["/", "/blog/", "/intelligence/",
                "/intelligence/whats-new/", "/intelligence/status/"]

PROBE = """() => {
  const nav = document.querySelector('nav') || document.querySelector('.nav');
  if (!nav) return { fatal: 'no nav' };

  // Nothing may stick out of the window, and the page must not scroll sideways.
  let edge = 0;
  nav.querySelectorAll('*').forEach(e => {
    const r = e.getBoundingClientRect();
    if (r.width > 0 && r.right > edge) edge = r.right;
  });
  window.scrollTo(300, 0);
  const sideways = window.scrollX;
  window.scrollTo(0, 0);

  const mark = document.querySelector('.brand-mark');
  const mr = mark ? mark.getBoundingClientRect() : null;

  // The wordmark's typography, so five pages cannot set the same two words
  // three different ways again.
  const word = document.querySelector('.brand-name');
  const ws = word ? getComputedStyle(word) : null;
  // Colour is in here too: the two families agreed on the light-mode ink and
  // not the dark one -- #EDEBE6 on three pages, pure #FFFFFF on the other two,
  // which reads as one being warm and the other cold.
  const wordFace = ws
    ? [ws.fontFamily.split(',')[0].replace(/['"]/g, '').trim(),
       ws.fontWeight, ws.letterSpacing, ws.color].join('/')
    : null;

  // Every destination reachable, whether in the bar or behind the mark.
  const sheet = document.querySelector('.ck-sheet');
  const inBar = [...nav.querySelectorAll('a[href]')]
    .filter(a => a.getBoundingClientRect().width > 0)
    .map(a => a.getAttribute('href'));
  // The panel only counts when the mark that opens it is actually on screen.
  //
  // This counted the panel's links unconditionally, and the panel exists in
  // the DOM at every width -- so a bar with no links AND no mark still scored
  // five reachable destinations. That is exactly the state an iPad in
  // landscape was in, and this check passed it at 1440 without noticing.
  const ck = document.querySelector('.ck-btn');
  const markUsable = !!ck && getComputedStyle(ck).display !== 'none'
                     && ck.getBoundingClientRect().width > 0;
  const inSheet = (sheet && markUsable)
    ? [...sheet.querySelectorAll('a[href]')].map(a => a.getAttribute('href')) : [];

  // And the current page said out loud, one way or the other.
  const here = document.querySelector('.ck-here');
  const active = document.querySelector('.nav-links a.active, .ck-sheet a.is-here');

  // The mark in the BAR, and whether it actually drew.
  //
  // The blog carried a correct .nav-links a.active::after rule that had been
  // dead for weeks: a later change made the links inline-flex, which turns a
  // display:block ::after into a zero-width flex item beside the word instead
  // of a rule under it. The CSS was present, the class was on the right
  // anchor, and nothing was visible -- so this measures the pixels rather than
  // asking whether the rule exists.
  const cur = [...nav.querySelectorAll('a[aria-current="page"]')]
    .filter(a => !a.closest('.ck-sheet') && a.getBoundingClientRect().width > 0);
  // The bar's own colour and the marked link's, for the contrast check.
  const navBg = getComputedStyle(nav).backgroundColor;
  const curColour = cur.length ? getComputedStyle(cur[0]).color : null;
  let rule = null;
  if (cur.length) {
    const a = getComputedStyle(cur[0], '::after');
    rule = { w: parseFloat(a.width) || 0, h: parseFloat(a.height) || 0,
             content: a.content };
  }
  const marked = cur.length;

  // Where the five site links actually SIT, measured from the right edge.
  //
  // Same order and same gap is not the same bar: the portfolio bought its link
  // spacing with padding while the others used the list's gap, so with one gap
  // rule applied the same five words still sat 5px further apart there. Three
  // pages looking right individually is how every one of these drifts started,
  // so the comparison is between pages, not against a number.
  //
  // Measured from the first link rather than from the window edge: the
  // Intelligence pages carry no beach-audio button, so their row genuinely
  // ends 25px further right and always will until that control exists on all
  // five. This asks whether the five words are laid out the same way, which is
  // the thing one stylesheet can promise.
  const SITE = ['/', '/blog/', '/intelligence/',
                '/intelligence/whats-new/', '/intelligence/status/'];
  const row = [...nav.querySelectorAll('.nav-links a[href]')]
    .filter(a => SITE.indexOf(a.getAttribute('href')) >= 0)
    .filter(a => a.getBoundingClientRect().width > 0)
    .map((a, i, all) => a.getAttribute('href') + '@' +
         Math.round(a.getBoundingClientRect().left -
                    all[0].getBoundingClientRect().left))
    .join(' ');

  // The bar's own order, left to right, so five pages cannot drift into five
  // different arrangements again.
  const seen = [];
  const walk = el => { [...el.children].forEach(c => {
    const r = c.getBoundingClientRect(); if (r.width < 1) return;
    if (c.matches('button,a,img,span,div.pal-nav') || !c.children.length) {
      seen.push([(c.className||'').toString().split(' ')[0] || c.tagName.toLowerCase(),
                 Math.round(r.x)]);
    } else walk(c); }); };
  walk(nav);
  seen.sort((a,b)=>a[1]-b[1]);
  const order = seen.map(x => x[0]);

  return {
    order, marked, rule, row, navBg, curColour,
    edge: Math.round(edge), vw: window.innerWidth, sideways,
    wordFace,
    markVisible: !!(mr && mr.width > 0 && mr.height > 0),
    markRadius: mark ? getComputedStyle(mark).borderRadius : null,
    reach: [...new Set(inBar.concat(inSheet))],
    saysWhere: !!((here && here.textContent.trim()) || active)
  };
}"""


def _rgb(text):
    """The three channels of any colour string CSS hands back, 0-1."""
    if not text:
        return None
    nums = re.findall(r"[\d.]+", text)
    if len(nums) < 3:
        return None
    v = [float(n) for n in nums[:3]]
    # color(srgb 0.98 0.94 0.94) is already 0-1; rgb(250, 242, 242) is 0-255.
    if "srgb" not in text:
        v = [c / 255.0 for c in v]
    return v


def contrast(fg, bg):
    a, b = _rgb(fg), _rgb(bg)
    if not a or not b:
        return None

    def lum(v):
        f = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
             for c in v]
        return 0.2126 * f[0] + 0.7152 * f[1] + 0.0722 * f[2]

    l1, l2 = sorted((lum(a), lum(b)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="webkit",
                    choices=["webkit", "chromium", "firefox"])
    args = ap.parse_args()

    os.chdir(ROOT)

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    srv = socketserver.TCPServer(("127.0.0.1", PORT), Quiet)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    from playwright.sync_api import sync_playwright

    problems = []
    faces = {}
    rows = {}
    with sync_playwright() as pw:
        browser = getattr(pw, args.engine).launch()
        for name, path in PAGES:
            notes = []
            for w in WIDTHS:
                pg = browser.new_page(viewport={"width": w, "height": 820})
                pg.goto("http://127.0.0.1:%d%s" % (PORT, path),
                        wait_until="networkidle", timeout=60000)
                pg.wait_for_timeout(900)
                r = pg.evaluate(PROBE)
                tag = "%s@%d" % (name, w)

                if r.get("fatal"):
                    problems.append("%s: %s" % (tag, r["fatal"]))
                    pg.close()
                    continue
                if r["edge"] > r["vw"] + 1:
                    problems.append("%s: the bar is %dpx wide in a %dpx window"
                                    % (tag, r["edge"], r["vw"]))
                if r["sideways"]:
                    problems.append("%s: the page scrolls sideways" % tag)
                if not r["markVisible"]:
                    problems.append("%s: the brand mark is not visible" % tag)
                elif r["markRadius"] != "50%":
                    problems.append("%s: the brand mark is not round (%s)"
                                    % (tag, r["markRadius"]))
                missing = [d for d in DESTINATIONS if d not in r["reach"]]
                if missing:
                    problems.append("%s: cannot reach %s"
                                    % (tag, ", ".join(missing)))
                if not r["saysWhere"]:
                    problems.append("%s: nothing says which page this is" % tag)
                # Above the breakpoint the links are in the bar, so exactly one
                # of them has to be marked and the mark has to be visible.
                if w > 1080:
                    if r.get("marked") != 1:
                        problems.append(
                            "%s: %d link(s) in the bar marked as the current "
                            "page, expected 1" % (tag, r.get("marked") or 0))
                    else:
                        rule = r.get("rule") or {}
                        if rule.get("h", 0) < 1 or rule.get("w", 0) < 20:
                            problems.append(
                                "%s: the current page's underline measures "
                                "%.0fx%.0f -- the rule is there and nothing "
                                "draws" % (tag, rule.get("w", 0),
                                           rule.get("h", 0)))
                # Same arrangement on every page: the mark first, the cairn
                # last, the page's name immediately before it. Five pages grew
                # five different bars once -- controls hard left on three,
                # floated to the middle on one, and one missing its theme
                # control entirely -- and every one of them looked reasonable
                # on its own page.
                order = r.get("order") or []
                if order:
                    if order[0] != "nav-logo":
                        problems.append("%s: the bar does not start with the "
                                        "brand mark (%s)" % (tag, order[0]))
                    if order[-1] != "ck-btn" and "ck-btn" in order:
                        problems.append("%s: the menu mark is not last (%s)"
                                        % (tag, order[-1]))
                    if "ck-here" in order and "ck-btn" in order:
                        if order.index("ck-here") != order.index("ck-btn") - 1:
                            problems.append(
                                "%s: the page name is not beside the mark (%s)"
                                % (tag, " ".join(order)))
                # The marked link has to be READABLE on the bar it sits on,
                # in both themes.
                #
                # The colour is chosen in JS by measuring the bar, because the
                # five pages signal "light" with three different conventions.
                # That measurement was taken 60ms after the toggle, and the
                # blog ANIMATES its background -- so it read a bar still mostly
                # dark, picked the dark-mode tan, and never looked again. Live,
                # in light mode, the current page and the "you are here" label
                # were both about 2:1 on cream. Nothing in the DOM was wrong;
                # the reading was taken too early.
                if w == 1440 and r.get("curColour"):
                    c = contrast(r["curColour"], r.get("navBg"))
                    if c is not None and c < 4.5:
                        problems.append(
                            "%s: the current page's link is %.1f:1 on the bar "
                            "(%s on %s)" % (tag, c, r["curColour"],
                                            r.get("navBg")))
                # The link row, compared against one width.
                if w == 1440 and r.get("row"):
                    rows[name] = [(h, int(x)) for h, x in
                                  (part.split("@") for part in r["row"].split())]
                if r.get("wordFace"):
                    faces.setdefault(r["wordFace"], []).append(name)
                # ...and again in the OTHER theme, which is where it failed.
                # A reader who switches the theme is the only one who ever saw
                # this, and no check had ever switched it.
                if w == 1440:
                    pg.evaluate("() => { const t = "
                                "document.querySelector('.theme-toggle'); "
                                "if (t) t.click(); }")
                    pg.wait_for_timeout(1500)
                    r2 = pg.evaluate(PROBE)
                    if r2.get("curColour"):
                        c = contrast(r2["curColour"], r2.get("navBg"))
                        if c is not None and c < 4.5:
                            problems.append(
                                "%s: after switching the theme the current "
                                "page's link is %.1f:1 on the bar (%s on %s)"
                                % (tag, c, r2["curColour"], r2.get("navBg")))
                notes.append("%d:%d" % (w, r["edge"]))
                pg.close()
            print("  %-10s widths ok, bar width by viewport: %s"
                  % (name, " ".join(notes)))
        browser.close()
    srv.shutdown()

    # Same wordmark everywhere, or nowhere. Three pages set it in Playfair
    # at 600 while the portfolio and the blog used DM Sans at 700, with
    # different letter spacing from each other -- three renderings of the
    # same two words in a bar that is otherwise identical.
    if len(faces) > 1:
        for face, where in sorted(faces.items(), key=lambda kv: -len(kv[1])):
            problems.append("the wordmark is %s on %s"
                            % (face, ", ".join(sorted(set(where)))))
    elif faces:
        print("  wordmark: %s on every page" % list(faces)[0])

    # Compared against the middle of the five, with 6px of slack.
    #
    # Not exact equality: the current page's link is set at 600 where the rest
    # are 500, so whichever word is bold is a couple of pixels wider and
    # everything after it shifts -- on a different word on every page. That is
    # the marking working, not the bar drifting. Six pixels is under half a
    # character and well below the 25px that a missing control moves things,
    # or the 99px that a wrapped label did.
    if rows:
        cols = {}
        for name, offs in rows.items():
            for href, x in offs:
                cols.setdefault(href, []).append((name, x))
        worst = 0
        for href, seen in cols.items():
            mid = sorted(x for _, x in seen)[len(seen) // 2]
            for name, x in seen:
                if abs(x - mid) > 6:
                    problems.append(
                        "at 1440 %s sits %+dpx from where the other pages put "
                        "it, on %s" % (href, x - mid, name))
                worst = max(worst, abs(x - mid))
        if worst <= 6:
            print("  the five links are laid out the same way on every page "
                  "(worst disagreement %dpx)" % worst)

    if problems:
        print("\n  %d NAVIGATION PROBLEM(S)\n" % len(problems))
        for p in problems:
            print("  - %s" % p)
        return 1
    print("\n  the bar fits, the mark shows, every page is reachable, and each")
    print("  page says which one it is -- on %d pages at %d widths."
          % (len(PAGES), len(WIDTHS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
