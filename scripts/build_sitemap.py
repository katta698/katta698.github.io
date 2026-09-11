#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Write sitemap.xml and robots.txt from what is actually published.

    python scripts/build_sitemap.py

Why this exists
---------------
Both were returning 404. Nothing pointed a search engine at 223 posts, five
main pages and an RSS feed -- the site was asking to be found by luck.

Generated rather than hand-kept, for the reason everything else here is: a
hand-written sitemap is correct on the day it is written and quietly wrong
from the next post onwards, and a sitemap that lists pages which no longer
exist is worse than none at all.

Last-modified dates come from git, not from the filesystem. A clone or a
checkout rewrites every mtime to "now", which would tell search engines the
whole archive was rewritten today -- and a site claiming 223 posts all changed
this morning is a site whose dates cannot be believed.
"""
import datetime as dt
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://jayanthkatta.com"

# Not everything published is worth indexing. The simulator is a toy, the
# offline page is a service-worker fallback, and paginated indexes are the
# same posts a second time.
SKIP_DIRS = {".git", "node_modules", "_archive", "_templates", "scripts",
             ".github", "posts", "drafts",
             # Internal surfaces that happen to be published: the CMS sign-in,
             # and the two pages that show how the hero rotation is scheduled.
             # Reachable is not the same as worth indexing.
             "admin", "schedule"}
SKIP_PATHS = {"offline.html", "404.html", "blog/simulator/index.html",
              "palette-preview.html"}

# How often each kind of page actually changes, as a hint rather than a claim.
PRIORITY = [
    ("index.html", "1.0", "weekly"),
    ("intelligence/status/index.html", "0.9", "hourly"),
    ("intelligence/whats-new/index.html", "0.9", "daily"),
    ("intelligence/index.html", "0.8", "weekly"),
    ("blog/index.html", "0.8", "daily"),
]


def git_date(path):
    """The last commit date for a file, or None if git cannot say."""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", path],
            capture_output=True, text=True, cwd=ROOT, timeout=20)
        d = (out.stdout or "").strip()
        return d if len(d) == 10 else None
    except Exception:                                           # noqa: BLE001
        return None


def pages():
    found = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs
                   if d not in SKIP_DIRS and not d.startswith(".")]
        for name in files:
            if not name.endswith(".html"):
                continue
            rel = os.path.relpath(os.path.join(base, name), ROOT)
            rel = rel.replace("\\", "/")
            if rel in SKIP_PATHS or "/page/" in rel:
                continue
            found.append(rel)
    return sorted(found)


def url_for(rel):
    if rel == "index.html":
        return SITE + "/"
    if rel.endswith("/index.html"):
        return SITE + "/" + rel[: -len("index.html")]
    return SITE + "/" + rel


def main():
    rels = pages()
    today = dt.date.today().isoformat()

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemap.org/schemas/sitemap/0.9">'
             .replace("www.sitemap.org", "www.sitemaps.org")]
    for rel in rels:
        prio, freq = "0.6", "monthly"
        for match, p, f in PRIORITY:
            if rel == match:
                prio, freq = p, f
                break
        lines.append("  <url>")
        lines.append("    <loc>%s</loc>" % url_for(rel))
        lines.append("    <lastmod>%s</lastmod>" % (git_date(rel) or today))
        lines.append("    <changefreq>%s</changefreq>" % freq)
        lines.append("    <priority>%s</priority>" % prio)
        lines.append("  </url>")
    # The feeds, which are not pages but are worth finding.
    #
    # Google accepts an RSS or Atom feed as a discovery source, and these are
    # the two things on the site that change without a page changing: the blog
    # feed when a post lands, the incident feeds when a cloud breaks. Listing
    # them costs six lines and means a crawler learns about an incident without
    # waiting to re-read the status page.
    for loc, freq in [("/blog/rss.xml", "daily"),
                      ("/intelligence/status/feed.xml", "hourly"),
                      ("/intelligence/status/feed-aws.xml", "hourly"),
                      ("/intelligence/status/feed-azure.xml", "hourly"),
                      ("/intelligence/status/feed-gcp.xml", "hourly")]:
        if not os.path.exists(os.path.join(ROOT, loc.lstrip("/"))):
            continue
        lines.append("  <url>")
        lines.append("    <loc>%s%s</loc>" % (SITE, loc))
        lines.append("    <lastmod>%s</lastmod>" % (git_date(loc.lstrip("/")) or today))
        lines.append("    <changefreq>%s</changefreq>" % freq)
        lines.append("    <priority>0.5</priority>")
        lines.append("  </url>")

    lines.append("</urlset>")

    io.open(os.path.join(ROOT, "sitemap.xml"), "w",
            encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")

    robots = [
        "# Everything here is meant to be read.",
        "User-agent: *",
        "Allow: /",
        "",
        "# Not worth indexing: a toy, a service-worker fallback, and the",
        "# paginated indexes, which are the same posts a second time.",
        "Disallow: /blog/simulator/",
        "Disallow: /offline.html",
        "Disallow: /blog/page/",
        "Disallow: /admin/",
        "Disallow: /schedule/",
        "Disallow: /palette-preview.html",
        "",
        "Sitemap: %s/sitemap.xml" % SITE,
        "",
    ]
    io.open(os.path.join(ROOT, "robots.txt"), "w",
            encoding="utf-8", newline="\n").write("\n".join(robots))

    print("  sitemap.xml: %d page(s)" % len(rels))
    print("  robots.txt written, pointing at the sitemap")
    return 0


if __name__ == "__main__":
    sys.exit(main())
