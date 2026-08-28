#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the complete note inventory for a GCP Weekly Intelligence post.

Emits the HTML for the "Complete inventory" section and validates every URL
before writing it -- the same two halves as build_weekly_inventory.py does for
AWS. It is a separate script rather than a flag on that one because the two
clouds do not publish anything like the same shape, and pretending otherwise is
what produced no GCP inventory at all for the first two roundups.

What is different about Google Cloud, all measured rather than assumed
-------------------------------------------------------------------
**Volume.** Measured for 17-21 August 2026: Azure 14 items, AWS 63, GCP 282.
AWS can print one row per announcement. GCP cannot -- 282 flat rows is not an
inventory a reader uses, it is one they scroll past.

**The volume is not spread evenly.** Container Optimized OS alone was 147 of the
282, and 131 of those were one-line kernel CVE fixes. Excluding it, the week was
135 notes -- the same order of magnitude as AWS, and entirely printable.

**Those 131 notes carry only 49 distinct CVEs.** COS ships one release note per
milestone, so a single kernel CVE is fixed in cos-129, cos-125, cos-121 and
cos-117 and is four separate notes. They are *not* duplicates. CLAUDE.md is
explicit that same-text/same-product must NOT be collapsed, and this is exactly
the case it means. So they are rolled up, which keeps the count, rather than
deduplicated, which would lose it.

**There is almost no per-item URL.** A note's link is the day anchor on the
release-notes page (`.../release-notes#August_17_2026`); only Cloud Blog items
have their own. Measured for that week: 282 notes, 11 distinct URLs. So link
validation here is mostly *anchor* validation -- the page answers 200 whether or
not the fragment exists, and a missing anchor drops the reader at the top of a
1.6 MB page. `check()` therefore fetches the page and asserts the id is present.

The rule for rolling up
-----------------------
A (product, type) group is rolled up when it has at least ROLLUP_MIN notes *and
repeats* -- fewer distinct summaries than notes. Repetition is the thing that
makes printing every row useless, and it is measurable, so the rule keys on it
rather than on a hardcoded product list that would go stale the first week
something other than COS has a bad month.

Deliberately NOT size alone: Gemini Enterprise shipped 9 features and Google
Kubernetes Engine 9 changes in the same week, all distinct and all real news.
A size threshold would have hidden them.

Completeness is asserted, not claimed
-------------------------------------
Every raw note lands in exactly one bucket -- collapsed across products, rolled
up, or listed -- and the script exits non-zero if the buckets do not sum to the
raw total. The reconciliation line is printed into the post so a reader can
check the same arithmetic.

Usage
-----
    python scripts/build_weekly_inventory_gcp.py 2026-08-17 2026-08-21 > section.html
"""
import argparse
import collections
import concurrent.futures
import datetime
import html
import re
import sys
import urllib.error
import urllib.request

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
# Import the source list rather than re-declaring it, so there is one definition
# of where GCP notes come from. build_weekly_inventory.py learned this the hard
# way: it re-declared the AWS feed URL and broke silently when fetch_week.py grew.
from fetch_week_gcp import MANUAL_SOURCES, gather_ctx  # noqa: E402

# A group must reach this many notes before repetition alone justifies rolling it
# up. Below it, even a repetitive group is short enough to read.
ROLLUP_MIN = 12

CVE_RE = re.compile(r"CVE-\d{4}-\d+")


def check(url):
    """Return (url, status). For a fragment URL, status 200 also requires the
    anchor to exist.

    The release-notes page answers 200 regardless of the fragment, so a status
    check alone would pass every dead day-anchor. Measured 28 August 2026:
    id="August_17_2026" is present in the served HTML and id="August_99_2026" is
    not, so the anchor is genuinely checkable -- which makes it worth checking.
    """
    base, _, frag = url.partition("#")
    for method in ("HEAD", "GET"):
        # A fragment can only be checked against a body, so never HEAD those.
        if frag and method == "HEAD":
            continue
        try:
            req = urllib.request.Request(
                base, method=method, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                if r.status != 200:
                    return url, r.status
                if not frag:
                    return url, 200
                body = r.read().decode("utf-8", "replace")
                if ('id="%s"' % frag) in body or ("id='%s'" % frag) in body:
                    return url, 200
                return url, "200 but no #%s anchor" % frag
        except urllib.error.HTTPError as e:
            if method == "GET" or frag:
                return url, e.code
        except Exception as e:                                    # noqa: BLE001
            if method == "GET" or frag:
                return url, "ERR %s" % type(e).__name__
    return url, "ERR"


def link_html(text, url, dead):
    """A title, linked unless its own URL is broken.

    A note whose link is dead still belongs in the inventory -- dropping it would
    break the completeness promise the series rests on -- but it must not ship as
    a link a reader cannot follow.
    """
    t = html.escape(text)
    if url and url not in dead:
        return '<a href="%s"><strong>%s</strong></a>' % (
            html.escape(url, quote=True), t)
    return "<strong>%s</strong>" % t


def classify(rows):
    """Split every row into exactly one of three buckets.

    Returns (cross, rolled, listed) where `cross` is grouped by summary text,
    `rolled` by (product, kind), and `listed` is the remainder. Precedence is
    cross first, because collapsing one text published under several products is
    a CLAUDE.md must; roll-up is a presentation choice and yields to it.
    """
    by_text = collections.defaultdict(set)
    for r in rows:
        by_text[r[3]].add(r[1])
    cross_texts = {t for t, ps in by_text.items() if len(ps) > 1 and t.strip()}

    rest = [r for r in rows if r[3] not in cross_texts]

    groups = collections.defaultdict(list)
    for r in rest:
        groups[(r[1], r[2])].append(r)
    rolled_keys = {
        k for k, g in groups.items()
        if len(g) >= ROLLUP_MIN and len({x[3] for x in g}) < len(g)
    }

    cross = collections.defaultdict(list)
    for r in rows:
        if r[3] in cross_texts:
            cross[r[3]].append(r)
    rolled = {k: groups[k] for k in rolled_keys}
    listed = [r for r in rest if (r[1], r[2]) not in rolled_keys]
    return cross, rolled, listed


def rollup_sentence(group):
    """Explain a run of repeating notes, and return the distinct facts inside it.

    Returns (sentence, extras). The count in the sentence is the raw note count,
    never a deduplicated one -- the repeats are real notes and CLAUDE.md forbids
    collapsing same-text/same-product. What is collapsed is only the *rendering*.

    `extras` is the set of distinct texts, listed so that rolling up costs the
    reader no information. Where the notes are CVE fixes the identifiers carry
    that already and go inline, because 49 CVE ids as a comma list is compact
    and 49 near-identical sentences is not.
    """
    n = len(group)
    texts = sorted({r[3] for r in group})
    milestones = sorted({r[5] for r in group if r[5]})
    cves = sorted({m.group(0) for r in group for m in [CVE_RE.search(r[3])] if m})

    s = "%d notes" % n
    if milestones:
        s += (", across %d %s (%s)"
              % (len(milestones),
                 "release" if len(milestones) == 1 else "releases",
                 ", ".join(milestones)))
    s += "."
    if cves:
        s += (" They fix %d distinct %s. A CVE is patched once per release, so "
              "the note count is higher than the CVE count &#8212; these are "
              "separate notes, not duplicates, and are counted as such: %s."
              % (len(cves), "CVE" if len(cves) == 1 else "CVEs", ", ".join(cves)))
        return s, []
    s += (" %d distinct %s, each repeated once per release and counted "
          "individually:" % (len(texts), "text" if len(texts) == 1 else "texts"))
    return s, texts


def build(rows, sources_read, failures):
    cross, rolled, listed = classify(rows)

    rolled_n = sum(len(g) for g in rolled.values())
    cross_n = sum(len(g) for g in cross.values())
    if rolled_n + cross_n + len(listed) != len(rows):
        print("BUCKETS DO NOT SUM: %d + %d + %d != %d"
              % (rolled_n, cross_n, len(listed), len(rows)), file=sys.stderr)
        return 1

    urls = sorted({r[4] for r in rows if r[4]})
    print("Validating %d distinct link(s)..." % len(urls), file=sys.stderr)
    bad = []
    dead = set()
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        for url, status in ex.map(check, urls):
            if status != 200:
                bad.append((url, status))
                dead.add(url)

    days = sorted({r[0] for r in rows})
    products = sorted({r[1] for r in rows})
    out = []

    # ---- reconciliation -------------------------------------------------
    out.append("    <h3>How this inventory reconciles</h3>")
    out.append(
        "    <p>\n"
        "      Google Cloud published <strong>%d notes</strong> across "
        "<strong>%d products</strong> and %d days in this window, read from %d "
        "feeds. Every one of them is accounted for below, in exactly one place:\n"
        "    </p>" % (len(rows), len(products), len(days), sources_read))
    out.append('    <div class="table-scroll">')
    out.append("    <table>")
    out.append("      <thead><tr><th>Bucket</th><th>Notes</th><th>Why</th></tr></thead>")
    out.append("      <tbody>")
    out.append(
        "        <tr><td>Listed individually</td><td>%d</td>"
        "<td>Every note that is its own distinct fact.</td></tr>" % len(listed))
    out.append(
        "        <tr><td>Published under several products</td><td>%d</td>"
        "<td>%d texts issued once per runtime or service; shown once, with the "
        "products named.</td></tr>" % (cross_n, len(cross)))
    out.append(
        "        <tr><td>Repeating runs, rolled up</td><td>%d</td>"
        "<td>%d product/type %s where the same text recurs once per release. "
        "Summarised with the full identifier list, not deduplicated.</td></tr>"
        % (rolled_n, len(rolled), "run" if len(rolled) == 1 else "runs"))
    out.append(
        "        <tr><td><strong>Total</strong></td><td><strong>%d</strong></td>"
        "<td>&nbsp;</td></tr>" % len(rows))
    out.append("      </tbody>")
    out.append("    </table>")
    out.append("    </div>")

    if failures:
        out.append(
            "    <p><strong>Feeds that did not answer:</strong> %s. This "
            "inventory is not provably complete for those sources.</p>"
            % html.escape(", ".join(failures)))

    # ---- rolled up ------------------------------------------------------
    if rolled:
        out.append("    <h3>Repeating runs, rolled up</h3>")
        out.append("    <ul>")
        for (product, kind), g in sorted(rolled.items(), key=lambda kv: -len(kv[1])):
            url = sorted({r[4] for r in g if r[4]})
            sentence, extras = rollup_sentence(g)
            out.append(
                "      <li>%s <em>&mdash; %s</em>"
                '<span class="inv-gist">%s</span>'
                % (link_html("%s (%d notes)" % (product, len(g)),
                             url[0] if url else "", dead),
                   html.escape(kind), sentence))
            if extras:
                out.append("        <ul>")
                for t in extras:
                    out.append('          <li><span class="inv-gist">%s'
                               "</span></li>" % html.escape(t))
                out.append("        </ul>")
            out.append("      </li>")
        out.append("    </ul>")

    # ---- cross-product --------------------------------------------------
    if cross:
        out.append("    <h3>One change, published under several products</h3>")
        out.append("    <ul>")
        for text, g in sorted(cross.items(), key=lambda kv: -len(kv[1])):
            ps = sorted({r[1] for r in g})
            url = sorted({r[4] for r in g if r[4]})
            out.append(
                "      <li>%s"
                '<span class="inv-gist">%s</span>'
                '<span class="inv-gist">Published under %d products: %s.</span>'
                "</li>"
                % (link_html(g[0][2], url[0] if url else "", dead),
                   html.escape(text), len(ps), html.escape(", ".join(ps))))
        out.append("    </ul>")

    # ---- everything else, by product ------------------------------------
    out.append("    <h3>Everything else, by product</h3>")
    by_product = collections.defaultdict(list)
    for r in listed:
        by_product[r[1]].append(r)
    for product in sorted(by_product):
        g = sorted(by_product[product], key=lambda r: (r[0], r[2]))
        out.append("    <h4>%s &mdash; %d</h4>" % (html.escape(product), len(g)))
        out.append("    <ul>")
        for d, _p, kind, summary, url, ctx in g:
            tail = " &middot; %s" % html.escape(ctx) if ctx else ""
            out.append(
                "      <li>%s"
                '<span class="inv-gist">%s</span>'
                '<span class="inv-gist">%s%s</span></li>'
                % (link_html(kind, url, dead), html.escape(summary),
                   d.strftime("%a %d %b"), tail))
        out.append("    </ul>")

    sys.stdout.buffer.write(("\n".join(out) + "\n").encode("utf-8"))

    print("\n%d notes | %d listed, %d cross-product, %d rolled up"
          % (len(rows), len(listed), cross_n, rolled_n), file=sys.stderr)
    print("buckets sum to the raw total: OK", file=sys.stderr)
    if bad:
        print("BROKEN LINKS, rendered as text (%d):" % len(bad), file=sys.stderr)
        for url, status in bad:
            print("  %s  %s" % (status, url), file=sys.stderr)
    else:
        print("all %d links resolve, anchors included" % len(urls), file=sys.stderr)
    for name in MANUAL_SOURCES:
        print("REMINDER: %s has no feed - check by hand" % name, file=sys.stderr)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("start")
    ap.add_argument("end")
    args = ap.parse_args()
    start = datetime.date.fromisoformat(args.start)
    end = datetime.date.fromisoformat(args.end)

    results = gather_ctx()
    rows, failures, ok = [], [], 0
    for name, _kind, rr, err in results:
        if err:
            failures.append(name)
            print("%-20s: FETCH FAILED - %s" % (name, err), file=sys.stderr)
            continue
        ok += 1
        hits = [r for r in rr if start <= r[0] <= end]
        rows.extend(hits)
        print("%-20s: %4d in range" % (name, len(hits)), file=sys.stderr)

    combined = next((rr for n, k, rr, e in results if k == "daynotes" and not e), [])
    if combined and min(r[0] for r in combined) >= start:
        print("\n*** TRUNCATION WARNING *** Release Notes reaches back only to %s;"
              " you asked from %s. Do not publish this as complete."
              % (min(r[0] for r in combined), start), file=sys.stderr)

    if not rows:
        print("Nothing in range across any source.", file=sys.stderr)
        return 1
    return build(rows, ok, failures)


if __name__ == "__main__":
    sys.exit(main())
