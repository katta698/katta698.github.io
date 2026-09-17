# Before saying "fixed"

Five rules, each written the day it cost hours. They are printed by
`scripts/preflight.py` on every push so they are in front of whoever is about
to ship, rather than in a file nobody opens.

---

## 1. Name the instrument, and name what it cannot see

Never write "fixed" without saying how it was verified and what that
verification is blind to.

> Verified in headless Chrome **launched with `--autoplay-policy=
> no-user-gesture-required`** — which an iPhone does not do.

That sentence, written once, would have ended a three-hour loop on 15 Sep
2026. The music was declared fixed twice from a browser that had been granted
permission the reader does not have. The site was never the disagreement; the
instrument was.

Where a real device is the only truth, say so and ask, rather than reporting a
pass. "I cannot reproduce iOS backgrounding here" is a result. A green check
that measured the wrong machine is not.

## 2. A check must assert what a reader would notice

Not that a number stayed the same.

- `check_audio_glyph` required **one glyph per load**. A permanently *wrong*
  glyph passes that perfectly: it never flickered, it just said sound was on
  during silence. Steadiness was the wrong property; truthfulness was the
  right one.
- `check_shell_consistency` read the bar's background, which agreed, and never
  its border, ink or backdrop, which did not.
- `check_shift` only ever opened a desktop window, and both faults it was meant
  to catch lived inside a `max-width` media query.
- `check_post_shell` counted `<div>` inside HTML comments, so a real
  two-container fault was reported as nine and dismissed as noise.

A check that can be passed by the bug it was written for is worse than no
check, because it ends the argument.

## 3. Re-run after the fix — and re-run the neighbours

Reading a diff is not verification. One contrast pass went through three wrong
versions, each caught only by re-running:

- applied to both themes, so it painted accent-on-accent: 4.06:1 → **1.68:1**
- written `body.light .a, .b, .c`, where the prefix binds only to `.a`, leaving
  eighteen selectors global: 49 failures → **50**
- correct on its own terms, and it broke `check_cloud_colors` by inventing new
  values for chips that have a canonical palette

A change that improves twenty elements can still ruin two. Only measuring says
which.

## 4. Never edit a generated file

`feed.xsl` is written by `build_status_feed.py`. `sw.js` is written from
`sw.template.js`. The Architecture Series pages are `externally_built`, so
editing `posts/` changes nothing that is served.

Each of these has shipped a half-applied fix: the blog feed themed correctly
and the four status feeds did not, in the same commit.

Check what writes a file before editing it.

## 5. Do not state a limitation you have not measured

A comment in `sync_blog.py` read:

> scripts in XSLT output do not execute in any browser

Written as fact, never tested, and false — they run in Chromium and WebKit
both. That sentence alone kept "the feeds cannot follow your theme" true for
as long as nobody challenged it. The fix was one line.

An unverified claim in a comment is worse than no comment. It closes off a fix
and sounds authoritative doing it.

## 6. An empty field is a claim. A zero result is not a fact.

Every check here asked "is what is on the page correct?" Nothing asked "is
anything missing?" -- and a page missing thirty events answers the first
question perfectly.

Six failures on the events page in one afternoon, every one a silent absence
rather than a wrong value, and every one found by a reader:

| what was missing | how it got missed |
|---|---|
| all AWS dates | one probe came back empty; written into three files as fact |
| 31 AWS Summits | a guessed API id returned `totalHits: 0`, read as "not served" |
| Ignite's city | the venue is three words after the date that WAS read |
| Singapore's link | a URL truncated at 60 chars by the width of my debug output |

Two habits, both cheap:

**Reconcile against the source, not against yourself.** `check_events` proved
every row valid while thirty were absent. `check_events_coverage` goes back to
the vendors' feeds, counts what they list as upcoming, and names anything the
store does not have. Deleting six rows makes it fail with six lines saying
which.

**A zero result has to be confirmed twice before it becomes a sentence.** "AWS
has no API for this" came from one guessed parameter. Watching the page make
its own request took two minutes and produced the real answer. If a negative
finding is about to be written into a comment, it is load-bearing -- check it
the way a claim gets checked, or write down which probe produced it and what
that probe could not see.

---

## The shape of every bug above

Something reported the state it *wanted* instead of the state it *was in*:

| reported | actual |
|---|---|
| `localStorage.beachAudio === 'on'` | iOS refused to start playback |
| `v.paused === false` | the decoded frames were freed; the clock never moved |
| `play()` resolved | the element had no `src` yet |
| the button exists and is styled | pressing it did nothing |
| the 200 from the indexer | `chunks.json` was never written |

When something looks right and behaves wrong, stop reading what it says about
itself and measure what it does.
