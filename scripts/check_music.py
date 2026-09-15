#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The music button actually plays something, on every page.

    python scripts/check_music.py
    python scripts/check_music.py --live

Why this exists
---------------
Reported as: "your music icon doesn't work. When I click it, it doesn't make
any sound." It had been broken on two of the five pages and nothing said so --
no error, no failed request, no console message. The button pressed, the glyph
changed, and the audio element sat there with no src and readyState 0.

The cause was position in the document. hero-media.js wires #beach-audio, and
that element is at the FOOT of every page. The script used to be loaded at the
foot too, so it always found it. Then the script was moved up beside the hero
<video> on the portfolio and the blog -- the video ships with no src and this
file sets it, and loading at the foot left the hero a flat rectangle until it
got there. The video got better and the audio silently stopped.

Live status kept working, because it still loads the file at the foot. Two
pages broken, three fine, no error anywhere: it looked like a per-page problem
rather than an ordering one, which is the most expensive way for a bug to look.

hero-media.js now waits for its element if it is not there yet, so it is safe
to load from anywhere in the document. This checks the property that actually
matters to a reader: press the button, and a second later the audio is playing
and its clock is moving.

Checking currentTime rather than just paused is deliberate. A media element
reports paused=false the instant play() is called, before it has any data --
the broken pages reported paused=false and made no sound. Only a clock that
has advanced proves audio is really running.
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

STATE = """() => {
  const a = document.getElementById('beach-audio');
  if (!a) return {missing: true};
  return {
    src: (a.getAttribute('src') || a.src || '').split('/').pop(),
    paused: a.paused,
    ready: a.readyState,
    time: +(a.currentTime || 0).toFixed(2),
    err: a.error ? a.error.code : null
  };
}"""


def serve():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    socketserver.TCPServer.allow_reuse_address = True
    for port in range(9301, 9351):
        try:
            srv = socketserver.TCPServer(("127.0.0.1", port), H)
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
            # Without this a headless browser refuses to start audio at all and
            # every page would look broken for a reason that is not the site's.
            b = pw.chromium.launch(
                args=["--autoplay-policy=no-user-gesture-required"])
            for p in PAGES:
                ctx = b.new_context(viewport={"width": 1440, "height": 900})
                pg = ctx.new_page()
                errors = []
                pg.on("pageerror", lambda e: errors.append(str(e)[:70]))
                pg.goto(base + p, wait_until="load", timeout=60000)
                pg.wait_for_timeout(2600)

                if pg.locator("#audio-toggle").count() == 0:
                    problems.append("%s: no music button on the page" % p)
                    ctx.close()
                    continue
                try:
                    pg.click("#audio-toggle", timeout=5000)
                except Exception as exc:                       # noqa: BLE001
                    problems.append("%s: the button could not be clicked (%s)"
                                    % (p, str(exc)[:50]))
                    ctx.close()
                    continue
                pg.wait_for_timeout(2500)
                s = pg.evaluate(STATE)
                ctx.close()

                if s.get("missing"):
                    problems.append("%s: no audio element to play" % p)
                    continue
                if not s["src"]:
                    problems.append(
                        "%s: the button was pressed and the audio element "
                        "still has no source -- nothing was ever wired to it, "
                        "and nothing reports that" % p)
                elif s["time"] <= 0:
                    problems.append(
                        "%s: source %s is set but the clock has not moved "
                        "after 2.5s (paused=%s, readyState=%s, error=%s)"
                        % (p, s["src"], s["paused"], s["ready"], s["err"]))
                print("    %-26s %-16s readyState %s, played %.1fs"
                      % (p, s["src"] or "NO SOURCE", s["ready"], s["time"]))
                if errors:
                    problems.append("%s: script error -- %s" % (p, errors[0]))
            b.close()
    finally:
        if srv:
            srv.shutdown()

    print()
    if problems:
        print("  %d PROBLEM(S)\n" % len(problems))
        for x in problems[:10]:
            print("  - %s" % x)
        print("\n  A button that presses, changes its glyph and makes no sound")
        print("  looks like it worked. Nothing else here reports it.")
        return 1
    print("  The music button plays on all %d pages." % len(PAGES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
