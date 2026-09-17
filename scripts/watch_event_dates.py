#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tell me the day a cloud finally publishes dates it has not published yet.

    python scripts/watch_event_dates.py
    python scripts/watch_event_dates.py --json   # for the workflow

Why this exists
---------------
Asked, about the row that says AWS re:Invent 2026 has no dates: "add AWS
re:Invent dates once they announce."

The obvious version of that is a scraper that reads the date off the page and
writes it into the store. I am not doing that, and the reason is the whole
point of the events page. AWS's re:Invent page is JavaScript-rendered
marketing: the first date-shaped string on it today belongs to a 2025 attendee
quote. A scraper that took it would have written "2025" into a row about 2026,
the page would have looked perfectly healthy, and the first person to notice
would have been someone who booked around it.

So this WATCHES and does not write. For every row in events.json with
announced: false, it renders the official page in a real browser and looks for
dates in the future. If it finds any, it says so and the daily workflow raises
it. A human then opens the page, reads what it actually says, and edits one
row -- which takes a minute and cannot silently invent a date.

That division is deliberate and worth keeping: the machine is good at noticing
that something changed, and bad at deciding what it means. Every automated
part of this page notices; every claim on it was read by a person.
"""
import argparse
import datetime as dt
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(ROOT, "intelligence", "events.json")

MONTH = (r"(?:January|February|March|April|May|June|July|August|September|"
         r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept?|Oct|"
         r"Nov|Dec)")
PATTERNS = [
    MONTH + r"\.?\s+\d{1,2}\s*[–—-]\s*(?:" + MONTH +
    r"\.?\s+)?\d{1,2},?\s*20\d\d",
    r"\d{1,2}\s*[–—-]\s*\d{1,2}\s+" + MONTH + r"\.?\s*,?\s*20\d\d",
    MONTH + r"\.?\s+\d{1,2},?\s*20\d\d",
    # ISO, because AWS writes its summit dates that way -- 2026-07-30 -- and
    # every pattern above wants a month NAME. Thirty-one summits with dates
    # sat behind that gap while this page said AWS had announced nothing.
    r"20\d\d-\d{2}-\d{2}",
    # A range with no year at all: "Nov. 30 - Dec. 4". re:Invent's own page
    # says exactly that, and puts the year in the <title>. Requiring a year
    # beside the day is why this watcher reported nothing for the single
    # most obvious event on the site.
    MONTH + r"\.?\s+\d{1,2}\s*[–—-]\s*" + MONTH + r"\.?\s+\d{1,2}",
]


MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _is_future(s, today):
    """Is this date-shaped string actually still ahead of us?

    The first version compared only the YEAR, and on its first run it reported
    "Google Cloud Next 2027 -- April 22-24, 2026" as news. That date had
    already passed; it is the old Next sitting on the page the new one will
    eventually replace. Comparing years let every stale date through for the
    rest of the year it belonged to.

    Parsed properly, a past date is not news. Anything that will not parse is
    still reported -- being told about something unclear is the job; deciding
    it is nothing is not.
    """
    year_m = re.search(r"20\d\d", s)
    if not year_m:
        # No year in the string is not the same as "not in the future".
        #
        # "Nov. 30 - Dec. 4" is re:Invent's own wording, and this returned
        # False for it -- so the pattern added specifically to catch that
        # shape was then thrown away one line later, and the watcher reported
        # "still nothing" about a page whose title says the dates. The year
        # for these comes from the row's name, which only to_range() knows
        # about, so the decision belongs there: pass it along as a candidate
        # and let the thing that can resolve it decide.
        return True
    year = int(year_m.group(0))

    mon_m = re.search(r"[A-Za-z]{3}", s)
    month = MONTHS.get(mon_m.group(0).lower()) if mon_m else None
    if month is None:
        return year >= today.year

    # Days only, with the year taken out of the string first.
    #
    # Scanning the whole string for one- and two-digit runs also finds "20"
    # and "26" inside "2026", and the largest of those can outrank the real
    # day. Worse, the first version of this line carried two literal backspace
    # bytes where \b word boundaries were meant -- a heredoc ate them -- so it
    # matched nothing at all, max() raised on the empty list, and every date
    # fell through to comparing YEARS. That passes for anything in the current
    # year, which is how "April 22-24, 2026" was reported as still ahead of a
    # day in September. It reads correctly in every editor: the bytes are
    # invisible.
    without_year = s.replace(year_m.group(0), " ")
    days = [int(d) for d in re.findall(r"\d{1,2}", without_year)
            if 1 <= int(d) <= 31]
    if not days:
        return year >= today.year
    try:
        # the LAST day mentioned, so a range ending tomorrow still counts
        return dt.date(year, month, max(days)) >= today
    except ValueError:
        return year >= today.year


def dates_on(page_text):
    """Every date-shaped string, de-duplicated, in the order they appear."""
    found = []
    flat = re.sub(r"\s+", " ", page_text)
    for p in PATTERNS:
        for m in re.finditer(p, flat, re.I):
            s = " ".join(m.group(0).split())
            if s not in found:
                found.append(s)
    return found


def to_range(s, name, today):
    """Turn one date-shaped string into (start, end), or None.

    Handles the three shapes these pages actually use:

        Nov 17-20, 2026        a range with the year at the end
        2026-11-30             ISO, as AWS writes summit dates
        Nov. 30 - Dec. 4       a range with NO year -- re:Invent's own words

    The last one is why this function takes the event's NAME. "AWS re:Invent
    2026" carries the year the page leaves out, and using the row's own name
    rather than scraping a year from somewhere else on the page means the
    answer cannot come from an unrelated number. A range that crosses into
    January would need more care; none of these do, and a guess there would be
    exactly the kind of cleverness this page is meant not to have -- so a
    crossing range returns None and stays manual.
    """
    s = " ".join(s.split())
    iso = re.match(r"^(20\d\d)-(\d{2})-(\d{2})$", s)
    if iso:
        d = dt.date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        return (d.isoformat(), d.isoformat())

    year_m = re.search(r"20\d\d", s)
    if year_m:
        year = int(year_m.group(0))
    else:
        nm = re.search(r"20\d\d", name or "")
        if not nm:
            return None
        year = int(nm.group(0))

    # Strip the year ONLY if there is one.
    #
    # This line read s.replace(year_m.group(0) if year_m else "", " "), and
    # str.replace("") does not mean "replace nothing" -- it inserts the
    # replacement between every character. "Nov. 30 - Dec. 4" became
    # "N o v .  3 0  -  D e c .  4", so the digits came out as 3, 0 and 4 and
    # re:Invent was written as 3 November instead of 30 November.
    #
    # A plausible wrong date, on the one page whose entire promise is that it
    # does not publish those, produced by a line that looks like a no-op. No
    # check here would have caught it: 3 November 2026 is a perfectly valid
    # date on a perfectly valid AWS link. Only running it and reading the
    # output did.
    text = s.replace(year_m.group(0), " ") if year_m else s
    months = re.findall(MONTH, s, re.I)
    days = [int(d) for d in re.findall(r"\d{1,2}", text)
            if 1 <= int(d) <= 31]
    if not months or not days:
        return None
    m1 = MONTHS.get(months[0][:3].lower())
    m2 = MONTHS.get(months[-1][:3].lower()) if len(months) > 1 else m1
    if not m1 or not m2:
        return None
    d1, d2 = days[0], days[-1]
    try:
        start = dt.date(year, m1, d1)
        end = dt.date(year, m2, d2)
    except ValueError:
        return None
    if end < start:
        return None                      # crosses a year boundary: not ours
    if end < today:
        return None
    return (start.isoformat(), end.isoformat())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true",
                    help="machine-readable, for the workflow")
    ap.add_argument("--write", action="store_true",
                    help="fill in a date when the page leaves no doubt")
    args = ap.parse_args()

    data = json.load(io.open(STORE, encoding="utf-8"))
    waiting = [e for e in data.get("events", []) if not e.get("announced")]
    if not waiting:
        print("  nothing is waiting on dates.")
        return 0

    from playwright.sync_api import sync_playwright

    # Anything in the past is a leftover: re:Invent's page today carries 2025
    # attendee quotes, and Google's still shows a Next date that has gone.
    # Only a date from today onward is news.
    today = dt.date.today()
    news, wrote = [], []
    print("  %d row(s) waiting on dates" % len(waiting))
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for e in waiting:
            url = e.get("url")
            ctx = b.new_context(viewport={"width": 1440, "height": 1400})
            pg = ctx.new_page()
            try:
                pg.goto(url, wait_until="load", timeout=80000)
                pg.wait_for_timeout(6000)
                text = pg.evaluate("() => document.body.innerText")
            except Exception as exc:                        # noqa: BLE001
                print("     ??   %-28s could not render (%s)"
                      % (e.get("name", "")[:28], str(exc)[:40]))
                ctx.close()
                continue
            ctx.close()

            found = dates_on(text)
            future = [d for d in found if _is_future(d, today)]

            # One future date on the page, and only one, may be written.
            #
            # This is the line between reading and guessing, and it is a line
            # rather than a refusal. Challenged on whether these three really
            # had to stay manual, and they do not -- what has to stay manual
            # is AMBIGUITY.
            #
            # re:Invent's page says "Nov. 30 - Dec. 4" once, and its title
            # says it again; the year comes from the row's own name. That is
            # not a guess, it is a reading, and a machine can do it every
            # morning more reliably than a person will.
            #
            # Two different future dates on one page IS a guess about which is
            # the event, so it reports and waits. Google Next is the case: its
            # page carries a date that has passed, so nothing future is found
            # and nothing is written, correctly.
            ranges = []
            for d in future:
                r = to_range(d, e.get("name"), today)
                if r and r not in ranges:
                    ranges.append(r)

            if len(ranges) == 1 and args.write:
                start, end = ranges[0]
                e["start"], e["end"] = start, end
                e["announced"] = True
                e["verified"] = today.isoformat()
                e["note"] = ("Dates read automatically from %s, which carried "
                             "exactly one future date: %r."
                             % (url, future[0]))
                wrote.append((e.get("name"), start, end, future[0]))
                print("     SET  %-28s %s -> %s"
                      % (e.get("name", "")[:28], future[0], start))
            elif future:
                news.append({"name": e.get("name"), "url": url,
                             "dates": future[:6],
                             "why": ("%d candidate dates -- too many to choose "
                                     "between" % len(ranges)) if len(ranges) > 1
                                    else "could not resolve to a date range"})
                print("     NEW  %-28s %s"
                      % (e.get("name", "")[:28], ", ".join(future[:4])))
            else:
                print("     ok   %-28s still nothing" % e.get("name", "")[:28])
        b.close()

    if wrote:
        with io.open(STORE, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print("\n  wrote %d date(s) into the store" % len(wrote))

    print()
    if args.json:
        print(json.dumps(news, indent=2))
    if news:
        print("  %d row(s) may now have dates." % len(news))
        print("  These are CANDIDATES, not facts. Open each page, read what it")
        print("  says, then set start/end/announced and verified in")
        print("  intelligence/events.json. Nothing here writes to the store:")
        print("  the first date-shaped string on a marketing page is as often")
        print("  a testimonial as an event.")
        return 2                      # distinct from a failure
    print("  No cloud has published dates for anything still waiting.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
