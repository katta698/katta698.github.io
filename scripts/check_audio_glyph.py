#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The music button is drawn once, and the sound carries between tabs.

    python scripts/check_audio_glyph.py
    python scripts/check_audio_glyph.py --live

Why this exists
---------------
Two faults reported together, both about the same control:

  "When I'm in portfolio, when I turn on music icon, the sound plays. But
   when I shift to blog, the sound stops... rest of the tabs work fine."

  "When I click on these tabs the music icon gonna flash. It goes back and
   forth with the speaker symbol and the music icon."

The sound. The <audio> element ships with no src; hero-media.js chooses the
track and sets it. Three pages load that file at the FOOT, after the element,
so the src is set during parsing. The blog loads it early, beside the hero
video, so it defers to DOMContentLoaded and sets the src after the resume has
already run. Measured at DOMContentLoaded:

    /intelligence/   src=/blog/assets/audio/boho-3.mp3
    /blog/           src=(none)

play() on an element with no source neither throws nor warns, and the src
assignment that follows resets the element and discards it. Silence, with the
button correctly showing not-playing and nothing in the console.

The glyph. It was painted three times per load -- the markup's hardcoded
violin, then the instrument for today, then the speaker if sound was on:

    243ms  the markup                 violin
    331ms  paintInstrument            guitar
    414ms  the resume, sound is on    speaker

Neither script was wrong; the glyph depends on today's date and on a choice
in localStorage, so a server cannot know it. The head script reads both
before the first frame -- it already reads the theme there -- and CSS draws
the glyph from what it leaves behind.

So this checks the two things a reader experiences: how many DIFFERENT glyphs
the button shows between navigation and settling (one, whatever it is), and
whether sound turned on at the portfolio is still playing after walking every
tab. It samples from commit, because both faults are finished within 500ms and
invisible to anything that waits for the page to settle first.
"""
import argparse
import http.server
import os
import random
import socketserver
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEAKER = "🔊"

PAGES = [("portfolio", "/"), ("blog", "/blog/"), ("hub", "/intelligence/"),
         ("whats-new", "/intelligence/whats-new/"),
         ("status", "/intelligence/status/")]

WATCH = """window.__v = [];
(function sample() {
  var b = document.getElementById('audio-toggle');
  if (b) {
    var g = getComputedStyle(b, '::before').content;
    if (!window.__v.length || window.__v[window.__v.length - 1] !== g) {
      window.__v.push(g);
    }
  }
  /* Keep looking until the button has actually been seen.
     On three of the five pages the button is built by script, so a fixed
     budget is a bet on how fast the machine is. Under the full preflight run
     this reported "no music button" on the portfolio and passed alone
     straight after -- the sampler had simply run out before the button
     arrived. The cap is now on TIME SPENT, not on samples collected. */
  if (window.__n === undefined) window.__n = 0;
  window.__n += 1;
  if (window.__n < 140) setTimeout(sample, 70);
})();"""

STATE = """() => {
  var a = document.getElementById('beach-audio');
  return {playing: a ? !a.paused : false,
          t: a ? +a.currentTime.toFixed(1) : 0};
}"""


# One connection at a time was the whole problem.
#
# socketserver.TCPServer is single-threaded: it serves one request, then the
# next. A browser opening a page wants the HTML, two stylesheets, three
# scripts and two font files, and it asks for them at once -- so they queued,
# and with six checks running in parallel they queued behind each other's
# queues too.
#
# That is why check_brand reported the wordmark at 114.8px (the fallback
# serif) instead of 96.6px (Playfair) only during a full run, and why
# check_bar_settle saw the portfolio's bar slide 18px only during a full run.
# Neither was a fault in the site. Both were this line.
#
# ThreadingTCPServer serves them concurrently. daemon_threads so a hung
# request cannot keep the process alive after the check is done.
class _Threaded(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def serve():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    socketserver.TCPServer.allow_reuse_address = True
    for port in range(9801, 9860):
        try:
            srv = _Threaded(("127.0.0.1", port), H)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            return srv, port
        except OSError:
            continue
    raise SystemExit("no free port")


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
            # Headless Chrome will not start audio without this, and every
            # page would look broken for a reason that is not the site's.
            b = pw.chromium.launch(
                args=["--autoplay-policy=no-user-gesture-required"])

            print("  the glyph is drawn once")
            for want in ("off", "on"):
                for name, path in PAGES:
                    ctx = b.new_context(viewport={"width": 1440, "height": 900})
                    ctx.add_init_script(
                        "try{localStorage.setItem('beachAudio','%s');}"
                        "catch(e){}" % want)
                    ctx.add_init_script(WATCH)
                    pg = ctx.new_page()
                    url = base + path
                    if args.live:
                        url += "?n=%d" % random.randint(1, 999999)
                    pg.goto(url, wait_until="commit", timeout=90000)
                    # Wait for the thing being measured to exist, rather than
                    # assuming three seconds is always enough for a script to
                    # build it.
                    try:
                        pg.wait_for_selector("#audio-toggle", state="attached",
                                             timeout=30000)
                    except Exception:                       # noqa: BLE001
                        pass
                    pg.wait_for_timeout(3000)
                    seq = pg.evaluate("() => window.__v")
                    # Read BEFORE closing the context, or the evaluate below
                    # runs against a dead page.
                    playing = pg.evaluate(STATE)["playing"]
                    ctx.close()
                    # The instrument must not churn, and the speaker must
                    # never appear unless the audio is really playing.
                    #
                    # An earlier version of this required exactly ONE glyph,
                    # which the pre-painted speaker satisfied -- it never
                    # flickered, it was simply wrong, showing sound-on on an
                    # iPhone that was silent. A check can be passed by the
                    # bug it was written to catch if it measures steadiness
                    # instead of truth.
                    quiet = [g for g in seq if SPEAKER not in g]
                    if not seq:
                        problems.append("%s (sound %s): no music button"
                                        % (name, want))
                    elif len(quiet) > 1:
                        problems.append(
                            "%s (sound %s): the instrument changes while "
                            "loading -- %s" % (name, want, " then ".join(quiet)))
                        print("     FAIL %-11s sound %-3s %s"
                              % (name, want, " -> ".join(seq)))
                    elif (SPEAKER in seq[-1]) != playing:
                        problems.append(
                            "%s (sound %s): the button shows %s while the "
                            "audio is %s -- the glyph is reporting what was "
                            "wanted, not what is happening"
                            % (name, want, seq[-1],
                               "playing" if playing else "silent"))
                        print("     FAIL %-11s sound %-3s %s, audio %s"
                              % (name, want, seq[-1],
                                 "playing" if playing else "silent"))
                    else:
                        print("     ok   %-11s sound %-3s %s (audio %s)"
                              % (name, want, seq[-1],
                                 "playing" if playing else "silent"))

            # A browser that will NOT autoplay, which is what a phone is.
            #
            # Everything above runs with autoplay permitted, so the resume
            # always succeeds and the speaker is always truthful. That is not
            # an iPhone. iOS refuses to start audio on a freshly loaded page,
            # and the fault reported -- a button showing the speaker on every
            # page while nothing played -- only exists in that case. A check
            # that grants itself permission the reader does not have cannot
            # see it.
            blocked = pw.chromium.launch()
            print("  and with autoplay refused, as on a phone")
            for name, path in PAGES:
                ctx = blocked.new_context(**pw.devices["iPhone 13"])
                ctx.add_init_script(
                    "try{localStorage.setItem('beachAudio','on');}catch(e){}")
                pg = ctx.new_page()
                url = base + path
                if args.live:
                    url += "?n=%d" % random.randint(1, 999999)
                pg.goto(url, wait_until="domcontentloaded", timeout=90000)
                pg.wait_for_timeout(3000)
                st = pg.evaluate(STATE)
                g = pg.evaluate("() => getComputedStyle("
                                "document.getElementById('audio-toggle'),"
                                "'::before').content")
                ctx.close()
                if SPEAKER in g and not st["playing"]:
                    problems.append(
                        "%s: the button shows the speaker while the audio is "
                        "silent -- it is reporting what the reader wanted, "
                        "not what the browser allowed" % name)
                    print("     FAIL %-11s says playing, is silent" % name)
                else:
                    print("     ok   %-11s %s, audio %s" % (
                        name, g, "playing" if st["playing"] else "silent"))
            blocked.close()

            print("  the sound carries between tabs")
            ctx = b.new_context(viewport={"width": 1440, "height": 900})
            pg = ctx.new_page()
            pg.goto(base + "/", wait_until="load", timeout=90000)
            pg.wait_for_timeout(2400)
            pg.click("#audio-toggle", timeout=8000)
            pg.wait_for_timeout(2200)
            if not pg.evaluate(STATE)["playing"]:
                problems.append("the portfolio would not start playing at all, "
                                "so the walk below proves nothing")
            for name, path in PAGES[1:] + [PAGES[0]]:
                pg.goto(base + path, wait_until="load", timeout=90000)
                pg.wait_for_timeout(3000)
                s = pg.evaluate(STATE)
                if not s["playing"] or s["t"] <= 0:
                    problems.append(
                        "%s: sound was on and this page is silent "
                        "(playing=%s, clock %.1fs)" % (name, s["playing"], s["t"]))
                    print("     FAIL %-11s silent" % name)
                else:
                    print("     ok   %-11s still playing, %.1fs" % (name, s["t"]))
            ctx.close()
            b.close()
    finally:
        if srv:
            srv.shutdown()

    print()
    if problems:
        print("  %d PROBLEM(S)\n" % len(problems))
        for x in problems[:12]:
            print("  - %s" % x)
        print("\n  A glyph repainted after the first frame is a flash, and")
        print("  play() on a source-less element fails without saying so.")
        return 1
    print("  One glyph per load on %d pages in both states, and the sound "
          "survives the whole walk." % len(PAGES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
