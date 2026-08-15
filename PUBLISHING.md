# Publishing runbook

A human runbook for this site. `CLAUDE.md` is written *at* Claude and assumes a
lot; this is written at you, assumes nothing, and every command in it works with
no AI involved at all.

If you read one section, read **[The 60-second version](#the-60-second-version)**.

---

## Can I publish if Claude is down?

Yes. Nothing in this pipeline requires an AI. Claude writes prose and catches
mistakes; the publishing machinery is plain Python and git, and it runs the same
whether a model was involved or not.

The only thing you lose is the drafting help. Everything below is yours.

```bash
python scripts/sync_blog.py
```

That one command rebuilds the entire site from `posts/`. It is the heart of the
whole system. If you remember nothing else, remember that the source of truth is
the `posts/` folder and that command turns it into a website.

---

## The 60-second version

Writing a post is three steps, always, for every series:

1. **Write one file** into `posts/`. Front matter at the top, HTML body below.
2. **Build.** Either `sync_blog.py` (most series) or `build_arch_post.py` (the
   three architecture series). Which one depends only on the filename prefix.
3. **Check, then commit and push.**

```bash
python scripts/prepublish.py --series az     # 4 checks; must pass
python scripts/sync_blog.py                  # rebuild the site
git add posts/ blog/ index.html resume.html now.html sw.js
git commit -m "Post title"
git push origin HEAD:main
```

Everything after the push is automatic. You are done.

---

## The one distinction that explains everything

Almost all the confusion here comes from there being **two kinds of post**, and
the difference being invisible unless someone tells you. So:

| | Sync-built | Custom-built |
| --- | --- | --- |
| **Which** | Weekly Lab, Daily Intelligence, all Weekly Intelligence, personal posts | The three Architecture Series |
| **Filename prefix** | anything else | `arch-`, `az-`, `gcp-` |
| **Who builds the page** | `sync_blog.py`, every run | `build_arch_post.py`, once |
| **Rebuilt on later syncs?** | Yes, every time | **Never** |
| **To fix it later** | edit `posts/`, re-run sync | edit `blog/<slug>/index.html` directly |

That last row is the one that bites. For a sync-built post, `posts/` is the
truth and the served page is disposable. For an arch post it is the **other way
round**: the served page is the artifact, and `posts/` is kept only so the
search index and the RAG widget can read it.

The switch is a literal prefix check in `sync_blog.py`:

```python
"externally_built": post_file.name.startswith(("arch-", "az-", "gcp-")),
```

Nothing else distinguishes them. A post named `arch-021-*.html` is pass-through;
rename it and sync will overwrite its page on the next run.

---

## Writing the file: no, you do not start from a blank page

**You never write a complete HTML page.** No `<html>`, no `<head>`, no `<title>`,
no CSS, no nav, no footer. The builder adds all of that. What you write is the
front matter plus the *body* — and the body is not free-form HTML either. It has
a fixed shape and a fixed set of CSS classes, and using those is the entire
mechanism by which your post looks like every other post.

**Start by copying the skeleton:**

```bash
cp _templates/post-skeleton.html posts/daily-021-your-topic.html
```

That file has the structure already laid out, with the class vocabulary and the
non-obvious rules listed at the bottom. Replace the content; do not edit the
skeleton itself.

For an **architecture post** (`arch-`/`az-`/`gcp-`) don't use that skeleton —
copy the most recent post in that series instead, then run
`build_arch_post.py`. Those posts have named sections the builder slots into
`_templates/arch-post-template.html`, plus extra front-matter fields
(`problem`, `builds`, `catch`) that the others don't use.

### The shape of a body

```html
<div id="jk-post">
  <div class="post-header">
    <div class="post-eyebrow">Series &middot; 15 August 2026</div>
    <div class="post-title">…</div>
    <div class="post-subtitle">…</div>
    <div class="post-meta"><span>…</span></div>
  </div>
  <div class="container">
    <div class="toc">…</div>
    <div class="section" id="what-changed">
      <h2>What changed</h2>
      <p>…</p>
    </div>
    <div class="section" id="cost">…</div>
  </div>
</div>
```

Header, then a `container`, then a `section` per heading. That's it. Most of a
post is `<p>` inside a `<div class="section">`.

### How consistency is actually enforced

Not by you matching a design — by you using classes the CSS already defines.
There are 54 of them. The ones you'll use constantly:

| Need | Class |
| --- | --- |
| A heading + its prose | `section` |
| Something the reader would miss | `callout` |
| Something that will cost money or data | `warning-box` |
| A wide table | `table-scroll` **(wrap every one)** |
| Before/after comparison | `before-after` + `before-card` / `after-card` |
| A row of figures | `stat-row` + `stat-box` / `stat-val` / `stat-lbl` |

The full list is at the bottom of the skeleton file.

**A class not in that list renders as unstyled plain text.** That — not layout,
not typography — is the usual cause of "my post doesn't look like the others".

**And never use `style="…"`.** `clean_html()` strips every inline style
attribute from sync-built posts, silently: your `<div>` stays, your styling
does not. This is why wide tables need `class="table-scroll"` and not
`style="overflow-x:auto"` — the second one looks right in your editor and clips
on the live site.

---

## What every file is for

### You write these

| Path | What it is |
| --- | --- |
| `posts/<name>.html` | **The source.** Front matter + body. One file per post. |
| `blog/assets/diagrams/<name>.svg` | Diagrams, one file each |
| `blog/<slug>/index.html` | The served page — **you edit this only for arch/az/gcp posts** |

### The machinery

| Path | What it does |
| --- | --- |
| `scripts/sync_blog.py` | Rebuilds the whole site from `posts/`. The main event. |
| `scripts/build_arch_post.py` | Builds one architecture-series page from the template |
| `scripts/prepublish.py` | Runs all four checks. Run before publishing. |
| `_templates/arch-post-template.html` | The page shell every arch post is built from |
| `blog/assets/blog.css` · `blog.js` | Shared styling and behaviour for every page |

### Generated — never edit these by hand

`sync_blog.py` rewrites all of them from scratch on every run. Editing one is
wasted work; your change disappears on the next sync.

```
blog/index.html          the blog listing, hero stats, filter pills
blog/page/2..N/          pagination
blog/posts.json          feeds the home page "latest posts" widget
blog/cards.json          card data
blog/stats.json          feeds the portfolio home page counters
blog/rss.xml             the feed
blog/drafts/index.html   unlisted index of draft: true posts
sw.js                    the service worker (PWA)
```

Plus the `?v=` cache-busting token inside `index.html`, `resume.html`,
`now.html` and every arch page — sync re-stamps those, which is why they show up
as modified after a CSS change you didn't make.

---

## Front matter

The block at the top of every `posts/` file, between `---` lines.

```yaml
---
title: "Azure Architecture Series #3 — Managed Identities"
date: '2026-08-15T09:00:00'
slug: azure-architecture-managed-identities
labels: [Azure, "Azure Architecture Series"]
---
```

Only `title` and `date` are strictly required — **a file missing either is
silently skipped**, with a note on the console and no error. If a post you wrote
doesn't appear on the site, check those two fields first.

Three rules that are easy to get wrong:

- **Quote the date and include a time.** `date: 2026-08-15` is parsed as
  midnight, so on any day two series publish, the one with a time sorts above
  the one without regardless of which you actually wrote first.
- **Label strings must match exactly**, character for character, across every
  post in a series. Filter pill counts match on the literal string.
- **A new label needs adding to `CATEGORY_ORDER`** in `sync_blog.py`, or the
  series gets no filter pill at all.

### The verification badge

Optional, and deliberately so. Add it only when you personally opened the vendor
docs and checked the figures:

```yaml
verified: '2026-08-15'
verified_claims:
  - claim: "Provisioned is $0.00065 per WCU-hour"
    source: https://aws.amazon.com/dynamodb/pricing/provisioned/
```

The date is when you *checked*, not when you publish. Two claims minimum. If you
skipped the check, leave it out entirely — no badge is correct, a badge nobody
backed is worse than nothing.

---

## Diagrams

**A standalone SVG file, referenced with `<img>`.** Not inline SVG, not mermaid
— nothing on this site renders mermaid, so a mermaid block ships as a raw code
block.

```html
<img src="/blog/assets/diagrams/az-003-managed-identities.svg"
     alt="Diagram: how a managed identity gets a token without a secret">
```

1. Save to `blog/assets/diagrams/`, named to match the post's file prefix.
2. Root element: `viewBox`, `style="width:100%;max-width:860px;"`, `role="img"`,
   `aria-label`. First child a background `<rect fill="#F8F7F5"/>`. No XML
   declaration.
3. Include a `<title>` element — it is the accessible description.

Two failure modes that produce no error message at all:

- **SVG is XML, not HTML.** `&mdash;` and `&rarr;` are undefined entities and
  make the entire file fail to render — blank, silently. Use `&#8212;` and
  `&#8594;`.
- **`<text>` does not wrap.** A long line runs off the canvas and is clipped.
  Break prose into one `<text>` per line yourself. The ceiling is about 120
  characters at the house size.

Check both before publishing:

```bash
python scripts/validate_diagrams.py
```

---

## Publishing, step by step

### A normal post (Lab, Daily, Weekly, personal)

```bash
git pull --rebase
```

Write `posts/<name>.html`. Then:

```bash
python scripts/prepublish.py
python scripts/sync_blog.py
git add posts/ blog/ index.html resume.html now.html sw.js
git commit -m "Post title"
git push origin HEAD:main
```

### An architecture post (arch / az / gcp)

Same, with one extra build step, because sync will not build these pages:

```bash
git pull --rebase
# write posts/az-003-managed-identities.html
python scripts/build_arch_post.py posts/az-003-managed-identities.html
python scripts/prepublish.py --series az
python scripts/sync_blog.py
git add posts/ blog/ index.html resume.html now.html sw.js
git commit -m "Azure Architecture Series #3 — Managed Identities"
git push origin HEAD:main
```

`build_arch_post.py` reads the same template for all three clouds and swaps the
cloud-specific wording based on the filename prefix. `sync_blog.py` still needs
to run afterwards — it won't touch the page, but it adds the post's *card* to
the blog index, the RSS feed and the JSON files.

**Add the root files to that `git add`.** Sync regenerates `sw.js` and
re-stamps the `?v=` token in `index.html`, `resume.html` and `now.html`. Leaving
them out ships a service worker asking for asset URLs no page requests. After
committing, `git status` should be clean — if a root file is still modified, the
`git add` was too narrow.

---

## Which folder am I in?

Four folders, one repository. They are git *worktrees*: separate working
directories sharing one history.

| Folder | Branch | Owns |
| --- | --- | --- |
| `katta698.github.io` | `main` | The site itself — CSS, scripts, workflows |
| `katta698-aws` | `aws` | AWS Architecture, Daily, Weekly, Weekly Lab |
| `katta698-azure` | `azure` | Azure Architecture, Azure Weekly |
| `katta698-gcp` | `gcp` | GCP Architecture, GCP Weekly |

```bash
git worktree list
```

They exist so several posts can be written at once without three sessions
sharing one set of files. Everything publishes to `main` regardless of which
branch you're on — `git push origin HEAD:main` works from all four.

**Two rules, and the second one loses posts:**

1. `git pull --rebase` before you start.
2. **Rebase before running sync, not just before editing.** Each worktree has
   its own `posts/`, so it cannot see a post written in another one until it
   rebases. Run sync from a stale checkout and the rebuilt index, `posts.json`,
   `rss.xml` and `stats.json` all come out *without* that post. Its page
   survives on disk but is unlinked everywhere, and nothing errors.

`sync_blog.py` refuses to run when your checkout is behind `origin/main` for
exactly this reason. `--skip-freshness-check` exists; reaching for it to get
past that message is how you lose someone else's post.

### If two of you publish at once

Conflicts on `blog/index.html`, `posts.json`, `rss.xml`, `stats.json`,
`cards.json` are normal and expected — every publish rewrites all of them.
**Never hand-merge a generated file.** Instead:

```bash
git checkout --theirs blog/index.html      # just to clear the markers
python scripts/sync_blog.py                # regenerate from posts/
git add blog/ posts/
git rebase --continue
```

By that point `posts/` holds both people's work, so the regenerated files are
correct by construction. Check the filter pill counts include both posts before
continuing.

---

## What happens automatically after you push

Nothing here needs you.

| Workflow | Fires when | Does |
| --- | --- | --- |
| GitHub Pages | every push to `main` | serves the site |
| `prepublish.yml` | push touching `posts/` or `blog/` | re-runs the four checks on what changed |
| `on-publish.yml` | push touching `blog/index.html` | waits for the deploy, re-indexes RAG search, updates your profile README |
| `doc-freshness.yml` | weekly, Tuesday | checks every citation still resolves; keeps one tracking issue updated |
| `refresh-aws-services.yml` | weekly | refreshes the AWS service catalogue |

The site is usually live within a minute or two of the push.

---

## When something goes wrong

**My post isn't on the site.**
Missing `title` or `date` in front matter — those are skipped silently. Check
the console output of `sync_blog.py` for a note naming the file.

**I fixed an arch post but the change didn't appear.**
You edited `posts/`. For `arch-`/`az-`/`gcp-` posts the served page is
`blog/<slug>/index.html` and sync never rebuilds it. Edit that file.

**I fixed a normal post but the change didn't appear.**
Opposite mistake — you edited `blog/<slug>/index.html` and sync overwrote it.
Edit `posts/` and re-run sync.

**A corrected excerpt or title won't update on an arch post.**
`posts.json` caches those for pass-through posts. Delete that post's entry from
`blog/posts.json` and re-run sync.

**The whole page is blank where a diagram should be.**
A named entity in the SVG. Search it for `&` — only `&#NNNN;` and the XML five
are legal. `validate_diagrams.py` catches this.

**The last column of a table is cut off on mobile.**
Wrap it in `<div class="table-scroll">`. Not `<div style="overflow-x:auto">` —
sync strips inline `style` attributes from every non-arch post, so that wrapper
silently becomes a bare `<div>` and the table clips anyway.

**A push was rejected as non-fast-forward.**
Someone published first. `git fetch origin && git rebase origin/main`, resolve
generated files with the recipe above, push again.

**CI went red on a post I didn't touch.**
It shouldn't — `prepublish.yml` only checks posts the push actually changed.
If it did, read the failure; reproduce locally with the exact command the
workflow prints at the end of a failed run.

---

## Two rules that are not about tooling

**Never edit `posts/` or `blog/` HTML with PowerShell.** It corrupts the
encoding. Use Python with `open(..., encoding='utf-8')`, or an editor you trust
to write UTF-8.

**Never explain the editorial process inside a post.** No "the news was slow
this week", no notes about the backlog or why this topic and not another. The
reader doesn't have a backlog and didn't ask.
