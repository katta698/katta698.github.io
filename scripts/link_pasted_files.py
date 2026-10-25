#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Replace pasted source blocks in a post with links to the file on GitHub.

    python scripts/link_pasted_files.py --list posts/week-05-hub-network.html
    python scripts/link_pasted_files.py posts/week-05-hub-network.html \\
        --week week-05-hub-network \\
        --drop 'resource "azurerm_firewall" "hub"'=terraform/firewall.tf

The Master Standard: "Do not include complete Terraform files, extensive
terminal output, unrelated debugging history, or exhaustive source-code
listings in the article. Link to the corresponding GitHub source files." Small
snippets stay where they teach an architectural decision.

This only removes what you name. It will not guess which block is worth
keeping, because that judgement is the whole point -- a variable that gates a
$0.405/hour meter teaches something a resource block does not.
"""
import argparse
import html
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
NL = chr(10)
REPO = "https://github.com/katta698/Azure-Platform-Engineering-Lab/blob/main"


def words(x):
    t = html.unescape(re.sub(r"<[^>]+>", " ", x))
    return len([w for w in t.split() if re.search(r"[A-Za-z0-9]", w)])


def blocks(s):
    for m in re.finditer(r"<pre><code>(.*?)</code></pre>", s, re.S):
        yield m, html.unescape(re.sub(r"<[^>]+>", "", m.group(1)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("post")
    ap.add_argument("--week")
    ap.add_argument("--drop", action="append", default=[],
                    metavar="MARKER=PATH",
                    help="drop the block containing MARKER, link to PATH")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    raw = open(a.post, "rb").read().decode("utf-8")
    term = "\r\n" if "\r\n" in raw else NL
    s = raw.replace("\r\n", NL)

    if a.list:
        for i, (m, txt) in enumerate(blocks(s), 1):
            first = txt.strip().split(NL)[0][:64]
            print("  %2d  %3d words  %2d lines  %s"
                  % (i, len(txt.split()), txt.count(NL) + 1, first))
        return

    if not a.week:
        ap.error("--week is required when dropping blocks")

    before = words(s)
    done = []

    # A link to a file that is not there is the same defect as the pasted
    # block, only harder to notice. Measured 2026-10-25: four links written
    # against guessed filenames -- week 05 keeps every resource in main.tf,
    # not the network.tf / dns.tf / firewall.tf the section headings implied.
    lab = os.environ.get("LAB_ROOT", r"C:\Projects\Engineering"
                         r"\Azure-Infrastructure-Projects"
                         r"\Azure-Platform-Engineering-Lab")
    for spec in a.drop:
        _marker, _, path = spec.partition("=")
        full = os.path.join(lab, a.week, path.replace("/", os.sep))
        if not os.path.exists(full):
            raise SystemExit("refusing to link a file that does not exist: "
                             "%s/%s" % (a.week, path))
    for spec in a.drop:
        marker, _, path = spec.partition("=")
        if not path:
            ap.error("--drop needs MARKER=PATH, got %r" % spec)
        for m, txt in blocks(s):
            if marker in txt:
                link = ('<p>In <a href="%s/%s/%s"><code>%s</code></a>.</p>'
                        % (REPO, a.week, path, os.path.basename(path)))
                s = s[:m.start()] + link + s[m.end():]
                done.append((marker[:40], len(txt.split())))
                break
        else:
            raise SystemExit("no block contains %r -- run --list first" % marker)

    open(a.post + ".tmp", "w", encoding="utf-8", newline="").write(
        s.replace(NL, term))
    os.replace(a.post + ".tmp", a.post)
    for marker, n in done:
        print("  dropped %-42s (%d words of source)" % (marker, n))
    print("  %s: %d -> %d words" % (os.path.basename(a.post), before, words(s)))


if __name__ == "__main__":
    main()
