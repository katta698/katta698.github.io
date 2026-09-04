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
# The lab structure, shared by all three clouds. Measured, not chosen: these are
# exactly the sections present in every AWS lab from week 8 and in GCP #1 and
# Azure #1. The em-dash subtitles ("Why - The Problem This Solves") vary, so the
# patterns anchor on the opening word only.
LAB_HEADINGS = [
    ('Why',                  r'^Why\b'),
    ('What You Need to Know', r'^What You Need to Know\b'),
    ('Architecture',         r'^Architecture\b'),
    ('How We Built It',      r'^How We Built It\b'),
    ('Challenges',           r'^Challenges\b'),
    ('Security',             r'^Security\b'),
    ('Cost',                 r'^Cost\b'),
    ('Cleanup',              r'^Cleanup\b'),
    ('References',           r'^References\b'),
    ('Key Takeaways',        r'^Key Takeaways\b'),
]

SERIES = {
    'arch': {
        'label': 'Architecture Series',
        'requires_diagram': True,
        'file_prefix': 'arch-',
        'slug_glob': 'aws-architecture-*',
        'labels': ['AWS', 'AWS Architecture Series'],
        # Arch pages are built from a template and never rebuilt by sync_blog.py,
        # so a page can drift from its posts/ source and stay that way forever.
        'externally_built': True,
        'ref_heading': 'Official AWS Reference',
        'first_section': 'id="challenge"',
        'vendor': 'AWS',
        'doc_hosts': ('docs.aws.amazon.com', 'aws.amazon.com'),
        # Hosts that answer HTTP 200 for pages that do not exist. See
        # _check_links_resolve.
        'shell_hosts': ('docs.aws.amazon.com',),
        'headings': [
            ('Business Challenge',     r'^Business Challenge$'),
            ('Architecture',           r'^Architecture$'),
            ('Why ...',                r'^Why\b'),
            ('... Decisions',          r'Decisions$'),
            ('Closing Thought',        r'^Closing Thought$'),
            ('Official AWS Reference', r'^Official AWS Reference$'),
        ],
    },
    'az': {
        'label': 'Azure Architecture Series',
        'requires_diagram': True,
        'file_prefix': 'az-',
        'slug_glob': 'azure-architecture-*',
        'labels': ['Azure', 'Azure Architecture Series'],
        # Same deal as arch: custom-built pages, never rebuilt by sync_blog.py.
        'externally_built': True,
        'ref_heading': 'Official Azure Reference',
        'first_section': 'id="challenge"',
        'vendor': 'Microsoft',
        'doc_hosts': ('learn.microsoft.com', 'azure.microsoft.com'),
        # Measured 2026-08-14: both Microsoft hosts return an honest HTTP 404
        # for a missing page, unlike docs.aws.amazon.com. No body-size heuristic
        # is needed, and applying one would be guesswork.
        'shell_hosts': (),
        'headings': [
            ('Business Challenge',       r'^Business Challenge$'),
            ('Architecture',             r'^Architecture$'),
            ('Why ...',                  r'^Why\b'),
            ('... Decisions',            r'Decisions$'),
            ('Closing Thought',          r'^Closing Thought$'),
            ('Official Azure Reference', r'^Official Azure Reference$'),
        ],
    },
    'gcp': {
        'label': 'GCP Architecture Series',
        'requires_diagram': True,
        'file_prefix': 'gcp-',
        'slug_glob': 'gcp-architecture-*',
        'labels': ['GCP', 'GCP Architecture Series'],
        # Same deal as arch and az: custom-built pages, never rebuilt by
        # sync_blog.py.
        'externally_built': True,
        'ref_heading': 'Official Google Cloud Reference',
        'first_section': 'id="challenge"',
        'vendor': 'Google Cloud',
        # Two hosts for one vendor, and not for the reason AWS has two.
        # Measured 2026-08-14 while verifying gcp-001: cloud.google.com/*/docs/*
        # answers 301 Moved Permanently to docs.cloud.google.com, which is where
        # the documentation now actually lives. Marketing and pricing pages stay
        # on cloud.google.com. Both are allowed, because a 301 still resolves and
        # older links are worth keeping citable -- but prefer the docs host when
        # writing a claim, since that is the URL a reader lands on.
        'doc_hosts': ('cloud.google.com', 'docs.cloud.google.com'),
        # This series' badge carries the publish date (see CLAUDE.md), so
        # check_verification enforces verified == published. AWS and Azure
        # deliberately allow verified < published and must not set this.
        'badge_is_publish_date': True,
        # Measured 2026-08-14 against two known-bad URLs on each host
        # (/resource-manager/docs/this-page-does-not-exist-xyz123 and
        # /nonsense-xyz123): both return an honest HTTP 404, unlike
        # docs.aws.amazon.com, which answers 200 with a ~1 KB shell. So the
        # body-size heuristic is not needed here and is not guessed at.
        'shell_hosts': (),
        'headings': [
            ('Business Challenge',              r'^Business Challenge$'),
            ('Architecture',                    r'^Architecture$'),
            ('Why ...',                         r'^Why\b'),
            ('... Decisions',                   r'Decisions$'),
            ('Closing Thought',                 r'^Closing Thought$'),
            ('Official Google Cloud Reference', r'^Official Google Cloud Reference$'),
        ],
    },
    'gcpweekly': {
        'label': 'GCP Weekly Intelligence',
        # NOT "gcp-weekly-". `externally_built` in sync_blog.py matches the
        # prefix tuple ("arch-", "az-", "gcp-"), so a file named gcp-weekly-001
        # would be treated as a custom-built architecture page and its served
        # page would never be generated at all. "gcpweekly-" clears that check
        # because the fourth character is not a hyphen. Do not "tidy" it.
        'file_prefix': 'gcpweekly-',
        'slug_glob': 'gcp-weekly-intelligence-*',
        'labels': ['GCP', 'GCP Weekly Intelligence'],
        'externally_built': False,
        'ref_heading': 'Official Google Cloud references',
        'first_section': 'id="the-week"',
        'vendor': 'Google Cloud',
        'doc_hosts': ('cloud.google.com', 'docs.cloud.google.com'),
        'shell_hosts': (),
        # Structural sections only, like the AWS weekly series. The domain
        # groupings vary with what actually shipped, and a quiet week is allowed
        # to be short.
        'headings': [
            ('The week in one paragraph',        r'^The week in one paragraph$'),
            ('What I would act on',              r'^What I would act on$'),
            ('Official Google Cloud references', r'^Official Google Cloud references$'),
        ],
    },
    'azweekly': {
        'label': 'Azure Weekly Intelligence',
        # NOT "az-weekly-". `externally_built` in sync_blog.py matches the
        # prefix tuple ("arch-", "az-", "gcp-"), so a file named az-weekly-001
        # would be treated as a custom-built architecture page and its served
        # page would never be generated at all. "azw-" clears that check
        # because the third character is not a hyphen. Do not "tidy" it.
        'file_prefix': 'azw-',
        'slug_glob': 'azure-weekly-intelligence-*',
        'labels': ['Azure', 'Azure Weekly Intelligence'],
        'externally_built': False,
        'ref_heading': 'Official Azure references',
        'first_section': 'id="week"',
        'vendor': 'Microsoft',
        # msrc.microsoft.com is allowed here and nowhere else. A roundup carries
        # CVEs, and the update guide is Microsoft's own authority on them; the
        # architecture series has no reason to cite it.
        'doc_hosts': ('learn.microsoft.com', 'azure.microsoft.com',
                      'msrc.microsoft.com'),
        'shell_hosts': (),
        # Structural sections only, like the AWS weekly series. The domain
        # groupings vary with what actually shipped, and a quiet week is
        # allowed to be short.
        'headings': [
            ('The week in one paragraph', r'^The week in one paragraph$'),
            ('What I would act on',       r'^What I would act on$'),
            ('Official Azure references', r'^Official Azure references$'),
        ],
    },
    'daily': {
        'label': 'AWS Daily Intelligence',
        'requires_diagram': True,
        'file_prefix': 'daily-',
        'slug_glob': 'aws-daily-intelligence-*',
        'labels': ['AWS', 'AWS Daily Intelligence'],
        'externally_built': False,
        'ref_heading': 'Official AWS references',
        'first_section': 'id="what-changed"',
        'vendor': 'AWS',
        'doc_hosts': ('docs.aws.amazon.com', 'aws.amazon.com'),
        'shell_hosts': ('docs.aws.amazon.com',),
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
        'vendor': 'AWS',
        'doc_hosts': ('docs.aws.amazon.com', 'aws.amazon.com'),
        'shell_hosts': ('docs.aws.amazon.com',),
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

    # --- The three lab series --------------------------------------------
    #
    # These are the only series that cannot be told apart by filename. AWS labs
    # are week-NN-*, and GCP and Azure both began at week-01-*, so all three
    # share one slug namespace -- `_week_num()` in sync_blog.py has the same
    # problem and numbers them all off `week-(\d+)`. So they are resolved by
    # their `series_label`, which is the only thing that separates them.
    #
    # `labels_subset` because weeks 1-7 came across from Blogger carrying
    # legacy labels (WeeklySeries, Platform Engineering, Serverless) alongside
    # the series one. Requiring an exact list would fail seven correct posts,
    # and a validator that fails correct work is a validator that gets
    # switched off.
    #
    # `min_week` for the same reason, harder. Measured across all 17 posts: AWS
    # weeks 8-15 share exactly the ten sections below, and so do GCP #1 and
    # Azure #1 -- but weeks 1-7 share *nothing* with them, being Blogger-era
    # posts with an entirely different structure. So the section rules apply
    # from week 8 on AWS and from week 1 on the two new series. Editing the
    # published seven is Jay's call, not a silent cleanup.
    'awslab': {
        'label': 'AWS Weekly Lab',
        'series_label': 'AWS Weekly Lab',
        # Not required, though every lab does have one. The check demands the
        # house standard -- a standalone SVG file referenced with <img> -- and
        # all 17 lab posts across all three clouds use inline <svg> instead,
        # including the two written this week. Enforcing it would fail every
        # lab post ever published, which is how a validator gets switched off.
        # The divergence is real and worth closing; doing it by failing correct
        # work is not the way.
        'requires_diagram': False,
        'file_prefix': 'week-',
        'slug_glob': 'week-*',
        'labels': ['AWS', 'Terraform', 'AWS Weekly Lab'],
        'labels_subset': True,
        'min_week': 8,
        'externally_built': False,
        'ref_heading': 'References',
        'first_section': '<h2>',
        'vendor': 'AWS',
        'doc_hosts': ('docs.aws.amazon.com', 'aws.amazon.com'),
        'shell_hosts': ('docs.aws.amazon.com',),
        # First-party docs for the *tooling* this series is explicitly about.
        # Every lab series carries 'Terraform' in its own labels, and a lab that
        # wires HCP Terraform to a cloud necessarily makes claims about both
        # products: TFC_GCP_PROVIDER_AUTH and terraform_run_phase are HashiCorp's
        # identifiers, and no amount of Google documentation describes them.
        # Dropping such a claim would leave those names printed in the post with
        # nothing behind them, which is worse than citing the vendor that owns
        # them -- the badge would cover fewer of the post's figures, not more.
        #
        # This is still first-party documentation. It is deliberately a separate
        # key from doc_hosts so that the architecture and intelligence series
        # cannot inherit it, and so that adding a host here is a visible decision
        # rather than a quiet widening of what "the vendor's own docs" means.
        # Probed 2026-08-28: developer.hashicorp.com returns a real HTTP 404 for
        # a missing page, so it needs no shell_hosts entry.
        'tool_doc_hosts': ('developer.hashicorp.com',),
        'headings': LAB_HEADINGS,
    },
    'azlab': {
        'label': 'Azure Weekly Lab',
        'series_label': 'Azure Weekly Lab',
        # Not required, though every lab does have one. The check demands the
        # house standard -- a standalone SVG file referenced with <img> -- and
        # all 17 lab posts across all three clouds use inline <svg> instead,
        # including the two written this week. Enforcing it would fail every
        # lab post ever published, which is how a validator gets switched off.
        # The divergence is real and worth closing; doing it by failing correct
        # work is not the way.
        'requires_diagram': False,
        'file_prefix': 'week-',
        'slug_glob': 'week-*',
        'labels': ['Azure', 'Terraform', 'Azure Weekly Lab'],
        'labels_subset': True,
        'min_week': 1,
        'externally_built': False,
        'ref_heading': 'References',
        'first_section': '<h2>',
        'vendor': 'Azure',
        'doc_hosts': ('learn.microsoft.com', 'azure.microsoft.com'),
        'shell_hosts': (),
        # First-party docs for the *tooling* this series is explicitly about.
        # Every lab series carries 'Terraform' in its own labels, and a lab that
        # wires HCP Terraform to a cloud necessarily makes claims about both
        # products: TFC_GCP_PROVIDER_AUTH and terraform_run_phase are HashiCorp's
        # identifiers, and no amount of Google documentation describes them.
        # Dropping such a claim would leave those names printed in the post with
        # nothing behind them, which is worse than citing the vendor that owns
        # them -- the badge would cover fewer of the post's figures, not more.
        #
        # This is still first-party documentation. It is deliberately a separate
        # key from doc_hosts so that the architecture and intelligence series
        # cannot inherit it, and so that adding a host here is a visible decision
        # rather than a quiet widening of what "the vendor's own docs" means.
        # Probed 2026-08-28: developer.hashicorp.com returns a real HTTP 404 for
        # a missing page, so it needs no shell_hosts entry.
        'tool_doc_hosts': ('developer.hashicorp.com',),
        'headings': LAB_HEADINGS,
    },
    'gcplab': {
        'label': 'GCP Weekly Lab',
        'series_label': 'GCP Weekly Lab',
        # Not required, though every lab does have one. The check demands the
        # house standard -- a standalone SVG file referenced with <img> -- and
        # all 17 lab posts across all three clouds use inline <svg> instead,
        # including the two written this week. Enforcing it would fail every
        # lab post ever published, which is how a validator gets switched off.
        # The divergence is real and worth closing; doing it by failing correct
        # work is not the way.
        'requires_diagram': False,
        'file_prefix': 'week-',
        'slug_glob': 'week-*',
        'labels': ['GCP', 'Terraform', 'GCP Weekly Lab'],
        'labels_subset': True,
        'min_week': 1,
        'externally_built': False,
        'ref_heading': 'References',
        'first_section': '<h2>',
        'vendor': 'Google Cloud',
        'doc_hosts': ('cloud.google.com', 'docs.cloud.google.com'),
        'shell_hosts': (),
        # First-party docs for the *tooling* this series is explicitly about.
        # Every lab series carries 'Terraform' in its own labels, and a lab that
        # wires HCP Terraform to a cloud necessarily makes claims about both
        # products: TFC_GCP_PROVIDER_AUTH and terraform_run_phase are HashiCorp's
        # identifiers, and no amount of Google documentation describes them.
        # Dropping such a claim would leave those names printed in the post with
        # nothing behind them, which is worse than citing the vendor that owns
        # them -- the badge would cover fewer of the post's figures, not more.
        #
        # This is still first-party documentation. It is deliberately a separate
        # key from doc_hosts so that the architecture and intelligence series
        # cannot inherit it, and so that adding a host here is a visible decision
        # rather than a quiet widening of what "the vendor's own docs" means.
        # Probed 2026-08-28: developer.hashicorp.com returns a real HTTP 404 for
        # a missing page, so it needs no shell_hosts entry.
        'tool_doc_hosts': ('developer.hashicorp.com',),
        'headings': LAB_HEADINGS,
    },
}


# Which lab series does a slug belong to? Filename cannot say -- see the comment
# on 'awslab' above -- so read the label out of the posts/ source. Built once and
# cached; the alternative is re-reading 140 files per lookup.
_LAB_LABEL_CACHE = None


def lab_series_for_slug(slug):
    global _LAB_LABEL_CACHE
    if _LAB_LABEL_CACHE is None:
        _LAB_LABEL_CACHE = {}
        for path in glob.glob(os.path.join(POSTS, 'week-*.html')):
            try:
                raw = io.open(path, encoding='utf-8').read()
            except OSError:
                continue
            m = re.search(r'^slug:\s*(\S+)', raw, re.M)
            if not m:
                continue
            for key in ('awslab', 'azlab', 'gcplab'):
                if SERIES[key]['series_label'] in raw:
                    _LAB_LABEL_CACHE[m.group(1)] = key
                    break
    return _LAB_LABEL_CACHE.get(slug)


def week_number(slug):
    """The lab week, from the slug. None if the slug carries no number."""
    m = re.match(r'week-0*(\d+)', slug)
    return int(m.group(1)) if m else None

XML_SAFE_ENTITIES = {'amp', 'lt', 'gt', 'quot', 'apos'}


def series_for_slug(slug):
    """Which series does this slug belong to? None if it is not a series post.

    The three lab series all match slug_glob 'week-*', so a prefix test cannot
    separate them and would hand every lab post to whichever of the three came
    first in the dict. They are resolved by label instead.
    """
    if slug.startswith('week-'):
        key = lab_series_for_slug(slug)
        return (key, SERIES[key]) if key else (None, None)
    for key, spec in SERIES.items():
        if spec.get('series_label'):
            continue
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
    # <h2[^>]*>, not <h2>. Every page on the site used a bare tag until the
    # first Azure Weekly Lab shipped with <h2 id="architecture">, at which point
    # all ten of its sections became invisible to this check and it reported the
    # post as having no sections at all. A heading is a heading whether or not
    # it carries an anchor id.
    headings = [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', h)).strip()
                for h in re.findall(r'<h2[^>]*>(.*?)</h2>', visible, re.DOTALL)]
    # A series can declare that its section rules only start from a given post.
    # AWS labs 1-7 predate the current structure and share no heading with it;
    # requiring the modern sections would fail seven published posts that are
    # not wrong, only old.
    min_week = spec.get('min_week')
    skip_headings = False
    if min_week:
        n = week_number(slug)
        skip_headings = n is not None and n < min_week

    if not skip_headings:
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

    # 4c. The page chrome must still be the site's chrome.
    #
    #     arch-020 shipped with four AWS documentation links in the site nav,
    #     beside Home / Blog / Resume. They were the post's reference list,
    #     inserted by a build script that anchored on "the first </li> before
    #     a </ul>" -- which is the nav, not the reference section. The page
    #     was verified by counting links inside #reference, which returned the
    #     right answer and said nothing about the nav.
    #
    #     That is the general shape of the mistake: editing a page by text
    #     substitution, then checking only the region you meant to change.
    #     This check looks at the region you did not mean to change.
    nav = re.search(r'<ul class="nav-links">(.*?)</ul>', visible, re.DOTALL)
    if not nav:
        err(slug, 'no <ul class="nav-links"> — the page chrome is missing')
    else:
        items = re.findall(r'<li>.*?</li>', nav.group(1), re.DOTALL)
        stray = [re.sub(r'<[^>]+>', '', i).strip() for i in items
                 if 'href="/' not in i]
        if stray:
            err(slug, 'site nav contains %d link(s) that are not site links: %s '
                      '— something wrote page content into the header'
                % (len(stray), ', '.join(s[:40] for s in stray)))
        #     The COUNT is a moving target, and hardcoding it caused a false
        #     failure on every push for a day. d428926 dropped Resume from the
        #     site nav ("Make the home nav look like the blog nav, and drop
        #     Resume from both"), so sync-built pages now render Home + Blog,
        #     while the 85 pages built from the arch template still carry the
        #     three-link version. Both are legitimate site chrome today; only
        #     one of them is the intended end state.
        #
        #     So: two links is current, three is the legacy arch template and
        #     is reported as a warning rather than a failure. Anything else
        #     means something wrote into the nav, which is what this is for.
        labels = [re.sub(r'<[^>]+>', '', i).strip() for i in items]
        if labels == ['Home', 'Blog']:
            pass
        elif labels == ['Home', 'Blog', 'Resume']:
            warn(slug, 'site nav still has the legacy Resume link - built from '
                       'the arch template, which d428926 did not update. '
                       '85 pages are in this state')
        else:
            err(slug, 'site nav is %d link(s): %s - expected Home, Blog'
                % (len(labels), ', '.join(labels)))

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
    diagrams = re.findall(r'<img[^>]+src="(/blog/assets/diagrams/[^"]+)"', visible)
    for src in diagrams:
        check_svg(slug, src)

    # 7b. An explanatory post must HAVE a diagram, not merely have a valid one.
    #
    # Checks 7 and 8 validate a diagram that is present -- it parses, it has a
    # title, its lines fit the canvas, the <img> has alt text. None of them
    # notices a post with no diagram at all, because an absence looks like a
    # deliberate choice. It was not: arch-023 through arch-027 shipped without
    # one over five consecutive days, and arch-009 before them, while the Azure
    # and GCP series stayed at 100%. Found by a person looking at a page, which
    # is the same way the empty post-nav and the stale roadmap entries were
    # found.
    #
    # Scoped to the series that explain a design. Roundups are inventories, not
    # explanations, so the weeklies are exempt; the legacy Weekly Lab uses
    # inline <symbol>/<use> rather than a file and would false-positive here.
    if spec.get("requires_diagram") and not diagrams:
        err(slug, 'no diagram. CLAUDE.md makes a standalone SVG referenced with '
                  '<img> the standard for this series, and nothing else notices '
                  'an absent one -- the other diagram checks only validate a '
                  'diagram that is already there')

    # 8. Images need alt text, and a diagram's alt text has to say something.
    #
    #    `'alt=' not in tag` was the entire check, which passes alt="" -- the
    #    markup that tells a screen reader the image is decorative and should be
    #    skipped. A diagram carrying the post's architecture is the exact
    #    opposite of decorative, and an empty alt is indistinguishable from a
    #    filled one unless somebody reads the tag.
    #
    #    THE EMPTY-ALT RULE IS SCOPED TO DIAGRAMS, and must stay that way.
    #    alt="" is correct HTML for a genuinely decorative image, and this site
    #    has 431 of them: the brand mark in every page header carries
    #    alt="" aria-hidden="true" (145 pages), and the Blogger-migrated posts
    #    carry 286 more on inline content images. Applying the rule to every
    #    <img> reported all 431 as errors on its first run -- a validator
    #    failing the build over correct markup, which is worse than no check.
    #
    #    The "Diagram:" prefix is CLAUDE.md's house standard and is deliberately
    #    a WARNING, not an error. 9 of the 72 diagram images on the site predate
    #    the rule and open with "Diagram showing ..." or end with "... diagram".
    #    Making that blocking would fail the build for every window, on every
    #    publish, over wording in six posts nobody is editing -- the validator
    #    would be reporting history rather than the post being published.
    for tag in re.findall(r'<img[^>]*>', visible):
        if 'alt=' not in tag:
            err(slug, 'an <img> is missing alt text')
            continue
        if '/blog/assets/diagrams/' not in tag:
            continue
        # Both quoting styles: a single-quoted alt is legal HTML, and matching
        # only double quotes would silently skip the tag rather than check it.
        m = re.search(r'''alt\s*=\s*(?:"([^"]*)"|'([^']*)')''', tag)
        if m is None:
            continue
        alt = (m.group(1) if m.group(1) is not None else m.group(2)).strip()
        if not alt:
            err(slug, 'a diagram <img> has an empty alt="" — that marks it '
                      'decorative and hides the post\'s architecture from '
                      'screen readers. Describe what the diagram shows.')
        elif not alt.startswith('Diagram:'):
            warn(slug, 'diagram alt text should start with "Diagram:" and '
                       'describe the content, not the picture (CLAUDE.md). '
                       'Got: %r' % (alt[:60] + ('...' if len(alt) > 60 else '')))

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
    elif spec.get('labels_subset'):
        # The series label is what pill counts and widgets match on; extra
        # labels are harmless. Weeks 1-7 came across from Blogger carrying
        # WeeklySeries, Platform Engineering and others alongside it.
        missing = [x for x in expected if x not in [str(g) for g in got]]
        if missing:
            err(slug, '%s labels are %s, missing %s — pill counts and widgets '
                      'match on the exact string' % (name, got, missing))
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

    # The ceiling is the post's own publish date, not the clock. A daily series
    # is written the day before it goes out, and the GCP Architecture Series
    # carries the publish date on its badge by decision (see CLAUDE.md), so a
    # post dated tomorrow and verified tomorrow is correct and must not fail the
    # build today. Verification dated AFTER publication is still nonsense --
    # nobody checked figures that were already public -- so that still fails.
    pub = parsed.get('date')
    try:
        pubdate = (pub if isinstance(pub, datetime.date)
                   else datetime.datetime.strptime(str(pub).strip()[:10], '%Y-%m-%d').date())
    except (ValueError, TypeError):
        pubdate = today
    ceiling = max(today, pubdate)
    if vdate > ceiling:
        err(slug, '%s claims verification on %s, which is after both today and '
                  'its publish date %s' % (name, vdate, pubdate))
    # The GCP Architecture Series decided its badge carries the PUBLISH date, so
    # any other value is wrong there by definition -- and the wrong value that
    # actually occurred was a stale one. gcp-004 was badged from a date read the
    # previous evening; the session crossed midnight and the clock read was
    # carried across turns instead of re-taken. It went out at 2026-08-16 on a
    # post published 2026-08-17, was "corrected" the wrong way, and needed a
    # second edit. Nothing failed either time, which is why it took a person
    # noticing.
    #
    # Enforced only for series whose rule is badge == publish date. AWS and Azure
    # deliberately allow verified < published, so this must not apply to them.
    if spec.get('badge_is_publish_date') and vdate != pubdate:
        err(slug, '%s is badged %s but publishes %s. This series carries the '
                  'publish date on its badge, so those must match: either '
                  're-verify on the publish date, or drop the badge. Do not '
                  'post-date a check.' % (name, vdate, pubdate))

    # Negative age for a scheduled post is not staleness.
    age = max(0, (today - vdate).days)
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
        allowed = tuple(spec['doc_hosts']) + tuple(spec.get('tool_doc_hosts', ()))
        if not any(host == h or host.endswith('.' + h) for h in allowed):
            err(slug, "%s verified_claims[%d] cites %s. Verification means %s's own "
                      'documentation (%s), not a blog quoting it secondhand.'
                % (name, i, host, spec['vendor'], ', '.join(allowed)))
            continue
        if src.rstrip('/') not in ref.replace('&amp;', '&'):
            warn(slug, '%s verified_claims[%d] cites %s, which is not in the post\'s '
                       'Official AWS Reference section -- a reader cannot repeat the '
                       'check' % (name, i, src))

    _check_derived(slug, name, claims)

    if CHECK_LINKS:
        _check_links_resolve(slug, name, claims, spec)


def _check_derived(slug, name, claims):
    """Recompute any claim that shows its arithmetic.

    Sourcing a claim is not the same as getting it right. arch-018 cited two
    genuine AWS pricing pages and still published a wrong break-even, because
    the error was in the maths done on top of them -- it paired a current write
    price with a read price from before November 2024 and derived a ratio from
    the mixture. Every check written before this one would have passed that
    post: the claims were real, the sources were AWS, the links resolved.

    So a claim may carry a `derive:` expression and an `expect:` value. The
    expression is evaluated with a deliberately tiny arithmetic evaluator and
    compared against what the post says. If they disagree, the post is wrong
    about its own numbers and the build fails.

    This is opt-in per claim, because most claims are quotations and have no
    arithmetic in them. It is meant for the ones that have actually been wrong:
    break-evens, ratios, per-unit conversions, effective rates.
    """
    import ast
    import operator

    ops = {ast.Add: operator.add, ast.Sub: operator.sub,
           ast.Mult: operator.mul, ast.Div: operator.truediv,
           ast.Pow: operator.pow, ast.USub: operator.neg}

    def evaluate(node):
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in ops:
            return ops[type(node.op)](evaluate(node.left), evaluate(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in ops:
            return ops[type(node.op)](evaluate(node.operand))
        raise ValueError("only numbers and + - * / ** are allowed")

    for i, c in enumerate(claims, 1):
        if not isinstance(c, dict) or "derive" not in c:
            continue
        expr = str(c["derive"])
        if "expect" not in c:
            err(slug, '%s verified_claims[%d] has "derive:" but no "expect:" — '
                      'there is nothing to compare the result against' % (name, i))
            continue
        try:
            got = evaluate(ast.parse(expr, mode="eval"))
        except Exception as exc:
            err(slug, '%s verified_claims[%d] derive "%s" did not evaluate: %s'
                % (name, i, expr, exc))
            continue
        try:
            want = float(str(c["expect"]).strip().rstrip("%$x×"))
        except ValueError:
            err(slug, '%s verified_claims[%d] expect "%s" is not a number'
                % (name, i, c["expect"]))
            continue
        # A published figure is rounded; allow a percent of slack, no more.
        tol = max(abs(want) * 0.01, 1e-9)
        if abs(got - want) > tol:
            err(slug, '%s verified_claims[%d] says %s but %s works out to %.6g '
                      '— the post disagrees with its own arithmetic'
                % (name, i, c["expect"], expr, got))


def _check_links_resolve(slug, name, claims, spec):
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

    That heuristic is a property of one host, not of documentation in general,
    so the hosts it applies to are declared per series as `shell_hosts`.
    Measured 2026-08-14, `learn.microsoft.com` and `azure.microsoft.com` both
    return a real HTTP 404 for a missing page, so the Azure series declares no
    shell hosts and relies on the status code alone. Do not extend the byte
    threshold to a host without checking a known-bad URL on it first — a wrong
    threshold either passes dead links or fails live ones.

    A dead link and a bad afternoon look identical for one request
    -------------------------------------------------------------
    404 and 410 are the vendor saying the page is gone: a real defect, and an
    error. 429 and the 5xx family are the vendor saying "not right now" —
    retried, and if they persist, a warning rather than an error. Microsoft's
    edge returned 503 during testing and served the page on immediate retry;
    failing a build for that teaches people the gate is noise, and a gate
    nobody trusts stops catching the 404s too.

    A connection-level failure was already a warning for the same reason. This
    only closes the gap where the same transient arrived with a status code
    attached.
    """
    import time
    import urllib.request
    import urllib.error

    # "Come back later", not "it is gone".
    TRANSIENT = (408, 425, 429, 500, 502, 503, 504)
    ATTEMPTS = 3

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

        code = body = None
        for attempt in range(ATTEMPTS):
            last = attempt == ATTEMPTS - 1
            try:
                resp = urllib.request.urlopen(req, timeout=25)
                code, body = resp.getcode(), resp.read(80000)
                break
            except urllib.error.HTTPError as exc:
                if exc.code in TRANSIENT:
                    if not last:
                        time.sleep(2 * (attempt + 1))
                        continue
                    warn(slug, '%s cites %s which returned HTTP %d on %d '
                               'attempts — treated as a vendor outage, not a '
                               'dead link. Not verified this run.'
                         % (name, src, exc.code, ATTEMPTS))
                else:
                    err(slug, '%s cites %s which returns HTTP %d'
                        % (name, src, exc.code))
                break
            except Exception as exc:
                if not last:
                    time.sleep(2 * (attempt + 1))
                    continue
                warn(slug, '%s could not reach %s (%s)' % (name, src, exc))
                break

        if code is None:
            continue
        if code >= 400:
            err(slug, '%s cites %s which returns HTTP %d' % (name, src, code))
        elif (any(h in src for h in spec.get('shell_hosts', ()))
              and len(body) < DOCS_SHELL_BYTES):
            err(slug, '%s cites %s which returns a %d-byte shell, not an article. '
                      'That host answers 200 for missing pages, so this '
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
            found = sorted(os.path.basename(os.path.dirname(p)) for p in
                           glob.glob(os.path.join(BLOG, spec['slug_glob'], 'index.html')))
            # The three lab series share the glob 'week-*', so each would
            # enumerate all 17 lab posts and every one would be checked three
            # times. Keep only the ones this series actually owns.
            if spec.get('series_label'):
                found = [s for s in found if lab_series_for_slug(s) == key]
            slugs += found
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
