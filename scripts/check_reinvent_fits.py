#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The re:Invent page fits the phone it will be read on.

    python scripts/check_reinvent_fits.py

Why this exists
---------------
Reported from an Android phone, with a photograph: body text cut off
mid-word -- "Circle siz...", "currently matc..." -- and every paragraph
rendered enormous.

Both symptoms had one cause. The document was 462px wide inside a 390px
viewport, and Chrome responds to a page wider than its viewport by turning
on font boosting, which inflates text in some blocks and not others. So a
72px overflow presented as a typography bug, which is the wrong place to
look.

Two things were doing it, and both had passed every existing check:

    .viewtabs   six tab pills in a flex row with no wrap, 449px at 390
    table.mx    the travel cost table, six nowrap columns, 433px

The second one matters more than it looks. With the row pushed out of the
viewport, "Just announced" could not be TAPPED -- Playwright timed out
trying, with the neighbouring elements intercepting the pointer. A whole
view was unreachable on the device most likely to be used at the event,
and nothing reported it.

So this asserts the two things a reader would notice:

  1. THE PAGE FITS.  scrollWidth never exceeds clientWidth, on every view,
     with the disclosure panels open -- which is how it was being read.
     Any offender is named with its width, because "the page overflows" is
     not actionable and ".viewtabs is 449px" is.

  2. EVERY CONTROL CAN BE TAPPED.  Each tab is hit-tested at its own
     centre point: the element at those coordinates has to be the tab, or
     inside it. An off-screen control is still in the DOM, still visible
     to a selector, and still impossible to press, which is exactly how
     this shipped.

Checked at 390 and at 360, because the narrower one is a common Android
width and is where a row that merely just fits stops fitting.
"""
import io
import os
import subprocess
import sys
import threading
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIDTHS = (390, 360)
TABS = ("browse", "plan", "map", "now", "team", "news", "plan2")

OVERFLOW_JS = """
() => {
  const vw = document.documentElement.clientWidth;
  const worst = [];
  document.querySelectorAll('*').forEach(el => {
    const r = el.getBoundingClientRect();
    if (!r.width && !r.height) return;
    const st = getComputedStyle(el);
    if (st.display === 'none' || st.visibility === 'hidden') return;
    // An element inside something that scrolls its own overflow is doing
    // the right thing. Walk the whole chain, not just the parent: the
    // cost table's rows sit two levels below its scroll box and were
    // being reported as overflow.
    let anc = el.parentElement, scrolls = false;
    while (anc && anc !== document.body) {
      const ox = getComputedStyle(anc).overflowX;
      if (ox === 'auto' || ox === 'scroll') { scrolls = true; break; }
      anc = anc.parentElement;
    }
    if (scrolls) return;
    if (r.right > vw + 1) {
      const cls = (el.className && el.className.baseVal !== undefined
                   ? el.className.baseVal : el.className || '').toString();
      worst.push({ sel: el.tagName.toLowerCase()
                        + (el.id ? '#' + el.id : '')
                        + (cls ? '.' + cls.trim().split(/\\s+/)[0] : ''),
                   w: Math.round(r.width), right: Math.round(r.right) });
    }
  });
  worst.sort((a, b) => b.right - a.right);
  return { vw, docW: document.documentElement.scrollWidth,
           worst: worst.slice(0, 6) };
}
"""

# A <select> with nothing in it but a placeholder, still enabled. The map's
# day picker was exactly this whenever the plan was empty: it looked like a
# working control, opened to one dead entry, and explained nothing. Asked
# about directly -- "so why it shows no days selected" -- which is the right
# question and one the page should have answered itself.
DEAD_CONTROL_JS = """
() => {
  const out = [];
  document.querySelectorAll('select').forEach(sel => {
    if (sel.disabled || !sel.offsetParent) return;
    const real = Array.from(sel.options).filter(o => o.value !== '');
    if (real.length === 0) {
      out.push({ sel: 'select#' + (sel.id || '?'),
                 why: 'no selectable option' });
    }
  });
  document.querySelectorAll('button').forEach(b => {
    if (b.disabled || !b.offsetParent) return;
    if (!(b.textContent || '').trim() && !b.getAttribute('aria-label'))
      out.push({ sel: 'button#' + (b.id || '?'), why: 'no label at all' });
  });
  return out;
}
"""

TAPPABLE_JS = """
(id) => {
  const el = document.getElementById(id);
  if (!el) return { ok: false, why: 'not in the DOM' };
  const r = el.getBoundingClientRect();
  if (!r.width || !r.height) return { ok: false, why: 'has no box' };
  const x = r.left + r.width / 2, y = r.top + r.height / 2;
  const vw = document.documentElement.clientWidth;
  const vh = document.documentElement.clientHeight;
  if (x < 0 || x > vw) return { ok: false,
    why: 'its centre is at x=' + Math.round(x) + ', outside a ' + vw
         + 'px viewport' };
  if (y < 0 || y > vh) return { ok: true, why: 'below the fold, scrollable' };
  const hit = document.elementFromPoint(x, y);
  if (!hit) return { ok: false, why: 'nothing is at its centre point' };
  if (hit === el || el.contains(hit)) return { ok: true };
  return { ok: false,
           why: 'covered by ' + hit.tagName.toLowerCase()
                + (hit.id ? '#' + hit.id : '') };
}
"""


def serve(port):
    """A real HTTP server. file:// makes absolute-path assets 404, and a
    check that measures a page whose stylesheet never loaded measures
    nothing -- that already produced three imaginary failures once."""
    import http.server
    import functools

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    handler = functools.partial(Quiet, directory=ROOT)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  playwright is not installed; skipping")
        return 0

    page_path = os.path.join(ROOT, "reinvent-2026", "index.html")
    if not os.path.exists(page_path):
        print("  reinvent-2026/index.html does not exist -- nothing to check")
        return 1

    port = 8771
    httpd = serve(port)
    time.sleep(0.4)
    problems = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for width in WIDTHS:
                page = browser.new_page(
                    viewport={"width": width, "height": 844},
                    device_scale_factor=2, is_mobile=True, has_touch=True)
                page.goto("http://127.0.0.1:%d/reinvent-2026/" % port,
                          wait_until="networkidle")
                page.wait_for_selector(".card", state="attached",
                                       timeout=30000)

                for tab in TABS:
                    page.evaluate(
                        "(t) => document.getElementById('tab-' + t).click()",
                        tab)
                    page.wait_for_timeout(350)
                    page.eval_on_selector_all(
                        "details", "ds => ds.forEach(d => d.open = true)")
                    page.wait_for_timeout(250)

                    r = page.evaluate(OVERFLOW_JS)
                    over = r["docW"] - r["vw"]
                    if over > 1:
                        names = ", ".join(
                            "%s (%dpx wide, reaching x=%d)"
                            % (w["sel"], w["w"], w["right"])
                            for w in r["worst"][:3]) or "no single element"
                        problems.append(
                            "at %dpx the %s view is %dpx wide, %dpx past the "
                            "viewport. Widest: %s"
                            % (width, tab, r["docW"], over, names))

                    dead = page.evaluate(DEAD_CONTROL_JS)
                    for d in dead:
                        problems.append(
                            "at %dpx, in the %s view, %s is enabled and "
                            "offers %s -- a control that looks operable and "
                            "does nothing, with no reason given"
                            % (width, tab, d["sel"], d["why"]))

                    for t in TABS:
                        got = page.evaluate(TAPPABLE_JS, "tab-" + t)
                        if not got.get("ok"):
                            problems.append(
                                "at %dpx, with the %s view open, the %s tab "
                                "cannot be tapped: %s"
                                % (width, tab, t, got.get("why")))
                print("  %dpx: %d view(s) checked, every tab hit-tested"
                      % (width, len(TABS)))
                page.close()
            browser.close()
    finally:
        httpd.shutdown()

    print()
    if problems:
        seen, unique = set(), []
        for p_ in problems:
            if p_ not in seen:
                seen.add(p_)
                unique.append(p_)
        print("  %d PROBLEM(S)" % len(unique))
        print()
        for p_ in unique[:12]:
            print("  - %s" % p_)
        print()
        print("  A page wider than the phone does not look like a width bug.")
        print("  Chrome turns on font boosting, the text comes out enormous")
        print("  and clipped, and whatever got pushed out stops being")
        print("  tappable while still looking present to every selector.")
        return 1
    print("  Nothing overflows at 390 or 360, and every tab can be pressed")
    print("  in every view with the disclosure panels open.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
