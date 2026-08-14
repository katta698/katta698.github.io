# Brief: starting an Intelligence Series for Azure or GCP

Written 2026-08-14. Read this and `NEW-SERIES-BRIEF.md` before writing anything.

An intelligence series is **not** the same shape of work as an architecture
series, and the difference is the whole reason this file exists.

An architecture post has no external dependency: you pick a topic and write it.
An intelligence post makes a promise of **completeness** — "here is everything
that shipped this week" — and that promise rests entirely on the feed list being
right. A reader cannot check it. Nothing errors when it is wrong.

## Do one cloud at a time

Azure first, then GCP, in separate sessions. Not because the code conflicts, but
because the work is *judgement about sources*, and that judgement does not
transfer: Azure publishes through a small number of central feeds, Google Cloud
publishes release notes per product. Doing both at once means neither list gets
the attention that is the entire value of the series.

Finish one cloud's audit, publish from it for a couple of weeks, and only then
start the second.

## The first deliverable is an audit, not a post

Do not write post #1 until a feed audit has been run and read. The AWS series
failed twice, and both failures were silent:

1. **Parsing.** A model was asked to read the feed and summarise it. It missed
   **24 of 66 announcements** in one week — a third of the week — with no error.
   Fixed by parsing raw RSS in `scripts/fetch_week.py` instead.

2. **The source list.** Fixing the parsing did not fix the sources. For a month
   only two feeds were read while AWS publishes across a dozen service blogs,
   and security bulletins were documented as "NO FEED, check by hand" when a
   feed existed and had never been opened. That was roughly **170 unread posts**.

The second failure is the instructive one: the code was correct and the output
looked complete. A source absent from the list cannot be noticed as missing at
run time.

## What the audit must show

Model it on `python scripts/fetch_week.py --audit`, which probes every feed and
prints item count and date coverage, so a feed that has gone dead or stale is
visible rather than silently returning nothing.

For each feed, print:

- **item count** — zero means broken, not quiet
- **date range covered** — oldest and newest item
- **truncation window** — how far back the feed still reaches

**Measure the truncation window; do not assume it.** The AWS What's New feed is
capped at exactly 100 items. Measured on 12 August 2026 that was a **12-day**
window, not "about two weeks" of slack. `fetch_week.py` prints a TRUNCATION
WARNING when the requested start date is not older than the oldest item the feed
still carries. An inventory that printed that warning is not a complete one.

Azure and Google Cloud will have their own caps and their own behaviour. Find
them by measurement.

## Known shape of each vendor's sources

Starting points only — verify and extend, do not treat as complete.

**Azure.** Publishes through a small number of central channels: the Azure
Updates feed, the Azure blog, and per-service blogs. Security advisories are
separate from feature announcements. The central feed is the backbone; the
per-service blogs carry the detail the announcement omits.

**Google Cloud.** The hard case. Release notes are **fragmented per product**,
each with its own page, alongside a combined feed and the Cloud blog. Establish
early whether the combined feed is genuinely complete or a curated subset — if
it is curated, the series needs the per-product notes and the source list is
much longer. This is exactly the failure mode that cost AWS ~170 posts.

## Carry over from the AWS series unchanged

These are in `CLAUDE.md` and are not per-cloud decisions:

- **Build the inventory with scripts, never by hand and never by asking a model
  to read the feed.** This is the rule that failure #1 produced. There is no
  version of "just summarise the feed" that is safe.
- **A quiet week stays quiet.** If a week produced little, publish little. If it
  produced nothing, publish nothing. Padding a roundup with old items destroys
  the reason to trust the page.
- **Never repeat an announcement across roundups**, but a genuine follow-up — a
  Preview reaching GA, a limit raised again — is a new announcement with its own
  date, and belongs in that week's post.
- **No process commentary in posts.** No notes about the backlog, the ranking,
  why this topic and not another, or the week being thin. The reader does not
  have a backlog and did not ask how the sausage is made.
- **Scope by news date, not publish date**, and reconcile the difference — a
  daily post published Tuesday covers Monday's announcement, so the set of posts
  published in a week is not the set of announcements made in it.
- **A backlog file per series**, modelled on `DAILY-BACKLOG.md`: every item
  ranked each day, not just the one that became a post. It exists because items
  age out of the feed and are then unwritable. Watch for topic-selection bias —
  re-ranking from scratch each day favours GA, all-Regions, no-extra-cost
  launches, so Preview and thinly-documented items never win on the day. Hold
  those in a standing-candidates section.
- **Verification badge rules apply**, including per-vendor doc hosts — see
  `NEW-SERIES-BRIEF.md`, which explains why no non-AWS post can carry a badge
  until `AWS_DOC_HOSTS` in `validate_arch_post.py` becomes per-series.

## Plumbing

Most of `NEW-SERIES-BRIEF.md` applies. Specifically for an intelligence series:

- **Generic sync-built pages.** Do **not** add the prefix to `externally_built`
  in `sync_blog.py`. A daily cadence cannot sustain hand-built pages — this is
  why the AWS daily series is sync-built while the arch series is not.
- **Label must be in `CATEGORY_ORDER`** or the series gets no filter pill, and
  `detect_tags()` drops it silently.
- **Title must contain `#N`** — the sidebar widget parses it.
- **Slug must never contain `week-<digits>`.** `_week_num()` matches
  `week-(\d+)` against slugs to number AWS Weekly Lab posts, and would pick it
  up as one.
- **Sidebar widget needs code** in `build_index_page()`; it is not automatic.

## Suggested order

1. Read `CLAUDE.md` (AWS Daily and Weekly Intelligence sections) and
   `NEW-SERIES-BRIEF.md`.
2. Discover the vendor's announcement feeds. Check the vendor's blog index for
   feeds that exist but are not obvious.
3. Write the fetch script with an `--audit` mode, modelled on
   `scripts/fetch_week.py`.
4. **Run the audit and read it.** Fix dead or missing feeds. Record the measured
   truncation window.
5. Only then write post #1.

Confirm the chain end to end on post #1 before writing post #2.
