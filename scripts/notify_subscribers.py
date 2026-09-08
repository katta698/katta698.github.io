#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Email subscribers when a post goes up.

Buttondown's own RSS-to-email feature costs $9/month. Its API does not --
"API is available on all plans, including free", per their pricing page -- so
this does the same job from the workflow that already runs on publish.

    python scripts/notify_subscribers.py            # send what is unsent
    python scripts/notify_subscribers.py --dry-run  # show what it would send
    python scripts/notify_subscribers.py --limit 1  # newest only

Idempotency is the whole problem here.
---------------------------------------
A workflow can re-run. A push can land twice. `on-publish.yml` fires on
`posts/**`, so editing a typo in a published post triggers it again. Any of
those sending a second copy is worse than not sending at all -- an unsubscribe
is one click and a reader who gets the same email twice will use it.

So the record of what has been sent lives in the repo, at
scripts/subscriber-sends.json, and is committed by the workflow. Not a
timestamp comparison, not "newest post" -- an explicit list of slugs that
have been emailed. A slug already in that file is never sent again, whatever
the trigger.

The first run is deliberately a no-op that backfills.
--------------------------------------------------
With an empty state file and 215 published posts, the obvious behaviour --
"send everything not yet sent" -- would send 215 emails. So a missing state
file means "record everything as sent, send nothing", and the next genuinely
new post is the first email anyone receives.
"""
import argparse
import io
import json
import os
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CARDS = os.path.join(ROOT, "blog", "cards.json")
STATE = os.path.join(HERE, "subscriber-sends.json")
SITE = "https://jayanthkatta.com"
API = "https://api.buttondown.email/v1/emails"


def load_cards():
    d = json.load(io.open(CARDS, encoding="utf-8"))
    posts = d if isinstance(d, list) else d.get("posts", d.get("cards", []))
    return sorted(posts, key=lambda p: (p.get("date", ""), p.get("slug", "")),
                  reverse=True)


def load_state():
    if not os.path.exists(STATE):
        return None                      # signals "first run, backfill"
    return set(json.load(io.open(STATE, encoding="utf-8")).get("sent", []))


def save_state(sent):
    tmp = STATE + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"sent": sorted(sent)}, fh, indent=2)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, STATE)               # never leave a half-written state file:
                                         # a truncated one reads as "nothing sent"
                                         # and would re-send the whole archive


def body_for(post):
    url = "%s/blog/%s/" % (SITE, post["slug"])
    series = post.get("tag1") or ""
    mins = post.get("read_time")
    meta = " &middot; ".join(
        [x for x in (series, "%s min read" % mins if mins else "") if x])
    return (
        '<p style="color:#6B7370;font-size:13px;margin:0 0 4px">%s</p>'
        '<h2 style="margin:0 0 12px;font-size:20px;line-height:1.3">'
        '<a href="%s" style="color:#1D2322;text-decoration:none">%s</a></h2>'
        '<p style="line-height:1.6;margin:0 0 18px">%s</p>'
        '<p style="margin:0 0 24px"><a href="%s" '
        'style="color:#A8825A;font-weight:600">Read it &rarr;</a></p>'
        '<hr style="border:0;border-top:1px solid #E0DCD4;margin:24px 0">'
        '<p style="color:#8A918E;font-size:12px;line-height:1.5;margin:0">'
        'You are getting this because you subscribed at jayanthkatta.com. '
        'One email per post, unsubscribe any time.</p>'
    ) % (meta, url, post.get("title", "New post"),
         post.get("excerpt", ""), url)


def send(post, key, dry):
    payload = {
        "subject": post.get("title", "New post"),
        "body": body_for(post),
        "status": "about_to_send",
    }
    if dry:
        print("    DRY-RUN would send: %s" % payload["subject"][:70])
        return True
    req = urllib.request.Request(
        API, data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Token %s" % key,
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            ok = r.status in (200, 201)
            print("    sent (HTTP %s): %s" % (r.status, payload["subject"][:60]))
            return ok
    except urllib.error.HTTPError as e:
        # Print the body. Buttondown explains refusals there, and without it a
        # failure is just a status code.
        print("    FAILED HTTP %s: %s" % (e.code, e.read()[:300]))
        return False
    except Exception as exc:                                   # noqa: BLE001
        print("    FAILED: %s" % exc)
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=3,
                    help="most emails to send in one run; a guard against a "
                         "state file that got lost")
    args = ap.parse_args()

    posts = load_cards()
    state = load_state()

    if state is None:
        save_state([p["slug"] for p in posts])
        print("  first run: recorded %d existing post(s) as already sent, "
              "sent nothing." % len(posts))
        print("  the next new post will be the first email.")
        return 0

    pending = [p for p in posts if p.get("slug") not in state]
    if not pending:
        print("  nothing new to send (%d post(s) already recorded)." % len(state))
        return 0

    if len(pending) > args.limit:
        print("  %d unsent post(s), which is more than --limit %d."
              % (len(pending), args.limit))
        print("  Refusing to send a burst. Check scripts/subscriber-sends.json;")
        print("  if that is genuinely correct, re-run with a higher --limit.")
        return 1

    key = os.environ.get("BUTTONDOWN_API_KEY", "")
    if not key and not args.dry_run:
        print("  BUTTONDOWN_API_KEY is not set; nothing sent.")
        return 1

    print("  %d post(s) to send:" % len(pending))
    sent_now = set(state)
    failed = 0
    for p in reversed(pending):          # oldest first, so the order a reader
                                         # receives matches the order published
        print("  - %s" % p.get("slug"))
        if send(p, key, args.dry_run):
            sent_now.add(p["slug"])
        else:
            failed += 1

    if not args.dry_run:
        save_state(sent_now)
    print("\n  %d sent, %d failed." % (len(pending) - failed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
