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
- [ ] The remaining consequence flags across the corpus (12 at last run) have
      not been triaged. Some are real.
- [ ] Consider requiring a `sources_fetched:` frontmatter list, so "which pages
      did the author actually read" is checkable rather than inferred. Invasive
      — every existing post lacks it — so advisory and optional at first.

## History

- `2827666` (2026-09-12) — made both checks fire outside AWS; added the
  canaries `check_assertions.py` had promised since the non-raw-string incident
  and did not have.
