#!/usr/bin/env python3
"""Give every four-column table's cells a data-label, so a phone can stack them.

On a 390px screen a Test / Expected / Actual / Status table cannot be a table.
Four columns of prose at ~95px each shred into "EXPEC TED" and "princi-pals" -
which is what the first attempt at fixing this produced, and worse than the
horizontal scroll it replaced.

The fix is to stack each row into a card on mobile. That needs each cell to
carry its own column name, because CSS cannot read the header row:

    <td data-label="Expected">5 resources</td>

and blog.css renders it with ::before. On desktop the attribute is inert and
the table stays a table.

Idempotent: re-running changes nothing. Safe to run after writing a new post.
"""
from __future__ import annotations

import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TABLE = re.compile(r"<table>\s*<thead>\s*<tr>(.*?)</tr>\s*</thead>(.*?)</table>", re.S)
TH = re.compile(r"<th[^>]*>(.*?)</th>", re.S)
ROW = re.compile(r"<tr>(.*?)</tr>", re.S)
CELL = re.compile(r"<td(?P<attrs>[^>]*)>", re.S)


def strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s).strip()


def label_table(match: re.Match) -> str:
    head, body = match.group(1), match.group(2)
    headers = [strip_tags(h) for h in TH.findall(head)]
    if len(headers) < 4:
        return match.group(0)        # only the wide ones need this

    def label_row(rm: re.Match) -> str:
        inner, idx = rm.group(1), [0]

        def one(cm: re.Match) -> str:
            attrs = cm.group("attrs")
            i = idx[0]
            idx[0] += 1
            if "data-label=" in attrs or i >= len(headers):
                return cm.group(0)
            return f'<td{attrs} data-label="{headers[i]}">'

        return "<tr>" + CELL.sub(one, inner) + "</tr>"

    return (f"<table>\n  <thead><tr>{head}</tr></thead>"
            + ROW.sub(label_row, body) + "</table>")


def main() -> int:
    check = "--check" in sys.argv
    changed, scanned = [], 0
    for path in sorted(glob.glob(os.path.join(ROOT, "posts", "*.html"))):
        text = open(path, encoding="utf-8").read()
        if "GCP Weekly Lab" not in text:
            continue
        scanned += 1
        new = TABLE.sub(label_table, text)
        if new != text:
            changed.append(os.path.basename(path))
            if not check:
                with open(path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(new)

    print(f"{scanned} lab post(s) scanned")
    if not changed:
        print("every four-column table already carries data-label on its cells.")
        return 0
    verb = "would label" if check else "labelled"
    print(f"{verb} {len(changed)}: {', '.join(changed)}")
    return 1 if check else 0


if __name__ == "__main__":
    sys.exit(main())
