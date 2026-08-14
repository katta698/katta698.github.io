#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the served page for an Architecture Series post.

    python scripts/build_arch_post.py posts/arch-021-discovery-wave-planning.html

sync_blog.py treats arch-* as read-only pass-through, so these pages are built
once from _templates/arch-post-template.html and edited in place afterwards.
This script exists because each post used to get its own throwaway build
script, and each one reintroduced the same defects:

  * a hardcoded VERIFIED date, which stamped the accuracy badge on whatever it
    built. Five consecutive posts were badged that way with nothing checked,
    and one shipped a factual error under it. The badge here is rendered from
    the front matter that validate_arch_post.py enforces, or omitted entirely.

  * the template wraps each content slot in <p>...</p>, which is right for a
    sentence and wrong for a section body full of cards and tables. arch-020
    shipped with <p><p> and a table inside a paragraph.

  * the reference list was patched in by matching "the first </li> before a
    </ul>", and the first list on the page is the site nav. arch-020 shipped
    with four AWS documentation links in its header.

Every one of those is now handled once, here, instead of being re-derived.
"""
import hashlib
import io
import math
import os
import re
import sys
from datetime import datetime

import yaml
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(ROOT, "_templates", "arch-post-template.html")

SECTIONS = ["challenge", "architecture", "why", "decisions", "closing"]

# One template, two series. _templates/arch-post-template.html is written in AWS
# terms because it predates the Azure series; rather than fork it -- two copies
# of the same page chrome drift, and the chrome is the part validate_arch_post.py
# checks hardest -- the Azure build rewrites the handful of literals that name
# the cloud. Order matters: the longest string is replaced first, so "AWS
# Architecture Series" is not left as "Azure Architecture Series" by an earlier
# bare "AWS" -> "Azure" pass.
AZURE_LITERALS = [
    ("AWS Architecture Series", "Azure Architecture Series"),
    ("Official AWS Reference", "Official Azure Reference"),
    ('<span class="tag-badge">AWS</span>', '<span class="tag-badge">Azure</span>'),
    ('data-topics="AWS,Architecture,', 'data-topics="Azure,Architecture,'),
]


def build(src_path, prev_slug=None, prev_title=None):
    raw = io.open(src_path, encoding="utf-8").read()
    _, fm_text, body = raw.split("---", 2)
    fm = yaml.safe_load(fm_text)
    slug = fm["slug"]

    def section(sid):
        m = re.search(r'<div class="section" id="%s">(.*?)\n  </div>' % sid, body, re.S)
        if not m:
            raise SystemExit("section %s missing from %s" % (sid, src_path))
        # the template supplies the <h2>
        return re.sub(r"\s*<h2>.*?</h2>", "", m.group(1), count=1).strip()

    content = {s: section(s) for s in SECTIONS}

    refs_block = re.search(r'<div class="section" id="reference">(.*?)\n  </div>', body, re.S)
    if not refs_block:
        raise SystemExit("no reference section in %s" % src_path)
    ref_links = re.findall(r'<li><a href="([^"]+)"[^>]*>(.*?)</a></li>', refs_block.group(1))
    if not ref_links:
        raise SystemExit("reference section has no links")

    title = fm["title"]
    number = re.search(r"#(\d+)", title).group(1)
    short_title = title.split("—", 1)[1].strip()
    plain = BeautifulSoup(body, "html.parser").get_text()
    read_time = "%d min read" % max(1, math.ceil(len(plain.split()) / 200))
    date = datetime.strptime(str(fm["date"]), "%Y-%m-%d")
    date_display = "%s %d, %d" % (date.strftime("%b"), date.day, date.year)

    css = io.open(os.path.join(ROOT, "blog", "assets", "blog.css"), encoding="utf-8").read()
    css_version = hashlib.md5(css.encode("utf-8")).hexdigest()[:8]

    tpl = io.open(TPL, encoding="utf-8").read()

    is_azure = os.path.basename(src_path).startswith("az-")
    if is_azure:
        for old, new in AZURE_LITERALS:
            tpl = tpl.replace(old, new)

    # Strip the template's instruction comment, which is for whoever is reading
    # the template and has no business in a served page.
    if "<!DOCTYPE html>" in tpl:
        tpl = tpl[tpl.index("<!DOCTYPE html>"):]

    # Unwrap the slots: the bodies carry their own block markup.
    for slot in ("CHALLENGE_CONTENT", "ARCHITECTURE_CONTENT", "WHY_CONTENT",
                 "DECISIONS_CONTENT", "CLOSING_CONTENT"):
        tpl = tpl.replace("<p>{{%s}}</p>" % slot, "{{%s}}" % slot)

    repl = {
        "{{FULL_TITLE}}": title,
        "{{SHORT_TITLE}}": short_title,
        "{{DESCRIPTION}}": fm.get("problem", ""),
        "{{SLUG}}": slug,
        "{{POST_NUMBER}}": number,
        "{{DATE_DISPLAY}}": date_display,
        "{{READ_TIME}}": read_time,
        "{{CSS_VERSION}}": css_version,
        "{{DISQUS_ID}}": slug,
        "{{CHALLENGE_CONTENT}}": content["challenge"],
        "{{ARCHITECTURE_CONTENT}}": content["architecture"],
        "{{WHY_CONTENT}}": content["why"],
        "{{DECISIONS_CONTENT}}": content["decisions"],
        "{{CLOSING_CONTENT}}": content["closing"],
        "{{AWS_DOCS_URL}}": ref_links[0][0],
        "{{AWS_DOCS_LINK_TEXT}}": ref_links[0][1],
        "{{AWS_DOCS_DESCRIPTION}}": (
            "Microsoft's own documentation for this post's claims." if is_azure
            else "AWS's own guidance for this post's claims."),
        "{{PREV_SLUG}}": prev_slug or "",
        "{{PREV_TITLE}}": prev_title or "",
    }
    # First post of a series: drop the previous half of the post-nav rather than
    # substituting empty strings into it. This has to happen BEFORE the
    # substitution loop below, which would otherwise turn the placeholders into
    # `href="/blog//"` around an empty title — both of which
    # validate_arch_post.py rejects. Until the Azure series started, every post
    # this script built had a predecessor, so the case had never arisen.
    if not prev_slug:
        tpl = re.sub(r'<a href="/blog/\{\{PREV_SLUG\}\}/" class="post-nav-link prev">.*?</a>',
                     "", tpl, flags=re.S)

    for k, v in repl.items():
        tpl = tpl.replace(k, v)

    # Reference list: replace the <ul> INSIDE the reference section, anchored on
    # its own heading. Never on "the first list", which is the nav.
    items = "\n".join(
        '      <li><a href="%s" target="_blank" rel="noopener">%s</a></li>' % (u, t)
        for u, t in ref_links)
    ref_heading = "Official Azure Reference" if is_azure else "Official AWS Reference"
    m = re.search(r'(<h2>%s</h2>\s*<ul>)(.*?)(</ul>)' % ref_heading, tpl, re.S)
    if not m:
        raise SystemExit("reference <ul> not found in the template")
    tpl = tpl[:m.start(2)] + "\n" + items + "\n    " + tpl[m.end(2):]

    # Latest post: drop the next half of the nav rather than leaving it blank.
    tpl = re.sub(r'<a href="/blog/\{\{NEXT_SLUG\}\}/" class="post-nav-link next">.*?</a>',
                 "", tpl, flags=re.S)

    # The "Next in this series" callout: the post body may carry its own. If it
    # does, that content wins; if not, remove the whole callout instead of
    # leaving a heading over an empty paragraph.
    teaser = re.search(r'<strong>Next in this series</strong>\s*<p>(.*?)</p>',
                       content["closing"], re.S)
    if teaser:
        # already inside CLOSING_CONTENT, so drop the template's empty one
        tpl = re.sub(r'\s*<div class="callout">\s*<strong>Next in this series</strong>\s*'
                     r'<p>\{\{NEXT_TOPIC_TEASER\}\}</p>\s*</div>', "", tpl, count=1, flags=re.S)
    else:
        tpl = re.sub(r'\s*<div class="callout">\s*<strong>Next in this series</strong>.*?</div>',
                     "", tpl, count=1, flags=re.S)
    tpl = tpl.replace("{{NEXT_TOPIC_TEASER}}", "")

    # Accuracy badge, from the front matter or not at all.
    if fm.get("verified") and len(fm.get("verified_claims") or []) >= 2:
        d = datetime.strptime(str(fm["verified"]), "%Y-%m-%d")
        shown = "%d %s %d" % (d.day, d.strftime("%B"), d.year)
        badge = ('<div class="verified-badge">'
                 '<span class="verified-check" aria-hidden="true">&#10003;</span>'
                 '<span class="verified-text"><strong>Verified against current vendor '
                 'documentation on %s.</strong> Pricing, limits and API behaviour were checked '
                 'against the official docs on that date. Cloud services change fast &mdash; if '
                 'you are reading this much later, treat the specifics as a starting point and '
                 're-check the linked sources.</span></div>' % shown)
        tpl = tpl.replace("</header>", "</header>\n    " + badge, 1)

    out_dir = os.path.join(ROOT, "blog", slug)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "index.html")
    io.open(out_path, "w", encoding="utf-8", newline="\n").write(tpl)

    left = sorted(set(re.findall(r"\{\{[A-Z_0-9]+\}\}", tpl)))
    nav = re.search(r'<ul class="nav-links">(.*?)</ul>', tpl, re.S)
    nav_items = len(re.findall(r"<li>", nav.group(1))) if nav else 0

    print("wrote %s" % out_path)
    print("  %s | %s | css v=%s" % (date_display, read_time, css_version))
    print("  references: %d | nav items: %d | placeholders left: %s"
          % (len(ref_links), nav_items, left or "none"))
    if left or nav_items != 3:
        raise SystemExit("build produced a page that would fail validation")
    return out_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    build(sys.argv[1],
          prev_slug=sys.argv[2] if len(sys.argv) > 2 else None,
          prev_title=sys.argv[3] if len(sys.argv) > 3 else None)
