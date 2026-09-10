#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One dated report on whether this site can be trusted this morning.

    python scripts/health_report.py                   # human-readable
    python scripts/health_report.py --markdown out.md # for the daily issue
    python scripts/health_report.py --no-network      # skip the vendor probes

Why this exists
---------------
The site's whole argument is that its numbers can be checked. That argument
only holds if somebody actually checks them, and twenty-five separate scripts
each answering one narrow question is not the same as knowing whether the site
is sound this morning.

The failure this is written against is not a crash. It is a page that renders
perfectly while saying something untrue: a count that no longer matches the
file behind it, a source that stopped refreshing three days ago, a scheduled
job that has been failing quietly since Tuesday. Every one of those looks
completely fine on screen, and every one of them is the kind of thing a
reader's manager notices first.

So it asks, in order:

  what does each page CLAIM, and does the data behind it agree
  is each source as fresh as its OWN schedule says it should be
  do two files that state the same fact still state the same fact
  did every scheduled job run, and did it pass
  are the vendor endpoints the site cites still answering
  is there anything on a reader's screen that should not be there

and prints one verdict. It reports; it never blocks. A typo, or a slow morning
at Amazon, should not stop this site from publishing.
"""
import argparse
import datetime as dt
import io
import json
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOW = dt.datetime.now(dt.timezone.utc)

OK, WARN, FAIL = "ok", "warn", "fail"
findings = []          # (section, level, message)


def note(section, level, message):
    findings.append((section, level, message))


def load(path):
    try:
        return json.load(io.open(os.path.join(ROOT, path), encoding="utf-8"))
    except Exception as exc:                                    # noqa: BLE001
        note("claims", FAIL, "cannot read %s (%s)" % (path, str(exc)[:60]))
        return None


def text(path):
    try:
        return io.open(os.path.join(ROOT, path), encoding="utf-8").read()
    except Exception:                                           # noqa: BLE001
        return ""


def age_hours(stamp):
    """Hours since an ISO timestamp, or None if it cannot be read."""
    if not stamp:
        return None
    s = str(stamp).replace("Z", "+00:00")
    try:
        t = dt.datetime.fromisoformat(s)
    except ValueError:
        try:
            t = dt.datetime.strptime(str(stamp)[:10], "%Y-%m-%d").replace(
                tzinfo=dt.timezone.utc)
        except ValueError:
            return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return (NOW - t).total_seconds() / 3600.0


def commas(n):
    try:
        return format(int(n), ",")
    except Exception:                                           # noqa: BLE001
        return str(n)


# ---------------------------------------------------------------------------
# 1. What the pages claim, against the data behind them.
#
# This is the section someone's manager would catch. A page saying "1,318
# announcements" when the file holds 1,290 is not a rendering bug -- it is the
# site being wrong in public, and nothing else in this repo would notice.
# ---------------------------------------------------------------------------
def claims():
    news = load("intelligence/news.json") or {}
    timeline = load("intelligence/timeline-index.json") or {}
    regions = load("intelligence/status/regions.json") or {}
    cards = load("blog/cards.json") or []
    stats = load("blog/stats.json") or {}

    checks = []

    m = re.search(r'id="news-count"[^>]*data-n="(\d+)"',
                  text("intelligence/whats-new/index.html"))
    checks.append(("What's New announcement count",
                   int(m.group(1)) if m else None,
                   len(news.get("items") or [])))

    st = text("intelligence/status/index.html")
    m = re.search(r'All years <span class="pm-yn">([\d,]+)</span>', st)
    checks.append(("Live status incident archive",
                   int(m.group(1).replace(",", "")) if m else None,
                   len(timeline.get("incidents") or [])))

    # The map builds its regions client-side, so the page states no number for
    # this check to verify -- an earlier version of it matched the "1" out of
    # an unrelated sentence and reported the site as wrong. What matters
    # instead is that the LIST is whole: a cloud dropping to nothing is what a
    # bad fetch looks like, and the map would just draw fewer dots without
    # saying anything was missing.
    per_cloud = {}
    for r in (regions.get("regions") or []):
        c = r.get("cloud", "?")
        per_cloud[c] = per_cloud.get(c, 0) + 1
    if not per_cloud:
        note("claims", FAIL, "the region list is empty — the map would draw nothing")
    else:
        summary = ", ".join("%s %d" % (c, n) for c, n in sorted(per_cloud.items()))
        thin = [c for c, n in per_cloud.items() if n < 10]
        if thin:
            note("claims", FAIL,
                 "a cloud has almost no regions (%s) — check %s" % (summary, thin))
        else:
            note("claims", OK, "regions on the map: %s — %d in total"
                 % (summary, sum(per_cloud.values())))

    bl = text("blog/index.html")
    m = re.search(r'>([\d,]{2,6})<[^<]*</span>\s*<span[^>]*>\s*POSTS', bl, re.I)
    if not m:
        m = re.search(r'([\d,]{2,6})\s+posts\b', bl, re.I)
    checks.append(("Blog post count",
                   int(m.group(1).replace(",", "")) if m else None,
                   len(cards)))

    if stats.get("total_posts") is not None:
        checks.append(("stats.json total_posts against cards.json",
                       stats.get("total_posts"), len(cards)))

    for label, shown, actual in checks:
        if shown is None:
            note("claims", WARN,
                 "%s: could not find the number on the page — this check may "
                 "need updating after a redesign" % label)
        elif int(shown) != int(actual):
            note("claims", FAIL, "%s: the page says %s, the data holds %s"
                 % (label, commas(shown), commas(actual)))
        else:
            note("claims", OK, "%s: %s, matches" % (label, commas(actual)))


# ---------------------------------------------------------------------------
# 2. Freshness, judged against each source's OWN schedule.
#
# A daily source at eleven hours old is on time. Judging everything by one
# threshold is how a healthy site gets reported as broken -- which is what the
# sources table does today, showing five sources "just now" and one at "11
# hours ago" with nothing to say the sixth is only fetched daily.
# ---------------------------------------------------------------------------
EXPECTED = [
    # path,                              field,       cadence,  allowed hours
    ("intelligence/status.json",         "checked",   "hourly",        3),
    ("intelligence/timeline-index.json", "updated",   "hourly",        6),
    ("intelligence/status/regions.json", "updated",   "daily",        36),
    ("intelligence/news.json",           "generated", "daily",        36),
]


def freshness():
    for path, field, cadence, allowed in EXPECTED:
        d = load(path)
        if not d:
            continue
        h = age_hours(d.get(field))
        if h is None:
            note("freshness", WARN, "%s has no usable '%s' timestamp"
                 % (path, field))
        elif h > allowed:
            note("freshness", FAIL,
                 "%s is %.1fh old — %s, so it should be under %dh"
                 % (path, h, cadence, allowed))
        else:
            note("freshness", OK, "%s is %.1fh old (%s, limit %dh)"
                 % (path, h, cadence, allowed))

    st = load("intelligence/status.json") or {}
    for key, src in sorted((st.get("sources") or {}).items()):
        if src.get("ok") is False:
            note("freshness", FAIL, "the %s source last returned HTTP %s"
                 % (key, src.get("http")))


# ---------------------------------------------------------------------------
# 3. Two files that state the same fact must still agree.
#
# status.json carried history_count 904 while timeline-index.json held 922.
# The page happened to render the right one, so no reader saw it -- until the
# day something renders the other.
# ---------------------------------------------------------------------------
def agreement():
    st = load("intelligence/status.json") or {}
    tl = load("intelligence/timeline-index.json") or {}
    a, b = st.get("history_count"), len(tl.get("incidents") or [])
    if a is None or not b:
        note("agreement", WARN, "cannot compare the two incident counts")
    elif int(a) != int(b):
        note("agreement", WARN,
             "status.json says %s incidents in history, timeline-index.json "
             "says %s — different jobs write them and they have drifted"
             % (commas(a), commas(b)))
    else:
        note("agreement", OK, "both incident counts agree at %s" % commas(b))

    regions = load("intelligence/status/regions.json") or {}
    stale = regions.get("stale")
    if stale:
        note("agreement", WARN, "a region list is marked stale: %s" % stale)
    else:
        note("agreement", OK, "no cloud's region list is marked stale")


# ---------------------------------------------------------------------------
# 4. Did the scheduled jobs run, and did they pass.
#
# A workflow failing since Tuesday looks like nothing at all from the site.
# Two were failing when this was written, and neither had been noticed.
# ---------------------------------------------------------------------------
def jobs():
    try:
        out = subprocess.run(
            ["gh", "run", "list", "--limit", "60", "--json",
             "name,conclusion,createdAt,status"],
            capture_output=True, text=True, cwd=ROOT, timeout=90,
            # gh prints UTF-8; Windows would otherwise decode it as cp1252 and
            # turn every em dash in a workflow name into mojibake.
            encoding="utf-8", errors="replace")
        runs = json.loads(out.stdout or "[]")
    except Exception as exc:                                    # noqa: BLE001
        note("jobs", WARN, "cannot read the workflow history (%s)"
             % str(exc)[:50])
        return
    if not runs:
        note("jobs", WARN, "no workflow runs were returned")
        return

    latest = {}
    for r in runs:
        name = r.get("name") or "?"
        h = age_hours(r.get("createdAt"))
        if h is None:
            continue
        if name not in latest or h < latest[name][0]:
            latest[name] = (h, r.get("conclusion") or r.get("status"))

    for name, (h, verdict) in sorted(latest.items()):
        if verdict in ("failure", "timed_out"):
            note("jobs", FAIL, "%s — last run %.1fh ago: %s"
                 % (name[:44], h, verdict))
        elif verdict == "cancelled":
            note("jobs", WARN, "%s — last run %.1fh ago: cancelled"
                 % (name[:44], h))
        else:
            note("jobs", OK, "%s — ran %.1fh ago: %s" % (name[:44], h, verdict))


# ---------------------------------------------------------------------------
# 5. Are the vendor endpoints the site cites still answering.
# ---------------------------------------------------------------------------
def vendors(enabled):
    if not enabled:
        note("vendors", WARN, "skipped, --no-network was passed")
        return
    import urllib.request
    st = load("intelligence/status.json") or {}
    for key, src in sorted((st.get("sources") or {}).items()):
        url = src.get("url")
        if not url:
            continue
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "jayanthkatta.com health check"})
            with urllib.request.urlopen(req, timeout=25) as r:
                code = r.status
            if code == 200:
                note("vendors", OK, "%s answered 200" % key)
            else:
                note("vendors", WARN, "%s answered HTTP %s" % (key, code))
        except Exception as exc:                                # noqa: BLE001
            note("vendors", FAIL, "%s did not answer: %s" % (key, str(exc)[:60]))


# ---------------------------------------------------------------------------
# 6. Do our regions still match what the vendors themselves publish.
#
# This is the objection the site is most exposed to: "your data centres do not
# match Google's page". It is answered by asking Google. The same three
# fetchers the site is built from are re-run and compared against what shipped,
# so the check reads the vendors' own lists rather than a copy of them.
#
# It reports in both directions, and the second one matters more: a region we
# list that the vendor has dropped is embarrassing, but a region the vendor has
# LAUNCHED and we do not show is the site quietly going out of date.
# ---------------------------------------------------------------------------
def vendor_regions(enabled):
    if not enabled:
        note("regions", WARN, "skipped, --no-network was passed")
        return
    ours = load("intelligence/status/regions.json") or {}
    mine = {}
    for r in (ours.get("regions") or []):
        mine.setdefault(r.get("cloud"), {})[r.get("code")] = r

    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    try:
        import fetch_regions as fr
    except Exception as exc:                                    # noqa: BLE001
        note("regions", WARN, "cannot load the vendor fetchers (%s)"
             % str(exc)[:50])
        return

    for cloud, fn in (("aws", "fetch_aws"), ("gcp", "fetch_gcp"),
                      ("azure", "fetch_azure")):
        try:
            live = getattr(fr, fn)()
        except Exception as exc:                                # noqa: BLE001
            note("regions", WARN, "%s: could not read the vendor's list (%s)"
                 % (cloud, str(exc)[:50]))
            continue
        theirs = {r.get("code"): r for r in live if r.get("code")}
        have = mine.get(cloud, {})
        gone = sorted(set(have) - set(theirs))
        new = sorted(set(theirs) - set(have))

        if not theirs:
            note("regions", WARN, "%s: the vendor returned no regions" % cloud)
            continue
        if gone:
            note("regions", FAIL,
                 "%s: we show %d region(s) the vendor no longer lists — %s"
                 % (cloud, len(gone), ", ".join(gone[:6])))
        if new:
            note("regions", WARN,
                 "%s: the vendor lists %d region(s) we do not show — %s"
                 % (cloud, len(new), ", ".join(new[:6])))
        if not gone and not new:
            note("regions", OK, "%s: all %d regions match the vendor's own list"
                 % (cloud, len(theirs)))

        # And the city, for the ones both sides agree exist. A region in the
        # wrong city is the version of this fault a reader can actually see on
        # the map.
        wrong = []
        for code in sorted(set(have) & set(theirs)):
            a = (have[code].get("city") or "").strip().lower()
            b = (theirs[code].get("city") or "").strip().lower()
            if a and b and a != b:
                wrong.append("%s: we say %s, they say %s"
                             % (code, have[code].get("city"),
                                theirs[code].get("city")))
        if wrong:
            note("regions", FAIL, "%s: %d region(s) placed in a different city "
                 "than the vendor states — %s"
                 % (cloud, len(wrong), "; ".join(wrong[:3])))
        elif set(have) & set(theirs):
            note("regions", OK, "%s: every shared region sits in the city the "
                 "vendor states" % cloud)


# ---------------------------------------------------------------------------
# 7. Typos and grammar in the copy a reader actually reads.
#
# A spellchecker over a site this technical is useless: every service name and
# region code is an unknown word. The first version of this tried "a long word
# used only once is suspicious" and reported 412 of them -- resilient, person,
# believe -- because seven pages of copy is nowhere near enough text for
# rarity to mean anything. A report with 412 false positives is a report
# nobody opens, which is worse than no report.
#
# So it looks for the shape a typo actually has: a word used ONCE that is one
# keystroke away from a word this site uses OFTEN. "recieve" next to 94 uses
# of "receive" is a typo; "resilient" used once is just a word. The corpus is
# every published post, which is enough text for "often" to mean something.
# ---------------------------------------------------------------------------
MECHANICAL = [
    (r"\s+[,;](?:\s|$)", "a space before a comma or semicolon"),
    (r"\s+\.(?:\s|$)", "a space before a full stop"),
    (r"([A-Za-z]{3,}) ", "a doubled word"),
    (r"[a-z]{2,},[A-Za-z]{2,}", "a missing space after a comma"),
]


# Tags that end a line of reading, and tags that sit inside one.
#
# Replacing EVERY tag with a space is what an earlier version did, and it
# invented eight punctuation faults that were not there:
#
#   <strong>understanding before doing</strong>, and   ->  "doing , and"
#   <a href="/blog/rss.xml">RSS</a>.                   ->  "RSS ."
#
# The copy was correct and the extractor was wrong -- which, in a report meant
# to be trusted, is the worst kind of finding to publish.
BLOCK = (r"p|div|li|ul|ol|br|hr|h[1-6]|section|header|footer|nav|aside|main|"
         r"table|thead|tbody|tr|td|th|blockquote|pre|figure|figcaption|dl|dt|dd")


def visible_text(page):
    body = text(page)
    if not body:
        return ""
    v = re.sub(r"<script.*?</script>|<style.*?</style>|<!--.*?-->", " ",
               body, flags=re.S)
    # An empty element carrying an id is a slot JavaScript fills in -- the page
    # reads "fetched 10 Sep 2026." and only the file reads "fetched ." Standing
    # in a character for it stops the extractor inventing a space before the
    # full stop, which it reported as a copy fault until it was checked.
    v = re.sub(r'<(\w+)[^>]*\bid="[^"]*"[^>]*>\s*</\1>', 'X', v)
    # A block boundary is a space; an inline tag is nothing at all.
    v = re.sub(r"</?(?:%s)\b[^>]*>" % BLOCK, " ", v, flags=re.I)
    v = re.sub(r"<[^>]+>", "", v)
    v = re.sub(r"&nbsp;", " ", v)
    v = re.sub(r"&[a-z]+;|&#\d+;", "", v)
    return re.sub(r"[ 	]+", " ", v)


def one_edit_away(word, known):
    """Is `word` one keystroke from anything in `known`?"""
    letters = "abcdefghijklmnopqrstuvwxyz"
    for i in range(len(word)):
        if word[:i] + word[i + 1:] in known:                    # a deletion
            return word[:i] + word[i + 1:]
        if i and word[:i - 1] + word[i] + word[i - 1] + word[i + 1:] in known:
            return word[:i - 1] + word[i] + word[i - 1] + word[i + 1:]
    for i in range(len(word)):
        for c in letters:
            if c != word[i]:
                cand = word[:i] + c + word[i + 1:]
                if cand in known:
                    return cand
    for i in range(len(word) + 1):
        for c in letters:
            cand = word[:i] + c + word[i:]
            if cand in known:
                return cand
    return None


def prose():
    # The corpus is every post plus the reader-facing pages -- enough text that
    # "this site uses that word often" is a real statement.
    corpus = {}
    posts_dir = os.path.join(ROOT, "blog")
    scanned = 0
    for base, dirs, files in os.walk(posts_dir):
        dirs[:] = [d for d in dirs if d not in ("assets", "page", "digests")]
        for name in files:
            if name != "index.html":
                continue
            rel = os.path.relpath(os.path.join(base, name), ROOT)
            v = visible_text(rel.replace("\\", "/"))
            if not v:
                continue
            scanned += 1
            for w in re.findall(r"[A-Za-z][A-Za-z]{3,}", v):
                w = w.lower()
                corpus[w] = corpus.get(w, 0) + 1

    per_page = {}
    for page in READER_PAGES:
        v = visible_text(page)
        if not v:
            continue
        per_page[page] = v
        for w in re.findall(r"[A-Za-z][A-Za-z]{3,}", v):
            w = w.lower()
            corpus[w] = corpus.get(w, 0) + 1

    common = {w for w, n in corpus.items() if n >= 8}
    found = 0
    for page, v in per_page.items():
        seen = set()
        for m in re.finditer(r"([a-z]{5,})", v):
            w = m.group(1)
            if corpus.get(w, 0) != 1 or w in seen:
                continue
            near = one_edit_away(w, common)
            if not near:
                continue
            seen.add(w)
            around = re.sub(r"\s+", " ",
                            v[max(0, m.start() - 30):m.end() + 30]).strip()
            note("prose", WARN,
                 "%s: '%s' is used once and is one letter from '%s', which the "
                 "site uses %d times — ...%s..."
                 % (page, w, near, corpus[near], around[:66]))
            found += 1
    if not found:
        note("prose", OK, "no likely typos across %d posts and %d pages"
             % (scanned, len(per_page)))

    mech = 0
    for page, v in per_page.items():
        for pattern, what in MECHANICAL:
            m = re.search(pattern, v)
            if not m:
                continue
            around = re.sub(r"\s+", " ",
                            v[max(0, m.start() - 30):m.end() + 30]).strip()
            note("prose", WARN, "%s: %s — ...%s..." % (page, what, around[:72]))
            mech += 1
    if not mech:
        note("prose", OK, "no doubled words or stray punctuation in the copy")


# ---------------------------------------------------------------------------
# 8. Does the site still RENDER correctly.
#
# The data can be perfect and the page still wrong: a nav that does not fit, a
# region drawn in the sea. These checks already exist and each needs a browser,
# so they are run here rather than rewritten, and only their verdict is folded
# into the report.
# ---------------------------------------------------------------------------
RENDER_CHECKS = [
    ("the map's dots sit on their own countries", "check_map_alignment.py"),
    ("the navigation holds on 5 pages at 6 widths", "check_nav.py"),
]


def rendering(enabled):
    if not enabled:
        note("rendering", WARN, "skipped, --no-browser was passed")
        return
    for label, script in RENDER_CHECKS:
        path = os.path.join(ROOT, "scripts", script)
        if not os.path.exists(path):
            note("rendering", WARN, "%s is missing" % script)
            continue
        try:
            out = subprocess.run([sys.executable, path], capture_output=True,
                                 text=True, cwd=ROOT, timeout=900,
                                 encoding="utf-8", errors="replace")
        except Exception as exc:                                # noqa: BLE001
            note("rendering", WARN, "%s did not run (%s)"
                 % (script, str(exc)[:50]))
            continue
        tail = [l for l in (out.stdout or "").strip().splitlines() if l.strip()]
        last = tail[-1].strip() if tail else "(no output)"
        if out.returncode == 0:
            note("rendering", OK, "%s — %s" % (label, last[:90]))
        else:
            note("rendering", FAIL, "%s — %s" % (label, last[:90]))


# ---------------------------------------------------------------------------
# 9. Anything on a reader's screen that should not be there.
# ---------------------------------------------------------------------------
LEFTOVERS = [
    (r"__[A-Z][A-Z0-9_]{2,}__", "an unresolved build token"),
    (r"\{\{[A-Za-z_]+\}\}", "an unresolved template placeholder"),
    (r"&amp;(amp|lt|gt|quot);", "a double-escaped HTML entity"),
    (r"\bTODO\b|\bFIXME\b|\bLorem ipsum\b", "a developer leftover"),
    (r"\bundefined\b", "a literal 'undefined'"),
    (r"\bNaN\b", "a literal 'NaN'"),
    (r"\b([A-Za-z]{4,}) \1\b", "a doubled word"),
]
READER_PAGES = ["index.html", "blog/index.html", "intelligence/index.html",
                "intelligence/status/index.html",
                "intelligence/whats-new/index.html", "now.html", "resume.html"]


def leftovers():
    clean = True
    for page in READER_PAGES:
        body = text(page)
        if not body:
            continue
        # Only what a reader could see: no scripts, styles or comments.
        visible = re.sub(r"<script.*?</script>|<style.*?</style>|<!--.*?-->",
                         " ", body, flags=re.S)
        visible = re.sub(r"<[^>]+>", " ", visible)
        for pattern, what in LEFTOVERS:
            m = re.search(pattern, visible)
            if not m:
                continue
            snippet = re.sub(r"\s+", " ",
                             visible[max(0, m.start() - 30):m.end() + 30]).strip()
            note("leftovers", WARN, "%s: %s — ...%s..."
                 % (page, what, snippet[:78]))
            clean = False
    if clean:
        note("leftovers", OK, "nothing out of place on %d reader-facing pages"
             % len(READER_PAGES))


TITLES = {
    "claims":    "What the pages claim, against the data behind them",
    "freshness": "Freshness, judged against each source's own schedule",
    "agreement": "Files that state the same fact",
    "jobs":      "Scheduled jobs",
    "vendors":   "Vendor endpoints the site cites",
    "regions":   "Our regions against the vendors' own lists",
    "prose":     "Typos and grammar in the copy",
    "rendering": "Does it still render correctly",
    "leftovers": "Anything on a reader's screen that should not be",
}
ORDER = ["claims", "regions", "freshness", "agreement", "jobs", "vendors",
         "prose", "rendering", "leftovers"]
MARK = {OK: "ok  ", WARN: "note", FAIL: "FAIL"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--markdown", default=None,
                    help="also write the report as markdown to this path")
    ap.add_argument("--no-network", action="store_true",
                    help="skip anything that leaves this machine")
    ap.add_argument("--no-browser", action="store_true",
                    help="skip the render checks, which need Playwright")
    args = ap.parse_args()

    claims()
    freshness()
    agreement()
    jobs()
    vendors(not args.no_network)
    vendor_regions(not args.no_network)
    prose()
    rendering(not args.no_browser)
    leftovers()

    fails = [f for f in findings if f[1] == FAIL]
    warns = [f for f in findings if f[1] == WARN]

    if fails:
        verdict = "NEEDS ATTENTION — %d problem(s), %d worth a look" % (
            len(fails), len(warns))
    elif warns:
        verdict = "HEALTHY — %d thing(s) worth a look" % len(warns)
    else:
        verdict = "HEALTHY — everything checked out"

    lines = ["# Site health — %s" % NOW.strftime("%d %B %Y, %H:%M UTC"), "",
             "**%s**" % verdict, ""]
    for key in ORDER:
        rows = [f for f in findings if f[0] == key]
        if not rows:
            continue
        bad = sum(1 for r in rows if r[1] != OK)
        lines += ["## %s" % TITLES[key], "",
                  "%d checked, %d to look at" % (len(rows), bad), "", "```"]
        lines += ["%s  %s" % (MARK[level], msg) for _, level, msg in rows]
        lines += ["```", ""]
    lines += ["---", "",
              "This checks what the site *says* against the data behind it. "
              "It reports and does not block: a typo, or a slow morning at a "
              "vendor, should not stop the site publishing."]

    report = "\n".join(lines)
    print(report)
    if args.markdown:
        io.open(os.path.join(ROOT, args.markdown), "w",
                encoding="utf-8", newline="\n").write(report)
    return 0            # reports, never blocks


if __name__ == "__main__":
    sys.exit(main())
