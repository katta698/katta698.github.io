#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render the walkthrough narration with a neural voice, once, into files.

    python scripts/build_narration_audio.py            # render what changed
    python scripts/build_narration_audio.py --force     # render everything

Why this exists
---------------
Reported, after three attempts at picking a better browser voice: "the
voiceover is not authentic, it's like a machine reading, a robot reading. It's
not natural at all. When I speak to Claude Code I hear a natural conversation.
Why don't you just add something like that?"

Because the browser's speechSynthesis is not that, and no amount of choosing
between its voices makes it that. On a phone it is a 2010-era formant
synthesiser; the code was already preferring Aria and Google US English over
Zira, and it still sounded like a station announcement. The ceiling is the
device, and the device is the wrong place to fix it.

So the narration is rendered ONCE, here, with a neural voice, and shipped as
eight small MP3s. Every visitor then hears the same thing, and it sounds like
a person because it was made by a model that sounds like a person.

edge-tts, deliberately: it uses the same neural voices Microsoft Edge uses for
Read Aloud, it needs no API key and no account, and it costs nothing. The text
of the narration goes to Microsoft to be spoken -- that is worth saying out
loud -- and it is eight sentences about how a static site is built, already
published on the page in writing.

The voice is en-US-AvaNeural: "Expressive, Caring, Pleasant, Friendly" in
Microsoft's own description, and the most natural of the eight American female
voices on offer. Slightly slowed, because a walkthrough explaining a build
pipeline is not a news bulletin.

What comes back besides audio
-----------------------------
SentenceBoundary events, each with an offset and a duration in 100ns units.
Those become the caption cues, so the subtitle on screen is the sentence being
spoken rather than the whole paragraph -- which is the other half of what was
reported: "the whole lines appear in the video".

Long sentences are cut at clause boundaries and their share of the sentence's
duration is apportioned by length. Not perfect timing, but within a word or
two, which is what a caption needs.
"""
import argparse
import asyncio
import hashlib
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

OUT_DIR = os.path.join(ROOT, "blog", "assets", "audio", "walkthrough")
CUES = os.path.join(OUT_DIR, "cues.json")

VOICE = "en-US-AvaNeural"
RATE = "-8%"

# A caption line, not a paragraph. 90 characters is about two lines on a
# 390px frame, which is the most a subtitle should ever be.
MAX_CAP = 90


def cut(text):
    """Break a sentence into caption-sized pieces at clause boundaries."""
    s = text.strip()
    if len(s) <= MAX_CAP:
        return [s]
    parts = re.split(r"(?<=[,;:])\s+|\s+(?=—)", s)
    out, buf = [], ""
    for part in parts:
        cand = (buf + " " + part).strip() if buf else part.strip()
        if len(cand) > MAX_CAP and buf:
            out.append(buf)
            buf = part.strip()
        else:
            buf = cand
    if buf:
        out.append(buf)
    return out or [s]


async def render(text, path):
    """Write one MP3 and return its sentence cues in milliseconds."""
    import edge_tts

    comm = edge_tts.Communicate(text, VOICE, rate=RATE)
    cues = []
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                fh.write(chunk["data"])
            elif chunk["type"] == "SentenceBoundary":
                cues.append({
                    # 100-nanosecond units, which is how the service reports
                    # them. Milliseconds are what an <audio> element speaks.
                    "t": round(chunk["offset"] / 10000),
                    "d": round(chunk["duration"] / 10000),
                    "text": chunk["text"],
                })
    os.replace(tmp, path)
    return cues


def spread(cues):
    """Split long sentences into caption pieces, sharing their duration.

    A sentence of 200 characters shown as one caption is three lines on a
    phone. Cut into pieces, each piece takes the share of the sentence's
    time that its length deserves -- so the words on screen stay roughly
    with the words in the air.
    """
    out = []
    for c in cues:
        pieces = cut(c["text"])
        if len(pieces) == 1:
            out.append({"t": c["t"], "text": pieces[0]})
            continue
        total = sum(len(p) for p in pieces) or 1
        at = c["t"]
        for p in pieces:
            out.append({"t": round(at), "text": p})
            at += c["d"] * (len(p) / total)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    from build_colophon import NARRATION

    os.makedirs(OUT_DIR, exist_ok=True)
    old = {}
    if os.path.exists(CUES):
        try:
            old = json.load(io.open(CUES, encoding="utf-8"))
        except ValueError:
            old = {}

    manifest = {"voice": VOICE, "rate": RATE, "lines": []}
    total = 0
    for i, line in enumerate(NARRATION):
        name = "%02d.mp3" % i
        path = os.path.join(OUT_DIR, name)
        digest = hashlib.sha256(line.encode("utf-8")).hexdigest()[:12]

        prev = None
        for entry in (old.get("lines") or []):
            if entry.get("file") == name:
                prev = entry
                break

        # Re-render only what changed. The words are the input; if they have
        # not moved there is nothing to say differently, and every render is a
        # request to somebody else's service.
        # Reuse needs the RELATIVE cues, which is why they are kept
        # separately -- see the note above `rel` below. A manifest written
        # before that split has no `rel` to reuse, so it re-renders once.
        if (not args.force and prev and prev.get("sha") == digest
                and prev.get("rel") and os.path.exists(path)):
            manifest["lines"].append({k: v for k, v in prev.items()
                                      if k not in ("start", "end", "cues")})
            total += os.path.getsize(path)
            print("  %-8s unchanged" % name)
            continue

        cues = asyncio.run(render(line, path))
        size = os.path.getsize(path)
        total += size
        # `rel` is milliseconds from the start of THIS clip, and it is the
        # only cue time ever stored. The absolute times the player reads are
        # derived from it at join time, every run, from scratch.
        #
        # They used to be the same field, and the caching above handed the
        # previous run's ALREADY-ABSOLUTE times back to be offset a second
        # time. Only the re-rendered lines were right, so the damage grew
        # the further into the track you got: scene 3's captions were cued
        # at 35.3s for a scene that plays 17.5-31.6s, and scene 8's were
        # 99 seconds past the end of the audio. On screen that is a caption
        # that appears once and then never changes again -- which is exactly
        # how it looked, and it survived a full live playthrough because the
        # VOICE was seamless. The words were right; only the subtitles lied.
        manifest["lines"].append({
            "file": name, "sha": digest, "bytes": size,
            "rel": spread(cues),
        })
        print("  %-8s %5dKB  %d cue(s)  %s"
              % (name, size // 1024, len(spread(cues)), line[:42] + "..."))

    # ---- one file, not eight ---------------------------------------------
    #
    # Reported as: "in the middle of the video the music just continues,
    # there's no voice, and maybe after a minute the voice continues."
    #
    # Eight separate clips meant eight separate downloads, each beginning only
    # when its scene did -- so on a phone every scene change was a gap while
    # the next 120KB arrived. And on iOS an <audio> element created AFTER the
    # tap that began playback frequently will not play at all, so some scenes
    # fell through to a silent timer while the music carried on underneath.
    # Both faults sound identical from the outside: the voice stops and the
    # music does not.
    #
    # Joined into one track the narration cannot gap. It is a single element
    # playing continuously, unlocked by the first tap, and the scenes are
    # offsets into it. Seeking is instant and the captions key off the same
    # clock.
    import subprocess

    joined = os.path.join(OUT_DIR, "narration.mp3")
    listing = os.path.join(OUT_DIR, "_join.txt")
    with io.open(listing, "w", encoding="utf-8", newline="\n") as fh:
        for entry in manifest["lines"]:
            fh.write("file '%s'\n" % entry["file"])
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "concat", "-safe", "0", "-i", "_join.txt",
                    "-c:a", "libmp3lame", "-b:a", "64k", "narration.mp3"],
                   cwd=OUT_DIR, check=True)
    os.remove(listing)

    # Where each scene starts in the joined file, measured from the parts
    # rather than assumed: concatenation is not always sample-exact.
    at_ms = 0.0
    for entry in manifest["lines"]:
        dur = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", os.path.join(OUT_DIR, entry["file"])],
            capture_output=True, text=True).stdout.strip()
        length = float(dur or 0) * 1000
        entry["start"] = round(at_ms)
        entry["end"] = round(at_ms + length)
        # Built fresh from `rel` every run, so this can never compound.
        entry["cues"] = [{"t": round(c["t"] + at_ms), "text": c["text"]}
                         for c in entry["rel"]]
        at_ms += length
    manifest["file"] = "narration.mp3"
    manifest["duration"] = round(at_ms)

    # A cue outside the scene it belongs to is a caption that cannot be
    # right, and nothing downstream would notice: the player just shows the
    # last one whose time has passed. Cheap to assert, and it is the exact
    # fault that shipped.
    strays = []
    for i, entry in enumerate(manifest["lines"]):
        for c in entry["cues"]:
            if not (entry["start"] - 250 <= c["t"] <= entry["end"] + 250):
                strays.append("scene %d plays %.1f-%.1fs but a caption is "
                              "cued at %.1fs: %r"
                              % (i + 1, entry["start"] / 1000.0,
                                 entry["end"] / 1000.0, c["t"] / 1000.0,
                                 c["text"][:40]))
    if strays:
        print()
        print("  %d CAPTION(S) CUED OUTSIDE THEIR SCENE" % len(strays))
        print()
        for line in strays[:8]:
            print("  - %s" % line)
        return 1

    tmp = CUES + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, CUES)
    print("  joined -> narration.mp3  %.1fs  %dKB"
          % (at_ms / 1000, os.path.getsize(joined) // 1024))

    print()
    print("  %d line(s), %dKB of audio, voice %s"
          % (len(NARRATION), total // 1024, VOICE))
    longest = max((len(c["text"]) for ln in manifest["lines"]
                   for c in ln["cues"]), default=0)
    print("  longest caption piece: %d characters" % longest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
