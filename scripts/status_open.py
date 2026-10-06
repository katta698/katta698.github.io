"""Is this incident still open? One rule, imported rather than retyped.

This module exists because the same mistake was written SEVEN times.

A vendor does not always tell you an incident has closed in the same way.
Azure and Google publish an end timestamp. AWS leaves the event on its
dashboard and marks it by prefixing the summary with "[RESOLVED]" -- that
prefix is the only signal its live feed carries. So an entry sitting in
status.json's clouds[] is NOT necessarily an open incident, and
len(clouds[c]) is not a count of what is wrong right now.

Every place that forgot this got the same symptom -- a resolved incident
presented as a live one -- and each was found by a person noticing a
number, not by a test:

  intelligence/status/pm.js     the map listed it under "Open right now"
  blog/assets/site-footer.js    the nav light said 3 open while the page said 2
  scripts/sync_blog.py          the blog sidebar card said "3 incidents"
  scripts/alert_new_incidents.py  would OPEN A GITHUB ISSUE announcing a
                                resolved incident as newly open, then later
                                announce it "cleared"
  scripts/build_status_feed.py  published it to Atom subscribers as open
  scripts/check_status_feed.py  asserted it MUST be in the feed marked open,
                                so the check enforced the bug
  .github/workflows/status.yml  committed "Cloud status: 3 active incident(s)"

Three of those were fixed one at a time, each with its own copy of the
rule and a comment asking the next file to agree. That is what produced
the fourth, fifth, sixth and seventh. A comment is not a mechanism, so
the rule now lives here and is imported.

Two implementations stay deliberately separate and are NOT replaced by
this:

  build_status_page.py resolved_at()      returns WHEN it closed, not just
                                          whether, because the page prints an
                                          "open for" duration
  check_status_lifecycle.py resolved_by_vendor()

Both are already correct. This module is the plain yes/no question that
the counting code asks, and it must agree with them.
"""


def still_open(incident):
    """True when the vendor has not told us this incident is over.

    An explicit end wins, because it is a time rather than an inference.
    Falling back to AWS's "[RESOLVED]" title prefix is matched after
    stripping leading whitespace and case-folding -- the live feed has
    carried both "[RESOLVED]" and a leading space before now.
    """
    if not isinstance(incident, dict):
        return False
    if (incident.get("end") or "").strip():
        return False
    title = (incident.get("title") or "").lstrip().upper()
    return not title.startswith("[RESOLVED]")


def open_only(incidents):
    """The subset of a clouds[] list that is actually open."""
    return [i for i in (incidents or []) if still_open(i)]


def count_open(clouds):
    """How many incidents are open across every cloud in a status payload.

    This is the number that belongs in a headline, a commit message or a
    status light. It is NOT sum(len(v) for v in clouds.values()), which is
    the bug this module was written for.
    """
    return sum(len(open_only(rows)) for rows in (clouds or {}).values()
               if isinstance(rows, list))
