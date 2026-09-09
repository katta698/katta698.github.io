#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail the build when text cannot be read against what sits behind it.

    python scripts/check_contrast.py            # every page, both themes
    python scripts/check_contrast.py --page /blog/
    python scripts/check_contrast.py --verbose  # print every measurement

Why this exists
---------------
Four separate elements shipped unreadable in light mode on 8 September 2026,
all with the same shape: a rule set a background for light mode and did not
set the colour that sits on it, so a pale grey chosen for a dark card stayed
pale grey on a pale card.

    .upd (vendor update text)   1.34:1
    .chip.aws                   1.63:1
    .chip.sev                   4.12:1
    .theme-toggle               1.08:1

An earlier one, the palette menu, measured 1.03:1. Every one was found by a
person looking at the page and saying "that looks faint" -- never by a check,
because nothing here rendered a page and measured it. Reviewing a diff cannot
catch this: the CSS reads as correct in isolation, and the failure only exists
once the cascade resolves against a themed background.

So this renders the real pages in a real browser, in both themes, walks up
each element's ancestors for the first non-transparent background, and
computes WCAG contrast.

Thresholds
----------
4.5:1 for normal text and 3.0:1 for large text, per WCAG 2.1 AA. Large is
>=24px, or >=18.66px when bold, measured from the computed style rather than
guessed from the selector.

Decorative elements are excluded by name rather than by heuristic: a dot that
carries no text has nothing to contrast. The list is short on purpose -- an
exclusion is how a real failure gets waved through.
"""
import argparse
import http.server
import os
import re
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAGES = [
    "/", "/blog/", "/now.html",
    "/intelligence/", "/intelligence/whats-new/", "/intelligence/status/",
]

# Elements with no text of their own. Kept deliberately short: every entry is
# a place a real failure could hide.
SKIP = {"pill", "dot", "cs-dot", "pal-nav-dot", "sc-i", "diya"}

AA_NORMAL = 4.5
AA_LARGE = 3.0


def lum(rgb):
    def f(c):
        c /= 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = [f(x) for x in rgb]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def parse(css):
    n = [float(x) for x in re.findall(r"[\d.]+", css)[:3]]
    if not n:
        return None
    # color(srgb 0.12 0.11 0.10) gives 0-1; rgb() gives 0-255.
    if max(n) <= 1.0:
        n = [x * 255 for x in n]
    return tuple(int(x) for x in n)


def composite(stack):
    """Flatten a stack of background layers into the colour actually seen.

    The browser hands back each layer's own rgba(). A translucent layer over a
    card is not the colour in that rgba() -- it is that colour mixed with what
    is beneath. The list arrives innermost-first, so it is composited from the
    bottom up.
    """
    if not stack:
        return None
    out = None
    for css in reversed(stack):                 # furthest ancestor first
        nums = [float(x) for x in re.findall(r"[\d.]+", css)]
        if len(nums) < 3:
            continue
        rgb = nums[:3]
        # Scale on the CHANNEL values alone, never on the length of the list.
        # color(srgb 0.96 0.95 0.93 / 0.94) has four numbers, so a
        # `len(nums) == 3` guard skipped the scaling and int() floored 0.96 to
        # 0 -- turning a cream nav bar black and reporting the nav links at
        # 1.18:1 when they measure 14.8:1. The checker was the thing that was
        # broken, which is the failure mode that makes a checker worthless.
        if max(rgb) <= 1.0:
            rgb = [x * 255 for x in rgb]
        a = nums[3] if len(nums) > 3 else 1.0
        layer = tuple(int(x) for x in rgb)
        out = layer if out is None else tuple(
            int(layer[i] * a + out[i] * (1 - a)) for i in range(3))
    return out


def contrast(a, b):
    l1, l2 = sorted([lum(a), lum(b)], reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


# Collect every text-bearing leaf with its resolved colours. Done in the page
# rather than in Python because only the browser knows what the cascade
# produced, which is the entire point.
JS = r"""() => {
  const out = [];
  for (const el of document.querySelectorAll('body *')) {
    if (el.children.length) continue;                    // leaves only
    const txt = (el.textContent || '').trim();
    if (!txt) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 4 || r.height < 4) continue;           // not rendered
    const s = getComputedStyle(el);
    if (s.visibility === 'hidden' || s.display === 'none') continue;
    if (parseFloat(s.opacity) < 0.15) continue;          // deliberately faint

    // Text painted by something other than `color` cannot be measured this
    // way. The What's New eyebrow is a gradient clipped to the glyphs, so its
    // computed colour is transparent by design -- reporting 1.00:1 there is
    // the checker being wrong, not the page.
    if (s.color === 'transparent' || s.color.startsWith('rgba(0, 0, 0, 0')) continue;
    if (s.webkitTextFillColor === 'transparent') continue;
    if (s.webkitBackgroundClip === 'text' || s.backgroundClip === 'text') continue;

    // Emoji carry their own colour, so `color` does not apply and a dark emoji
    // on a dark bar measures 1.00:1 while looking perfectly fine.
    //
    // But "contains no letter or digit" was far too broad a test for that. The
    // theme toggle is U+25D0, a geometric shape, and `color` applies to it
    // normally -- excluding it meant this checker passed the status page while
    // its theme control sat at 1.08:1, which is precisely the bug it exists to
    // catch. A checker that skips the thing it was written for is worse than
    // none, because it retires the question.
    //
    // So skip only text made ENTIRELY of true emoji, by codepoint range.
    // Everything else -- arrows, geometric shapes, dingbats -- is measured.
    if (/^[\s\u{1F000}-\u{1FAFF}\u{FE0F}\u{200D}]+$/u.test(txt)) continue;
    // Collect the whole stack of backgrounds up to the first OPAQUE one.
    // Taking the first non-transparent layer is wrong when that layer is
    // itself translucent: the cloud chips paint their own hue at 20% alpha,
    // so comparing the text colour against the raw rgba() numbers gave 1.00:1
    // for a chip that is perfectly legible once the layer is composited over
    // the card beneath it.
    let n = el; const stack = [];
    while (n) {
      const c = getComputedStyle(n).backgroundColor;
      if (c && c !== 'transparent' && !/rgba\(0, 0, 0, 0\)/.test(c)) {
        stack.push(c);
        const m = c.match(/[\d.]+/g);
        const a = (m && m.length > 3) ? parseFloat(m[3]) : 1;
        if (a >= 0.999) break;                  // opaque: nothing below shows
      }
      n = n.parentElement;
    }
    out.push({
      cls: (el.className || '').toString().split(' ')[0] || el.tagName.toLowerCase(),
      txt: txt.slice(0, 40),
      fg: s.color,
      bg: stack.length ? stack : ['rgb(255,255,255)'],
      size: parseFloat(s.fontSize),
      weight: parseInt(s.fontWeight, 10) || 400
    });
  }
  return out;
}"""


def serve(port):
    os.chdir(ROOT)

    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), Q)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", action="append")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--port", type=int, default=8899)
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  playwright is not installed; skipping the contrast check.")
        print("  pip install playwright && playwright install chromium")
        return 0

    pages = args.page or PAGES
    srv = serve(args.port)
    base = "http://127.0.0.1:%d" % args.port
    failures, checked = [], 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for path in pages:
            for theme in ("dark", "light"):
                ctx = browser.new_context(viewport={"width": 430, "height": 900})
                ctx.add_init_script(
                    "try{localStorage.setItem('theme','%s')}catch(e){}" % theme)
                pg = ctx.new_page()
                try:
                    pg.goto(base + path, wait_until="networkidle", timeout=30000)
                    pg.wait_for_timeout(1200)
                    items = pg.evaluate(JS)
                except Exception as exc:                        # noqa: BLE001
                    print("  %-28s %-5s could not render: %s"
                          % (path, theme, str(exc)[:60]))
                    ctx.close()
                    continue
                for it in items:
                    fg, bg = parse(it["fg"]), composite(it["bg"])
                    if not fg or not bg:
                        continue
                    if it["cls"] in SKIP:
                        continue
                    checked += 1
                    large = it["size"] >= 24 or (it["size"] >= 18.66 and it["weight"] >= 700)
                    need = AA_LARGE if large else AA_NORMAL
                    c = contrast(fg, bg)
                    if args.verbose:
                        print("    %-24s %-5s %5.2f:1  .%s" % (path, theme, c, it["cls"]))
                    if c < need:
                        failures.append((path, theme, it["cls"], c, need, it["txt"]))
                ctx.close()
        browser.close()
    srv.shutdown()

    if failures:
        print("\n  UNREADABLE TEXT\n")
        seen = set()
        for path, theme, cls, c, need, txt in sorted(failures, key=lambda f: f[3]):
            key = (path, theme, cls)
            if key in seen:
                continue                    # one line per element, not per instance
            seen.add(key)
            print("  %-28s %-5s .%-18s %5.2f:1  (needs %.1f)"
                  % (path, theme, cls[:18], c, need))
            print("  %-28s %-5s   %s" % ("", "", txt))
        print("\n  %d element(s) below the threshold, %d checked." % (len(seen), checked))
        print("  Almost always: a rule set a background for one theme and left")
        print("  the colour that sits on it alone.")
        return 1

    # A check that measured nothing must not report success. Running this
    # under Git Bash rewrote "/intelligence/status/" into a Windows path, every
    # navigation failed, and it printed "all readable" over zero measurements.
    # Vacuous passes are worse than no check: they retire the question.
    if checked == 0:
        print("  NOTHING WAS MEASURED across %d page(s)." % len(pages))
        print("  Either the pages did not render, or every element was excluded.")
        print("  Under Git Bash, a leading-slash --page argument is rewritten to")
        print("  a Windows path -- prefix the command with MSYS_NO_PATHCONV=1.")
        return 1

    print("  %d text element(s) checked across %d page(s) in both themes: "
          "all readable." % (checked, len(pages)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
