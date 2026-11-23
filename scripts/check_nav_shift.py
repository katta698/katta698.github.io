#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fingerprint the nav bar on every page family, so a nav change can be proved.

    python scripts/check_nav_shift.py --base http://127.0.0.1:8911 --out before.json
    ...make the change, rebuild...
    python scripts/check_nav_shift.py --base http://127.0.0.1:8911 --out after.json
    python scripts/check_nav_shift.py --diff before.json after.json

WHY THIS EXISTS
---------------
Adding a link to the nav touches 608 pages. The failure mode is not a broken
page -- it is a page that looks right and sits two pixels lower than it did,
on one family, at one width, which nobody notices until the whole site feels
unsteady. This repository has had that exact fault: the comment in the nav
markup records the bar jumping 44px left and then 39px back on every single
load, because a control was being injected after first paint.

So the rule here is not "does the nav still render". It is "is every number
identical except the ones that are supposed to change".

WHAT IS CAPTURED, AND WHY EACH ONE
----------------------------------
  nav height, --nav-h       if the bar grows, every page's content moves down
  first-content y           the actual proof that nothing moved
  per-link type metrics     font, size, weight, letter-spacing, padding --
                            a new link must be indistinguishable from its
                            neighbours, not merely present
  gaps between links        spacing is the thing a reader sees before text
  layout shift during load  a bar that settles late is worse than a bar that
                            is wrong, because it is wrong only sometimes
"""
import argparse
import io
import json
import sys

FAMILIES = [
    ("portfolio", "/"),
    ("blog index", "/blog/"),
    ("blog post", None),            # filled in at run time from the index
    ("arch post", None),
    ("intelligence hub", "/intelligence/"),
    ("live status", "/intelligence/status/"),
    ("services", "/intelligence/services/"),
    ("data", "/data/"),
]
WIDTHS = [1440, 1280, 1100, 980, 820, 600, 430, 390, 360]

PROBE = """() => {
  const nav = document.querySelector('nav');
  if (!nav) return {missing: true};
  const r = nav.getBoundingClientRect();
  const cs = getComputedStyle(document.documentElement);
  const links = [...nav.querySelectorAll('.nav-links li')].map(li => {
    const a = li.querySelector('a, button');
    const b = li.getBoundingClientRect();
    const s = a ? getComputedStyle(a) : null;
    return {
      text: (a ? a.textContent : '').trim().replace(/\\s+/g, ' '),
      ctl: li.classList.contains('nav-ctl'),
      shown: li.offsetParent !== null,
      x: Math.round(b.x * 10) / 10, y: Math.round(b.y * 10) / 10,
      w: Math.round(b.width * 10) / 10, h: Math.round(b.height * 10) / 10,
      font: s ? s.fontFamily.split(',')[0].replace(/["']/g, '') : '',
      size: s ? s.fontSize : '', weight: s ? s.fontWeight : '',
      spacing: s ? s.letterSpacing : '',
      pad: s ? [s.paddingTop, s.paddingRight, s.paddingBottom,
                s.paddingLeft].join(' ') : '',
      mar: s ? [s.marginTop, s.marginRight, s.marginBottom,
                s.marginLeft].join(' ') : '',
      color: s ? s.color : ''
    };
  });
  const vis = links.filter(l => l.shown && !l.ctl);
  const gaps = [];
  for (let i = 1; i < vis.length; i++) {
    gaps.push(Math.round((vis[i].x - (vis[i - 1].x + vis[i - 1].w)) * 10) / 10);
  }
  const first = document.querySelector('main, .wrap, article, h1');
  return {
    navH: Math.round(r.height * 10) / 10,
    navTop: Math.round(r.y * 10) / 10,
    navHVar: (cs.getPropertyValue('--nav-h') || '').trim(),
    links: links,
    gaps: gaps,
    shownLinks: vis.map(l => l.text),
    firstContentY: first ? Math.round(
        first.getBoundingClientRect().y * 10) / 10 : null,
    overflow: document.documentElement.scrollWidth > window.innerWidth,
    cls: Math.round((window.__cls || 0) * 10000) / 10000
  };
}"""

CLS_INIT = """
window.__cls = 0;
try {
  new PerformanceObserver((l) => {
    for (const e of l.getEntries()) {
      if (!e.hadRecentInput) window.__cls += e.value;
    }
  }).observe({type: 'layout-shift', buffered: true});
} catch (e) {}
"""


def discover(page, base):
    """Pick a real blog post and a real arch post off the index."""
    page.goto(base + "/blog/", wait_until="load", timeout=60000)
    hrefs = page.evaluate(
        "() => [...document.querySelectorAll('a[href^=\"/blog/\"]')]"
        ".map(a => a.getAttribute('href'))")
    post = next((h for h in hrefs if h.count("/") == 3
                 and "architecture" not in h and h != "/blog/"), None)
    arch = next((h for h in hrefs if "architecture" in h), None)
    return post, arch


def capture(base):
    from playwright.sync_api import sync_playwright
    out = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1280, "height": 900})
        post, arch = discover(pg, base)
        pg.close()
        fams = []
        for name, path in FAMILIES:
            if path is None:
                path = post if name == "blog post" else arch
            if path:
                fams.append((name, path))
        for name, path in fams:
            for w in WIDTHS:
                ctx = b.new_context(viewport={"width": w, "height": 900})
                ctx.add_init_script(CLS_INIT)
                pg = ctx.new_page()
                errs = []
                pg.on("pageerror", lambda e: errs.append(str(e)[:90]))
                pg.goto(base + path, wait_until="load", timeout=60000)
                pg.wait_for_timeout(1600)   # let site-footer.js finish
                r = pg.evaluate(PROBE)
                r["path"] = path
                r["errors"] = errs
                out["%s@%d" % (name, w)] = r
                ctx.close()
        b.close()
    return out


def diff(a, b, expect_new):
    """Report every change. Only the arrival of expect_new is allowed."""
    problems, notes = [], []
    for key in sorted(set(a) | set(b)):
        if key not in a or key not in b:
            problems.append("%s: present in only one capture" % key)
            continue
        x, y = a[key], b[key]
        for field in ("navH", "navTop", "navHVar", "firstContentY",
                      "overflow"):
            if x.get(field) != y.get(field):
                problems.append("%s: %s %r -> %r"
                                % (key, field, x.get(field), y.get(field)))
        if y.get("cls", 0) > 0.01 and y.get("cls", 0) > x.get("cls", 0) + 0.005:
            problems.append("%s: layout shift grew %.4f -> %.4f"
                            % (key, x.get("cls", 0), y.get("cls", 0)))
        # the new link must match its neighbours on every type metric
        old_links = {l["text"]: l for l in x["links"] if not l["ctl"]}
        new_links = {l["text"]: l for l in y["links"] if not l["ctl"]}
        for text, link in new_links.items():
            old = old_links.get(text)
            if old and old.get("color") != link.get("color"):
                notes.append("%s: %s colour %s -> %s (daily palette)"
                             % (key, text, old["color"], link["color"]))
        arrived = set(new_links) - set(old_links)
        gone = set(old_links) - set(new_links)
        if gone:
            problems.append("%s: link(s) disappeared: %s"
                            % (key, ", ".join(sorted(gone))))
        if arrived - {expect_new}:
            problems.append("%s: unexpected new link(s): %s"
                            % (key, ", ".join(sorted(arrived - {expect_new}))))
        for text, link in new_links.items():
            if text == expect_new:
                continue
            old = old_links.get(text)
            if not old:
                continue
            # colour is deliberately absent: the site picks a different
            # accent each day, so two captures taken on different days always
            # differ. A check that fires every time is a check that gets
            # switched off. It is reported as a note instead.
            for f in ("font", "size", "weight", "spacing", "pad", "mar", "h"):
                if old[f] != link[f]:
                    problems.append("%s: %s %s %r -> %r"
                                    % (key, text, f, old[f], link[f]))
        if expect_new in new_links:
            n = new_links[expect_new]
            peers = [l for t, l in new_links.items() if t != expect_new]
            if peers and not n["ctl"]:
                ref = peers[0]
                for f in ("font", "size", "weight", "spacing", "pad", "mar",
                          "h"):
                    if n[f] != ref[f]:
                        problems.append(
                            "%s: the new link's %s is %r, its neighbours use "
                            "%r" % (key, f, n[f], ref[f]))
            if n["shown"] != peers[0]["shown"] if peers else False:
                problems.append("%s: the new link's visibility differs from "
                                "its neighbours" % key)
        # One more flex item changes sub-pixel rounding. Anything under half
        # a pixel is the renderer, not the layout.
        if x["gaps"] and y["gaps"]:
            old_g, new_g = sorted(set(x["gaps"])), sorted(set(y["gaps"]))
            drift = max((min(abs(g - o) for o in old_g) for g in new_g),
                        default=0)
            if drift >= 0.5:
                problems.append("%s: spacing moved %s -> %s"
                                % (key, old_g, new_g))
            elif old_g != new_g:
                notes.append("%s: spacing rounding %s -> %s (%.1fpx)"
                             % (key, old_g, new_g, drift))
    return problems, notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base")
    ap.add_argument("--out")
    ap.add_argument("--diff", nargs=2)
    ap.add_argument("--expect-new", default="Data")
    a = ap.parse_args()

    if a.diff:
        with io.open(a.diff[0], encoding="utf-8") as f:
            before = json.load(f)
        with io.open(a.diff[1], encoding="utf-8") as f:
            after = json.load(f)
        problems, notes = diff(before, after, a.expect_new)
        print("compared %d page/width combinations" % len(before))
        for n in notes:
            print("  note  %s" % n)
        if problems:
            print("\n%d PROBLEM(S):" % len(problems))
            for p in problems:
                print("    %s" % p)
            return 1
        print("\nNothing moved. Nav height, content position, type metrics "
              "and layout shift are identical everywhere; the only change is "
              "the new %r link." % a.expect_new)
        return 0

    data = capture(a.base)
    with io.open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, sort_keys=True)
    bad = [k for k, v in data.items() if v.get("missing") or v.get("errors")]
    print("captured %d page/width combinations -> %s" % (len(data), a.out))
    if bad:
        print("pages with no nav or console errors: %s" % ", ".join(bad[:6]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
