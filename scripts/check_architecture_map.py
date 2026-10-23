#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Every box on the architecture diagram still names something real.

    python scripts/check_architecture_map.py

Why this exists
---------------
/how-this-was-made/ prints, under the diagram: "Every box names a real file in
the repository -- a check refuses this page if one of them stops existing."

That sentence is either true or it is the most embarrassing kind of wrong, so
this is the check it refers to. A diagram is a promise about how something
fits together, and the failure mode is not that it breaks: it keeps rendering,
beautifully, describing a shape the code left behind months ago. Nobody
reports a diagram. They just quietly stop trusting it.

So this asserts two directions, because only one of them is easy:

  1. Every path the diagram claims exists.
  2. Every builder that writes a published page is ON the diagram.

The second is the one that catches drift. build_colophon.py itself was added
to this site after the diagram was drawn and is not in it -- caught by writing
this half of the check, not by looking at the picture.
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

# Builders that write a page a reader can open. A builder here and not on the
# diagram means the picture is missing a moving part.
#
# build_colophon.py is exempt for one honest reason: it is the builder OF the
# diagram, and drawing itself inside itself explains nothing. Named here
# rather than silently skipped, so the exemption is a decision somebody can
# disagree with rather than an omission.
EXEMPT_BUILDERS = {"build_colophon.py"}


def rendered():
    """The diagram is legible in BOTH themes, measured off the pixels.

    Every check here read the source and none of them opened the page, and
    that is precisely how the diagram shipped unreadable. A rewrite that
    added the hover notes rebuilt each box's opening tag and dropped the
    class attribute doing it -- `<g src ...>` instead of `<g class="ab src"
    ...>`. Every fill and every text colour in colophon_scene_css.py hangs
    off that class.

    Dark mode looked correct by coincidence: an unstyled rect paints black
    and the page is nearly black, and the labels inherit a light
    currentColor. Light mode was black boxes carrying black text on cream,
    and it reached a reader, who photographed it. Not one assertion here
    noticed, because the markup was still well-formed, every box still
    named a real file, and nothing overlapped anything.

    So: load the built page in both themes and ask the questions a reader
    asks. Can I see the box? Can I read the label? A computed style is not
    the answer -- alpha, opacity and currentColor all resolve against what
    is behind them -- so this measures contrast from the values actually
    painted.
    """
    page = os.path.join(ROOT, "how-this-was-made", "index.html")
    if not os.path.exists(page):
        return ["the colophon has never been built"]
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  (playwright missing -- the rendered pass did not run)")
        return []

    # Over HTTP, not file://.
    #
    # The page links site-footer.css by absolute path, so under file:// it
    # resolves to the filesystem root and 404s -- and a failed sheet still
    # appears in document.styleSheets, so nothing looks wrong. The first
    # version of this check ran that way and reported three accent labels
    # at 2.15:1 in light mode. They are not: --acc-ink resolves to #6E5236
    # once the stylesheet is actually there. The defect was the ruler.
    import functools
    import http.server
    import socketserver
    import threading

    class Quiet(http.server.SimpleHTTPRequestHandler):      # noqa: N801
        def log_message(self, *a):                          # noqa: D102
            pass

    srv = socketserver.TCPServer(
        ("127.0.0.1", 0), functools.partial(Quiet, directory=ROOT))
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    probe = """() => {
      // 'none', a url(#id) paint server, or a keyword all arrive here and
      // none of them is a colour. Treat them as fully transparent, which
      // is what they look like over the page.
      const hex = c => { const m = (c || '').match(/[\d.]+/g);
        return m && m.length >= 3 ? m.map(Number) : [0, 0, 0, 0]; };
      const lum = c => { const [r,g,b] = c.slice(0,3).map(v => {
        v /= 255; return v <= 0.03928 ? v/12.92
                                      : Math.pow((v+0.055)/1.055, 2.4); });
        return 0.2126*r + 0.7152*g + 0.0722*b; };
      const over = (fg, bg) => { const a = fg[3] === undefined ? 1 : fg[3];
        return [0,1,2].map(i => fg[i]*a + bg[i]*(1-a)); };
      const ratio = (a, b) => { const L1 = lum(a), L2 = lum(b);
        return (Math.max(L1,L2)+0.05) / (Math.min(L1,L2)+0.05); };
      const page = hex(getComputedStyle(document.body).backgroundColor);
      const out = { boxes: 0, invisible: [], unreadable: [] };
      document.querySelectorAll('.cf-arch-svg g.ab').forEach(g => {
        out.boxes++;
        const rect = g.querySelector('rect');
        if (!rect) return;
        const cs = getComputedStyle(rect);
        const fill = over(hex(cs.fill), page);
        const label = (g.querySelector('text') || {}).textContent || '(box)';
        // A box whose fill is the page is a box nobody can see. The stroke
        // may still outline it, so this only complains when the fill is the
        // page AND the stroke is too.
        const stroke = over(hex(cs.stroke || 'rgba(0,0,0,0)'), page);
        if (ratio(fill, page) < 1.06 && ratio(stroke, page) < 1.25)
          out.invisible.push(label.trim().slice(0, 28));
        g.querySelectorAll('text').forEach(t => {
          const ts = getComputedStyle(t);
          const c = hex(ts.fill);
          const op = parseFloat(ts.opacity || 1);
          if (c[3] === undefined) c[3] = 1;
          c[3] *= op;
          const r = ratio(over(c, fill), fill);
          if (r < 3)
            out.unreadable.push((t.textContent || '').trim().slice(0, 28)
                                + ' at ' + r.toFixed(2) + ':1');
        });
      });
      return out; }"""

    found = []
    url = "http://127.0.0.1:%d/how-this-was-made/" % port
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for theme in ("dark", "light"):
            ctx = b.new_context(viewport={"width": 1280, "height": 900})
            ctx.add_init_script("try{localStorage.setItem('theme','%s');}"
                                "catch(e){}" % theme)
            pg = ctx.new_page()
            pg.goto(url, wait_until="load", timeout=60000)
            pg.wait_for_timeout(1400)
            r = pg.evaluate(probe)
            ctx.close()
            if not r["boxes"]:
                found.append("%s: the diagram rendered no boxes at all -- "
                             "g.ab matched nothing, so every fill and every "
                             "text colour in the stylesheet is unused"
                             % theme)
                continue
            print("  %-5s %d boxes, %d invisible, %d unreadable label(s)"
                  % (theme, r["boxes"], len(r["invisible"]),
                     len(r["unreadable"])))
            if r["invisible"]:
                found.append(
                    "%s: %d box(es) are the same colour as the page they sit "
                    "on, with no outline either: %s"
                    % (theme, len(r["invisible"]),
                       ", ".join(r["invisible"][:4])))
            if r["unreadable"]:
                found.append(
                    "%s: %d label(s) cannot be read against their own box: "
                    "%s" % (theme, len(r["unreadable"]),
                            "; ".join(r["unreadable"][:4])))
        b.close()
    srv.shutdown()
    return found



def main():
    from colophon_architecture import CLAIMS, ARCHITECTURE

    problems = []

    # 1. Everything the picture names has to exist.
    print("  boxes on the diagram: %d" % len(CLAIMS))
    for label, rel in sorted(CLAIMS.items()):
        path = os.path.join(ROOT, rel.replace("/", os.sep))
        if not os.path.exists(path):
            problems.append(
                "the diagram has a box labelled %r pointing at %s, which does "
                "not exist. The picture still renders and is now describing a "
                "site that is not this one" % (label, rel))
            print("     MISSING  %-26s %s" % (label, rel))

    # Every label in CLAIMS must actually appear in the drawing, or the check
    # is validating a list nobody is looking at.
    for label in CLAIMS:
        if label not in ARCHITECTURE:
            problems.append(
                "%r is in the claims list but does not appear in the drawing "
                "-- this check is guarding a box that is not there" % label)

    # 2. Every page-writing builder has to be in the picture.
    builders = [f for f in os.listdir(os.path.join(ROOT, "scripts"))
                if f.startswith("build_") and f.endswith(".py")]
    writes_page = []
    for f in sorted(builders):
        if f in EXEMPT_BUILDERS:
            continue
        try:
            src = io.open(os.path.join(ROOT, "scripts", f),
                          encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        # A builder that writes an index.html is one a reader meets.
        if re.search(r'["\']index\.html["\']', src):
            writes_page.append(f)

    for f in writes_page:
        if f not in ARCHITECTURE:
            problems.append(
                "%s writes a page a reader can open and is not on the "
                "diagram. The picture is missing a moving part, which is the "
                "way a diagram goes wrong: it keeps rendering" % f)
            print("     ABSENT   %s" % f)

    print("  builders that write a page: %d" % len(writes_page))

    problems += rendered()

    print()
    if problems:
        print("  %d PROBLEM(S)\n" % len(problems))
        for p in problems:
            print("  - %s" % p)
        print()
        print("  The page says every box names a real file. Either fix the")
        print("  diagram or stop printing that sentence under it.")
        return 1
    print("  Every box names something that exists, and every builder that "
          "writes\n  a page is on the picture.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
