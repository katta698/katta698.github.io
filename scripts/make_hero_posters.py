#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One still per hero clip, so the hero is never an empty rectangle.

    python scripts/make_hero_posters.py          # only what is missing
    python scripts/make_hero_posters.py --force  # rebuild every one

Why this exists
---------------
The hero <video> ships with no src and no poster; hero-media.js picks the clip
from the date and assigns it. Until the video had data the hero was a flat
#1D2322 block -- 414px tall on the blog, 890px on the portfolio -- and then the
clip appeared over it. That is what "the blog and the portfolio refresh, but
Intelligence and What's New and Live status are seamless" was describing:
those three have no hero video, so nothing about them arrives late.

A poster is the video's own first frame, about 20KB against 1.4MB of mp4. It
paints almost immediately, so the clip fades in over a picture of itself
instead of over a dark rectangle.

Generated rather than hand-made, and named from the clip, so a new video cannot
end up showing a still from a different one. Run this after adding clips; it
skips any poster that already exists unless --force.
"""
import argparse
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEOS = os.path.join(ROOT, "blog", "assets", "videos")
POSTERS = os.path.join(VIDEOS, "posters")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if not os.path.isdir(VIDEOS):
        print("  no videos directory at %s" % VIDEOS)
        return 1
    os.makedirs(POSTERS, exist_ok=True)

    clips = sorted(f for f in os.listdir(VIDEOS) if f.endswith(".mp4"))
    made, skipped, failed = 0, 0, []
    for clip in clips:
        out = os.path.join(POSTERS, clip[:-4] + ".webp")
        if os.path.exists(out) and not args.force:
            skipped += 1
            continue
        cmd = ["ffmpeg", "-loglevel", "error", "-y",
               "-i", os.path.join(VIDEOS, clip),
               "-frames:v", "1", "-vf", "scale=1280:-2",
               "-quality", "60", out]
        try:
            subprocess.run(cmd, check=True, timeout=120)
            made += 1
        except Exception as exc:                               # noqa: BLE001
            failed.append("%s (%s)" % (clip, str(exc)[:50]))

    total = sum(os.path.getsize(os.path.join(POSTERS, f))
                for f in os.listdir(POSTERS) if f.endswith(".webp"))
    print("  %d clip(s): %d poster(s) made, %d already there"
          % (len(clips), made, skipped))
    print("  %d poster(s) on disk, %.1f MB total"
          % (len(os.listdir(POSTERS)), total / 1048576.0))

    # A clip with no poster falls back to a dark rectangle, silently.
    missing = [c for c in clips
               if not os.path.exists(os.path.join(POSTERS, c[:-4] + ".webp"))]
    if missing or failed:
        print()
        for f in failed:
            print("  FAILED %s" % f)
        for m in missing:
            print("  MISSING poster for %s" % m)
        print("\n  A clip without a poster still shows an empty hero on the")
        print("  day it comes up, and nothing will report it.")
        return 1
    print("  Every clip has one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
