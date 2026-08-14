# Brief: starting an Azure (then GCP) Architecture Series

Written 2026-08-14. Read this before writing the first post. Everything below
was verified against the code on that date, not recalled.

The site already runs three AWS series. The machinery that makes them work is
AWS-coupled in specific, findable places. This document lists them so a new
session fixes the plumbing **before** post #1 rather than after publishing
URLs that then have to change.

## Recommendation: one series first

Start with **Azure Architecture only**. Not GCP in parallel, and not a daily
intelligence twin.

- The badge is the site's trust mechanism, and it only means something if every
  printed figure is actually checked against vendor docs. Three series at once
  triples that burden in the week it is least likely to be absorbed.
- GCP is a copy of whatever groove Azure cuts. Doing Azure alone makes the
  generalization real; doing both at once makes it theoretical.
- A daily-intelligence series for another cloud needs its own verified feed
  list. `scripts/fetch_week.py` `SOURCES` is 19 **AWS** RSS feeds. The weekly
  roundup's completeness promise already broke twice over source lists (~170
  unread posts once). Do not inherit that problem into a second cloud casually.

## Blockers — must be fixed before the first post

### 1. `sync_blog.py:945` — `externally_built`

```python
"externally_built": post_file.name.startswith("arch-"),
```

Only `arch-*` files are read-only pass-through. **Any other prefix means sync
regenerates and overwrites `blog/<slug>/index.html` on every run.**

Decide up front:

- Custom-designed pages, like the Architecture Series → add the new prefix here,
  or the pages are destroyed on the next sync.
- Generic sync-built pages, like the daily series → change nothing.

Recommended: custom (`az-`), to match the arch series' quality bar.

### 2. `sync_blog.py:721` — `CATEGORY_ORDER`

A label absent from this list gets no filter pill, and `detect_tags()` drops it
silently. Add the exact label string. Position controls pill order.

### 3. `validate_arch_post.py:434` — the badge cannot work yet

```python
AWS_DOC_HOSTS = ('docs.aws.amazon.com', 'aws.amazon.com')
```

This is a module-level constant, not per-series. Every `verified_claim` must
cite one of these hosts, so **no Azure or GCP post can carry a verified badge
today** — each claim fails the "source is not the vendor's own documentation"
check.

This is the real blocker. The badge asserts a human checked the figures; it is
the reason the series is trustworthy. Fix: move the host allowlist into the
existing `SERIES` dict as a per-series `doc_hosts` tuple.

Azure: `learn.microsoft.com`, `azure.microsoft.com`
GCP: `cloud.google.com`

### 4. The dead-link probe is AWS-shaped

`docs.aws.amazon.com` is client-side routed and answers **HTTP 200 for pages
that do not exist**, returning a ~1 KB shell — hence `DOCS_SHELL_BYTES` judging
body size rather than status code. Microsoft Learn and `cloud.google.com` fail
differently. Establish how each behaves on a known-bad URL before trusting
`--check-links` for them, otherwise dead links pass.

### 5. The service widget is botocore-derived

`SERVICE_DOMAIN`, `load_service_catalogue()` and the "services across all posts"
widget come from **botocore**, which only knows AWS (425 services). Azure and
GCP have no equivalent offline catalogue in this repo. Either source one or
scope the widget to AWS posts explicitly — today it would just find nothing and
show an empty group.

### 6. Sidebar progress widgets are not automatic

They filter on the exact label and parse `#N` from the title by regex, in
`build_index_page()`. A new series needs code added there.

## Conventions to fix now (they end up in published URLs)

Follow the existing two-part convention — file prefix and slug prefix are
deliberately different:

| | File prefix | Slug prefix | Label |
| --- | --- | --- | --- |
| Existing | `arch-NNN-` | `aws-architecture-` | `AWS Architecture Series` |
| Proposed | `az-NNN-` | `azure-architecture-` | `Azure Architecture Series` |
| Later | `gcp-NNN-` | `gcp-architecture-` | `GCP Architecture Series` |

The label string must be **exact and identical in every post** — pill counts and
sidebar widgets match the literal string. Quote multi-word labels in YAML.

Check the slug prefix does not collide with `_week_num()`, which matches
`week-(\d+)` against slugs to number AWS Weekly Lab posts.

## Write the curriculum before post #1

The request is "basics to advanced covering all the topics". The AWS series grew
organically and now has gaps that are awkward to backfill, because post numbers
appear in published URLs and in the sidebar widget — #7 cannot be inserted
between #6 and #7 later.

So produce a numbered outline first, committed as `AZURE-ROADMAP.md`, covering
the full arc before writing any post. Expect to revise it; the point is that
numbering is a decision made once, deliberately.

## The standards that carry over unchanged

These are not negotiable per-series and already documented in `CLAUDE.md`:

- **Every figure printed needs a `verified_claim`**, not just the two the
  validator enforces as a floor. `python scripts/audit_claims.py` reports the
  coverage.
- **Derived figures carry their arithmetic** (`derive:` / `expect:`), recomputed
  at build time. Break-evens, ratios and effective rates are where every error
  has actually happened — arch-018 cited two real AWS pages and still shipped a
  wrong break-even.
- **Never put `verified:` in a build script template.** Writing the claim list is
  work a script cannot fake, which is the entire point. No personal check → no
  badge. That is the correct outcome, not a gap to fill.
- **Diagrams are standalone SVG files** referenced with `<img>`, validated by
  `scripts/validate_diagrams.py`. No mermaid — nothing on this site renders it.
- **No process commentary inside posts.** No notes about the backlog, the
  ranking, or why this topic and not another.
- `python scripts/validate_arch_post.py` must report **0 errors** before publish.

## Suggested order of work for the new session

1. Read `CLAUDE.md`, especially "Starting a new series".
2. Generalize `AWS_DOC_HOSTS` into a per-series `doc_hosts` in the `SERIES`
   dict, and add an `az` entry.
3. Establish how `learn.microsoft.com` responds to a known-bad URL; adapt the
   link probe.
4. Add `az-` to `externally_built` and the label to `CATEGORY_ORDER`.
5. Add the sidebar widget branch in `build_index_page()`.
6. Decide the service-widget behaviour for non-AWS posts.
7. Write `AZURE-ROADMAP.md` — the full numbered outline.
8. Only then write post #1, using `_templates/arch-post-template.html` via
   `scripts/build_arch_post.py`.

Confirm the whole chain works end to end on post #1 before writing post #2.

## Known pre-existing bug, unrelated but in the same path

`_templates/arch-post-template.html` carries
`blog.css?v=<hash>?v={{CSS_VERSION}}` — a doubled query token, because
`stamp_static_pages()` stamps a line that already holds the placeholder. It does
not break rendering (static servers ignore the query) but the cache-bust token
is not what it appears to be, and every new arch-style page inherits it. Worth
fixing in `sync_blog.py` (skip lines containing a placeholder) while touching
this machinery anyway.
