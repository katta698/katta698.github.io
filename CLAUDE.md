# Claude Code Instructions — katta698.github.io

## Workflow rules

- **At the start of the day, read `MORNING.md` in this folder.** It is written
  into all four worktrees by a scheduled task at logon, and says what is due
  today, which number each series is on with its roadmap line, and — on
  Saturdays — the state of every feed the roundups depend on. Re-run it by hand
  with `python scripts/morning.py` when the brief is stale, which on a Saturday
  means any time you start writing hours after logon.
- **When the post is written, run one command:**
  ```
  python scripts/publish.py
  ```
  It fetches, rebases, syncs, runs every check, re-checks the remote, reports
  what changed, and stops before committing. Everything below about ordering is
  what it already does — read it to understand *why*, not to do it by hand.
- Always `git pull --rebase` before any edits. Three other worktrees publish to this same branch, so `origin/main` moves without you.
- Never commit or push without explicit instruction. Jayanth pushes himself.
- After `sync_blog.py` runs, stage ALL modified files under `blog/` — not just the new post's directory. Older posts get regenerated too (widgets, date format, CSS).

### The morning brief

`scripts/morning.py` runs once, from the `main` window's scheduled task, and
covers all four worktrees. **Do not run it in each window.** Four copies would
mean four rebases racing each other and four identical feed fetches; the whole
point is that the work happens once and the *output* is shared.

It writes `MORNING.md` into every worktree rather than only into `main`, because
a window can only be in one directory at a time — a brief that existed only in
the site folder would be one the three cloud windows could not read. The file is
gitignored: it is a briefing, not content.

What it does, and why each part is there:

- **What is due today**, from the cadence rules rather than from memory: three
  architecture posts every day, AWS Daily Intelligence Tuesday to Saturday, the
  three Weekly Intelligence roundups on Saturday. Seven posts land on a Saturday.
- **All four worktrees** fetched and reported, and rebased when clean. Never when
  dirty — sweeping a half-written post into a stash is not a thing a background
  task should do. A dirty worktree is reported and left alone.
- **The next number per series**, with the matching roadmap line. Where a number
  matches more than one line it prints all of them rather than choosing, because
  the AWS roadmap restarts numbering per phase and a wrong pick costs a post.
- **Feeds fetched fresh** on Saturday for the Monday–Friday window, and the
  previous day's AWS news on weekdays.

- **The three lab series, as open items rather than due ones.** AWS, Azure and
  GCP Weekly Lab have no fixed publish day — a lab post's whole claim is that
  the thing runs, so it goes out when it runs. The brief reports the next week
  number per series and leaves it at that.

**Lab series are matched on their label, never on the filename.** The AWS labs
are `week-NN-*` and the GCP series began at `week-01-gcp-landing-zone`, so the
two share a slug namespace. `_week_num()` in `sync_blog.py` numbers Weekly Lab
posts by matching `week-(\d+)` against the slug and cannot tell them apart
either — `AWS Weekly Lab`, `Azure Weekly Lab` and `GCP Weekly Lab` in `labels:`
are the only thing that does.

**It does not write posts, commit, push, or touch the verification badge.** That
last one is deliberate and must stay that way: a badge asserts that a human
checked the figures on a date, and a script stamping one would be making that
claim on nobody's behalf. See the verification section below.

It exists because the mechanical half of a publishing morning is forgettable and
its failure mode is silent. A roundup built from a truncated feed looks exactly
like a complete one.

### Why there is one command

Four windows publish to one branch, each reading these same paragraphs, and they
drifted. In one week: one window pushed without being asked while the other three
waited; one published in a shape that never triggered the RAG re-index, so its
posts had no *At a glance* summary for days and nothing reported it; and one ran
`prepublish.py` **before** its final rebase — checking a tree that was not the
tree being pushed. That last one is commit `43ef899`, whose entire subject is
"Run prepublish after the final rebase, not before".

None of that was carelessness. It is what a procedure kept in prose does: every
session re-derives it, and a re-derivation is an opportunity to differ.
`prepublish.py` already proved the remedy — it turned "run these four checks"
into one command and the checks stopped drifting. `publish.py` is the same fix
applied to the sequence around them.

**If you find yourself typing the steps by hand, the script is the bug report.**
Fix the script rather than working around it, so the next window inherits the
fix instead of re-deriving the workaround.

## Finish the work and stop

**Do not end a response with offers of further work.** No "Want me to…?", no
"I could also…", no closing block of open items to authorise. Finish what was
asked, say what changed, stop.

Raised 2026-08-15, about every window rather than one of them — which is why
the rule lives here, in the file all four worktrees share, rather than in one
window's memory.

The problem is not that any single suggestion is bad. It is that each one is
plausible enough to need a decision, so a closing menu of three turns a
finished task into three more judgements. Jayanth acts on them, so the cost
lands entirely on him: "I am kind of sick at times to see if I need to go ahead
or ignore your suggestions."

What to do instead:

- **End on the result.** A list of what changed is information and is welcome.
  An invitation to authorise more work is not.
- **A real fork gets one flat sentence**, in the body where it is relevant, no
  question mark and no menu. "arch-002 and daily-008 fail the prose check and
  belong to the AWS window" — then move on, and do not re-raise it next turn.
- **Answer at the size asked.** A yes/no question gets a yes or no.
- **This is about unsolicited offers, not about answering.** Asked for the
  options, lay them out properly.

## What Jayanth means by each series name

One word, one series. **"daily" is not one of them** — every series in this
window publishes daily, so the word identifies nothing.

| He says | He means |
| --- | --- |
| **arch** | AWS Architecture Series — the next numbered topic in `ROADMAP.md` |
| **intel** | AWS Daily Intelligence — rank yesterday's news, recommend one, then write on "write" |
| **weekly** | AWS Weekly Intelligence — the Saturday roundup |
| **lab** | The Weekly Lab for whichever cloud this window owns — the next week number, from `MORNING.md` |

Set 2026-08-17, after "next daily post" was read as Daily Intelligence when it
meant the daily architecture post, and a full Daily Intelligence post was
written and thrown away. The ambiguity was noticed when the trigger words were
first proposed, and writing it down was skipped — so it happened anyway.

**`lab` is the only one of the four that means something different in each
window.** In the AWS window it is the AWS Weekly Lab, in Azure the Azure Weekly
Lab, in GCP the GCP Weekly Lab — the window decides the cloud, exactly as it
does for `arch`. The other three words are AWS-only, because only AWS runs a
daily intelligence series and only the AWS window owns three series at once.

Labs have **no fixed publish day** and are never "due today". `MORNING.md`
reports the next week number per series as an open item; `lab` writes that one.

**If the word is ambiguous, ask before writing.** A one-line question costs
nothing; a wrong 3,000-word post costs an hour and has to be deleted.

## Which folder am I in?

**One chat window, one folder. One site on `main`, three clouds on branches.**
Check before doing anything.

| Chat window | Folder | Branch | Owns |
| --- | --- | --- | --- |
| Site | `C:\Projects\Engineering\katta698.github.io` | `main` | Everything that is not a post |
| AWS | `C:\Projects\Engineering\katta698-aws` | `aws` | AWS Architecture, AWS Daily + Weekly Intelligence, Weekly Lab |
| Azure | `C:\Projects\Engineering\katta698-azure` | `azure` | Azure Architecture, Azure Weekly Intelligence |
| GCP | `C:\Projects\Engineering\katta698-gcp` | `gcp` | GCP Architecture, GCP Weekly Intelligence |

Site work sits on `main` because it owns the shared files every series depends
on — `blog.css`, `blog.js`, `sync_blog.py`, the validators and the workflows.
The clouds branch off it and publish back to it, so a change to the machinery
reaches all three by the rebase they already do before syncing.

**A worktree belongs to a window, not to a series.** A window can only be in one
directory at a time, so two folders for one window is one too many — `daily` and
`weekly` were exactly that before the AWS series were consolidated into a single
window. For the same reason, Azure and GCP weekly intelligence need **no new
worktrees**: they belong to the windows that already own those clouds. All three
AWS series share the `aws` worktree for the same reason.

Add a worktree when a new *window* is opened, not when a new series starts.

### Why site work is its own window, and why it holds `main`

Post work touches `posts/` and one page. Site work touches `blog.css`,
`blog.js`, `sync_blog.py` and the workflows — files that regenerate **every**
page. A single CSS change rewrites the `?v=` cache-busting token on all ~110
pages, so it collides with anything else publishing at that moment.

Separating it means a post can publish without waiting for a half-finished CSS
change, and site work can rebuild the whole site without stepping on a draft.

It holds `main` rather than a branch of its own because the clouds branch from
`main` and rebase onto it before every sync — so a fix to the shared machinery
reaches all three through a step they already take, instead of needing to be
merged anywhere first.

Belongs in the `main` window: the blog index and its filters, pagination, the
PWA and service worker, the home-page tools, diagram tooling, `sync_blog.py`,
`validate_arch_post.py`, `check_freshness.py`, and the GitHub workflows.

```
git worktree list
```

Run that if there is any doubt. Each worktree has its own working files and its
own staging area, but they share one history — a commit made in any of them is
visible to the others immediately.

Two worktrees cannot check out the same branch. That is the only reason these
branches exist; they are staging branches, not long-lived ones, and everything
publishes to `main`.

**One window, one worktree. This is not optional.** The `azure` and `gcp`
worktrees were created on 2026-08-14 because all three cloud series were being
written in *this* folder at once, from three chat windows. Worktrees are not
about avoiding merge conflicts — they are about not sharing a working directory.
Three sessions in one folder share one set of files and one staging area, so:

- each session sees the others' half-finished edits as if they were its own;
- `git add -A` in any window stages whatever the others happen to have open;
- a commit can capture another window's incomplete work;
- running `sync_blog.py` regenerates files another window is mid-edit on.

None of that produces an error. It was noticed only because a push was blocked
by 264 lines of another session's uncommitted changes to `sync_blog.py` and
`validate_arch_post.py`.

Opening a fifth window means adding a fifth worktree, not a fifth session here:

```
git worktree add C:\Projects\Engineering\katta698-<name> -b <name> main
```

Branch from `main` rather than `origin/main` when the work being moved has
commits that are not pushed yet, or the new worktree starts without them.

### Publishing from a series worktree

Identical for `aws`, `azure` and `gcp`. Rebase onto `main` first, then push
straight to remote `main`:

```
cd C:\Projects\Engineering\katta698-aws       # or -azure, or -gcp
# write the post, then:
python scripts/publish.py       # fetch, rebase, sync, check, re-check, report
git add blog/ posts/ scripts/ index.html resume.html now.html sw.js
git commit
git push origin HEAD:main       # fast-forwards remote main, no merge commit
```

`publish.py` does the fetch, the rebase and the sync in the order below, and
stops before committing — so the two git lines after it are the only ones you
type. It prints the `git add` line for you at the end.

The long form, for when something goes wrong and you need to step through it:

```
git fetch origin
git rebase origin/main          # BEFORE running sync, not just before editing
python scripts/sync_blog.py
python scripts/prepublish.py    # AFTER the final rebase, not before
```

`git push origin HEAD:main` works from any of those branches and needs no merge
commit, provided you rebased first. If it is rejected, the branch has fallen
behind — rebase and push again.

**Run `prepublish.py` after the final rebase, not before it.** Rebasing pulls in
other windows' posts, and Previous/Next is a function of every post on the site
— so a post arriving between your build and your push silently invalidates the
nav on all 32 hand-built pages. `sync_blog.py` recomputes it for the pages it
generates; `arch-`, `az-` and `gcp-` pages are `externally_built` and keep
whatever the last build gave them.

`build_arch_post.py` does call `fix_series_nav.backfill_all()`, and it works —
but only for the set of posts that existed at build time. On 2026-08-18 arch-025
was committed at 07:17 and Azure #5 landed on origin at 07:18; the rebase that
followed left three pages with stale links, and `prepublish.py` was the only
thing that caught it.

With four windows publishing daily, the gap between build and push routinely
contains somebody else's post. So the order is: rebase, sync, **prepublish**,
commit, push. If the push is rejected and you rebase again, run it again.

**No window waits for another.** Each commits in its own folder whenever it is
ready and pushes independently; rebasing first is what makes that safe. If you
find yourself holding a change because another window has not pushed, something
is wrong with the layout, not with the timing.

**Rebase before running sync, not just before editing.** Each worktree has its
own copy of `posts/`, so it cannot see a post written in another worktree until
it rebases. Running sync first regenerates the whole index without that post.
`sync_blog.py` refuses to run when the checkout is behind `origin/main` for
exactly this reason; do not reach for `--skip-freshness-check` to get past it.

**Renaming a post: stage the deletion too.** `git add <new-name>` does not stage
the removal of the old file. The first weekly roundup was retitled and both
files were committed, so `posts/` carried two copies of the same post. The live
site was fine only because the stale file was absent from the tree that ran
sync; any clean checkout would have built a duplicate page, a doubled filter
pill, two RSS entries and two RAG index entries. Use `git mv`, or
`git add -A posts/`, and check `git status` shows the deletion staged.

## Publishing in parallel

Posts are often written in two sessions at once. Conflicts between them are
normal and harmless **if** you know which files are source and which are
generated.

| | Files | Conflicts? |
| --- | --- | --- |
| **Source** | `posts/<name>.html`, `blog/assets/diagrams/*.svg` | Never — each post is its own filename |
| **Generated** | `blog/posts.json`, `blog/index.html`, `blog/rss.xml`, `blog/stats.json`, every rebuilt `blog/<slug>/index.html` | Every parallel publish |

`sync_blog.py` rebuilds the whole site index from `posts/`, so any two people
publishing rewrite the same generated files.

**No workflow commits back after a post push.** `on-publish.yml` used to
regenerate `posts.json` from the rendered HTML and commit it, which made the
Actions bot a third writer on every publish; `111570f` deleted that step on
5 August 2026, and `posts.json` now comes only from `sync_blog.py`. The three
workflows that still commit are `refresh-aws-services.yml` (weekly cron),
`regenerate-schedule.yml` (fires on hero media and `index.html`, never on
`posts/`) and `publish-lab-draft.yml` (manual). So after pushing a post your
local branch stays level with `origin/main`, and a pull before the next post is
only needed because another *window* may have published.

Worktrees make conflicts *more* likely, not less: each of the four has its own
`posts/` and cannot see another's new post until it rebases. With four writers
rather than two, conflicts on generated files are routine. That is why the rule
is rebase before **sync**, not merely before editing.

They are still the right structure. A conflict on a generated file is visible
and has a documented fix; sharing one working directory silently mixes two
sessions' unfinished work, which does not.

**Resolving a conflict on a generated file — never hand-merge it:**

1. `git checkout --theirs <file>` (during a rebase, `--theirs` is the commit
   being replayed) just to clear the conflict markers.
2. `python scripts/sync_blog.py` — regenerates every generated file from
   `posts/`, which by then contains both people's work.
3. Confirm both posts are present (check the filter pill counts in
   `blog/index.html`), then `git add blog/ posts/` and `git rebase --continue`.

**The failure that loses a post silently.** Do not run `sync_blog.py` and push
from a checkout that predates someone else's post. Their `posts/` file is
absent from your tree, so the regenerated index, `posts.json`, `rss.xml` and
`stats.json` all come out without it. The post's own page survives on disk but
is unlinked everywhere — no card, no filter pill count, no RSS entry, no RAG
index entry — and nothing errors. Always `git pull --rebase` before running
sync, not just before editing.

## Dates: every post carries a time

```yaml
date: '2026-08-14T09:00:00'     # quoted, ISO 8601, local time
```

**Not** `date: 2026-08-14`. A bare date is parsed as midnight, so on any day
when more than one series publishes, the post with a time always sorts above
the ones without — regardless of which was actually written first.

That is not hypothetical. On 14 August 2026 the AWS daily post carried
`'2026-08-14T09:00:00'` while the Azure and GCP posts carried bare dates, so
AWS was labelled **Latest** on the home page even though the other two were
published after it. Ordering is `posts.sort(key=lambda p: p["date"],
reverse=True)` in `sync_blog.py` — one key, no tie-break, so without a time the
order within a day comes down to the order files happen to be read in.

Four windows now publish on the same day routinely. Use the real publish time;
it costs nothing and it is the only thing that makes "Latest" mean anything.

**Existing posts are deliberately left alone.** Backfilling times onto ~100
published posts would rewrite the order of the whole archive to no benefit —
their relative order is already settled and nobody is looking at which of two
posts from March 2026 came first. The standard applies from now on.

## Label colours: hue follows the cloud, treatment follows the kind

Every filter pill and post card carries an accent, and the two axes mean
different things:

- **Hue** identifies the cloud. AWS tan `#C4A484`, Azure dusty indigo
  `#5B7B9A`, GCP olive sage `#8A9A5B` — the same colour wherever that cloud
  appears: series pill, bare tag pill, post card, sidebar widget, progress tab.
- **Treatment** identifies the kind. A **series** gets a filled tint; a **tag**
  gets accent text and border only. A post belongs to exactly one series but
  can carry several tags, so the two are not the same kind of thing and should
  not look alike.

Non-cloud topics have their own hues in the same warm desaturated register
(`TOPIC_BY_LABEL` in `sync_blog.py`, `.topic-*` in `blog.css`). Databases & Ops
is deliberately slate blue-grey rather than warm: it is the pre-cloud DBA
writing and looks like a different era on purpose.

**Adding a label means adding an accent.** A new entry in `CATEGORY_ORDER` with
no `TOPIC_BY_LABEL` mapping renders neutral grey beside coloured neighbours.

**Watch the dark-mode cascade.** `body.dark .filter-pill.cloud` is specificity
(0,3,1) and beats `.filter-pill.cloud.active` at (0,3,0), so the selected pill
takes the orange fill but keeps its pale accent text — measured 1.10-1.39:1,
invisible. Both the `.cloud` and `.topic` halves need an explicit
`body.dark .filter-pill.X.active { color: #1D2322; }`. This was shipped broken
twice: once for clouds, then again for topics, because only the half that
happened to be selected got noticed.

## Blog post structure

Two files per post:
- `posts/<slug>.html` — YAML frontmatter + body (source; RAG indexer reads this)
- `blog/<slug>/index.html` — full served page (what GitHub Pages delivers)

**Always edit `blog/<slug>/index.html` for live fixes. `posts/` is for RAG only.**

## Never write about this publishing pipeline failing — ALL series

**Standing instruction, confirmed with Jay 2026-08-21 and reconfirmed 2026-08-22.
Applies to every post in every series — AWS, Azure, GCP, weekly labs,
architecture, intelligence. Permanently.**

Do not put lines like these into a published post:

- *"The screenshot tooling leaked a member account ID"*
- *"The redaction placeholder rendered as an HTML tag"*
- *"two of my own documents had leaked a billing account ID into prose"*

Not as a challenge card, not as an aside, not as a footnote.

**Describe the control, never the incident.**

| | |
| --- | --- |
| Right | "The capture script masks organization IDs, billing account IDs and project numbers, and refuses to write the file if any survive redaction." |
| Wrong | "It once failed to, and here is what went wrong." |

**Why.** A post whose subject is handling account data carefully undercuts itself
by opening with a time it did not. It invites the reader to distrust every other
figure in the series, and it is off-topic — the reader came for the cloud, not
for the author's screenshot script.

**Scope: this is only about the blog, capture and publishing tooling.** Real
failures against a cloud provider are exactly what a Challenges section is for,
and they should stay honest and specific — an API that returned an empty list
instead of a permission error, a resource that took five minutes, a consent
screen that silently skipped a scope. Keep those.

If a tooling failure produces a genuinely generalisable lesson, state it as a
design rule in the Security section, with the code linked as the evidence.

**Already published under the old habit:** `posts/week-15-cloudtrail-audit-forensics.html`
carries two such lines in its Challenges section. Left in place deliberately —
editing published content is Jay's call, not a silent cleanup. Raise it, do not
rewrite it.

## Verification badge — REQUIRED on every technical post, ALL series

Applies to **every** series: AWS Weekly Lab, Architecture Series, and AWS Daily
Intelligence. Standing instruction from Jay, 2026-08-07. Jay publishes from three
separate Claude Code windows, so this rule lives here — in the repo every series
publishes through — rather than being repeated per-window.

**Before publishing any post containing pricing, quotas, limits, API behaviour,
CLI flags or IaC arguments:** verify those claims against the vendor's current
official documentation (WebSearch + WebFetch the real docs pages — not training
data, not a blog post quoting the docs secondhand). Then add to the front matter:

```yaml
verified: '2026-08-07'    # the date you actually did the checking
```

`sync_blog.py`'s `verification_html()` renders a badge under the post header. The
markup and wording live in that one function so they stay identical across all
three series — do not hand-write badge HTML into a post body.

**The date is the VERIFICATION date, not the publish date.** They routinely
differ: a post checked on Friday and held for a Sunday publish should still say
Friday. That is the point — a reader arriving a year later needs to know how
stale the figures might be.

### The badge must be backed by evidence, not by a date

A date alone cannot be checked by anything. It was not: every per-post build
script carried a hardcoded `VERIFIED = '<date>'` and stamped it on whatever it
built, which is exactly what the rule below forbids. Posts #15-19 were badged on
five consecutive days for that reason and nothing else, and **#18 shipped a
factual error under a badge claiming it had been checked** — it mixed current
write pricing with pre-November-2024 read pricing and concluded reads and writes
break even at different utilisations when they break even at the same one.

So the badge now requires the evidence alongside it:

```yaml
verified: '2026-08-12'
verified_claims:
  - claim: "On-demand is $0.625 per million write request units"
    source: https://aws.amazon.com/dynamodb/pricing/on-demand/
  - claim: "Provisioned is $0.00065 per WCU-hour"
    source: https://aws.amazon.com/dynamodb/pricing/provisioned/
```

`validate_arch_post.py` fails the build when `verified:` is present and there
are fewer than two claims, when a source is not AWS's own documentation, when
the date is in the future, or when the served page's badge disagrees with the
front matter (arch pages are never rebuilt, so those drift silently). It warns
when a cited page is missing from the post's Official AWS Reference section, and
when the check is more than 180 days old.

**Every figure the post prints needs a claim, not just two of them.**

`validate_arch_post.py` enforces that a badge carries at least two sourced
claims. That is a floor, not the standard. The badge says "the figures in this
post were checked", so a price, limit, threshold or quota that appears in the
body and in no `verified_claim` is a number nobody checked, sitting next to
numbers that were.

`python scripts/audit_claims.py` reports that coverage per post. It does not
fail a build -- deciding which figures matter is a judgement -- but a badged
post tracing 0% of its figures is a badge doing less than it appears to.

**A derived figure must show its arithmetic.** Break-evens, ratios, per-unit
conversions and effective rates are the only things that have ever been wrong
here, so a claim stating one carries the calculation:

```yaml
  - claim: "Writes break even near 29% sustained utilisation"
    derive: "(0.00065 / 3600 * 1000000) / 0.625"
    expect: "0.289"
    source: https://aws.amazon.com/dynamodb/pricing/provisioned/
```

`validate_arch_post.py` evaluates `derive:` and fails the build if it disagrees
with `expect:` by more than one percent. The inputs are the rates from the cited
page, so a price change makes the check fail rather than leaving a stale
conclusion in place. This is what would have caught arch-018: its wrong
break-even came from pairing a current write price with a read price from
before November 2024, and no amount of source-checking notices that.

**Sourcing is not correctness.** The checks confirm a claim cites AWS and that
the page resolves. They cannot tell whether the page was read correctly.
arch-018 cited two real AWS pricing pages and still stated a wrong break-even,
because the error was in arithmetic done on top of correct sources. Derived
figures -- break-evens, ratios, "N times cheaper", effective rates -- are where
every error here has actually happened. Recompute them from the cited numbers
before publishing, and write the inputs into the claim so the arithmetic can be
repeated.

**Run `--check-links` before publishing.** It fetches every cited page.
Status codes are not sufficient on their own: `docs.aws.amazon.com` is
client-side routed and **answers HTTP 200 for pages that do not exist**,
returning a ~1 KB shell, so the checker judges the body size instead. Without
that, every dead docs link passes.

```bash
python scripts/validate_arch_post.py --check-links
```

**Never add `verified:` to a build script's template.** Writing the claim list
is work a build script cannot fake, which is the entire point. If you did not
personally fetch the pages, the post gets no badge — that is the correct
outcome, not a gap to fill.

**Do NOT make this automatic.** It is deliberately opt-in, and a future session
should not "improve" it by defaulting it on for every post. The badge asserts
that a human actually checked this post's figures on a specific date.
Auto-stamping it would make that claim on posts where no check happened, which is
worse than no badge at all — readers would be trusting something nothing backs. A
post that skipped the check simply renders no badge, which is the correct
outcome.

Non-technical posts (Health, Life, career reflections) do not need it — there are
no vendor facts to verify.

## Architecture Series posts

Slugs follow `arch-NNN-short-topic-name`. Source: `posts/arch-NNN-*.html`.

The arch post pages (`blog/aws-architecture-*/index.html`) are **NOT rebuilt by
sync_blog.py** — they are built from `_templates/arch-post-template.html` at
publish time, by hand or by a per-post build script. sync_blog.py only updates
their cards in `blog/index.html`.

There is no workflow that builds them. `publish-draft.yml` used to, and this
file used to say so, but it was deleted in August 2026: it had not run
successfully since 26 July 2026 and could no longer produce a valid page. It
built from `posts/arch-002-iam-identity-center.html`, and `posts/` files carry
only front matter and a body — no `<head>`, no `<title>`, no canonical — so its
substitutions matched nothing and the output was a headless fragment. Its
post-publish steps (RAG re-index, README trigger) were already duplicated by
`on-publish.yml`, which fires on any push touching `blog/index.html` and waits
for the real Pages deploy rather than sleeping 90 seconds.

This pass-through is driven by a filename check in `sync_blog.py` (`externally_built`): only files named `arch-*`, `az-*` or `gcp-*` are treated as read-only. See "Starting a new series" below before adding any other series.

**One narrow exception:** `stamp_static_pages()` rewrites the `?v=` cache-busting
token on `blog.js` / `site-footer.js` in arch pages. See "PWA" below. It rewrites
that one token and nothing else — the rest of the page is still never regenerated.

When fixing an arch post page directly, edit `blog/aws-architecture-*/index.html` and commit. Use `posts/arch-*.html` as the canonical template reference (arch-003 is the canonical template — never re-read old posts when building new ones; use the template).

### Social preview tags on arch pages

Arch pages carry their own `<head>`, and `sync_blog.py` never rebuilds them, so
they do not inherit head changes made in `html_head()`. Every existing arch page
now carries `og:*` and `twitter:*` tags; a new page copied from one of them
inherits them, but the values are per-post and must be updated:

- `og:title` — the post title **without** the ` | Jayanth Katta Blog` suffix
  that belongs in `<title>`.
- `og:description` — same text as `<meta name="description">`.
- `og:url` — the canonical URL.

Leave `og:image` and `twitter:image` pointing at the site image. Do **not** point
them at the post's diagram: those are SVG, and LinkedIn, X and Facebook do not
render SVG for `og:image`, so the card would come out blank.

## Azure Architecture Series

Started 2026-08-14. Read `AZURE-ROADMAP.md` before writing any post — the full
numbered curriculum is decided there, and post numbers appear in published URLs
and in readers' saved progress, so a number cannot be reassigned later.

- File prefix `az-NNN-*` in `posts/`, slug prefix `azure-architecture-*`.
- Labels: `[Azure, "Azure Architecture Series"]`.
- Title format: `Azure Architecture Series #N — <Topic>` (em dash), matching the
  AWS series exactly. The sidebar progress
  widget parses `#N` **from the title**, unlike the AWS arch widget which numbers
  by position — position is only correct while nothing is ever backfilled.
- **Custom-built pages, like the AWS arch series.** `az-` is in the
  `externally_built` tuple in `sync_blog.py`, so sync never regenerates them.
  Build from `_templates/arch-post-template.html`; edit
  `blog/azure-architecture-*/index.html` directly for live fixes.
- Reference section heading is `Official Azure Reference` (singular, matching the
  arch series), and `validate_arch_post.py` requires it.

**Not an AWS comparison series.** Azure is explained on its own terms, for a
reader who may never have opened an AWS console. No running translation table,
no "the AWS equivalent is". A comparison appears only where the Azure design is
genuinely unintelligible without one, which should be rare. See the note in
`AZURE-ROADMAP.md`.

### Verification on Azure posts

Same badge, same rules, different hosts. `AWS_DOC_HOSTS` is gone; the allowlist
is now per-series `doc_hosts` in the `SERIES` dict in `validate_arch_post.py`.
Azure claims must cite `learn.microsoft.com` or `azure.microsoft.com`.

Measured 2026-08-14, both Microsoft hosts return a real HTTP 404 for a missing
page — unlike `docs.aws.amazon.com`, which answers 200 with a ~1 KB shell. So the
`az` series declares no `shell_hosts` and `--check-links` judges it on the status
code. **Do not extend the body-size heuristic to a host without probing a
known-bad URL on it first**; a wrong threshold either passes dead links or fails
live ones.

### The service widget is AWS-only, by design

`SERVICE_DOMAIN` and the "AWS services across all posts" bar list are derived
from botocore, which knows AWS and nothing else. Azure posts are now excluded
from that widget and from the domain donut (`NON_AWS_SERIES` in
`build_index_page()`), rather than being counted as posts with zero services and
filed under "Non-AWS" beside the health and career posts. A non-AWS series gets
its own widget when there is a catalogue behind it — not a share of this one.

## GCP Architecture Series

Started 2026-08-14. Read `GCP-ROADMAP.md` before writing any post — the full
numbered curriculum is decided there, and post numbers appear in published URLs
and in readers' saved progress, so a number cannot be reassigned later.

- File prefix `gcp-NNN-*` in `posts/`, slug prefix `gcp-architecture-*`.
- Labels: `[GCP, "GCP Architecture Series"]`.
- Title format: `GCP Architecture Series #N — <Topic>` (em dash). The sidebar
  progress widget parses `#N` **from the title**, as the Azure one does.
- **Custom-built pages**, like the AWS and Azure arch series. `gcp-` is in the
  `externally_built` tuple in `sync_blog.py`, so sync never regenerates them.
  Build with `scripts/build_arch_post.py` from
  `_templates/arch-post-template.html`; edit `blog/gcp-architecture-*/index.html`
  directly for live fixes.
- Reference section heading is `Official Google Cloud Reference`, and
  `validate_arch_post.py` requires it.

**This series is written while learning the material, not from experience.** It
publishes **one post a day, every day**, from no GCP background: 365 numbered
posts from 14 August 2026 to 13 August 2027, the same rhythm as the Azure
series. That makes the
verification badge more load-bearing here than anywhere else on the site — there is no experience to catch a wrong figure, so an unverified
claim ships as a confident guess. Build the architecture in a real project
before writing about it.

### Verification on GCP posts

**The badge carries the publish date on this series.** Decided 2026-08-14,
scoped to the GCP Architecture Series and overriding the general "verification
date, not publish date" rule above for these posts only — the AWS and Azure
series are unchanged. The cadence is what makes it work: a daily post is written
and verified within a day of going out, so the two dates are the same anyway.

**What that obliges you to do.** The badge still asserts a human checked the
figures, so a post written on Friday for a Saturday publish is verified *on
Saturday morning*, before it goes out. Do not write the publish date onto a check
you did the day before and leave it — that is the auto-stamping this whole
mechanism exists to prevent, just done by hand. If the re-check does not happen,
drop the badge rather than post-date it.

`validate_arch_post.py` compares `verified:` against the post's own publish date
rather than against the clock, so a post dated tomorrow and verified tomorrow
passes today. Verification dated *after* publication still fails, because nobody
checks figures that are already public.

`doc_hosts` for the `gcp` series is `cloud.google.com` and
`docs.cloud.google.com`.

**Cite the docs host.** Measured 2026-08-14 while verifying gcp-001,
`cloud.google.com/*/docs/*` answers **301 Moved Permanently** to
`docs.cloud.google.com` — the documentation moved, and that is the URL a reader
actually lands on. Pricing and marketing pages stay on `cloud.google.com`, which
is why both are allowed; a docs claim pointed at the old host is citing a
redirect, and `--check-links` will not flag it.

Measured the same day against two known-bad URLs on each host, both return a real
HTTP 404, so the series declares no `shell_hosts` and `--check-links` judges them
on the status code. As with Azure: **do not extend the body-size heuristic to a
host without probing a known-bad URL on it first.**

### Not an AWS comparison

Google Cloud is explained on its own terms, for a reader who may never have
opened an AWS console. No running translation table, no "the AWS equivalent is".
The temptation is stronger here than for Azure, because the material is being
learned against an AWS background and comparison is the fastest way to understand
it yourself — it is not the fastest way to explain it. See `GCP-ROADMAP.md`.

The card accent (`.cloud-gcp`, olive sage) already exists in `blog.css` and is
applied by `CLOUD_BY_LABEL` on the literal label string. Use the exact label and
it appears by itself. **Do not add CSS for it and do not change the colour** — it
is deliberately desaturated to sit in the site's warm palette, and Google's
four-colour mark was tried and rejected.

The service widget and domain donut stay AWS-only: `GCP Architecture Series` is
in `NON_AWS_SERIES` in `build_index_page()`, for the same reason Azure is.

## Starting a new series

Read this before publishing the first post of any new series (e.g. a daily
intelligence/editorial series). Everything below was verified against
`scripts/sync_blog.py`.

### ⚠️ Read this first — sync_blog.py will overwrite custom pages

`sync_blog.py` decides whether to leave a post's served page alone using a
**filename prefix check**:

```python
"externally_built": post_file.name.startswith(("arch-", "az-", "gcp-")),  # sync_blog.py
```

Only those three prefixes are read-only pass-through. **Any other prefix means
`sync_blog.py` regenerates and overwrites `blog/<slug>/index.html` every time
it runs.** Decide up front:

- **Custom-designed pages** (like the Architecture Series) → add the new
  prefix to that condition, otherwise the pages are destroyed on the next sync.
- **Generic pages** (like the Weekly Lab) → change nothing. Just write the
  `posts/` file and let sync_blog.py build the page.

### Checklist

1. **Frontmatter** — only `title` and `date` are required. A file missing
   either is **silently skipped** with a console note, not an error.
   ```yaml
   ---
   title: "AWS Daily Intelligence #1 — <topic>"
   date: 2026-08-04
   slug: aws-daily-intelligence-<topic>
   labels: [AWS, "AWS Daily Intelligence"]
   ---
   ```
2. **Label string must be exact and identical across every post.** Filter pill
   counts and the sidebar widgets match on the literal string. Quote any
   multi-word label.
3. **Add the label to `CATEGORY_ORDER`** in `sync_blog.py` or the series gets
   no filter pill. Position in that list controls pill order.
4. **Pick a file prefix and a slug prefix, and keep them consistent.** The arch
   series uses file `arch-NNN-*` → slug `aws-architecture-*`; they are
   deliberately different. Follow the same two-part convention.
5. **RAG needs nothing special** — the indexer reads `posts/`, so any file with
   valid frontmatter is picked up. Reindex by invoking the `blog-search-indexer`
   Lambda (see `on-publish.yml`, which does it automatically after each push).
6. **Progress widgets are not automatic.** They filter on the exact label and
   parse numbers by regex (`#N` in the arch title, `week-(\d+)` in the lab
   slug). A third series needs code added to `build_index_page()`.
7. **Run `python scripts/sync_blog.py`**, then `git add posts/ blog/`.
   `blog/index.html`, `posts.json`, `stats.json` and `rss.xml` all regenerate.

### Gotchas that cost real time

- **Never edit `posts/` or `blog/` HTML with PowerShell** — it corrupts
  encoding. Use Python `open(..., encoding='utf-8')`.
- **SVG is XML, not HTML.** `&mdash;` and `&rarr;` are undefined entities and
  make the whole file fail to render, silently. Use `&#8212;` / `&#8594;`.
- **Wrap wide tables** or the last column is clipped on mobile with no way to
  scroll to it. **Which wrapper depends on the series:**
  - Arch posts bypass `clean_html()`, so `<div style="overflow-x:auto">` works.
  - **Every other series is sync-built, and `clean_html()` strips every inline
    `style` attribute** — that wrapper silently becomes a bare `<div>` and the
    table clips anyway. Use `<div class="table-scroll">`; class attributes
    survive cleaning. The rule lives in `JK_POST_THEME_CSS`.
- **Don't lead a post's first paragraph with `<code>`** — the auto-excerpt
  strips tags without adding spaces, producing "240m5.2xlargeinstances" on the
  home page widget.
- **`posts.json` caches title/excerpt/tags for `externally_built` posts.** If a
  corrected excerpt won't take, delete that entry from `blog/posts.json` and
  re-run sync.

### Diagrams — the house standard

**There is no mermaid on this site.** Nothing renders it; a mermaid fence ships
as a raw code block. Do not author diagrams in mermaid.

**Standard for all series: a standalone SVG file referenced with `<img>`.**

```html
<img src="/blog/assets/diagrams/<prefix>-NNN-<topic>.svg" alt="Diagram: ...">
```

- File lives in `blog/assets/diagrams/`, named to match the post's file prefix
  (`arch-007-*`, `daily-001-*`).
- SVG root: `viewBox`, `style="width:100%;max-width:860px;"`, `role="img"`,
  `aria-label`. No XML declaration. First child is a background
  `<rect ... fill="#F8F7F5"/>`.
- Include a `<title>` element — it is the accessible description.
- `alt` on the `<img>` starts with `Diagram:` and describes the content, not
  the picture.
- **SVG is XML.** No named entities beyond the XML five (`&#8212;`, not
  `&mdash;`) or the file fails to render, silently and completely.
- **`<text>` does not wrap.** A line longer than the canvas does not reflow —
  it runs off the edge and is clipped, with no error. Break prose into one
  `<text>` per line yourself and grow the box and `viewBox` to match. At the
  house sizes (10.5px body text starting at x=44 on an 860px canvas) the
  practical ceiling is about **120 characters per line**.
  `python scripts/validate_diagrams.py` estimates the width of every line and
  fails on anything that overruns; it also runs automatically as part of
  `validate_arch_post.py`. Five diagrams shipped broken before it existed —
  arch-014's worst line ran to 1311px on an 860px canvas.

Why a file rather than inline SVG: `clean_html()` strips the `style` attribute
off inline SVG, so an inline diagram loses its own sizing. An `<img>` is never
descended into, so the file keeps its sizing — and it caches separately.

Inline `<symbol>`/`<use>` with official AWS icons (Weekly Lab weeks 11-12) is
the legacy approach. Prefer a file for anything new. If a diagram genuinely
needs AWS service iconography, reuse the generic `i-*` symbol ids from
week-11 rather than inventing per-post ids like week-12's `w12-*`.

## AWS Daily Intelligence series

- File prefix `daily-NNN-*` in `posts/`, slug prefix
  `aws-daily-intelligence-*` (mirrors the arch two-part convention).
- Labels: `[AWS, "AWS Daily Intelligence"]`. **`detect_tags()` keeps only
  labels present in `CATEGORY_ORDER`** — `Cloud`, `Security`, and anything
  else outside that list is silently dropped, so do not bother adding them.
- Generic sync-built pages. Do **not** add `daily-` to the `externally_built`
  check: a daily cadence cannot sustain hand-built pages, and no separate
  pipeline builds them.
- Title format: `AWS Daily Intelligence #N - <topic>`. The sidebar widget
  parses `#N` from the title, so the number must be present.
- Every technical claim cites official AWS documentation, and the post ends
  with an "Official AWS references" section of those links.

**Never explain the editorial process inside a post.** No "why this topic and
not yesterday's", no note that the day was thin, no reference to the backlog,
the ranking, or how the topic was chosen. Post #8 shipped a callout doing all
four and it was cut. The reader does not have a backlog and did not ask how the
sausage is made; a post that opens by explaining the news was slow is arguing
against itself. This is the same rule as "do not write about the weekend being
empty" in the weekly series — process commentary is not news, in either series.
Pick the topic on its merits and write about the topic.

## GCP Weekly Intelligence series

Started 2026-08-14 with a feed audit, not a post. Everything Google Cloud
shipped that week, ranked, in one post.

**Published every Saturday, covering the Monday–Friday news window.** Same rule
as the AWS weekly and for the same reason: Google publishes Monday to Friday, so
by Saturday morning the week is closed and the inventory cannot be invalidated by
something landing after publication. Title the post with the **news window**, not
the calendar week — a post titled with a range that has not finished is claiming
something it cannot know.

**Compose it on Saturday morning, from a fresh fetch.** Do not pre-write it on
Friday. Friday's release notes are still landing while Friday is happening — the
combined feed's Friday entry grows through the day and into the evening — so an
inventory built on Friday afternoon can be missing items from the window the post
claims to cover. Run `--week` on Saturday, then write. The post is cheap to
compose from the inventory; the inventory is the part that must be current.

**There is no GCP *daily intelligence* series** and one is not planned. The
GCP daily cadence is the **Architecture Series** (one post a day, see
`GCP-ROADMAP.md`); intelligence for this cloud is weekly only. Do not add a daily
intelligence series on the assumption that the AWS shape transfers — AWS runs
both because its daily series predates its weekly one.

- File prefix `gcpweekly-NNN-*` in `posts/`, slug prefix
  `gcp-weekly-intelligence-*`.
- Labels: `[GCP, "GCP Weekly Intelligence"]`.
- Title format: `GCP Weekly Intelligence #N - 10-14 August 2026`. The sidebar
  feed parses `#N`.
- Generic sync-built pages. Do **not** add the prefix to `externally_built`.
- The slug must never contain `week-<digits>` — `_week_num()` would number it as
  an AWS Weekly Lab post.

### The feed list, and what the audit found

Build the inventory with `python scripts/fetch_week_gcp.py`, never by hand and
never by asking a model to read a feed. Run `--audit --products` before a
roundup. Measured 2026-08-14:

**Feeds live on `docs.cloud.google.com`, not `cloud.google.com`,** and the GKE
feeds move again to `/static/feeds/gke-*`.

**The combined release-notes feed is day-granular, not item-granular.** One Atom
entry is one *calendar day*; its content holds every product's notes for that day
— 447 in the 4 August entry alone. Counting entries counts days. Parsing means
exploding the content HTML on `<h2 class="release-note-product-title">` and
`<h3>`.

**The combined feed is complete, not curated.** This was the open question in
`INTELLIGENCE-SERIES-BRIEF.md` and the answer inverts what it expected.
Cross-checked against eight products' own feeds: zero misses.

**The per-product feeds are the unreliable ones, and are NOT the source list.**
`compute-engine` is frozen at April 2020 — 2,307 days stale — while the combined
feed carries Compute Engine notes throughout. 9 of 39 probed feeds are over 60
days behind, and every one answers HTTP 200.

**The security bulletins feed gives every entry the same `<updated>`** — the
feed's generation time. The real date is `Published:` in the body. Trusting
`<updated>` dates the whole backlog to today.

**Truncation window is 30 days**, not AWS's 12, because the 30-entry cap is 30
days rather than 30 items. Re-measured on every `--audit` run; the script warns
when a requested start date reaches past what the feed still holds.

**The GKE bulletins feed being ~60 days stale is expected, not a fault.** Both
bulletin feeds share one `GCP-YYYY-NNN` numbering series, and the main feed is
authoritative: every recent GKE id appears in it, and it carried a newer
GKE-related bulletin (`GCP-2026-046`) than the GKE feed's newest
(`GCP-2026-037`). The GKE-only ids are 2025 ones that aged out of the main feed's
30-item cap. The GKE feed is a lagging subset, kept for cross-checking. Do not
"fix" its staleness or go hunting for a replacement.

**Deduplicate before counting, with two different rules.** Measured across two
weeks, 22% and 34% of raw notes are duplicates — but from two causes that need
opposite handling:

- *Same text, different products* — one App Engine TLS change published six
  times, once per runtime. Collapse these; the reader wants it once.
- *Same text, same product* — Container OS and GKE version notes that share
  boilerplate. These are separate real notes. Collapsing them under-counts.

**A note delimiter is a bare `<h3>`.** Google uses `<h3>` both for the note type
(`Feature`, `Security`, `Change`, `Fixed`, `Announcement`, `Deprecated`,
`Breaking`) and for headings *inside* a note, which carry attributes
(`<h3 id="release_7_0_2">`). Splitting on every h3 invented notes with no text
and gave real notes an empty body — 6% of a week. `--audit` now prints a PARSE
QUALITY line; anything above 0% means investigate before publishing, because a
counted note with no text inflates the total the roundup's headline rests on.

**The `gcpweekly-` file prefix is deliberate, like the Azure series' `azw-`.**
`externally_built` in `sync_blog.py` matches the prefix tuple
`("arch-", "az-", "gcp-")`, so a file named `gcp-weekly-001` would be treated as
a custom-built architecture page and its served page would never be generated.
`gcpweekly-` clears that check because the fourth character is not a hyphen. Do
not "tidy" it to `gcp-weekly-`.

Everything else carries over from the AWS weekly section below: scope by news
date, never repeat an announcement but do follow up on a genuine one, a quiet
week stays quiet, and no process commentary in the post.

## AWS Weekly Intelligence series

The Saturday companion to the daily series: everything AWS shipped that week,
ranked, in one post. Started 9 August 2026.

- File prefix `weekly-NNN-*` in `posts/`, slug prefix `aws-weekly-intelligence-*`.
- Labels: `[AWS, "AWS Weekly Intelligence"]`.
- Title format: `AWS Weekly Intelligence #N - 3-9 August 2026`. The sidebar feed
  parses `#N`, same as the daily series.
- Published **Saturday**, titled with the news window it covers, which is
  Monday to Friday (`3-7 August 2026`).

**Saturday is deliberate and it removes a failure mode.** AWS publishes Monday
to Friday, so by Saturday morning the week is closed and the inventory cannot
be invalidated by something landing after publication. A Sunday post titled with
the full calendar week would claim a range that had not finished. Title the post
with the news window, not the calendar week.

**Scope by news date, not publish date, and reconcile the difference.** The
daily series runs a day behind the news &mdash; a post published Tuesday covers
Monday's announcement. So the set of posts published in a week is not the set of
announcements made in that week. Scope the roundup's news sections by
announcement date, but check which dailies published during the week and account
for any that fall outside the window, rather than leaving them orphaned. Daily
#1 published Monday 3 August covering a 30 July announcement, and is linked
separately in the first roundup for exactly this reason.

**Do not write about the weekend being empty.** Check the feed for Saturday
items before publishing and include any that exist — but if there are none, say
nothing. A callout explaining an absence is process commentary, not news, and it
draws attention to a non-issue. "Across five working days" in the subtitle
carries it.

**Build the inventory with the scripts, never by hand or by asking a model to
read the feed.** `scripts/fetch_week.py` parses the raw RSS of **19 AWS feeds**;
`scripts/build_weekly_inventory.py` generates the inventory HTML with AWS's own
one-line summaries and validates every link, exiting non-zero if any fails.
Model summarisation of the feed silently drops items — it missed 24 of 66
announcements in the week of 3-7 August 2026, a third of the week, with no
error. The completeness promise this series makes to readers depends entirely
on not doing it that way again.

**Two distinct completeness failures have happened. Guard against both.**

1. *Parsing* — fixed by reading raw RSS instead of summarising it.
2. *The source list* — fixing the parsing did not fix the sources. For a month
   only two feeds were read while AWS publishes across a dozen service blogs,
   and security bulletins were documented as "NO FEED, check by hand" when a
   feed exists and had never been opened. That was ~170 unread posts.

Run `python scripts/fetch_week.py --audit` before a roundup. It probes every
feed and prints item count and date coverage, so a feed that has gone dead or
stale is visible rather than silently returning nothing. A source absent from
`SOURCES` in that file cannot be noticed as missing at run time — check the AWS
blog index for new blogs periodically and add them.

**The What's New feed is capped at exactly 100 items.** Measured 12 August 2026
that was a **12-day** window, not "about two weeks" of slack. `fetch_week.py`
prints a TRUNCATION WARNING when the requested start date is not older than the
oldest item the feed still carries, because items in range may have aged out
unseen. Do not publish an inventory that printed that warning as a complete one.
- Generic sync-built pages, like the daily series.

**The slug must never contain `week-<digits>`.** `_week_num()` in
`sync_blog.py` numbers AWS **Weekly Lab** posts by matching `week-(\d+)` against
the slug. `aws-weekly-intelligence-3-9-august-2026` is safe;
`aws-weekly-intelligence-week-32` would be picked up as a Weekly Lab number.

### Never repeat an announcement, but do follow up on a real one

Each roundup covers a **distinct date range** and its inventory comes straight
from the feed for those dates, so the same announcement cannot appear in two
weeklies. Keep it that way:

- **Scope the analysis sections to that week's announcements only.** Do not pull
  a still-`open` item from a previous week into a later roundup to pad it out.
  The backlog is a queue for *daily* deep-dives, not a source of weekly filler.
- **A genuine follow-up is not a repeat.** When AWS re-announces something —
  a Preview reaching GA, a limit raised again, a feature reaching new Regions —
  that is a new announcement with its own date and URL, and it belongs in that
  week's roundup. Network Firewall Forward Proxy, currently Preview in one
  Region, is the standing example: cover it again on GA.
- **A quiet week stays quiet.** If a week produced little, publish little. If it
  produced nothing, publish nothing. Do not manufacture a roundup out of old
  items to keep the cadence — an empty week is information, and padding destroys
  the reason to trust the page.

**`DAILY-BACKLOG.md` is the source material.** Do not re-research the week. The
backlog already holds every item ranked each day with its importance and
official link; the weekly post is that content written up, with the items that
became daily posts linked rather than repeated.

Structure that works: the week in one paragraph, a table of what was covered in
depth (linking the daily posts, one line each on the detail the announcement
omitted), then the unwritten items grouped by domain, then "What I would act
on" — three or four items worth doing something about now, which is the part
readers actually use.

### The backlog is part of the workflow

`DAILY-BACKLOG.md` in the repo root records **every** item ranked in a daily
run, not just the one that became a post. It is both the to-write queue and a
durable log of what changed and when.

This exists because the AWS What's New feed only returns about a week of
items. Roughly ten items qualify each day and one becomes a post, so anything
not written ages out of the feed and is lost with no warning.

Each daily run:

1. **Read the backlog before choosing a topic.** A held item can beat the
   day's news, and anything near a week old is about to become unwritable.
2. **Append the day's full ranking** — every item, with service, importance,
   status and official link.
3. **Update the status** of the item that became a post to `#N`.

Status values: `#N` shipped · `open` still worth writing · `aged out` no
longer current, kept for reference · `skipped` deliberately filtered.

Watch for topic-selection bias. Re-ranking from scratch each day favours the
same profile — GA, all Regions, no extra cost, well documented — so Preview
features and thinner-documented launches never win on the day. The
"Standing candidates" section at the end of the backlog is where those are
held so they are not lost to that bias.

## PWA — the site is installable

The whole site is a progressive web app, added 2026-08-11. Scope is `/`, not
`/blog/`: the nav links Home, Blog and Resume, so a blog-scoped app would eject
the reader out to the browser on the second link they tapped.

| File | Role |
| --- | --- |
| `manifest.webmanifest` (repo root) | Name, icons, `scope: "/"`, `start_url: "/"` |
| `scripts/sw.template.js` | **Service worker source — edit this** |
| `sw.js` (repo root) | Generated by sync. Must be at the root: a worker can only claim a scope at or below its own path |
| `offline.html` (repo root) | Offline fallback. Styles are inlined so it renders when nothing is cached |
| `blog/assets/icons/` | 192, 512, maskable-512, apple-touch-icon |

**Registration lives in `blog/assets/site-footer.js`** — the one script every
page loads (`index.html`, `resume.html` and `now.html` include it directly;
`blog.js` injects it on every blog surface, arch pages included). That is what
makes it reach the whole origin with no per-page edits.

**It registers on `readyState === 'complete'`, not only on the `load` event.**
`blog.js` injects this file *after* load has already fired, so a plain `load`
listener never runs on a blog page. Do not "simplify" that check away.

### Caching strategy — do not make HTML cache-first

Navigations are network-first so a live fix to a post page takes effect on the
next load, exactly as it does with no service worker. CSS and JS are
stale-while-revalidate; images are cache-first. Cross-origin (fonts, cdnjs,
Disqus, the search API) is never intercepted, and `/admin/`, `/_archive/` and
`/_templates/` are excluded.

### Cache-busting: every asset URL carries a `?v=` token

Two hashes, both computed in `sync_blog.py` from file contents, so neither is a
constant anyone has to remember to bump:

- `CSS_VERSION` — md5 of `blog.css`. Also names the SW cache (`jk-site-<hash>`),
  so a CSS change invalidates the whole cache.
- `JS_VERSION` — md5 of `blog.js` **and** `site-footer.js` combined. One hash for
  the pair on purpose: `blog.js` injects `site-footer.js` and passes its own
  token straight through, so a change to either busts both.

`stamp_static_pages()` re-stamps `JS_VERSION` on the pages sync does not build —
`index.html`, `resume.html`, `now.html`, the 18 arch pages and the arch template.

**Why this matters, concretely.** While `site-footer.js` was unversioned, a
returning visitor executed a cached copy that predated the registration code and
never registered the service worker at all — silently, with nothing in the
console. `validate_arch_post.py` check 9 guards the CSS token the same way.

## CSS and design rules

- **Identical CSS for all arch posts — zero per-post customisation.** Every post uses the same template. No unique colours, fonts, or layout per post.
- Never touch mobile styles when fixing desktop, and vice versa.
- SVG diagrams in iframe HTML files must use `width:100%;max-width:Npx`, never fixed px widths.

## Previous/Next is chronological across the whole site, not per series

**One order for every page: strict publish date, all series mixed.** A reader on
GCP #4 whose Next is an AWS post is seeing the intended behaviour. `sync_blog.py`
has always done this for the ~110 pages it generates:

```python
post["_prev"] = visible_posts[i + 1]     # next older post, any series
post["_next"] = visible_posts[i - 1]     # next newer post, any series
```

The 32 hand-built pages (`arch-`, `az-`, `gcp-`) are not regenerated by sync, so
they get the same order from `fix_series_nav.py`, which `build_arch_post.py` calls
on every build. **A page written by hand without that script keeps whatever the
template had** — that is the one path that can still diverge.

The first version of `fix_series_nav.py` scoped the nav per series. That made the
hand-built pages the only ones on the site navigating differently, and with three
series publishing daily it put a dead end at the front of each: GCP #4 had no
Next while two newer posts existed. Do not reintroduce per-series scoping.

## The failure with no symptom: a post that never reaches the index

**`sync_blog.py` rebuilds the index from `posts/`, and your `posts/` is not the
others'.** Sync from a checkout that predates another window's post and the
regenerated index, `cards.json`, `rss.xml` and `stats.json` all come out without
it. The post's own page still serves. Its card, filter pill count, RSS item and
RAG entry are gone. Nothing errors.

This is not hypothetical. On 2026-08-17, `e131603` published Azure #4 with its
card; `a9bbdd6` published GCP #4 from a checkout predating it and the Azure card
was gone; `a0f49bb` put it back. It was noticed because a person went looking for
a post and could not find it.

`python scripts/check_index_complete.py` asserts every non-draft post in `posts/`
has a served page, a card on the index or a `page/N`, a `cards.json` entry and an
`rss.xml` item — and that `cards.json` holds nothing `posts/` no longer produces,
which is the renamed-post case. It exits non-zero, runs in `prepublish.py`, and
runs in CI even on pushes that touched only generated files. Verified against
`a9bbdd6`: it reports all three missing surfaces and fails.

**Rebase before sync, every time.** The check catches it after the fact; rebasing
is what prevents it.

## The search widget cannot answer "latest"

`/blog/` search is a vector search over post text, so "latest GCP post" ranks by
**semantic similarity, not date**. Measured 2026-08-17: it answered
`GCP Weekly Intelligence #1 - 10-14 August 2026` — a title containing a date
range reads as recency — while GCP Architecture #4, published that morning, was
in the index and returned correctly for a content query about service enablement.

So a wrong answer to "latest" is **not** evidence of a stale index. Check the
index directly before assuming staleness:

```bash
curl -s -X POST https://37arp5b92a.execute-api.us-east-1.amazonaws.com/search -H 'Content-Type: application/json' -d '{"query":"<a distinctive phrase from the post>"}'
```

A chunk of the blog index page (`Blog post index — most recent first`) is also in
the corpus and scores well on "newest"/"latest" queries, which makes this worse.
For "what published today", the home page and `/blog/` are the answer; the widget
is for finding posts by content.

## After publishing a new arch post

1. **`python scripts/publish.py`** — this is steps 1, 2 and 5 of the old list, in
   the order that is correct, plus a rebase before the sync and a re-check of the
   remote afterwards. It stops before committing. Add `--offline` to skip the
   checks that fetch vendor pages; name a post (`publish.py arch-025`) to scope
   the per-post checks to it.
2. `git add blog/ posts/ scripts/ index.html resume.html now.html sw.js`
   (broad add — picks up all regenerated pages; `publish.py` prints this line for
   you). **The root files are not optional:** sync regenerates `sw.js` and
   re-stamps the `?v=` token on `index.html`, `resume.html` and `now.html`.
   Leaving them out ships a service worker whose precache asks for asset URLs no
   page requests.
3. Check `git status` is clean before committing — a leftover modified root
   file means step 2 was too narrow.
4. Commit and ask Jayanth to push

What `publish.py` runs on your behalf, so the names are still findable:
`validate_arch_post.py` (unclosed comments that silently swallow a post body,
unresolved `{{PLACEHOLDER}}`s, missing sections, empty nav boxes, broken or
absent diagrams, missing alt text, wrong labels, and a missing `posts/` source
file that would leave the post out of RAG), then `sync_blog.py`, then
`prepublish.py` — whose site-wide half catches damage to pages this post never
touched.

Do not hand-inspect for these problems — the validator exists because every
check in it corresponds to a bug that shipped or nearly shipped.

## Post count and stats

- `blog/index.html` — hardcoded hero stats and filter pill counts (updated by sync_blog.py)
- `blog/stats.json` — used by the portfolio home page
- `blog/posts.json` — used by the portfolio home page latest posts widget (top 7 only)

All three are updated automatically when sync_blog.py runs.

## Blog index filtering (blog/index.html + blog/assets/blog.js)

Each post card has `data-date="YYYY-MM-DD"`, `data-tags`, `data-title`, `data-excerpt`.
Filters: topic pills + year pills + month pills (month row appears only when a year is selected).
Search matches title, excerpt, tags, and date.

## Disqus

Shortname: `jayanthkatta`
