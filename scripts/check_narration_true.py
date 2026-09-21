#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The walkthrough says nothing the repository cannot back up.

    python scripts/check_narration_true.py

Why this exists
---------------
The narration said "fifty checks drive a real browser over the real pages".
By the time anyone listened closely there were 58 checks and 34 of them drove
a browser. Nobody had lied: the sentence was true the week it was recorded and
had quietly stopped being true since.

That is the worst place for a stale fact. A wrong number in a page can be
read, questioned and corrected in a minute; a wrong number in a VOICEOVER is
invisible to every tool, survives every rebuild, and is heard by every visitor
in a confident human voice.

Asked for as: "make it standard, so that even when we make changes down the
road we don't have to come here and revisit all the time."

So the script is generated from counted(), and this holds the three ends that
generation alone does not:

    1. THE AUDIO MATCHES THE WORDS. Each line is hashed when it is rendered.
       If the text changed and the audio was not re-rendered, the page shows
       one sentence and speaks another -- and the captions, which come from
       the render, would be the old ones.

    2. THE NUMBERS MATCH THE REPOSITORY. The spoken figures are recomputed
       here from the live repository and must appear in the line. A hand-edit
       that types a number back in is caught.

    3. EVERY NAMED THING EXISTS. The script names a feed, a sitemap, an
       offline worker and four pages. If one is renamed or dropped, the
       narration is describing a site that no longer exists.

None of this is about wording. It is about a recording that claims things,
and whether those claims are still true today.
"""
import hashlib
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

CUES = os.path.join(ROOT, "blog", "assets", "audio", "walkthrough",
                    "cues.json")

# Everything the script names out loud, and where it lives. A claim that
# names a real path is a claim that can be checked; that is the whole reason
# the narration is written this way.
NAMED = [
    ("the feed", os.path.join("blog", "rss.xml")),
    ("the sitemap", "sitemap.xml"),
    ("the offline worker", "sw.js"),
    ("What's New", os.path.join("intelligence", "whats-new", "index.html")),
    ("Live Status", os.path.join("intelligence", "status", "index.html")),
    ("the Intelligence hub", os.path.join("intelligence", "index.html")),
    ("the paged archive", os.path.join("blog", "index.html")),
]


_PAGE_CACHE = {}


def html_of(path):
    if path not in _PAGE_CACHE:
        try:
            _PAGE_CACHE[path] = io.open(path, encoding="utf-8",
                                        errors="replace").read()
        except OSError:
            _PAGE_CACHE[path] = ""
    return _PAGE_CACHE[path]



def main():
    from build_colophon import NARRATION, counted, roughly

    problems = []
    facts = counted()

    # ---- 1. the audio is the words -----------------------------------
    if not os.path.exists(CUES):
        print("  no cues.json -- the narration has never been rendered")
        return 1
    manifest = json.load(io.open(CUES, encoding="utf-8"))
    lines = manifest.get("lines") or []

    if len(lines) != len(NARRATION):
        problems.append(
            "the script has %d lines and the rendered audio has %d. One of "
            "them was changed without the other"
            % (len(NARRATION), len(lines)))
    else:
        stale = []
        for i, text in enumerate(NARRATION):
            want = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
            got = lines[i].get("sha")
            if want != got:
                stale.append(i + 1)
        if stale:
            problems.append(
                "scene(s) %s have been reworded since the audio was made, so "
                "the page reads one sentence and the voice speaks another. "
                "Run: python scripts/build_narration_audio.py"
                % ", ".join(str(n) for n in stale))
        print("  audio matches the script for %d of %d scenes"
              % (len(NARRATION) - len(stale), len(NARRATION)))

    # ---- 2. the numbers are this repository's numbers -----------------
    spoken = " ".join(NARRATION)
    for key, label in (("gate", "checks the gate runs"),
                       ("browser", "checks driving a browser")):
        phrase = roughly(facts[key])
        if phrase.lower() not in spoken.lower():
            problems.append(
                "the script no longer says %r for the %s (measured %d). "
                "Either it was hand-edited or the phrasing changed without "
                "the measurement" % (phrase, label, facts[key]))
        else:
            print("  %-26s %-18s (measured %d)" % (label, phrase, facts[key]))

    # A figure stated exactly is a figure that goes stale. This catches the
    # original fault: a bare number sitting in the spoken text.
    import re
    for i, text in enumerate(NARRATION):
        for m in re.finditer(r"\b(twenty|thirty|forty|fifty|sixty|seventy|"
                             r"eighty|ninety|hundred)\b", text, re.I):
            before = text[max(0, m.start() - 12):m.start()].lower()
            if "more than" not in before:
                problems.append(
                    "scene %d states %r without a band around it. An exact "
                    "figure in a recording is true on the day it is spoken "
                    "and slowly stops being true afterwards"
                    % (i + 1, m.group(0)))

    # ---- 3. everything it names still exists -------------------------
    missing = [(what, rel) for what, rel in NAMED
               if not os.path.exists(os.path.join(ROOT, rel))]
    for what, rel in missing:
        problems.append(
            "the narration names %s, and %s does not exist. The walkthrough "
            "is describing a site that is no longer there" % (what, rel))
    print("  %d of %d named things exist"
          % (len(NAMED) - len(missing), len(NAMED)))

    # ---- 4. and the page agrees with itself ---------------------------
    #
    # The narration and the written stops were both fixed, and the page
    # still said "255 posts" and "50 checks" -- because those figures are
    # <text> labels inside the scene artwork and the architecture diagram,
    # not prose. Then a fourth source turned up in a paragraph and the page
    # carried 58 and 59 checks at the same time.
    #
    # So this stops chasing sources and reads the OUTPUT. Every figure on
    # the built page that sits next to a noun this repository can count has
    # to equal what it counts today. It does not matter how many places
    # produce them or which file they live in.
    page = os.path.join(ROOT, "how-this-was-made", "index.html")
    _bc = __import__("build_colophon")
    NOUNS = {"pages": facts["pages"],
             "jobs": len(_bc.schedules()) or facts["flows"]}

    # "N posts" now means one of five things on this page, because the trip
    # got a tab per route: the whole site, or the size of one of the four
    # routes. Each of the five is measured -- the site total from the built
    # index, the four from blog/cards.json, which is what the filter pills
    # a reader can click are counted from.
    #
    # Listing them rather than dropping the noun is the point. A figure
    # beside "posts" that is none of the five is still a number nobody
    # measured, and that is the only thing this check has ever been for.
    POST_COUNTS = {facts["posts"]}
    for _k, _v in _bc.series_counts().items():
        POST_COUNTS.add(_v["posts"])
    for m in re.finditer(r"(\d[\d,]*)\s+posts\b", html_of(page)):
        got = int(m.group(1).replace(",", ""))
        if got not in POST_COUNTS:
            around = re.sub(r"<[^>]*>", " ",
                            html_of(page)[max(0, m.start() - 40):
                                          m.end() + 20]).strip()
            problems.append(
                "the page says %d posts. The site has %d, and the four "
                "routes have %s -- this is none of them. Near: ...%s..."
                % (got, facts["posts"],
                   ", ".join(str(n) for n in sorted(POST_COUNTS)
                             if n != facts["posts"]), around[:70]))
    if os.path.exists(page):
        html = io.open(page, encoding="utf-8", errors="replace").read()
        seen = 0
        for noun, truth in NOUNS.items():
            for m in re.finditer(r"(\d[\d,]*)\s+" + noun + r"\b", html):
                seen += 1
                got = int(m.group(1).replace(",", ""))
                if got != truth:
                    around = html[max(0, m.start() - 40):m.end() + 20]
                    around = re.sub(r"<[^>]*>", "", around).strip()
                    problems.append(
                        "the page says %d %s and this repository has %d. "
                        "Near: ...%s..." % (got, noun, truth, around[:70]))
        # "checks" is stated two ways -- what the gate runs, and how many of
        # those open a browser -- so any figure beside it must be one of the
        # two rather than a single expected value.
        for m in re.finditer(r"(\d+)\s+checks\b", html):
            seen += 1
            got = int(m.group(1))
            # Three different check counts are all true on this page, and
            # they mean different things: what the GATE runs over the whole
            # site, how many of those drive a browser, how many check
            # scripts exist, and what PREPUBLISH runs over the one post you
            # just wrote. The page names all of them, so all of them are
            # allowed -- and anything else is still a number nobody measured.
            allowed = (facts["gate"], facts["browser"], facts["checks"],
                       facts.get("prepub"))
            if got not in allowed:
                problems.append(
                    "the page says %d checks; the gate runs %d (%d in a "
                    "browser), there are %d check scripts, and prepublish "
                    "runs %d" % (got, facts["gate"], facts["browser"],
                                 facts["checks"], facts.get("prepub") or 0))
        print("  %d figure(s) on the built page checked against the repo"
              % seen)
        if "{{" in html:
            problems.append("the built page still contains an unfilled "
                            "token -- a measurement that never arrived")

    print()
    if problems:
        print("  %d PROBLEM(S)" % len(problems))
        print()
        for p in problems:
            print("  - %s" % p)
        print()
        print("  A wrong number on a page can be read and corrected. A wrong")
        print("  number in a voiceover is invisible to every tool and is")
        print("  still said, confidently, to everybody who presses play.")
        return 1
    print("  The script is generated from what the repository measures, the")
    print("  audio matches it, and everything it names exists.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
