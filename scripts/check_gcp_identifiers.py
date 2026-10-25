#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""No GCP account identifier may appear in a published GCP lab post.

    python scripts/check_gcp_identifiers.py
    python scripts/check_gcp_identifiers.py week-09
    python scripts/check_gcp_identifiers.py --self-test

Why this exists
---------------
On 2026-10-25 the published Week 09 post was found to contain the full default
Compute Engine service account addresses -

    <project-number>-compute@developer.gserviceaccount.com

- twice, exposing the project numbers of the logging and security projects. The
standing rule is explicit: never commit an org ID, billing account ID, project
number or personal email to anything that lands in git, and this repo is public.

The screenshots were fine. `capture_gcp.py` in the lab repo masks exactly these
numbers and masked them correctly in the same week's figures. The lab repo also
has `scripts/sweep_identifiers.sh`. Neither covers POST PROSE in this
repository, which is where the leak lived for a day.

It was found by a human reading the file while restructuring it. Two automated
checks run minutes earlier had reported clean, because the command composing the
project numbers returned nothing and an empty result was read as a pass.

So this file does two things differently:

1. **It fails loudly when it cannot derive the values.** A sweep that silently
   checks zero patterns is worse than no sweep: it produces a green tick that
   means nothing. If gcloud or the lab tfvars are unavailable, this EXITS
   NON-ZERO and says so.
2. **It also matches the SHAPE of the leak**, not only known values. A
   twelve-digit number in front of `-compute@` is a project number whether or
   not this machine can enumerate projects today.

   The domain is deliberately NOT required. The real leak was truncated output,
   `<number>-compute@  NEVER AUTHENTICATED`, with no domain at all - so the
   first version of this pattern, written from the canonical full address in
   Google's documentation, could never have matched the thing it was written
   for. Match how a leak APPEARS, not how the vendor spells it.

Scope is the GCP lab series, per Jay's instruction on 2026-10-25.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
POSTS = os.path.join(ROOT, "posts")
SERIES_LABEL = "GCP Weekly Lab"

LAB = os.path.join(os.path.dirname(ROOT), "GCP-Infrastructure-Projects",
                   "GCP-Platform-Engineering-Lab")
TFVARS = os.path.join(LAB, "terraform", "bootstrap", "terraform.tfvars")

# Shapes that are identifiers regardless of what this machine can enumerate.
# These need no credentials and are the backstop when derivation is impossible.
SHAPE_PATTERNS = [
    (re.compile(r"\b\d{9,14}-compute@"),
     "a project number in a default Compute Engine service account address"),
    (re.compile(r"\bservice-\d{9,14}@"),
     "a project number in a Google-managed service agent address"),
    (re.compile(r"\bprojects/\d{9,14}\b"),
     "a project number in a resource path"),
    (re.compile(r"\borganizations/\d{10,14}\b"),
     "an organization ID in a resource path"),
    (re.compile(r"\b[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}\b"),
     "a billing account ID"),
]


def derive_values():
    """Exact identifiers to search for. Raises if they cannot be obtained."""
    values = {}

    if not os.path.exists(TFVARS):
        raise RuntimeError(
            f"cannot read {TFVARS} - the lab's gitignored tfvars is where the "
            "org and billing identifiers live. Without it this check can only "
            "match shapes, not values.")
    with open(TFVARS, encoding="utf-8") as fh:
        tf = fh.read()
    for key, label in (("org_id", "organization ID"),
                       ("billing_account", "billing account ID")):
        m = re.search(r'^%s\s*=\s*"([^"]+)"' % key, tf, re.M)
        if m:
            values[m.group(1)] = label

    # shutil.which, not a bare "gcloud": on Windows gcloud is a .CMD shim and
    # CreateProcess does not apply PATHEXT, so subprocess raises WinError 2.
    # Recorded in the lab's SESSION_CONTEXT after a script died this way
    # mid-run and left an org policy degraded.
    exe = shutil.which("gcloud")
    if not exe:
        raise RuntimeError("gcloud is not on PATH")

    def gcloud(*args):
        out = subprocess.run([exe, *args], capture_output=True, text=True,
                             timeout=120)
        if out.returncode != 0:
            raise RuntimeError("gcloud failed: " + out.stderr.strip()[:160])
        return out.stdout.split()

    projects = gcloud("projects", "list", "--format=value(projectId)")
    if not projects:
        raise RuntimeError("gcloud returned no projects - cannot derive project "
                           "numbers. Refusing to report a pass.")
    for pid in projects:
        for num in gcloud("projects", "describe", pid,
                          "--format=value(projectNumber)"):
            values[num] = f"a project number"

    org = next((v for v, l in values.items() if l == "organization ID"), None)
    if org:
        for cid in gcloud("organizations", "describe", org,
                          "--format=value(owner.directoryCustomerId)"):
            values[cid] = "the directory customer ID"
    return values


def scan(text, values):
    """Return a list of (label, redacted_excerpt).

    Whitespace is collapsed before SHAPE matching. HTML wraps prose at column
    80, so a leaked address is routinely split across two lines - and the shape
    patterns are the backstop for numbers this machine cannot enumerate, so a
    wrapped address slipping past them is the gap that matters most. Proved by
    reintroducing the real Week 09 leak: the literal matched, the shape did not,
    because the address spanned a line break.
    """
    flat = re.sub(r"\s+", " ", text)
    found = []
    for value, label in values.items():
        if value and value in text:
            found.append((label, f"literal {label} present"))
    for pattern, label in SHAPE_PATTERNS:
        for m in pattern.finditer(flat):
            shown = re.sub(r"\d", "#", m.group(0))
            found.append((label, shown))
    return found


def front_matter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return m.group(1) if m else ""


def self_test():
    values = {"123456789012": "a project number"}
    cases = [
        ("<p>nothing to see</p>", 0, "a clean post"),
        ("<p>123456789012-compute@developer.gserviceaccount.com</p>", 2,
         "the Week 09 leak: matches the literal AND the shape"),
        ("<p>987654321098-compute@developer.gserviceaccount.com</p>", 1,
         "an UNKNOWN project number - caught by shape alone"),
        ("<pre>987654321098-compute@  NEVER AUTHENTICATED</pre>", 1,
         "the real leak's shape: truncated, no domain"),
        ("<p>service-987654321098@gcp-sa-cloudasset.iam.gserviceaccount.com</p>", 1,
         "a service agent address carrying a project number"),
        ("<p>organizations/12345678901</p>", 1, "an org ID in a resource path"),
        ("<p>tf-apply@seed.iam.gserviceaccount.com</p>", 0,
         "an ordinary service account address is publishable"),
    ]
    bad = 0
    for text, want, label in cases:
        got = len(scan(text, values))
        ok = got == want
        bad += not ok
        print(f"  [{' ok ' if ok else 'FAIL'}] {label}: {got} hit(s), want {want}")
    if bad:
        print("\nSELF-TEST FAILED: the check cannot detect the defect it exists for.")
        return 1
    print("\nself-test passed: the exact leak is caught twice over, an unknown")
    print("project number is caught by shape alone, and a normal service account")
    print("address is not flagged.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("posts", nargs="*")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()

    try:
        values = derive_values()
    except Exception as e:
        print("CANNOT RUN: " + str(e))
        print("\nRefusing to report a pass on an incomplete check. This is the")
        print("2026-10-25 lesson: a sweep that quietly checks nothing is worse")
        print("than no sweep, because it produces a green tick that means nothing.")
        return 2

    print(f"Derived {len(values)} exact identifier(s) plus "
          f"{len(SHAPE_PATTERNS)} shape pattern(s).")

    failures, checked = 0, 0
    for fn in sorted(os.listdir(POSTS)):
        if not fn.endswith(".html"):
            continue
        if args.posts and not any(a in fn for a in args.posts):
            continue
        with open(os.path.join(POSTS, fn), encoding="utf-8") as fh:
            text = fh.read()
        if SERIES_LABEL not in front_matter(text):
            continue
        checked += 1
        hits = scan(text, values)
        if hits:
            failures += 1
            print(f"  [FAIL] {fn}")
            for label, shown in hits:
                print(f"           {label}: {shown}")
        else:
            print(f"  [ ok ] {fn}")

    print(f"\n{checked} {SERIES_LABEL} post(s) checked.")
    if failures:
        print(f"{failures} post(s) contain an account identifier. Replace with a "
              "placeholder before publishing.")
        return 1
    print("No GCP account identifier appears in any GCP lab post.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
