# The announcement store

One JSON object per line, one file per cloud per month:

```
intelligence/data/<cloud>/<YYYY-MM>.jsonl
```

Written by `scripts/news_store.py`. Read it with that module rather than by
hand — the identity rules below are not obvious and getting them wrong changes
counts silently.

## Why it exists

The three fetchers (`fetch_week.py`, `fetch_azure_week.py`,
`fetch_week_gcp.py`) print a window and discard it. The vendors' own feeds are
short — AWS What's New holds ~100 items, measured at **12 days** on 2026-08-12,
and the GCP combined feed truncates at **30 days**. An announcement not written
down within days of publication becomes unrecoverable.

The weekly roundups capture their own window, but in prose, in HTML. Nothing
held the series as data, so "what has changed on S3 lately" could only reach as
far back as the feed still went.

## Fields

| Field | Meaning |
| --- | --- |
| `id` | sha1 of cloud + date + headline + url + context, first 16 hex |
| `cloud` | `aws`, `azure`, `gcp` |
| `date` | the announcement's own date, not the fetch date |
| `headline` | AWS/Azure feed title; for GCP, `product: summary` |
| `summary` | GCP note body. Empty for AWS and Azure, whose feeds carry a title only |
| `url` | official link |
| `source` | which feed it came from |
| `product`, `kind`, `context` | GCP only — product heading, note type, sub-release |
| `services` | tagged service names. **Not yet populated** |
| `first_seen` | when this store first recorded it, which is not the publish date |

## Two rules that matter

**`context` is part of the identity, on purpose.** Container Optimized OS ships
one release note per milestone, so a single kernel CVE fixed in cos-138,
cos-125 and cos-121 is three separate notes with byte-identical text and the
same day-anchor URL. On the first ingest, 82 of 120 id collisions differed only
by context — keying without it would have silently dropped 246 real notes and
under-counted the totals the roundups rest on. Rows identical *including*
context are true duplicates (one note reached by two feeds) and do collapse.

**Ingest is idempotent.** Re-running merges rather than duplicates, preserves
`first_seen`, and never blanks a populated field from a thinner later fetch.
Verified by running it twice: the second run reported 0 new, 0 enriched.

## Coverage on the first ingest, 2026-09-04

| Cloud | Records | Earliest |
| --- | --- | --- |
| AWS | 517 | 2025-11-06 |
| Azure | 5,237 | 2024-05-20 |
| GCP | 1,056 | 2025-09-10 |

Far more than the 12-day worry, because only *What's New* truncates that hard —
the other 18 AWS feeds reach back much further. Azure's Updates API is
queryable by date and goes back years.

## Not done yet

- **Service tagging.** `services` is empty on every record. Matching on a bare
  name over-matches badly: `ARM` hits arm64 kernel CVEs, and an S3 search
  catches any post that merely mentions S3. The catalogues in
  `scripts/*_services.json` are the input, and `aws_services.json` already
  carries an `ambiguous` flag for exactly this.
- **Backfill from published roundups.** The 10 weekly inventories and
  `DAILY-BACKLOG.md` hold items that may predate what the feeds still serve.
- **Scheduled ingest.** Runs by hand today. It belongs in a GitHub Actions
  cron so it does not depend on a laptop being awake.
