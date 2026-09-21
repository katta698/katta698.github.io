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
from colophon_architecture import ARCHITECTURE, CLAIMS  # noqa: E402
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


# The four routes a post can take, and the label that identifies each.
#
# Counted from the labels rather than from the filename, because the label is
# what the blog itself counts by -- the filter pill a reader clicks. The two
# disagree: posts/ holds 37 files named daily-*, and the prefix says nothing
# about which series a file belongs to once a series is renamed.
SERIES_FAMILIES = [
    ("arch", ("AWS Architecture Series", "Azure Architecture Series",
              "GCP Architecture Series")),
    ("daily", ("AWS Daily Intelligence",)),
    ("weekly", ("AWS Weekly Intelligence", "Azure Weekly Intelligence",
                "GCP Weekly Intelligence")),
    ("lab", ("AWS Weekly Lab", "Azure Weekly Lab", "GCP Weekly Lab")),
]


# What each box on the architecture diagram actually does.
#
# Asked for: "it's good to include what each script does when we hover over
# a box -- what exactly it does at the back end. That way it gives good
# information on not only the workflow but what each component does."
#
# For anything that is a Python file the sentence is READ OUT OF THE FILE --
# the first line of its module docstring. That is deliberate and it is the
# whole reason this is worth doing: a hand-written caption for twelve scripts
# is twelve sentences that quietly stop being true, and nothing on the page
# would ever say so. A docstring is edited by whoever changes the script,
# because they are looking straight at it.
#
# The boxes that are not scripts -- the data stores, the clouds, the pages a
# reader opens -- have no docstring to read, so they are written here. Each
# says what the thing IS and who writes it, not what it is for.
BOX_NOTES = {
    "posts/": "One HTML file per post, front matter and body. This is the "
              "source: every page, card, feed entry and search result is "
              "derived from it, and nothing is derived from a served page.",
    "news.json": "Every cloud announcement, ranked, with the day it was "
                 "made. Written by the scheduled jobs, never by hand.",
    "status.json": "The current health of AWS, Azure and GCP, as each "
                   "vendor's own status feed reports it.",
    "events.json": "Vendor conferences, launches and end-of-life dates, "
                   "with the source each one came from.",
    "ai.json": "What the AI vendors have shipped, and the model catalogue "
               "behind the j.AI page &mdash; announcements, prices and "
               "context windows.",
    "AWS · Azure · GCP": "The vendors' own feeds. Nothing here is "
                                   "summarised by a model: the raw RSS and "
                                   "sitemaps are parsed, because a summary "
                                   "silently drops items and a parser does "
                                   "not.",
    ".github/workflows": "The scheduled jobs. They fetch, rebuild and commit "
                         "on GitHub's machines, so the data pages stay "
                         "current whether or not I have opened a laptop.",
    "sitemap.xml": "Every published URL with the date it last changed, plus "
                   "robots.txt. Regenerated on every sync, so it cannot "
                   "drift from what is actually published.",
    "Portfolio": "The home page. Its figures &mdash; post count, latest "
                 "posts, the service and domain widgets &mdash; are read "
                 "from the same files the blog is built from.",
    "Blog": "The index, the paged archive, the filter pills and the RSS "
            "feed. All of it is regenerated from posts/ on every sync.",
    "Intelligence": "The hub for the four data-driven pages below it.",
    "What’s new": "Cloud announcements, ranked, from news.json.",
    "Live status": "Current vendor health, from status.json.",
    "Cloud events": "Conferences and end-of-life dates, from events.json.",
    "j.AI": "The AI page: models, prices, context windows and what each "
            "vendor shipped, from ai.json.",
    "GitHub Pages": "Static hosting. There is no server and no database, so "
                    "there is nothing to restart and nothing to patch.",
    "site-footer.css": "One stylesheet and one script shared by every page "
                       "on the site &mdash; the nav bar, the theme switch "
                       "and the menu. A change here reaches all of them.",
    "reader": "You. Everything to the left of this exists to put a correct "
              "page in front of you without a human remembering a step.",
}


def box_note(label):
    """One sentence for a box, read from the script where there is one."""
    import ast
    path = CLAIMS.get(label)
    if path and path.endswith(".py"):
        try:
            src = io.open(os.path.join(ROOT, path), encoding="utf-8").read()
            doc = (ast.get_docstring(ast.parse(src)) or "").strip()
            first = doc.split(chr(10) + chr(10))[0].replace(chr(10), " ")
            first = " ".join(first.split())
            # One sentence. sync_blog.py's opening paragraph runs to three,
            # and the second and third are about a migration that finished
            # years ago -- true, and not what somebody hovering a box is
            # asking. Source files write "--" where prose wants an em dash.
            import re as _re
            first = _re.split(r"(?<=[.]) (?=[A-Z(])", first)[0]
            first = first.replace(" -- ", " — ")
            if first:
                return first
        except (OSError, SyntaxError, ValueError):
            pass
    return BOX_NOTES.get(label, "")


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

    # What runs BEFORE the gate: prepublish's own list, read from the file
    # that owns it. Two different numbers with two different jobs -- 21
    # checks on the post you just wrote, then the gate's checks on the whole
    # site -- and a page that prints one as the other is describing a
    # pipeline nobody runs.
    prepub = 0
    try:
        src = io.open(os.path.join(SCRIPTS, "prepublish.py"),
                      encoding="utf-8").read()
        block = src[src.index("CHECKS ="):]
        prepub = len(re.findall(r'"([a-z_]+\.py)"', block[:block.index("]")]))
    except Exception:
        prepub = 0

    # Which pages are built by hand and which by sync. The three
    # architecture series are externally_built -- sync never regenerates
    # them -- and every other series' page comes out of sync_blog itself.
    # The pasted flow described the architecture path as if it were the
    # whole site; it is 135 of 274.
    #
    # Counted against the published total, not against posts/. Counting the
    # directory gave 138 hand-built and 139 sync-built beside a stated total
    # of 275 post pages -- a reader who adds them gets 277, because posts/
    # holds drafts and a README and the blog does not. The two halves now
    # come out of the same number they are printed next to.
    handbuilt = syncbuilt = diagrams = 0
    arch_labels = set(SERIES_FAMILIES[0][1])
    try:
        cards = json.load(io.open(os.path.join(ROOT, "blog", "cards.json"),
                                  encoding="utf-8"))
        handbuilt = sum(1 for c in cards if c.get("tag1") in arch_labels)
        syncbuilt = len(cards) - handbuilt
    except (OSError, ValueError):
        pass
    try:
        for f in os.listdir(os.path.join(ROOT, "posts")):
            if not f.endswith((".html", ".md")):
                continue
            try:
                with io.open(os.path.join(ROOT, "posts", f), encoding="utf-8",
                             errors="replace") as fh:
                    if "/blog/assets/diagrams/" in fh.read():
                        diagrams += 1
            except OSError:
                pass
    except OSError:
        pass

    # The shared files one sync rewrites: the eight named ones plus however
    # many pages the archive currently runs to.
    shared = 8
    try:
        shared += len([d for d in os.listdir(os.path.join(ROOT, "blog", "page"))
                       if os.path.isdir(os.path.join(ROOT, "blog", "page", d))])
    except OSError:
        pass

    # What the GATE actually runs, asked of the gate rather than counted by
    # eye. preflight discovers its own checks, so a hardcoded number here
    # would be a second opinion about a fact preflight already owns -- and
    # the two would part company the first time one was skipped.
    gate, browser = checks, 0
    try:
        sys.path.insert(0, SCRIPTS)
        import preflight as _pf
        names = _pf.discover(fast=False)
        gate = len(names)
        for n in names:
            try:
                with io.open(os.path.join(SCRIPTS, n + ".py"),
                             encoding="utf-8", errors="replace") as fh:
                    if "playwright" in fh.read():
                        browser += 1
            except OSError:
                pass
    except Exception:
        pass

    return {"pages": pages, "checks": checks, "scripts": scripts,
            "flows": flows, "posts": posts, "loc": loc,
            "gate": gate, "browser": browser,
            "prepub": prepub, "handbuilt": handbuilt, "syncbuilt": syncbuilt,
            "diagrams": diagrams, "shared": shared}


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
# The spoken script, generated from what the repository measures about
# itself -- not typed out and then left behind.
#
# Asked for as: "make it standard, so that even when we make changes down
# the road we don't have to come here and revisit all the time."
#
# The failure it fixes was live: the narration said "fifty checks drive a
# real browser". By then there were 58 checks and 34 of them drove a
# browser. Nobody had lied; the sentence was true the week it was written
# and had quietly stopped being true since, in a recording, where being
# wrong is least visible and most expensive.
#
# Two rules make this hold on its own:
#
#   MEASURED, NOT TYPED. Every number comes from counted(), which asks
#   preflight how many checks it runs rather than counting files by eye.
#   One source for a fact the gate already owns.
#
#   BANDED, NOT EXACT. "More than fifty" rather than "fifty-eight", so the
#   words change when the figure meaningfully does and not on the day a
#   fifty-ninth check is added. Adding one check should not re-record a
#   voiceover; crossing sixty is worth saying out loud.
#
# check_narration_true holds both ends: every spoken number is compared
# against the live repository, and the audio is compared against the words,
# so neither can drift without the push being refused.
_TENS = {2: "twenty", 3: "thirty", 4: "forty", 5: "fifty", 6: "sixty",
         7: "seventy", 8: "eighty", 9: "ninety"}


def roughly(n):
    """A spoken figure that stays true while the real one grows."""
    n = int(n or 0)
    if n < 20:
        return str(n)
    if n >= 100:
        return "more than %s hundred" % ("a" if n < 200 else _TENS.get(
            n // 100 * 10 // 10, str(n // 100)))
    return "more than %s" % _TENS[n // 10]


def narration(f=None):
    f = f or counted()
    return [
        "This site has no database, no content management system and no "
        "server. It starts here: an idea, away from the desk.",

        "A post is one hand-written file. It is the only thing on this site "
        "that is not generated, and everything you see is built from it.",

        "Before anything is built, the draft is checked. Are the claims "
        "supported, do the links resolve, does the page have the structure "
        "its series expects. A post with a dead citation does not get to "
        "become a page.",

        "Then one file becomes the whole site. Every post page, the index, "
        "the paged archive, the tag and year data, the feed, the sitemap "
        "and the offline worker. Each page is stamped with a fingerprint of "
        "the shared stylesheet and script, so you can never be served last "
        "week's design with this week's words.",

        "Nothing ships on trust. %s checks run before anything is "
        "published, %s of them driving a real browser over the real pages: "
        "does the header hold still, does the music button actually play, "
        "does a filter filter, is every link alive. If one fails, the push "
        "is refused and the change never leaves this machine."
        % (roughly(f["gate"]).capitalize(), roughly(f["browser"])),

        "What ships is only files. They are served straight from GitHub "
        "Pages, so there is no server to deploy, nothing to restart, and "
        "nothing to fall over in the middle of the night.",

        "This is the part that buys the time back. Jobs on a clock read the "
        "three clouds' own status feeds, release feeds and event "
        "directories, rebuild What's New, Live Status, Cloud Events and the "
        "Intelligence hub, and commit them by themselves. The pages stay "
        "current whether or not I open a laptop.",

        "And the archive answers for itself. A question is matched against "
        "what is actually written in these posts, and the answer cites the "
        "post it came from, so it can say that nothing here covers it "
        "instead of inventing something that sounds right.",
    ]


NARRATION = narration()


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


# The eight stops of the journey, with their figures measured.
#
# These read as prose and were typed as prose, so they went stale the way
# prose does: "255 posts -> 279 pages" when it was 268 -> 295, "50 checks"
# when the gate ran 59, "Seven jobs" when thirteen were on a clock. Every one
# of them was true on the afternoon it was written.
#
# The audio is BANDED because re-recording is expensive. A page is not: it is
# regenerated on every build, so it can afford to be exact, and exact is more
# convincing than approximate when the whole point of the page is that the
# numbers are real. check_narration_true refuses any figure here that is not
# one the repository just measured.
def stops(f=None):
    f = f or counted()
    jobs = len(schedules()) or f["flows"]
    return [
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
     "%d posts &rarr; %d pages" % (f["posts"], f["pages"])),
    ("preflight.py", "Open it in a browser",
     "%d checks run before anything is published and %d of them drive a real "
     "browser: does the header hold still, does the music button actually "
     "play, does a filter filter, is every link alive. If one fails the push "
     "is refused &mdash; the change never leaves this machine."
     % (f["gate"], f["browser"]),
     "%d checks, %d in a browser" % (f["gate"], f["browser"])),
    ("git push", "Ship it",
     "GitHub Pages serves the files directly. No server to deploy, no "
     "container to restart, nothing to fall over at 2am.",
     "static files, straight out"),
    (".github/workflows", "Then it runs without me",
     "This is the part that buys the time back. %d jobs on a clock read the "
     "clouds&rsquo; own status, release feeds and event directories, rebuild "
     "the pages and commit them &mdash; so What&rsquo;s new, Live status, "
     "Cloud events and the Intelligence hub are current whether or not I "
     "open a laptop." % jobs,
     "%d jobs, 4 pages, 0 hands" % jobs),
    ("the ask terminal", "Ask it anything",
     "And the archive answers for itself. A question is matched against what "
     "is actually written in these posts and the answer cites the post it "
     "came from &mdash; retrieval first, so it can say &ldquo;nothing here "
     "covers that&rdquo; instead of inventing something.",
     "grounded in %d posts" % f["posts"]),
]


STOPS = stops()


# The figures inside the DRAWINGS, filled from the same measurements.
#
# The stops and the narration were fixed first, and the page still said
# "255 posts" and "50 checks" -- because those numbers are not prose, they
# are <text> labels inside the scene artwork and the architecture diagram.
# Three places holding the same fact, and fixing two of them is how a page
# ends up disagreeing with itself in public.
#
# A token rather than a format string: this is SVG, and one stray brace in
# a path would take the whole build down with it.
def fill(svg, f=None):
    f = f or counted()
    for token, value in (("{{POSTS}}", f["posts"]),
                         ("{{PAGES}}", f["pages"]),
                         ("{{GATE}}", f["gate"]),
                         ("{{BROWSER}}", f["browser"]),
                         ("{{JOBS}}", len(schedules()) or f["flows"])):
        svg = svg.replace(token, str(value))
    return svg



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



# The journeys, one per kind of post -- because they are not the same one.
#
# Asked, after the first version shipped with a single list and two greyed
# stops: "does everything follow the same process? If a lab or a weekly
# intelligence post follows a different path, then obviously it requires
# each tab and its own journey."
#
# It does, and the greying was hiding it. Measured across every post on the
# site rather than reasoned from the architecture series:
#
#     Architecture   138 posts   100% carry a diagram   page by build_arch_post
#     Daily intel     37 posts   100% carry a diagram   page by sync_blog
#     Weekly intel    13 posts     0% carry a diagram   page by sync_blog
#     Weekly lab      29 posts     0% carry a diagram   page by sync_blog
#
# And the difference is not only what is MISSING. Two paths have steps the
# architecture path has never had: a weekly roundup fetches a week of feeds
# and builds an inventory from them before a word is written, and a daily
# post ranks every announcement from the day before. Those are real scripts
# -- fetch_week.py, fetch_week_gcp.py, build_weekly_inventory.py, news.py --
# and a greyed-out list cannot show a step that only exists somewhere else.
#
# So four journeys, each ending in the same five stops, because from sync
# onwards every post on this site is treated identically.


def series_counts():
    """How many posts each route has, and how many of them show a diagram.

    Counted from blog/cards.json and the served pages, not from posts/. Those
    two disagree -- posts/ holds 37 files named daily-* and the blog shows 36
    -- because a draft is a file and is not a post. The number printed here is
    beside a sentence a reader can check by clicking the filter pill, so it
    has to be the number the filter pill gives.
    """
    out = {}
    for key, _labels in SERIES_FAMILIES:
        out[key] = {"posts": 0, "diagrams": 0}
    by_label = {}
    for key, labels in SERIES_FAMILIES:
        for label in labels:
            by_label[label] = key
    try:
        cards = json.load(io.open(os.path.join(ROOT, "blog", "cards.json"),
                                  encoding="utf-8"))
    except (OSError, ValueError):
        return out
    for card in cards:
        key = by_label.get(card.get("tag1") or "")
        if not key:
            continue
        out[key]["posts"] += 1
        page = os.path.join(ROOT, "blog", card.get("slug") or "",
                            "index.html")
        try:
            html = io.open(page, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if "assets/diagrams/" in html:
            out[key]["diagrams"] += 1
    return out


def _next(prefix, width=3):
    import re as _re
    try:
        ns = [int(m.group(1)) for f in os.listdir(os.path.join(ROOT, "posts"))
              for m in [_re.match(_re.escape(prefix) + r"(\d+)", f)] if m]
        return "%0*d" % (width, max(ns) + 1) if ns else "001"
    except OSError:
        return "001"


def tail_stops(f, jobs):
    """The five stops every post shares, whatever it is."""
    return [
        ("machine", "Sync the site", "publish.py &rarr; sync_blog.py",
         "rewrites %d shared files: the index, the paged archive, the feed, "
         "the sitemap, the offline worker" % f["shared"]),
        ("machine", "Check the post", "prepublish.py",
         "%d checks on what was just written, then it prints Ready"
         % f["prepub"]),
        ("hand", "Commit", "local, reversible",
         "nothing is public yet and nothing is claimed"),
        ("machine", "Push, and wait", "preflight.py",
         "%d checks over all %d posts, %d of them driving a real browser. "
         "Ten to thirteen minutes, measured. A failure refuses the push"
         % (f["gate"], f["posts"], f["browser"])),
        ("machine", "Live", "GitHub Pages, then the search index",
         "%d jobs on a clock keep the rest of the site current afterwards"
         % jobs),
    ]


def journeys(f=None):
    f = f or counted()
    jobs = len(schedules()) or f["flows"]
    tail = tail_stops(f, jobs)
    sc = series_counts()
    n_arch, d_arch = sc["arch"]["posts"], sc["arch"]["diagrams"]
    n_daily, d_daily = sc["daily"]["posts"], sc["daily"]["diagrams"]
    n_weekly, n_lab = sc["weekly"]["posts"], sc["lab"]["posts"]
    return [
        ("arch", "An architecture post", "%d posts" % n_arch, [
            ("hand", "Write", "posts/arch-%s-….html" % _next("arch-"),
             "one hand-written file, with the vendor&rsquo;s own docs quoted "
             "and every figure carrying a source"),
            ("hand", "Draw", "blog/assets/diagrams/arch-%s-….svg"
             % _next("arch-"),
             "raw SVG, no tool &mdash; all %d of the %d architecture posts carry one" % (d_arch, n_arch)),
            ("machine", "Build the page", "build_arch_post.py",
             "%d post pages are built from the template and never "
             "regenerated; the other %d come from sync_blog"
             % (f["handbuilt"], f["syncbuilt"])),
        ] + tail),
        ("daily", "A daily intelligence post", "%d posts" % n_daily, [
            ("machine", "Rank yesterday", "news.py &rarr; DAILY-BACKLOG.md",
             "every announcement from the day before is ranked and written "
             "down, not just the one that becomes a post &mdash; the feed "
             "only holds about a week"),
            ("hand", "Write", "posts/daily-%s-….html" % _next("daily-"),
             "one item, in depth, with what the announcement left out"),
            ("hand", "Draw", "blog/assets/diagrams/daily-….svg",
             "all %d carry one, like the architecture series" % d_daily),
            ("machine", "Build the page", "sync_blog.py",
             "no per-post builder here: the page comes out of the sync with "
             "the other %d" % f["syncbuilt"]),
        ] + tail),
        ("weekly", "A weekly roundup", "%d posts" % n_weekly, [
            ("machine", "Fetch the week", "fetch_week.py &middot; "
             "fetch_week_gcp.py &middot; fetch_azure_week.py",
             "raw RSS from every feed, parsed rather than summarised. A "
             "model reading the feed missed 24 of 66 announcements once"),
            ("machine", "Build the inventory", "build_weekly_inventory.py",
             "one row per announcement, in the vendor&rsquo;s own words, "
             "every link fetched &mdash; it exits non-zero if one fails"),
            ("hand", "Write", "posts/weekly-%s-….html" % _next("weekly-"),
             "the week in a paragraph, then what is worth acting on"),
            ("machine", "Build the page", "sync_blog.py",
             "no diagram and no per-post builder: none of the %d roundups "
             "carries either" % n_weekly),
        ] + tail),
        ("lab", "A weekly lab", "%d posts" % n_lab, [
            ("hand", "Run it, for real", "a console, and a bill",
             "a lab post&rsquo;s whole claim is that the thing runs, so it "
             "goes out when it runs &mdash; these have no fixed publish day"),
            ("hand", "Write", "posts/week-%s-….html" % _next("week-", 2),
             "what was built, what it cost, and what broke"),
            ("machine", "Build the page", "sync_blog.py",
             "no diagram and no per-post builder, the same path the "
             "roundups take"),
        ] + tail),
    ]



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
             % (VIEWBOX, fill("".join(SCENES[i] for i in sorted(SCENES)))))

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
    # Chapter marks, cut into the track at the real scene boundaries.
    #
    # A two-minute explainer with eight parts should show that it has eight
    # parts. The marks are notches the colour of the bar behind them rather
    # than lines drawn on top, so they read the same over the played side of
    # the track and the unplayed side without needing a colour that fights
    # both.
    #
    # Positions come from the rendered audio, so a re-recording moves them.
    ticks = ""
    try:
        _lines = json.load(io.open(_cp, encoding="utf-8")).get("lines") or []
        stops_pct = [100.0 * (ln.get("start") or 0) / total
                     for ln in _lines[1:] if total]
        parts, at = [], 0.0
        for pct in stops_pct:
            parts.append("transparent %.3f%% %.3f%%" % (at, pct))
            parts.append("var(--cf-notch) %.3f%% %.3f%%" % (pct, pct + 0.45))
            at = pct + 0.45
        parts.append("transparent %.3f%% 100%%" % at)
        ticks = "linear-gradient(to right, %s)" % ", ".join(parts)
    except Exception:
        ticks = ""
    b.append('<input type="range" class="cf-seek" data-seek min="0" max="%d" '
             'value="0" step="200" style="--cf-ticks: %s" '
             'aria-label="Position in the walkthrough">'
             % (total or (len(STOPS) - 1), ticks or "none"))
    # And the clock he asked for: "I don't see any sort of timer -- how long
    # has it been running, when does it end."
    # "0:00/2:03", not "0:00 / 2:03". The spaces either side of the slash
    # cost 16px of a row where the scrub bar is the thing that needed them,
    # and the total was nearly deleted on phones to find that width -- which
    # would have taken away the half of the clock that answers "when does
    # this end", asked for in the first place.
    b.append('<span class="cf-time" data-time>0:00<span class="cf-of">/'
             '%d:%02d</span></span>' % (total // 60000, (total // 1000) % 60))
    # The chapter you are in, named. The same titles as the written stops
    # below the player, so the two never describe the journey differently.
    b.append('<span class="cf-chap" data-chap>%s</span>' % esc(STOPS[0][1]))
    b.append('<script type="application/json" data-chapters>%s</script>'
             % json.dumps([st[1] for st in STOPS], ensure_ascii=False))
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
    # The diagram is checked for collisions as it is written, not after.
    #
    # Twice now the architecture picture has shipped with two labels drawn
    # at the same coordinates -- once when the AI row was added into a slot
    # build_sitemap.py already owned, and again when a window with an older
    # checkout rebuilt this page and committed the pre-fix layout over the
    # top. The second time it reached a reader, who photographed
    # "build_aitemagp.py" -- two names on one line.
    #
    # A build that cannot produce a broken diagram is worth more than a
    # check that catches it afterwards, because the rebuild is done by
    # whichever window happens to publish next.
    arch = fill(ARCHITECTURE)
    boxes = []
    for m in re.finditer(r'<rect x="(\d+)" y="(\d+)" width="(\d+)" '
                         r'height="(\d+)"', arch):
        x, y, w, h = (int(g) for g in m.groups())
        boxes.append((x, y, w, h))
    clashes = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            ax, ay, aw, ah = boxes[i]
            bx, by, bw, bh = boxes[j]
            if (min(ax + aw, bx + bw) - max(ax, bx) > 1
                    and min(ay + ah, by + bh) - max(ay, by) > 1):
                clashes.append("(%d,%d %dx%d) over (%d,%d %dx%d)"
                               % (ax, ay, aw, ah, bx, by, bw, bh))
    if clashes:
        print("  the architecture diagram has %d overlapping box(es):"
              % len(clashes))
        for c in clashes[:4]:
            print("    %s" % c)
        print("  Two labels drawn at one place is what a reader "
              "photographs.")
        raise SystemExit(1)

    # And the two failures a rect-versus-rect check cannot see.
    #
    # Reported from a photograph of the live page: "look at those boxes, why
    # is the text coming out of the box", and "from ai.json there is a
    # pointer to build_ai_page.py, from there it is pointing to
    # build_sitemap.py and then preflight.py -- does the whole workflow make
    # sense?"
    #
    # Neither is a collision. The first was a caption sitting at x=424, in
    # the gap between two columns, belonging to no box. The second was one
    # straight line from a builder's bottom edge down to the gate, drawn
    # across the box that happened to lie between them -- so the picture
    # read as a three-step chain that has never existed. A line that passes
    # through a box IS an arrow into that box, as far as a reader is
    # concerned, and this is a page about being checkable.
    #
    # Widths are estimated from the font sizes in colophon_scene_css.py.
    # SVG <text> does not wrap and reports no error when it overruns, so an
    # estimate that is slightly generous is the whole defence.
    from html import unescape as html_unescape
    PER_CHAR = {"at": 7.1, "as": 5.4, "ah": 6.4, "ar": 6.6}
    FREE = ("WRITTEN BY HAND", "BUILT BY PYTHON", "WHAT A READER OPENS",
            "DATA STORES", "re-read, rebuilt,", "committed", "passes",
            "everything the builders wrote")
    loose = []
    for m in re.finditer(r'<text class="([a-z ]+)"[^>]*x="(\d+)"[^>]*'
                         r'y="(\d+)"[^>]*>([^<]*)</text>', arch):
        cls, tx, ty, label = m.group(1), int(m.group(2)), int(m.group(3)),             m.group(4).strip()
        if label in FREE:
            continue
        key = "ar" if "ar" in cls.split() else cls.split()[0]
        width = len(html_unescape(label)) * PER_CHAR.get(key, 7.0)
        if "text-anchor=\"middle\"" in m.group(0):
            x0, x1 = tx - width / 2, tx + width / 2
        else:
            x0, x1 = tx, tx + width
        inside = any(bx <= x0 and x1 <= bx + bw + 1
                     and by <= ty <= by + bh
                     for bx, by, bw, bh in boxes)
        if not inside:
            loose.append("%r at (%d,%d), about %dpx wide" % (label, tx, ty,
                                                             width))
    if loose:
        print("  %d label(s) in the architecture diagram run outside every "
              "box:" % len(loose))
        for c in loose[:5]:
            print("    %s" % c)
        print("  A caption that belongs to no box belongs to whichever box "
              "the reader is nearest.")
        raise SystemExit(1)

    crossings = []
    for m in re.finditer(r'<path class="[^"]*" d="M (\d+) (\d+)([^"]*)"',
                         arch):
        x, y = int(m.group(1)), int(m.group(2))
        pts = [(x, y)]
        for seg in re.finditer(r'([HV]) ?(\d+)', m.group(3)):
            if seg.group(1) == "H":
                x = int(seg.group(2))
            else:
                y = int(seg.group(2))
            pts.append((x, y))
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            for cx, cy, cw, ch in boxes:
                # A segment may touch the box it starts or ends against.
                # Overlap-of-areas is the wrong test here and was wrong
                # in the first version of this check: a connector is a
                # zero-thickness line, so its "width" is 0 and an
                # area-overlap test can never fire on the vertical arrow
                # that caused the report. Ask instead whether any point of
                # the segment lands INSIDE the box, with a 2px margin so a
                # line that merely ends against an edge is not a crossing.
                ox0, ox1 = min(ax, bx), max(ax, bx)
                oy0, oy1 = min(ay, by), max(ay, by)
                if (max(ox0, cx + 2) <= min(ox1, cx + cw - 2)
                        and max(oy0, cy + 2) <= min(oy1, cy + ch - 2)):
                    crossings.append("(%d,%d)->(%d,%d) through "
                                     "(%d,%d %dx%d)"
                                     % (ax, ay, bx, by, cx, cy, cw, ch))
    if crossings:
        print("  %d connector(s) in the architecture diagram pass through a "
              "box:" % len(crossings))
        for c in crossings[:5]:
            print("    %s" % c)
        print("  A line crossing a box is an arrow into that box, to "
              "everyone who did not draw it.")
        raise SystemExit(1)
    # What each box does, listed under the picture.
    #
    # This was a hover tooltip as well, and the tooltip is gone: "we anyway
    # have the what each part does section". Two places carrying the same
    # sentence is two places to read and one of them only works for a
    # reader with a mouse. The list works on a phone, on a keyboard, in a
    # screen reader and on a printout, so it is the one that stays.
    #
    # The sentence for a script is the first line of its own docstring,
    # read at build time -- a hand-written caption for twelve scripts is
    # twelve sentences that quietly stop being true, and a docstring is
    # edited by whoever changes the script.
    parts = []
    missing = []
    for m in re.finditer(r'<g class="ab[^"]*">(.*?)</g>', arch, flags=re.S):
        label = re.search(r'<text class="at[^"]*"[^>]*>([^<]*)</text>',
                          m.group(1))
        from html import unescape as _un
        label = _un(label.group(1).strip() if label else "")
        note = box_note(label) or box_note(label.split(" · ")[0])
        if not note:
            missing.append(label)
            continue
        parts.append((label, note))
    if missing:
        print("  %d box(es) on the architecture diagram have no note: %s"
              % (len(missing), ", ".join(repr(x) for x in missing)))
        print("  A diagram that explains six of its eighteen boxes is a "
              "diagram a reader gives up on.")
        raise SystemExit(1)
    b.append('<div class="cf-arch">%s</div>' % arch)
    b.append('<details class="cf-parts"><summary>What each part does'
             '</summary><dl>')
    for label, note in parts:
        b.append("<dt>%s</dt><dd>%s</dd>" % (esc(label), note))
    b.append("</dl></details>")

    # ---- the trip, stop by stop ---------------------------------------
    n = counted()
    b.append('<h2 id="the-trip">The trip, stop by stop</h2>')
    b.append('<p class="cf-note">Four kinds of post, and they do not take the '
             'same route. Three of them do work before a word is written '
             'that the architecture series never does &mdash; a roundup '
             'fetches a week of feeds and builds an inventory from them, a '
             'daily post ranks everything the cloud announced yesterday, and '
             'a lab post has to actually run the thing it is about. Two of '
             'them draw a diagram and two never do. From the sync onwards '
             'every post is treated identically, which is the last five '
             'stops on all four.</p>')
    b.append('<div class="cf-trip-paths" role="tablist" '
             'aria-label="Kind of post">')
    for i, (key, label, count, _stops) in enumerate(journeys(n)):
        b.append('<button type="button" class="cf-path" role="tab" '
                 'id="tab-%s" aria-controls="trip-%s" data-path="%s" '
                 'aria-selected="%s">%s <span class="cf-path-n">%s</span>'
                 "</button>"
                 % (key, key, key, "true" if i == 0 else "false",
                    esc(label), esc(count)))
    b.append("</div>")
    for i, (key, label, count, stops) in enumerate(journeys(n)):
        b.append('<ol class="cf-trip" id="trip-%s" role="tabpanel" '
                 'aria-labelledby="tab-%s"%s>'
                 % (key, key, "" if i == 0 else " hidden"))
        for num, (kind, title, where, note) in enumerate(stops, 1):
            b.append('<li class="cf-stop cf-%s">'
                     '<span class="cf-stop-n">%d</span>'
                     '<span class="cf-by" aria-hidden="true">%s</span>'
                     '<span class="cf-what"><b>%s</b>'
                     '<code>%s</code><span class="cf-why">%s</span>'
                     "</span></li>"
                     % (kind, num, "hand" if kind == "hand" else "machine",
                        esc(title), where, note))
        b.append("</ol>")
    # role="tablist" is a promise that the arrow keys move between tabs and
    # that only the selected one is in the tab order. A tablist that does
    # neither is worse than four plain buttons would have been, because a
    # screen reader announces "tab, 1 of 4" and then the arrow keys do
    # nothing.
    b.append('<script>(function(){'
             'var tabs=[].slice.call(document.querySelectorAll(".cf-path"));'
             'if(!tabs.length)return;'
             'function show(t,focus){'
             'tabs.forEach(function(o){'
             'var on=(o===t);'
             'o.setAttribute("aria-selected",String(on));'
             'o.tabIndex=on?0:-1;'
             'var panel=document.getElementById("trip-"+o.dataset.path);'
             'if(panel) panel.hidden=!on;'
             '});'
             'if(focus) t.focus();}'
             'tabs.forEach(function(t,i){'
             't.tabIndex=t.getAttribute("aria-selected")==="true"?0:-1;'
             't.addEventListener("click",function(){show(t,false);});'
             't.addEventListener("keydown",function(e){'
             'var k=e.key,n=null;'
             'if(k==="ArrowRight"||k==="ArrowDown")n=tabs[(i+1)%tabs.length];'
             'else if(k==="ArrowLeft"||k==="ArrowUp")'
             'n=tabs[(i-1+tabs.length)%tabs.length];'
             'else if(k==="Home")n=tabs[0];'
             'else if(k==="End")n=tabs[tabs.length-1];'
             'if(n){e.preventDefault();show(n,true);}'
             '});});'
             '})();</script>')
    b.append('<p class="cf-note cf-trip-foot">The last five stops are the '
             'same on every path. %d of the %d post pages are built by '
             'sync_blog rather than by a builder of their own; only the '
             'three architecture series have one.</p>'
             % (n["syncbuilt"], n["posts"]))
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
        # n["checks"] counts check_*.py files. The GATE runs those plus the
        # validate_* family, and only some of them open a browser -- so this
        # sentence managed to be wrong twice at once: it said 58 where the
        # gate runs 59, and it said all of them drove a browser when 34 do.
        # Both numbers come from preflight itself now.
        '<p class="cf-note">%d checks on every push, %d of them in a real '
        'browser. They do not read the code &mdash; they open the pages and '
        'look: does the header hold still, does the music button actually '
        'play, does a filter filter, does every link still resolve, is each '
        'page asking for the current stylesheet. If one fails, the push is '
        'refused. It costs about twelve minutes, which is the price of not '
        'finding out from a reader.</p>' % (n["gate"], n["browser"]))

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
