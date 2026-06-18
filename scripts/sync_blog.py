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
API_URL     = "https://37arp5b92a.execute-api.us-east-1.amazonaws.com/search"

FEEDBACK_WIDGET_HTML = """
<button class="fb-btn" id="fb-btn" aria-label="Give feedback" title="Give feedback">&#9733;</button>
<div class="fb-overlay" id="fb-overlay">
  <div class="fb-modal" id="fb-modal">
    <div class="fb-title">How was your experience?</div>
    <div class="fb-sub">Your feedback helps improve this site.</div>
    <div class="fb-stars" id="fb-stars">
      <button class="fb-star" data-v="1" aria-label="1 star">&#9733;</button>
      <button class="fb-star" data-v="2" aria-label="2 stars">&#9733;</button>
      <button class="fb-star" data-v="3" aria-label="3 stars">&#9733;</button>
      <button class="fb-star" data-v="4" aria-label="4 stars">&#9733;</button>
      <button class="fb-star" data-v="5" aria-label="5 stars">&#9733;</button>
    </div>
    <div class="fb-labels"><span>Poor</span><span>Excellent</span></div>
    <textarea class="fb-textarea" id="fb-text" placeholder="Any thoughts? (optional)"></textarea>
    <div class="fb-footer">
      <button class="fb-skip" id="fb-skip">Skip</button>
      <button class="fb-send" id="fb-send">Send feedback</button>
    </div>
  </div>
</div>
<script>
(function(){
  var FORM_ID='xzdqqvqd';
  var rating=0;
  var btn=document.getElementById('fb-btn'),overlay=document.getElementById('fb-overlay');
  var stars=document.querySelectorAll('.fb-star');
  btn.addEventListener('click',function(){overlay.classList.add('open');});
  overlay.addEventListener('click',function(e){if(e.target===overlay)overlay.classList.remove('open');});
  document.getElementById('fb-skip').addEventListener('click',function(){overlay.classList.remove('open');});
  stars.forEach(function(s){
    s.addEventListener('click',function(){
      rating=parseInt(s.getAttribute('data-v'));
      stars.forEach(function(x){x.classList.toggle('on',parseInt(x.getAttribute('data-v'))<=rating);});
    });
  });
  document.getElementById('fb-send').addEventListener('click',function(){
    var msg=document.getElementById('fb-text').value;
    fetch('https://formspree.io/f/'+FORM_ID,{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({rating:rating,message:msg,page:window.location.pathname})
    });
    document.getElementById('fb-modal').innerHTML='<div class="fb-thanks"><span>&#10003;</span><strong>Thanks for your feedback!</strong><p style="color:#879196;font-size:13px;margin-top:0.35rem;">It means a lot.</p></div>';
    setTimeout(function(){overlay.classList.remove('open');},2000);
  });
})();
</script>"""

ASK_WIDGET_HTML = f"""
<button class="ask-launcher" id="ask-launcher" aria-label="Ask about me" title="Ask about me">
  <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" stroke="none">
    <path d="M12 2l1.6 4.8L18.4 8.4l-4.8 1.6L12 14.8l-1.6-4.8L5.6 8.4l4.8-1.6L12 2z"/>
    <path d="M19.5 14l.9 2.6 2.6.9-2.6.9-.9 2.6-.9-2.6-2.6-.9 2.6-.9.9-2.6z" opacity=".55"/>
    <path d="M5 17.5l.6 1.9 1.9.6-1.9.6L5 22.5l-.6-1.9-1.9-.6 1.9-.6L5 17.5z" opacity=".35"/>
  </svg>
</button>
<div class="ask-overlay" id="ask-overlay" role="dialog" aria-modal="true" aria-label="Ask about me">
  <div class="ask-terminal">
    <div class="ask-titlebar">
      <span class="ask-dot ask-dot-red"></span>
      <span class="ask-dot ask-dot-yellow"></span>
      <span class="ask-dot ask-dot-green"></span>
      <span class="ask-titlebar-label">ask-jay — about me</span>
      <button class="ask-close" id="ask-close" aria-label="Close">✕</button>
    </div>
    <div class="ask-body">
      <form id="ask-form">
        <div class="ask-prompt-row">
          <span class="ask-prompt-label">jay@me :~$</span>
          <textarea class="ask-input" id="ask-input" rows="1" placeholder='ask "your question here"' autocomplete="off"></textarea>
        </div>
        <div class="ask-send-row">
          <button class="ask-send-btn" id="ask-send" type="submit">Run ↵</button>
        </div>
      </form>
    </div>
    <div class="ask-output" id="ask-output"></div>
  </div>
</div>
<script>
(function(){{
  var API_URL = '{API_URL}';
  var launcher=document.getElementById('ask-launcher'),overlay=document.getElementById('ask-overlay'),
      closeBtn=document.getElementById('ask-close'),form=document.getElementById('ask-form'),
      input=document.getElementById('ask-input'),sendBtn=document.getElementById('ask-send'),
      output=document.getElementById('ask-output');
  function openModal(){{overlay.classList.add('open');document.body.style.overflow='hidden';setTimeout(function(){{input.focus();}},220);}}
  function closeModal(){{overlay.classList.remove('open');document.body.style.overflow='';}}
  launcher.addEventListener('click',openModal);
  closeBtn.addEventListener('click',closeModal);
  overlay.addEventListener('click',function(e){{if(e.target===overlay)closeModal();}});
  document.addEventListener('keydown',function(e){{if(e.key==='Escape')closeModal();}});
  input.addEventListener('input',function(){{this.style.height='auto';this.style.height=this.scrollHeight+'px';}});
  input.addEventListener('keydown',function(e){{if(e.key==='Enter'&&!e.shiftKey){{e.preventDefault();form.dispatchEvent(new Event('submit'));}}}});
  form.addEventListener('submit',function(e){{
    e.preventDefault();var q=input.value.trim();if(!q)return;
    sendBtn.disabled=true;output.className='ask-output visible';
    output.innerHTML='<p class="ask-spinner">▌ thinking…</p>';
    fetch(API_URL,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{question:q}})}})
      .then(function(r){{if(!r.ok)throw new Error('HTTP '+r.status);return r.json();}})
      .then(function(data){{
        var answer=esc(data.answer).replace(/`([^`]+)`/g,'<code>$1</code>');
        var src='';
        if(data.sources&&data.sources.length){{
          src='<div class="ask-sources-label">Sources</div><div class="ask-sources">'+
            data.sources.map(function(s){{return '<a href="'+esc(s.url)+'" target="_blank" rel="noopener">'+esc(s.title)+'</a>';}}).join('')+'</div>';
        }}
        output.innerHTML='<div class="ask-output-label">Answer</div><div class="ask-answer">'+answer+'</div>'+src;
      }})
      .catch(function(){{output.innerHTML='<p class="ask-error">Error — check your connection and try again.</p>';}})
      .finally(function(){{sendBtn.disabled=false;}});
  }});
  function esc(str){{return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}}
}})();
</script>"""

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
  <button class="nav-icon-btn" id="nav-search-btn" aria-label="Search" title="Search posts">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
  </button>
  <button class="nav-icon-btn" id="nav-theme-btn" aria-label="Toggle dark mode" title="Toggle dark mode">
    <svg id="theme-icon-moon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
    <svg id="theme-icon-sun" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="display:none"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
  </button>
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
{FEEDBACK_WIDGET_HTML}
{ASK_WIDGET_HTML}
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
<div class="search-bar-wrap" id="search-bar-wrap">
  <input id="blog-search" type="search" placeholder="Search posts…" autocomplete="off"/>
</div>
<div class="filters">
  {filter_pills}
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
{FEEDBACK_WIDGET_HTML}
{ASK_WIDGET_HTML}
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
