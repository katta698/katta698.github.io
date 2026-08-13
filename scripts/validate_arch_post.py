#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pre-publish validator for every post series on the site.

Every check here exists because the failure actually happened and was caught by
eye rather than by tooling. Run it before committing a new post:

    python scripts/validate_arch_post.py                 # every series
    python scripts/validate_arch_post.py <slug> [<slug>] # specific ones
    python scripts/validate_arch_post.py --series daily  # one series
    python scripts/validate_arch_post.py --check-links   # also fetch cited pages

Exits non-zero if any ERROR is found, so it can gate CI.

**It used to check only the Architecture Series**, which is why it is still
named `validate_arch_post.py` — the name is referenced from CLAUDE.md and from
three publishing workflows, so renaming it costs more than it gains.

That arch-only scope was a real gap rather than a cosmetic one. The
`verified_claims` evidence rule was added to stop a badge asserting a check
that never happened, and it was enforced for 19 arch posts while the daily and
weekly series — which publish far more often, and carry exactly the pricing and
quota claims the rule exists for — were never examined at all. Daily #9 shipped
with six verified claims and was silently skipped; the links were checked by
hand instead, which is the situation the validator exists to remove.

Adding a series means adding an entry to SERIES below. Anything absent from
that list is not checked by anything.
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

# Sections are validated by heading text, not element id: ids drifted across
# template revisions (id="why" became id="why-it-matters"), but the headings are
# stable and are what actually tells you a section is missing.
#
# Each series' required headings were derived from the posts already published,
# taking only headings present in *every* post of that series. Requiring a
# heading that established posts do not have would fail correct work, which is
# how a validator gets switched off.
SERIES = {
    'arch': {
        'label': 'Architecture Series',
        'file_prefix': 'arch-',
        'slug_glob': 'aws-architecture-*',
        'labels': ['AWS', 'AWS Architecture Series'],
        # Arch pages are built from a template and never rebuilt by sync_blog.py,
        # so a page can drift from its posts/ source and stay that way forever.
        'externally_built': True,
        'ref_heading': 'Official AWS Reference',
        'first_section': 'id="challenge"',
        'headings': [
            ('Business Challenge',     r'^Business Challenge$'),
            ('Architecture',           r'^Architecture$'),
            ('Why ...',                r'^Why\b'),
            ('... Decisions',          r'Decisions$'),
            ('Closing Thought',        r'^Closing Thought$'),
            ('Official AWS Reference', r'^Official AWS Reference$'),
        ],
    },
    'daily': {
        'label': 'AWS Daily Intelligence',
        'file_prefix': 'daily-',
        'slug_glob': 'aws-daily-intelligence-*',
        'labels': ['AWS', 'AWS Daily Intelligence'],
        'externally_built': False,
        'ref_heading': 'Official AWS references',
        'first_section': 'id="what-changed"',
        'headings': [
            ('Executive summary',        r'^Executive summary$'),
            ('What changed',             r'^What changed$'),
            ('Architecture',             r'^Architecture$'),
            ('Business value',           r'^Business value$'),
            ('Security considerations',  r'^Security considerations$'),
            ('Cost considerations',      r'^Cost considerations$'),
            ('Operational considerations', r'^Operational considerations$'),
            ('Tradeoffs',                r'^Tradeoffs$'),
            ('Implementation guidance',  r'^Implementation guidance$'),
            ('Best practices',           r'^Best practices$'),
            ('Who should adopt ...',     r'^Who should adopt'),
            ('Key takeaways',            r'^Key takeaways$'),
            ('Official AWS references',  r'^Official AWS references$'),
        ],
    },
    'weekly': {
        'label': 'AWS Weekly Intelligence',
        'file_prefix': 'weekly-',
        'slug_glob': 'aws-weekly-intelligence-*',
        'labels': ['AWS', 'AWS Weekly Intelligence'],
        'externally_built': False,
        'ref_heading': 'Official AWS references',
        'first_section': 'id="the-week"',
        # Deliberately only the structural sections. The domain groupings
        # ("Storage and backup", "AI and agents") vary with what AWS actually
        # shipped that week, and a quiet week is allowed to be short -- see the
        # never-repeat rules in CLAUDE.md.
        'headings': [
            ('The week in one paragraph', r'^The week in one paragraph$'),
            ('What I would act on',       r'^What I would act on$'),
            ('Official AWS references',   r'^Official AWS references$'),
        ],
    },
}

XML_SAFE_ENTITIES = {'amp', 'lt', 'gt', 'quot', 'apos'}


def series_for_slug(slug):
    """Which series does this slug belong to? None if it is not a series post."""
    for key, spec in SERIES.items():
        if slug.startswith(spec['slug_glob'].rstrip('*')):
            return key, spec
    return None, None

errors = []
warnings = []


def err(slug, msg):
    errors.append('%s: %s' % (slug, msg))


def warn(slug, msg):
    warnings.append('%s: %s' % (slug, msg))


def strip_comments(html):
    """Remove HTML comments so we only inspect what actually renders."""
    return re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)


def check_page(slug, spec):
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
    #     next one cannot. Sync-built pages get these from html_head() and were
    #     confirmed to carry all eight, so the check is applied to every series
    #     rather than only to the one that once got it wrong.
    #     og:image is intentionally not checked for a per-post
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
    for label, pattern in spec['headings']:
        if not any(re.search(pattern, h) for h in headings):
            err(slug, 'no rendered <h2> matching "%s" — section missing or '
                      'commented out' % label)

    # 4b. An empty "Next in this series" callout. The template marks it
    #     REQUIRED and the build scripts either fill it or remove the whole
    #     block; substituting an empty string leaves the heading with nothing
    #     under it, which is what arch-020 shipped. Check 4 already catches the
    #     same shape in the post-nav -- this is the other place a required
    #     element can end up present but blank.
    m = re.search(r'Next in this series</strong>\s*<p>(.*?)</p>', visible, re.DOTALL)
    if m and not m.group(1).strip():
        err(slug, 'empty "Next in this series" callout — either write the teaser '
                  'or remove the whole callout block, as the posts with no '
                  'successor do')

    # 4. Empty nav boxes (shipped once on arch-009).
    if re.search(r'class="post-nav-link (?:prev|next)"[^>]*>\s*'
                 r'<span class="post-nav-dir">[^<]*</span>\s*'
                 r'<span class="post-nav-title">\s*</span>', visible):
        err(slug, 'post-nav link with an empty title')
    if re.search(r'href="/blog//+"', visible):
        err(slug, 'post-nav link with a malformed empty slug URL')

    # 5. Wide tables need their own scroll container or the last column is
    #    unreachable on mobile. Which wrapper is valid depends on the series:
    #    arch posts bypass clean_html() so inline overflow-x survives, but every
    #    sync-built series has its inline style attributes stripped, and there
    #    the only wrapper that survives is class="table-scroll". Accepting just
    #    one of the two would flag correct posts in the other series.
    for m in re.finditer(r'<table[\s>]', visible):
        before = visible[max(0, m.start() - 300):m.start()]
        if 'overflow-x' not in before and 'table-scroll' not in before:
            warn(slug, 'a <table> is not wrapped in a scroll container '
                       '(last column clips on mobile). Use class="table-scroll" '
                       'on sync-built pages — inline styles are stripped there')
            break

    # 6. A leading <code> in the first paragraph mangles the auto-excerpt,
    #    because tag stripping does not reinsert spaces.
    body = visible.split(spec['first_section'], 1)
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
        #    Hash the text, not the raw bytes, and hash it exactly the way
        #    sync_blog.py's _css_version() does. Git checks this file out with
        #    CRLF endings on Windows while the repo — and therefore what Pages
        #    serves — stores LF. Hashing bytes off a CRLF working copy produces
        #    a value the served file never has, so this check failed on all 19
        #    arch pages at once and blamed the pages, which were correct.
        want = hashlib.md5(
            io.open(css_file, encoding='utf-8').read().encode('utf-8')
        ).hexdigest()[:8]
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


def check_source(slug, spec):
    """The posts/ file is what the RAG indexer reads."""
    pattern = '%s*.html' % spec['file_prefix']
    matches = [p for p in glob.glob(os.path.join(POSTS, pattern))
               if ('slug: %s' % slug) in io.open(p, encoding='utf-8').read()]
    if not matches:
        err(slug, 'no posts/%s source file declares slug: %s '
                  '(RAG will not index it)' % (pattern, slug))
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

    # Read labels from the parsed YAML, not a regex. The arch series writes them
    # inline (`labels: [AWS, ...]`) and the daily and weekly series write them as
    # a block sequence; a regex for one form silently skips the other, which is
    # how the label check went unenforced on every daily post ever published.
    expected = spec['labels']
    got = parsed.get('labels')
    if got is None:
        warn(slug, '%s has no labels — the series filter pill will not count it'
             % name)
    elif [str(x) for x in got] != expected:
        err(slug, '%s labels are %s, expected %s — pill counts and widgets '
                  'match on the exact string' % (name, got, expected))

    if not name.startswith(spec['file_prefix']):
        err(slug, '%s must start with "%s" — sync_blog.py decides whether to '
                  'overwrite the served page from the filename prefix'
            % (name, spec['file_prefix']))

    body = raw.split('---', 2)[2]
    check_verification(slug, name, fm, parsed, body, spec)

    # The badge is rendered from the posts/ front matter into the served page.
    # Arch pages are never rebuilt by sync_blog.py, so the two can drift: a
    # badge removed from the source stays visible on the live page forever.
    page = os.path.join(BLOG, slug, 'index.html')
    if os.path.isfile(page):
        served = io.open(page, encoding='utf-8').read()
        shown = 'verified-badge' in served
        if bool(parsed.get('verified')) != shown:
            fix = ('Arch pages are not rebuilt by sync, so fix '
                   'blog/%s/index.html by hand.' % slug
                   if spec['externally_built'] else
                   'This page is sync-built, so run scripts/sync_blog.py — the '
                   'served page is stale relative to posts/.')
            err(slug, 'badge mismatch: posts/%s %s a "verified:" date but the '
                      'served page %s a badge. %s'
                % (name, 'has' if parsed.get('verified') else 'has no',
                   'shows' if shown else 'shows none', fix))


AWS_DOC_HOSTS = ('docs.aws.amazon.com', 'aws.amazon.com')
STALE_DAYS = 180
# A missing docs.aws.amazon.com page returns ~1 KB; a real article, tens of KB.
DOCS_SHELL_BYTES = 5000


def check_verification(slug, name, fm, parsed, body, spec):
    """The verification badge must be backed by evidence, not by a build flag.

    CLAUDE.md forbids auto-stamping `verified:`, because the badge asserts that
    a human checked this post's figures on a stated date. Nothing enforced that:
    every build script carried a hardcoded `VERIFIED = '<date>'` and stamped it
    unconditionally, which is precisely the thing the rule prohibits. Posts #15
    to #19 were stamped on five consecutive days for that reason alone, and #18
    shipped with a factual error under a badge claiming it had been checked --
    it mixed current write pricing with pre-November-2024 read pricing and
    concluded reads and writes broke even at different utilisations when they
    break even at the same one.

    A date alone cannot be falsified by a script. A list of claims each paired
    with the AWS page it came from can be: the URLs must resolve, must be AWS's
    own documentation, and must also appear in the post's Official AWS Reference
    section so a reader can repeat the check. Writing that list is work a build
    script cannot fake, which is the whole point.
    """
    import datetime

    verified = parsed.get('verified')
    claims = parsed.get('verified_claims')

    # A post with vendor figures and no badge is fine -- the badge is opt-in and
    # its absence is honest. A badge with no evidence is not.
    if not verified:
        if claims:
            err(slug, '%s has verified_claims but no "verified:" date' % name)
        return

    if not isinstance(verified, (str, datetime.date)):
        err(slug, '%s "verified:" must be a quoted date, got %r' % (name, verified))
        return
    try:
        vdate = (verified if isinstance(verified, datetime.date)
                 else datetime.datetime.strptime(str(verified).strip(), '%Y-%m-%d').date())
    except ValueError:
        err(slug, '%s "verified: %s" is not YYYY-MM-DD' % (name, verified))
        return

    today = datetime.date.today()
    if vdate > today:
        err(slug, '%s claims verification on %s, which is in the future' % (name, vdate))
    age = (today - vdate).days
    if age > STALE_DAYS:
        warn(slug, '%s was verified %d days ago (%s). Pricing and quotas move; '
                   're-check before the figures are quoted anywhere.' % (name, age, vdate))

    if not isinstance(claims, list) or len(claims) < 2:
        err(slug, '%s carries a verification badge but lists fewer than two '
                  'verified_claims. The badge tells readers a human checked this '
                  "post's figures -- list what was checked and where, or drop the "
                  'badge.' % name)
        return

    # Everything cited must also be reachable from the post itself. The heading
    # text differs by series ("Official AWS Reference" in arch, "Official AWS
    # references" in daily and weekly); splitting on the wrong one yields the
    # entire body, which makes this check pass for any URL mentioned anywhere.
    ref_heading = spec['ref_heading']
    if ref_heading not in body:
        warn(slug, '%s has no "%s" heading in its body — cannot confirm cited '
                   'sources are reachable from the post' % (name, ref_heading))
        ref = ''
    else:
        ref = body.split(ref_heading, 1)[-1]

    for i, c in enumerate(claims, 1):
        if not isinstance(c, dict) or not c.get('claim') or not c.get('source'):
            err(slug, '%s verified_claims[%d] needs both "claim:" and "source:"' % (name, i))
            continue
        src = str(c['source']).strip()
        if not src.startswith('https://'):
            err(slug, '%s verified_claims[%d] source is not https: %s' % (name, i, src))
            continue
        host = src.split('/')[2]
        if not any(host == h or host.endswith('.' + h) for h in AWS_DOC_HOSTS):
            err(slug, '%s verified_claims[%d] cites %s. Verification means AWS\'s own '
                      'documentation, not a blog quoting it secondhand.' % (name, i, host))
            continue
        if src.rstrip('/') not in ref.replace('&amp;', '&'):
            warn(slug, '%s verified_claims[%d] cites %s, which is not in the post\'s '
                       'Official AWS Reference section -- a reader cannot repeat the '
                       'check' % (name, i, src))

    if CHECK_LINKS:
        _check_links_resolve(slug, name, claims)


def _check_links_resolve(slug, name, claims):
    """Opt-in (--check-links): confirm every cited page still exists.

    Off by default so the validator stays usable offline and in CI without
    network egress, but run it before publishing: a source that has moved means
    the figure quoted from it may have moved with it.

    Status codes alone are not enough. `aws.amazon.com` 404s honestly, but
    `docs.aws.amazon.com` is client-side routed and answers **HTTP 200 for
    pages that do not exist** -- it returns a ~1 KB shell whose <title> is just
    the service name, and the real article is fetched by script afterwards. A
    HEAD request therefore passes every dead docs link. So fetch the body and
    judge it: a real article is tens of KB and its title names the article.
    """
    import urllib.request
    import urllib.error
    seen = set()
    for c in claims:
        if not isinstance(c, dict):
            continue
        src = str(c.get('source', '')).strip()
        if not src.startswith('https://') or src in seen:
            continue
        seen.add(src)
        req = urllib.request.Request(src, headers={
            'User-Agent': 'Mozilla/5.0 (validate_arch_post.py)'})
        try:
            resp = urllib.request.urlopen(req, timeout=25)
            code, body = resp.getcode(), resp.read(80000)
        except urllib.error.HTTPError as exc:
            err(slug, '%s cites %s which returns HTTP %d' % (name, src, exc.code))
            continue
        except Exception as exc:
            warn(slug, '%s could not reach %s (%s)' % (name, src, exc))
            continue
        if code >= 400:
            err(slug, '%s cites %s which returns HTTP %d' % (name, src, code))
        elif 'docs.aws.amazon.com' in src and len(body) < DOCS_SHELL_BYTES:
            err(slug, '%s cites %s which returns a %d-byte shell, not an article. '
                      'docs.aws.amazon.com answers 200 for missing pages, so this '
                      'link is dead -- the page moved.' % (name, src, len(body)))


CHECK_LINKS = False


def main():
    global CHECK_LINKS
    args = sys.argv[1:]
    CHECK_LINKS = '--check-links' in args

    only = None
    if '--series' in args:
        i = args.index('--series')
        if i + 1 >= len(args):
            print('--series needs a value: %s' % ', '.join(sorted(SERIES)))
            return 2
        only = args[i + 1]
        if only not in SERIES:
            print('unknown series %r. Known: %s' % (only, ', '.join(sorted(SERIES))))
            return 2
        args = args[:i] + args[i + 2:]

    slugs = [a for a in args if not a.startswith('--')]
    if not slugs:
        for key, spec in sorted(SERIES.items()):
            if only and key != only:
                continue
            slugs += sorted(os.path.basename(os.path.dirname(p)) for p in
                            glob.glob(os.path.join(BLOG, spec['slug_glob'], 'index.html')))
    if not slugs:
        print('No posts found%s.' % (' for series %s' % only if only else ''))
        return 0

    counts = {}
    for slug in slugs:
        key, spec = series_for_slug(slug)
        if spec is None:
            # Not a hard error: the blog holds standalone pages that belong to
            # no series and have no template to conform to.
            warn(slug, 'does not match any series in SERIES — not checked')
            continue
        counts[key] = counts.get(key, 0) + 1
        check_page(slug, spec)
        check_source(slug, spec)

    for w in warnings:
        print('WARN  %s' % w)
    for e in errors:
        print('ERROR %s' % e)

    summary = ', '.join('%d %s' % (n, SERIES[k]['label'])
                        for k, n in sorted(counts.items())) or 'none'
    print('\nChecked %d post(s) [%s]: %d error(s), %d warning(s)'
          % (sum(counts.values()), summary, len(errors), len(warnings)))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
