#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail when a stylesheet has more closing braces than opening ones.

    python scripts/check_css_balance.py

Why this exists
---------------
An unbalanced brace does not make a stylesheet fail loudly. The browser
recovers, discards what it cannot parse, and renders the page -- so the file
loads, most of it works, and some arbitrary run of rules after the damage
quietly does nothing.

That happened here twice in one evening, both times from a script that spliced
a block of CSS in by index and cut in the wrong place, leaving two orphan
closers behind. Everything after them was dead: on the status page and What's
New that included the brand mark, so those two pages showed a square favicon
while every other page showed the circle. Nothing about the page said anything
was wrong -- it was found by a reader noticing the shape did not match.

Braces are counted with comments stripped first, because /* } */ is a comment
and not a brace, and this file exists to stop false alarms as much as real
ones.
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP = {"node_modules", ".git", "_archive"}


def balance(css):
    """Opens minus closes, with comments and quoted strings removed."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r'"(?:[^"\\]|\\.)*"', '""', css)
    css = re.sub(r"'(?:[^'\\]|\\.)*'", "''", css)
    return css.count("{") - css.count("}")


def main():
    problems = []
    checked = 0

    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP and not d.startswith(".")]
        for name in files:
            path = os.path.join(base, name)
            rel = os.path.relpath(path, ROOT).replace("\\", "/")

            if name.endswith(".css"):
                try:
                    d = balance(io.open(path, encoding="utf-8").read())
                except (OSError, UnicodeDecodeError):
                    continue
                checked += 1
                if d:
                    problems.append((rel, d, "stylesheet"))

            elif name.endswith((".html", ".py")):
                try:
                    text = io.open(path, encoding="utf-8").read()
                except (OSError, UnicodeDecodeError):
                    continue
                for i, block in enumerate(
                        re.findall(r"<style[^>]*>(.*?)</style>", text, re.S)):
                    checked += 1
                    d = balance(block)
                    if d:
                        problems.append((rel, d, "inline <style> #%d" % (i + 1)))

    print("  %d stylesheet(s) and inline block(s) checked" % checked)
    if not problems:
        print("  every one balances.")
        return 0

    print("\n  %d UNBALANCED\n" % len(problems))
    for rel, d, what in problems:
        print("  %-44s %s: %+d %s"
              % (rel, what, d,
                 "unclosed" if d > 0 else "orphan closing brace(s)"))
    print("\n  An orphan closer does not break the page. It silently drops")
    print("  every rule after it, which is how two pages ended up showing a")
    print("  square favicon while the rest showed a circle.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
