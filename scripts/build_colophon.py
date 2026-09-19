#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build /how-this-was-made/ -- what this site is, counted from the repo.

    python scripts/build_colophon.py

Why this exists
---------------
Asked for: "a feature in my menu where it says how I made it, so that when
readers open it they know the gist of how my website was made and what
components were touched -- something creative, something fun."

The usual version of this page is a list of logos and a sentence about a
framework, written once and wrong within a month. Every number here is counted
from the repository at build time instead: the posts are counted by listing
them, the checks by listing them, the scheduled jobs by reading
.github/workflows. If a number is on the page, something measured it -- which
is the same rule the events page follows, and the only reason either can claim
to be current.

The nav bar is untouched. It has 11px of slack at three widths, so a sixth tab
would mean renaming the two beside it; this lives in the sheet menu instead,
which is on all 278 pages and is where somebody looks for what else is here.

The head and the bar come from build_events_page, which takes them from
build_news_page. Three files each holding their own copy of that markup is how
the five headers drifted into four border colours, and a colophon that does
not match the site it describes would be a poor advertisement for the point
it is making.
"""
import io
import json
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)

from colophon_scenes import SCENES, VIEWBOX       # noqa: E402
from colophon_scene_css import SCENE_CSS          # noqa: E402
from colophon_architecture import ARCHITECTURE    # noqa: E402
from colophon_player_js import PLAYER_JS          # noqa: E402

OUT_DIR = os.path.join(ROOT, "how-this-was-made")


def esc(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def count(pattern_dir, *exts):
    d = os.path.join(ROOT, pattern_dir)
    if not os.path.isdir(d):
        return 0
    return sum(1 for f in os.listdir(d) if f.lower().endswith(exts))


def counted():
    """Every figure on the page, measured rather than typed.

    Deliberately not cached and not committed anywhere: the page is rebuilt
    on every publish, so the numbers are as old as the last build and no
    older. A stored count is a count that can be wrong quietly.
    """
    pages = 0
    for base, _dirs, files in os.walk(ROOT):
        if os.sep + "." in base or "_archive" in base:
            continue
        for f in files:
            if not f.endswith(".html"):
                continue
            try:
                with io.open(os.path.join(base, f), encoding="utf-8",
                             errors="replace") as fh:
                    # The whole file, not the first 4KB. Reading a prefix
                    # counted 122 of 278: a post page carries a long inline
                    # inline stylesheet before it links the shared one, so
                    # than half the site failed a test it passes.
                    if "site-footer.css" in fh.read():
                        pages += 1
            except OSError:
                continue

    checks = len([f for f in os.listdir(SCRIPTS)
                  if f.startswith("check_") and f.endswith(".py")])
    scripts = len([f for f in os.listdir(SCRIPTS) if f.endswith(".py")])
    flows = count(os.path.join(".github", "workflows"), ".yml", ".yaml")
    # Counted from what the blog actually publishes, not from the source
    # directory. posts/ holds 257 files and the blog index says 255 -- drafts
    # and one migration leftover. Two different numbers for "how many posts"
    # on two pages of the same site is exactly the kind of thing this page is
    # supposed to be above.
    posts = count("posts", ".html", ".md")
    cards = os.path.join(ROOT, "blog", "cards.json")
    if os.path.exists(cards):
        try:
            import json
            with io.open(cards, encoding="utf-8") as fh:
                posts = len(json.load(fh))
        except (OSError, ValueError):
            pass

    # Lines of hand-written code, excluding everything generated and every
    # binary. The first version of this number said 1,078,966 -- two thirds of
    # which were newline BYTES inside PNGs and mp3s, counted as lines. A
    # number nobody can check is worse than no number.
    loc = 0
    for rel_dir, exts in (("scripts", (".py",)),
                          (os.path.join("blog", "assets"), (".js", ".css")),
                          (os.path.join(".github", "workflows"),
                           (".yml", ".yaml"))):
        d = os.path.join(ROOT, rel_dir)
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if f.endswith(exts):
                try:
                    with io.open(os.path.join(d, f), encoding="utf-8",
                                 errors="replace") as fh:
                        loc += sum(1 for _ in fh)
                except OSError:
                    pass

    return {"pages": pages, "checks": checks, "scripts": scripts,
            "flows": flows, "posts": posts, "loc": loc}


def commits():
    """How many commits, if git is here. Absent rather than guessed."""
    try:
        out = subprocess.check_output(["git", "rev-list", "--count", "HEAD"],
                                      cwd=ROOT, stderr=subprocess.DEVNULL)
        return int(out.decode().strip())
    except Exception:                                       # noqa: BLE001
        return None


CRON = re.compile(r"cron:\s*[\"']([^\"']+)[\"']")


def schedules():
    """The scheduled jobs, read from the workflow files themselves."""
    d = os.path.join(ROOT, ".github", "workflows")
    out = []
    if not os.path.isdir(d):
        return out
    for f in sorted(os.listdir(d)):
        if not f.endswith((".yml", ".yaml")):
            continue
        try:
            src = io.open(os.path.join(d, f), encoding="utf-8",
                          errors="replace").read()
        except OSError:
            continue
        m = CRON.search(src)
        if not m:
            continue
        out.append((f.rsplit(".", 1)[0], m.group(1).strip()))
    return out


def when(expr):
    """A cron line as a person would say it."""
    parts = expr.split()
    if len(parts) != 5:
        return expr
    mi, hr, _dom, _mon, dow = parts
    if hr == "*":
        return "every hour"
    try:
        t = "%02d:%02d UTC" % (int(hr), int(mi))
    except ValueError:
        return expr
    days = {"1": "Mondays", "2": "Tuesdays", "3": "Wednesdays",
            "4": "Thursdays", "5": "Fridays", "6": "Saturdays",
            "0": "Sundays"}
    if dow in days:
        return "%s, %s" % (days[dow], t)
    return "daily, %s" % t



# The seven stops, in the order they actually happen. Each one names the file
# that does it, because a walkthrough that says "then it builds" is a cartoon;
# naming sync_blog.py means a reader can go and look.
# What the voice says, one line per scene.
#
# Asked for: "a voice over explaining the moving parts of the whole
# architecture." So this is not the on-screen text read aloud -- that text is
# written to be scanned, and reading it out loud sounds like a form being
# filled in. These lines name the moving part, say what it does, and say what
# would go wrong without it.
#
# Deliberately free of live figures. The counters on this page are measured at
# build time and change every week; a voice that says "two hundred and
# fifty-five posts" is wrong by the next publish and, unlike the text, cannot
# be rebuilt from the repository without re-synthesising audio. The one number
# kept is fifty checks, because that is the claim the section is making and it
# is checked by check_instrument_glyphs' sibling, preflight itself.
NARRATION = [
    "This site has no database, no content management system and no server. "
    "It starts here: an idea, away from the desk.",

    "A post is one hand-written file. It is the only thing on this site that "
    "is not generated, and everything you see is built from it.",

    "Before anything is built, the draft is checked. Are the claims "
    "supported, do the links resolve, does the page have the structure its "
    "series expects. A post with a dead citation does not get to become a "
    "page.",

    "Then one file becomes the whole site. Every post page, the index, the "
    "paged archive, the tag and year data, the feed, the sitemap and the "
    "offline worker. Each page is stamped with a fingerprint of the shared "
    "stylesheet and script, so you can never be served last "
    "week's design with this week's words.",

    "Nothing ships on trust. Fifty checks drive a real browser over the real "
    "pages: does the header hold still, does the music button actually play, "
    "does a filter filter, is every link alive. If one fails, the push is "
    "refused and the change never leaves this machine.",

    "What ships is only files. They are served straight from GitHub Pages, so "
    "there is no server to deploy, nothing to restart, and nothing to fall "
    "over in the middle of the night.",

    "This is the part that buys the time back. Jobs on a clock read the three "
    "clouds' own status feeds, release feeds and event directories, rebuild "
    "What's New, Live Status, Cloud Events and the Intelligence hub, and "
    "commit them by themselves. The pages stay current whether or not I open "
    "a laptop.",

    "And the archive answers for itself. A question is matched against what "
    "is actually written in these posts, and the answer cites the post it "
    "came from, so it can say that nothing here covers it instead of "
    "inventing something that sounds right.",
]


# Icons as SVG, not as characters.
#
# Reported with a screenshot: the expand control was rendering as an ICE
# SKATE on an iPhone. U+26F6 and U+26F8 are "square four corners" and "ice
# skate", they sit next to each other in the block, and iOS draws both as
# colour emoji -- so a geometric symbol became a picture of a boot. The
# speaker was a colour emoji too, next to two monochrome outlines.
#
# This is the flute bug again in a different costume: a character is a
# request, and the device decides what to draw. An inline path is a drawing.
# These are 14px, stroked in currentColor, so they inherit the bar's ink and
# cannot be substituted by anything.
def _svg(body):
    return ('<svg viewBox="0 0 24 24" width="14" height="14" fill="none" '
            'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            'stroke-linejoin="round" aria-hidden="true" '
            'focusable="false">%s</svg>' % body)

IC_PLAY   = _svg('<path d="M8 5l11 7-11 7V5z" fill="currentColor" '
                 'stroke="none"/>')
IC_PAUSE  = _svg('<path d="M9 5v14M15 5v14"/>')
IC_SOUND  = _svg('<path d="M5 9v6h4l5 4V5L9 9H5z"/>'
                 '<path d="M17.5 8.5a5 5 0 0 1 0 7"/>')
IC_MUTED  = _svg('<path d="M5 9v6h4l5 4V5L9 9H5z"/>'
                 '<path d="M17 9.5l4 5M21 9.5l-4 5"/>')
IC_REPLAY = _svg('<path d="M3.5 12a8.5 8.5 0 1 0 2.6-6.1"/>'
                 '<path d="M6 3v4h4"/>')
IC_EXPAND = _svg('<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>')
IC_SHRINK = _svg('<path d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5"/>')


STOPS = [
    ("a deck chair, usually", "The idea",
     "It starts away from the desk. Somewhere quiet, a laptop, a coffee, and "
     "something worth writing down before it goes.",
     "no ticket, no sprint"),
    ("posts/arch-042-....html", "Write it",
     "One file per post, written by hand. It is the only thing here that is "
     "not generated, and every page a reader sees is built from it.",
     "1 file, by hand"),
    ("prepublish.py", "Check the draft",
     "Before anything is built: are the claims supported, do the links "
     "resolve, does the page have the structure its series expects. A post "
     "with a dead citation does not get to become a page.",
     "runs first, refuses early"),
    ("sync_blog.py", "Build the site",
     "One file becomes every post page, the index, the paged archive, the "
     "tag and year data, the RSS feed, the sitemap and the service worker "
     "&mdash; each stamped with a hash of the shared CSS and JavaScript so "
     "nobody is served last week&rsquo;s stylesheet.",
     "255 posts → 279 pages"),
    ("preflight.py", "Open it in a browser",
     "50 checks drive a real browser: does the header hold still, does the "
     "music button actually play, does a filter filter, is every link alive. "
     "If one fails the push is refused &mdash; the change never leaves this "
     "machine.",
     "50 checks, ~12 minutes"),
    ("git push", "Ship it",
     "GitHub Pages serves the files directly. No server to deploy, no "
     "container to restart, nothing to fall over at 2am.",
     "static files, straight out"),
    (".github/workflows", "Then it runs without me",
     "This is the part that buys the time back. Seven jobs on a clock read "
     "the clouds&rsquo; own status, release feeds and event directories, "
     "rebuild the pages and commit them &mdash; so What&rsquo;s new, Live "
     "status, Cloud events and the Intelligence hub are current whether or "
     "not I open a laptop.",
     "7 jobs, 4 pages, 0 hands"),
    ("the ask terminal", "Ask it anything",
     "And the archive answers for itself. A question is matched against what "
     "is actually written in these posts and the answer cites the post it "
     "came from &mdash; retrieval first, so it can say &ldquo;nothing here "
     "covers that&rdquo; instead of inventing something.",
     "grounded in 255 posts"),
]


# The walkthrough's script.
#
# Inline and small, because this is the only page with a journey on it and
# putting it in site-footer.js would ship it to 278 pages that have none.
#
# It starts when the section is actually on screen rather than on load: a
# walkthrough that finished before the reader scrolled to it has walked alone.
# IntersectionObserver rather than a scroll handler, so nothing runs on every
# frame of every scroll, and it pauses when scrolled away or when the tab is
# hidden -- a backgrounded tab should not run a timer for an hour.
#
# prefers-reduced-motion lights every stop at once and never starts the timer.
# The information is the seven steps; the travelling is decoration, and
# somebody who asked their system for less movement asked for exactly that.


STYLE = """
<style>
  body { margin: 0; background: var(--bg, var(--surface, #1F1D1B));
         color: var(--tx, var(--text, #EDEBE6));
         font-family: 'DM Sans', system-ui, sans-serif; }
  .cf-wrap { max-width: 54rem; margin: 0 auto; padding: 2rem 1.25rem 5rem; }
  .cf-wrap h1 { font-family: 'Playfair Display', Georgia, serif;
                font-size: 1.9rem; margin: 0 0 .4rem; font-weight: 600; }
  .cf-lede { color: var(--mut, var(--text-muted, #9C9A94));
             font-size: .95rem; line-height: 1.65; margin: 0 0 .5rem;
             max-width: 44rem; }
  .cf-wrap h2 { font-family: 'Playfair Display', Georgia, serif;
                font-size: 1.15rem; font-weight: 600;
                margin: 2.6rem 0 .3rem; }
  .cf-note { color: var(--mut, var(--text-muted, #9C9A94));
             font-size: .9rem; line-height: 1.7; margin: .5rem 0 0;
             max-width: 44rem; }

  /* Counted, not typed -- so they are set as a grid of facts rather than
     buried in a sentence where a stale one could hide. */
  .cf-nums { display: grid; gap: .75rem; margin: 1.6rem 0 .5rem;
             grid-template-columns: repeat(3, minmax(0, 1fr)); }
  @media (max-width: 560px) { .cf-nums { grid-template-columns: 1fr 1fr; } }
  .cf-num { border: 1px solid var(--bd, var(--border, #33302C));
            border-radius: 10px; padding: .8rem .9rem; }
  .cf-num b { display: block; font-family: 'DM Mono', ui-monospace, monospace;
              font-size: 1.35rem; font-weight: 500; letter-spacing: -.01em; }
  .cf-num span { display: block; font-size: .72rem; letter-spacing: .08em;
                 text-transform: uppercase; margin-top: .2rem;
                 color: var(--mut, var(--text-muted, #9C9A94)); }

  /* The pipeline, as rows rather than as a diagram: a diagram has to be
     redrawn every time a builder is added, and this is generated. */
  .cf-flow { margin: 1rem 0 0; padding: 0; list-style: none; }
  .cf-flow li { display: grid; grid-template-columns: 11rem 1fr; gap: .9rem;
                padding: .62rem 0;
                border-top: 1px solid var(--bd, var(--border, #33302C)); }
  .cf-flow li:last-child { border-bottom: 1px solid
                           var(--bd, var(--border, #33302C)); }
  .cf-flow code { font-family: 'DM Mono', ui-monospace, monospace;
                  font-size: .78rem;
                  color: var(--acc-ink, var(--acc, #C4A484));
                  word-break: break-word; }
  .cf-flow p { margin: 0; font-size: .88rem; line-height: 1.6;
               color: var(--mut, var(--text-muted, #9C9A94)); }
  @media (max-width: 560px) {
    .cf-flow li { grid-template-columns: 1fr; gap: .2rem; }
  }

  /* The journey.
     -------------------------------------------------------------------------
     Nothing here changes size when a stop becomes active. The pin scales
     inside a box that is already its full size, and the text changes colour
     and nothing else -- so the animation cannot reflow the page under a
     reader, which is the property that matters more than the effect.

     The rail is one line behind the pins and a fill that grows down it. The
     fill is a scaleY transform rather than a height, so it animates on the
     compositor and costs nothing on a phone. */
  .cf-journey { position: relative; margin: 1.4rem 0 0; }
  .cf-rail { position: absolute; left: 7px; top: .8rem; bottom: .8rem;
             width: 2px; background: var(--bd, var(--border, #33302C));
             border-radius: 2px; }
  .cf-rail-fill { position: absolute; inset: 0; transform-origin: top;
                  transform: scaleY(0);
                  background: var(--acc-ink, var(--acc, #C4A484));
                  transition: transform .55s ease; }
  .cf-stops { list-style: none; margin: 0; padding: 0; }
  .cf-stop { position: relative; padding: .55rem 0 .95rem 2.1rem;
             cursor: pointer; outline: none; }
  .cf-pin { position: absolute; left: 0; top: 1.05rem;
            width: 16px; height: 16px; border-radius: 50%;
            display: grid; place-items: center; }
  .cf-pin::before { content: ""; width: 9px; height: 9px; border-radius: 50%;
                    background: var(--bd, var(--border, #33302C));
                    transition: background .3s ease, transform .3s ease; }
  .cf-stop-h { margin: 0 0 .15rem; font-size: .93rem; }
  .cf-stop-h b { font-weight: 600; }
  .cf-stop-h code { font-family: 'DM Mono', ui-monospace, monospace;
                    font-size: .76rem; margin-left: .4rem;
                    color: var(--mut, var(--text-muted, #9C9A94)); }
  .cf-stop-p { margin: 0; font-size: .88rem; line-height: 1.6;
               color: var(--mut, var(--text-muted, #9C9A94)); }
  .cf-tag { display: inline-block; margin-top: .35rem;
            font-family: 'DM Mono', ui-monospace, monospace;
            font-size: .66rem; letter-spacing: .07em; text-transform: uppercase;
            color: var(--mut, var(--text-muted, #9C9A94)); opacity: .75; }

  /* Everything is legible before any of this applies. The active state only
     brightens; the resting state is not dimmed below readable. */
  .cf-stop.is-on .cf-pin::before { background: var(--acc-ink, var(--acc, #C4A484));
                                   transform: scale(1.55); }
  .cf-stop.is-on .cf-stop-h b { color: var(--acc-ink, var(--acc, #C4A484)); }
  .cf-stop.is-on .cf-stop-p { color: var(--tx, var(--text, #EDEBE6)); }
  .cf-stop.is-on .cf-tag { opacity: 1; }
  .cf-stop:focus-visible { border-radius: 8px;
                           box-shadow: 0 0 0 2px var(--acc-ink, #C4A484); }

  .cf-ctl { display: flex; gap: .5rem; margin: .4rem 0 0 2.1rem; }
  .cf-btn { font: inherit; font-size: .76rem; cursor: pointer;
            padding: .28rem .7rem; border-radius: 999px;
            background: transparent; color: var(--mut, var(--text-muted, #9C9A94));
            border: 1px solid var(--bd, var(--border, #33302C)); }
  .cf-btn:hover { color: var(--tx, var(--text, #EDEBE6)); }
  /* No controls until the script is running them: a Pause button that pauses
     nothing is worse than no button. */
  .cf-ctl { display: none; }
  .cf-journey.is-live .cf-ctl { display: flex; }

  @media (prefers-reduced-motion: reduce) {
    .cf-rail-fill { transition: none; }
    .cf-pin::before { transition: none; }
  }

  .cf-jobs { width: 100%; border-collapse: collapse; margin-top: 1rem;
             font-size: .86rem; }
  .cf-jobs th { text-align: left; font-family: 'DM Mono', ui-monospace,
                monospace; font-size: .66rem; letter-spacing: .1em;
                text-transform: uppercase; font-weight: 500; padding: 0 0 .5rem;
                color: var(--mut, var(--text-muted, #9C9A94)); }
  .cf-jobs td { padding: .5rem 0;
                border-top: 1px solid var(--bd, var(--border, #33302C));
                vertical-align: top; }
  .cf-jobs td:first-child { font-family: 'DM Mono', ui-monospace, monospace;
                            font-size: .8rem; padding-right: 1rem; }
  .cf-jobs td:last-child { color: var(--mut, var(--text-muted, #9C9A94));
                           white-space: nowrap; }

  .cf-foot { margin-top: 2.8rem; font-size: .86rem;
             color: var(--mut, var(--text-muted, #9C9A94)); }
  .cf-foot a { color: var(--acc-ink, var(--acc, #C4A484)); }
""" + SCENE_CSS + """
</style>
"""


def build():
    import build_events_page as bep
    from asset_version import JS_VERSION

    jsv = JS_VERSION
    n = counted()
    ncommits = commits()

    b = []
    b.append('<div class="cf-wrap">')
    b.append("<h1>How this was made</h1>")
    b.append(
        '<p class="cf-lede">No framework, no build server, no database. This '
        'is plain HTML, CSS and JavaScript on GitHub Pages &mdash; the same '
        'free static hosting anybody gets with a repository &mdash; and a '
        'pile of Python that writes the pages before they ship.</p>')
    b.append(
        '<p class="cf-lede">Every number below is counted from the repository '
        'when this page is built, not typed in. That is the rule the whole '
        'site runs on: if a figure is on a page, something measured it.</p>')

    nums = [(n["posts"], "posts written"),
            (n["pages"], "pages published"),
            (n["scripts"], "python scripts"),
            (n["checks"], "checks before a push"),
            (n["flows"], "github workflows"),
            ("{:,}".format(n["loc"]), "lines behind it")]
    if ncommits:
        nums.append(("{:,}".format(ncommits), "commits"))
    b.append('<div class="cf-nums">')
    for v, label in nums:
        b.append('<div class="cf-num"><b>%s</b><span>%s</span></div>'
                 % (esc(v), esc(label)))
    b.append("</div>")

    b.append('<h2 id="journey">What happens when I publish</h2>')
    b.append(
        '<p class="cf-note">A post is a file. Everything a reader sees is '
        'built from it, which means the pages can always be thrown away and '
        'made again &mdash; and are, on every publish. Here is the whole trip '
        'a post takes, from the file to your screen.</p>')

    # The journey.
    #
    # Every stop is rendered, styled and readable BEFORE any script runs. The
    # animation only moves a marker down a line that is already there and
    # brightens one stop at a time -- it never inserts, removes or resizes
    # anything. That is deliberate and it is the same rule the live-status
    # glow follows: an effect that changes layout is an effect that can push
    # the page around while somebody is reading it.
    #
    # So with JavaScript off, with prefers-reduced-motion, or if the script
    # simply fails, this is a legible list of seven steps. The travelling is
    # the decoration, not the content.
    # The player.
    #
    # Rebuilt from a pile of buttons into something shaped like a video,
    # because that is what it is and that is what a reader already knows how
    # to use: "just show something like a YouTube video... why do we have all
    # those options at the bottom, can't it be just below the video".
    #
    # What went, and why:
    #
    #   the list of eight steps    Its words are the subtitles now. Printing
    #                              them twice, once as a list and once as a
    #                              caption, is the same thought in two places
    #                              -- and the architecture diagram below is
    #                              the map, so nothing is lost.
    #   previous / next buttons    Replaced by the scrubber. A seek bar says
    #                              where you are AND where you can go; two
    #                              step buttons say neither.
    #   "Play with narration"      The voice is the point, so it is simply on.
    #                              A reader who wants it quiet presses mute,
    #                              which is where everyone looks anyway.
    #   the "Expand" text button   A corner icon on the picture, the way every
    #                              video player has done it for fifteen years.
    #
    # One <svg>, eight groups, one visible, aria-hidden because each drawing
    # restates the caption beside it.
    b.append('<div class="cf-player" data-stage>')
    b.append('<div class="cf-scene">')
    b.append('<svg viewBox="%s" preserveAspectRatio="xMidYMid meet" '
             'aria-hidden="true" focusable="false">%s</svg>'
             % (VIEWBOX, "".join(SCENES[i] for i in sorted(SCENES))))

    # Everything lives INSIDE the frame, the way a video does.
    #
    # "Just have the video, have all those options within the video. Why do we
    # have that line underneath? When users check subtitles it has all the
    # information, so why do we need something below it."
    #
    # Right. A caption under the picture is a second thing to read; a caption
    # ON the picture is the picture talking. So the subtitle and the controls
    # are overlaid, and nothing at all follows the frame.
    b.append('<button type="button" class="cf-big" data-journey-big '
             'aria-label="Play">%s</button>' % IC_PLAY)
    b.append('<div class="cf-bar">')
    b.append('<button type="button" class="cf-play" data-journey-play '
             'aria-label="Play">%s</button>' % IC_PLAY)
    # A TIME scrubber, not eight scene stops.
    #
    # Reported as: "the video came at the end, but the animation and the
    # audio were still in progress... the scrolling has literally stopped."
    #
    # Exactly what it did. The bar had one position per scene, and the last
    # scene begins at 104.7s of 119.2s -- so the thumb reached the far right
    # with 14.5 seconds still to play and sat there, finished, while the
    # voice carried on. Every scene did this to a smaller degree; the last
    # one just did it for a quarter of a minute.
    #
    # In milliseconds, stepped at 200 so a drag feels continuous.
    total = 0
    try:
        _cp = os.path.join(ROOT, "blog", "assets", "audio", "walkthrough",
                           "cues.json")
        total = int(json.load(io.open(_cp, encoding="utf-8")).get("duration")
                    or 0)
    except Exception:
        total = 0
    b.append('<input type="range" class="cf-seek" data-seek min="0" max="%d" '
             'value="0" step="200" aria-label="Position in the walkthrough">'
             % (total or (len(STOPS) - 1)))
    # And the clock he asked for: "I don't see any sort of timer -- how long
    # has it been running, when does it end."
    b.append('<span class="cf-time" data-time>0:00<span class="cf-of"> / '
             '%d:%02d</span></span>' % (total // 60000, (total // 1000) % 60))
    # CC, where every player puts it: on the right, next to the sound.
    #
    # It was dropped in the simplification pass and asked for straight back:
    # "why doesn't it have a subtitles option -- at least to disable and
    # enable, like YouTube." Subtitles carry the whole script here, so they
    # are ON unless somebody says otherwise, and the choice is remembered.
    b.append('<button type="button" class="cf-icon cf-cc" data-journey-cc '
             'aria-pressed="false" aria-label="Turn subtitles on" '
             'title="Subtitles">CC</button>')
    b.append('<button type="button" class="cf-icon" data-journey-mute '
             'aria-pressed="false" aria-label="Mute">%s</button>' % IC_SOUND)
    b.append('<button type="button" class="cf-icon" data-journey-replay '
             'aria-label="Start again" title="Start again">%s</button>'
             % IC_REPLAY)
    b.append('<button type="button" class="cf-icon" data-journey-zoom '
             'aria-label="Expand" title="Expand">%s</button>' % IC_EXPAND)
    b.append("</div>")          # .cf-bar
    # The caption is a SIBLING of the picture, not a child of it.
    #
    # .cf-scene clips its overflow -- it has a border radius, and the drawing
    # has to stay inside it. So a caption parked below the scene's box while
    # living inside it was measured at exactly the right place and painted
    # nowhere: clipped, invisible, and measurable as present. Out here it can
    # sit over the picture when the player is inline and under it when the
    # player is expanded, which is the whole point.
    b.append('<p class="cf-cap" data-caption></p>')
    b.append("</div>")          # .cf-scene
    # The cue list: what is said, and when, per scene.
    #
    # Written by build_narration_audio.py from the service's own sentence
    # boundaries. Inlined rather than fetched -- it is about 4KB and a second
    # request to show a subtitle is a second thing that can fail.
    cues_path = os.path.join(ROOT, "blog", "assets", "audio",
                             "walkthrough", "cues.json")
    cues = {"lines": []}
    if os.path.exists(cues_path):
        try:
            cues = json.load(io.open(cues_path, encoding="utf-8"))
        except ValueError:
            cues = {"lines": []}
    b.append('<script type="application/json" data-cues>%s</script>'
             % json.dumps(cues, ensure_ascii=False, separators=(",", ":")))
    b.append('<script type="application/json" data-icons>%s</script>'
             % json.dumps({"play": IC_PLAY, "pause": IC_PAUSE,
                           "sound": IC_SOUND, "muted": IC_MUTED,
                           "expand": IC_EXPAND, "shrink": IC_SHRINK}))
    b.append("</div>")

    # The same story as one picture.
    #
    # The eight scenes are a walkthrough -- one step at a time, which is the
    # right shape for following along and the wrong shape for "show me the
    # whole thing". This is that other view, and it is the one somebody sends
    # to a colleague.
    b.append('<h2 id="architecture">Everything, in one picture</h2>')
    b.append(
        '<p class="cf-note">The same trip, laid out at once: what is written '
        'by hand, what Python builds from it, what stands between the two, '
        'and what a reader finally opens. Every box names a real file in the '
        'repository &mdash; a check refuses this page if one of them stops '
        'existing.</p>')
    b.append('<div class="cf-arch">%s</div>' % ARCHITECTURE)
    b.append('<p class="cf-arch-hint">scroll the diagram sideways &rarr;</p>')

    jobs = schedules()
    b.append("<h2>How it stays current</h2>")
    b.append(
        # "%d of those %d" rather than a bare count. The tile above says 13
        # and only 7 carry a cron -- the rest run on a push or a pull request
        # -- and a page whose own two numbers disagree has no business
        # lecturing anybody about measuring things.
        '<p class="cf-note">%d of those %d run on a clock, on '
        'GitHub&rsquo;s machines rather than mine. They fetch, rebuild and '
        'commit on their own &mdash; the cloud pages are current whether or '
        'not I have opened a laptop. The rest run when something is '
        'pushed.</p>' % (len(jobs), n["flows"]))
    if jobs:
        b.append('<table class="cf-jobs"><thead><tr><th>Job</th>'
                 "<th>Does</th><th>When</th></tr></thead><tbody>")
        said = {
            "status": "fetch every cloud's incidents, rebuild Live status",
            "ingest-news": "ingest announcements, rebuild What&rsquo;s new",
            "refresh-events": "re-import events from the vendors",
            "verify-events": "open every event link, reconcile what is missing",
            "refresh-aws-services": "refresh the AWS service catalogue",
            "doc-freshness": "flag documentation going stale",
            "health": "rebuild the health report",
        }
        for name, cron in jobs:
            b.append("<tr><td>%s</td><td>%s</td><td>%s</td></tr>"
                     % (esc(name), said.get(name, "scheduled maintenance"),
                        esc(when(cron))))
        b.append("</tbody></table>")

    b.append("<h2>What runs before anything ships</h2>")
    b.append(
        '<p class="cf-note">%d checks, in a real browser, on every push. They '
        'do not read the code &mdash; they open the pages and look: does the '
        'header hold still, does the music button actually play, does a '
        'filter filter, does every link still resolve, is each page asking '
        'for the current stylesheet. If one fails, the push is refused. It '
        'costs about twelve minutes, which is the price of not finding out '
        'from a reader.</p>' % n["checks"])

    b.append("<h2>Ask it anything</h2>")
    b.append(
        '<p class="cf-note">The terminal on the portfolio answers questions '
        'over these posts rather than from a model&rsquo;s memory: the '
        'question is matched against what is actually written here, and the '
        'answer cites the post it came from. If nothing here covers it, it '
        'says so instead of inventing something.</p>')

    b.append("<h2>Why it is built this way</h2>")
    b.append(
        '<p class="cf-note">Static files cannot be hacked through a plugin, '
        'cost nothing to serve, and load on a bad connection. Nothing here '
        'needs a server to be running, a subscription to be paid or a '
        'database to be backed up. In ten years these pages will open the '
        'same way, because they are just files.</p>')

    b.append(
        '<p class="cf-foot">The whole thing is public: '
        '<a href="https://github.com/katta698/katta698.github.io" '
        'target="_blank" rel="noopener">github.com/katta698/'
        'katta698.github.io</a></p>')
    b.append("</div>")

    head = bep.head_html(jsv)
    head = re.sub(r"<title>.*?</title>",
                  "<title>How this was made | Jayanth Katta</title>",
                  head, count=1, flags=re.S)
    head = re.sub(r'<meta name="description" content=".*?">',
                  '<meta name="description" content="How jayanthkatta.com is '
                  'built: static files on GitHub Pages, Python builders, '
                  'scheduled jobs and a browser-based check suite that runs '
                  'before every push.">', head, count=1, flags=re.S)
    head = re.sub(r'<link rel="canonical" href=".*?">',
                  '<link rel="canonical" '
                  'href="https://jayanthkatta.com/how-this-was-made/">',
                  head, count=1, flags=re.S)

    # No tab is current here.
    #
    # bep.nav_html() re-points aria-current at Intelligence, which is right
    # for the events page because it sits under that hub. This page sits under
    # nothing -- it is reached from the sheet menu -- so marking a tab would
    # tell a reader they are somewhere they are not, and leave the underline
    # sitting under the wrong word.
    nav = bep.nav_html().replace(' class="active" aria-current="page"', '')

    html = (head + STYLE + "</head>\n<body>\n" + nav + "\n"
            + "\n".join(b) + PLAYER_JS
            + bep.tail_html(jsv, "how-this-was-made"))

    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)
    out = os.path.join(OUT_DIR, "index.html")
    tmp = out + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html)
    os.replace(tmp, out)
    print("  %s" % os.path.relpath(out, ROOT))
    print("  %d posts, %d pages, %d scripts, %d checks, %d jobs, %s lines"
          % (n["posts"], n["pages"], n["scripts"], n["checks"], n["flows"],
             "{:,}".format(n["loc"])))
    print("  %.1fKB" % (os.path.getsize(out) / 1024.0))


if __name__ == "__main__":
    build()
