#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check the half of a post that carries the argument rather than the quotes.

    python scripts/check_assertions.py                 # every series
    python scripts/check_assertions.py --series arch   # one series
    python scripts/check_assertions.py arch-042        # one post

Why this exists
---------------
Every factual error found in this series so far has been in a sentence written
in the author's own voice, not in a quotation. Not one has been a misquote.
`verify_claims.py` matches a claim's figures against the literal text of the
cited page and has never let a bad quote through; `validate_arch_post.py`
evaluates every `derive:` and has never let bad arithmetic through. Both work.
Neither can see an assertion, because an assertion has nothing attached to it.

The record, at the point this was written:

* **#40** said an AWS Config aggregator enables recording. It does not -- an
  aggregator is read-only. The sentence sat between two correctly cited facts
  and carried no claim of its own.
* **#32** said an Athena reservation was "about a third of the price" of the
  smallest Redshift Serverless capacity. It is 20% below. That post has
  seventeen `derive:` claims, all correct; the wrong number was a ratio in
  flowing prose that no claim covered.
* **#34** said streaming cost is "not a function of volume" while the same post
  cited a per-GB charge.
* **#42** said an emergency IAM user "depends on nothing outside IAM".
* **#35** and **#40** both shipped an SCP whose break-glass exception was
  written `arn:aws:iam::*:role/<name>`, which lets any member-account
  administrator who can create a role with that name exempt themselves.

Two categories, and they need different treatment.

**Example policy code** is checked hard, because these patterns are defects
rather than judgements. A wildcard account in a principal ARN, an `Allow` to
`"Principal": "*"`, or a deny on an API that both sets and unsets a control are
wrong in a teaching example every time, whatever the surrounding prose says.
Those fail the build.

**Prose assertions** are reported, not failed, for the same reason
`audit_claims.py` is advisory: deciding whether "the only" is overreach or
precision needs a human, and a checker that fails on the word "only" would be
switched off within a week. So this prints every comparative and every absolute
in body text, with whether the post has arithmetic backing it, and leaves the
judgement where it belongs. The value is that the sentences which have
historically been wrong are the ones on the list -- they stop being invisible.
"""
import argparse
import glob
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS = os.path.join(ROOT, "posts")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validate_arch_post import SERIES                          # noqa: E402

# --- hard failures, in example code only -----------------------------------
#
# Each of these has shipped. The comment names where, so a future reader can
# see the pattern is observed rather than imagined.
CODE_DEFECTS = [
    # arch-035 and arch-040. An exception written against a role NAME with a
    # wildcard account is an exception anyone able to choose a role name can
    # claim -- including a member-account administrator the policy is meant to
    # constrain.
    (re.compile(r'arn:aws:iam::\\?\*:role/'),
     'wildcard account ID in a role ARN - any account with a role of that '
     'name matches. Pin the account the role actually lives in'),
    # arch-040. s3:PutAccountPublicAccessBlock is the same API for setting the
    # block as for removing it, so denying it blocks your own baseline.
    (re.compile(r'"Deny"[\s\S]{0,600}?s3:PutAccountPublicAccessBlock'),
     'deny on s3:PutAccountPublicAccessBlock - that API both sets and unsets '
     'Block Public Access, so this also blocks applying the baseline'),
]

PRINCIPAL_STAR = re.compile(r'"Principal"\s*:\s*(?:"\*"|\{\s*"AWS"\s*:\s*"\*"\s*\})')
EFFECT = re.compile(r'"Effect"\s*:\s*"(Allow|Deny)"')


def public_allow(block):
    """True when a wildcard Principal sits under an Allow.

    Decided from the Effect that governs the statement, not from whether the
    word "Deny" appears somewhere nearby. arch-043 has a legitimate
    "Effect": "Deny" with "Principal": "*" -- denying everyone is how a bucket
    policy says nobody deletes -- and a proximity test flagged it.
    """
    for m in PRINCIPAL_STAR.finditer(block):
        before = EFFECT.findall(block[:m.start()])
        after = EFFECT.findall(block[m.end():])
        effect = before[-1] if before else (after[0] if after else None)
        if effect == "Allow":
            return True
    return False


# --- advisory, in prose ----------------------------------------------------
#
# Comparatives are the ones that have actually been wrong. Each needs a
# `derive:` behind it or a reason it does not.
COMPARATIVE = re.compile(
    r'\b(?:'
    r'(?:a|one)[- ](?:third|quarter|fifth|half) of\b'
    r'|half (?:the|of) (?:the )?(?:price|cost|rate|size|time)\b'
    r'|\d+(?:\.\d+)?\s*(?:times|x)\s+(?:the|as|more|less|cheaper|faster|slower)\b'
    r'|\d+(?:\.\d+)?\s*%\s*(?:cheaper|dearer|more|less|below|above|faster|slower|of)\b'
    r'|(?:cheaper|dearer|faster|slower|larger|smaller)\s+by\b'
    r'|exactly\s+(?:\d+(?:\.\d+)?|twice|half|double)\b'
    r'|(?:twice|double|triple)\s+(?:the|that of)\b'
    r')', re.I)

# A comparative is only interesting when it compares quantities, so the
# sentence must also carry a number. Without this the checker fired on "run
# twice", "read that twice" and "for a third party" -- 57 flags across the
# arch series, which is how a checker gets switched off.
#
# Written as raw strings on purpose. The first version of this block was
# patched in through a non-raw Python string, so every \b became a literal
# backspace byte and the pattern matched nothing at all -- the checker
# reported a clean corpus because it was checking for a control character.
# The controls at the bottom of this file exist so that cannot recur
# silently: a checker that cannot fail is worse than no checker.
HAS_NUMBER = re.compile(r'[$\d]')

# Absolutes are reported more loosely. Many are legitimate, and a good number
# are direct quotations of AWS, which is why this never fails a build.
ABSOLUTE = re.compile(
    r'\b(?:'
    r'depends on nothing|nothing (?:outside|else|other than)'
    r'|the only (?:identity|thing|way|mechanism|one|control|answer)'
    r'|every single\b|cannot ever\b|no other\b'
    r'|entirely dependent|wholly dependent'
    r')', re.I)

SENTENCE = re.compile(r'(?<=[.!?])\s+')


def body_and_front(path):
    raw = io.open(path, encoding="utf-8").read()
    if raw.startswith("---"):
        end = raw.find("\n---", 3)
        return raw[end + 4:], raw[:end]
    return raw, ""


def code_blocks(body):
    return re.findall(r"<pre><code>([\s\S]*?)</code></pre>", body)


def prose(body):
    """Body text with code, styles, and quoted inventories removed.

    Three exclusions, each because it produced a false positive:

    * `<style>` and inline SVG CSS -- week-14's diagram matched on a font
      shorthand that happened to contain a number and the word "times".
    * The weekly roundups' `id="inventory"` section, which is AWS's own
      announcement titles verbatim. "Amazon Quick Max: 5x the usage" is a
      product name, not an assertion this author made, and the point of this
      checker is the sentences written in the author's own voice.
    * Code blocks, which are checked separately and by different rules.
    """
    body = re.sub(r'<div class="section" id="inventory">[\s\S]*?(?=<div class="section")',
                  " ", body)
    body = re.sub(r"<style[\s\S]*?</style>", " ", body)
    body = re.sub(r"<pre><code>[\s\S]*?</code></pre>", " ", body)
    body = re.sub(r"<[^>]+>", " ", body)
    body = (body.replace("&mdash;", "-").replace("&ndash;", "-")
                .replace("&amp;", "&").replace("&nbsp;", " ")
                .replace("&#8212;", "-").replace("&quot;", '"'))
    return re.sub(r"\s+", " ", body)


def series_of(name):
    for key, spec in SERIES.items():
        if name.startswith(spec["file_prefix"]):
            return key
    return None


def check(path, show_absolutes):
    name = os.path.basename(path)
    body, front = body_and_front(path)
    errors, notes = [], []

    for block in code_blocks(body):
        for pattern, message in CODE_DEFECTS:
            if pattern.search(block):
                errors.append(message)
        if public_allow(block):
            errors.append('Allow to a wildcard Principal - public access. '
                          'Name the principal, or pair the wildcard with Deny '
                          'and a condition')

    derives = front.count("derive:")
    text = prose(body)
    for sentence in SENTENCE.split(text):
        s = sentence.strip()
        if not s:
            continue
        if COMPARATIVE.search(s) and HAS_NUMBER.search(s):
            notes.append(("ratio", s))
        elif show_absolutes and ABSOLUTE.search(s):
            notes.append(("absolute", s))
    return name, errors, notes, derives


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("posts", nargs="*")
    ap.add_argument("--series")
    ap.add_argument("--absolutes", action="store_true",
                    help="also list absolute constructions, which are noisier")
    args = ap.parse_args()

    paths = []
    if args.posts:
        for p in args.posts:
            paths += sorted(glob.glob(os.path.join(POSTS, p + "*.html")))
    else:
        prefixes = ([SERIES[args.series]["file_prefix"]] if args.series
                    else [s["file_prefix"] for s in SERIES.values()])
        for pre in prefixes:
            paths += sorted(glob.glob(os.path.join(POSTS, pre + "*.html")))
    paths = sorted(set(paths))

    failed = 0
    flagged = 0
    for path in paths:
        if not series_of(os.path.basename(path)):
            continue
        name, errors, notes, derives = check(path, args.absolutes)
        if not errors and not notes:
            continue
        print("\n%s" % name)
        for message in errors:
            failed += 1
            print("   ERROR  example code: %s" % message)
        for kind, sentence in notes:
            flagged += 1
            trimmed = sentence if len(sentence) <= 150 else sentence[:147] + "..."
            print("   %-8s %s" % (kind + ":", trimmed))
        if notes:
            print("            (post has %d derive claim%s)"
                  % (derives, "" if derives == 1 else "s"))

    print("\nChecked %d post(s): %d code defect(s), %d assertion(s) to eyeball."
          % (len(paths), failed, flagged))
    if flagged and not failed:
        print("Assertions are advisory. Each ratio above needs a derive claim "
              "behind it, or a reason it does not need one.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
