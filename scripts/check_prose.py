#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Catch retired product names and misspellings in post prose.

    python scripts/check_prose.py                 # every series
    python scripts/check_prose.py --series az     # one series
    python scripts/check_prose.py az-002          # one post
    python scripts/check_prose.py --list          # show the rename table

Why this exists
---------------
Two gaps that nothing else on this site covers, both of which damage a post in
the way a reader notices first.

**Retired names.** Cloud vendors rename things constantly, and a post using the
old name reads as written from memory rather than from the current docs --
which is exactly what the verification badge claims it was not. "Azure Active
Directory" in a 2026 post is not a typo, it is a signal that the author did not
open the page they cited.

**Misspellings.** There was no spellcheck of any kind in this pipeline. A full
dictionary is the wrong tool: technical prose is full of legitimate words no
dictionary has, and a checker that cries wolf on "Bicep", "kubelet" and "IOPS"
gets switched off within a week. So this uses a curated list of *known* wrong
spellings, in the style of codespell -- every hit is a real error, and the
false-positive rate is zero by construction. It will miss novel typos. That is
the trade, and it is the right one for a check that has to survive daily use.

Renames that a post is legitimately explaining
----------------------------------------------
A post about the Entra rename has to say "Azure Active Directory". So an old
name is allowed when the current name appears within RENAME_WINDOW characters
of it -- close enough that the sentence is plainly drawing the comparison. A
post can also opt out per-name in its front matter:

    allow_legacy_names:
      - Azure Active Directory
"""
import argparse
import io
import os
import re
import sys

import yaml

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS = os.path.join(ROOT, "posts")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validate_arch_post import SERIES                          # noqa: E402

# How close the current name has to be for an old name to read as a deliberate
# comparison rather than a stale habit.
RENAME_WINDOW = 140

# Retired name -> current name. Only renames that are settled and unambiguous.
# Names still in flux are deliberately absent: a check that fires on a name the
# vendor itself uses inconsistently is worse than no check.
RENAMES = [
    # Microsoft
    (r"Azure Active Directory", "Microsoft Entra ID"),
    (r"\bAzure AD\b", "Microsoft Entra ID"),
    (r"\bAAD\b", "Microsoft Entra ID"),
    (r"Azure AD B2C", "Microsoft Entra External ID"),
    (r"Azure AD Connect", "Microsoft Entra Connect"),
    (r"Azure Sentinel", "Microsoft Sentinel"),
    (r"Azure Security Center", "Microsoft Defender for Cloud"),
    (r"Azure Defender", "Microsoft Defender for Cloud"),
    (r"Azure Stack HCI", "Azure Local"),
    (r"Azure AI Studio", "Azure AI Foundry"),
    (r"Azure Data Lake Store\b(?! Gen)", "Azure Data Lake Storage Gen2"),
    (r"Azure Log Analytics\b(?! workspace)", "Azure Monitor Logs"),
    # AWS
    (r"Amazon Elasticsearch Service", "Amazon OpenSearch Service"),
    (r"AWS Single Sign-On", "AWS IAM Identity Center"),
    (r"\bAWS SSO\b", "AWS IAM Identity Center"),
    (r"Amazon Simple Storage Service Glacier", "Amazon S3 Glacier"),
    # Google Cloud
    (r"\bStackdriver\b", "Google Cloud Operations Suite"),
    (r"Google Container Engine", "Google Kubernetes Engine"),
    (r"\bAnthos\b", "GKE Enterprise"),
    (r"Cloud Identity-Aware Proxy", "Identity-Aware Proxy"),
]

# Known-wrong spellings only. Every entry is an error whenever it appears, so a
# hit never needs judgement. Grouped by how they got here.
MISSPELLINGS = {
    # the ones that actually turn up in cloud writing
    "avaliable": "available", "availabe": "available", "availble": "available",
    "seperate": "separate", "seperately": "separately",
    "occured": "occurred", "occurence": "occurrence", "occuring": "occurring",
    "recieve": "receive", "recieved": "received",
    "acheive": "achieve", "acheived": "achieved",
    "accross": "across", "adress": "address", "adressed": "addressed",
    "allready": "already", "alot": "a lot", "arguement": "argument",
    "authentification": "authentication",
    "begining": "beginning", "beleive": "believe",
    "calender": "calendar", "cancelation": "cancellation",
    "compatability": "compatibility", "compatiable": "compatible",
    "consistant": "consistent", "consistancy": "consistency",
    "definately": "definitely", "dependancy": "dependency",
    "dependant": "dependent", "deprecrated": "deprecated",
    "descriptior": "descriptor", "diferent": "different",
    "enviroment": "environment", "enviornment": "environment",
    "existant": "existent", "explicitely": "explicitly",
    "extention": "extension", "guaranteee": "guarantee",
    "hierachy": "hierarchy", "heirarchy": "hierarchy",
    "immediatly": "immediately", "independant": "independent",
    "infrastucture": "infrastructure", "infrastrucure": "infrastructure",
    "inital": "initial", "initialise": "initialize",
    "invalidatation": "invalidation", "issueing": "issuing",
    "lenght": "length", "maintainance": "maintenance", "maintenence": "maintenance",
    "managable": "manageable", "neccessary": "necessary", "necesary": "necessary",
    "noticable": "noticeable", "occassion": "occasion",
    "paramter": "parameter", "parametrs": "parameters",
    "particulary": "particularly", "perfomance": "performance",
    "performace": "performance", "persistant": "persistent",
    "priviledge": "privilege", "priviliges": "privileges",
    "propogate": "propagate", "propogation": "propagation",
    "recomend": "recommend", "recomended": "recommended",
    "refered": "referred", "refering": "referring",
    "relevent": "relevant", "reponse": "response", "reponsible": "responsible",
    "retreive": "retrieve", "retrive": "retrieve",
    "seperation": "separation", "similiar": "similar",
    "specifc": "specific", "sucessful": "successful", "succesful": "successful",
    "supress": "suppress", "supressed": "suppressed",
    "targetting": "targeting", "teh": "the", "temperary": "temporary",
    "threshhold": "threshold", "throughtput": "throughput",
    "tolerence": "tolerance", "transfered": "transferred",
    "unfortunatly": "unfortunately", "untill": "until",
    "usefull": "useful", "verfiy": "verify", "wich": "which",
    "witout": "without", "writen": "written",
}

# Deliberately [ \t] rather than \s: prose() puts a newline where a tag was, so
# a doubled word must be doubled *within* one element. Two adjacent table cells
# ending and starting with "it" are not a repeat, and treating them as one
# reported every decision table on the site.
DOUBLED_RE = re.compile(
    r"\b(the|a|an|and|is|are|was|were|of|to|in|on|for|that|this|it|as|at|be)"
    r"[ \t]+\1\b", re.I)

# A rename is often explained using the short form of the current name -- "IAM
# Identity Center (renamed from AWS Single Sign-On)" never repeats the "AWS".
# So the proximity check accepts the name with a leading vendor word dropped.
VENDOR_PREFIX_RE = re.compile(r"^(AWS|Azure|Microsoft|Google|Amazon|Google Cloud)\s+")

TAGS_RE = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)


def prose(raw):
    """Body prose only: no front matter, no markup, no code, no URLs.

    Code and URLs are excluded deliberately -- `az ad sp list` is not a
    misspelling of anything, and a slug containing "seperate" would be a URL
    that has to stay wrong.
    """
    body = raw.split("---", 2)[2] if raw.startswith("---") else raw
    body = TAGS_RE.sub(" ", body)
    # A newline, not a space, for the same reason as the element boundary
    # below: removing a code span joins the words either side of it, and a
    # space lets them read as adjacent prose when they are not. This reported
    # daily-008 as having a doubled word for "and <code>FAILED</code> and
    # <code>EXPIRED</code> ones count" -- a correct sentence, flagged because
    # the two <code> spans were deleted into nothing and the two "and"s landed
    # side by side. A false positive is worse here than a miss: the whole
    # premise of this checker is that every hit is real and needs no judgement.
    # Match the opening tag with any attributes. `<code>` alone misses
    # `<code class="inline">`, which is what the house style actually emits --
    # so every attributed code span leaked its contents into "prose" and was
    # checked as if it were English. That is how `aws sso login` came to be
    # reported as the retired product name "AWS SSO": it is a CLI command, the
    # rename would break it, and the rule was never meant to see it.
    body = re.sub(r"<code\b[^>]*>.*?</code>", "\n", body, flags=re.S)
    body = re.sub(r"<pre\b[^>]*>.*?</pre>", "\n", body, flags=re.S)
    body = re.sub(r"https?://\S+", "\n", body)
    # A newline, not a space: an element boundary is a break between phrases,
    # and collapsing it hides that from the doubled-word check.
    body = re.sub(r"<[^>]+>", "\n", body)
    body = re.sub(r"[ \t]+", " ", body)
    return re.sub(r"\n{2,}", "\n", body)


def check(path):
    raw = io.open(path, encoding="utf-8").read()
    fm = {}
    if raw.startswith("---"):
        try:
            fm = yaml.safe_load(raw.split("---", 2)[1]) or {}
        except Exception:                                      # noqa: BLE001
            fm = {}
    allowed = [str(x) for x in (fm.get("allow_legacy_names") or [])]
    text = prose(raw)
    found = []

    for pattern, current in RENAMES:
        for m in re.finditer(pattern, text, re.I):
            old = m.group(0)
            if any(a.lower() in old.lower() or old.lower() in a.lower()
                   for a in allowed):
                continue
            near = text[max(0, m.start() - RENAME_WINDOW):
                        m.end() + RENAME_WINDOW].lower()
            short = VENDOR_PREFIX_RE.sub("", current).lower()
            if current.lower() in near or short in near:
                continue                     # the post is explaining the rename
            found.append(("RENAMED", old, current,
                          text[max(0, m.start() - 55):m.end() + 55].strip()))

    for m in re.finditer(r"[A-Za-z']+", text):
        w = m.group(0).lower()
        if w in MISSPELLINGS:
            found.append(("SPELLING", m.group(0), MISSPELLINGS[w],
                          text[max(0, m.start() - 55):m.end() + 55].strip()))

    for m in DOUBLED_RE.finditer(text):
        found.append(("DOUBLED", m.group(0), m.group(1),
                      text[max(0, m.start() - 55):m.end() + 55].strip()))
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("posts", nargs="*")
    ap.add_argument("--series", help="one of: %s" % ", ".join(sorted(SERIES)))
    ap.add_argument("--list", action="store_true", help="print the rename table")
    args = ap.parse_args()

    if args.list:
        print("%-42s %s" % ("RETIRED", "CURRENT"))
        for pattern, current in RENAMES:
            print("%-42s %s" % (pattern.replace("\\b", ""), current))
        print("\n%d misspellings tracked" % len(MISSPELLINGS))
        return 0

    specs = SERIES if not args.series else {args.series: SERIES[args.series]}
    files = []
    for _key, spec in sorted(specs.items()):
        for f in sorted(os.listdir(POSTS)):
            if f.startswith(spec["file_prefix"]) and f.endswith(".html"):
                files.append(os.path.join(POSTS, f))
    if args.posts:
        files = [p for p in files
                 if any(a in os.path.basename(p) for a in args.posts)]

    total = 0
    for path in sorted(set(files)):
        hits = check(path)
        if not hits:
            continue
        total += len(hits)
        print("\n%s" % os.path.basename(path))
        for kind, found, want, context in hits:
            print("  [%s] %r -> %r" % (kind, found, want))
            print("      ...%s..." % context)

    print("\nChecked %d post(s): %d issue(s)." % (len(set(files)), total))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
