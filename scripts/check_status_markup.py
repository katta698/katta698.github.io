#!/usr/bin/env python
"""The status page shows the vendor's words, never the vendor's markup.

Azure publishes its incident updates as HTML. The fetcher stores what the
vendor sent and the page escapes what it renders, so for a while a reader
looking at a live Azure incident saw this:

    <p>We are investigating an issue affecting<strong> </strong>Azure
    OpenAI and Foundry agent services in the Sweden Central region.

Tags and all, as characters, in the middle of the card. Nothing errored.
The page was serving exactly what it had been given.

This asserts the reader-facing half: no HTML tag name appears as literal
text anywhere on the built page. It reads the file rather than driving a
browser, so it is fast enough to run on every push -- which matters,
because the two existing status checks that could have hosted this do not
run there. check_status_cards is a browser check excluded from the hook,
and check_status_fresh is skipped outright.

It carries a canary. A check that cannot fail is worse than no check, and
this one is a pattern match against a generated file -- precisely the
shape that quietly stops matching anything.
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

PAGE = os.path.join(ROOT, "intelligence", "status", "index.html")

# The tags a vendor actually writes. Deliberately not "anything in angle
# brackets": a vendor writing &lt;X-Request-Id&gt; means those characters,
# and flagging that would be a false alarm in exactly the prose -- headers,
# placeholders -- where it is most likely to appear.
TAGS = ("p|div|span|strong|b|i|em|u|a|br|ul|ol|li|h[1-6]|table|tr|td|th|"
        "tbody|thead|tfoot|pre|code|blockquote|img|hr|small|sub|sup|font")

# Escaped, because that is how it reaches the reader: the page escapes the
# text it renders, so a stored "<p>" is served as "&lt;p&gt;".
ESCAPED = re.compile(r"&lt;/?(?:%s)\b[^&]{0,80}?&gt;" % TAGS, re.I)


def canary():
    """Prove the pattern still matches the thing it was written for."""
    sample = ("&lt;p&gt;We are investigating an issue affecting"
              "&lt;strong&gt; &lt;/strong&gt;Azure OpenAI")
    hits = ESCAPED.findall(sample)
    if len(hits) < 3:
        print("  CANARY FAILED: the pattern no longer matches the reported")
        print("  defect -- it found %d of 3 tags in the original text."
              % len(hits))
        return False
    # and that it does not fire on prose a vendor legitimately writes
    innocent = "Set the &lt;X-Request-Id&gt; header, and see &amp; note 5."
    if ESCAPED.findall(innocent):
        print("  CANARY FAILED: the pattern fires on a literal placeholder,")
        print("  which would make this check cry wolf: %r"
              % ESCAPED.findall(innocent))
        return False
    return True


def main():
    if not canary():
        return 1

    if not os.path.exists(PAGE):
        print("  intelligence/status/index.html is not built; nothing to read.")
        print("  Run scripts/build_status_page.py first.")
        return 1

    html = io.open(PAGE, encoding="utf-8").read()
    hits = ESCAPED.findall(html)

    if hits:
        seen = {}
        for h in hits:
            seen[h] = seen.get(h, 0) + 1
        print("  %d VENDOR TAG(S) RENDERED AS TEXT" % len(hits))
        for h, n in sorted(seen.items(), key=lambda x: -x[1])[:10]:
            print("    %-28s x%d" % (h, n))
        print()
        print("  A vendor's update reached the page with its markup intact.")
        print("  The page escapes what it renders, so the reader sees the")
        print("  tags as characters. detag() in build_status_page.py strips")
        print("  them; flat() in fetch_status.py keeps them out of the store.")
        print("  One of the two has stopped being applied to this field.")
        return 1

    print("  no vendor markup renders as text on the status page")
    print("  (%d chars checked, %d incident card(s))"
          % (len(html), html.count('class="inc"')))
    return 0


if __name__ == "__main__":
    sys.exit(main())
