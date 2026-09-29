#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The contact card's artwork sits where it should, and its paper is paper.

Two things were reported from a phone, in one message, and neither is
visible in a screenshot taken at the height the page happens to be on the
machine it was built on:

  "the guy's head is just under AI"     The figure cleared the AI pill by
                                        six pixels, which reads as
                                        touching. Before that he was
                                        behind the LinkedIn button
                                        entirely.

  "the borders don't quite match"       theme-color, left behind by a
                                        repaint. The phone paints the
                                        status bar above the page and the
                                        gesture bar below it with that
                                        colour, so it is part of the card
                                        whether or not the CSS thinks so.

  "the background image stays static    background-attachment: fixed. The
   and the whole page is moving"        paper was pinned to the viewport
                                        while the card slid over it, so
                                        the grain swam against the
                                        content instead of belonging to
                                        it. A sheet of paper moves with
                                        what is printed on it.

And one more, from the same session: the card fits iPhone's screen
without scrolling and does not fit Android's, because Chrome's address
bar and gesture bar take about 85px more than Safari's chrome at the same
nominal height. Not two layouts -- one layout and two viewport heights.
So the height is asserted too, at the three the card is actually read on.

All of it is geometry, so all of it is measurable. The art is positioned
in percentages against a fixed aspect ratio, which means every phone size
resolves it differently -- hence three, not one.

The scroll half is checked by scrolling and comparing a strip of bare
paper against itself: if the strip is identical after scrolling 200px,
the paper did not move, which is the defect. The comparison is against
what a real 200px shift of the same paper looks like, so the assertion
does not depend on a threshold somebody guessed.
"""
import hashlib
import io
import os
import re
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_connect_chain as C          # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    from playwright.sync_api import sync_playwright
    from PIL import Image
    import numpy as np
except ImportError:
    print("  playwright or pillow not installed -- skipping")
    sys.exit(0)

PORT = 9002
URL = "http://127.0.0.1:%d/connect/" % PORT
# The two short ones are Android with its chrome showing: a 360x800
# handset gives about 740 of usable viewport, a 393x800 one about
# 760. Without them the height assertion only ever saw sizes the
# card happened to fit, and it was over by 18 to 24px on a real
# phone for months while reporting "page N in N" three times.
WIDTHS = [(360, 740), (393, 760), (360, 780), (402, 874),
          (430, 880), (430, 932)]
HEAD = 0.764          # where the figure's head sits in the artwork
FEET = 0.953          # and his feet
GAP = 12              # px of air the head needs under the AI pill
SCENE = os.path.join(ROOT, "connect", "ink-scene.webp")


def birds_at():
    """How far down the artwork the topmost ink sits, as a fraction.

    The birds are the only marks in the top eighth -- above the sun and
    above the pine -- so this finds them without a hardcoded box, and it
    re-derives itself if the crop ever changes.
    """
    im = Image.open(SCENE).convert("RGBA")
    a = np.asarray(im)
    lum = 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]
    ink = (a[..., 3] > 110) & (lum < 120)
    ys, _ = np.where(ink[:int(im.height * 0.13)])
    return (ys.min() / im.height) if len(ys) else 0.0

BOXES = """()=>{
  const r = s => { const e = document.querySelector(s); if (!e) return null;
    const b = e.getBoundingClientRect();
    return {l: Math.round(b.left), t: Math.round(b.top),
            r: Math.round(b.right), b: Math.round(b.bottom)}; };
  /* The cloud pills became a road he walks, so the thing the
     figure has to clear is the road block now. Left pointing at
     .c-ai this threw rather than passing -- which is the right
     failure, but the check has to follow the page. */
  return {ai: r('.road') || r('.c-ai'), hero: r('.hero'),
          btn: r('.act-main'),
          page: document.body.scrollHeight, vh: innerHeight,
          attach: getComputedStyle(document.documentElement).backgroundAttachment};
}"""


def art_is_stamped():
    """Every picture on the card must carry the hash of the file on disk.

    The service worker serves images cache-first, so a bare filename is a
    promise never to change that picture. It was broken by every artwork
    revision in this session, and it showed up as a platform difference
    that was not one: "on iPhone the birds are there, on Android they are
    not" -- the iPhone had never cached the old file and the Android had.
    """
    page = os.path.join(ROOT, "connect", "index.html")
    text = io.open(page, encoding="utf-8").read()
    problems = []
    for name in sorted(set(re.findall(r"/connect/([a-z0-9-]+\.webp)", text))):
        art = os.path.join(ROOT, "connect", name)
        if not os.path.exists(art):
            continue
        want = hashlib.md5(io.open(art, "rb").read()).hexdigest()[:8]
        for m in re.finditer(r"/connect/%s(\?v=([0-9a-f]{8}))?" % re.escape(name),
                             text):
            got = m.group(2)
            if got != want:
                problems.append(
                    "%s is referenced as %s where the file hashes to %s -- a "
                    "phone that cached the old one never sees the new picture"
                    % (name, got or "no version", want))
                break
    return problems


def alpha_is_smooth():
    """The fades live in the alpha channel, so the alpha must be lossless.

    WebP compresses alpha separately, and lossily by default it keeps
    about eleven levels. The card's artwork fades out along its left edge
    and its bottom by fading its ALPHA, so eleven levels turned both into
    a staircase -- six visible steps across the foot of the picture -- and
    put a contour on every soft ink edge besides. Reported as the page
    looking dirty and uneven, on both phones, which is what it was.

    Written as a floor on distinct levels rather than "was it saved
    losslessly", because the file cannot say how it was made, and because
    a future re-save at alpha_quality=96 would pass a flag check and still
    band. scripts/build_connect_art.py is what produces these.
    """
    problems = []
    for name in ("ink-scene.webp", "ink-scene-dusk.webp"):
        art = os.path.join(ROOT, "connect", name)
        if not os.path.exists(art):
            continue
        try:
            from PIL import Image
            import numpy as np
        except ImportError:
            return []
        alpha = np.asarray(Image.open(art).convert("RGBA"))[..., 3]
        levels = len(np.unique(alpha))
        print("  %-22s %3d alpha levels" % (name, levels))
        if levels < 200:
            problems.append(
                "%s has only %d alpha levels -- its fades are a staircase. "
                "Rebuild with scripts/build_connect_art.py, which writes the "
                "alpha losslessly" % (name, levels))
    return problems


# Only the looping animations get scrubbed. document.getAnimations()
# also returns the card's finished entrance fade, and winding that back
# dims the whole card -- which is exactly what an earlier version of this
# measurement did, then blamed the walker for the result it had caused.
PICK_LOOPS = """() => {
  window.__a = document.getAnimations().filter(a => {
    try { return a.effect.getTiming().iterations === Infinity; }
    catch (e) { return false; } });
  window.__a.forEach(a => a.pause());
  return window.__a.length; }"""
# The pose frames are held apart by animation-delay, so the delay has to
# come out before the modulo and go back after it. Ignore it and all
# eight walk poses land on the same phase -- sometimes all lit, sometimes
# none, and the figure appears to vanish for reasons nothing on the page
# is doing.
SCRUB = """t => window.__a.forEach(a => {
  const ti = a.effect.getTiming(), d = ti.duration || 1, dl = ti.delay || 0;
  try { a.currentTime = ((t - dl) % d + d) % d + dl; } catch (e) {} })"""
HIKER_BOX = """() => { const r = document.querySelector('.hiker').getBoundingClientRect();
  return {x: r.x, y: r.y, w: r.width, h: r.height}; }"""


def figures_never_flicker(pg):
    """Exactly one pose, fully opaque, for every figure, all the way round.

    "He's kind of disappearing for a millisecond" was reported three
    times in those words, and fixed wrongly twice, because both fixes
    were checked by SUMMING the opacity of the pose groups. That sum
    cannot see the failure: cross-fading one silhouette into another
    holds the sum at 1 while the figure is genuinely see-through, since
    two shapes at half opacity composite to 75% where they overlap and
    50% where they do not, and nowhere to solid.

    Counting pixels instead was tried and abandoned. At 27px a pose
    change and a fade are not separable by ink: the airborne pose is
    thin raised arms on a tucked body, so it legitimately has a third
    less solid area than a stride, and any threshold loose enough to
    let that through is loose enough to let a fade through with it. A
    number tuned until it passed would be a check that cannot fail.

    So assert the rule the artwork actually follows, which is sharp:
    poses CUT. One lit, none part-lit, no instant with nothing. That
    catches a cross-fade (part-lit) and a mistimed swap (none lit), and
    it cannot be confused by what shape the pose happens to be.

    It sweeps the whole loop rather than the jump, and every figure
    rather than the man. Each of them now carries three pose groups
    instead of one -- walking, standing and, for him, the jump -- and
    the windows that hand over between them are generated per figure
    from a simulation. Seven figures times three handovers is twenty-one
    seams, and the one that matters will not be the one anybody thought
    to look at.
    """
    problems = []
    pg.evaluate(PICK_LOOPS)
    who = pg.evaluate("""() => ['.hiker .walker']
        .concat([...document.querySelectorAll('.follow')]
                .map(f => '.' + [...f.classList].find(c => /^f\d+$/.test(c)) + ' .bot'))""")
    bad, seen = {}, dict((w, []) for w in who)
    # 241 samples, offset off every boundary. A cut has no width, so at
    # the exact instant of one both the outgoing and the incoming pose
    # read as lit -- that is the boundary being measured, not anything a
    # frame can ever show.
    for i in range(241):
        pg.evaluate(SCRUB, 26000.0 * i / 240.0 + 0.31)
        st = pg.evaluate("""sels => sels.map(sel => {
          const o = e => +getComputedStyle(e).opacity;
          let lit = [], group = '';
          for (const g of document.querySelectorAll(sel + ' > g')) {
            const go = o(g);
            if (go < 0.02) continue;
            group = g.getAttribute('class') || '';
            for (const pose of g.children) {
              const v = go * o(pose);
              if (v > 0.02) lit.push(v);
            }
          }
          const box = document.querySelector(sel).getBoundingClientRect();
          return {n: lit.length, min: lit.length ? Math.min(...lit) : 0,
                  group: group, x: box.x}; })""", who)
        for sel, r in zip(who, st):
            pct = 100.0 * i / 240.0
            seen[sel].append((pct, r))
            if r["n"] == 0:
                bad.setdefault(sel, []).append(("nothing drawn", pct, 0))
            elif r["n"] > 1:
                bad.setdefault(sel, []).append(("%d poses at once" % r["n"], pct, 0))
            elif r["min"] < 0.99:
                bad.setdefault(sel, []).append(
                    ("only %.0f%% opaque" % (100 * r["min"]), pct, r["min"]))
    # And the pose has to be the RIGHT one. "Exactly one pose lit" is
    # satisfied perfectly by a figure that walks on the spot for the five
    # seconds it is meant to be standing at AWS working -- which is what
    # it was doing, through two rounds of this check passing, because a
    # generator function was written and never called. Tie the pose to
    # the motion and neither half can drift from the other.
    #
    # Sustained mismatch only, for two reasons that are not fussiness. At
    # the instant a figure arrives somewhere it is both "was moving" and
    # "is standing", so every honest handover looks like a fault for one
    # sample. And a follower waiting for the line to reach it creeps at a
    # fraction of a pixel per sample, which is walking slowly, not
    # standing. A treadmill lasts seconds; a seam lasts one frame. A
    # check that cries wolf on every seam gets switched off, and then it
    # is not protecting anything.
    RUN, SPAN = 6, 3           # ~1.6s of disagreement, measured over ~0.8s
    for sel in who:
        rows = seen[sel]
        streak, worst = {}, {}
        for i in range(SPAN, len(rows) - SPAN - 1):
            pct, r = rows[i]
            travel = abs(rows[i + SPAN][1]["x"] - rows[i - SPAN][1]["x"])
            still = travel < 0.3
            grp = r["group"]
            if still and grp in ("wcyc", "rcyc"):
                kind = "treadmill"
            elif not still and grp in ("wstand", "rstand"):
                kind = "sliding"
            else:
                streak.clear()
                continue
            streak[kind] = streak.get(kind, 0) + 1
            if streak[kind] >= RUN and kind not in worst:
                worst[kind] = pct - RUN * 100.0 / 240.0
        if "treadmill" in worst:
            problems.append(
                "%s stands still from %.1f%% of the loop but keeps running its "
                "walk cycle -- it stops by marching on the spot, which is a "
                "treadmill and contradicts the one thing the stop at AWS is "
                "there to say" % (sel, worst["treadmill"]))
        if "sliding" in worst:
            problems.append(
                "%s is walking from %.1f%% of the loop but showing its standing "
                "pose -- it slides along the road without moving its legs"
                % (sel, worst["sliding"]))
    if not bad and not problems:
        print("  %d figures, 241 instants each: one pose lit at every one of "
              "them, none part-lit, and each one walking or standing to match "
              "whether it is moving" % len(who))
    for sel, hits in bad.items():
        what, pct, _ = hits[0]
        problems.append(
            "%s: %s at %.1f%% of the loop (%d instant(s) in all). Every figure "
            "must have exactly one pose lit and fully opaque at every moment "
            "-- poses CUT between neighbouring shapes, they never cross-fade, "
            "and the walking, standing and jumping windows must tile with no "
            "gap. See make_connect_road.py and make_connect_chain.py"
            % (sel, what, pct, len(hits)))
    return problems


def labels_never_collide():
    """Three names at once, but never two in the same column.

    Arithmetic, not rendering, because it is a property of how the queue
    is laid out rather than of any one frame -- and the frame that would
    catch it comes round once a minute.

    The clouds fire together on purpose now: one row is one capability in
    three dialects, so S3, Blob Storage and Cloud Storage light at the
    same moment. That is only safe because each cloud's labels are
    anchored to its own data centre with seventy-odd pixels of clear air
    before the next one's begin -- which labels_fit measures. What this
    checks is the other half: that a row never asks one cloud to say two
    things at once, and that a name is gone before the next row starts.
    """
    problems = []
    gap = C.BEAT - C.VISIBLE
    print("  %d rows (%d capabilities + %d agent beats), one every %.1fs, "
          "each on %.1fs -- %.1fs of clear air, full lap %.0fs"
          % (len(C.CLOUD_SLOTS), len(C.TRIPLETS), len(C.AWS_AGENTS),
             C.BEAT, C.VISIBLE, gap, C.CLOUD_CYCLE))
    if gap <= 0:
        problems.append(
            "a name is on screen for %.1fs but the next row starts %.1fs "
            "later, so two rows are lit at once and every column doubles "
            "up. Raise BEAT or drop VISIBLE in make_connect_chain.py"
            % (C.VISIBLE, C.BEAT))
    column = {"s-aws": "AWS", "s-azu": "Azure", "s-gcp": "GCP",
              "f4": "AWS", "f5": "AWS", "f6": "AWS", "f2": "Azure",
              "f3": "GCP"}
    for i, row in enumerate(C.CLOUD_SLOTS):
        seen = {}
        for who, _kind, txt in row:
            col = column.get(who, who)
            if col in seen:
                problems.append(
                    "row %d lights %r and %r in the %s column at the same "
                    "instant -- one cloud, one name per row"
                    % (i, seen[col], txt, col))
            seen[col] = txt
    if C.CLOUD_CYCLE % 26 == 0:
        problems.append(
            "the cloud queue laps in %.0fs, a whole multiple of the 26s "
            "walk -- the two will fall into step and the card will start "
            "looking canned" % C.CLOUD_CYCLE)
    return problems


def labels_fit(pg):
    """Every service name fits the card, wherever its robot is standing.

    Five of the six robots never move, but the model does, so its label
    sweeps the whole road -- and the longest names belong to the boards at
    the two ends, where there is least room left. Each name is checked at
    every stop rather than at one instant, because a label is on screen
    for a second and a half once a minute and a screenshot will not find
    this.

    Both kinds are measured: the names that rise off a robot and the
    service names that hang under a board. The second lot were added and
    not checked for one round, which is exactly how the first lot came to
    be a pixel inside a gantry board.
    """
    problems = []
    for where, pct in (("Azure", C.AT_AZ + 2.0), ("AWS", 95.0),
                       ("GCP", C.AT_GCP + 2.0)):
        pg.evaluate(SCRUB, 26000.0 * pct / 100.0 + 0.31)
        hits = pg.evaluate("""() => {
          const card = document.querySelector('.wrap').getBoundingClientRect();
          const board = Math.max(...[...document.querySelectorAll('.plate')]
              .map(e => e.getBoundingClientRect().bottom));
          const out = [];
          for (const el of document.querySelectorAll('.puff b, .svcs b')) {
            const keep = el.style.cssText;
            el.style.animation = 'none'; el.style.opacity = '1';
            const k = el.getBoundingClientRect();
            const own = el.closest('.follow') || el.parentElement;
            out.push({who: own.classList[1] || own.classList[0],
                      txt: el.textContent, w: k.width,
                      left: k.left - card.left, right: card.right - k.right,
                      board: k.top - board});
            el.style.cssText = keep; }
          return out; }""")
        worst = min(hits, key=lambda h: min(h["left"], h["right"]))
        low = min(hits, key=lambda h: h["board"])
        print("  labels with him at %-5s worst card edge %5.1fpx (%s), "
              "closest under a board %4.1fpx (%s)"
              % (where, min(worst["left"], worst["right"]), worst["txt"],
                 low["board"], low["txt"]))
        # The clouds must not be able to reach each other. This is the
        # geometry the four separate queues rest on: within a cloud a
        # queue keeps two labels apart, but nothing keeps Azure's longest
        # name off AWS's building except the distance between them.
        band = {}
        for h in hits:
            if not h["who"].startswith("s-"):
                continue
            lo, hi = band.get(h["who"], (1e9, -1e9))
            band[h["who"]] = (min(lo, h["left"]), max(hi, h["left"] + h["w"]))
        rows = sorted(band.items(), key=lambda kv: kv[1][0])
        for (n1, (_l1, r1)), (n2, (l2, _r2)) in zip(rows, rows[1:]):
            if r1 > l2:
                problems.append(
                    "with him at %s, %s's longest label runs %.1fpx into "
                    "where %s's labels start. The per-cloud queues assume "
                    "the clouds cannot reach each other -- shorten the name "
                    "or move the buildings apart"
                    % (where, n1, r1 - l2, n2))
        for h in hits:
            if min(h["left"], h["right"]) < 2:
                problems.append(
                    "with him at %s, the label %r runs off the card (%.1fpx "
                    "left, %.1fpx right). Shorten the name or move the robot "
                    "-- see PUFFS in make_connect_chain.py"
                    % (where, h["txt"], h["left"], h["right"]))
            if h["board"] < 0:
                problems.append(
                    "with him at %s, the label %r rises %.1fpx into a gantry "
                    "board. The boards own the top of this block and the "
                    "names get the gap under them"
                    % (where, h["txt"], -h["board"]))
    return problems


def label_colours_read(pg, theme):
    """Every label colour clears 4.5:1 on the paper it is printed on.

    Six pixels is small text, so 4.5:1 is the floor -- not the 3:1 that
    display type gets. A colour that reads on a board at nine and a half
    pixels bold is not automatically legible at six, and the card's rust
    is exactly that case: it clears the floor easily on the name in the
    heading and missed it on a service label, at 3.84 on paper.

    Measured against --paper rather than body's background colour. The
    body paints its paper through a layered background image, so its
    computed backgroundColor is transparent, which parses as black and
    flatters every light-mode reading into nonsense.
    """
    problems = []
    r = pg.evaluate("""() => {
      const pick = sel => { const e = document.querySelector(sel);
        return e ? getComputedStyle(e).color : null; };
      return {paper: getComputedStyle(document.documentElement)
                  .getPropertyValue('--paper').trim(),
              Azure: pick('.s-azu b'), AWS: pick('.s-aws b'),
              GCP: pick('.s-gcp b'),
              // the agents and the model keep the default ink; checked
              // here too, because "the default" is a colour like any
              // other and six-pixel text is held to 4.5:1 whatever it is
              model: pick('.f1 .puff b'),
              agent: pick('.f2 .puff b')}; }""")

    def rgb(t):
        t = t.strip()
        if t.startswith("#"):
            h = t[1:]
            if len(h) == 3:
                h = "".join(c * 2 for c in h)
            return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
        return tuple(int(x) for x in
                     t.replace("rgba", "rgb").strip("rgb() ").split(",")[:3])

    def lum(c):
        def f(v):
            v /= 255.0
            return v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4
        return .2126 * f(c[0]) + .7152 * f(c[1]) + .0722 * f(c[2])

    paper = rgb(r["paper"])
    worst, worst_k = 99.0, ""
    for k in ("Azure", "AWS", "GCP", "model", "agent"):
        c = rgb(r[k])
        la, lb = lum(c), lum(paper)
        cr = (max(la, lb) + .05) / (min(la, lb) + .05)
        if cr < worst:
            worst, worst_k = cr, k
        if cr < 4.5:
            problems.append(
                "the %s label colour measures %.2f:1 on the %s paper, under "
                "the 4.5:1 that six-pixel text needs. Deepen it in the --c-* "
                "block in make_connect_chain.py" % (k, cr, theme))
    print("  %-5s label colours: worst is %s at %.2f:1"
          % (theme, worst_k, worst))
    return problems


def labels_actually_animate(pg):
    """Every label has a running animation attached to it.

    This is the check that was missing, and the bug it would have caught
    shipped: the service labels were generated with a DESCENDANT selector
    -- ".s-aws .svcs b" -- against an element carrying both classes at
    once, <i class="svcs s-aws">. It matched nothing. The labels were
    laid out, coloured, correctly placed and permanently invisible, and
    every other check passed, because every other check forces
    "animation: none" and reads the static position. A still cannot tell
    a label that is waiting its turn from a label that will never come.

    So this one asks the browser what is actually animating, and asserts
    that the count matches the number of names the queues were told to
    run.
    """
    problems = []
    got = pg.evaluate("""() => {
      const out = {};
      for (const el of document.querySelectorAll('.puff b, .svcs b')) {
        const own = el.closest('.follow') || el.parentElement;
        const key = own.classList[1] || own.classList[0];
        const name = getComputedStyle(el).animationName;
        out[key] = out[key] || {total: 0, running: 0};
        out[key].total += 1;
        if (name && name !== 'none') out[key].running += 1;
      }
      return out; }""")
    want = {}
    for _q, _c, _at, who, _k, _t in C.queue_slots():
        want[who] = want.get(who, 0) + 1
    total = sum(want.values())
    live = sum(v["running"] for v in got.values())
    print("  %d of %d labels have an animation attached" % (live, total))
    for who, n in sorted(want.items()):
        g = got.get(who, {"total": 0, "running": 0})
        if g["running"] != n:
            problems.append(
                "%s has %d names in the queue but %d of its %d labels are "
                "actually animating -- the rule that drives them is not "
                "matching the element. Check the selector built in "
                "puff_css() in make_connect_chain.py"
                % (who, n, g["running"], g["total"]))
    return problems


def main():
    bad_early = []
    for line in art_is_stamped():
        bad_early.append(line)
    for line in alpha_is_smooth():
        bad_early.append(line)
    for line in labels_never_collide():
        bad_early.append(line)
    top_f = birds_at()
    print("  the topmost ink in the artwork sits at %.3f of its height"
          % top_f)
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT)],
                           cwd=ROOT, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
    time.sleep(2)
    bad = list(bad_early)
    try:
        with sync_playwright() as p:
            b = p.webkit.launch()
            for w, h in WIDTHS:
                ctx = b.new_context(viewport={"width": w, "height": h},
                                    device_scale_factor=2, is_mobile=True,
                                    has_touch=True)
                pg = ctx.new_page()
                pg.goto(URL, wait_until="domcontentloaded")
                pg.wait_for_timeout(1600)
                m = pg.evaluate(BOXES)
                hero, ai, btn = m["hero"], m["ai"], m["btn"]
                H = hero["b"] - hero["t"]
                head = round(hero["t"] + HEAD * H)
                feet = round(hero["t"] + FEET * H)
                over_ai = head - ai["b"]
                over_btn = btn["t"] - feet
                # Horizontal: if the figure is clear to the right of the
                # road block there is nothing to clear vertically.
                beside = hero["l"] >= ai["r"]
                print("  %4dx%-3d head clears the road by %+3d   feet clear the "
                      "button by %+3d   birds at %+4d   page %d in %d%s"
                      % (w, h, over_ai, over_btn,
                         round(hero["t"] + top_f * H), m["page"], m["vh"],
                         "  [figure is beside it]" if beside else ""))
                if not beside and over_ai < GAP:
                    bad.append("%dpx: the figure's head clears the road block "
                               "by %dpx, under the %dpx that stops it reading "
                               "as touching" % (w, over_ai, GAP))
                if over_btn < 0:
                    bad.append("%dpx: the figure runs %dpx behind the LinkedIn "
                               "button" % (w, -over_btn))
                # "Are all the birds at the top visible or cut?" On one
                # size of three they were cut: the panel is anchored to
                # the buttons, and on a short screen the buttons sit high
                # enough to push its top off the viewport.
                birds = hero["t"] + top_f * H
                if birds < 0:
                    bad.append("%dx%d: the birds at the top of the artwork "
                               "are cut off by %dpx -- the panel starts "
                               "above the screen" % (w, h, -birds))

                if (w, h) == WIDTHS[0]:
                    bad.extend(figures_never_flicker(pg))
                    bad.extend(labels_actually_animate(pg))
                    bad.extend(labels_fit(pg))
                    bad.extend(label_colours_read(pg, "light"))
                    pg.evaluate("() => document.documentElement"
                                ".setAttribute('data-theme','dark')")
                    pg.wait_for_timeout(300)
                    bad.extend(label_colours_read(pg, "dark"))
                    pg.evaluate("() => document.documentElement"
                                ".setAttribute('data-theme','light')")

                over = m["page"] - m["vh"]
                if over > 2:
                    bad.append("%dx%d: the card is %dpx taller than the "
                               "screen, so the footer needs a scroll -- it is "
                               "meant to be one screen" % (w, h, over))
                if m["attach"] == "fixed":
                    bad.append("%dpx: the paper is attachment:fixed, so it "
                               "stays still while the card scrolls" % w)
                ctx.close()

                    # ---- the colour the phone paints around the page ---------
            #
            # Sampled from the render rather than compared against a
            # constant, so the day the paper changes again this fails
            # instead of quietly going stale -- which is how it got three
            # points out in the first place.
            ctx = b.new_context(viewport={"width": 402, "height": 874},
                                device_scale_factor=2)
            pg = ctx.new_page()
            pg.goto(URL, wait_until="domcontentloaded")
            pg.wait_for_timeout(1600)
            declared = pg.evaluate(
                "()=>document.querySelector('meta[name=theme-color]')"
                ".getAttribute('content')")
            # Its own file, not a fixed name at the repo root. The hook
            # runs checks two at a time and retries failures, so two runs
            # of this check overlap -- and the shared path meant one could
            # delete the image the other was still reading. Worse, a run
            # that died between the write and the remove left a zero-byte
            # file behind, and every later run opened THAT and failed with
            # UnidentifiedImageError, which says nothing about the page and
            # never clears itself.
            fd, shot_path = tempfile.mkstemp(prefix="paper_top_",
                                             suffix=".png")
            os.close(fd)
            try:
                pg.screenshot(path=shot_path)
                ctx.close()
                shot = np.asarray(Image.open(shot_path).convert("RGB"),
                                  dtype=float)
            finally:
                try:
                    os.remove(shot_path)
                except OSError:
                    pass
            edge = np.median(shot[0:24].reshape(-1, 3), axis=0)
            want = tuple(int(declared.lstrip("#")[i:i + 2], 16)
                         for i in (0, 2, 4))
            off = max(abs(edge[i] - want[i]) for i in range(3))
            print("  theme-color %s, page's top edge #%02X%02X%02X, "
                  "worst channel off by %d"
                  % (declared, int(edge[0]), int(edge[1]), int(edge[2]), off))
            if off > 6:
                bad.append("theme-color %s is %d off the colour the page "
                           "actually paints at its top edge, so the band the "
                           "phone draws above the card does not match it"
                           % (declared, off))

            # ---- and the same page at night -----------------------------
            #
            # Dark mode is the same sheet stained dark, not a second
            # design, so the things that can go wrong are the same ones:
            # a band round the page that does not match it, type that
            # stops carrying, and -- the one that actually happened -- the
            # artwork's pale wash lighting up a rectangle, because low
            # alpha over white pixels lightens whatever is behind it.
            # The page follows the SUN now, not the OS preference, so
            # asking for a dark colour-scheme is no longer enough to see
            # the night sheet -- at 07:00 in Chicago it correctly ignores
            # you. The clock is pinned to 22:00 local instead.
            ctx = b.new_context(viewport={"width": 412, "height": 915},
                                device_scale_factor=2, is_mobile=True,
                                has_touch=True, timezone_id="America/Chicago")
            pg = ctx.new_page()
            pg.clock.install(time="2026-09-25T03:00:00Z")
            pg.goto(URL, wait_until="domcontentloaded")
            pg.wait_for_timeout(1800)
            night = pg.evaluate("""()=>{
              const cs = getComputedStyle(document.documentElement);
              const g = n => cs.getPropertyValue(n).trim();
              const meta = [...document.querySelectorAll('meta[name=theme-color]')]
                .filter(m => (m.media||'').includes('dark'))[0];
              return {paper: g('--paper'), ink: g('--ink'), muted: g('--muted'),
                      theme: meta ? meta.getAttribute('content') : null,
                      scene: getComputedStyle(document.querySelector('.hero'))
                               .backgroundImage};
            }""")
            pg.screenshot(path=os.path.join(ROOT, "_night.png"))
            ctx.close()
            shot = np.asarray(Image.open(os.path.join(ROOT, "_night.png"))
                              .convert("RGB"), dtype=float)
            os.remove(os.path.join(ROOT, "_night.png"))
            edge = np.median(shot[0:24].reshape(-1, 3), axis=0)
            field = np.median(shot[900:1500, 8:120].reshape(-1, 3), axis=0)

            def lin(c):
                c = c / 255.0
                return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

            def lum(t):
                return (0.2126 * lin(t[0]) + 0.7152 * lin(t[1])
                        + 0.0722 * lin(t[2]))

            def ratio(hexc, bg):
                t = tuple(int(hexc.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
                a, c = lum(t), lum(bg)
                hi, lo = max(a, c), min(a, c)
                return (hi + 0.05) / (lo + 0.05)

            ink_cr = ratio(night["ink"], field)
            muted_cr = ratio(night["muted"], field)
            want = tuple(int(night["theme"].lstrip("#")[i:i + 2], 16)
                         for i in (0, 2, 4))
            off = max(abs(edge[i] - want[i]) for i in range(3))
            print("  night: paper %s  ink %.1f:1  muted %.1f:1  "
                  "theme-color %s off by %d"
                  % (night["paper"], ink_cr, muted_cr, night["theme"], off))
            if ink_cr < 7:
                bad.append("at night the body ink is %.1f:1 on the page's own "
                           "background" % ink_cr)
            if muted_cr < 4.5:
                bad.append("at night the muted text is %.1f:1, under 4.5"
                           % muted_cr)
            if off > 8:
                bad.append("the dark theme-color is %d off the page's top "
                           "edge at night" % off)
            if "dusk" not in night["scene"]:
                bad.append("at night the artwork is the daylight cut -- its "
                           "pale wash lights a rectangle on the dark sheet")

            # ---- the switch ---------------------------------------------
            #
            # It is deliberately a small mark rather than a labelled
            # control, which makes it exactly the kind of thing that ends
            # up too small to hit and too quiet to find. So: the target is
            # measured, the tap has to actually change the sheet, and the
            # choice has to survive a reload.
            ctx = b.new_context(viewport={"width": 412, "height": 915},
                                device_scale_factor=2, is_mobile=True,
                                has_touch=True, timezone_id="America/Chicago")
            pg = ctx.new_page()
            pg.clock.install(time="2026-09-24T17:00:00Z")   # midday, so light
            pg.goto(URL, wait_until="domcontentloaded")
            pg.wait_for_timeout(1500)
            lamp = pg.evaluate("""()=>{
              const e = document.getElementById('lamp');
              if (!e) return null;
              const r = e.getBoundingClientRect();
              return {w: Math.round(r.width), h: Math.round(r.height),
                      x: Math.round(r.x + r.width/2),
                      y: Math.round(r.y + r.height/2),
                      theme: document.documentElement.dataset.theme};
            }""")
            if not lamp:
                bad.append("the card has no day/night switch")
            else:
                if lamp["w"] < 44 or lamp["h"] < 44:
                    bad.append("the switch is %dx%d, under the 44px floor "
                               "every other target on this site holds"
                               % (lamp["w"], lamp["h"]))
                pg.touchscreen.tap(lamp["x"], lamp["y"])
                pg.wait_for_timeout(600)
                flipped = pg.evaluate(
                    "()=>document.documentElement.dataset.theme")
                pg.reload(wait_until="domcontentloaded")
                pg.wait_for_timeout(900)
                kept = pg.evaluate(
                    "()=>document.documentElement.dataset.theme")
                print("  switch %dx%d: %s -> %s, still %s after a reload"
                      % (lamp["w"], lamp["h"], lamp["theme"], flipped, kept))
                if flipped == lamp["theme"]:
                    bad.append("tapping the switch did not change the sheet")
                if kept != flipped:
                    bad.append("the chosen sheet did not survive a reload "
                               "(%s became %s)" % (flipped, kept))
            ctx.close()

            # ---- the paper moves with the page --------------------------
            ctx = b.new_context(viewport={"width": 402, "height": 620},
                                device_scale_factor=2, is_mobile=True,
                                has_touch=True)
            pg = ctx.new_page()
            pg.goto(URL, wait_until="domcontentloaded")
            pg.wait_for_timeout(1600)
            pg.screenshot(path=os.path.join(ROOT, "_paper_s0.png"))
            pg.evaluate("window.scrollTo(0,200)")
            pg.wait_for_timeout(500)
            moved = pg.evaluate("()=>window.scrollY")
            pg.screenshot(path=os.path.join(ROOT, "_paper_s1.png"))
            ctx.close()
            b.close()

            a0 = np.asarray(Image.open(os.path.join(ROOT, "_paper_s0.png"))
                            .convert("L"), dtype=float)
            a1 = np.asarray(Image.open(os.path.join(ROOT, "_paper_s1.png"))
                            .convert("L"), dtype=float)
            os.remove(os.path.join(ROOT, "_paper_s0.png"))
            os.remove(os.path.join(ROOT, "_paper_s1.png"))
            # a strip of the left margin: bare paper at either position
            strip = (slice(200, 800), slice(4, 60))
            after = float(np.abs(a0[strip] - a1[strip]).mean())
            # what a genuine shift of this paper looks like, for scale
            genuine = float(np.abs(a0[200:800, 4:60]
                                   - a0[600:1200, 4:60]).mean())
            print("  scrolled %dpx: the paper strip changed by %.1f, and a "
                  "real shift of it changes by %.1f" % (moved, after, genuine))
            if after < genuine * 0.4:
                bad.append("the paper did not move when the page scrolled -- "
                           "it is pinned to the viewport while the card "
                           "slides over it")
    finally:
        srv.terminate()

    print()
    if bad:
        print("  PROBLEMS:")
        for line in bad:
            print("   -", line)
        return 1
    print("  The figure clears the pills and the first button at every width,")
    print("  and the paper moves with the page rather than under it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
