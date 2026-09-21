#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pull-to-refresh works in the installed app, and does not exist outside it.

    python scripts/check_pull_refresh.py
    python scripts/check_pull_refresh.py --live

Why this exists
---------------
Reported after adding the site to an iPhone home screen: inside Safari you can
pull down to reload, and the installed app cannot be refreshed at all. That is
the manifest doing its job -- "display": "standalone" removes the address bar,
the reload button, and the pull gesture with them.

The service worker does reload a changed page, but only before you have
touched anything and only within ten seconds of load, so that it can never
yank the page out from under a reader:

    if (touched) return;
    if (performance.now() > 10000) return;

Open the app, scroll once, and nothing will refresh it again.

This checks the two halves that matter, and the second is the one that
protects what already works:

    in standalone   a pull from the top past the threshold reloads
    in a tab        the indicator is never created, so Safari's own pull
                    gesture is the only one and they cannot fight

display-mode is emulated through CDP rather than assumed, and the gesture is
driven with real touch events rather than by calling the handler directly --
"the function runs" and "a thumb on a phone reaches it" are different claims,
and only the second is the one being made.
"""
import argparse
import http.server
import os
import socketserver
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = [("portfolio", "/"), ("blog", "/blog/"), ("hub", "/intelligence/"),
         ("whats-new", "/intelligence/whats-new/"),
         ("status", "/intelligence/status/")]

# Drives the gesture the way a thumb does: down from the top, in steps, then
# release. Returns what the page did about it.
PULL = """(dist) => new Promise(function (resolve) {
  var fire = function (type, y) {
    var touch = new Touch({identifier: 1, target: document.body,
                           clientX: 100, clientY: y,
                           pageX: 100, pageY: y});
    var empty = (type === 'touchend');
    document.dispatchEvent(new TouchEvent(type, {
      touches: empty ? [] : [touch],
      changedTouches: [touch],
      targetTouches: empty ? [] : [touch],
      bubbles: true, cancelable: true}));
  };
  window.scrollTo(0, 0);
  fire('touchstart', 40);
  var y = 40;
  var iv = setInterval(function () {
    y += 20;
    fire('touchmove', y);
    if (y - 40 >= dist) {
      clearInterval(iv);
      var el = document.querySelector('.jk-ptr');
      var state = {
        exists: !!el,
        ready: !!(el && el.classList.contains('is-ready')),
        moved: el ? el.style.transform : '',
        opacity: el ? el.style.opacity : ''
      };
      state.hard = !!(el && el.classList.contains('is-hard'));
      fire('touchend', y);
      setTimeout(function () {
        state.firing = !!document.querySelector('.jk-ptr.is-firing');
        resolve(state);
      }, 60);
    }
  }, 16);
})"""


class _Threaded(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def serve():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    for port in range(9611, 9660):
        try:
            srv = _Threaded(("127.0.0.1", port), H)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            return srv, port
        except OSError:
            continue
    raise SystemExit("no free port")


# Tell the page it is an installed app, before any of its scripts run.
#
# The first version of this used CDP Emulation.setEmulatedMedia with a
# display-mode feature, which Chromium accepts without complaint and then
# ignores -- measured:
#
#     matchMedia('(display-mode: standalone)').matches  ->  false
#
# so the check reported the gesture missing on all five pages when it was
# simply never told to attach. An emulation that silently does nothing is the
# same class of fault as a check that measures the wrong property.
#
# navigator.standalone is what iOS actually sets, and it is the signal
# site-footer.js reads first for exactly that reason, so overriding it here
# exercises the real path rather than a parallel one. It has to be an init
# script: it must be defined before the page's own scripts decide.
STANDALONE = """Object.defineProperty(window.navigator, 'standalone',
    {get: function () { return true; }, configurable: true});"""


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

            print("  installed app -- the gesture must work")
            for name, path in PAGES:
                ctx = b.new_context(**pw.devices["iPhone 13"])
                ctx.add_init_script(STANDALONE)
                pg = ctx.new_page()
                pg.goto(base + path, wait_until="load", timeout=90000)
                pg.wait_for_timeout(2200)
                # Stamp the document and see whether the stamp survives.
                #
                # This used to compare pg.url before and after, and reported
                # /blog/ as never reloading. /blog/ reloads perfectly well:
                # the pull adds a ?r=<timestamp> cache-buster, and blog.js
                # then rewrites the URL from its own filter state on load,
                # which strips it. Same URL, so the instrument saw nothing --
                # while the reader got exactly what they pulled for.
                #
                # A reload wipes the window, so a property set on it is a
                # direct measurement of the thing being asserted, and it does
                # not care what any page does to its own address bar.
                pg.evaluate("window.__pullStamp = 'before'")
                before = pg.url
                r = pg.evaluate(PULL, 110)
                pg.wait_for_timeout(1200)
                after = pg.url
                try:
                    survived = pg.evaluate("window.__pullStamp === 'before'")
                except Exception:                             # noqa: BLE001
                    survived = False    # navigating away is a reload too
                ctx.close()

                if not r["exists"]:
                    problems.append("%s: no pull indicator in the installed "
                                    "app -- the gesture is not attached" % name)
                    print("     FAIL %-11s no indicator" % name)
                elif not r["ready"]:
                    problems.append("%s: pulled past the threshold and the "
                                    "indicator never armed (%s)"
                                    % (name, r["moved"] or "no transform"))
                    print("     FAIL %-11s never armed" % name)
                elif survived:
                    problems.append("%s: released past the threshold and the "
                                    "page did not reload (url %s -> %s)"
                                    % (name, before, after))
                    print("     FAIL %-11s no reload" % name)
                else:
                    print("     ok   %-11s armed, released, reloaded" % name)

            print("  a browser tab -- it must not exist at all")
            for name, path in PAGES:
                ctx = b.new_context(**pw.devices["iPhone 13"])
                pg = ctx.new_page()
                pg.goto(base + path, wait_until="load", timeout=90000)
                pg.wait_for_timeout(2200)
                exists = pg.evaluate(
                    "() => !!document.querySelector('.jk-ptr')")
                ctx.close()
                if exists:
                    problems.append(
                        "%s: the pull indicator exists in an ordinary tab, "
                        "where Safari has its own pull gesture -- two of them "
                        "fighting is worse than either" % name)
                    print("     FAIL %-11s indicator present in a tab" % name)
                else:
                    print("     ok   %-11s absent, as it should be" % name)

            # Ordinary scrolling must not be swallowed.
            #
            # The gesture calls preventDefault on touchmove, and that is the
            # one thing here that could break the whole site: preventDefault
            # in the wrong branch stops the page scrolling at all. It is
            # guarded by "only at scrollY 0, only moving downward", so this
            # asserts the guard directly -- dispatch a cancelable touchmove
            # going UP and require that nobody cancelled it.
            #
            # Asserted on defaultPrevented rather than by watching the page
            # move, because synthetic touch events are untrusted and do not
            # scroll Chromium at all. Measuring whether the page moved would
            # measure the harness, not the site.
            print("  ordinary scrolling must not be swallowed")
            ctx = b.new_context(**pw.devices["iPhone 13"])
            ctx.add_init_script(STANDALONE)
            pg = ctx.new_page()
            pg.goto(base + "/blog/", wait_until="load", timeout=90000)
            pg.wait_for_timeout(2200)
            swallowed = pg.evaluate("""() => {
              var mk = function (y) {
                var t = new Touch({identifier: 2, target: document.body,
                                   clientX: 100, clientY: y,
                                   pageX: 100, pageY: y});
                return t;
              };
              var out = {};
              // a finger moving UP from the top: this is a scroll down
              document.dispatchEvent(new TouchEvent('touchstart', {
                touches: [mk(400)], changedTouches: [mk(400)],
                targetTouches: [mk(400)], bubbles: true, cancelable: true}));
              var ev = new TouchEvent('touchmove', {
                touches: [mk(300)], changedTouches: [mk(300)],
                targetTouches: [mk(300)], bubbles: true, cancelable: true});
              document.dispatchEvent(ev);
              out.upwardCancelled = ev.defaultPrevented;
              document.dispatchEvent(new TouchEvent('touchend', {
                touches: [], changedTouches: [mk(300)], targetTouches: [],
                bubbles: true, cancelable: true}));
              // and a finger moving down while already scrolled: also a scroll
              window.scrollTo(0, 500);
              document.dispatchEvent(new TouchEvent('touchstart', {
                touches: [mk(200)], changedTouches: [mk(200)],
                targetTouches: [mk(200)], bubbles: true, cancelable: true}));
              var ev2 = new TouchEvent('touchmove', {
                touches: [mk(320)], changedTouches: [mk(320)],
                targetTouches: [mk(320)], bubbles: true, cancelable: true});
              document.dispatchEvent(ev2);
              out.midPageCancelled = ev2.defaultPrevented;
              window.scrollTo(0, 0);
              return out;
            }""")
            ctx.close()
            if swallowed.get("upwardCancelled"):
                problems.append("a finger moving UP was cancelled -- that is "
                                "a scroll down, and the page would not move")
                print("     FAIL upward swipe cancelled")
            elif swallowed.get("midPageCancelled"):
                problems.append("a downward finger PART WAY DOWN the page was "
                                "cancelled -- scrolling back up would stick")
                print("     FAIL mid-page downward swipe cancelled")
            else:
                print("     ok   both scroll directions left alone")

            # The long pull: same gesture, carried much further, clears
            # every cache and unregisters the worker before reloading.
            #
            # Checked by putting something in a cache first and requiring it
            # to be gone afterwards. Asserting that the classes changed would
            # only prove the indicator changed colour; the promise being made
            # here is that the app's stored copy is actually discarded.
            print("  the long pull must clear the caches")
            ctx = b.new_context(**pw.devices["iPhone 13"])
            ctx.add_init_script(STANDALONE)
            pg = ctx.new_page()
            pg.goto(base + "/blog/", wait_until="load", timeout=90000)
            pg.wait_for_timeout(2500)
            seeded = pg.evaluate("""() => caches.open('jk-probe')
                .then(function (c) { return c.put('/probe-marker',
                    new Response('x')); })
                .then(function () { return caches.keys(); })""")
            short_state = pg.evaluate(PULL, 110)
            pg.wait_for_timeout(1500)
            after_short = pg.evaluate("() => caches.keys()")
            long_state = pg.evaluate(PULL, 240)
            pg.wait_for_timeout(2500)
            after_long = pg.evaluate("() => caches.keys()")
            ctx.close()

            if "jk-probe" not in (seeded or []):
                print("     ??   could not seed a cache; skipping")
            elif short_state.get("hard"):
                problems.append("a 110px pull armed the FULL CLEAR -- the "
                                "everyday refresh would be wiping the app's "
                                "cache every time")
                print("     FAIL short pull armed the hard clear")
            elif "jk-probe" not in (after_short or []):
                problems.append("an ordinary pull emptied the caches -- it is "
                                "meant to reload, not to wipe")
                print("     FAIL short pull cleared the caches")
            elif not long_state.get("hard"):
                problems.append("a 240px pull did not arm the full clear")
                print("     FAIL long pull never armed")
            elif "jk-probe" in (after_long or []):
                problems.append("the long pull armed and the caches survived "
                                "-- the one thing it exists to do did not "
                                "happen")
                print("     FAIL long pull left the caches in place")
            else:
                print("     ok   short pull keeps them, long pull clears them")

            # Android must be left to Chrome.
            #
            # Chrome KEEPS its own pull-to-refresh in an installed PWA; only
            # iOS takes the gesture away. An earlier version matched
            # (display-mode: standalone) as well, which would have layered a
            # second gesture over a working one -- the same fault as attaching
            # in a browser tab, but harder to spot, because the symptom is a
            # pull that feels slightly wrong rather than one that is missing.
            print("  an installed Android app must keep Chrome's own gesture")
            ctx = b.new_context(**pw.devices["Pixel 7"])
            ctx.add_init_script(
                "window.matchMedia = (function (real) {"
                "  return function (q) {"
                "    if (q && q.indexOf('display-mode: standalone') !== -1) {"
                "      return {matches: true, media: q,"
                "              addListener: function () {},"
                "              removeListener: function () {},"
                "              addEventListener: function () {},"
                "              removeEventListener: function () {}};"
                "    }"
                "    return real(q);"
                "  };"
                "})(window.matchMedia.bind(window));")
            pg = ctx.new_page()
            pg.goto(base + "/blog/", wait_until="load", timeout=90000)
            pg.wait_for_timeout(2200)
            android = pg.evaluate(
                "() => ({ptr: !!document.querySelector('.jk-ptr'),"
                " standalone: window.matchMedia("
                "'(display-mode: standalone)').matches})")
            ctx.close()
            if not android["standalone"]:
                print("     ??   could not emulate an installed app; skipping")
            elif android["ptr"]:
                problems.append(
                    "the pull indicator attached on an installed ANDROID app, "
                    "where Chrome already provides the gesture -- two of them "
                    "over one thumb")
                print("     FAIL attached on Android")
            else:
                print("     ok   absent on Android, as it should be")

            # A short pull is an ordinary scroll and must be left alone.
            print("  a short pull must do nothing")
            ctx = b.new_context(**pw.devices["iPhone 13"])
            ctx.add_init_script(STANDALONE)
            pg = ctx.new_page()
            pg.goto(base + "/blog/", wait_until="load", timeout=90000)
            pg.wait_for_timeout(2200)
            before = pg.url
            r = pg.evaluate(PULL, 30)
            pg.wait_for_timeout(900)
            if pg.url != before:
                problems.append("a 30px pull reloaded the page -- the "
                                "threshold is not holding, and every careless "
                                "thumb will trigger it")
                print("     FAIL reloaded on a 30px pull")
            elif r["ready"]:
                problems.append("a 30px pull armed the indicator")
                print("     FAIL armed on a 30px pull")
            else:
                print("     ok   30px pull ignored")
            ctx.close()
            b.close()
    finally:
        if srv:
            srv.shutdown()

    print()
    if problems:
        print("  %d PROBLEM(S)\n" % len(problems))
        for x in problems[:10]:
            print("  - %s" % x)
        print()
        print("  The installed app has no reload button. If this does not")
        print("  work there is no way to refresh it at all.")
        return 1
    print("  Pull-to-refresh works on %d pages in the installed app, and is "
          "absent in a tab." % len(PAGES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
