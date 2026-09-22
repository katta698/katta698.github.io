# Sketch demo — Ink & Pipeline

**Concept name:** Ink & Pipeline  
**Demo file:** `how-this-was-made/sketch-demo.html` (local / review only — not linked from production)  
**Production:** `how-this-was-made/index.html` — **do not treat this demo as a drop-in replace without the notes below.**

## Pitch (5 bullets)

- One continuous warm-paper sketch strip that *draws itself* as the existing walkthrough narration plays — Kurzgesagt clarity with a YouTube-whiteboard hand.
- Camera gently pans/zooms between eight storyboard panels instead of hard SVG scene swaps; completed nodes stay inked, the active node pulses.
- Same audio + cue timings as live (`data-cues` / `narration.mp3`); chapter chips, scrubber notches, CC, mute, replay, filmstrip, and a scrolling transcript.
- Real script names on the page (`prepublish.py`, `sync_blog.py`, `preflight.py`, ask-the-archive) so the story matches the repo.
- Dark site chrome with a warm paper stage — readable in the site’s dark theme without fighting tokens.

## Suggested page-level changes if this ships

**Keep**

- The walkthrough player (audio, cues, chapter list, CC/mute/replay) — this demo already reuses that contract.
- The “why static / why this way” closing copy and the public GitHub link.
- Scheduled-jobs table as a *detail* appendix for people who want the clock list.

**Cut or demote**

- The large static architecture SVG as the *primary* visual — replace (or lead) with the ink strip / filmstrip. Keep a simplified static diagram as a fallback / print / reduced-motion alternative.
- Duplicate narration of the same eight beats in long prose immediately under the player; let the sketch + captions carry the story first.

**Reorder**

1. Short lede + sketch player (this demo’s stage).  
2. Filmstrip / chapter jump (already in-player).  
3. Optional “open the full diagram” disclosure for the current big SVG + trip tabs.  
4. “How it stays current” jobs table.  
5. Preflight / ask-the-archive short notes (or fold into chapters 4 and 7 only).  
6. Why it’s built this way + repo link.

Trip tabs can stay as an advanced “three paths into the same last five stops” appendix rather than competing with the linear storyboard.

## What still needs real art / narration rewrite later

- Hand-ink assets (or a tighter SVG library) drawn by a human — current panels are schematic path sketches, not final art.
- Per-cue micro-animations (checklist ticks timed to each sentence; fan-out arrows that appear on the “index / archive / feed” lines, not only on chapter start).
- Optional light-theme paper invert (light ink on dark) if the site’s light mode should match.
- Narration rewrite only if product wants shorter chapters or new beats (audio/cues are intentionally identical to production today).
- Reduced-motion: pre-inked panels + crossfade only (partially gated via CSS; needs a full pass).
- Mobile layout polish for the filmstrip and caption type size on narrow phones.
- iOS autoplay / gesture: already uses one `narration.mp3` like production; still verify on device before shipping.
- Accessibility pass: focus order, live region for captions, filmstrip keyboard roving tabindex.

## Local preview

Serve from the repo root (not the `how-this-was-made/` folder) so `/blog/assets/audio/walkthrough/…` resolves:

```text
http://127.0.0.1:8765/how-this-was-made/sketch-demo.html
```
