"""Does this post look like the rest of its series?

Every other structural check in this repo asks "is what is on the page
correct?". None of them ask "is anything missing?", because a check can only
inspect what exists. That blind spot is not hypothetical:

  * gcpweekly-006 shipped with no "On this page" block. #1-#5 all carry one.
    All 41 checks passed. The page looked finished, and a reader navigating a
    245-note roundup had no way to jump to a section.

The pattern is always the same -- a structural element that is hand-written
prose rather than generated output gets dropped, and nothing notices, because
nothing was comparing the post against its siblings.

Adding `requires_toc` fixed that one case. It does not fix the next one, which
will be some other element nobody has thought to write a flag for. So this
check does not carry a list of required things. It derives the list from the
series itself:

    for each post, the expected skeleton is the set of CSS class tokens
    present in at least 90% of the OTHER posts in that series.

Leave-one-out matters. With six posts and a token in five of them, a plain
"present in 90% of all posts" test computes 5/6 = 83% and stays silent about
precisely the post that is missing it. Excluding the post under test gives
5/5 = 100%, and the omission is obvious. The defect defines itself away under
the naive threshold, which is worth stating because it is easy to write.

Class tokens, not element ids: ids legitimately vary between posts in a
roundup series (one week has `#vpcsc`, another `#apigee`), whereas the classes
carrying layout -- toc, post-header, section, table-scroll, callout -- are the
series contract. A token has to appear in at least three other posts before it
counts, so a young series cannot generate confident nonsense.

This is advisory by default and blocking with --fail. It reports what it
believes the convention is, so a deliberate departure can be read and
dismissed rather than silently tolerated.
"""

import argparse
import collections
import glob
import io
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BLOG = os.path.join(ROOT, 'blog')

sys.path.insert(0, HERE)

MIN_SIBLINGS = 3      # below this, the series has not established a convention
SHARE = 0.9           # a token in >=90% of siblings is part of the skeleton

# Classes that describe content rather than structure. A post legitimately has
# no tables, or no callouts, so their absence says nothing about whether the
# skeleton is intact. Everything else is fair game.
IGNORE = {
    # The newest post on the site has no "next" link until something is
    # published after it -- post-nav is chronological across all series, not
    # within one. Flagging that would fire on every new post, every week, and
    # a check that cries wolf is one that gets ignored.
    'next', 'prev',
    'inv-gist', 'muted', 'val', 'red', 'inline', 'amber', 'green', 'blue',
    'code-block', 'code-header', 'code-lang', 'code-dot', 'zoom-trigger',
    'zoomable-img', 'lightbox-img', 'lightbox-svg', 'lightbox-x',
    'lightbox-close', 'lightbox-overlay',
}

CLASS_RE = re.compile(r'class="([^"]+)"')


def series_map():
    """Reuse validate_arch_post's registry rather than keeping a second copy.

    A duplicated glob would drift the first time a series is renamed, and this
    check would then quietly measure the wrong corpus.
    """
    import validate_arch_post as V
    out = {}
    for key, spec in V.SERIES.items():
        g = spec.get('slug_glob')
        if g:
            out[key] = (spec.get('label', key), g)
    return out


def tokens_for(path):
    html = io.open(path, encoding='utf-8').read()
    toks = set()
    for attr in CLASS_RE.findall(html):
        for t in attr.split():
            if t and t not in IGNORE:
                toks.add(t)
    return toks


def check_series(key, label, pattern, verbose=False):
    paths = sorted(glob.glob(os.path.join(BLOG, pattern, 'index.html')))
    if len(paths) < MIN_SIBLINGS + 1:
        return [], 0
    by_slug = {}
    for p in paths:
        by_slug[os.path.basename(os.path.dirname(p))] = tokens_for(p)

    problems = []
    for slug, toks in sorted(by_slug.items()):
        others = [t for s, t in by_slug.items() if s != slug]
        if len(others) < MIN_SIBLINGS:
            continue
        need = math.ceil(SHARE * len(others))
        counts = collections.Counter()
        for o in others:
            counts.update(o)
        expected = {t for t, n in counts.items() if n >= need}
        missing = sorted(expected - toks)
        if missing:
            for m in missing:
                problems.append((slug, m, counts[m], len(others)))
    return problems, len(by_slug)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--series', help='only this series key')
    ap.add_argument('--fail', action='store_true',
                    help='exit non-zero when a post departs from its series')
    ap.add_argument('--verbose', action='store_true')
    args = ap.parse_args()

    smap = series_map()
    if args.series:
        if args.series not in smap:
            print('unknown series %r. known: %s'
                  % (args.series, ', '.join(sorted(smap))))
            return 2
        smap = {args.series: smap[args.series]}

    total_problems = 0
    checked = 0
    for key in sorted(smap):
        label, pattern = smap[key]
        problems, n = check_series(key, label, pattern, args.verbose)
        checked += n
        if args.verbose and n:
            print('  %-28s %d post(s)' % (label, n))
        for slug, tok, seen, of in problems:
            total_problems += 1
            print('  %s: missing class %r, which %d of the other %d '
                  '%s posts carry' % (slug, tok, seen, of, label))

    print('\nChecked %d post(s) across %d series: %d departure(s) from the '
          'series skeleton.' % (checked, len(smap), total_problems))
    if total_problems and args.fail:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
