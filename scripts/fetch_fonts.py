#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pull the three typefaces into the repo and write their @font-face rules.

    python scripts/fetch_fonts.py
    python scripts/fetch_fonts.py --check     # verify, download nothing

Why the fonts are in the repo at all
------------------------------------
They used to come from fonts.googleapis.com, and the page could not paint
with them until two round trips had finished: one for the CSS, then one for
each file it named. Until that landed the browser rendered in Georgia,
system-sans and Consolas and then swapped -- and DM Mono is 9.13% wider than
Consolas, so text that fitted two lines in the fallback needed three in the
real font. Measured at 390px: /now.html moved 129px after first paint,
/intelligence/events/ 65px, /resume.html 25px, /intelligence/status/ 18px.

Reported as the page blinking on refresh. The reader named /intelligence/ai/
as the page that does not do it; it does not, because it has no long mono
paragraph to rewrap, which is luck rather than a technique.

Self-hosting removes the swap rather than hiding it: the files are
same-origin, a <link rel=preload> in the head starts them before the
stylesheet that references them, and the service worker can cache them --
cross-origin fonts are never intercepted, so under Google they were outside
the offline story entirely.

Why not the alternatives
------------------------
font-display: optional would also guarantee no reflow, by never swapping
mid-view. It costs the typeface on the first visit, which on this site is the
home page, which is the worst place to pay it.

A metric-matched fallback (size-adjust) keeps the typeface and adds no files,
but one adjustment can only match one fallback font: 109.13% is right against
Consolas on Windows and wrong against the font a phone falls back to, and the
phone is where this was reported.

What is downloaded
------------------
latin and latin-ext only. The site is written in English; cyrillic and
vietnamese would double the file count to serve text that does not exist.
Adding a language means adding its subset here.

DM Sans and Playfair Display are variable fonts, so ONE file covers weights
400 through 700 -- Google returns the same URL for each weight, which is why
the download list is 12 files and not 30.
"""
import argparse
import io
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(ROOT, "blog", "assets", "fonts")
CSS_OUT = os.path.join(ROOT, "blog", "assets", "fonts.css")

# A real desktop UA, because the API serves woff2 only to browsers it
# recognises; with urllib's default it answers with ancient TrueType.
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# The superset of what the two different Google URLs on this site asked for:
# blog.css's @import wanted DM Sans italic, the generators' <link> did not.
# Fetching the union means one set of files satisfies both.
SRC = ("https://fonts.googleapis.com/css2"
       "?family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400"
       "&family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;"
       "0,9..40,700;1,9..40,400"
       "&family=DM+Mono:wght@400;500"
       "&display=swap")

KEEP = ("latin", "latin-ext")

SHORT = {"DM Sans": "dm-sans", "DM Mono": "dm-mono",
         "Playfair Display": "playfair"}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=60).read()


def faces():
    """Every @font-face Google would serve, parsed, latin subsets only."""
    css = get(SRC).decode("utf-8")
    out = []
    for subset, body in re.findall(
            r"/\*\s*([a-z0-9\[\]-]+)\s*\*/\s*@font-face\s*\{(.*?)\}",
            css, re.S):
        if subset not in KEEP:
            continue
        fam = re.search(r"font-family:\s*'([^']+)'", body).group(1)
        style = re.search(r"font-style:\s*(\w+)", body).group(1)
        weight = re.search(r"font-weight:\s*([^;]+);", body).group(1).strip()
        rng = re.search(r"unicode-range:\s*([^;]+);", body).group(1).strip()
        url = re.search(r"url\((https[^)]+)\)", body).group(1)
        out.append({"family": fam, "style": style, "weight": weight,
                    "subset": subset, "range": rng, "url": url})
    return out


def name_by_url(fs):
    """One name per FILE, not per face, keyed on the URL.

    DM Sans and Playfair Display are variable: Google returns the same URL for
    weight 400, 500, 600 and 700. Naming each face independently produced
    rules pointing at dm-sans-500-latin.woff2 and nine more like it -- files
    that were never written, because their URL had already been fetched under
    a different name. The stylesheet looked entirely correct and ten of its
    twenty-two rules 404ed.

    So group by URL first. A file shared across weights does not carry one in
    its name; a file backing exactly one weight does.
    """
    weights = {}
    for f in fs:
        weights.setdefault(f["url"], set()).add(f["weight"])
    out = {}
    for f in fs:
        if f["url"] in out:
            continue
        bits = [SHORT[f["family"]]]
        if len(weights[f["url"]]) == 1 and " " not in f["weight"]:
            bits.append(f["weight"])
        if f["style"] != "normal":
            bits.append(f["style"])
        bits.append(f["subset"])
        out[f["url"]] = "-".join(bits) + ".woff2"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report what is missing, download nothing")
    args = ap.parse_args()

    fs = faces()
    if not fs:
        print("  no faces parsed -- the API response shape changed")
        return 1

    # One URL can back several faces (a variable file serves every weight),
    # so download by URL and write a rule per face.
    by_url = name_by_url(fs)

    if not args.check:
        if not os.path.isdir(FONT_DIR):
            os.makedirs(FONT_DIR)

    total, missing = 0, 0
    for url, name in sorted(by_url.items(), key=lambda kv: kv[1]):
        path = os.path.join(FONT_DIR, name)
        if os.path.exists(path):
            total += os.path.getsize(path)
            continue
        missing += 1
        if args.check:
            print("  MISSING  %s" % name)
            continue
        blob = get(url)
        with io.open(path, "wb") as fh:
            fh.write(blob)
        total += len(blob)
        print("  %-34s %6.1f KB" % (name, len(blob) / 1024.0))

    if args.check and missing:
        print("\n  %d file(s) missing -- run without --check" % missing)
        return 1

    rules = ["""/* Generated by scripts/fetch_fonts.py -- do not edit by hand.
   Self-hosted so the files are same-origin: a <link rel=preload> in the head
   can start them before this stylesheet is even parsed, the service worker
   can cache them, and the swap that used to rewrap text after first paint
   does not happen.

   font-display:optional rather than swap, inherited from the two faces
   site-footer.css used to override: swap means "draw it twice", and the
   second draw IS the flicker. optional says use it if it is ready and
   otherwise never swap, so the text is drawn once whatever happens -- and
   with a preloaded same-origin file it is ready.

   See fetch_fonts.py's docstring for the measurements. */"""]
    for f in sorted(fs, key=lambda f: (f["family"], f["style"], f["subset"])):
        rules.append(
            "@font-face{font-family:'%s';font-style:%s;font-weight:%s;"
            "font-display:optional;src:url('/blog/assets/fonts/%s') "
            "format('woff2');unicode-range:%s}"
            % (f["family"], f["style"], f["weight"], by_url[f["url"]],
               f["range"]))
    with io.open(CSS_OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(rules) + "\n")

    bad = sorted({n for n in by_url.values()
                  if not os.path.exists(os.path.join(FONT_DIR, n))})
    if bad:
        print("\n  %d rule(s) name a file that is not here: %s"
              % (len(bad), ", ".join(bad)))
        return 1

    print("\n  %d face rule(s) over %d file(s), %.1f KB total"
          % (len(fs), len(by_url), total / 1024.0))
    print("  -> blog/assets/fonts.css")
    return 0


if __name__ == "__main__":
    sys.exit(main())
