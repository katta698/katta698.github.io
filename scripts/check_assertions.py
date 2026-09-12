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


def statements(block):
    """Split a policy document into its statement objects, roughly.

    Brace-counting rather than json.loads, because these blocks are teaching
    examples: they carry comments, elisions and placeholder tokens that are not
    valid JSON. Getting the boundaries approximately right is enough to decide
    which Effect and which Condition govern a given Principal.

    The first version tracked a single `start`, set only when depth went from
    zero to one. Every inner object therefore reported the *outer* document's
    start offset, so a statement's span began at the top of the policy and
    swept up every earlier Effect. arch-043's "Effect": "Deny" statement was
    read as an Allow because an Allow appeared earlier in the same document,
    and a correct post was flagged. A stack gives each brace its own start.
    """
    out, stack = [], []
    for i, ch in enumerate(block):
        if ch == "{":
            stack.append(i)
        elif ch == "}" and stack:
            out.append(block[stack.pop():i + 1])
    # Keep the innermost objects that look like statements: one that contains
    # another Effect-bearing object is a wrapper, not a statement.
    stmts = [s for s in out if '"Effect"' in s]
    innermost = [s for s in stmts
                 if not any(o != s and o in s and '"Effect"' in o for o in stmts)]
    return innermost or stmts or [block]


def public_allow(block):
    """True when a wildcard Principal sits under an unconditioned Allow.

    Two exclusions, both found by running this against posts that were right.

    arch-043 has a legitimate "Effect": "Deny" with "Principal": "*" -- denying
    everyone is how a bucket policy says nobody deletes -- so the Effect that
    governs the statement decides, not whether the word "Deny" appears nearby.

    arch-044 has two wildcard Allows that are also correct. A VPC gateway
    endpoint policy *must* set Principal to "*": AWS requires it, and the
    narrowing is done with aws:PrincipalArn or aws:ResourceOrgID in a
    Condition. So a wildcard Principal carrying a Condition is not a public
    grant, and flagging it would push authors towards a policy AWS rejects.
    """
    for stmt in statements(block):
        if not PRINCIPAL_STAR.search(stmt):
            continue
        effects = EFFECT.findall(stmt)
        if effects and effects[0] != "Allow":
            continue
        if not effects:
            continue
        if '"Condition"' in stmt:
            continue
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

# Consequences drawn from correct facts, which is the one shape neither of the
# patterns above can see. COMPARATIVE is gated on HAS_NUMBER by design -- see
# the note above -- so a sentence that states a *billing or eligibility
# outcome* without a digit is invisible to this file.
#
# That is not hypothetical. Azure Architecture #31, published 2026-09-12, said:
#
#     "So a single access review spanning employees and partners is billed two
#      ways at once: a held seat count for the members, and a monthly active
#      charge against an Azure subscription for the guests."
#
# Every quoted fact around it was correct and sourced. The sentence was not,
# and contains no digit, so nothing here fired. Microsoft's rule is that guests
# are billed only for capabilities exclusive to ID Governance; a review using
# P2 capabilities is not billed twice.
#
# Two conditions, deliberately: a connective that signals the author is drawing
# a conclusion, *and* a verb that asserts a cost or a requirement. Either alone
# is ordinary prose and fires constantly. Together they are rare, and they are
# where the error lives. Report-only, like everything else in this half.
CONSEQUENCE_CUE = re.compile(
    r'\b(?:so|therefore|which means|that means|meaning|so that|hence|'
    r'as a result|in other words|put plainly|the upshot)\b', re.I)
CONSEQUENCE_VERB = re.compile(
    r'\b(?:is|are|was|were|gets?|becomes?)\s+(?:\w+\s+){0,2}'
    r'(?:billed|charged|priced|licen[cs]ed|required|exempt|covered|free)\b'
    r'|\b(?:you|teams?|estates?)\s+(?:then\s+)?(?:pay|owe|need|must)\b'
    r'|\bcosts? (?:you )?(?:nothing|twice|double)\b'
    r'|\brequires? (?:a |an |two |both )', re.I)

# A sentence that quotes its source is not an unsupported inference. The quote
# marks the assertion as the vendor's rather than the author's, which is the
# whole distinction this file was written to police.
HAS_QUOTE = re.compile(r'<em>|&ldquo;|"')

SENTENCE = re.compile(r'(?<=[.!?])\s+')


def body_and_front(path):
    raw = io.open(path, encoding="utf-8").read()
    if raw.startswith("---"):
        end = raw.find("\n---", 3)
        return raw[end + 4:], raw[:end]
    return raw, ""


# An opt-out for a code block that is deliberately showing a bad policy.
# arch-044 quotes AWS's default VPC endpoint policy -- Allow, Principal "*",
# Action "*", Resource "*" -- precisely to argue that it is too permissive.
# Flagging that is correct by the rule and wrong by the intent, and the honest
# way to resolve it is a marker in the post that says so, rather than loosening
# the rule for everybody. Rare by design: two in forty-four posts.
OPT_OUT = re.compile(r"<!--\s*check_assertions:\s*allow-public-principal")


def code_blocks(body):
    """Code blocks, minus any preceded by an opt-out marker."""
    out = []
    for m in re.finditer(r"<pre><code>([\s\S]*?)</code></pre>", body):
        # 900 rather than 400: the marker sits above the code-block div, and
        # the code-header line between them is itself around 200 characters of
        # span and dot markup. 400 put the marker just outside the window, so
        # the opt-out silently did nothing.
        preceding = body[max(0, m.start() - 900):m.start()]
        if OPT_OUT.search(preceding):
            continue
        out.append(m.group(1))
    return out


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


QUOTE_MARK = "\x01"

# A table with no sentence-ending punctuation flattens into one pseudo-sentence
# hundreds of characters long, and over that distance a cue and a verb co-occur
# by accident rather than by argument. The first version of this rule reported
# 30 findings, and the three sampled were all flattened tables -- "Tradeoffs
# Decision Benefit Cost One CMK per service per account ...". Requiring the two
# to sit in the same clause is what separates a drawn conclusion from two
# unrelated words in the same cell.
CONSEQUENCE_WINDOW = 120


def consequence_span(s):
    """True when a consequence cue and a cost/requirement verb share a clause."""
    for cue in CONSEQUENCE_CUE.finditer(s):
        for verb in CONSEQUENCE_VERB.finditer(s):
            if 0 <= verb.start() - cue.end() <= CONSEQUENCE_WINDOW:
                return True
    return False


def prose_marked(body):
    """prose(), but with quoted spans still identifiable.

    prose() strips every tag, so by the time a sentence reaches the scan loop
    there is no way to tell a vendor quotation from the author's own claim --
    and that distinction is the entire basis of the consequence rule below. So
    the <em> spans are collapsed to a sentinel byte first, which survives the
    tag strip and cannot appear in ordinary text.
    """
    marked = re.sub(r"<em>([\s\S]*?)</em>",
                    QUOTE_MARK + r"\1" + QUOTE_MARK, body)
    return prose(marked)


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

    # Consequences are scanned over the marked text so a quoted sentence can
    # be told from an inferred one. Separate loop rather than another branch
    # above, because the two passes read different strings.
    for sentence in SENTENCE.split(prose_marked(body)):
        s = sentence.strip()
        if not s or QUOTE_MARK in s:
            continue
        if consequence_span(s):
            notes.append(("consequence", s.replace(QUOTE_MARK, "")))
    return name, errors, notes, derives


# --- the controls the note above promises -----------------------------------
#
# That note has said "the controls at the bottom of this file exist" since the
# non-raw-string incident, and until now they did not. The gap was not
# theoretical: check_sources.py had the same shape of hole -- an AWS-only rule
# that reported "0 sourcing gaps" for 31 Azure posts because it had nothing to
# apply -- and Azure #31 went out through it.
#
# So each pattern gets a string it must match and a string it must not. If a
# pattern is edited into inertness, this fails at startup instead of printing a
# clean corpus. Cheap enough to run on every invocation.
CANARIES = [
    (COMPARATIVE, "the reservation is about a third of the price",
     "read that twice before shipping"),
    (ABSOLUTE, "this role depends on nothing outside IAM",
     "the account depends on a pipeline"),
    (CONSEQUENCE_CUE, "So the delivery is billed either way", "delivery billing"),
    (CONSEQUENCE_VERB, "the review is billed twice", "the review completed"),
    (HAS_NUMBER, "costs $4", "costs nothing"),
]


def selftest():
    """Fail loudly if any pattern has stopped matching what it was written for."""
    bad = []
    for pattern, must_match, must_not in CANARIES:
        if not pattern.search(must_match):
            bad.append("pattern no longer matches %r" % must_match)
        if pattern.search(must_not):
            bad.append("pattern now over-matches %r" % must_not)
    if not consequence_span("So a single access review is billed two ways at once"):
        bad.append("consequence_span no longer fires on the Azure #31 sentence")
    if consequence_span("So the team met. " + "x " * 200 + "it is billed monthly"):
        bad.append("consequence_span ignores its proximity window")
    return bad


def main():
    broken = selftest()
    if broken:
        print("check_assertions.py is not checking anything:")
        for b in broken:
            print("   %s" % b)
        return 2

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
