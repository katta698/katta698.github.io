#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Collect what the AI vendors have actually shipped, from their own sources.

    python scripts/fetch_ai.py            # fetch, merge, write intelligence/ai.json
    python scripts/fetch_ai.py --audit    # probe every source and report, write nothing

Why this exists
---------------
Asked for as: "a dedicated page for AI, like Intelligence and What's New --
what GPT has to offer, what models they have, what's new, and the same for
Anthropic, Gemini, Grok, Copilot. Can we make API calls to the official
sites and fetch the latest models, features, releases?"

Mostly yes, and the shape of "mostly" is the whole design. Every source below
was probed before a line of this was written, because a page that claims to
track a vendor and silently tracks nothing is worse than no page:

    OpenAI news            RSS, 644 items
    Google AI blog         RSS,  20 items
    Google DeepMind        RSS, 100 items
    Microsoft 365 blog     RSS,  10 items
    Azure blog             RSS,  10 items
    Hugging Face blog      RSS, 862 items
    AWS What's New         RSS, 100 items   (filtered to AI services only)

    Anthropic              NO FEED -- sitemap.xml, 535 urls with lastmod
    xAI                    NO FEED -- sitemap.xml, 251 urls with lastmod
    Mistral                sitemap holds 1 url; nothing usable

Anthropic and xAI publish no RSS at all. Their sitemaps are official and
carry <lastmod>, so a new page under /news/ is detectable the day it
appears -- and the page's own <title> is then fetched, rather than inventing
a headline from the slug. It is a weaker source than a feed and is labelled
as one on the page.

THE MODEL CATALOGUE IS ONE CALL. OpenRouter's /api/v1/models answers with 446
models across every vendor asked about -- openai 91, qwen 54, google 41,
anthropic 27, mistralai 24, deepseek 18, meta 8 -- each carrying
context_length, pricing, created, knowledge_cutoff, reasoning support and
modalities. `created` is what makes "new models this week" a measurement
rather than an opinion.

It is an AGGREGATOR, not the vendors' own API, and that is stated on the
page rather than glossed: it lags a launch by hours to days, it lists
community models beside official ones, and its prices are what OpenRouter
charges, which is not always what the vendor charges direct. Every vendor
would otherwise need a key, a different auth scheme and a different schema,
and three of them publish no model API at all.

The store grows rather than resets
----------------------------------
Same reason as the cloud announcements: feeds are short. Google's AI blog
holds 20 items and Microsoft's 10, so a fortnight unread is a fortnight
gone. Items are merged into intelligence/ai.json by URL and never dropped,
so the page can say "since we started watching" rather than "whatever the
feed still remembers".
"""
import argparse
import concurrent.futures as futures
import html
import io
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "intelligence", "ai.json")

UA = ("Mozilla/5.0 (compatible; jayanthkatta.com/1.0; "
      "+https://jayanthkatta.com)")

# Every source, with what it is. `kind` decides how it is read, and the page
# prints it, so a reader can tell a vendor's own feed from a sitemap probe.
FEEDS = [
    ("OpenAI", "feed", "https://openai.com/news/rss.xml"),
    ("Google", "feed", "https://blog.google/technology/ai/rss/"),
    ("Google DeepMind", "feed", "https://deepmind.google/blog/rss.xml"),
    ("Microsoft", "feed",
     "https://www.microsoft.com/en-us/microsoft-365/blog/feed/"),
    ("Microsoft Azure", "feed", "https://azure.microsoft.com/en-us/blog/feed/"),
    ("Hugging Face", "feed", "https://huggingface.co/blog/feed.xml"),
    ("AWS", "feed", "https://aws.amazon.com/about-aws/whats-new/recent/feed/"),
]

# The two that publish no feed. Only paths under these prefixes are treated
# as announcements -- a sitemap lists every page a site has, and a docs page
# changing is not a release.
SITEMAPS = [
    ("Anthropic", "https://www.anthropic.com/sitemap.xml",
     ("/news/", "/research/")),
    # x.ai/news/<slug>, with no trailing slash on the section itself, so
    # "/news/" as a prefix matches the articles and not the index page.
    ("xAI", "https://x.ai/sitemap.xml", ("/news/", "/blog/")),
]

MODELS_API = "https://openrouter.ai/api/v1/models"

# AWS publishes everything on one feed; only the AI services belong here.
AWS_AI = re.compile(
    r"\b(bedrock|sagemaker|amazon q|nova|titan|comprehend|rekognition|"
    r"textract|transcribe|polly|lex|kendra|personalize|forecast|"
    r"trainium|inferentia)\b", re.I)

# Which vendor an OpenRouter id belongs to. Anything unlisted is kept and
# grouped under its own prefix rather than dropped -- the catalogue is not
# ours to curate.
VENDOR = {
    "openai": "OpenAI", "anthropic": "Anthropic", "google": "Google",
    "x-ai": "xAI", "meta-llama": "Meta", "meta": "Meta",
    "mistralai": "Mistral", "deepseek": "DeepSeek", "qwen": "Qwen",
    "microsoft": "Microsoft", "cohere": "Cohere", "ai21": "AI21",
    "amazon": "Amazon", "nvidia": "NVIDIA", "moonshotai": "Moonshot",
    "perplexity": "Perplexity",
}

# The vendors the page leads with, in this order. Everything else is real and
# listed, just not given a section of its own.
HEADLINE = ["OpenAI", "Anthropic", "Google", "xAI", "Meta", "Microsoft",
            "Mistral", "DeepSeek"]


def fetch(url, cap=2_500_000, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read(cap).decode("utf-8", "replace")


def when(text):
    """A date from whatever the feed felt like emitting."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        d = parsedate_to_datetime(text)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception:
        pass
    # ISO 8601 with whatever precision the publisher felt like. Both
    # sitemaps stamp "2026-09-09T19:42:51.000Z" -- fractional seconds and a
    # Z -- which matched none of the formats below, so every sitemap row
    # lost its date and was filtered out as undatable.
    try:
        d = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            d = datetime.strptime(text.replace("Z", "+0000"), fmt)
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return d.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def strip_tags(s):
    # CDATA first, and this is not a detail.
    #
    # OpenAI wraps every title in <![CDATA[...]]>, which contains no ">"
    # until its own terminator -- so a plain tag-stripper matches from the
    # opening "<" all the way to "]]>" and deletes the headline with it.
    # parse_feed then drops the item for having no title, and a 1,210-item
    # feed yields nothing at all. It fails silently and completely: the
    # source is reachable, the items are found, and none survive.
    s = re.sub(r"<!\[CDATA\[(.*?)\]\]>", lambda m: m.group(1), s or "", flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s or "")
    # html.unescape, not six replacements by hand.
    #
    # The hand-rolled version knew &amp; &lt; &gt; &quot; &#39; and &nbsp;
    # and nothing else, so an apostrophe written any of the other three
    # common ways survived it and was then re-escaped on the way out:
    #
    #     How Claude&#x27;s values vary by model and language
    #     Granite 4.2 LLMs: How They&apos;re Built
    #     How Microsoft&#8217;s Physical Security Engineering Team...
    #
    # Five titles across three vendors, each using a different form of the
    # same character. A list of entities is a list that is always missing
    # one; the standard library has all of them.
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


ITEM_RE = re.compile(r"<(item|entry)[ >].*?</\1>", re.S)


def parse_feed(vendor, xml):
    """Items from RSS or Atom, without a dependency."""
    out = []
    for m in ITEM_RE.finditer(xml):
        blob = m.group(0)
        title = re.search(r"<title[^>]*>(.*?)</title>", blob, re.S)
        link = re.search(r'<link[^>]*href="([^"]+)"', blob) or \
            re.search(r"<link[^>]*>(.*?)</link>", blob, re.S)
        date = (re.search(r"<pubDate>(.*?)</pubDate>", blob, re.S)
                or re.search(r"<updated>(.*?)</updated>", blob, re.S)
                or re.search(r"<published>(.*?)</published>", blob, re.S))
        summary = (re.search(r"<description>(.*?)</description>", blob, re.S)
                   or re.search(r"<summary[^>]*>(.*?)</summary>", blob, re.S))
        d = when(strip_tags(date.group(1)) if date else "")
        url = strip_tags(link.group(1)) if link else ""
        t = strip_tags(title.group(1)) if title else ""
        if not (url and t):
            continue
        out.append({
            "vendor": vendor, "title": t, "url": url,
            "date": d.date().isoformat() if d else None,
            "summary": strip_tags(summary.group(1))[:280] if summary else "",
            "via": "feed",
        })
    return out


def parse_sitemap(vendor, xml, prefixes, limit=12):
    """New pages under the announcement paths, newest first.

    A sitemap is not a feed: it has no titles. The <title> is fetched from
    the page itself for the few that are new, because a headline invented
    from a URL slug is a headline nobody wrote.
    """
    rows = []
    for m in re.finditer(r"<url>(.*?)</url>", xml, re.S):
        blob = m.group(1)
        loc = re.search(r"<loc>(.*?)</loc>", blob, re.S)
        mod = re.search(r"<lastmod>(.*?)</lastmod>", blob, re.S)
        if not loc:
            continue
        url = strip_tags(loc.group(1))
        if not any(p in url for p in prefixes):
            continue
        d = when(strip_tags(mod.group(1))) if mod else None
        rows.append((d, url))
    rows = [r for r in rows if r[0]]
    rows.sort(key=lambda r: r[0], reverse=True)
    return [{"vendor": vendor, "url": u, "title": "",
             "date": d.date().isoformat(), "summary": "", "via": "sitemap"}
            for d, u in rows[:limit]]


def title_of(url):
    try:
        _code, html = fetch(url, cap=180_000, timeout=20)
    except Exception:
        return ""
    m = (re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"',
                   html)
         or re.search(r"<title[^>]*>(.*?)</title>", html, re.S))
    t = strip_tags(m.group(1)) if m else ""
    for tail in (" \\ Anthropic", " | Anthropic", " | xAI", " - xAI"):
        if t.endswith(tail):
            t = t[: -len(tail)]
    return t.strip()


def models():
    """The catalogue, in one call, with the fields worth printing."""
    _code, body = fetch(MODELS_API, cap=6_000_000)
    data = json.loads(body).get("data") or []
    out = []
    for m in data:
        mid = m.get("id") or ""
        prefix = mid.split("/")[0].lstrip("~")
        price = m.get("pricing") or {}

        def rate(key):
            try:
                v = float(price.get(key) or 0)
            except (TypeError, ValueError):
                return None
            # A NEGATIVE price is a sentinel, not a discount.
            #
            # OpenRouter answers "-1" for its routers -- Auto Router, Fusion,
            # Pareto Code Router -- which charge whatever the model they pick
            # charges. Multiplied by a million that became -$1,000,000 per
            # million tokens, which would have plotted five points a very
            # long way below the axis and printed a number no reader could
            # take seriously. Unknown is unknown; the page prints a dash.
            if v < 0:
                return None
            # per token -> per million, which is how every vendor quotes it
            return round(v * 1_000_000, 4) if v else 0.0

        created = m.get("created")
        out.append({
            "id": mid,
            "name": m.get("name") or mid,
            "vendor": VENDOR.get(prefix, prefix),
            "context": m.get("context_length"),
            "in_per_m": rate("prompt"),
            "out_per_m": rate("completion"),
            "created": (datetime.fromtimestamp(created, timezone.utc)
                        .date().isoformat() if created else None),
            "cutoff": m.get("knowledge_cutoff"),
            "reasoning": bool((m.get("supported_parameters") or [])
                              and "reasoning" in
                              (m.get("supported_parameters") or [])),
            "modalities": ((m.get("architecture") or {})
                           .get("input_modalities") or []),
        })
    return out


def audit():
    """Probe everything and say what is actually there. Writes nothing."""
    print("  %-18s %-8s %-6s %s" % ("source", "kind", "items", "newest"))
    problems = []

    def one(row):
        vendor, kind, url = row
        try:
            code, body = fetch(url)
        except Exception as e:
            return vendor, kind, 0, "ERR %s" % str(e)[:40], True
        items = parse_feed(vendor, body)
        dates = sorted([i["date"] for i in items if i["date"]], reverse=True)
        stale = (not dates) or (
            datetime.now(timezone.utc).date()
            - datetime.fromisoformat(dates[0]).date() > timedelta(days=45))
        return vendor, kind, len(items), (dates[0] if dates else "?"), stale

    with futures.ThreadPoolExecutor(max_workers=8) as ex:
        for vendor, kind, n, newest, bad in ex.map(one, FEEDS):
            print("  %-18s %-8s %-6d %s%s"
                  % (vendor, kind, n, newest, "   STALE" if bad else ""))
            if bad:
                problems.append("%s: %s" % (vendor, newest))

    for vendor, url, prefixes in SITEMAPS:
        try:
            _code, body = fetch(url)
            rows = parse_sitemap(vendor, body, prefixes)
            print("  %-18s %-8s %-6d %s" % (vendor, "sitemap", len(rows),
                                            rows[0]["date"] if rows else "?"))
            if not rows:
                problems.append("%s: sitemap matched no announcement paths"
                                % vendor)
        except Exception as e:
            print("  %-18s %-8s %-6d ERR %s" % (vendor, "sitemap", 0,
                                                str(e)[:40]))
            problems.append("%s: %s" % (vendor, str(e)[:60]))

    try:
        cat = models()
        by = {}
        for m in cat:
            by[m["vendor"]] = by.get(m["vendor"], 0) + 1
        top = sorted(by.items(), key=lambda kv: -kv[1])[:8]
        print("  %-18s %-8s %-6d %s" % ("OpenRouter", "api", len(cat),
                                        ", ".join("%s %d" % t for t in top)))
        if len(cat) < 50:
            problems.append("the model catalogue returned only %d models"
                            % len(cat))
    except Exception as e:
        print("  %-18s %-8s %-6d ERR %s" % ("OpenRouter", "api", 0,
                                            str(e)[:40]))
        problems.append("model catalogue: %s" % str(e)[:60])

    print()
    if problems:
        print("  %d SOURCE(S) NEED LOOKING AT" % len(problems))
        for p in problems:
            print("  - %s" % p)
        return 1
    print("  Every source answered and is current.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", action="store_true")
    ap.add_argument("--days", type=int, default=120,
                    help="how far back to keep feed items on a fresh store")
    args = ap.parse_args()

    if args.audit:
        return audit()

    old = {"releases": [], "models": []}
    if os.path.exists(OUT):
        try:
            old = json.load(io.open(OUT, encoding="utf-8"))
        except ValueError:
            pass

    # ---- releases ----------------------------------------------------
    seen = {r["url"]: r for r in (old.get("releases") or [])}
    added = 0
    cutoff = (datetime.now(timezone.utc) - timedelta(days=args.days)).date()

    def pull(row):
        vendor, _kind, url = row
        try:
            _code, body = fetch(url)
        except Exception:
            return []
        items = parse_feed(vendor, body)
        if vendor == "AWS":
            items = [i for i in items
                     if AWS_AI.search(i["title"] + " " + i["summary"])]
        return items

    with futures.ThreadPoolExecutor(max_workers=8) as ex:
        for items in ex.map(pull, FEEDS):
            for i in items:
                if i["url"] in seen:
                    continue
                if i["date"] and datetime.fromisoformat(i["date"]).date() < cutoff:
                    continue
                seen[i["url"]] = i
                added += 1

    for vendor, url, prefixes in SITEMAPS:
        try:
            _code, body = fetch(url)
        except Exception:
            continue
        for i in parse_sitemap(vendor, body, prefixes):
            if i["url"] in seen:
                continue
            i["title"] = title_of(i["url"]) or i["url"].rstrip("/").split("/")[-1].replace("-", " ").title()
            seen[i["url"]] = i
            added += 1

    # Repair what is already in the store.
    #
    # The merge deliberately never revisits a URL it has seen -- that is
    # what makes it a store rather than a snapshot -- so a parser fix does
    # not reach the rows it was written for. Re-running strip_tags over the
    # stored text is idempotent and costs nothing, and it means a decoding
    # fix repairs the archive instead of only helping tomorrow's items.
    for row in seen.values():
        for field in ("title", "summary"):
            if row.get(field):
                row[field] = strip_tags(row[field])

    releases = sorted(seen.values(),
                      key=lambda r: (r.get("date") or "0000-00-00"),
                      reverse=True)

    # ---- models ------------------------------------------------------
    try:
        catalogue = models()
    except Exception as e:
        print("  model catalogue failed (%s); keeping the previous one"
              % str(e)[:60])
        catalogue = old.get("models") or []

    payload = {
        "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "releases": releases,
        "models": catalogue,
        "sources": (
            [{"vendor": v, "kind": k, "url": u} for v, k, u in FEEDS]
            + [{"vendor": v, "kind": "sitemap", "url": u}
               for v, u, _p in SITEMAPS]
            + [{"vendor": "OpenRouter", "kind": "api", "url": MODELS_API}]
        ),
    }
    tmp = OUT + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, OUT)

    vendors = {}
    for r in releases:
        vendors[r["vendor"]] = vendors.get(r["vendor"], 0) + 1
    print("  %d release(s) from %d vendor(s), %d new this run"
          % (len(releases), len(vendors), added))
    print("  %d model(s) in the catalogue" % len(catalogue))
    print("  %s" % ", ".join("%s %d" % kv for kv in
                             sorted(vendors.items(), key=lambda kv: -kv[1])[:8]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
