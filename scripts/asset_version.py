#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The cache-busting token for the shared assets, and nothing else.

    from asset_version import JS_VERSION, CSS_VERSION

Why this is its own file
------------------------
build_status_page.py needed this number and got it by importing sync_blog,
which is right in principle -- three builders each hashing their own idea of
"the shared assets" is how one page ends up pinned to a copy the others have
moved on from. But sync_blog imports markdown, yaml and BeautifulSoup at module
level, and the hourly status workflow installs none of them. So the import
raised, a `except Exception: return "0"` caught it, and the status page shipped

    site-footer.js?v=0

every hour, to everyone. A constant is not a cache-buster: the shared script
was pinned on the one page that rebuilds hourly, so a returning reader kept
running whatever copy they already had, no matter what was fixed. Nothing
reported it, because from the builder's side it had a version and the page
looked fine.

This file imports nothing but hashlib and pathlib, so any builder can have the
number without dragging in a publishing pipeline, and there is no reason left
for a fallback. If the assets cannot be read, that is a broken checkout and it
should raise rather than quietly stamp a constant.

Newlines are normalised before hashing: this tree is CRLF and CI is LF, and
hashing the bytes as they sit on disk gives two different answers for identical
content.
"""
import hashlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS = REPO_ROOT / "blog" / "assets"

# Everything the shared token covers. hero-media.js is here because every page
# loads it and a change to the rotation would otherwise ship behind a cached
# copy; site-footer.css is here because no page links it -- site-footer.js
# injects it and stamps it with this same token, so hashing it here is what
# makes an edit to the stylesheet reach a returning reader at all.
SHARED_JS = ("blog.js", "site-footer.js", "site-footer.css",
             "hero-media.js", "occasion-banner.js")


def content_hash(*paths):
    h = hashlib.md5()
    for p in paths:
        h.update(Path(p).read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()[:8]


def js_version():
    return content_hash(*[ASSETS / name for name in SHARED_JS])


def css_version():
    return content_hash(ASSETS / "blog.css")


JS_VERSION = js_version()
CSS_VERSION = css_version()


if __name__ == "__main__":
    print("  shared JS/CSS token : %s" % JS_VERSION)
    print("  blog.css token      : %s" % CSS_VERSION)
