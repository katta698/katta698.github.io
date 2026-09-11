#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Publish the cloud incidents as Atom feeds, so a reader can be told.

    python scripts/build_status_feed.py

Writes, into intelligence/status/:

    feed.xml         every cloud
    feed-aws.xml     }
    feed-azure.xml   }  one cloud each, for a reader who only runs on one
    feed-gcp.xml     }
    feed.xsl         so a browser renders the file instead of showing code

Why a feed and not an email list
--------------------------------
The alerts that exist today reach one person: they are GitHub issues, and they
arrive because I own the repository. A reader who wants to know when their
cloud breaks has no way to ask.

An email list would mean collecting addresses, storing them, being responsible
for them, and sending bursts of mail on exactly the evenings when three things
break at once -- which is where people unsubscribe. A feed asks nothing of the
reader and nothing of me: it is a static file, the reader points their own
software at it, and I never learn who is listening. Anyone who does want email
can point a service like Blogtrottr at the feed and give their address to them
instead of to me.

The thing that makes a feed useful or infuriating
-------------------------------------------------
An entry's `updated` timestamp is what tells a reader's software "this is new,
wake them". So it must change when something ACTUALLY happens and at no other
time.

The obvious implementation -- stamp every entry with the time the file was
built -- would re-notify every subscriber every hour, about incidents they were
already told about, forever. That is not a feed, it is a stuck alarm, and the
first thing anyone would do is unsubscribe.

So `updated` is the incident's own clock: when it began, and later when it was
resolved. Two notifications per incident, which is exactly the two moments a
reader wants: it broke, and it is over. The id never changes, so the second one
updates the first entry rather than arriving as a stranger.

The feed's own `updated` is the newest entry's, not the build time, for the
same reason.
"""
import datetime as dt
import io
import json
import os
import sys
from xml.sax.saxutils import escape

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "intelligence", "status")
SITE = "https://jayanthkatta.com"
PAGE = SITE + "/intelligence/status/"
NAMES = {"aws": "AWS", "azure": "Azure", "gcp": "Google Cloud"}
# Enough to give a new subscriber context without turning the file into the
# whole archive. The archive is on the page, and it is 922 long.
LIMIT = 60


def load(rel):
    try:
        return json.load(io.open(os.path.join(ROOT, rel), encoding="utf-8"))
    except Exception:                                           # noqa: BLE001
        return {}


def rfc3339(value):
    """A timestamp Atom will accept, from the several shapes this data uses.

    Open incidents carry a unix epoch as a string; the timeline carries a bare
    date. A date becomes midnight UTC, which is honest about the precision we
    actually have rather than inventing an hour.
    """
    if value in (None, ""):
        return None
    s = str(value).strip()
    if s.isdigit():
        try:
            return dt.datetime.fromtimestamp(int(s), dt.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, OSError, OverflowError):
            return None
    if len(s) >= 10:
        try:
            dt.date.fromisoformat(s[:10])
            return s[:10] + "T00:00:00Z"
        except ValueError:
            return None
    return None


def clean(text, limit=600):
    t = " ".join((text or "").split())
    return t[:limit] + ("…" if len(t) > limit else "")


def entries():
    """Open incidents first-hand, then what has recently cleared."""
    rows = []
    seen = set()

    status = load("intelligence/status.json")
    for cloud, items in (status.get("clouds") or {}).items():
        for i in items or []:
            ident = i.get("id") or (i.get("title") or "")[:80]
            if not ident or (cloud, ident) in seen:
                continue
            seen.add((cloud, ident))
            where = (i.get("region") or "").strip()
            code = (i.get("region_code") or "").strip()
            place = where + ((" (%s)" % code) if code and code != where else "")
            rows.append({
                "cloud": cloud,
                "id": ident,
                "open": True,
                "title": "%s — %s%s" % (NAMES.get(cloud, cloud),
                                        clean(i.get("title"), 90) or "open incident",
                                        (" in " + place) if place else ""),
                "when": rfc3339(i.get("begin")),
                "url": i.get("url") or PAGE,
                # " — " rather than a space: the service name and the vendor's
                # update ran together as "Multiple services We are providing".
                "body": clean(" — ".join(x.strip() for x in
                                         [i.get("service"), i.get("update")]
                                         if x and x.strip())),
            })

    # Then the recent record, so a feed is never empty and so the reader sees
    # the incident close rather than just stop being mentioned.
    tl = (load("intelligence/timeline-index.json") or {}).get("incidents") or []
    dated = [x for x in tl if x.get("b")]
    dated.sort(key=lambda x: (x.get("e") or x.get("b") or ""), reverse=True)
    for i in dated:
        cloud, ident = i.get("c"), i.get("i")
        if not ident or (cloud, ident) in seen:
            continue
        seen.add((cloud, ident))
        title = clean(i.get("t"), 110) or "an incident"
        # AWS prefixes its own resolved titles; saying it twice reads as noise.
        resolved = i.get("e")
        if not title.lower().startswith("[resolved]") and resolved:
            title = "[Resolved] " + title
        rows.append({
            "cloud": cloud,
            "id": ident,
            "open": False,
            "title": "%s — %s" % (NAMES.get(cloud, cloud), title),
            "when": rfc3339(resolved or i.get("b")),
            "url": i.get("u") or PAGE,
            "body": "Began %s%s. Read from the vendor's own record." % (
                i.get("b"), (", resolved " + resolved) if resolved else ""),
        })
        if len(rows) >= LIMIT * 2:
            break

    rows = [r for r in rows if r["when"]]
    # Open incidents stay at the top whatever their age: something broken now
    # matters more than something that cleared this morning.
    rows.sort(key=lambda r: (r["open"], r["when"]), reverse=True)
    return rows[:LIMIT]


def feed_xml(rows, cloud=None):
    which = NAMES.get(cloud, "AWS, Azure and Google Cloud")
    slug = "feed-%s.xml" % cloud if cloud else "feed.xml"
    self_url = PAGE + slug
    # The feed's clock is its newest entry, not the moment this ran. Otherwise
    # every hourly rebuild would look like news.
    newest = max((r["when"] for r in rows), default="1970-01-01T00:00:00Z")

    # The day's palette travels in the file.
    #
    # The whole site shifts its ground colour with the weekday, and the feed
    # was a fixed dark grey -- so following a link to it looked like leaving
    # the site, which is the complaint status.css already records about the
    # status page itself. A stylesheet applied by XSLT cannot read localStorage
    # or run a script: scripts in XSLT output do not execute in any browser. So
    # the day is written here, where the file is generated, and feed.xsl puts
    # it on <html> for the site's own CSS to pick up.
    day = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"][
        int(dt.datetime.now(dt.timezone.utc).strftime("%w"))]

    out = ['<?xml version="1.0" encoding="utf-8"?>',
           '<?xml-stylesheet type="text/xsl" href="feed.xsl"?>',
           '<feed xmlns="http://www.w3.org/2005/Atom" data-palette="%s">' % day,
           '  <title>Cloud incidents — %s</title>' % escape(which),
           '  <subtitle>Open incidents and the recent record, read from the '
           'vendors\' own status feeds. Nothing here is summarised or '
           'reworded.</subtitle>',
           '  <link rel="self" href="%s"/>' % escape(self_url),
           '  <link rel="alternate" type="text/html" href="%s"/>' % escape(PAGE),
           '  <id>%s</id>' % escape(self_url),
           '  <updated>%s</updated>' % newest,
           '  <author><name>Jayanth Katta</name>'
           '<uri>%s</uri></author>' % SITE,
           '  <generator uri="%s">jayanthkatta.com</generator>' % SITE]

    for r in rows:
        # A stable id, so a resolution updates the entry a reader already has
        # instead of arriving as a second, unrelated alert.
        eid = "tag:jayanthkatta.com,2026:incident:%s:%s" % (r["cloud"], r["id"])
        out += ['  <entry>',
                '    <title>%s</title>' % escape(r["title"]),
                '    <id>%s</id>' % escape(eid),
                '    <updated>%s</updated>' % r["when"],
                '    <link rel="alternate" href="%s"/>' % escape(r["url"]),
                '    <category term="%s" label="%s"/>'
                % (escape(r["cloud"]), escape(NAMES.get(r["cloud"], r["cloud"]))),
                '    <category term="%s"/>' % ("open" if r["open"] else "resolved"),
                '    <summary type="text">%s</summary>'
                % escape(r["body"] or r["title"]),
                '  </entry>']
    out.append('</feed>')
    return "\n".join(out) + "\n"


def main():
    rows = entries()
    os.makedirs(OUT, exist_ok=True)

    written = []
    for cloud in [None, "aws", "azure", "gcp"]:
        subset = rows if cloud is None else [r for r in rows if r["cloud"] == cloud]
        name = "feed-%s.xml" % cloud if cloud else "feed.xml"
        io.open(os.path.join(OUT, name), "w", encoding="utf-8",
                newline="\n").write(feed_xml(subset, cloud))
        written.append((name, len(subset),
                        sum(1 for r in subset if r["open"])))

    io.open(os.path.join(OUT, "feed.xsl"), "w", encoding="utf-8",
            newline="\n").write(XSL)

    for name, n, live in written:
        print("  %-16s %2d entr%s%s" % (name, n, "y" if n == 1 else "ies",
                                        ", %d open now" % live if live else ""))
    print("  feed.xsl written, so a browser shows a page and not code")
    return 0


# A feed is XML, and a browser handed raw XML shows what looks like broken
# code. This is applied by the browser only -- feed readers ignore it entirely
# -- so the same file serves software and people.
XSL = """<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:atom="http://www.w3.org/2005/Atom">
<xsl:output method="html" encoding="utf-8" indent="yes"/>
<xsl:template match="/">
<html lang="en">
  <xsl:attribute name="data-palette"><xsl:value-of
    select="/atom:feed/@data-palette"/></xsl:attribute>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title><xsl:value-of select="atom:feed/atom:title"/></title>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600&amp;family=Playfair+Display:wght@600&amp;family=DM+Mono:wght@400&amp;display=swap" rel="stylesheet"/>
  <!-- The site's own stylesheet, not a copy of its colours. That is what makes
       the ground, the type and the weekday palette the same here as on the
       page this was linked from; a second set of hex values would drift from
       the first the day either changed. -->
  <link rel="stylesheet" href="/intelligence/status/status.css"/>
  <style>
    .wrap{max-width:44rem;margin:0 auto;padding:2.25rem 1.25rem 4rem}
    h1{font-family:var(--serif);font-size:1.5rem;margin:0 0 .4rem}
    .sub{color:var(--mut);font-size:.92rem;margin:0 0 1.5rem}
    .note{background:var(--card);border:1px solid var(--bd);
      border-radius:12px;padding:1rem 1.1rem;margin:0 0 2rem;font-size:.92rem}
    .note strong{color:var(--acc)}
    .note code{background:rgba(128,128,128,.16);padding:.1rem .35rem;
      border-radius:4px;font-family:var(--mono);font-size:.86em}
    article{border-top:1px solid var(--bd);padding:1.1rem 0}
    h2{font-size:1rem;margin:0 0 .3rem;font-weight:600;font-family:var(--sans)}
    h2 a{color:var(--tx);text-decoration:none}
    h2 a:hover{color:var(--acc)}
    .meta{color:var(--mut);font-size:.8rem;margin:0 0 .45rem;
      font-family:var(--mono)}
    .open{color:var(--red);font-weight:600}
    p.body{margin:0;color:var(--tx);opacity:.88;font-size:.92rem}
    a{color:var(--acc)}
  </style>
</head>
<body><div class="wrap">
  <h1><xsl:value-of select="atom:feed/atom:title"/></h1>
  <p class="sub"><xsl:value-of select="atom:feed/atom:subtitle"/></p>
  <div class="note">
    <strong>This is a feed, not a page.</strong> Copy this page's address into
    a feed reader, or into Slack with
    <code>/feed subscribe &lt;address&gt;</code>, and you will be told when a
    cloud breaks and again when it clears. No sign-up, no email address, and
    nothing to unsubscribe from &#8212; you are not on a list, because there is
    no list. <a href="/intelligence/status/">Back to the status page</a>.
  </div>
  <xsl:for-each select="atom:feed/atom:entry">
    <article>
      <h2>
        <a><xsl:attribute name="href"><xsl:value-of
           select="atom:link/@href"/></xsl:attribute>
          <xsl:value-of select="atom:title"/></a>
      </h2>
      <p class="meta">
        <xsl:if test="atom:category[@term='open']">
          <span class="open">Open now</span><xsl:text> &#183; </xsl:text>
        </xsl:if>
        <xsl:value-of select="atom:updated"/>
      </p>
      <p class="body"><xsl:value-of select="atom:summary"/></p>
    </article>
  </xsl:for-each>
</div></body>
</html>
</xsl:template>
</xsl:stylesheet>
"""


if __name__ == "__main__":
    sys.exit(main())
