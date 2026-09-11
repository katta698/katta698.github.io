#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The region suggestions must work in Safari's engine as well as Chrome's.

    python scripts/check_region_suggest.py
    python scripts/check_region_suggest.py --live

Why this exists
---------------
The suggestions began as a native <datalist>, chosen because the browser's own
control is the one a phone keyboard and a screen reader already understand.
That reasoning only holds where the browser draws it, and two browsers did not:

    Chrome on Android   drew a popup over the site's own header
    Safari on iPad      drew nothing at all

Same page, same markup, all 248 suggestions present in the DOM and no way for
an iPad reader to see one. Neither was fixable, because a native control cannot
be positioned or styled. It was reported from an iPad, not caught here -- every
check ran in Chromium, which drew it correctly, so the whole class of fault was
invisible.

The list is now built by the page. So this runs in BOTH engines: Chromium for
Chrome and Edge, WebKit for Safari on the iPad and the iPhone. Testing one
engine is what let this through.

It checks the things a hand-built control has to do that a native one did for
free: open on typing, rank prefix matches first, move with the arrow keys,
commit on Enter, dismiss on Escape without discarding the text, carry the
combobox roles a screen reader needs, and stay clear of the header.
"""
import argparse
import http.server
import os
import socketserver
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = "/intelligence/status/"


def serve():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    socketserver.TCPServer.allow_reuse_address = True
    for port in range(8701, 8751):
        try:
            srv = socketserver.TCPServer(("127.0.0.1", port), H)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            return srv, port
        except OSError:
            continue
    raise SystemExit("no free port")


STATE = """() => {
  const u = document.getElementById('om-sug');
  const q = document.getElementById('om-q');
  const nav = document.querySelector('nav');
  const r = u.hidden ? null : u.getBoundingClientRect();
  return {
    open: !u.hidden,
    rows: [...u.children].map(li => (li.querySelector('.om-sug-v') || li).textContent.trim()),
    expanded: q.getAttribute('aria-expanded'),
    active: q.getAttribute('aria-activedescendant'),
    role: q.getAttribute('role'),
    listRole: u.getAttribute('role'),
    optionRoles: [...u.children].every(li => li.getAttribute('role') === 'option'),
    value: q.value,
    overNav: !!(r && nav && r.top < nav.getBoundingClientRect().bottom),
    found: (document.getElementById('om-found') || {}).textContent
  };
}"""


def run(engine, base, name):
    problems = []
    pg = engine.new_page(viewport={"width": 834, "height": 1112})
    pg.goto(base + PATH, wait_until="domcontentloaded", timeout=90000)
    pg.wait_for_timeout(3200)

    if not pg.query_selector("#om-sug"):
        return ["%s: the page has no suggestion list at all" % name]

    # Nothing typed: there must be no clear cross. It shipped visible over an
    # empty field, offering to clear nothing, because an author
    # `display: flex` beats the browser's own `[hidden] { display: none }` and
    # the hidden attribute quietly meant nothing.
    if pg.evaluate("""() => {
          const x = document.getElementById('om-clear');
          return !!x && getComputedStyle(x).display !== 'none';
        }"""):
        problems.append("%s: the clear cross shows on an empty field" % name)

    # It opens, and it ranks what was typed first.
    pg.click("#om-q")
    pg.type("#om-q", "mum", delay=40)
    pg.wait_for_timeout(400)
    s = pg.evaluate(STATE)
    if not s["open"]:
        problems.append("%s: typing 'mum' offered nothing" % name)
    elif not s["rows"] or "mumbai" not in s["rows"][0].lower():
        problems.append("%s: 'mum' ranked %r first, not Mumbai"
                        % (name, (s["rows"] or ["nothing"])[0]))
    x2 = pg.evaluate('''() => {
      const x = document.getElementById('om-clear');
      const i = document.getElementById('om-q');
      const a = x.getBoundingClientRect(), b = i.getBoundingClientRect();
      const s = getComputedStyle(x), sa = getComputedStyle(x, '::after');
      return { shown: s.display !== 'none',
               inside: a.right <= b.right - 1 && a.left >= b.left,
               hit: Math.round(Math.min(parseFloat(sa.width) || a.width,
                                        parseFloat(sa.height) || a.height)) };
    }''')
    if not x2["shown"]:
        problems.append("%s: typing showed no clear cross" % name)
    if not x2["inside"]:
        problems.append("%s: the clear cross sits outside the input's border" % name)
    if x2["hit"] < 40:
        problems.append("%s: the clear cross has only a %dpx target" % (name, x2["hit"]))

    if s["expanded"] != "true":
        problems.append("%s: aria-expanded is %r while the list is open"
                        % (name, s["expanded"]))
    if s["role"] != "combobox" or s["listRole"] != "listbox" or not s["optionRoles"]:
        problems.append("%s: the combobox/listbox/option roles are incomplete" % name)
    if s["overNav"]:
        problems.append("%s: the list covers the site header" % name)

    # Arrow keys move a highlight a screen reader can follow, Enter commits.
    pg.keyboard.press("ArrowDown")
    pg.wait_for_timeout(200)
    s2 = pg.evaluate(STATE)
    if not s2["active"]:
        problems.append("%s: arrowing down set no aria-activedescendant" % name)
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(400)
    s3 = pg.evaluate(STATE)
    if s3["open"]:
        problems.append("%s: Enter left the list open" % name)
    if s3["value"].lower() != "mumbai":
        problems.append("%s: Enter put %r in the box, not Mumbai" % (name, s3["value"]))
    if "1 place" not in (s3["found"] or ""):
        problems.append("%s: choosing a suggestion did not filter the map (%r)"
                        % (name, (s3["found"] or "").strip()[:40]))

    # Escape dismisses the list without throwing away what was typed.
    pg.fill("#om-q", "")
    pg.type("#om-q", "eu-we", delay=40)
    pg.wait_for_timeout(350)
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(250)
    s4 = pg.evaluate(STATE)
    if s4["open"]:
        problems.append("%s: Escape did not dismiss the list" % name)
    if s4["value"] != "eu-we":
        problems.append("%s: Escape also cleared the box (%r) — the first press "
                        "should only dismiss" % (name, s4["value"]))

    # A code typed in full must be offered too, not just place names.
    pg.fill("#om-q", "")
    pg.type("#om-q", "ap-south-1", delay=20)
    pg.wait_for_timeout(400)
    s5 = pg.evaluate(STATE)
    if not s5["open"] or not any("ap-south-1" in r for r in s5["rows"]):
        problems.append("%s: a full region code offered no suggestion" % name)

    pg.close()
    return problems


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
            for label, launcher in (("Chrome / Edge", pw.chromium),
                                    ("Safari, iPad and iPhone", pw.webkit)):
                try:
                    b = launcher.launch()
                except Exception as exc:                        # noqa: BLE001
                    print("  %-24s could not start: %s" % (label, str(exc)[:44]))
                    problems.append("%s could not be tested" % label)
                    continue
                found = run(b, base, label)
                b.close()
                problems += found
                print("  %-24s %s" % (label, "ok" if not found else
                                      "FAIL — %d problem(s)" % len(found)))
    finally:
        if srv:
            srv.shutdown()

    print()
    if problems:
        print("  %d PROBLEM(S)\n" % len(problems))
        for p in problems[:14]:
            print("  - %s" % p)
        return 1
    print("  the suggestions open, rank, arrow, commit, dismiss and announce")
    print("  themselves the same way in both engines.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
