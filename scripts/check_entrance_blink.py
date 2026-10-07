#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""No page assembles itself in front of the reader.

    python scripts/check_entrance_blink.py
    python scripts/check_entrance_blink.py --page /intelligence/whats-new/

An entrance animation is one that runs a fixed number of times and starts its
element invisible or displaced. On a refresh the reader watches the page put
itself together, which is what gets reported as "the header is blinking".

Reported from a phone three times before this check existed, each time about a
different page and each time fixed in isolation:

  * the re:Invent countdown, which was `hidden` until JS measured it and so
    appeared 250ms in, 144px tall, shoving the page down;
  * the creed letters on /connect/, animating colour on a loop;
  * the header on /intelligence/whats-new/ -- a staggered .rise on the
    heading, the count, the lede and the lede links, with delays to .31s on
    top of a .7s animation, plus a one-shot gradient sweep over the eyebrow
    and a count-up that ran the headline figure from 55% of itself to its
    real value over 1.1s. Nothing settled for a full second.

/intelligence/status/ was the page the reader named as the one that does NOT
blink, and the reason is simply that it never had any of this: its header is
final in the HTML. That is the standard this check holds every page to.

What is allowed, and why the distinction matters
------------------------------------------------
A CONTINUOUS animation is fine. The pulsing dot beside "Cloud status" runs
forever, so a refresh reveals nothing about it -- you are always arriving in
the middle. The same goes for the service-name cycles on /connect/, which run
on 27s and 142s loops.

So the rule is not "no animation". It is "nothing finite that starts from
invisible or displaced", and the two are told apart by iteration count rather
than by name -- a check keyed to class names would have found `.rise` on two
pages and missed `eyebrowSweep` sitting three lines above it.

Why getAnimations() rather than reading the CSS
-----------------------------------------------
An earlier version of this probe read computed style and filtered on
animation-fill-mode, looking for `forwards`. /connect/ used `backwards` -- the
element is transparent through the delay and settles to its own style
afterwards, which is a fade-in by any reader's definition -- and the probe
called the page clean. getAnimations() hands back the actual keyframes the
browser resolved, so the question "does this start from opacity 0" is asked of
the animation itself instead of inferred from CSS semantics.

Why this is not check_page_settle.py
------------------------------------
That check asks a different question and they are easy to confuse. It measures
vertical DISPLACEMENT -- did the page shove its own content down -- against a
50px budget, and it is the right tool for furniture arriving late.

It was running on /intelligence/whats-new/ the whole time this page was
blinking, and passed, correctly. The .rise animation displaced its elements by
14px, well inside a budget whose reason for existing is a blog that once moved
666px. The rest of the effect was opacity, which that check does not look at
at all: an element fading 0 -> 1 in place displaces nothing.

So: settle watches the page's SHAPE, this watches its VISIBILITY. Neither
subsumes the other, and the 14px gap between them is where three reader
reports landed.

Only the first viewport is judged. Something that animates in when scrolled to
is a different effect with a different intent, and is not what a refresh
reveals.
"""
import argparse
import http.server
import json
import os
import socketserver
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The same nine the shell check holds to one standard, plus the pages that
# carry hand-written entrance effects. /connect/ is on the list because it is
# where the second blink report came from.
PAGES = ["/", "/blog/", "/connect/", "/resume.html", "/now.html",
         "/intelligence/", "/intelligence/whats-new/",
         "/intelligence/whats-new/sources/", "/intelligence/status/",
         "/intelligence/events/", "/intelligence/ai/", "/intelligence/clouds/",
         "/reinvent-2026/", "/reinvent-2026/plan/", "/reinvent-2026/planner/",
         "/how-this-was-made/"]

WIDTH, HEIGHT = 390, 780          # a phone, which is where it was reported

PROBE = r"""() => {
  const out = [];
  const fold = window.innerHeight;
  document.querySelectorAll('body *').forEach(el => {
    let anims = [];
    try { anims = el.getAnimations(); } catch (e) { return; }
    anims.forEach(a => {
      let t, kf;
      try { t = a.effect.getTiming(); kf = a.effect.getKeyframes(); }
      catch (e) { return; }
      // Continuous. A refresh reveals nothing you would not see anyway.
      if (t.iterations === Infinity || t.iterations === null) return;
      if (!t.duration) return;
      const starts_hidden = kf.some(k =>
        (k.opacity !== undefined && parseFloat(k.opacity) < 0.99) ||
        (k.transform && k.transform !== 'none' && k.transform !== ''));
      if (!starts_hidden) return;
      const b = el.getBoundingClientRect();
      if (b.top > fold) return;        // not what a refresh shows
      out.push({
        tag: el.tagName.toLowerCase(),
        cls: (typeof el.className === 'string' ? el.className : '').slice(0, 40),
        anim: a.animationName || '(script)',
        delay: Math.round(t.delay || 0),
        dur: Math.round(t.duration || 0),
        top: Math.round(b.top)
      });
    });
  });
  return out;
}"""


def serve(port):
    os.chdir(ROOT)
    h = http.server.SimpleHTTPRequestHandler
    h.log_message = lambda *a, **k: None
    httpd = socketserver.TCPServer(("127.0.0.1", port), h)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def canary(page):
    """Prove the probe can still see an entrance animation.

    Runs on every invocation. A check that cannot fail is worse than no check
    -- and this one is a browser probe against a moving target, so "found
    nothing" and "stopped working" look identical from the outside.
    """
    page.set_content("""<!doctype html><html><body>
      <style>
        @keyframes canaryIn{from{opacity:0;transform:translateY(14px)}
                            to{opacity:1;transform:none}}
        .ghost{animation:canaryIn .7s ease .3s forwards}
        /* Must NOT be reported: continuous, so a refresh reveals nothing. */
        @keyframes canaryPulse{50%{opacity:.4}}
        .pulse{animation:canaryPulse 2s infinite}
      </style>
      <p class="ghost">arrives</p><p class="pulse">always pulsing</p>
      </body></html>""")
    page.wait_for_timeout(60)
    hits = page.evaluate(PROBE)
    names = {h["anim"] for h in hits}
    if "canaryIn" not in names:
        return "CANARY FAILED: the probe no longer sees a plain fade-in entrance"
    if "canaryPulse" in names:
        return "CANARY FAILED: the probe reports an infinite pulse as an entrance"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", action="append", dest="pages")
    ap.add_argument("--port", type=int, default=8931)
    args = ap.parse_args()
    pages = args.pages or PAGES

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  playwright not installed -- skipping")
        return 0

    httpd = serve(args.port)
    base = "http://127.0.0.1:%d" % args.port
    problems, checked = [], 0
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch()
            pg = br.new_page(viewport={"width": WIDTH, "height": HEIGHT})

            bad = canary(pg)
            if bad:
                print("  " + bad)
                br.close()
                return 1
            print("  canary: a fade-in is seen, an infinite pulse is not")

            for path in pages:
                pg.goto(base + path, wait_until="domcontentloaded")
                # Long enough for a delayed entrance to have been created,
                # short enough that a .7s one has not finished and been
                # discarded by the browser.
                pg.wait_for_timeout(150)
                hits = pg.evaluate(PROBE)
                checked += 1
                if not hits:
                    continue
                seen = set()
                for h in hits:
                    k = (h["anim"], h["cls"])
                    if k in seen:
                        continue
                    seen.add(k)
                    problems.append((path, h))
            br.close()
    finally:
        httpd.shutdown()

    print("  %d page(s) checked at %dpx" % (checked, WIDTH))
    if not problems:
        print("\n  Nothing on any page assembles itself after first paint.")
        return 0

    print("\n  %d ENTRANCE ANIMATION(S) above the fold\n" % len(problems))
    for path, h in problems:
        print("  - %-32s %s.%s" % (path, h["tag"], h["cls"] or "(no class)"))
        print("      %s, %dms delay + %dms, %dpx from the top"
              % (h["anim"], h["delay"], h["dur"], h["top"]))
    print("\n  A reader refreshing watches these arrive. /intelligence/status/")
    print("  is the reference: its header is final in the HTML. Either make")
    print("  the animation continuous, or let the element ship finished.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
