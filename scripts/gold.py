#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A gold copy of the site, in code AND in behaviour, to prove a change is
only what it claims to be.

    python scripts/gold.py snapshot        # before you change anything
    python scripts/gold.py compare         # after -- what actually moved
    python scripts/gold.py compare --code-only    # skip the browser pass

Why this exists
---------------
Asked for, in these words: "take a carbon copy or a gold copy of every single
piece of code... next time when you add a new feature, validate only the new
feature has been added and the rest is not altered in any way... give me a
final statement that out of 5,000 or 10,000 lines only this specific area has
been created or altered and the rest is intact."

That is the right instinct and it needs one correction, which is the whole
reason this file has two halves.

A code snapshot would NOT have caught the bug that prompted it. The year
filter on the blog broke on 14 September, and blog.js -- the file containing
the broken line -- was not edited that day. sync_blog.py was: it began
rendering the year row into the server HTML, so a query in blog.js that had
never matched those pills suddenly did. Every year pill lit at once for three
days. A file-by-file diff would have reported, accurately and uselessly, "only
sync_blog.py changed".

Code diffs catch what you EDITED. They cannot catch what you AFFECTED.

So:

  snapshot code       every tracked file, hashed. Proves nothing was touched
                      that you did not mean to touch.

  snapshot behaviour  what each page DOES -- how many posts, how many cards,
                      what the nav measures, and what happens when the
                      filters are clicked. Proves nothing STOPPED WORKING
                      that you did not mean to change.

The second half is the one that matters, and it is the one no diff gives you.
It drives a real browser, clicks the real controls, and records the result, so
"the year pills still filter" is a recorded fact rather than an assumption.

The snapshot lives in .gold/ and is not committed: it is a record of one
machine at one moment, and a stale one committed to the repo would be worse
than none.
"""
import argparse
import datetime as dt
import hashlib
import io
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLD = os.path.join(ROOT, ".gold")
CODE = os.path.join(GOLD, "code.json")
BEHAVIOUR = os.path.join(GOLD, "behaviour.json")

# The pages a reader actually opens. Behaviour is recorded for these; the code
# snapshot covers everything.
PAGES = [
    ("portfolio", "/"),
    ("blog", "/blog/"),
    ("intelligence", "/intelligence/"),
    ("whats-new", "/intelligence/whats-new/"),
    ("status", "/intelligence/status/"),
    ("events", "/intelligence/events/"),
]

# What "it still works" means, per page, in things a reader would notice.
PROBE = r"""() => {
  const n = (sel) => document.querySelectorAll(sel).length;
  const nav = document.querySelector('nav') || document.querySelector('.nav');
  const navCs = nav ? getComputedStyle(nav) : null;
  const ctl = (sel) => {
    const e = nav && nav.querySelector(sel);
    if (!e) return null;
    const r = e.getBoundingClientRect();
    const c = getComputedStyle(e);
    return [Math.round(r.x), Math.round(r.width), c.color, c.opacity];
  };
  return {
    title: document.title,
    nav: nav ? {
      h: Math.round(nav.getBoundingClientRect().height),
      bg: navCs.backgroundColor, ink: navCs.color,
      rule: navCs.borderBottomColor,
      links: [].slice.call(nav.querySelectorAll('.nav-links a[href]'))
               .map(a => a.textContent.trim()),
      subscribe: ctl('#subnav-btn, .subnav-btn'),
      music: ctl('#audio-toggle, .audio-toggle'),
      palette: ctl('.pal-nav-btn'),
      theme: ctl('#nav-theme-btn, .theme-toggle')
    } : null,
    counts: {
      postCards: n('.post-card'),
      eventRows: n('.ev-row'),
      topicPills: n('.filters:not(.year-filters):not(.month-filters) .filter-pill'),
      yearPills: n('.year-filters .filter-pill'),
      evPills: n('.ev-pill'),
      internalLinks: [].slice.call(document.querySelectorAll('a[href^="/"]')).length,
      headings: n('h1, h2')
    }
  };
}"""

# Clicking things is the half a diff cannot do.
INTERACT = r"""() => {
  const out = {};
  const shownCards = () => [].slice.call(
      document.querySelectorAll('.post-card')).filter(
      c => c.style.display !== 'none').length;
  const shownRows = () => [].slice.call(
      document.querySelectorAll('.ev-row')).filter(
      c => c.style.display !== 'none').length;

  const years = [].slice.call(document.querySelectorAll(
      '.year-filters .filter-pill[data-year]'));
  if (years.length) {
    out.years = {};
    years.forEach(function (p) {
      p.click();
      const lit = [].slice.call(document.querySelectorAll(
          '.year-filters .filter-pill.active')).map(e => e.dataset.year);
      out.years[p.dataset.year] = {lit: lit, shown: shownCards()};
    });
  }

  const evs = [].slice.call(document.querySelectorAll(
      '.ev-pill[data-group="cloud"]'));
  if (evs.length) {
    out.eventClouds = {};
    evs.forEach(function (p) {
      p.click();
      out.eventClouds[p.dataset.value] = shownRows();
    });
  }
  return out;
}"""


def tracked_files():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                         text=True, encoding="utf-8", errors="replace")
    return [f for f in out.stdout.splitlines() if f.strip()]


# A newline byte inside a PNG is not a line.
#
# The first version counted every tracked file the same way, and reported the
# site at 1,078,966 lines. 698,048 of those were newline BYTES inside images,
# fonts and mp3s -- a number with no meaning, printed in the one sentence that
# is supposed to be the trustworthy summary of a change.
#
# Binaries are still HASHED, because a swapped image is a change worth seeing.
# They are just not counted in lines, and the summary now says how many were
# treated that way rather than quietly folding them in.
BINARY = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svgz",
          ".woff", ".woff2", ".ttf", ".otf", ".eot",
          ".mp3", ".mp4", ".webm", ".mov", ".pdf", ".zip", ".gz")


def hash_code():
    files = {}
    for rel in tracked_files():
        p = os.path.join(ROOT, rel)
        try:
            with open(p, "rb") as fh:
                data = fh.read()
        except OSError:
            continue
        binary = rel.lower().endswith(BINARY)
        files[rel] = {"sha": hashlib.sha256(data).hexdigest()[:16],
                      "lines": 0 if binary else data.count(b"\n") + 1,
                      "bytes": len(data),
                      "binary": binary}
    return files


def serve():
    import http.server
    import socketserver
    import threading

    class T(socketserver.ThreadingTCPServer):
        daemon_threads = True
        allow_reuse_address = True

    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    os.chdir(ROOT)
    for port in range(9711, 9760):
        try:
            srv = T(("127.0.0.1", port), H)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            return srv, port
        except OSError:
            continue
    raise SystemExit("no free port")


def record_behaviour():
    from playwright.sync_api import sync_playwright
    srv, port = serve()
    base = "http://127.0.0.1:%d" % port
    out = {}
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            for name, path in PAGES:
                ctx = b.new_context(viewport={"width": 1440, "height": 900})
                pg = ctx.new_page()
                try:
                    pg.goto(base + path, wait_until="load", timeout=90000)
                    pg.wait_for_timeout(3500)
                    rec = pg.evaluate(PROBE)
                    rec["interact"] = pg.evaluate(INTERACT)
                except Exception as exc:                    # noqa: BLE001
                    rec = {"error": str(exc)[:80]}
                out[name] = rec
                ctx.close()
            b.close()
    finally:
        srv.shutdown()
    return out


def cmd_snapshot(args):
    if not os.path.isdir(GOLD):
        os.makedirs(GOLD)
    code = hash_code()
    io.open(CODE, "w", encoding="utf-8").write(json.dumps(
        {"taken": dt.datetime.now().isoformat(timespec="seconds"),
         "files": code}, indent=1))
    nbin = sum(1 for f in code.values() if f.get("binary"))
    print("  code:      %d files, %d lines (%d binaries hashed, not counted)"
          % (len(code), sum(f["lines"] for f in code.values()), nbin))
    if args.code_only:
        print("  behaviour: skipped (--code-only)")
        return 0
    beh = record_behaviour()
    io.open(BEHAVIOUR, "w", encoding="utf-8").write(json.dumps(
        {"taken": dt.datetime.now().isoformat(timespec="seconds"),
         "pages": beh}, indent=1))
    ok = sum(1 for v in beh.values() if "error" not in v)
    print("  behaviour: %d of %d pages recorded" % (ok, len(beh)))
    print("\n  Gold copy taken. Make your change, then: gold.py compare")
    return 0


def walk(a, b, path=""):
    """Every leaf where two nested structures disagree."""
    diffs = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            diffs += walk(a.get(k), b.get(k), "%s.%s" % (path, k) if path else k)
    elif a != b:
        diffs.append((path, a, b))
    return diffs


def cmd_compare(args):
    if not os.path.exists(CODE):
        print("  no snapshot yet -- run: python scripts/gold.py snapshot")
        return 1
    old = json.load(io.open(CODE, encoding="utf-8"))
    print("  gold copy taken %s\n" % old.get("taken"))
    now = hash_code()
    before = old["files"]

    added = sorted(set(now) - set(before))
    removed = sorted(set(before) - set(now))
    changed = sorted(f for f in set(now) & set(before)
                     if now[f]["sha"] != before[f]["sha"])

    print("  CODE")
    print("     %d file(s) in the gold copy, %d now" % (len(before), len(now)))
    if not (added or removed or changed):
        print("     nothing changed at all")
    for f in added:
        print("     NEW      %-56s %d lines" % (f[:56], now[f]["lines"]))
    for f in removed:
        print("     DELETED  %-56s" % f[:56])
    for f in changed:
        d = now[f]["lines"] - before[f]["lines"]
        print("     CHANGED  %-56s %+d lines" % (f[:56], d))

    beh_diffs = []
    measured_behaviour = False
    if not args.code_only and os.path.exists(BEHAVIOUR):
        measured_behaviour = True
        oldb = json.load(io.open(BEHAVIOUR, encoding="utf-8"))["pages"]
        newb = record_behaviour()
        print("\n  BEHAVIOUR")
        for name, _ in PAGES:
            d = walk(oldb.get(name), newb.get(name))
            if not d:
                print("     same     %s" % name)
                continue
            beh_diffs += [(name,) + x for x in d]
            print("     MOVED    %s" % name)
            for p, a, b in d[:8]:
                print("                %-34s %s  ->  %s"
                      % (p[:34], str(a)[:26], str(b)[:26]))
            if len(d) > 8:
                print("                ...and %d more" % (len(d) - 8))
    elif not args.code_only:
        print("\n  BEHAVIOUR: no behaviour snapshot to compare against")

    print()
    print("  " + "-" * 66)
    total_lines = sum(f["lines"] for f in now.values())
    nbin = sum(1 for f in now.values() if f.get("binary"))
    scope = ("%d files (%d text, %d binary) and %d lines"
             % (len(now), len(now) - nbin, nbin, total_lines))
    # Say which half was actually measured.
    #
    # --code-only skips the browser entirely, and this still printed "0
    # behavioural difference(s)" and "behaves as it did" underneath it. That
    # is the tool built to stop unmeasured claims making one: zero differences
    # found and zero differences looked for read identically, and the second
    # is worth nothing. (CHECKLIST rule 5, and rule 6 -- a zero result is not
    # a fact.)
    if not (added or removed or changed) and not beh_diffs:
        if measured_behaviour:
            print("  Of %s, NOTHING changed and no page behaves differently."
                  % scope)
        else:
            print("  Of %s, NOTHING changed. Behaviour was NOT measured on "
                  "this run." % scope)
    else:
        print("  Of %s:" % scope)
        print("    %d file(s) added, %d deleted, %d changed."
              % (len(added), len(removed), len(changed)))
        if measured_behaviour:
            print("    %d behavioural difference(s) across %d page(s)."
                  % (len(beh_diffs), len({d[0] for d in beh_diffs})))
            print("  Everything else is byte-for-byte identical and behaves "
                  "as it did.")
        else:
            print("    behaviour NOT measured on this run%s."
                  % (" (--code-only)" if args.code_only
                     else " (no behaviour in the gold copy)"))
            print("  Everything else is byte-for-byte identical. What those "
                  "files DO has not been re-checked.")
    print("  " + "-" * 66)
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot")
    s.add_argument("--code-only", action="store_true")
    s.set_defaults(fn=cmd_snapshot)
    c = sub.add_parser("compare")
    c.add_argument("--code-only", action="store_true")
    c.set_defaults(fn=cmd_compare)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
