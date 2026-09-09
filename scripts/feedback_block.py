#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The "tell me this is wrong" block, defined once for every Intelligence page.

    from feedback_block import feedback_html, FEEDBACK_CSS

Why it exists
-------------
These pages make factual claims -- which cloud is broken, when an incident
started, what a vendor published. They are assembled from feeds that move, by
parsers that have been wrong before: a missing slash killed every Google
incident link, a banner year dated a 2025 outage to 2026, and a schedule that
never ran was described as running every fifteen minutes. Each of those was
found by a reader looking at the page, not by any check.

A page that asks to be trusted has to offer a way to be corrected. Without
one, the only thing a reader can do with an error is stop believing the page,
and I never find out.

Why no form
-----------
A form needs somewhere to POST, which means a service, a secret, and a thing
that can quietly stop working -- the exact failure this site keeps hitting.
Both routes here are plain links that cannot break: a mailto to an address
already published on this site, and a GitHub issue on the repository that
builds these pages. The issue route also makes a correction PUBLIC, which
matters on a page whose argument is that its claims are checkable.

Defined once, in one module, imported by both generated pages. The cloud
palette lived in five files that agreed by hand until they did not, and two of
them ended up colouring Google and Azure the same blue.
"""
import urllib.parse

EMAIL = "katta.jayant@gmail.com"
REPO = "https://github.com/katta698/katta698.github.io"


def feedback_html(page_name, page_url):
    """A correction block for one page, with the page named in both routes.

    The page is carried in the subject and the issue title because a report
    that says only "this is wrong" costs a round trip to place, and most
    people will not make it.
    """
    subject = "Correction: %s" % page_name
    body = ("What looks wrong:\n\n\nWhere I saw it:\n%s\n\n"
            "(Anything you can add helps -- what you expected, and what the "
            "vendor's own page says.)\n" % page_url)
    mailto = "mailto:%s?subject=%s&body=%s" % (
        EMAIL,
        urllib.parse.quote(subject),
        urllib.parse.quote(body))

    issue = "%s/issues/new?title=%s&body=%s" % (
        REPO,
        urllib.parse.quote("Correction: %s" % page_name),
        urllib.parse.quote("**Page:** %s\n\n**What looks wrong:**\n\n\n"
                           "**What the vendor's own page says:**\n\n"
                           % page_url))

    return (
        '<aside class="fb">'
        '<p class="fb-h">Found something wrong here?</p>'
        '<p class="fb-t">This page is assembled from the vendors’ own '
        'feeds, and it has been wrong before — a broken link, a '
        'mislabelled region, a figure that went stale. If something does not '
        'match what the vendor says, tell me and I’ll fix it and say so.</p>'
        '<p class="fb-a">'
        '<a class="fb-b" href="%s">Email a correction</a>'
        '<a class="fb-l" href="%s" target="_blank" rel="noopener">'
        'or open an issue on GitHub</a>'
        '</p></aside>' % (mailto, issue))


# Written against the tokens both Intelligence pages define (--card, --bd,
# --tx, --mut, --acc). Kept here so the two pages cannot drift apart.
FEEDBACK_CSS = """
/* The correction block. Deliberately quiet: it sits at the end, states what
   can be wrong, and offers two routes that cannot break -- no form, no
   endpoint, nothing to go silently down.

   SELF-CONTAINED ON PURPOSE. The first version filled the button with
   var(--acc), which the status page defines and the other two do not. An
   undefined custom property invalidates the whole declaration, so the fill
   silently vanished and dark text sat on a dark card at 1.23:1 -- on two of
   the three pages this block exists to serve. That is the fifth time an
   undefined token has done this here (--accent-gold, --nav-bg, --accent,
   --ink, --acc), and the first time inside a module written to stop exactly
   this kind of divergence.

   So nothing below depends on a token that any given page might not define.
   The button borrows the page's own text colour with `inherit`, which is
   readable against that page's own background by definition, and every var()
   carries a literal fallback. */
.fb{margin:2.2rem 0 0;padding:1.1rem 1.2rem;border-radius:12px;
  background:var(--card, var(--surface, transparent));
  border:1px solid var(--bd, var(--border, rgba(128,128,128,.28)))}
.fb-h{margin:0 0 .4rem;font-size:.92rem;font-weight:600}
.fb-t{margin:0 0 .9rem;font-size:.82rem;line-height:1.55;
  /* inherit, not --mut. What's New defines --mut at 4.40:1 against its own
     card in light mode -- fine for a timestamp, under AA for a paragraph. A
     shared block cannot assume another page's muted colour clears the bar for
     the use IT puts that colour to, so this takes the page's body colour,
     which is readable there by definition, and stays secondary by size. */
  color:inherit}
.fb-a{margin:0;display:flex;gap:.9rem;align-items:center;flex-wrap:wrap}
.fb-b{display:inline-block;padding:.45rem .85rem;border-radius:8px;
  background:transparent;color:inherit;font-size:.8rem;font-weight:600;
  text-decoration:none;border:1px solid currentColor}
.fb-b:hover,.fb-b:focus-visible{
  background:color-mix(in srgb, currentColor 10%, transparent)}
.fb-l{font-size:.78rem;color:inherit;text-decoration:underline;
  text-underline-offset:2px;opacity:.85}
.fb-l:hover,.fb-l:focus-visible{opacity:1}
"""
