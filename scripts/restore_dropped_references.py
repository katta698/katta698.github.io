#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Put back the reference links that the Master Standard restructure dropped.

WHY THIS EXISTS (2026-10-29)
----------------------------
The restructure condensed each post's References list along with everything
else. That was fine for prose and wrong for citations: a post's
`verified_claims:` front matter records which page was checked for each claim,
and `validate_arch_post.py` requires every cited URL to also be reachable from
the post's own References list -- otherwise the verification badge asserts a
check the reader cannot repeat.

Eleven restructured posts (weeks 13-23) lost at least one cited page that way.
Week 14 lost six, including the CloudWatch and Athena pricing pages behind nine
separate cost claims.

The link text is NOT written here. It is lifted verbatim from the post's own
pre-restructure version -- the last commit in which the References heading was
still an <h2> -- so a restored entry says what the author originally said about
that page. A URL with no recoverable wording is reported and skipped rather
than given invented text.

Idempotent: a URL already present in the References list is left alone.
"""
from __future__ import annotations

import io
import os
import re
import subprocess
import sys

POSTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "posts")

REF_HEADING = re.compile(r"<h3>References</h3>\s*<ul>(.*?)</ul>", re.S)
OLD_REF = re.compile(r"<h2>References</h2>\s*<ul>(.*?)</ul>", re.S)


def norm(u):
    return u.rstrip("/").replace("&amp;", "&")


def claim_sources(text):
    """The URLs the verification badge says were checked."""
    fm = text.split("---", 2)[1] if text.count("---") >= 2 else ""
    return [norm(m) for m in re.findall(r"^\s*source:\s*(\S+)", fm, re.M)]


def anchor_text(block, url):
    """The post's own wording for a link, from an old References block.

    The anchor pattern must tolerate attributes after the href. Older posts
    write `<a href="..." target="_blank" rel="noopener">`, and a pattern
    demanding `">` immediately after the URL matched none of them -- which
    looked exactly like "this citation was never listed" and would have left
    three of week 18's dropped references out on those grounds.
    """
    for m in re.finditer(r'<a href="([^"]+)"[^>]*>(.*?)</a>', block, re.S):
        if norm(m.group(1)) == url:
            return m.group(2).strip()
    return None


def _git(args, cwd):
    """git output as text. Decoded as UTF-8 explicitly: these posts contain
    em-dashes and middots, and Python's default on this machine is cp1252,
    which raises on the first one."""
    p = subprocess.run(["git"] + args, cwd=cwd, capture_output=True)
    if p.returncode != 0:
        return None
    return p.stdout.decode("utf-8", "replace")


def old_version(path):
    """The last committed version whose References heading was still an <h2>."""
    root = os.path.dirname(POSTS)
    rel = os.path.relpath(path, root).replace(os.sep, "/")
    revs = (_git(["log", "--format=%H", "--", rel], root) or "").split()
    for rev in revs:
        blob = _git(["show", "%s:%s" % (rev, rel)], root)
        if not blob:
            continue
        m = OLD_REF.search(blob)
        if m:
            return m.group(1)
    return None


# Pages that no AWS lab post has ever named in a References list, so there is no
# authored wording to recover. The label is the page's OWN <title>, fetched
# 2026-10-29 and trimmed of the site-name suffix AWS appends ("- Amazon EKS",
# "- AWS WAF, AWS Firewall Manager, ..."). Taking the title rather than writing a
# description keeps the entry checkable: it is what the page calls itself.
TITLES = {
    "https://aws.amazon.com/blogs/security/aws-shield-threat-landscape-review-2020-year-in-review":
        "AWS Shield threat landscape review: 2020 year-in-review",
    "https://docs.aws.amazon.com/waf/latest/developerguide/aws-managed-rule-groups-baseline.html":
        "Baseline rule groups",
    "https://docs.aws.amazon.com/waf/latest/developerguide/limits.html":
        "AWS WAF quotas",
    "https://aws.amazon.com/ec2/pricing/on-demand":
        "EC2 On-Demand Instance Pricing",
    "https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-lake-service-availability-change.html":
        "CloudTrail Lake availability change",
    "https://aws.amazon.com/lightsail/pricing":
        "Amazon Lightsail Pricing",
    "https://docs.aws.amazon.com/eks/latest/userguide/argocd.html":
        "Continuous Deployment with Argo CD",
    "https://docs.aws.amazon.com/eks/latest/userguide/create-argocd-capability.html":
        "Create an Argo CD capability",
    "https://aws.amazon.com/inspector/pricing":
        "Pricing &mdash; Amazon Inspector",
    "https://docs.aws.amazon.com/AmazonECR/latest/userguide/doc-history.html":
        "Document history &mdash; Amazon ECR",
}

_WORDING = None


def wording_index(files):
    """URL -> the shortest wording the AWS lab series itself has used for it.

    A post that lost a citation often shares that citation with another week:
    the CloudWatch pricing page is cited by six labs and named in several of
    their References lists. Borrowing wording from a sibling post keeps the
    restored entry in the author's own words.

    Shortest wins because the long forms carry a post-specific trailing clause
    ("-- the version table, including the v11 tag"), which would be a false
    statement about why a different week cited the page. The bare link text is
    the part that travels.
    """
    global _WORDING
    if _WORDING is not None:
        return _WORDING
    _WORDING = {}
    for fn in files:
        path = os.path.join(POSTS, fn)
        blocks = []
        text = io.open(path, encoding="utf-8").read()
        m = REF_HEADING.search(text)
        if m:
            blocks.append(m.group(1))
        old = old_version(path)
        if old:
            blocks.append(old)
        for b in blocks:
            for a in re.finditer(r'<a href="([^"]+)"[^>]*>(.*?)</a>', b, re.S):
                url, label = norm(a.group(1)), a.group(2).strip()
                # A label that is itself markup-heavy or a bare URL is no help.
                if not label or label.startswith("http") or len(label) > 80:
                    continue
                if url not in _WORDING or len(label) < len(_WORDING[url]):
                    _WORDING[url] = label
    return _WORDING


def repair(path, apply_it, index=None):
    text = io.open(path, encoding="utf-8").read()
    m = REF_HEADING.search(text)
    if not m:
        return None, "no <h3>References</h3> list"

    present = {norm(u) for u in re.findall(r'href="([^"]+)"', m.group(1))}
    wanted = [u for u in claim_sources(text)
              if u.startswith("https://") and u not in present]
    # de-duplicate, keep first-cited order
    seen, missing = set(), []
    for u in wanted:
        if u not in seen:
            seen.add(u)
            missing.append(u)
    if not missing:
        return [], None

    old = old_version(path)
    rows, unresolved = [], []
    for u in missing:
        label = anchor_text(old, u) if old else None
        if not label and index:
            label = index.get(u)
        if not label:
            label = TITLES.get(u)
        if not label:
            unresolved.append(u)
            continue
        rows.append('      <li><a href="%s">%s</a></li>' % (u, label))

    if rows and apply_it:
        block = m.group(1).rstrip()
        new = m.group(0).replace(block, block + "\n" + "\n".join(rows), 1)
        io.open(path, "w", encoding="utf-8", newline="\n").write(
            text[:m.start()] + new + text[m.end():])

    return [len(rows), unresolved], None


def main():
    apply_it = "--apply" in sys.argv
    names = [a for a in sys.argv[1:] if not a.startswith("--")]

    # AWS lab posts only. The three clouds share the 'week-NN-' filename shape
    # in one posts/ directory, and separate agents own the Azure and GCP series
    # -- a first run reached into eight GCP posts before this filter existed.
    # The series lives in the front matter's labels list, not the filename.
    files = []
    for fn in sorted(os.listdir(POSTS)):
        if not (fn.startswith("week-") and fn.endswith(".html")):
            continue
        if names and not any(n in fn for n in names):
            continue
        # Read the WHOLE file, not a prefix. A 4000-byte head skipped every post
        # whose front matter is longer than that -- which is exactly the posts
        # with the most verified_claims, and so the ones most likely to have
        # lost a citation. Eight of eleven affected posts went silently missing.
        whole = io.open(os.path.join(POSTS, fn), encoding="utf-8").read()
        if whole.count("---") < 2:
            print("  [skip] %-52s no front matter" % fn)
            continue
        if "AWS Weekly Lab" in whole.split("---", 2)[1]:
            files.append(fn)
    if not files:
        print("NOTHING MATCHED %s -- a run that touched no post has not passed."
              % ", ".join(names or ["posts/"]))
        return 1

    # Say how many posts the filter actually admitted. The count is the only
    # visible symptom when a filter silently drops the posts that matter.
    print("%d AWS Weekly Lab post(s) considered." % len(files))

    touched = 0
    for fn in files:
        res, why = repair(os.path.join(POSTS, fn), apply_it,
                          wording_index(files))
        if why:
            print("  [skip] %-52s %s" % (fn, why))
            continue
        added, unresolved = res if res else (0, [])
        if not added and not unresolved:
            continue
        touched += 1
        print("  [%s] %-52s +%d reference(s)"
              % ("fix " if apply_it else "plan", fn, added))
        for u in unresolved:
            print("         NO RECOVERABLE WORDING, left out: %s" % u)

    print("\n%d post(s) %s." % (touched, "repaired" if apply_it else
                                "would be repaired (use --apply)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
