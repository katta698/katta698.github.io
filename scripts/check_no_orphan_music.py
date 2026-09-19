#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The walkthrough's music never plays without the voice.

    python scripts/check_no_orphan_music.py
    python scripts/check_no_orphan_music.py --live

Why this exists
---------------
Reported four times, in the same words every time:

    "the voiceover stops, but the music in the background still continues"

and the fourth time: "I've been telling you multiple times. Can you fix it
for good?"

Each time I fixed the end of the track, which was the one place it was not
happening. The fault was structural, and it had three doors:

    voice.onerror      set voice = null and carried on with a timer
    play() rejected    the same silent timer, the same music
    a stall mid-track  no handler at all -- the narration clock stops, the
                       pictures freeze, and the bed, which is a smaller,
                       fully buffered file on loop, keeps playing

All three sound identical from the outside. None of them is the end of the
file, which is why four rounds of testing the ending found nothing.

The rule now is that the bed's volume is DERIVED from whether the narration
clock has moved in the last 1.2 seconds, checked four times a second -- so it
cannot outlive the voice for any reason, including reasons nobody has thought
of yet. This check exists to keep that true, and it tests the property rather
than the implementation: freeze the clock and see whether the music stops.

The frozen case is done with playbackRate = 0, deliberately. Pausing the
element fires events that the code listens for; playbackRate = 0 fires
nothing at all and simply stops the clock, which is the closest thing to a
phone stalling on a slow connection and the case that had no handler.

A note on the server
--------------------
This serves the site with Range support. SimpleHTTPRequestHandler ignores
Range entirely and answers 200 with the whole file, so a media element cannot
seek against it -- every local scrub test run against one measures the
pictures and nothing else. That gap is why an earlier fault looked fine here
and broke on a real phone.
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
PAGE = "/how-this-was-made/"

# How long the music may keep sounding after the voice stops. The player
# checks four times a second against a 1.2s threshold, so 2.5s is that plus
# the fade and a wide margin.
GRACE_S = 2.5

WRAP_AUDIO = """
window.__a = [];
const N = window.Audio;
window.Audio = function (s) { const a = new N(s); window.__a.push(a); return a; };
window.Audio.prototype = N.prototype;
"""

STATE = """
() => {
  const a = window.__a || [];
  const v = a.find(x => (x.src || '').indexOf('narration') >= 0);
  const b = a.find(x => (x.src || '').indexOf('mountains') >= 0);
  return {
    voice: v ? {t: +v.currentTime.toFixed(2), paused: v.paused} : null,
    music: b ? {vol: +b.volume.toFixed(3), paused: b.paused} : null
  };
}
"""

FREEZE = """
() => { const v = (window.__a || []).find(a => (a.src || '').indexOf('narration') >= 0);
        if (v) { v.playbackRate = 0; } }
"""

THAW = """
() => { const v = (window.__a || []).find(a => (a.src || '').indexOf('narration') >= 0);
        if (v) { v.playbackRate = 1; } }
"""


class _Threaded(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


class _Range(http.server.SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler with the one feature audio needs."""

    def log_message(self, *a):
        pass

    def send_head(self):
        rng = self.headers.get("Range")
        if not rng:
            return http.server.SimpleHTTPRequestHandler.send_head(self)
        path = self.translate_path(self.path)
        if not os.path.isfile(path):
            return http.server.SimpleHTTPRequestHandler.send_head(self)
        m = re.match(r"bytes=(\d*)-(\d*)", rng.strip())
        if not m:
            return http.server.SimpleHTTPRequestHandler.send_head(self)
        size = os.path.getsize(path)
        start = int(m.group(1)) if m.group(1) else 0
        end = int(m.group(2)) if m.group(2) else size - 1
        end = min(end, size - 1)
        length = max(0, end - start + 1)
        with open(path, "rb") as fh:
            fh.seek(start)
            data = fh.read(length)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
        self.send_header("Content-Length", str(length))
        self.end_headers()
        self.wfile.write(data)
        return None


def serve():
    for port in range(9840, 9880):
        try:
            srv = _Threaded(("127.0.0.1", port), _Range)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            return srv, port
        except OSError:
            continue
    raise SystemExit("no free port")


def sounding(music):
    return bool(music) and not music["paused"] and music["vol"] > 0.01


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
            br = pw.chromium.launch(
                args=["--autoplay-policy=no-user-gesture-required"])

            # ---- 1. the clock stops with no event fired at all -----------
            ctx = br.new_context(viewport={"width": 412, "height": 915},
                                 has_touch=True, is_mobile=True)
            ctx.add_init_script(WRAP_AUDIO)
            pg = ctx.new_page()
            pg.goto(base + PAGE, wait_until="load", timeout=90000)
            pg.wait_for_timeout(1500)
            pg.locator(".cf-player").scroll_into_view_if_needed()
            pg.locator(".cf-big").click()
            pg.wait_for_timeout(3000)

            st = pg.evaluate(STATE)
            if not sounding(st["music"]):
                problems.append(
                    "the music is not playing during normal playback, so this "
                    "check cannot prove anything about it stopping")
            print("  normal playback      music vol %.3f, voice at %.1fs"
                  % (st["music"]["vol"] if st["music"] else -1,
                     st["voice"]["t"] if st["voice"] else -1))

            pg.evaluate(FREEZE)
            pg.wait_for_timeout(int(GRACE_S * 1000))
            st = pg.evaluate(STATE)
            print("  narration clock frozen for %.1fs  ->  music vol %.3f %s"
                  % (GRACE_S, st["music"]["vol"] if st["music"] else -1,
                     "paused" if (st["music"] or {}).get("paused") else "PLAYING"))
            if sounding(st["music"]):
                problems.append(
                    "the narration clock stopped and %0.1fs later the music "
                    "was still sounding at %.3f. This is the report, in the "
                    "words it was made in: the voiceover stops and the music "
                    "carries on"
                    % (GRACE_S, st["music"]["vol"]))

            # ---- 2. and it comes back when the voice does ----------------
            pg.evaluate(THAW)
            pg.wait_for_timeout(2000)
            st = pg.evaluate(STATE)
            print("  clock resumes        music vol %.3f, voice at %.1fs"
                  % (st["music"]["vol"] if st["music"] else -1,
                     st["voice"]["t"] if st["voice"] else -1))
            if not sounding(st["music"]):
                problems.append(
                    "the narration resumed and the music did not come back "
                    "with it -- silencing it is only half the rule")
            ctx.close()

            # ---- 3. the voice can never play at all ---------------------
            ctx = br.new_context(viewport={"width": 412, "height": 915},
                                 has_touch=True, is_mobile=True)
            ctx.add_init_script(WRAP_AUDIO)
            ctx.route("**/narration.mp3*", lambda r: r.abort())
            pg = ctx.new_page()
            pg.goto(base + PAGE, wait_until="load", timeout=90000)
            pg.wait_for_timeout(1500)
            pg.locator(".cf-player").scroll_into_view_if_needed()
            pg.locator(".cf-big").click()
            pg.wait_for_timeout(int(GRACE_S * 1000) + 1500)
            st = pg.evaluate(STATE)
            print("  narration unreachable ->  music vol %.3f %s"
                  % (st["music"]["vol"] if st["music"] else -1,
                     "paused" if (st["music"] or {}).get("paused")
                     else ("PLAYING" if st["music"] else "never created")))
            if sounding(st["music"]):
                problems.append(
                    "the narration could not be fetched and the music played "
                    "anyway, at %.3f -- a walkthrough with a soundtrack and "
                    "no narrator" % st["music"]["vol"])
            ctx.close()
            br.close()
    finally:
        if srv:
            srv.shutdown()

    print()
    if problems:
        print("  %d PROBLEM(S)" % len(problems))
        print()
        for p in problems:
            print("  - %s" % p)
        print()
        print("  Music outliving the voice has been reported four times. It")
        print("  is never the end of the track -- it is a stall, an error or")
        print("  a refusal, and all three sound the same from the outside.")
        return 1
    print("  The music stops when the narration clock stops, comes back when")
    print("  it does, and never plays at all if the narration cannot.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
