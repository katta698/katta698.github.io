#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Give every AWS lab post's services table its third column.

    python scripts/add_services_column.py --check   # report only
    python scripts/add_services_column.py --write

Fifteen posts carried "Service | Purpose here" under four different spellings
of the header, with no column saying what the service actually is. This
rewrites the header to the standard's exact three and fills the third column
from scripts/service_glossary.py, so the same service reads the same way in
every week.

It refuses to write a post whose table contains a service the glossary does not
define, rather than leaving a blank cell. A blank cell ships; a refusal does
not.
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
POSTS = os.path.join(os.path.dirname(HERE), "posts")
sys.path.insert(0, HERE)

import check_lab_post_shape as shape          # noqa: E402
from service_glossary import definition       # noqa: E402

HEADER = ("Service", "Purpose here", "What it is")


def _text(cell):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", cell)).strip()


def aws_lab_posts():
    for fn in sorted(os.listdir(POSTS)):
        if not (fn.startswith("week-") and fn.endswith(".html")):
            continue
        t = io.open(os.path.join(POSTS, fn), encoding="utf-8").read()
        fm = t.split("---", 2)[1] if t.count("---") >= 2 else ""
        if "AWS Weekly Lab" in fm:
            yield fn, t


def rewrite_table(table: str):
    """Return (new_table, names, already_ok) or raise ValueError."""
    head = re.search(r"<thead>.*?</thead>", table, re.S)
    ths = re.findall(r"<th[^>]*>(.*?)</th>", head.group(0) if head else table, re.S)
    cols = [_text(x) for x in ths]
    if tuple(cols) == HEADER:
        return table, [], True
    if len(cols) != 2:
        raise ValueError("expected a 2-column table, found %s" % (cols,))

    names = []
    out = table

    # header
    new_head = (
        "<thead><tr><th>%s</th><th>%s</th><th>%s</th></tr></thead>" % HEADER)
    if head:
        out = out[:head.start()] + new_head + out[head.end():]
    else:
        raise ValueError("no <thead> to replace")

    # body rows
    body = re.search(r"<tbody>(.*?)</tbody>", out, re.S)
    if not body:
        raise ValueError("no <tbody>")
    rows = re.findall(r"<tr>.*?</tr>", body.group(1), re.S)
    new_rows = []
    for row in rows:
        cells = re.findall(r"<td[^>]*>.*?</td>", row, re.S)
        if len(cells) != 2:
            raise ValueError("row has %d cells, expected 2" % len(cells))
        name = _text(cells[0])
        names.append(name)
        d = definition(name)
        if d is None:
            raise ValueError("no glossary definition for %r" % name)
        new_rows.append("<tr>%s%s<td>%s</td></tr>" % (cells[0], cells[1], d))
    out = out[:body.start(1)] + "".join(new_rows) + out[body.end(1):]
    return out, names, False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("posts", nargs="*")
    args = ap.parse_args()

    touched = done = skipped = failed = 0
    for fn, text in aws_lab_posts():
        if args.posts and not any(a in fn for a in args.posts):
            continue
        sec = shape.section(text, "services")
        if sec is None:
            print("  [skip] %-46s no services section" % fn[:46])
            skipped += 1
            continue
        m = re.search(r"<table.*?</table>", sec, re.S)
        if not m:
            print("  [skip] %-46s no table" % fn[:46])
            skipped += 1
            continue
        try:
            new_table, names, already = rewrite_table(m.group(0))
        except ValueError as e:
            print("  [FAIL] %-46s %s" % (fn[:46], e))
            failed += 1
            continue
        if already:
            print("  [ ok ] %-46s already three columns" % fn[:46])
            done += 1
            continue
        if args.write:
            whole = text.replace(m.group(0), new_table, 1)
            io.open(os.path.join(POSTS, fn), "w", encoding="utf-8",
                    newline="\n").write(whole)
        print("  [%s] %-46s %d row(s)"
              % ("writ" if args.write else "plan", fn[:46], len(names)))
        touched += 1

    print("\n  %d to change, %d already correct, %d skipped, %d failed"
          % (touched, done, skipped, failed))
    if not args.write and touched:
        print("  (dry run - pass --write to apply)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
