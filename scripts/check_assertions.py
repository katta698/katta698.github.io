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
    r'|\d+(?:\.\d+)?\s*%\s*(?:cheaper|dearer|more|less|below|above|faster|slower)\b'
    # "N% of" is quantification far more often than comparison. Twenty of the
    # forty-two ratio flags were this branch, and not one was a comparative:
    # "99.9% of newly written objects within one hour" is a durability target,
    # "60-80% of S3 data is in the Standard tier" is a population share. A
    # comparative needs something priced on the other side of the "of".
    r'|\d+(?:\.\d+)?\s*%\s*of\s+(?:the\s+|its\s+)?'
    r'(?:price|cost|rate|list|on-demand|budget|spend|bill|charge)\b'
    r'|(?:cheaper|dearer|faster|slower|larger|smaller)\s+by\b'
    # "exactly" was written for "exactly twice" / "exactly 60 percent" -- a
    # stated ratio. Bare "exactly <number>" is a count or a version pin and
    # compares nothing: "four functions at 250 each looks like exactly 1,000"
    # and "pins AVM at exactly 0.10.0" were both flagged and both fine.
    r'|exactly\s+(?:twice|half|double)\b'
    r'|exactly\s+\d+(?:\.\d+)?\s*(?:%|percent|times)\b'
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

# The same construction, in the two places a reader skims rather than reads:
# a heading and a decision-table cell. Those are summary positions, stripped of
# the qualification the body paragraph would carry, and that is where an
# over-claim does its damage.
#
# arch-051 shipped the heading "The forecast alert is the only pre-emptive
# signal" while the same post argues, three paragraphs later, that SCPs and
# quotas "act at provisioning time with no learning period" -- which is to say
# pre-emptively. An external reviewer caught it. ABSOLUTE could not, for two
# reasons worth recording:
#
#   1. Its noun list is closed -- identity, thing, way, mechanism, one, control,
#      answer -- so "signal" and "alert" walked straight past it.
#   2. It only ran under --absolutes, and prepublish.py has never passed that
#      flag. The whole class had never executed in the pipeline.
#
# A closed list behind a flag nobody sets is a checker that cannot fail, which
# this file's own docstring calls worse than no checker.
#
# Scoped to "the only <noun>" in headings and cells because the alternatives
# were measured and rejected: any "the only <noun>" anywhere gives 388 flags
# across 152 posts, and adding "<noun> only" to the summary positions gives 90,
# most of them terse table values like "Parquet only" that assert nothing.
# This gives 60 across 47 posts -- about one post in four, comparable to the
# advisory load already carried.
SUMMARY_ABSOLUTE = re.compile(r'\bthe only \w+', re.I)
SUMMARY_BLOCK = re.compile(
    r'<h[1-6][^>]*>([\s\S]*?)</h[1-6]>|<t[dh][^>]*>([\s\S]*?)</t[dh]>')


def summary_positions(body):
    """Heading and table-cell text: what a reader takes in without reading."""
    out = []
    for m in SUMMARY_BLOCK.finditer(body):
        raw = m.group(1) if m.group(1) is not None else m.group(2)
        text = re.sub(r"<[^>]+>", " ", raw or "")
        text = (text.replace("&mdash;", "-").replace("&ndash;", "-")
                    .replace("&amp;", "&").replace("&nbsp;", " ")
                    .replace("&#8212;", "-").replace("&quot;", '"'))
        text = re.sub(r"&[a-z#0-9]+;", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            out.append(text)
    return out


# Both classes below were added on 2026-09-12, independently, in two windows,
# from the same realisation: the errors that survive verification are the ones
# in the author's own voice. They catch different shapes and both are kept.
#   CONSEQUENCE_* - a conclusion drawn from correct facts (Azure #31).
#   DOC_CLAIM     - a characterisation of what a document says (GCP #30).

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
    r'(?:billed|charged|priced|licen[cs]ed|exempt)\b'
    r'|\b(?:you|teams?|estates?)\s+(?:then\s+)?(?:pay|owe)\b'
    r'|\bcosts? (?:you )?(?:nothing|twice|double)\b'
    # "requires a" alone is any requirement at all. az-024's "crossing between
    # them requires a specific mechanism" is a definition of deployment scopes,
    # not a cost. Name the thing being required.
    r'|\brequires? (?:a |an |two |both )(?:\w+\s+){0,2}'
    r'(?:licen[cs]e|subscription|plan|tier|sku|charge|fee|payment|seat|commitment)\b',
    re.I)

# The same words carry a billing sense and a scope sense, and only the rest of
# the sentence decides which. Three of thirteen consequence flags were the
# scope sense and all three were noise:
#
#   "Associate by Auto Scaling group tag so new instances are covered"  (alarms)
#   "so its coverage is the coverage of your traffic"                   (dry run)
#   "The adjuster is on, so we are covered"                             (quota)
#
# against one that is genuinely about money:
#
#   "$1.00 On-Demand against $0.70 ... so the r5 usage is covered first"
#
# So these fire only with a billing or entitlement term somewhere in the same
# sentence. Entitlement counts as well as money because the docstring's subject
# is "a billing *or eligibility* outcome" -- daily-014's "only to the number a
# role now gets for free" is a quota entitlement and belongs on the list.
AMBIGUOUS_VERB = re.compile(
    r'\b(?:is|are|was|were|gets?|becomes?)\s+(?:\w+\s+){0,2}'
    r'(?:covered|free|required)\b'
    r'|\b(?:you|teams?|estates?)\s+(?:then\s+)?(?:need|must)\b', re.I)
BILLING_CONTEXT = re.compile(
    r'\b(?:billed?|billing|charges?|charged|costs?|cost|price[sd]?|pricing|'
    r'rate|invoice|licen[cs]e[sd]?|licensing|commitment|savings plan|discount|'
    r'on-demand|free tier|quota|limit|maximum|default)\b|\$', re.I)

# A sentence that quotes its source is not an unsupported inference. The quote
# marks the assertion as the vendor's rather than the author's, which is the
# whole distinction this file was written to police.
HAS_QUOTE = re.compile(r'<em>|&ldquo;|"')

# A third class, added 2026-09-12 after GCP arch #30 shipped this sentence:
#
#     "The blueprint assumes a greenfield organisation with no prior
#      commitments."
#
# The enterprise foundations blueprint assumes the opposite. Its own
# authentication page says "We recommend federating your Cloud Identity
# account with your existing identity provider", and its overview offers two
# uses, the second being "To review an existing environment on Google Cloud".
# The post also listed "No existing identity provider" among what the blueprint
# assumes. Both were wrong, and an external reader caught them.
#
# Neither existing class could see it. There is no ratio and no absolute in
# that sentence -- it is a characterisation of what a DOCUMENT assumes or
# omits, which is a different kind of claim from a fact about a product. A
# fact about a product either appears on the cited page or it does not, and
# verify_claims.py settles it. A claim about a page's coverage can only be
# settled by reading the whole page, and the workflow that produced the error
# read excerpts. The reference list even carried the unread page as a link.
#
# Deliberately narrow. The broad version -- any "assumes" or "does not" --
# fires on 23 of the 30 GCP arch posts, which is how a checker gets switched
# off. Scoped to assertions whose subject is a document, it fires on 3 of 30,
# and two of those three are sound. That ratio is what makes it worth reading.
DOC_CLAIM = re.compile(
    r'\b(?:blueprint|guide|documentation|docs|reference|whitepaper|spec)\b'
    r'[^.]{0,70}?\b(?:assumes?|presumes?|expects?|omits?|offers no'
    r'|says nothing|is silent|does not(?: cover| mention| say| support| address)?)\b'
    r'|\b(?:assumes?|presumes?)\b[^.]{0,50}?'
    r'\b(?:blueprint|guide|documentation|docs)\b', re.I)

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
    # A block-level element ends a sentence. HTML carries that boundary in the
    # markup rather than in punctuation, and stripping tags without honouring
    # it flattens a table into one pseudo-sentence hundreds of characters long.
    # Over that distance a cue and a verb co-occur by accident rather than by
    # argument: arch-005's tradeoffs table produced a 1,181-character "sentence"
    # pairing a "so" in one cell with an "are free" in another. CONSEQUENCE_WINDOW
    # narrowed that class but cannot close it, because two words inside one cell
    # are genuinely adjacent. Giving every cell its own boundary keeps the
    # table's content in scope while stopping it from reading as one assertion.
    body = re.sub(r"</(?:td|th|tr|li|p|h[1-6]|div|blockquote|figcaption)>", ". ", body)
    body = re.sub(r"<br\s*/?>", ". ", body)
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
    """True when a consequence cue and a cost/requirement verb share a clause.

    Two verb sets. The unambiguous one fires on its own; the ambiguous one
    needs a billing or entitlement term elsewhere in the sentence, because
    "covered", "free", "required" and "you must" all have a scope sense that
    has nothing to do with money.
    """
    return consequence_clause(s) is not None


def consequence_clause(s):
    """The conclusion half of the sentence, from its cue onward, or None.

    Returned rather than a bare bool so the claim cross-reference can be
    applied to the *conclusion* instead of to the whole sentence. That
    distinction is load-bearing. daily-020 reads:

        "this feature is available in all AWS Regions where Aurora DSQL is
         available, with no separate opt-in and no pricing note, which means
         it is priced as ordinary read and write activity rather than as a
         feature."

    The first half restates a sourced claim verbatim; the second half is an
    unsourced inference about pricing drawn from the *absence* of a pricing
    note. Testing the echo against the whole sentence suppressed it entirely --
    a sourced fact acting as cover for the conclusion bolted onto it, which is
    the exact shape of the Azure #31 error this rule was written for.
    """
    if REPORTED_BELIEF.search(s):
        return None
    verbs = list(CONSEQUENCE_VERB.finditer(s))
    if BILLING_CONTEXT.search(s):
        verbs += list(AMBIGUOUS_VERB.finditer(s))
    for cue in CONSEQUENCE_CUE.finditer(s):
        for verb in verbs:
            if 0 <= verb.start() - cue.end() <= CONSEQUENCE_WINDOW:
                return s[cue.start():]
    return None


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
    # Curly and straight quotes carry the same signal as <em>, and only <em>
    # was ever honoured -- HAS_QUOTE was defined and never called, so the
    # docstring's promise that "a sentence that quotes its source is not an
    # unsupported inference" held for one of the three ways this repo quotes.
    # The challenge cards are the common case: their headers open with a
    # misconception in quotes, so the rule fired on the strawman rather than on
    # the argument that demolishes it two words later.
    #
    #   <strong>"The adjuster is on, so we are covered"</strong>
    #   <strong>"It is managed, so we do not think about state"</strong>
    marked = re.sub(r"&ldquo;([\s\S]{0,500}?)&rdquo;",
                    QUOTE_MARK + r"\1" + QUOTE_MARK, marked)
    text = prose(marked)
    # Straight quotes are marked after the tag strip, never before it: before,
    # every HTML attribute value in the document would match.
    return re.sub(r'"([^"\n]{0,500}?)"', QUOTE_MARK + r"\1" + QUOTE_MARK, text)


# A belief the post attributes to someone -- usually to its own earlier self,
# in order to refute it in the next sentence -- is not an assertion the post is
# making. week-02: "The plan identity was first given roles/viewer at the
# organization, reasoning that a plan only reads, so breadth costs nothing",
# immediately followed by "That reasoning is wrong, and the documentation says
# why". Flagging that is flagging the setup for the correction.
REPORTED_BELIEF = re.compile(
    r'\b(?:reasoning that|on the (?:reasoning|assumption|theory|basis) that'
    r'|the (?:thinking|assumption|argument) (?:was|being)'
    r'|we (?:assumed|thought)|it was assumed|the myth (?:is|was))\b', re.I)


# A sentence that restates a claim the post already sources is not an
# unsupported assertion -- it is the sourced one, written out in prose. The
# checker had no idea, because it never read verified_claims:
#
#   claim:    "The capability runs as AWS Systems Manager Automation runbooks,
#              so you pay standard Automation usage charges for the runbooks
#              you run"                    -> sourced to the What's New page
#   sentence: "It is available in all Regions enabled by default, and it runs
#              as Automation runbooks, so you pay standard Automation usage
#              charges for what you run."  -> flagged as an inference
#
# Eight consecutive words is long enough that an accidental match is not
# credible, and short enough to survive the rewording every post does between
# its claim list and its prose.
CLAIM_ECHO = 8


def _words(s):
    """Word tokens, with decimals kept intact and sentence punctuation dropped.

    The dot has to be inside the character class so "$0.70" survives as one
    token, which means a sentence-final word arrives as "team." while the same
    word quoted in front matter arrives as "team". That one-character
    difference silently defeated a judgements: signature on the last word of
    every sentence -- the failure looked exactly like a signature that had not
    been written. Strip trailing dots only: 0.70 keeps its own.
    """
    return [t for t in (tok.rstrip(".")
                        for tok in re.findall(r"[a-z0-9$.%]+", s.lower())) if t]


def claim_texts(front):
    return [_words(m.group(1))
            for m in re.finditer(r'-\s+claim:\s*"([^"]*)"', front, re.S)]


def _grams(words, n=CLAIM_ECHO):
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def echoes_claim(sentence, claims):
    """True when the sentence shares a long phrase with an existing claim."""
    w = _words(sentence)
    if len(w) < CLAIM_ECHO:
        return False
    grams = _grams(w)
    return any(grams & _grams(c) for c in claims if len(c) >= CLAIM_ECHO)


# --- dispositions ----------------------------------------------------------
#
# The gate this file is built towards does not ask "is this sentence true",
# which no script can answer. It asks "has someone decided about this
# sentence", which is checkable. A flagged sentence is dispositioned two ways:
#
#   * it restates a claim the post already sources  -- echoes_claim(), above
#   * the author signed it as judgement rather than fact:
#
#         judgements:
#           - "so the r5 usage is covered first"
#
# A reviewer cannot correct a judgement, only disagree with it, so a signed
# sentence leaves the factual surface. That is the property VALIDATION.md states
# as the goal: every sentence is either sourced to a page that was actually
# fetched, or visibly a judgement.
#
# Matching is on a contiguous run of words, not a substring, so entity and
# whitespace differences between the front matter and the rendered prose do not
# matter. Editing the sentence *does* lapse the signature, and that is
# deliberate: a sign-off applies to the wording it was given, and reworded prose
# deserves a fresh look rather than an inherited pass.
JUDGEMENTS_BLOCK = re.compile(r'^judgements:\s*\n((?:[ \t]*-[ \t]+.*\n?)+)', re.M)


def judgement_texts(front):
    m = JUDGEMENTS_BLOCK.search(front)
    if not m:
        return []
    out = []
    for line in m.group(1).splitlines():
        t = line.strip()
        if not t.startswith("-"):
            continue
        t = t[1:].strip()
        if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'":
            t = t[1:-1]
        if t:
            out.append(_words(t))
    return out


def _contains_run(hay, needle):
    if not needle or len(needle) > len(hay):
        return False
    return any(hay[i:i + len(needle)] == needle
               for i in range(len(hay) - len(needle) + 1))


def signed_judgement(sentence, judgements):
    w = _words(sentence)
    return any(_contains_run(w, j) for j in judgements)


def series_of(name):
    for key, spec in SERIES.items():
        if name.startswith(spec["file_prefix"]):
            return key
    return None


# Scan by default; skip only what is declared out of scope. The old default was
# the other way round -- a filename matching no file_prefix in SERIES was
# skipped, silently, and the run still printed a clean summary. That hid 41
# technical posts: the whole 30-post "30 Days of AWS Terraform" series plus
# Oracle, MongoDB, SQL Server, MariaDB and Azure cost write-ups. 17% of the
# corpus, carrying AWS content and no badge, checked by nothing.
#
# It is the same shape as the bug this window was opened for -- check_sources.py
# reporting "0 findings" for 31 Azure posts it had no rule for -- and it recurred
# because *absence of registration* was the skip condition. An exception has to
# be declared to be honoured, so a series nobody registers now gets scanned
# rather than ignored, and the next one inherits coverage instead of a hole.
#
# The non-technical posts are genuinely out of scope: no vendor facts, nothing
# to cite, and validate_arch_post.py matches no series for them either. They are
# excluded on their labels, which are explicit and visible in the front matter.
NON_TECHNICAL = {
    "Health", "Life", "Career", "Personal Growth", "Financial Thinking",
}
LABEL_LINE = re.compile(r'^\s*-\s+"?([^"\n]+?)"?\s*$', re.M)

UNREGISTERED = "(unregistered)"


def in_scope(name, front):
    """The series key, '(unregistered)', or None when out of scope."""
    key = series_of(name)
    if key:
        return key
    labels_block = re.search(r'^labels:\s*\n((?:\s*-\s+.*\n?)+)', front, re.M)
    if labels_block:
        labels = {m.group(1).strip()
                  for m in LABEL_LINE.finditer(labels_block.group(1))}
        if labels & NON_TECHNICAL:
            return None
    return UNREGISTERED


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
    claims = claim_texts(front)
    judgements = judgement_texts(front)
    text = prose(body)
    for sentence in SENTENCE.split(text):
        s = sentence.strip()
        if not s:
            continue
        m = COMPARATIVE.search(s)
        if m and HAS_NUMBER.search(s):
            # Scoped to the comparative, for the same reason as the consequence
            # clause: a claim quoted elsewhere in the sentence must not excuse
            # the ratio drawn on top of it.
            near = s[max(0, m.start() - 60):m.end() + 60]
            if not echoes_claim(near, claims):
                notes.append(("ratio", s, signed_judgement(s, judgements)))
        elif DOC_CLAIM.search(s):
            # A characterisation of what a document says or assumes. Kept whole
            # rather than scoped: the assertion IS about the page's coverage, so
            # there is no sub-span that carries it, and a claim quoting the page
            # is exactly what would settle it.
            if not echoes_claim(s, claims):
                notes.append(("doc-claim", s, signed_judgement(s, judgements)))
        elif (CONSEQUENCE_CUE.search(s) and CONSEQUENCE_VERB.search(s)
              and not HAS_QUOTE.search(s)):
            if not echoes_claim(s, claims):
                notes.append(("inference", s, signed_judgement(s, judgements)))
        elif show_absolutes and ABSOLUTE.search(s):
            notes.append(("absolute", s, signed_judgement(s, judgements)))

    # Consequences are scanned over the marked text so a quoted sentence can
    # be told from an inferred one. Separate loop rather than another branch
    # above, because the two passes read different strings.
    for sentence in SENTENCE.split(prose_marked(body)):
        s = sentence.strip()
        if not s or QUOTE_MARK in s:
            continue
        clause = consequence_clause(s)
        if clause and not echoes_claim(clause, claims):
            bare = s.replace(QUOTE_MARK, "")
            notes.append(("consequence", bare,
                          signed_judgement(bare, judgements)))

    # Absolutes in the positions a reader skims. Runs unconditionally: the
    # --absolutes flag stays for the noisier prose-wide sweep, but the summary
    # positions are where this class has actually shipped wrong.
    for text in summary_positions(body):
        if SUMMARY_ABSOLUTE.search(text) and not echoes_claim(text, claims):
            notes.append(("absolute", text, signed_judgement(text, judgements)))
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
    # The tightened branches, each against the sentence that motivated it.
    (COMPARATIVE, "$1.20 against $1.50 is 20% below the smallest",
     "99.9% of newly written objects land within one hour"),
    (COMPARATIVE, "the SCP budget is exactly twice the RCP budget",
     "four functions at 250 each looks like exactly 1,000"),
    (COMPARATIVE, "the boundary has exactly 60 percent of the budget",
     "the wrapper pins the module at exactly 0.10.0"),
    (ABSOLUTE, "this role depends on nothing outside IAM",
     "the account depends on a pipeline"),
    # The noun after "the only" is open on purpose: a closed list is what let
    # "the only pre-emptive signal" and "the only alert" through.
    (SUMMARY_ABSOLUTE, "the forecast alert is the only pre-emptive signal",
     "forecast alerts warn before spend accrues"),
    (CONSEQUENCE_CUE, "So the delivery is billed either way", "delivery billing"),
    (CONSEQUENCE_VERB, "the review is billed twice", "the review completed"),
    (CONSEQUENCE_VERB, "so it requires a licence for each guest",
     "crossing between them requires a specific mechanism"),
    (AMBIGUOUS_VERB, "the r5 usage is covered first", "the runbook finished"),
    (BILLING_CONTEXT, "billed against the commitment", "the instances are tagged"),
    (REPORTED_BELIEF, "reasoning that a plan only reads",
     "the reason is documented on that page"),
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

    # The ambiguous verbs must stay sensitive to their billing context: the
    # same word decides a false positive and a true one.
    if not consequence_span("$1.00 On-Demand against $0.70, so the r5 usage "
                            "is covered first"):
        bad.append("consequence_span lost the billing sense of 'covered'")
    if consequence_span("Associate by Auto Scaling group tag so new instances "
                        "are covered automatically"):
        bad.append("consequence_span still fires on the scope sense of 'covered'")
    if consequence_span("reasoning that a plan only reads, so breadth costs "
                        "nothing"):
        bad.append("consequence_span still fires on a reported belief")

    # A block boundary must end a sentence, or tables flatten again.
    if len(SENTENCE.split(prose("<td>so the key</td><td>rotations are free</td>"))) < 2:
        bad.append("prose() no longer splits sentences on block boundaries")

    # Quote marking must survive all three of the ways this repo quotes.
    for markup in ('<em>so it is billed twice</em>',
                   '&ldquo;so it is billed twice&rdquo;',
                   '<strong>"so it is billed twice"</strong>'):
        if QUOTE_MARK not in prose_marked(markup):
            bad.append("prose_marked does not mark %s" % markup)

    # The claim cross-reference must match a reworded restatement and must not
    # match an unrelated sentence that happens to share short phrases.
    claim = [_words("The capability runs as AWS Systems Manager Automation "
                    "runbooks, so you pay standard Automation usage charges "
                    "for the runbooks you run")]
    if not echoes_claim("It runs as Automation runbooks, so you pay standard "
                        "Automation usage charges for what you run.", claim):
        bad.append("echoes_claim no longer recognises a restated claim")
    if echoes_claim("The runbooks are listed in the console.", claim):
        bad.append("echoes_claim over-matches on a short overlap")

    # A sourced fact must not launder the inference bolted onto it. This is the
    # daily-020 regression: the first cut tested the echo against the whole
    # sentence, so a verbatim claim in the first half suppressed an unsourced
    # pricing conclusion in the second -- the Azure #31 shape exactly.
    dsql = [_words("This feature is available in all AWS Regions where Aurora "
                   "DSQL is available")]
    laundered = ("this feature is available in all AWS Regions where Aurora "
                 "DSQL is available, with no separate opt-in and no pricing "
                 "note, which means it is priced as ordinary read and write "
                 "activity rather than as a feature")
    clause = consequence_clause(laundered)
    if clause is None:
        bad.append("consequence_clause no longer fires on the daily-020 sentence")
    elif echoes_claim(clause, dsql):
        bad.append("a sourced first half still suppresses an unsourced conclusion")

    # The disposition mechanism has to recognise a signature, and has to lose it
    # when the sentence it was given is reworded.
    signed = judgement_texts(
        'judgements:\n  - "so the r5 usage is covered first"\n')
    if not signed:
        bad.append("judgement_texts no longer parses a judgements: block")
    elif not signed_judgement(
            "AWS's worked example has r5 at 30%, so the r5 usage is covered "
            "first even across teams.", signed):
        bad.append("signed_judgement no longer honours a signature")
    elif signed_judgement("so the Fargate usage is covered first", signed):
        bad.append("signed_judgement matches a sentence it was not given")

    # Scope must be scan-by-default. If this inverts again, 41 technical posts
    # go quiet and the summary still reads clean.
    if in_scope("day-12-terraform-functions-part-2.html",
                "labels:\n  - AWS\n  - Terraform\n") != UNREGISTERED:
        bad.append("an unregistered technical post is no longer scanned")
    if in_scope("some-reflection.html", "labels:\n  - Life\n") is not None:
        bad.append("a non-technical post is being scanned")
    if in_scope("arch-050-x.html", "labels:\n  - AWS\n") != "arch":
        bad.append("a registered series no longer resolves to its key")

    # Summary positions must be extracted from both headings and cells, and the
    # class must run without a flag. It never did before arch-051.
    found = summary_positions(
        "<h3>The forecast alert is the only pre-emptive signal</h3>"
        "<td>Central enforcement</td><p>the only thing in a paragraph</p>")
    if len(found) != 2:
        bad.append("summary_positions no longer reads headings and cells")
    elif any("paragraph" in f for f in found):
        bad.append("summary_positions is reaching into body prose")
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
    ap.add_argument("--strict", action="store_true",
                    help="fail on any assertion that has not been dispositioned "
                         "-- either sourced by a claim or signed in judgements:")
    ap.add_argument("--backlog", action="store_true",
                    help="per-series count of what --strict would fail on, "
                         "which is the work before the gate can be turned on")
    args = ap.parse_args()

    paths = []
    if args.posts:
        for p in args.posts:
            paths += sorted(glob.glob(os.path.join(POSTS, p + "*.html")))
    elif args.series:
        pre = SERIES[args.series]["file_prefix"]
        paths += sorted(glob.glob(os.path.join(POSTS, pre + "*.html")))
    else:
        # Every post, not every registered prefix. See in_scope().
        paths = sorted(glob.glob(os.path.join(POSTS, "*.html")))
    paths = sorted(set(paths))

    failed = 0
    flagged = 0
    undisposed = 0
    by_series = {}
    skipped = 0
    unregistered = 0
    for path in paths:
        _, front = body_and_front(path)
        key = in_scope(os.path.basename(path), front)
        if not key:
            skipped += 1
            continue
        if key == UNREGISTERED:
            unregistered += 1
        name, errors, notes, derives = check(path, args.absolutes)
        open_here = sum(1 for n in notes if not n[2])
        if open_here:
            tally = by_series.setdefault(key, [0, 0])
            tally[0] += open_here
            tally[1] += 1
        if args.backlog:
            undisposed += open_here
            flagged += len(notes)
            failed += len(errors)
            continue
        if not errors and not notes:
            continue
        print("\n%s" % name)
        for message in errors:
            failed += 1
            print("   ERROR  example code: %s" % message)
        for kind, sentence, disposed in notes:
            flagged += 1
            if not disposed:
                undisposed += 1
            trimmed = sentence if len(sentence) <= 150 else sentence[:147] + "..."
            print("   %-8s %s%s" % (kind + ":", "[signed] " if disposed else "",
                                    trimmed))
        if notes:
            print("            (post has %d derive claim%s)"
                  % (derives, "" if derives == 1 else "s"))

    if args.backlog:
        print("\nUndispositioned assertions -- what --strict would fail on today")
        print("%-14s %8s %8s" % ("series", "open", "posts"))
        print("-" * 32)
        for key in sorted(by_series, key=lambda k: -by_series[k][0]):
            n, posts = by_series[key]
            print("%-14s %8d %8d" % (key, n, posts))
        print("-" * 32)
        print("%-14s %8d %8d" % ("TOTAL", undisposed,
                                 sum(v[1] for v in by_series.values())))
        print("\nEach one needs either a verified_claims entry that sources it,")
        print("or a judgements: line signing it as the author's judgement.")
        return 0

    print("\nChecked %d post(s): %d code defect(s), %d assertion(s) to eyeball, "
          "%d undispositioned."
          % (len(paths) - skipped, failed, flagged, undisposed))
    if skipped:
        print("Skipped %d non-technical post(s) -- no vendor facts to check."
              % skipped)
    if unregistered:
        # Named rather than silent: these are scanned, but nothing else knows
        # about them. No SERIES entry means no doc_hosts, so verify_claims.py
        # and validate_arch_post.py still cannot see them.
        print("%d scanned post(s) have no SERIES entry. They are checked for "
              "assertions only -- no claim verification, no source rules."
              % unregistered)
    if flagged and not failed:
        print("Assertions are advisory. Each ratio needs a derive claim behind "
              "it; each doc-claim needs a verified_claim on the page it "
              "characterises, or a reason it does not need one.")
    if args.strict and undisposed:
        print("\n--strict: %d assertion(s) carry neither a source nor a "
              "judgements: signature." % undisposed)
        return 1
    return 1 if failed else 0


# Every pattern in this file is one bad escape away from matching nothing, and
# a checker that matches nothing reports a clean corpus. That happened twice:
# once to COMPARATIVE (see its comment) and once to DOC_CLAIM on the day it was
# added, when a word-boundary escape arrived in the file as a literal backspace byte instead and all eight
# cases below passed as "quiet". The fix is that the checker now proves it can
# still see, on demand and in CI, rather than being trusted to.
SELF_TEST = [
    # (should_flag, sentence)
    (True,  "The blueprint assumes a greenfield organisation with no prior commitments."),
    (True,  "The blueprint's stage 1 presumes groups it can create."),
    (True,  "The documentation does not cover what happens on delete."),
    (False, "A policy page shows intent; it does not show the estate."),
    (False, "Asset history is kept for 35 days and folders are not supported."),
    (False, "This assumes you have already read post 29."),
    # Intentionally quiet: HAS_NUMBER requires a numeral, which is what stops
    # "read that twice" flagging. A wordy ratio with no digit is a known gap.
    (False, "Athena reservations are about a third of the price of Redshift Serverless."),
    (True,  "An Athena reservation is 20% below the smallest Redshift Serverless capacity."),
    (False, "Read that twice before running it in production."),
    # The inference class, from the Azure #31 sentence that motivated it.
    (True,  "So a single access review spanning employees and partners is "
            "billed two ways at once."),
    # A quotation is the vendor's assertion, not the author's, so it is exempt.
    (False, "Microsoft says guests &ldquo;are billed only for capabilities "
            "exclusive to ID Governance&rdquo;."),
]


def self_test():
    """Prove the patterns still match. Returns an exit code."""
    bad = 0
    for want, sentence in SELF_TEST:
        if COMPARATIVE.search(sentence) and HAS_NUMBER.search(sentence):
            got = True
        elif DOC_CLAIM.search(sentence):
            got = True
        else:
            got = bool(CONSEQUENCE_CUE.search(sentence)
                       and CONSEQUENCE_VERB.search(sentence)
                       and not HAS_QUOTE.search(sentence))
        if got != want:
            bad += 1
            print("   FAIL  expected flag=%s: %s" % (want, sentence))
    if chr(8) in io.open(__file__, encoding="utf-8").read():
        bad += 1
        print("   FAIL  this file contains a literal backspace byte -- a %sb "
              "was written through a non-raw string and the pattern is dead"
              % chr(92))
    print("self-test: %d of %d case(s) behave as intended"
          % (len(SELF_TEST) - bad, len(SELF_TEST)))
    return 1 if bad else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    sys.exit(main())
