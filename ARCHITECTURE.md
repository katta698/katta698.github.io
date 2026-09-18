# How this site is built

One page, so that "which file do I change?" and "what else does that touch?"
have an answer that is not a search.

Read the arrows as **"is built from"**. Anything downstream of an arrow is
generated: editing it works until the next build, and then it is gone.
(CHECKLIST.md, rule 4.)

---

## 1. The whole thing, at a distance

```
   SOURCES              BUILDERS                PUBLISHED             SHELL
   (you edit)           (scripts/*.py)          (never edit)          (shared)

   posts/*.html  ─────► sync_blog.py     ─────► blog/<slug>/       ┐
   257 post bodies      build_arch_post.py      blog/index.html    │
                                                blog/page/2..11/   │
                                                blog/*.json        │
                                                blog/rss.xml       │
                                                                   │
   intelligence/  ┌───► build_news_page   ───►  intelligence/      │
   news.json      │                             whats-new/         ├──► site-footer.css
   status.json    ├───► build_status_page  ──►  intelligence/      │    site-footer.js
   postmortems    │     build_status_feed       status/ + feeds    │    blog.css
   events.json    └───► build_events_page  ──►  intelligence/      │    hero-media.js
                                                events/            │    feedback.js
                                                                   │
   index.html          (hand-written, no builder)                  │
   resume.html         portfolio / CV / now                        ┘
   now.html                                          │
                                                     ▼
                             build_sitemap.py ──► sitemap.xml, robots.txt
                             sync_blog.py     ──► sw.js  (from scripts/sw.template.js)
                             asset_version.py ──► the ?v= token on every asset URL
```

Five pages carry the bar: **portfolio** (`/`), **blog** (`/blog/`),
**Intelligence** (`/intelligence/`), **What's New**, **Live status**.
`/intelligence/events/` is the sixth page and is reached from the hub, not
the bar. 278 pages include the shared shell.

---

## 2. Sources of truth — the only files you hand-edit

| File | Holds | Built into |
|---|---|---|
| `posts/*.html` (257) | every post body | all of `blog/` |
| `intelligence/news.json` | cloud announcements | What's New |
| `intelligence/status.json` + `status-history.json` | live incidents | Live status + Atom feeds |
| `intelligence/postmortems.json` | vendor post-mortems | Live status |
| `intelligence/events.json` (38) | cloud events calendar | `/intelligence/events/` |
| `index.html`, `resume.html`, `now.html` | portfolio, CV, now | nothing — they ARE the page |
| `intelligence/index.html` | the hub | nothing |
| `blog/assets/*.css`, `*.js` | the shared shell | every page at once |

Everything else under `blog/` and `intelligence/*/` is output.

---

## 3. Where the data comes in

Nothing is typed twice. Each store has one fetcher, on a cron.

```
   AWS/Azure/GCP RSS + APIs ──► news_store.py ingest ──► news.json ──► What's New
                                news_tag.py apply

   vendor status pages     ──► fetch_status.py      ──► status.json ──┐
   vendor post-mortems     ──► fetch_postmortems.py ──► postmortems ──┤
                                                                      ├► Live status
                                alert_new_incidents.py ──► GitHub issue┘

   aws.amazon.com/api/dirs ──► import_aws_events.py  ──┐
   aitour.microsoft.com    ──► import_aitour.py       ─┼► events.json ──► Events
   vendor announcement pgs ──► watch_event_dates.py   ─┘

   AWS/Azure/GCP regions   ──► fetch_regions.py      ──► the world map
   AWS service catalogue   ──► refresh_aws_services.py ──► aws_services.json
```

---

## 4. The shared shell — one file, every page

This is where a change is cheapest and also where it is most dangerous:
`site-footer.css` is on 278 pages.

```
   blog/assets/site-footer.css   the bar, the nav, the theme tokens,
                                 the music glyph, pull-to-refresh, the
                                 subscribe sheet
   blog/assets/site-footer.js    theme switch, music that survives a page
                                 change, pull-to-refresh, the menu
   blog/assets/blog.js           the blog index: cards, filters, pills,
                                 search, sort
   blog/assets/hero-media.js     the hero video and #beach-audio
   blog/assets/feedback.js       the feedback star
   sw.js  ◄── scripts/sw.template.js
                                 navigations network-first, css/js
                                 stale-while-revalidate, images cache-first
```

Two theme conventions live side by side and this trips people up:
the Intelligence family uses `--bg/--tx/--mut/--bd` with `body.light`;
the blog uses `--surface/--text/--text-muted/--border` with `body.dark`.

---

## 5. The gates — what runs before anything ships

```
   git push
      │
      ▼
   scripts/preflight.py   (the pre-push hook)
      │  prints CHECKLIST.md, then runs 21 checks in parallel
      │
      ├── check_reader_facing    conflict markers, broken ink, dead text
      ├── check_nav / check_bar_settle / check_brand   the bar cannot move
      ├── check_blog_filters     one year at a time, and the whole archive
      ├── check_music            the clock must actually move
      ├── check_events           vendor domains only, live links
      ├── check_events_coverage  is anything MISSING (a different question)
      ├── check_sw_strategy      the cache rules still say what they said
      └── ... 13 more
      │
      ▼
   scripts/gold.py snapshot   before a change
   scripts/gold.py compare    after  ─► "of 1100 files (965 text, 135
                                         binary) and 405,803 lines, only
                                         X changed, and N pages behave
                                         differently"
```

`publish.py` is the one command for a post: `prepublish.py` → `sync_blog.py`
→ re-check → repeat until it converges.

---

## 6. What runs on its own

| Workflow | When | Does |
|---|---|---|
| `status.yml` | hourly | fetch status, rebuild Live status + feeds, open an issue on a new incident |
| `ingest-news.yml` | 05:10 UTC daily | ingest announcements, tag, rebuild What's New |
| `refresh-events.yml` | 05:40 UTC daily | re-import AWS + AI Tour events, watch for announced dates |
| `verify-events.yml` | 06:20 UTC daily | deep-render every event link, reconcile against the vendors |
| `health.yml` | 13:00 UTC daily | health-report.md |
| `refresh-aws-services.yml` | Mondays 06:00 | refresh the service catalogue |
| `doc-freshness.yml` | Tuesdays 07:00 | flag stale docs |
| `prepublish.yml`, `validate-post.yml`, `on-publish.yml` | on push / PR | gate posts, notify subscribers |

---

## 7. The counts, so a number in a commit message means something

```
   60,062   lines of code      36,290 Python · 8,843 hand-written HTML
                               7,013 JS · 6,282 CSS · 1,634 workflows
   78,240   lines of writing   255 post sources
  282,030   lines generated    ~300 built blog pages + the data stores
      135   binary files       images, fonts, audio, video — hashed by
                               gold.py, counted as 0 lines
```

`gold.py` is the only thing that should be quoted for "what changed".
