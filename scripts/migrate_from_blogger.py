"""
One-time migration: pull every post off Blogger and save it as a local
posts/<slug>.html file (front matter + raw body), so the site has zero
ongoing dependency on Blogger going forward.

Run once:
  python scripts/migrate_from_blogger.py

After running, sync_blog.py no longer needs to fetch from Blogger at all —
every post (old and new) is a local file under posts/.
"""

import re
from pathlib import Path

import requests
import yaml

REPO_ROOT = Path(__file__).parent.parent
POSTS_DIR = REPO_ROOT / "posts"
FEED_BASE = "https://blog.jayanthkatta.com/feeds/posts/default"


def fetch_all_posts():
    posts = []
    url = f"{FEED_BASE}?alt=json&max-results=50"
    while url:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        feed = data.get("feed", {})
        for entry in feed.get("entry", []):
            link = next(
                (l["href"] for l in entry.get("link", []) if l.get("rel") == "alternate"), None
            )
            title = entry.get("title", {}).get("$t", "Untitled")
            content_html = entry.get("content", {}).get("$t", "")
            published = entry.get("published", {}).get("$t", "")
            labels = [c.get("term", "") for c in entry.get("category", [])]
            posts.append({"title": title, "url": link, "html": content_html, "published": published, "labels": labels})
        next_link = next(
            (l["href"] for l in feed.get("link", []) if l.get("rel") == "next"), None
        )
        url = next_link
    return posts


def slugify(title):
    s = re.sub(r"[^a-z0-9]+", "-", title.lower())
    return s.strip("-")[:60]


def main():
    print("Fetching all posts from Blogger...")
    raw_posts = fetch_all_posts()
    print(f"  {len(raw_posts)} posts found")

    POSTS_DIR.mkdir(exist_ok=True)
    written, skipped = 0, []
    seen_slugs = set()

    for entry in raw_posts:
        title = entry["title"]
        slug = slugify(title)
        if slug in seen_slugs:
            skipped.append((title, "duplicate slug"))
            continue
        seen_slugs.add(slug)

        out_path = POSTS_DIR / f"{slug}.html"
        if out_path.exists():
            skipped.append((title, "file already exists, not overwritten"))
            continue

        front_matter = {
            "title": title,
            # Keep the full timestamp (not just the date) — truncating loses
            # the time-of-day, which breaks prev/next ordering between any
            # two posts published on the same calendar day.
            "date": entry.get("published") or "2024-01-01T00:00:00",
            "labels": entry.get("labels", []),
            "slug": slug,
        }
        fm_text = yaml.dump(front_matter, default_flow_style=False, allow_unicode=True, sort_keys=False)
        out_path.write_text(f"---\n{fm_text}---\n{entry['html']}", encoding="utf-8")
        written += 1

    print(f"Wrote {written} post(s) to posts/")
    if skipped:
        print(f"Skipped {len(skipped)}:")
        for title, reason in skipped:
            print(f"  - {title!r}: {reason}")


if __name__ == "__main__":
    main()
