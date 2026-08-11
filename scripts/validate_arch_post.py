#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pre-publish validator for Architecture Series posts.

Every check here exists because the failure actually happened and was caught by
eye rather than by tooling. Run it before committing a new post:

    python scripts/validate_arch_post.py                 # all arch posts
    python scripts/validate_arch_post.py <slug> [<slug>] # specific ones

Exits non-zero if any ERROR is found, so it can gate CI.
"""
import io
import os
import hashlib
import re
import sys
import glob
import xml.dom.minidom

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOG = os.path.join(ROOT, 'blog')
POSTS = os.path.join(ROOT, 'posts')

# Validated by heading text, not element id: section ids drifted across template
# revisions (id="why" became id="why-it-matters"), but the headings are stable
# and are what actually tells you a section is missing.
REQUIRED_HEADINGS = [
    ('Business Challenge',    r'^Business Challenge$'),
    ('Architecture',          r'^Architecture$'),
    ('Why ...',               r'^Why\b'),
    ('... Decisions',         r'Decisions$'),
    ('Closing Thought',       r'^Closing Thought$'),
    ('Official AWS Reference', r'^Official AWS Reference$'),
]
EXPECTED_LABELS = ['AWS', 'AWS Architecture Series']
XML_SAFE_ENTITIES = {'amp', 'lt', 'gt', 'quot', 'apos'}

errors = []
warnings = []


def err(slug, msg):
    errors.append('%s: %s' % (slug, msg))


def warn(slug, msg):
    warnings.append('%s: %s' % (slug, msg))


def strip_comments(html):
    """Remove HTML comments so we only inspect what actually renders."""
    return re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)


def check_page(slug):
    path = os.path.join(BLOG, slug, 'index.html')
    if not os.path.isfile(path):
        err(slug, 'served page missing: blog/%s/index.html' % slug)
        return
    html = io.open(path, encoding='utf-8').read()

    # 1. Unbalanced comments. A missing '-->' silently swallows the whole body.
    opens, closes = html.count('<!--'), html.count('-->')
    if opens != closes:
        err(slug, 'unbalanced HTML comments (%d open, %d close) — '
                  'body may be commented out' % (opens, closes))

    # 1b. Social preview tags. Arch pages carry their own <head> and are never
    #     rebuilt by sync_blog.py, so they do not inherit the og:*/twitter:*
    #     tags that html_head() emits for every other series. Arch #14 shipped
    #     without them and needed a follow-up commit; this check is here so the
    #     next one cannot. og:image is intentionally not checked for a per-post
    #     value — it points at the site image everywhere, because LinkedIn, X
    #     and Facebook do not render SVG and the diagrams are all SVG.
    for tag in ('og:type', 'og:title', 'og:description', 'og:url', 'og:image',
                'twitter:card', 'twitter:title', 'twitter:description'):
        if tag not in html:
            err(slug, 'missing social preview tag %s — a shared link will '
                      'render as a bare URL (see "Social preview tags on arch '
                      'pages" in CLAUDE.md)' % tag)

    og_title = re.search(r'<meta property="og:title" content="([^"]*)"', html)
    if og_title and og_title.group(1).strip().endswith('| Jayanth Katta Blog'):
        err(slug, 'og:title still carries the " | Jayanth Katta Blog" suffix — '
                  'that belongs in <title>, not in the share card')

    og_url = re.search(r'<meta property="og:url" content="([^"]*)"', html)
    canon = re.search(r'<link rel="canonical" href="([^"]*)"', html)
    if og_url and canon and og_url.group(1) != canon.group(1):
        err(slug, 'og:url (%s) does not match canonical (%s) — a copied page '
                  'kept the previous post\'s URL'
                  % (og_url.group(1), canon.group(1)))

    visible = strip_comments(html)

    # 2. Unreplaced template placeholders.
    for ph in sorted(set(re.findall(r'\{\{[A-Z_0-9]+\}\}', visible))):
        err(slug, 'unresolved placeholder %s' % ph)

    # 3. Every section must survive comment-stripping, i.e. actually render.
    #    (This is what catches a body swallowed by an unclosed comment.)
    headings = [re.sub(r'\s+', ' ', h).strip()
                for h in re.findall(r'<h2>(.*?)</h2>', visible, re.DOTALL)]
    for label, pattern in REQUIRED_HEADINGS:
        if not any(re.search(pattern, h) for h in headings):
            err(slug, 'no rendered <h2> matching "%s" — section missing or '
                      'commented out' % label)

    # 4. Empty nav boxes (shipped once on arch-009).
    if re.search(r'class="post-nav-link (?:prev|next)"[^>]*>\s*'
                 r'<span class="post-nav-dir">[^<]*</span>\s*'
                 r'<span class="post-nav-title">\s*</span>', visible):
        err(slug, 'post-nav link with an empty title')
    if re.search(r'href="/blog//+"', visible):
        err(slug, 'post-nav link with a malformed empty slug URL')

    # 5. Wide tables need their own scroll container or the last column is
    #    unreachable on mobile.
    for m in re.finditer(r'<table[\s>]', visible):
        before = visible[max(0, m.start() - 300):m.start()]
        if 'overflow-x' not in before:
            warn(slug, 'a <table> is not wrapped in an overflow-x container '
                       '(last column clips on mobile)')
            break

    # 6. A leading <code> in the first paragraph mangles the auto-excerpt,
    #    because tag stripping does not reinsert spaces.
    body = visible.split('id="challenge"', 1)
    if len(body) > 1:
        first_p = re.search(r'<p>(.*?)</p>', body[1], re.DOTALL)
        if first_p and '<code>' in first_p.group(1):
            warn(slug, 'first paragraph contains <code> — auto-excerpt will '
                       'run words together on the home page widget')

    # 7. Referenced diagrams must exist and be valid XML.
    for src in re.findall(r'<img[^>]+src="(/blog/assets/diagrams/[^"]+)"', visible):
        check_svg(slug, src)

    # 8. Images need alt text.
    for tag in re.findall(r'<img[^>]*>', visible):
        if 'alt=' not in tag:
            err(slug, 'an <img> is missing alt text')

    # 9. The cache-busting token must match the stylesheet it claims to name.
    #    sync_blog.py stamps sync-built pages with md5(blog.css)[:8] and never
    #    touches arch pages, so an arch page's token only changes when whatever
    #    built it supplied a fresh one. The template used to hard-code a literal
    #    hash, which meant every arch post copied one frozen value forward and
    #    all 18 pages drifted from the real stylesheet together.
    #
    #    Nothing visibly breaks when it drifts — the query string only varies
    #    the cache key, it does not select a file, so a stale token still serves
    #    the current CSS. That is exactly why this needs a check rather than an
    #    eye: it is invisible until something (a long max-age, a service worker)
    #    starts honouring the token, at which point it pins stale CSS for good.
    css_file = os.path.join(BLOG, 'assets', 'blog.css')
    if os.path.isfile(css_file):
        want = hashlib.md5(io.open(css_file, 'rb').read()).hexdigest()[:8]
        m = re.search(r'blog\.css\?v=([0-9a-zA-Z]+)', html)
        if not m:
            warn(slug, 'no cache-busting token on blog.css')
        elif m.group(1) != want:
            err(slug, 'blog.css?v=%s does not match the current stylesheet '
                      '(md5 is %s) — re-stamp the page' % (m.group(1), want))

    return html


def check_svg(slug, src):
    path = os.path.join(ROOT, src.lstrip('/'))
    if not os.path.isfile(path):
        err(slug, 'diagram not found: %s' % src)
        return
    raw = io.open(path, encoding='utf-8').read()

    # SVG is XML: HTML named entities are undefined and kill the whole render.
    bad = sorted({e for e in re.findall(r'&([a-zA-Z][a-zA-Z0-9]*);', raw)
                  if e not in XML_SAFE_ENTITIES})
    if bad:
        err(slug, '%s uses HTML named entities invalid in XML: %s '
                  '(use numeric, e.g. &#8212;)' % (src, ', '.join('&%s;' % b for b in bad)))

    try:
        xml.dom.minidom.parse(path)
    except Exception as exc:
        err(slug, '%s is not valid XML: %s' % (src, exc))

    # Responsive sizing rule from CLAUDE.md.
    head = raw[:400]
    if 'width:100%' not in head.replace(' ', ''):
        warn(slug, '%s should use style="width:100%%;max-width:Npx"' % src)

    # Text that runs off the canvas. Delegated to validate_diagrams.py rather
    # than duplicated, so the width estimation lives in one place — and so this
    # runs as part of the normal pre-publish check instead of being a separate
    # command nobody remembers.
    try:
        import validate_diagrams as vd
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import validate_diagrams as vd
    before_e, before_w = len(vd.errors), len(vd.warnings)
    vd.check(path)
    for msg in vd.errors[before_e:]:
        err(slug, msg)
    for msg in vd.warnings[before_w:]:
        warn(slug, msg)


def check_source(slug):
    """The posts/ file is what the RAG indexer reads."""
    matches = [p for p in glob.glob(os.path.join(POSTS, 'arch-*.html'))
               if ('slug: %s' % slug) in io.open(p, encoding='utf-8').read()]
    if not matches:
        err(slug, 'no posts/arch-*.html source file declares slug: %s '
                  '(RAG will not index it)' % slug)
        return
    raw = io.open(matches[0], encoding='utf-8').read()
    name = os.path.basename(matches[0])

    if not raw.startswith('---'):
        err(slug, '%s has no YAML front matter' % name)
        return
    fm = raw.split('---', 2)[1]

    # Parse it the way sync_blog.py does. Front matter that looks fine to a
    # regex can still fail YAML — a title containing double quotes inside a
    # double-quoted scalar is the easy way in — and sync_blog.py responds by
    # skipping the post with a console note rather than an error. The post's
    # page still builds, so nothing looks broken; it is simply absent from the
    # index, the pill counts, posts.json, rss.xml and the RAG index.
    try:
        import yaml
        parsed = yaml.safe_load(fm)
    except Exception as exc:
        detail = str(exc).splitlines()[0]
        err(slug, '%s front matter is not valid YAML (%s) — sync_blog.py will '
                  'skip this post silently' % (name, detail))
        return
    if not isinstance(parsed, dict) or not parsed.get('title') or not parsed.get('date'):
        err(slug, '%s front matter parses but has no usable title/date — '
                  'sync_blog.py will skip this post silently' % name)
        return

    for field in ('title', 'date', 'slug', 'labels'):
        if not re.search(r'^%s:' % field, fm, re.MULTILINE):
            # title/date are hard requirements; sync_blog silently skips without them
            (err if field in ('title', 'date') else warn)(
                slug, '%s missing "%s:" front matter' % (name, field))

    m = re.search(r'^labels:\s*\[(.*?)\]', fm, re.MULTILINE)
    if m:
        got = [x.strip().strip('"\'') for x in m.group(1).split(',')]
        if got != EXPECTED_LABELS:
            err(slug, '%s labels are %s, expected %s — pill counts and widgets '
                      'match on the exact string' % (name, got, EXPECTED_LABELS))

    if not name.startswith('arch-'):
        err(slug, '%s must start with "arch-" or sync_blog.py will overwrite '
                  'the served page' % name)


def main():
    slugs = sys.argv[1:]
    if not slugs:
        slugs = sorted(os.path.basename(os.path.dirname(p))
                       for p in glob.glob(os.path.join(BLOG, 'aws-architecture-*', 'index.html')))
    if not slugs:
        print('No Architecture Series posts found.')
        return 0

    for slug in slugs:
        check_page(slug)
        check_source(slug)

    for w in warnings:
        print('WARN  %s' % w)
    for e in errors:
        print('ERROR %s' % e)

    print('\nChecked %d post(s): %d error(s), %d warning(s)'
          % (len(slugs), len(errors), len(warnings)))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
