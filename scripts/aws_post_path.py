# -*- coding: utf-8 -*-
"""Resolve week number -> the AWS lab post's path.

Three series share the posts/ directory and the week-NN- prefix, so a glob of
"week-3-*" matches an Azure post, a GCP post and an AWS one. Every ad-hoc glob
in this repo's history has eventually matched the wrong series; this reads the
front matter and is the only thing that should be used.

    python scripts/aws_post_path.py 7        # prints the path
    python scripts/aws_post_path.py          # prints every AWS lab post
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
POSTS = os.path.join(os.path.dirname(HERE), "posts")


def is_aws_lab(path):
    t = io.open(path, encoding="utf-8").read()
    fm = t.split("---", 2)[1] if t.count("---") >= 2 else ""
    return "AWS Weekly Lab" in fm


def all_posts():
    """[(week_number, path), ...] sorted by week."""
    out = []
    for fn in sorted(os.listdir(POSTS)):
        if not (fn.startswith("week-") and fn.endswith(".html")):
            continue
        p = os.path.join(POSTS, fn)
        if not is_aws_lab(p):
            continue
        out.append((int(re.match(r"week-(\d+)", fn).group(1)), p))
    return sorted(out)


def for_week(n):
    hits = [p for w, p in all_posts() if w == int(n)]
    if len(hits) != 1:
        raise SystemExit("expected one AWS lab post for week %s, got %s"
                         % (n, hits))
    return hits[0]


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(for_week(sys.argv[1]))
    else:
        for w, p in all_posts():
            print("%-3d %s" % (w, p))
