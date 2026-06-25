# Local posts

Write posts directly here as Markdown — no Blogger required. Each `.md` file
becomes a post the next time `scripts/sync_blog.py` runs.

## Format

```markdown
---
title: Week 6 — Something Great
date: 2026-06-29
labels: [AWS, Terraform]
slug: week-6-something-great   # optional — defaults to a slug of the title
---

Write the body in Markdown. Raw HTML is also allowed inline, so you can use
the canonical theme's component classes directly when you need them:

<div class="callout amber">
A real heads-up the reader needs.
</div>

<figure class="screenshot">
  <img src="https://raw.githubusercontent.com/katta698/.../screenshot.png" alt="..."/>
  <figcaption>What this shows</figcaption>
</figure>
```

## What happens automatically at sync time

Local posts go through the exact same pipeline as Blogger posts
(`clean_html()` in `sync_blog.py`), so you get for free:
- Canonical `#jk-post` theme (orange/clean design)
- Image sharpening + the zoom lightbox on every screenshot/diagram
- Tag detection from the `labels` front matter (must match the site's
  taxonomy: AWS, Terraform, Kubernetes, GitOps, AI, Tech, Career, Health, Life
  — case-insensitive — else it defaults to "Tech")
- Title/description/reading-time/excerpt generation

## Required front matter

- `title` — exact post title
- `date` — `YYYY-MM-DD`, used for sorting and the displayed date

## Optional front matter

- `labels` — list of tags; omit for just `["Tech"]`
- `slug` — explicit URL slug; omit to auto-generate from the title
