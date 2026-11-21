# Publishing takes hours in every window, and it is one shared cause

Raised 2026-11-21 from the AWS window, after a Saturday in which publishing three
posts consumed roughly three hours of wall clock. The same complaint arrives from
the Azure and GCP windows, which matters because it is the strongest evidence for
the diagnosis: all four windows run the same `scripts/sync_blog.py` from the same
repository. **This is one defect, not four.** One fix reaches every window on its
next rebase.

This document raises the problem and proposes fixes. It deliberately changes no
code: `sync_blog.py` belongs to the `main` window and the shared checks to the
Validation window.

## Measurements

Taken 2026-11-21 in the `aws` worktree.

| | |
| --- | --- |
| Posts in `posts/` | 553 |
| Generated directories under `blog/` | 558 |
| Observed full `sync_blog.py` run | ~40 minutes |
| Implied per-post cost | ~4.3 seconds |
| Syncs run to publish 3 posts | 5 |
| Of those, avoidable | 4 |

Four windows publish daily, and seven posts fall due on a Saturday. The cost is
not one 40-minute build; it is 40 minutes multiplied by the number of windows and
again by every re-run that another window's push forces.

## The decisive measurement

`publish.py` reports what actually changed after a sync. Across three runs on
2026-11-21:

```
5 post file(s), 37 blog file(s), 2 other
4 post file(s), 34 blog file(s), 3 other
5 post file(s), 37 blog file(s), 2 other
```

**553 pages are written. About 35 differ.** The remaining ~518 are rewritten with
byte-identical content, which is why git reports no change for them.

Nothing requires this. The builder's signature is:

```python
def build_post_page(post, prev_post, next_post):
```

It receives the post and its two immediate neighbours. It does **not** receive the
full post set: there is no per-page counter, widget or total computed across all
posts. So an already-published page has no dependency on a post added later unless
it is one of the two neighbours whose Previous/Next links change.

The genuinely global input is the `?v=` cache-bust token, and it changes only when
`blog.css` or the JS pair changes — not when a post is added. On a post-only
publish every one of those ~518 pages receives the identical token it already had.

What must change on a normal publish:

| What | Count | Why |
| --- | --- | --- |
| The new post's page | 1 | It is new |
| Its two neighbours | 2 | Previous/Next now point at it |
| Index + pagination | ~21 | Aggregates over all posts |
| `cards.json`, `posts.json`, `rss.xml`, `stats.json`, colophon, `sitemap.xml` | 6 | Aggregates |

## Root cause

**1. `sync_blog.py` has no incremental path.** The only hashing in the file is
`_content_hash()`, used to compute the `?v=` cache-bust tokens for `blog.css` and
the JS pair. Nothing compares a post's inputs against its last build.
`build_post_page(post, prev_post, next_post)` is called for every post on every
invocation, so publishing one post regenerates 553 pages plus the pagination set,
`cards.json`, `rss.xml` and `stats.json`.

At ~4.3 seconds per post for what is template substitution and a file write, the
time is going somewhere other than the substitution — most likely the I/O of
writing 558 directories, or a per-post scan over all posts for prev/next and tag
counts. **Profiling one run is step zero**; the proposals below are worth doing
regardless, but the profile decides whether B is a 20x win or a 200x one.

**2. Every writer is also a full-site builder.** Each window runs the whole-site
build locally and commits its output. That is also why generated-file conflicts
are routine rather than rare: four processes write the same `blog/index.html`,
`cards.json`, `rss.xml` and `stats.json`. The documented resolution for such a
conflict is to re-run `sync_blog.py` — another 40 minutes, which can itself be
invalidated by the next window's push.

## Proposal A — run the cheap checks before the sync, not after

No code. Process only. Applies to every window today.

On 2026-11-21 four of five syncs died on checks that never needed a built page:

| Sync | Died on | Needs `blog/`? |
| --- | --- | --- |
| 1 | `check_prose` (doubled word) | No — reads `posts/` |
| 2 | `validate_arch_post` (missing section, missing TOC) | No — reads `posts/` |
| 3 | overlapped an in-flight edit | No |
| 4 | `verify_claims` (figure in `claim:` text) | No — reads `posts/`, fetches vendor pages |

`check_prose.py`, `verify_claims.py`, `validate_diagrams.py`, the front-matter
half of `validate_arch_post.py`, and any verbatim-quote checking all read sources
or fetch vendor pages. None require a generated page.

**Order to follow:** write every post, run all source-level checks, fix, *then*
sync once, commit, push. `publish.py` should be the last step, not the instrument
for finding problems. Two corollaries: never start a sync while still editing a
post, and fix all posts before syncing rather than syncing after each fix.

This is free and removes most of the retries. It does not reduce the cost of the
one sync that remains.

## Proposal B — skip posts whose inputs have not changed

The recommended first code change. One file, no architectural risk.

Per post, hash the inputs that can affect its page:

- the `posts/<slug>.html` source
- the template it is built from
- `CSS_VERSION` and `JS_VERSION`
- the identity of its `prev` and `next` neighbours

Store the map (`blog/.build-cache.json` or similar) and skip `build_post_page()`
when a post's hash is unchanged. `hashlib` is already imported, so the machinery
exists.

Why this is safe: the genuinely global inputs are the cache-bust token and
Previous/Next. The token changes only when `blog.css` or the JS pair changes, and
on those runs every hash changes and everything rebuilds — correctly. Previous/Next
changes only for the *neighbours* of an added or removed post, which the neighbour
identities in the hash capture precisely.

Expected effect: a routine publish regenerates a handful of pages rather than 553.
The index, pagination, `cards.json`, `rss.xml` and `stats.json` are aggregates and
must still be rebuilt every run; they are a small fraction of the work.

Add `--no-cache` to force a full rebuild, and make the cache file's absence mean
"rebuild everything" so a cold checkout is always correct.

## Proposal C — move the build out of the windows

Structural, higher value, higher risk. Worth doing after B.

Windows commit **sources** only — `posts/`, `blog/assets/diagrams/`. A single
GitHub Actions job on `main` runs `sync_blog.py` and deploys. Publishing from a
window becomes commit-and-push: seconds.

It also eliminates generated-file conflicts permanently, because no window writes
generated files. That is the other half of the current cost and no amount of
incremental caching fixes it.

**What this costs.** The checks that read a *built* page —
`check_series_pattern.py`, `check_built_pages_current.py`, the theme and contrast
checks, and the rendered-page half of `validate_arch_post.py` — would run in CI
and fail *after* push rather than before. For a series whose whole claim is that
nothing ships unverified, that is a real regression in guarantee, and it is why B
should come first.

**Do not reintroduce a workflow that commits generated files back.** `111570f`
deleted exactly that on 2026-08-05 because it made the Actions bot a third writer
on every publish. Proposal C is only safe if the windows stop writing generated
files altogether, leaving exactly one writer. `deploy-pages.yml` can deploy from a
build artifact, so the output need not be committed at all.

## Appendix — a second, unrelated deadlock found the same day

Not a performance issue, but it blocks a finished post and belongs with the
Validation window, so it is recorded here rather than lost in a chat.

`arch-120-instance-recovery` is about mechanisms — two recovery paths, which
status check triggers them, what a recovered instance keeps and loses. It prints
no price, quota or limit, so none of its 23 claims contains a figure of the class
`verify_claims.STRONG_RE` recognises (currency, percentage, multiplier, unit,
time-with-unit, decimal, comma-grouped or 3+ digit number). Single digits are
deliberately excluded.

The two checks then contradict each other:

| State of the post | `verify_claims` | `check_publish_date` |
| --- | --- | --- |
| With `verified:` | **fails** — "NOTHING VERIFIED - no claim carries a figure" | passes |
| Without `verified:` | passes | **fails** — "no verified date in front matter" |

No configuration satisfies both, so a correct, fully sourced post cannot pass the
gate. Removing the badge only moves the failure, and `--no-verify` is scoped to
the Azure window.

The narrow fix: `verify_claims` should treat "badged, and no claim carries a
figure" as a **warning** rather than an error. A post with no figures has no
figure to get wrong, which is the class of error that check exists to catch —
`audit_claims.py` already reports figure coverage without failing a build, and is
the right place for the signal. The badge's own definition in `CLAUDE.md` covers
"pricing, quotas, limits, **API behaviour**, CLI flags or IaC arguments", so a
post verifying only API behaviour is in scope for the badge by design.

## Ownership

- `scripts/sync_blog.py` — `main` window. Proposals B and C.
- Shared checks and their ordering in `prepublish.py` / `publish.py` — Validation
  window. Proposal A's enforcement, if it is to be enforced rather than followed.
- The cloud windows consume both and should not patch either.

## Why this is written down rather than worked around

Each window has independently discovered that publishing is slow and has
independently absorbed the cost. That is the failure this repository's `CLAUDE.md`
exists to prevent: a procedure kept in prose gets re-derived, and every
re-derivation is an opportunity to differ. The remedy it prescribes is to fix the
shared thing once so every window inherits the fix through a step it already takes.

If this is not acted on, the next Saturday costs the same four hours again, in
three separate chats, with three separate agents explaining the same arithmetic.
