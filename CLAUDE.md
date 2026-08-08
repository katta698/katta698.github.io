# Claude Code Instructions — katta698.github.io

## Workflow rules

- Always `git pull --rebase` before any edits. GitHub Actions auto-commits posts.json after every push.
- Never commit or push without explicit instruction. Jayanth pushes himself.
- After `sync_blog.py` runs, stage ALL modified files under `blog/` — not just the new post's directory. Older posts get regenerated too (widgets, date format, CSS).

## Which folder am I in?

Two worktrees share one repository. **Check before doing anything.**

| Folder | Branch | Used for |
| --- | --- | --- |
| `C:\Projects\Engineering\katta698.github.io` | `main` | Architecture Series, Weekly Lab, site work |
| `C:\Projects\Engineering\katta698-daily` | `daily` | AWS Daily Intelligence series |

`git worktree list` confirms both. They have separate working files and
separate staging areas but one shared history, so a commit in either is
visible to the other immediately.

Two worktrees cannot check out the same branch — that is why the daily
worktree is on `daily` rather than `main`.

### Publishing from the daily worktree

`daily` is a staging branch, not a long-lived one. Rebase it onto `main` before
writing, then push it straight to remote `main`:

```
cd C:\Projects\Engineering\katta698-daily
git fetch origin
git rebase origin/main          # do this BEFORE running sync
# write the post, run scripts/sync_blog.py, commit
git push origin daily:main      # fast-forwards remote main
git rebase origin/main          # realign after the Actions bot commits
```

`git push origin daily:main` publishes to `main` without a merge commit,
provided `daily` was rebased first. If it is rejected, `daily` has fallen
behind — rebase and push again.

**Rebase before running sync, not just before editing.** The daily worktree
has its own copy of `posts/`, so it does not see a post written in the other
worktree until it rebases. Running sync first would regenerate the whole index
without that post. See "Publishing in parallel" below for what that breaks.

## Publishing in parallel

Posts are often written in two sessions at once. Conflicts between them are
normal and harmless **if** you know which files are source and which are
generated.

| | Files | Conflicts? |
| --- | --- | --- |
| **Source** | `posts/<name>.html`, `blog/assets/diagrams/*.svg` | Never — each post is its own filename |
| **Generated** | `blog/posts.json`, `blog/index.html`, `blog/rss.xml`, `blog/stats.json`, every rebuilt `blog/<slug>/index.html` | Every parallel publish |

`sync_blog.py` rebuilds the whole site index from `posts/`, so any two people
publishing rewrite the same generated files. The Actions bot also auto-commits
`blog/posts.json` after every push, which is a third writer.

Worktrees make this *more* likely, not less: each worktree has its own `posts/`
and cannot see the other's new post until it rebases. That is why the rule is
rebase before **sync**, not merely before editing.

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

## Blog post structure

Two files per post:
- `posts/<slug>.html` — YAML frontmatter + body (source; RAG indexer reads this)
- `blog/<slug>/index.html` — full served page (what GitHub Pages delivers)

**Always edit `blog/<slug>/index.html` for live fixes. `posts/` is for RAG only.**

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

The arch post pages (`blog/aws-architecture-*/index.html`) are **NOT rebuilt by sync_blog.py** — they are built by `.github/workflows/publish-draft.yml`. sync_blog.py only updates their cards in `blog/index.html`.

This pass-through is driven by a filename check in `sync_blog.py` (`externally_built`): only files named `arch-*` are treated as read-only. See "Starting a new series" below before adding any other series.

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

## Starting a new series

Read this before publishing the first post of any new series (e.g. a daily
intelligence/editorial series). Everything below was verified against
`scripts/sync_blog.py`.

### ⚠️ Read this first — sync_blog.py will overwrite custom pages

`sync_blog.py` decides whether to leave a post's served page alone using a
**filename prefix check**:

```python
"externally_built": post_file.name.startswith("arch-"),   # sync_blog.py
```

Only `arch-*` files are read-only pass-through. **Any other prefix means
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
   Lambda (see `publish-draft.yml`).
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

## AWS Weekly Intelligence series

The Sunday companion to the daily series: everything AWS shipped that week,
ranked, in one post. Started 9 August 2026.

- File prefix `weekly-NNN-*` in `posts/`, slug prefix `aws-weekly-intelligence-*`.
- Labels: `[AWS, "AWS Weekly Intelligence"]`.
- Title format: `AWS Weekly Intelligence #N - 3-9 August 2026`. The sidebar feed
  parses `#N`, same as the daily series.
- Published **Sunday**, covering that week's news (Mon-Fri announcements).
- Generic sync-built pages, like the daily series.

**The slug must never contain `week-<digits>`.** `_week_num()` in
`sync_blog.py` numbers AWS **Weekly Lab** posts by matching `week-(\d+)` against
the slug. `aws-weekly-intelligence-3-9-august-2026` is safe;
`aws-weekly-intelligence-week-32` would be picked up as a Weekly Lab number.

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

## CSS and design rules

- **Identical CSS for all arch posts — zero per-post customisation.** Every post uses the same template. No unique colours, fonts, or layout per post.
- Never touch mobile styles when fixing desktop, and vice versa.
- SVG diagrams in iframe HTML files must use `width:100%;max-width:Npx`, never fixed px widths.

## After publishing a new arch post

1. Run `python scripts/validate_arch_post.py` — **must report 0 errors.**
   It checks for unclosed comments (which silently swallow the entire post
   body), unresolved `{{PLACEHOLDER}}`s, missing sections, empty nav boxes,
   broken/invalid diagram SVGs, missing alt text, wrong labels, and a missing
   `posts/` source file (which would leave the post out of RAG).
2. Run `python scripts/sync_blog.py`
3. `git add blog/ posts/ scripts/` (broad add — picks up all regenerated pages)
4. Commit and ask Jayanth to push

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
