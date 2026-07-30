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

The 6 arch post pages (`blog/aws-architecture-*/index.html`) are **NOT rebuilt by sync_blog.py** — they are built by `.github/workflows/publish-lab-draft.yml`. sync_blog.py only updates their cards in `blog/index.html`.

When fixing an arch post page directly, edit `blog/aws-architecture-*/index.html` and commit. Use `posts/arch-*.html` as the canonical template reference (arch-003 is the canonical template — never re-read old posts when building new ones; use the template).

## CSS and design rules

- **Identical CSS for all arch posts — zero per-post customisation.** Every post uses the same template. No unique colours, fonts, or layout per post.
- Never touch mobile styles when fixing desktop, and vice versa.
- SVG diagrams in iframe HTML files must use `width:100%;max-width:Npx`, never fixed px widths.

## After publishing a new arch post

1. Run `python scripts/sync_blog.py`
2. `git add blog/ scripts/sync_blog.py` (broad add — picks up all regenerated pages)
3. Commit and ask Jayanth to push

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
