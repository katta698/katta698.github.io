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
        if (not args.force and prev and prev.get("sha") == digest
                and os.path.exists(path)):
            manifest["lines"].append(prev)
            total += os.path.getsize(path)
            print("  %-8s unchanged" % name)
            continue

        cues = asyncio.run(render(line, path))
        size = os.path.getsize(path)
        total += size
        manifest["lines"].append({
            "file": name, "sha": digest, "bytes": size,
            "cues": spread(cues),
        })
        print("  %-8s %5dKB  %d cue(s)  %s"
              % (name, size // 1024, len(spread(cues)), line[:42] + "..."))

    tmp = CUES + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, CUES)

    print()
    print("  %d line(s), %dKB of audio, voice %s"
          % (len(NARRATION), total // 1024, VOICE))
    longest = max((len(c["text"]) for ln in manifest["lines"]
                   for c in ln["cues"]), default=0)
    print("  longest caption piece: %d characters" % longest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
