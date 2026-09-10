#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Say something the first time a cloud breaks, not the next morning.

    python scripts/alert_new_incidents.py            # print what it would say
    python scripts/alert_new_incidents.py --issue    # open a GitHub issue

Why this exists
---------------
The status page refreshes hourly and the health report arrives at eight. So an
outage that starts at nine in the morning sits on the page, correct and
unremarked, until somebody happens to look -- and the whole point of building
this was to know before being told.

This runs after each refresh and compares what is open now with what was open
last time. Only genuinely NEW incidents are announced: an outage that has been
running for six hours is not news at hour seven, and a job that shouted every
hour about the same incident would train its reader to ignore it, which is the
opposite of the intent.

It also says when the last one clears, because "is it over?" is the second
question and nobody should have to poll a page for it.

State lives in intelligence/alerted.json, next to the data it describes, and
is committed like everything else here -- so what was announced and when is
part of the record rather than something only the runner remembers.
"""
import argparse
import datetime as dt
import io
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUS = os.path.join(ROOT, "intelligence", "status.json")
STATE = os.path.join(ROOT, "intelligence", "alerted.json")
NAMES = {"aws": "AWS", "azure": "Azure", "gcp": "Google Cloud"}


def load(path, default):
    try:
        return json.load(io.open(path, encoding="utf-8"))
    except Exception:                                           # noqa: BLE001
        return default


def open_now(status):
    """Every open incident, keyed the way the vendor identifies it."""
    out = {}
    for cloud, rows in (status.get("clouds") or {}).items():
        for i in rows or []:
            ident = i.get("id") or (i.get("title") or "")[:80]
            out["%s:%s" % (cloud, ident)] = {
                "cloud": cloud,
                "title": (i.get("title") or "").strip(),
                "service": (i.get("service") or "").strip(),
                "region": (i.get("region") or i.get("region_code") or "").strip(),
                "url": i.get("url") or "",
                "update": (i.get("update") or "").strip(),
            }
    return out


def body_for(new, still_open, cleared, checked):
    lines = []
    for key, i in new.items():
        where = i["region"] or "no region stated"
        lines.append("### %s — %s" % (NAMES.get(i["cloud"], i["cloud"]),
                                      i["title"] or "an open incident"))
        lines.append("")
        lines.append("- **Where:** %s" % where)
        if i["service"]:
            lines.append("- **Service:** %s" % i["service"])
        if i["url"]:
            lines.append("- **The vendor's own record:** %s" % i["url"])
        if i["update"]:
            lines.append("")
            lines.append("> %s" % i["update"][:600])
        lines.append("")
    if cleared:
        lines.append("### Cleared since the last check")
        lines.append("")
        for i in cleared.values():
            lines.append("- %s — %s" % (NAMES.get(i["cloud"], i["cloud"]),
                                        i["title"] or "an incident"))
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("%d open in total as of %s."
                 % (len(still_open), checked or "the last refresh"))
    lines.append("")
    lines.append("Read from the vendors' own status feeds. Nothing here is "
                 "summarised or reworded — the wording is theirs. "
                 "https://jayanthkatta.com/intelligence/status/")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--issue", action="store_true",
                    help="open a GitHub issue instead of only printing")
    args = ap.parse_args()

    status = load(STATUS, {})
    if not status:
        print("  no status.json to read; nothing to do.")
        return 0

    now = open_now(status)
    prior = load(STATE, None)

    # The first run records; it does not announce.
    #
    # With no prior state every open incident looks new, and the first alert
    # would have been "2 new incidents" about two AWS regions that have been
    # down since March. An alerting system whose opening message is stale is
    # one nobody trusts afterwards.
    if prior is None:
        io.open(STATE, "w", encoding="utf-8", newline="\n").write(
            json.dumps({"updated": dt.datetime.now(dt.timezone.utc)
                        .strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "open": now, "seeded": True},
                       ensure_ascii=False, indent=1))
        print("  first run: recorded %d open incident(s) as already known. "
              "Anything after this is new." % len(now))
        return 0

    seen = prior.get("open") or {}

    new = {k: v for k, v in now.items() if k not in seen}
    cleared = {k: v for k, v in seen.items() if k not in now}

    # Record first, announce second.
    #
    # If the issue fails to open, the state must not already claim the incident
    # was announced -- that would swallow the only alert this outage gets. So
    # the write happens after a successful announcement, or when there is
    # nothing to announce.
    def remember():
        io.open(STATE, "w", encoding="utf-8", newline="\n").write(
            json.dumps({"updated": dt.datetime.now(dt.timezone.utc)
                        .strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "open": now}, ensure_ascii=False, indent=1))

    if not new and not cleared:
        remember()
        print("  nothing new: %d incident(s) open, all of them already known."
              % len(now))
        return 0

    if not new and cleared:
        title = ("All clear — %s" % NAMES.get(list(cleared.values())[0]["cloud"],
                                              "a cloud")
                 if len(now) == 0 else "%d incident(s) cleared" % len(cleared))
    else:
        first = list(new.values())[0]
        where = first["region"] or "no region stated"
        title = "%s — %s (%s)" % (NAMES.get(first["cloud"], first["cloud"]),
                                  first["title"][:70] or "open incident", where)
        if len(new) > 1:
            title = "%d new incidents — %s and %d more" % (
                len(new), NAMES.get(first["cloud"], first["cloud"]), len(new) - 1)

    body = body_for(new, now, cleared, status.get("checked"))
    print("  %s\n" % title)
    print(body)

    if not args.issue:
        # Deliberately does NOT advance the state. A dry run that recorded
        # these as announced would swallow the only alert the outage gets.
        print("\n  (--issue not passed: nothing opened and nothing "
              "recorded, so this will show again next time)")
        return 0

    try:
        subprocess.run(["gh", "issue", "create", "--title", title,
                        "--body", body, "--label", "incident"],
                       check=True, cwd=ROOT, timeout=90,
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    except Exception:                                           # noqa: BLE001
        # The label may not exist yet; the alert matters more than the label.
        try:
            subprocess.run(["gh", "issue", "create", "--title", title,
                            "--body", body],
                           check=True, cwd=ROOT, timeout=90,
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        except Exception as exc:                                # noqa: BLE001
            print("  could not open an issue (%s); state not advanced, so the "
                  "next run will try again." % str(exc)[:60])
            return 1

    remember()
    print("\n  announced.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
