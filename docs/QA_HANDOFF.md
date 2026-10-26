# Cross-cloud documentation QA — handoff

**For the quality agent covering AWS, Azure and GCP.** Written 2026-10-25 by
the AWS window, which does not own this duty going forward.

Everything here is verified against the repository as of that date. Where
something is an open decision rather than a fact, it says so.

---

## 1. The ground truth you are enforcing

**`docs/MASTER_STANDARD.md`, in this repository.** It is the only copy. Issued
by Jay on 2026-10-25, governs all three series, and supersedes the older
ten-section weekly template and the 2026-09-30 "complete rendered file tree"
instruction.

**Do not let a cloud keep a private copy in its own lab repository.** That is
how the standard fragmented in the first place: it was issued once in chat, and
each window kept whatever it remembered.

## 2. Why one change reaches all three clouds

The three series are **git worktrees of one git directory**, not three repos:

```
C:/Projects/Engineering/katta698.github.io/.git      <- the real git dir
  katta698-aws      [branch aws]
  katta698-azure    [branch azure]
  katta698-gcp      [branch gcp]
```

So `CLAUDE.md`, `docs/`, `scripts/` and `_templates/` are **shared**. A commit
on one branch reaches the other two on their next rebase. It also means all
three share `.git/hooks`.

## 3. What enforces it, and what does not

```
git push  ->  .git/hooks/pre-push  ->  preflight.py --fast
                                         -> prepublish.CHECKS registry
                                              -> check_lab_post_shape.py   BLOCKING
```

In `prepublish.py` the registry row is
`(script, blocking, needs_network, passes_series, passes_posts)` and the shape
check is `(…, True, False, True, True)` — **blocking is True**. A lab post that
fails it cannot be pushed, on any branch.

### The check matches HEADINGS, not ids

This is the most important thing to understand, and it was learned the hard way.

The standard specifies section **headings**. It never specified the HTML `id`,
so each series invented its own and they diverged within a day of the standard
being issued — while all three were in fact compliant. Checking ids would have
declared two of the three broken over a detail the standard does not contain.

Matching is on a distinctive **stem**, so GCP's `Troubleshooting` passes against
the canonical `Troubleshooting and Lessons`.

### What it catches

| | |
|---|---|
| A missing or renamed mandated section | yes |
| Services section with no table | yes |
| Prerequisites with no table or list | yes |
| Validation with no `Status` column | yes |
| Troubleshooting without `Root cause` | yes |
| Architecture with no diagram (inline `<svg>` or an `<img>` of a `.svg`) | yes |
| The retired `terraform-layout` card (per-file line counts) | yes |

### What it CANNOT catch — this is where you come in

- **Whether the evidence is real.** A Validation table of invented results
  passes. The standard says never invent evidence; nothing mechanical enforces
  it.
- **Whether a cost is measured or estimated.** The standard requires measured
  cost from the billing console. A rate-card calculation presented as measured
  passes.
- **Word count and figure count.** 1,500–2,500 words and 4–7 screenshots are
  in the standard and are not checked.
- **Whether the architecture diagram matches what was actually built.**
- **Whether the blog duplicates the GitHub guide** instead of linking it.
- **Prose quality, repetition, and whether a reader understands the
  architecture in five minutes.**

## 4. Current state, measured 2026-10-25

| Series | Posts | Migrated | Pending | Section ids in use |
|---|---|---|---|---|
| AWS Weekly Lab | 24 | 5 (weeks 20–24) | 19 | `implementation` `security-cost` `cleanup` |
| Azure Weekly Lab | 10 | 1 (week 10) | 9 | none on a div — the id is on the `<h2>` |
| GCP Weekly Lab | 10 | 2 (weeks 09–10) | 8 | `build` `security` `takeaways` |

"Migrated" means all nine mandated headings are present.

Un-migrated posts are listed in `MIGRATION_PENDING` in
`check_lab_post_shape.py` so the gate stays green and meaningful rather than red
and ignored. **That list shrinks only.** Remove a slug as its post lands; never
add one back.

## 5. Open items you are inheriting

**a. Section ids differ across the three series.** Cosmetic — they are the
anchor links. The canonical list is in `MASTER_STANDARD.md` §2b. The agreed
position is that headings are the contract and ids are housekeeping, so each
series converges when it next touches a post. **It is reasonable to leave this
alone.** Decide and record it either way.

**b. `verified_claims` debt — the real one.** `validate_arch_post.py` reports
roughly 60 errors across AWS weeks 13–19 and several Azure posts:

- entries with a `claim:` but no `source:`
- entries with `derive:` but no `expect:`, so there is nothing to compare against
- sources citing `github.com` rather than vendor documentation

These are **pre-existing**, not caused by the restructures — verified by
hashing the `verified_claims` blocks before and after. They surfaced as
*advisory* on push, so they do not block.

This matters more than the id question: the verification badge asserts that a
human checked these facts on a date. Claims with no source quietly weaken that
promise on every post carrying one.

**c. Restructuring a published post is not republishing.** Leave `date:` and
`verified:` alone unless that post's vendor facts were genuinely re-checked
that day. `lab_post_kit.py` in the AWS lab repo enforces this mechanically; the
other series have no equivalent guard.

## 5b. The failure mode that nearly shipped, and the tool for it

**`scripts/diff_post_facts.py`** compares every number in a rewritten post
against the committed previous version. Run it on any restructured post, in any
series:

```bash
python scripts/diff_post_facts.py week-12-whatever.html
```

- **ADDED** = a number in the new version that was not in the old one. It must
  trace to the repository or to a measurement taken today, or it was invented.
- **dropped** = expected; the rewrite cuts 40-60% on purpose. Worth a glance for
  anything load-bearing.

**Why it exists.** Restructuring is not a mechanical move: each post is read and
re-expressed. The shape gate guarantees the front matter, publish date,
verification badge and figure set survive. It guarantees nothing about whether
the prose still says the same thing.

**The specific trap, and it is structural rather than one window's mistake.**
The mandated Lab Overview table asks for *difficulty* and *approximate
completion time*. **Most back-catalogue posts never recorded either.** The
temptation is to fill the row in. The AWS window did exactly that on ten posts
before this check existed, and several were badly wrong against the posts' own
recorded timings — one said "about 2 hours" for a lab the post records as
running 41 hours.

It is the hardest class of error to catch by reading, because an invented
duration reads exactly like a recorded one.

**Measured 2026-10-25, after the tool existed:**

| Post | Result |
|---|---|
| GCP `week-10-group-access` | clean — no added numbers |
| GCP `week-09-sa-lifecycle` | one added: a Terraform version, traces to the repo |
| Azure `week-10-opentelemetry` | clean — no added numbers |
| AWS weeks 15–24 | **ten invented durations, now corrected** |

So the other two series were doing this correctly. The guidance worth passing
on is the pattern, not a correction: **where a post never recorded a duration,
say "Not recorded" or something honestly vague.** Azure's "Roughly an evening"
is the right instinct; a precise-sounding number nobody measured is the trap.

## 6. New posts

**`_templates/lab-post-skeleton.html`** — the nine sections in order with the
required shape already in place, and inline notes on what each must and must
not contain. Same file for all three clouds. It passes the gate itself.

The hook catches a bad shape at *push* time, after the writing is done. The
skeleton catches it at the first keystroke. **If a window is building the
structure from memory, that is the thing to correct** — it is what produced
three structures from one standard.

## 7. Commands

```bash
# the shape gate, all three series
python scripts/check_lab_post_shape.py
python scripts/check_lab_post_shape.py week-12      # one post

# claim metadata (the verified_claims debt above)
python scripts/validate_arch_post.py

# everything the push hook runs
python scripts/preflight.py --fast
```

A named post that matches nothing **exits 1**. A check that examined no post has
not passed — that failure mode is how the AWS series went unchecked for months.
