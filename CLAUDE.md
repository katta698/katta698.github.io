# Claude Code Instructions — katta698.github.io

## Workflow rules

- Always `git pull --rebase` before any edits. GitHub Actions auto-commits posts.json after every push.
- Never commit or push without explicit instruction. Jayanth pushes himself.
- After `sync_blog.py` runs, stage ALL modified files under `blog/` — not just the new post's directory. Older posts get regenerated too (widgets, date format, CSS).

## Blog post structure

Two files per post:
- `posts/<slug>.html` — YAML frontmatter + body (source; RAG indexer reads this)
- `blog/<slug>/index.html` — full served page (what GitHub Pages delivers)

**Always edit `blog/<slug>/index.html` for live fixes. `posts/` is for RAG only.**

## Architecture Series posts

Slugs follow `arch-NNN-short-topic-name`. Source: `posts/arch-NNN-*.html`.

The arch post pages (`blog/aws-architecture-*/index.html`) are **NOT rebuilt by sync_blog.py** — they are built by `.github/workflows/publish-draft.yml`. sync_blog.py only updates their cards in `blog/index.html`.

This pass-through is driven by a filename check in `sync_blog.py` (`externally_built`): only files named `arch-*` are treated as read-only. See "Starting a new series" below before adding any other series.

When fixing an arch post page directly, edit `blog/aws-architecture-*/index.html` and commit. Use `posts/arch-*.html` as the canonical template reference (arch-003 is the canonical template — never re-read old posts when building new ones; use the template).

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
- **Wrap wide tables** in `<div style="overflow-x:auto">` or the last column is
  clipped on mobile with no way to scroll to it.
- **Don't lead a post's first paragraph with `<code>`** — the auto-excerpt
  strips tags without adding spaces, producing "240m5.2xlargeinstances" on the
  home page widget.
- **`posts.json` caches title/excerpt/tags for `externally_built` posts.** If a
  corrected excerpt won't take, delete that entry from `blog/posts.json` and
  re-run sync.

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
