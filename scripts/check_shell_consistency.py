#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Everything shared between pages is actually the same on every page.

    python scripts/check_shell_consistency.py
    python scripts/check_shell_consistency.py --live

Why this exists
---------------
Asked for directly: "the length, the logo size, text, font -- everything has to
be similar, so when I move between tabs it has to be seamless."

Each of these was found and fixed one at a time, by eye, after being reported:

    the festival strip   37px on the portfolio, 33px on the other four,
                         because it inherited that page's body line-height
    the wordmark         0.8px further from the mark on two tabs, because the
                         gap rule exists in five separate files with two values
    the nav logo         1.05rem on the portfolio at phone widths, 1rem
                         everywhere else
    the hero             a video on two pages and nothing on three

Every one is the same species: a value restated per page, drifting by an amount
small enough to survive for months and large enough to notice when you move
between tabs. Fixing them one at a time does not stop the next one.

So this compares the RENDERED shell across all five pages at three widths and
fails on any divergence. It measures the result rather than the rules, so it
does not care how many copies of a declaration exist or which one wins -- only
that the pages agree. The portfolio is the reference because it is where a
reader starts.

Deliberately NOT checked: anything below the shell. Pages are allowed to differ
in their own content; that is the point of having more than one.
"""
import argparse
import http.server
import os
import socketserver
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = ["/", "/blog/", "/intelligence/", "/intelligence/whats-new/",
         "/intelligence/status/"]
WIDTHS = [390, 1024, 1440]
# Both, not just the default.
#
# The blog's bar was 92% opaque against solid on the other four, and its rule
# was rgba(0,0,0,.06) against #CFCFCE -- in LIGHT MODE ONLY. This check ran in
# the default theme and reported the shell identical the whole time.
THEMES = ["dark", "light"]
# Sub-pixel layout noise. The smallest fault actually reported was 0.8px, so
# this sits just under it rather than at some round number.
TOL = 0.6

PROBE = r"""() => {
  const g = (sel) => document.querySelector(sel);
  const box = (e) => { if (!e) return null; const r = e.getBoundingClientRect();
    return {x: r.x, y: r.y, w: r.width, h: r.height}; };
  const font = (e) => { if (!e) return null; const c = getComputedStyle(e);
    return {size: c.fontSize, weight: c.fontWeight,
            family: c.fontFamily.split(',')[0].replace(/[\"']/g, ''),
            spacing: c.letterSpacing, transform: c.textTransform}; };

  const nav = g('nav.nav') || g('nav');
  const mark = g('.nav-logo img, .brand-mark');
  const name = g('.brand-name');
  const banner = g('#occasion-banner');
  const hero = g('header.hero, section.hero, .hero');
  const video = g('#hero-video');
  // A link that is NOT the current page, on every page.
  //
  // The first version took whichever of Blog/Portfolio/Intelligence came
  // first, which on the portfolio is the ACTIVE one -- and an active link is
  // deliberately heavier. It reported weight 600 against 500 on all four other
  // pages, which is the nav working correctly, not a fault. Comparing the
  // current-page link on one page against an ordinary link on another compares
  // two different things.
  const ctl = (sel) => { const e = g(sel); if (!e) return null;
    const r = e.getBoundingClientRect(); const c = getComputedStyle(e);
    return {w: Math.round(r.width), h: Math.round(r.height),
            size: c.fontSize, radius: c.borderRadius, color: c.color,
            // Surface as well as size. Two icons can be 32x32 and still look
            // nothing alike if one has a filled circle behind it.
            bg: c.backgroundColor, border: c.borderWidth}; };

  const links = [].slice.call(document.querySelectorAll('nav a'));
  const link = links.filter(function (a) {
    const t = (a.textContent || '').trim();
    if (!(t === 'Blog' || t === 'Portfolio' || t === 'Intelligence')) return false;
    return !a.hasAttribute('aria-current') && !a.classList.contains('active');
  })[0];

  return {
    navH: nav ? nav.getBoundingClientRect().height : null,
    navY: nav ? nav.getBoundingClientRect().top : null,
    navBg: nav ? getComputedStyle(nav).backgroundColor : null,
    markBox: box(mark),
    markSrc: mark ? (mark.currentSrc || mark.src || '').split('/').pop() : null,
    markRadius: mark ? getComputedStyle(mark).borderRadius : null,
    nameFont: font(name),
    nameShown: name ? getComputedStyle(name).display !== 'none' : false,
    gap: (mark && name && getComputedStyle(name).display !== 'none')
         ? name.getBoundingClientRect().x -
           (mark.getBoundingClientRect().x + mark.getBoundingClientRect().width)
         : null,
    bannerH: banner ? banner.getBoundingClientRect().height : null,
    bannerFont: font(banner),
    linkFont: font(link),
    hasHero: !!hero,
    hasVideo: !!video,
    videoSrc: video ? (video.currentSrc || '').split('/').pop() : null,
    videoPoster: video ? (video.poster || '').split('/').pop() : null,
    bodyFont: font(document.body),
    bodyBg: getComputedStyle(document.body).backgroundColor,
    // The three controls at the right of the bar. Added after the music icon
    // turned out to be 32x20 on three pages, 32x34 on one and 32x44 on
    // another -- at 390px only, because the rule that pins them lived in the
    // desktop block and the phone block set order and margin but never size.
    ctlAudio: ctl('#audio-toggle, .audio-toggle'),
    ctlTheme: ctl('#nav-theme-btn, .theme-toggle'),
    ctlPalette: ctl('.pal-nav-btn, .pal-toggle'),
    // Added after the subscribe glyph turned out to be the only icon in
    // the bar with a background and a border -- and not even the same
    // background: rgba(0,0,0,.05) on two pages, rgba(255,255,255,.08) on
    // another. The check compared the other three and passed while this
    // one wore a grey circle nobody else wore.
    ctlSubscribe: ctl('#subnav-btn, .subnav-btn'),
    // The bar's own ink, rule and backdrop.
    //
    // navBg was already compared and already agreed. These three did not,
    // and nothing read them: four different border colours under five
    // headers (rgba(255,255,255,.05), rgba(255,255,255,.06), #2F3131 and
    // #2E3634), a blur(12px) on the blog and a saturate(1.8) blur(8px) on
    // Live status where the other three had none, and #F5F5F3 against
    // #EDEBE6 for the ink the subscribe and palette glyphs inherit.
    //
    // Each on its own is a difference nobody can point at. Together they
    // are why moving between tabs does not feel like one site, which is
    // what kept being reported while this check passed.
    navInk: nav ? getComputedStyle(nav).color : null,
    navRule: nav ? getComputedStyle(nav).borderBottomColor : null,
    navBackdrop: nav ? (getComputedStyle(nav).backdropFilter || 'none') : null
  };
}"""

NUMERIC = [("navH", "nav height"), ("navY", "nav top edge"),
           ("gap", "gap between mark and wordmark"),
           ("bannerH", "festival banner height")]
BOXES = [("markBox", "brand mark")]
EXACT = [("markSrc", "brand mark image"), ("markRadius", "brand mark radius"),
         ("navBg", "nav background"), ("hasHero", "hero section present"),
         ("hasVideo", "hero video present"), ("videoSrc", "hero clip"),
         ("videoPoster", "hero poster"), ("nameShown", "wordmark visible"),
         ("bodyBg", "page background"),
         ("navInk", "nav ink"), ("navRule", "nav rule colour"),
         ("navBackdrop", "nav backdrop-filter")]
FONTS = [("nameFont", "wordmark"), ("linkFont", "nav link"),
         ("bannerFont", "festival banner"), ("bodyFont", "body text")]
CONTROLS = [("ctlAudio", "music button"), ("ctlTheme", "theme button"),
            ("ctlPalette", "palette button"),
            ("ctlSubscribe", "subscribe button")]


def serve():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    socketserver.TCPServer.allow_reuse_address = True
    for port in range(9201, 9251):
        try:
            srv = socketserver.TCPServer(("127.0.0.1", port), H)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            return srv, port
        except OSError:
            continue
    raise SystemExit("no free port")


def compare(w, ref_page, ref, page, cur, problems):
    def note(what, a, b):
        problems.append("%dpx  %-32s %s has %s, %s has %s"
                        % (w, what, page, a, ref_page, b))

    for key, label in NUMERIC:
        a, b = cur.get(key), ref.get(key)
        if a is None and b is None:
            continue
        if (a is None) != (b is None):
            note(label, a, b)
        elif abs(a - b) > TOL:
            note(label, "%.1fpx" % a, "%.1fpx" % b)

    for key, label in BOXES:
        a, b = cur.get(key), ref.get(key)
        if not a or not b:
            if bool(a) != bool(b):
                note(label, bool(a), bool(b))
            continue
        for f in ("x", "y", "w", "h"):
            if abs(a[f] - b[f]) > TOL:
                note("%s %s" % (label, f), "%.1f" % a[f], "%.1f" % b[f])

    for key, label in EXACT:
        if cur.get(key) != ref.get(key):
            note(label, repr(cur.get(key)), repr(ref.get(key)))

    for key, label in FONTS:
        a, b = cur.get(key), ref.get(key)
        if not a or not b:
            continue
        for f in ("size", "weight", "family", "spacing", "transform"):
            if a.get(f) != b.get(f):
                note("%s %s" % (label, f), repr(a.get(f)), repr(b.get(f)))

    for key, label in CONTROLS:
        a, b = cur.get(key), ref.get(key)
        if (a is None) != (b is None):
            note("%s present" % label, bool(a), bool(b))
            continue
        if not a:
            continue
        for f in ("w", "h", "size", "radius", "bg", "border"):
            if a.get(f) != b.get(f):
                note("%s %s" % (label, f), repr(a.get(f)), repr(b.get(f)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    args = ap.parse_args()
    os.chdir(ROOT)

    srv = None
    base = "https://jayanthkatta.com"
    if not args.live:
        srv, port = serve()
        base = "http://127.0.0.1:%d" % port

    from playwright.sync_api import sync_playwright

    problems = []
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            for w, theme in [(w, t) for w in WIDTHS for t in THEMES]:
                rows = {}
                for p in PAGES:
                    ctx = b.new_context(viewport={"width": w, "height": 900})
                    # Set before any document runs, so the page's own
                    # pre-paint script reads it and no theme is applied late.
                    ctx.add_init_script(
                        "try{localStorage.setItem('theme','%s');}catch(e){}"
                        % theme)
                    pg = ctx.new_page()
                    pg.goto(base + p, wait_until="load", timeout=60000)
                    pg.wait_for_timeout(3000)
                    rows[p] = pg.evaluate(PROBE)
                    ctx.close()
                ref_page = PAGES[0]
                ref = rows[ref_page]
                before = len(problems)
                for p in PAGES[1:]:
                    compare(w, ref_page, ref, p, rows[p], problems)
                print("    %4dpx %-5s nav %.0fpx, mark %.0fpx, banner %s, "
                      "hero %s  -- %d difference(s)"
                      % (w, theme, ref["navH"] or 0,
                         (ref["markBox"] or {}).get("w", 0),
                         ("%.0fpx" % ref["bannerH"]) if ref["bannerH"] else "none",
                         "video" if ref["hasVideo"]
                         else ("yes" if ref["hasHero"] else "none"),
                         len(problems) - before))
            b.close()
    finally:
        if srv:
            srv.shutdown()

    print()
    if problems:
        print("  %d DIFFERENCE(S) between pages\n" % len(problems))
        for x in problems[:25]:
            print("  - %s" % x)
        if len(problems) > 25:
            print("  ... and %d more" % (len(problems) - 25))
        print("\n  Moving between tabs should not change the furniture.")
        return 1
    print("  The shell is identical on all %d pages, at %d widths, in %d "
          "themes." % (len(PAGES), len(WIDTHS), len(THEMES)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
