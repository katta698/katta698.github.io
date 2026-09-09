#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail when the status dashboard has stopped refreshing.

    python scripts/check_status_fresh.py
    python scripts/check_status_fresh.py --max-age-hours 6

Why this exists
---------------
The dashboard shipped claiming "refreshed every 15 minutes". The schedule was
silently dropped by GitHub and never fired once -- not late, not failing, just
absent, with nothing in the Actions log to say so. It went unnoticed for a day
and was found by a person reading the page and noticing the timestamp did not
match the sentence beside it.

That is the failure mode worth defending against: not a job that breaks, but
one that quietly stops existing. A broken job goes red and sends mail. A
dropped schedule produces silence, and silence is indistinguishable from
everything being fine.

So this is deliberately NOT run by the hourly job it watches. A watchdog that
shares its subject's scheduler dies with it. It runs from the daily ingest
workflow, whose cron has fired every day without missing, so the thing doing
the checking is the thing already proven to run.

What it checks
--------------
Two different questions, because either can fail alone.

  1. Is the data recent? status.json carries the time it was written.
  2. Is the SCHEDULE alive? The run log is the evidence. Data can look recent
     because a human pushed something an hour ago while the scheduled job has
     been dead for a week, which is exactly the state this repo was in.
"""
import argparse
import datetime
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUS = os.path.join(ROOT, "intelligence", "status.json")
RUNS = os.path.join(ROOT, "intelligence", "status-runs.json")


def load(p):
    if not os.path.exists(p):
        return None
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except ValueError:
        return None


def parse(ts):
    if not ts:
        return None
    try:
        return datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-age-hours", type=float, default=6.0)
    # An hourly schedule should manage far more than this in a day. The floor
    # is set low on purpose: it is here to catch a schedule that has STOPPED,
    # not to grade GitHub on punctuality, and a watchdog that cries about
    # ordinary lateness is one that gets muted.
    ap.add_argument("--min-runs-24h", type=int, default=6)
    args = ap.parse_args()

    now = datetime.datetime.now(datetime.timezone.utc)
    problems = []

    status = load(STATUS)
    if not status:
        problems.append("intelligence/status.json is missing or unreadable.")
    else:
        checked = parse(status.get("checked"))
        if not checked:
            problems.append("status.json has no readable 'checked' timestamp.")
        else:
            age = (now - checked).total_seconds() / 3600.0
            print("  data age        %.1f h (limit %.1f)" % (age, args.max_age_hours))
            if age > args.max_age_hours:
                problems.append(
                    "The dashboard data is %.1f hours old. The hourly refresh "
                    "is not running." % age)

    log = load(RUNS)
    runs = (log or {}).get("runs") or []
    if not runs:
        # Not fatal on its own: the log starts empty and fills from the first
        # run after it was added. It becomes evidence once it has any.
        print("  run log         empty (nothing recorded yet)")
    else:
        day = [r for r in runs
               if (parse(r.get("at")) or now) > now - datetime.timedelta(hours=24)]
        last = parse(runs[-1].get("at"))
        gap = (now - last).total_seconds() / 3600.0 if last else None
        print("  runs in 24h     %d (floor %d)" % (len(day), args.min_runs_24h))
        if gap is not None:
            print("  since last run  %.1f h" % gap)
        # Do not judge a 24-hour window the log is not yet 24 hours old
        # enough to describe. Alarming here would make the build red from the
        # moment this was added until a full day had passed -- and a check
        # that is red on day one is one people learn to skip, which is how the
        # contrast backlog got to forty findings.
        first = parse(runs[0].get("at"))
        young = first is not None and (now - first) < datetime.timedelta(hours=24)
        if young:
            print("  run log         %.1f h old — too young to judge cadence"
                  % ((now - first).total_seconds() / 3600.0))
        if not young and len(day) < args.min_runs_24h:
            problems.append(
                "Only %d scheduled refresh(es) in the last 24 hours, expected "
                "at least %d. The cron is being dropped, which is what "
                "happened with the original */15 schedule."
                % (len(day), args.min_runs_24h))

        failing = [c for c in (runs[-1].get("failed") or [])]
        if failing:
            print("  last run failed sources: %s" % ", ".join(failing))

    if problems:
        print("\n  STATUS DASHBOARD IS NOT REFRESHING\n")
        for p in problems:
            print("  - %s" % p)
        print("\n  The page reports its own measured cadence, so a reader can")
        print("  already see this. Fixing it is the point of the alarm.")
        return 1

    print("  the status dashboard is refreshing as scheduled.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
