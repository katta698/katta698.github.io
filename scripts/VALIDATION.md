# Claim validation across all three clouds

This file is the brief for the **validation window**
(`C:/Projects/Engineering/katta698-validation`, branch `validation`).

## The goal, stated as a test

**When a published post is sent to an external reviewer, it should only ever
come back with framing or style suggestions — never a data correction.**

That is the target, and it is deliberately a test rather than an aspiration,
because it says when the work is done. "Make the checks better" never
terminates; "reviews return framing only" either holds or it doesn't.

Note what it does *not* require: it does not require the author to be perfect.
It requires one property of the prose —

> every sentence is either sourced to a page that was actually fetched, or
> visibly a judgement.

A reviewer cannot correct a judgement, only disagree with it. So the factual
surface shrinks to the sourced sentences, and those are already checked. The
errors have all lived in the third category: sentences that *read* as fact,
carry no source, and sit in the same prose voice as the quotations around
them. Azure #31's "is billed two ways at once" is the type specimen.

**Where external review still fits.** Not as a daily gate — it runs after
publication, it is manual, and what it finds depends on what the reviewer
happens to look at. Run it **monthly, as measurement of whether the checks
hold**: framing notes only means the gates are working; a data correction
means a gate leaked and the leak is the thing to fix, not just the post.

Keeping one independent pass matters. A window that writes the checks *and*
certifies its own output has a blind spot by construction — the same reasoning
that produced an error would certify it.

## The per-post routine

Agreed with Jayanth 2026-09-13, replacing "export every post to another model".

1. The cloud window writes the post and runs `publish.py`. The mechanical
   checks already run there — `validate_arch_post.py`, `verify_claims.py`,
   `check_assertions.py`. Nothing changes about that step.
2. **Before pushing**, `validate <post-name>` in this window. That means, for
   that one post:
   - fetch every page in `verified_claims` and confirm the claim against it;
   - recompute every `derive:` and every ratio, break-even or effective rate in
     the prose, from the cited numbers;
   - triage every advisory flag `check_assertions.py` raises — each one is
     either a real defect, or noise that belongs back here as a rule change;
   - check the *governing* page was cited, not merely an adjacent one. This is
     Mode A and no script catches it.
   - **read the prose back against the claims, not only the claims against the
     pages.** See below; this is the step that was missing.
3. Push.

### Check both directions, because the tools only check one

Added 2026-09-14, after arch-051 leaked a real correction to an outside reader
one day after this window validated it.

`verify_claims.py` asks *does this claim appear on the page it cites?* When this
window validates a post by hand it has been asking the same question, of the
same claim list. Both directions of that check are the same direction, and the
error lived in the other one:

| Direction | Checked by | arch-051 |
|---|---|---|
| claim → cited page | `verify_claims.py`, and this window by hand | passed, correctly |
| prose → claim | **nothing** | the scope was dropped here |

arch-051's claim is exact: *"approximately 5 weeks of usage data to generate
budget **forecasts**"*. Its body prose is exact too. Its callout then says *"the
useful control is not a budget at all"* — dropping **forecasts** and condemning
all of AWS Budgets, when actual-value alerts work on day one. Every claim was
right; the advice built on them was wrong.

So: **for every claim carrying a qualifier — forecasts, provisioned, per-Region,
first-year, management-account-only — find where the prose restates it and
confirm the qualifier survived.** A claim narrowed correctly and then widened in
prose is invisible to everything in `scripts/`.

**It does not mechanise cheaply, and that was measured rather than assumed.** A
prototype comparing the noun phrase after a figure in the claims against the
same figure in the prose produced 313 signals across the corpus, essentially all
noise — ordinary rephrasing is indistinguishable from a dropped qualifier
without knowing that "budget forecasts" is a narrower category than "a budget".
That is semantics. Do not ship a version of this without measuring it first;
313 flags is a checker switched off within a day.

What *did* mechanise is the position: the over-claim landed in a callout, and
callouts are now a summary position in `check_assertions.py` alongside headings
and table cells. That catches the shape, not the scope.

**Monthly, send three or four posts to a different model.** Not to catch those
posts — to measure whether step 2 is working. Framing notes only means the gates
hold; a data correction means one leaked, and the leak is the thing to fix.

**Why the monthly pass cannot be dropped, and cannot be done here.** The cloud
windows write the posts and this window checks them, but both are the same model
reasoning the same way. A wrong inference drafted in the AWS window is the thing
this window is *least* likely to notice, because it would re-derive it
identically. Independence is the whole value, and it is the one property no
amount of work in `scripts/` can manufacture. Same argument as the note at the
top of this file: a window that writes the checks and certifies its own output
has a blind spot by construction.

## The gate, and when to turn it on

Decided 2026-09-13. The mechanical checks already run on every push —
`prepublish.yml` fires on `posts/**` and runs the whole suite. What did not run
was any requirement to *decide* about what they reported: a prose finding
printed and the build passed, so a flagged sentence could ship with nobody
having looked at it.

`check_assertions.py --strict` closes that. It does not ask whether a sentence
is true, which no script can answer. It asks whether the sentence has been
**dispositioned**, which is checkable, and there are exactly two ways:

- **sourced** — the sentence restates a `verified_claims` entry, detected
  automatically by an eight-word phrase match; or
- **signed** — the author declared it a judgement rather than a fact:

  ```yaml
  judgements:
    - "so the r5 usage is covered first"
  ```

A reviewer cannot correct a judgement, only disagree with one. So a signed
sentence leaves the factual surface, and the surface shrinks to the sourced
sentences — which are already checked. That is this file's stated goal made
enforceable.

**A signature is scoped to the wording it was given.** Matching is on a
contiguous run of words, so reworded prose lapses its own sign-off and gets
looked at again. That is deliberate, not a limitation.

### The flip

```yaml
# .github/workflows/prepublish.yml  -- one line, when the backlog is clear
python scripts/check_assertions.py --strict
```

**Not yet.** `--backlog` prints what it would fail on, and today that is:

| series | open | posts |
|---|---|---|
| arch | 9 | 8 |
| daily | 6 | 5 |
| az | 4 | 4 |
| gcp | 2 | 1 |
| awslab | 2 | 2 |
| **total** | **23** | **20** |

Standard #5 applies: the other windows did not opt into a new gate mid-series,
and flipping it today stops three windows publishing tomorrow morning over
sentences that are, as of the 2026-09-12 triage, all correct. The order is:
those windows clear their 23, then the line goes in.

Run `python scripts/check_assertions.py --backlog` to see where it stands.

## Why this window exists

The checks that decide whether a post is factually sound are **shared by all
three series**. They live in `scripts/`, they run from `prepublish.py`, and
every cloud window inherits them on its next rebase from `main`.

They were being *edited* by whichever window happened to hit a bug. That is how
`check_sources.py` came to hold an AWS-only rule while reporting a clean result
for 31 Azure posts — a green light that meant "nothing was tested". A post went
out through that gap (see below).

So: one window owns the checks, three windows consume them.

**The rule, which is Jayanth's and predates this file:** adding a cloud is a
registry entry, not a fork. Three windows must not each invent an answer to the
same problem.

## Scope of this window

Touch: `scripts/*.py`, this file, and check-related docs.

Do not touch: `posts/`, `blog/`, or anything generated. Those belong to the
cloud windows, and staying out of them is why this window almost never hits the
rebase conflicts the others live with.

## What the checks actually are

Correctness-critical only; the cosmetic ones (`check_contrast`, `check_links`,
`check_dark_theme`, …) are omitted.

| Check | Blocking | What it can see | What it cannot |
|---|---|---|---|
| `verify_claims.py` | yes | Figures in a `claim:` appear on the cited page | Whether the cited page was the right one |
| `validate_arch_post.py` | yes | Every `derive:` evaluates; sources are on an allowed host | Anything not registered as a claim |
| `audit_claims.py` | advisory | Printed figures that appear in no claim | Assertions carrying no figure |
| `check_assertions.py` | yes\* | Comparatives with a number; consequence sentences; unsafe example IAM policy | Prose it has no pattern for |
| `check_sources.py` | advisory | A topic discussed without the page that governs it | Topics with no rule written yet |

\* blocks on example-code defects only; prose findings are advisory by design.

## The two failure modes, with evidence

Every factual error found across all three series so far has been in a sentence
written in the author's own voice. **Not one has been a misquote.** The quote
checkers work; the gap is elsewhere.

**Mode A — the owning page was never read.** The post reasons from a page
adjacent to the topic instead of the page that governs it.

- *AWS arch-048* priced CloudTrail Lake from the pricing page. The service had
  been closed to new customers since 31 May 2026; the notice was on the docs
  page, which the post never cited. A reader caught it.
- *Azure az-028* said what-if was unsupported for deployment stacks, citing the
  known-issues page. A newer dedicated page documented it fully.
- *Azure az-031* asserted guest billing rules from two general Entra licensing
  pages. The page that scopes it —
  `id-governance/microsoft-entra-id-governance-licensing-for-guest-users` —
  says guests are billed **only** for capabilities exclusive to ID Governance,
  and that P2 capabilities are not billed to that meter. It is linked from both
  pages the post cited.

`check_sources.py` addresses this. Its AWS rule is pricing→docs; its Azure rule
is topic→governing-page. **GCP has one placeholder rule and needs real ones.**

**Mode B — right sources, wrong inference on top.** Every quoted fact is true;
the sentence built from them is not.

- *AWS arch-018* cited two real pricing pages and stated a wrong break-even.
- *AWS arch-032* said "about a third of the price"; it was 20% below.
- *Azure az-031* said an access review spanning employees and guests "is billed
  two ways at once". No digit in the sentence, so `HAS_NUMBER` gating meant
  `check_assertions.py` could not see it.

`check_assertions.py` addresses this: `CONSEQUENCE_CUE` + `CONSEQUENCE_VERB`
within a 120-character window, skipping sentences that quote their source.

## Coverage today — read this before trusting a green result

| Series | `check_sources` topic rules | `check_assertions` |
|---|---|---|
| `arch` (AWS) | pricing→docs, with alias table | full |
| `az` (Azure) | 1 rule (guest-users licensing) | full |
| `gcp` | 1 placeholder (free tier) — **needs real rules** | full |
| `azw`, `gcpweekly`, `week`, `weekly` | **none** | full |

`check_sources.py` prints a note naming series with no rules, so a count of
zero is distinguishable from an absence of rules. Do not remove it.

## Standards for changing a rule

Inherited from the AWS window and worth keeping verbatim:

1. **"A rule that passes the case it was written for is worse than no rule."**
   Test every new rule against the post that motivated it, *as published*.
   `git show <sha>:posts/<file>` gives you that version.
2. **"A checker that cries wolf on a correctly sourced post gets switched off."**
   Measure the flag count across all 235 posts before committing. The
   consequence rule went 30 → 12 by adding a proximity window; 30 would have
   been ignored within a week.
3. **"A checker that cannot fail is worse than no checker."** Every pattern has
   a canary in `CANARIES` and runs on each invocation. Add one for any pattern
   you add.
4. **Prove the other clouds are unaffected.** Diff the output for each series
   before and after. `check_sources.py`'s AWS output is byte-identical across
   the last change; keep it that way unless the change is deliberately for AWS.
5. **Advisory first.** The other windows did not opt into a new rule mid-series.
   Promote to blocking only after their backlogs are clean.

## Open work

- [ ] Real GCP topic rules. The free-tier placeholder is a guess, not a case.
- [ ] Weekly-series rules (`azw`, `gcpweekly`, `week`) — currently zero coverage.
- [ ] `check_sources.py --online` withdrawal scan is opt-in and slow. It belongs
      in a weekly sweep; nothing schedules it yet. This is the check that
      catches a retired service, which is Mode A's worst case.
- [x] ~~The remaining consequence flags across the corpus have not been
      triaged.~~ Done 2026-09-12: all 55 flags (13 consequence, 42 ratio)
      triaged, **no factual errors found**. Two sourcing defects went to the
      cloud windows — `daily-020` infers pricing from silence on a What's New
      page, `week-01-gcp-landing-zone` calls projects free with nothing cited.
      One internal inconsistency in `arch-048` ("rate applies across
      destinations alike" against its own claim that rates may vary by
      destination). Every derived figure recomputed and correct, including
      `arch-032`'s 20%-below, so the historical "a third of the price" error is
      confirmed fixed in the published post.
- [ ] Consider requiring a `sources_fetched:` frontmatter list, so "which pages
      did the author actually read" is checkable rather than inferred. Invasive
      — every existing post lacks it — so advisory and optional at first.

## What a green `check_assertions.py` does and does not mean

Worth stating plainly, because the run prints a clean-looking summary either
way. Of 238 posts, `check_assertions.py` scans **185** — the other 53 match no
`file_prefix` in `SERIES` and are skipped in silence. Of those 185, **20 carry
no `verified_claims` block at all**, so there is nothing for `verify_claims.py`
to check on them.

And scanning is not reading. The prose half matches three regexes; it finds
sentences *shaped* like an unsupported inference. A wrong fact in a shape it has
no pattern for is invisible to it. So a clean run means "no sentence matched a
known-bad shape", never "this post is correct". The independent monthly pass at
the top of this file is not redundancy — it is the only thing measuring whether
these gates hold.

## History

- `2827666` (2026-09-12) — made both checks fire outside AWS; added the
  canaries `check_assertions.py` had promised since the non-raw-string incident
  and did not have.
- 2026-09-12 — triaged all 55 prose flags and cut the false-positive rate:
  **55 → 23**, consequence 13 → 6, ratio 42 → 17, with every true positive
  retained. Five noise classes, each traced to the sentence that motivated it:
  `% of` quantification read as comparison (20 flags — "99.9% of newly written
  objects" is a durability target); bare `exactly <n>` on counts and version
  pins; tables flattening into one pseudo-sentence because tag-stripping did not
  honour block boundaries; the scope sense of "covered"/"free"/"you must"; and
  a misconception quoted in order to be refuted, which got through because
  `HAS_QUOTE` was defined and **never called**.

  The claim cross-reference added here is deliberately scoped to the
  *conclusion* of a sentence, not the whole of it. The first cut tested the
  whole sentence and silently dropped `daily-020`, where a verbatim sourced
  claim in the first half was laundering an unsourced pricing inference in the
  second — the Azure #31 shape exactly. `selftest()` now carries that case.
