#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Every workflow that commits must also trigger the deploy.

WHY
---
On 14 October the site stopped updating for thirteen hours and nothing was
broken. The ingest ran, committed 76 announcements, and the commit sat on
main undeployed while the page told readers the newest news was Monday.

The cause is a rule of GitHub's: a push made with GITHUB_TOKEN does not
trigger other workflows, so that a workflow which commits cannot trigger
itself forever. deploy-pages.yml ran `on: push`, and every commit that night
came from a scheduled workflow. None of them deployed.

deploy-pages.yml now lists those workflows under `workflow_run`. But that
list is matched on workflow NAME, so renaming one -- or adding a tenth
workflow that commits -- drops it with no symptom at all: the site simply
stops carrying that one job's output, and looks perfectly healthy doing it.
That is the same shape as the fault it was written to fix.

So this asserts the two sets are equal, in both directions. A workflow that
commits and is not listed is a hole. A name listed that matches no workflow
is a trigger that will never fire, which is the rename that already happened
by the time anyone notices.

A four-hourly schedule in deploy-pages.yml is the backstop, so a miss costs
hours rather than days. This is what makes it cost nothing.
"""
import glob
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WF = os.path.join(ROOT, ".github", "workflows")
DEPLOY = os.path.join(WF, "deploy-pages.yml")

# A workflow that pushes its own output. Matched on the commands rather than
# on a list of filenames, so a new scheduled job is covered the day it is
# written rather than the day somebody remembers this file.
COMMIT_MARKERS = ("git commit", "git-auto-commit")


def workflow_name(text):
    m = re.search(r"^name:\s*(.+)$", text, re.M)
    if not m:
        return None
    return m.group(1).strip().strip('"').strip("'")


def committing_workflows():
    out = {}
    for path in sorted(glob.glob(os.path.join(WF, "*.yml"))):
        base = os.path.basename(path)
        if base == "deploy-pages.yml":
            continue
        text = io.open(path, encoding="utf-8").read()
        if not any(m in text for m in COMMIT_MARKERS):
            continue
        name = workflow_name(text)
        if name:
            out[name] = base
    return out


def listed_workflows():
    """The names under deploy-pages.yml's workflow_run trigger.

    Parsed with a small reader rather than a YAML library, because this has to
    run anywhere prepublish runs and a check that cannot run is a check that
    is not run.
    """
    text = io.open(DEPLOY, encoding="utf-8").read()
    m = re.search(r"^  workflow_run:\s*$", text, re.M)
    if not m:
        return None
    rest = text[m.end():]
    stop = re.search(r"^\s{4}types:", rest, re.M)
    block = rest[:stop.start()] if stop else rest
    return set(re.findall(r'^\s*-\s*"(.+?)"\s*$', block, re.M))


def main():
    problems = []
    listed = listed_workflows()
    if listed is None:
        print("  ERROR deploy-pages.yml has no workflow_run trigger. Every "
              "commit made by a scheduled workflow will sit on main "
              "undeployed, which is exactly the 14 October outage.")
        return 1

    commits = committing_workflows()
    for name, base in sorted(commits.items()):
        if name not in listed:
            problems.append(
                "%s commits its own output but is not under deploy-pages.yml's "
                "workflow_run trigger. Its pushes cannot deploy -- a push made "
                "with GITHUB_TOKEN never triggers another workflow -- so its "
                "output will reach main and stop there. Add: \"%s\""
                % (base, name))

    for name in sorted(listed - set(commits)):
        problems.append(
            "deploy-pages.yml triggers on a workflow called \"%s\", and no "
            "workflow has that name. Either it was renamed -- in which case "
            "its output is no longer deploying -- or the entry is a typo that "
            "has never fired." % name)

    for name in sorted(commits):
        print("  ok    %s triggers the deploy" % name)
    for p in problems:
        print("  ERROR %s" % p)
    print("\n  %d workflow(s) that commit, %d listed, %d problem(s)."
          % (len(commits), len(listed), len(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
