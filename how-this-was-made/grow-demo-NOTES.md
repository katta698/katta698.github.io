# Grow demo — One file grows the site

**Concept name:** One file grows the site  
**Demo file:** `how-this-was-made/grow-demo.html` (local / review only — not linked from production)  
**Production:** `how-this-was-made/index.html` — **untouched**. `sketch-demo.html` left alone.

## Pitch (5 bullets)

- One full-bleed warm-paper stage that *grows* as the existing walkthrough narration plays — Kurzgesagt / whiteboard energy, not a filmstrip of eight tiny panels.
- Scene changes are morph/crossfade inside the same frame; the camera gently zooms out (ch0→ch7) as the system expands.
- Same audio + absolute cue timings as live (`cues.json` / production `data-cues` → `narration.mp3`); YouTube-style caption bar, chapter progress path, scrub / mute / CC / replay, collapsed transcript on phone.
- Real script names on the drawing (`prepublish.py`, `sync_blog.py` / `publish.py`, `preflight.py`) so the story matches the repo.
- Idle open lands on **Write** (chapter 1) so a 390px phone, without pressing play, already reads “one file → whole site.”

## What would change on the page if this shipped

**Keep**

- The walkthrough player contract (audio, cues, chapter list, CC/mute/replay).
- Closing “why static” copy and the public GitHub link.
- Scheduled-jobs table as a detail appendix.

**Cut or demote**

- Leading with the large static architecture SVG — lead with this growing stage instead; keep a simplified static diagram as reduced-motion / print fallback.
- Long prose that retells the same eight beats immediately under the player.

**Reorder (suggested)**

1. Short lede + grow player (this demo).  
2. Chapter progress path (in-player).  
3. Optional disclosure for the current big SVG / trip tabs.  
4. Jobs table.  
5. Why it’s built this way + repo link.

## Local preview

Serve from the **repo root** so `/blog/assets/audio/walkthrough/…` resolves:

```text
http://127.0.0.1:8765/how-this-was-made/grow-demo.html
http://100.84.220.76:8765/how-this-was-made/grow-demo.html
```

## Chapter → visual mapping

| # | Chip | Audio window (ms) | Visual |
|---|------|-------------------|--------|
| 0 | Idea | 0–9168 | Empty desk / spark; “no CMS / no server” |
| 1 | Write | 9168–17544 | Bold postcard `posts/arch-….html` |
| 2 | Check | 17544–31584 | `prepublish.py` ticks; dead-link X then cleared |
| 3 | Build | 31584–52608 | Branches → index / archive / feed / sitemap (`sync_blog.py` · `publish.py`) |
| 4 | Preflight | 52608–76512 | Browser-check ring + `preflight.py` |
| 5 | Live | 76512–88200 | Tree lifts into GitHub Pages cloud |
| 6 | Clock | 88200–108960 | Orbiting job clocks → What’s New / Status / Events |
| 7 | Ask | 108960–123456 | Terminal asks; answer cites post or unknown |

## Still open if productized

- Human-inked SVG polish; per-cue micro-motion beyond chapter gates.
- Full reduced-motion pass; light-theme paper invert.
- Focus / live-region a11y pass before linking from production.
