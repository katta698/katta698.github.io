"""Every occasion banner's "what is this" link must resolve, and be the right article.

Asked for 2026-10-20: the festival greetings should let a reader click
through and find out what the day actually is. A greeting the reader cannot
look up is a nice sentence; a greeting with a dead or wrong link is worse
than no link at all, because it spends their attention and returns nothing.

So this asserts two things per link, not one:

  1. it answers HTTP 200 after redirects, and
  2. the article it lands on is the one meant -- checked against a required
     phrase, because Wikipedia resolves near-misses silently. "Dussehra"
     redirects to "Vijayadashami", which is correct and would look like a
     failure to a strict URL match; "Ugadi" and "Gudi Padwa" are different
     articles and a status check alone cannot tell them apart.

Run it whenever the table changes, and on a schedule -- a link rots quietly
and the banner shows for one day a year, which is the worst possible
combination for noticing by eye.

    python scripts/check_occasion_links.py
    python scripts/check_occasion_links.py --canary
"""
import io
import os
import re
import sys
import json
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "blog", "assets", "occasion-banner.js")

UA = {"User-Agent": "jayanthkatta.com link check (+https://jayanthkatta.com)"}

# What the landing page must contain for the link to count as correct. Kept
# to a phrase the article cannot plausibly lack -- usually its own subject.
EXPECT = {
    # Keyed on the full URL, not the last path segment: two of these are UN
    # observance pages whose slug ("mountain-day") says less than the article
    # it serves, and one ends in a slash and has no segment at all.
    "https://en.wikipedia.org/wiki/New_Year": "New Year",
    "https://en.wikipedia.org/wiki/Republic_Day_(India)": "Republic Day",
    "https://en.wikipedia.org/wiki/Juneteenth": "Juneteenth",
    "https://en.wikipedia.org/wiki/Independence_Day_(United_States)": "Independence Day",
    "https://en.wikipedia.org/wiki/Independence_Day_(India)": "Independence Day",
    "https://en.wikipedia.org/wiki/May_Revolution": "May Revolution",
    "https://en.wikipedia.org/wiki/Argentine_Declaration_of_Independence": "Declaration of Independence",
    "https://en.wikipedia.org/wiki/Hari_Merdeka": "Merdeka",
    "https://en.wikipedia.org/wiki/Malaysia_Day": "Malaysia Day",
    "https://en.wikipedia.org/wiki/Gandhi_Jayanti": "Gandhi Jayanti",
    "https://en.wikipedia.org/wiki/Halloween": "Halloween",
    "https://en.wikipedia.org/wiki/Veterans_Day": "Veterans Day",
    "https://en.wikipedia.org/wiki/International_Day_of_Forests": "Forests",
    "https://en.wikipedia.org/wiki/Earth_Day": "Earth Day",
    "https://en.wikipedia.org/wiki/World_Oceans_Day": "Oceans Day",
    "https://en.wikipedia.org/wiki/F%C3%AAte_de_la_Musique": "Musique",
    # No Wikipedia article exists for either of these two -- every spelling
    # 404s. The UN owns the observance, and the photography day has only its
    # own site. A 404 page still echoes the requested name in <title>, which
    # is why this check reads the BODY and not the title.
    "https://www.un.org/en/observances/end-human-trafficking-day": "Trafficking in Persons",
    "https://www.worldphotographyday.com/": "World Photography Day",
    "https://en.wikipedia.org/wiki/Human_Rights_Day": "Human Rights Day",
    "https://www.un.org/en/observances/mountain-day": "International Mountain Day",
    "https://en.wikipedia.org/wiki/Christmas": "Christmas",
    "https://en.wikipedia.org/wiki/Martin_Luther_King_Jr._Day": "Martin Luther King",
    "https://en.wikipedia.org/wiki/Washington%27s_Birthday": "Washington",
    "https://en.wikipedia.org/wiki/Memorial_Day": "Memorial Day",
    # /wiki/Labor_Day redirects to the INTERNATIONAL Labour Day article. The
    # banner greets the US holiday on the first Monday in September, which is
    # a different day and a different article.
    "https://en.wikipedia.org/wiki/Labor_Day_(United_States)": "Labor Day",
    "https://en.wikipedia.org/wiki/Thanksgiving_(United_States)": "Thanksgiving",
    "https://en.wikipedia.org/wiki/Chinese_New_Year": "Chinese New Year",
    "https://en.wikipedia.org/wiki/Holi": "Holi",
    "https://en.wikipedia.org/wiki/Ugadi": "Ugadi",
    "https://en.wikipedia.org/wiki/Raksha_Bandhan": "Raksha Bandhan",
    "https://en.wikipedia.org/wiki/Krishna_Janmashtami": "Janmashtami",
    "https://en.wikipedia.org/wiki/Ganesh_Chaturthi": "Ganesh",
    "https://en.wikipedia.org/wiki/Vijayadashami": "Vijayadashami",
    "https://en.wikipedia.org/wiki/Diwali": "Diwali",
}


def links_in_source():
    """Pull every `link:` out of the banner tables, with its text."""
    s = io.open(SRC, encoding="utf-8").read()
    out = []
    for m in re.finditer(r"text:\s*'((?:[^'\\]|\\.)*)'[^}]*?link:\s*'([^']+)'",
                         s, re.S):
        out.append((m.group(1), m.group(2)))
    # The LUNAR table puts link on its own line after text; the regex above
    # spans it, but an entry that has text and no link must still be caught.
    texts = re.findall(r"text:\s*'((?:[^'\\]|\\.)*)'", s)
    return out, texts


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.getcode(), r.geturl(), r.read(90000).decode("utf-8", "replace")


def main():
    canary = "--canary" in sys.argv
    pairs, texts = links_in_source()
    print("occasions with text: %d | with link: %d\n" % (len(texts), len(pairs)))

    missing = len(texts) - len(pairs)
    fails = []

    checks = list(pairs)
    if canary:
        checks.append(("CANARY (must fail)",
                       "https://en.wikipedia.org/wiki/Diwali_festival_of_"
                       "lights_that_does_not_exist_zzz"))

    for text, url in checks:
        label = re.sub(r"[^\x20-\x7e]", "", text).strip()[:38]
        try:
            code, final, body = fetch(url)
        except urllib.error.HTTPError as e:
            fails.append((label, url, "HTTP %s" % e.code))
            print("  %-40s HTTP %s" % (label, e.code))
            continue
        except Exception as e:
            fails.append((label, url, type(e).__name__))
            print("  %-40s %s" % (label, type(e).__name__))
            continue
        want = EXPECT.get(url)
        if want is None:
            fails.append((label, url, "no EXPECT entry for this URL"))
            print("  %-40s no EXPECT entry" % label)
            continue
        # Wikipedia puts the article title in <title>…</title>.
        title = re.search(r"<title>(.*?)</title>", body, re.S)
        title = (title.group(1) if title else "")[:90]
        ok = code == 200 and want.lower() in body[:400000].lower()
        print("  %-40s %s  %s" % (label, "ok  " if ok else "WRONG", title))
        if not ok:
            fails.append((label, url, "expected %r in the article" % want))

    if canary:
        bad = [f for f in fails if f[0].startswith("CANARY")]
        other = [f for f in fails if not f[0].startswith("CANARY")]
        if not bad:
            print("\nCANARY FAILED: a nonexistent article passed the check.")
            return 1
        print("\nCanary OK: the nonexistent article was caught (%s)." % bad[0][2])
        return 1 if other else 0

    if missing > 0:
        print("\n%d occasion(s) carry text but no link." % missing)
        fails.append(("<%d occasions>" % missing, "-", "no link"))
    if fails:
        print("\n%d problem(s):" % len(fails))
        for label, url, why in fails:
            print("  %-40s %s\n      %s" % (label, why, url))
        return 1
    print("\nEvery occasion links to an article that exists and is the right one.")
    return 0


if __name__ == "__main__":
    import urllib.parse
    sys.exit(main())
