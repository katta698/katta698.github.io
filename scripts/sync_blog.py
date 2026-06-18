"""
Sync blog: fetch from Blogger → clean → build static pages at blog/
Run locally or via GitHub Actions (nightly cron).

Usage:
  python scripts/sync_blog.py
"""

import json
import math
import os
import re
import sys
from datetime import datetime
from html import escape
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ── Paths (relative to repo root) ─────────────────────────────
REPO_ROOT   = Path(__file__).parent.parent
BLOG_DIR    = REPO_ROOT / "blog"
ASSETS_URL  = "/blog/assets"

# ── Blogger config ────────────────────────────────────────────
FEED_BASE   = "https://blog.jayanthkatta.com/feeds/posts/default"
SITE_URL    = "https://jayanthkatta.com"
BLOG_URL    = f"{SITE_URL}/blog"
DISQUS_ID   = "jayanthkatta"

# ── ChatGPT CodeMirror markers ────────────────────────────────
CHATGPT_MARKERS = [
    "q9tKkq_viewer", "cm-editor", "lxnfua_", "cm-scroller",
    "cm-content", "q9tKkq_readonly", "border-token-border-light",
    "ͼd", "ͼr", "ͼm", "ͼg",
]

# ── Tag detection ─────────────────────────────────────────────
TAG_RULES = [
    ("AI",         ["rag", "bedrock", "llm", "amazon nova", "titan embed",
                    "vector embed", "semantic search"]),
    ("Kubernetes", ["kubernetes", "k8s", "helm", "kubectl", "pod manifest",
                    "namespace", "eks cluster"]),
    ("GitOps",     ["gitops", "argocd", "flux", "git ops", "drift detection"]),
    ("Terraform",  ["terraform", "hcl", "tfstate", "workspace", "terraform module",
                    "terraform import", "terraform cloud"]),
    ("AWS",        ["aws", "ec2", "s3 bucket", "rds mysql", "iam role", "lambda",
                    "cloudwatch", "cloudfront", "route 53", "vpc", "beanstalk",
                    "ssm", "glue", "fleet intelligence", "servicenow", "eks"]),
    ("Health",     ["sugar", "wheat", "longevity", "turning 40", "diet ",
                    "refined carbs", "i reduced"]),
    ("Career",     ["platform engineer", "enterprise platform", "self-service",
                    "ticket to ec2", "postgresql provisioning"]),
    ("Life",       ["daughter", "my child", "patience", "quiet promise",
                    "the conversations", "i stopped competing", "beautiful"]),
    ("Tech",       ["oracle", "mariadb", "mongodb", "azure log", "ansible",
                    "studio 3t", "asm integrity", "lock tables"]),
]
MAX_TAGS = 3
CATEGORY_ORDER = ["All", "AWS", "Terraform", "Kubernetes", "GitOps", "AI", "Tech", "Career", "Health", "Life"]

NAV_SVG = """<svg width="30" height="30" viewBox="0 0 80 80" xmlns="http://www.w3.org/2000/svg">
  <rect width="80" height="80" rx="14" fill="#0f1923"/>
  <defs><linearGradient id="jkg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="#FF9900"/>
    <stop offset="100%" stop-color="#FF9900" stop-opacity="0.3"/>
  </linearGradient></defs>
  <rect x="12" y="12" width="56" height="56" rx="10" fill="url(#jkg)"/>
  <text x="40" y="54" font-family="monospace" font-size="28" font-weight="700" fill="#0f1923" text-anchor="middle">JK</text>
</svg>"""


# ── Blogger fetch ─────────────────────────────────────────────
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
            posts.append({"title": title, "url": link, "html": content_html})
        next_link = next(
            (l["href"] for l in feed.get("link", []) if l.get("rel") == "next"), None
        )
        url = next_link
    return posts


# ── Clean HTML ────────────────────────────────────────────────
def has_chatgpt_junk(html):
    return any(m in html for m in CHATGPT_MARKERS)


def extract_code_text(pre_soup):
    code_el = pre_soup.find("pre", class_="cm-content") or pre_soup.find("code")
    if not code_el:
        return None
    for br in code_el.find_all("br"):
        br.replace_with("\n")
    for span in code_el.find_all("span"):
        span.unwrap()
    return code_el.get_text()


def clean_html(html):
    soup = BeautifulSoup(html, "html.parser")
    for pre in soup.find_all("pre"):
        try:
            pre_str = pre.decode()
        except Exception:
            pre_str = ""
        if has_chatgpt_junk(pre_str):
            code_text = extract_code_text(pre)
            if code_text and code_text.strip():
                new_pre = soup.new_tag("pre")
                new_code = soup.new_tag("code")
                new_code.string = code_text.strip()
                new_pre.append(new_code)
                pre.replace_with(new_pre)
            else:
                pre.decompose()
    for pre in soup.find_all("pre"):
        if not pre.get_text(strip=True):
            pre.decompose()
    for h2 in soup.find_all("h2"):
        style = h2.get("style", "")
        spans = h2.find_all("span", style=True)
        if "font-weight: 400" in style or any("font-weight: 400" in s.get("style", "") for s in spans):
            new_p = soup.new_tag("p")
            new_p.string = h2.get_text(strip=True)
            h2.replace_with(new_p)
    for tag in soup.find_all(["h2", "h3", "p"]):
        if tag.get("style"):
            del tag["style"]
    for code in soup.find_all("code"):
        for span in code.find_all("span"):
            span.unwrap()
        for br in code.find_all("br"):
            br.replace_with("\n")
    return str(soup)


# ── Post metadata helpers ─────────────────────────────────────
def detect_tags(text):
    text_lower = text.lower()
    tags = []
    for tag, keywords in TAG_RULES:
        if any(kw in text_lower for kw in keywords):
            tags.append(tag)
    return (tags or ["Tech"])[:MAX_TAGS]


def reading_time(html):
    text = BeautifulSoup(html, "html.parser").get_text()
    return max(1, math.ceil(len(text.split()) / 200))


def excerpt(html, max_chars=160):
    soup = BeautifulSoup(html, "html.parser")
    for p in soup.find_all("p"):
        txt = p.get_text(strip=True)
        if len(txt) > 30:
            return txt[:max_chars].rstrip() + ("…" if len(txt) > max_chars else "")
    text = soup.get_text(" ", strip=True)
    return text[:max_chars].rstrip() + "…"


def parse_date(url):
    m = re.search(r"/(\d{4})/(\d{2})/", url or "")
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), 1)
    return datetime(2024, 1, 1)


def slugify(title):
    s = re.sub(r"[^a-z0-9]+", "-", title.lower())
    return s.strip("-")[:60]


# ── HTML templates ────────────────────────────────────────────
def html_head(title, description, canonical, extra=""):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{escape(title)}</title>
<meta name="description" content="{escape(description)}"/>
<link rel="canonical" href="{canonical}"/>
<link rel="icon" href="/favicon.svg" type="image/svg+xml"/>
<link rel="stylesheet" href="{ASSETS_URL}/blog.css"/>
{extra}
</head>"""


def nav_html():
    return f"""<nav class="nav">
  <a class="nav-logo" href="/">{NAV_SVG}<span>Jayanth Katta</span></a>
  <div class="nav-spacer"></div>
  <ul class="nav-links">
    <li><a href="/">Home</a></li>
    <li><a href="/blog/" class="active">Blog</a></li>
    <li><a href="/resume.html">Resume</a></li>
  </ul>
</nav>"""


def footer_html():
    return f"""<footer class="footer">
  <p>&copy; {datetime.now().year} Jayanth Katta &mdash; <a href="{SITE_URL}">jayanthkatta.com</a></p>
</footer>"""


def back_top_html():
    return '<button class="back-top" id="back-top" aria-label="Back to top">↑</button>'


# ── Build individual post page ────────────────────────────────
def build_post_page(post, prev_post, next_post):
    slug     = post["slug"]
    title    = post["title"]
    tags     = post["tags"]
    post_url = f"{BLOG_URL}/{slug}/"

    tags_html = " ".join(f'<span class="tag-badge">{t}</span>' for t in tags)

    prev_link = (
        f'<a href="/blog/{prev_post["slug"]}/" class="post-nav-link prev">'
        f'<span class="post-nav-dir">← Previous</span>'
        f'<span class="post-nav-title">{escape(prev_post["title"])}</span></a>'
        if prev_post else ""
    )
    next_link = (
        f'<a href="/blog/{next_post["slug"]}/" class="post-nav-link next">'
        f'<span class="post-nav-dir">Next →</span>'
        f'<span class="post-nav-title">{escape(next_post["title"])}</span></a>'
        if next_post else ""
    )

    disqus = f"""<div class="comments-section">
  <h3>Comments</h3>
  <div id="disqus_thread"></div>
  <script>
    var disqus_config = function () {{
      this.page.url = '{post_url}';
      this.page.identifier = '{slug}';
    }};
    (function() {{
      var d = document, s = d.createElement('script');
      s.src = 'https://{DISQUS_ID}.disqus.com/embed.js';
      s.setAttribute('data-timestamp', +new Date());
      (d.head || d.body).appendChild(s);
    }})();
  </script>
  <noscript>Please enable JavaScript to view comments.</noscript>
</div>"""

    extra = '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css"/>'

    return f"""{html_head(title + " | Jayanth Katta Blog", post["excerpt"], post_url, extra)}
<body>
{nav_html()}
<main class="post-page-layout">
  <div class="post-breadcrumb">
    <a href="/">Home</a><span class="post-breadcrumb-sep">›</span>
    <a href="/blog/">Blog</a><span class="post-breadcrumb-sep">›</span>
    <span>{escape(title[:50])}{"…" if len(title)>50 else ""}</span>
  </div>
  <article>
    <header class="post-header">
      <div class="post-header-meta">{tags_html}</div>
      <h1>{escape(title)}</h1>
      <div class="post-info">
        <span>{post["date_fmt"]}</span>
        <span class="post-info-dot"></span>
        <span>{post["read_time"]} min read</span>
        <span class="post-info-dot"></span>
        <a href="https://blog.jayanthkatta.com" target="_blank" rel="noopener" style="color:inherit;opacity:.6;font-size:.72rem;">Originally on Blogger</a>
      </div>
    </header>
    <div class="post-divider"></div>
    <div class="post-body">{post["body_html"]}</div>
    <div class="post-tags">
      <span class="post-tags-label">Topics:</span>
      {tags_html}
    </div>
    <nav class="post-nav">{prev_link}{next_link}</nav>
  </article>
  {disqus}
</main>
{back_top_html()}
{footer_html()}
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<script>
  hljs.highlightAll();
  var btn=document.getElementById('back-top');
  window.addEventListener('scroll',function(){{btn.classList.toggle('show',window.scrollY>400);}},{{passive:true}});
  btn.addEventListener('click',function(){{window.scrollTo({{top:0,behavior:'smooth'}});}});
</script>
</body></html>"""


# ── Build index page ──────────────────────────────────────────
def build_index_page(posts):
    tag_counts = {}
    for p in posts:
        for t in p["tags"]:
            tag_counts[t] = tag_counts.get(t, 0) + 1

    cats = [c for c in CATEGORY_ORDER if c == "All" or tag_counts.get(c, 0) > 0]

    filter_pills = "\n".join(
        f'<button class="filter-pill {"active" if c=="All" else ""}" data-tag="{c.lower()}">'
        f'{c}{" ("+str(tag_counts.get(c,0))+")" if c!="All" else " ("+str(len(posts))+")"}'
        f'</button>'
        for c in cats
    )

    total_posts = len(posts)
    total_mins  = sum(p["read_time"] for p in posts)
    unique_tags = len([c for c in CATEGORY_ORDER if tag_counts.get(c, 0) > 0])

    cards_html = []
    for p in posts:
        tag1 = p["tags"][0] if p["tags"] else "Tech"
        tags_data = " ".join(p["tags"]).lower()
        cards_html.append(
            f'<a href="/blog/{p["slug"]}/" class="post-card"'
            f' data-title="{escape(p["title"])}"'
            f' data-excerpt="{escape(p["excerpt"])}"'
            f' data-tags="{escape(tags_data)}">'
            f'<div class="post-card-body">'
            f'<div class="post-meta"><span class="tag-badge">{tag1}</span>'
            f'<span class="post-date">{p["date_fmt"]}</span></div>'
            f'<div class="post-title">{escape(p["title"])}</div>'
            f'<div class="post-excerpt">{escape(p["excerpt"])}</div>'
            f'<div class="post-footer">'
            f'<span class="read-time"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> {p["read_time"]} min read</span>'
            f'<span class="read-more">Read <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg></span>'
            f'</div></div></a>'
        )

    sb_tags = "\n".join(
        f'<span class="sb-tag" data-tag="{c.lower()}">{c} <span style="opacity:.5;font-size:.65rem">{tag_counts.get(c,0)}</span></span>'
        for c in CATEGORY_ORDER if c != "All" and tag_counts.get(c, 0) > 0
    )

    return f"""{html_head(
        "Blog | Jayanth Katta",
        "AWS Platform Engineer writing about cloud infrastructure, Terraform, Kubernetes, and life.",
        f"{BLOG_URL}/"
    )}
<body>
{nav_html()}
<section class="hero">
  <span class="hero-eyebrow">Engineering &amp; Life</span>
  <h1>Jayanth's Blog</h1>
  <p class="hero-sub">Thoughts on AWS, Terraform, Kubernetes, platform engineering, and the quieter things in life.</p>
  <div class="hero-stats">
    <div class="hero-stat"><span class="hero-stat-n">{total_posts}</span><span class="hero-stat-l">Posts</span></div>
    <div class="hero-stat"><span class="hero-stat-n">{unique_tags}</span><span class="hero-stat-l">Topics</span></div>
    <div class="hero-stat"><span class="hero-stat-n">{total_mins}</span><span class="hero-stat-l">Min of reading</span></div>
  </div>
</section>
<div class="filters">
  {filter_pills}
  <div style="flex:1"></div>
  <div class="nav-search" style="position:relative">
    <svg class="nav-search-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
    <input id="blog-search" type="search" placeholder="Search posts…" style="background:#f6f8fa;border:1.5px solid #e8edf2;color:#1a1a2e;"/>
  </div>
</div>
<div class="results-count" id="results-count">{total_posts} posts</div>
<div class="layout">
  <div>
    <div class="posts-grid" id="posts-grid">
      {"".join(cards_html)}
      <div class="empty-state" id="empty-state" style="display:none">
        <h3>No posts found</h3><p>Try a different search term or topic filter.</p>
      </div>
    </div>
  </div>
  <aside class="sidebar">
    <div class="sidebar-card">
      <div class="sidebar-title">Stats</div>
      <div class="sidebar-stats">
        <div class="sb-stat"><span class="sb-stat-n">{total_posts}</span><span class="sb-stat-l">Posts</span></div>
        <div class="sb-stat"><span class="sb-stat-n">{unique_tags}</span><span class="sb-stat-l">Topics</span></div>
        <div class="sb-stat"><span class="sb-stat-n">{total_mins}</span><span class="sb-stat-l">Min</span></div>
        <div class="sb-stat"><span class="sb-stat-n">{posts[0]["date_fmt"] if posts else ""}</span><span class="sb-stat-l">Latest</span></div>
      </div>
    </div>
    <div class="sidebar-card">
      <div class="sidebar-title">Topics</div>
      <div class="sidebar-tags">{sb_tags}</div>
    </div>
    <div class="sidebar-card ask-cta">
      <div class="ask-cta-icon">✦</div>
      <div class="ask-cta-title">Ask about Jayanth</div>
      <div class="ask-cta-sub">Ask anything about his experience, projects, or career.</div>
      <a href="/" class="ask-cta-btn">Ask away</a>
    </div>
  </aside>
</div>
{back_top_html()}
{footer_html()}
<script src="{ASSETS_URL}/blog.js"></script>
</body></html>"""


# ── Main ──────────────────────────────────────────────────────
def main():
    print("Fetching posts from Blogger...")
    raw_posts = fetch_all_posts()
    print(f"  {len(raw_posts)} posts found")

    posts = []
    for entry in raw_posts:
        title    = entry["title"]
        url      = entry.get("url", "")
        body_html = clean_html(entry["html"])
        plain_text = BeautifulSoup(body_html, "html.parser").get_text()
        tags     = detect_tags(title + " " + plain_text)
        dt       = parse_date(url)
        slug     = slugify(title)

        posts.append({
            "slug":      slug,
            "title":     title,
            "url":       url,
            "date":      dt,
            "date_fmt":  dt.strftime("%b %Y"),
            "tags":      tags,
            "read_time": reading_time(body_html),
            "excerpt":   excerpt(body_html),
            "body_html": body_html,
        })

    posts.sort(key=lambda p: p["date"], reverse=True)

    print(f"Building {len(posts)} post pages...")
    for i, post in enumerate(posts):
        out_dir = BLOG_DIR / post["slug"]
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(
            build_post_page(
                post,
                prev_post=posts[i + 1] if i + 1 < len(posts) else None,
                next_post=posts[i - 1] if i > 0 else None,
            ),
            encoding="utf-8",
        )

    (BLOG_DIR / "index.html").write_text(build_index_page(posts), encoding="utf-8")
    print(f"Done — {len(posts)} posts built at blog/")


if __name__ == "__main__":
    main()
