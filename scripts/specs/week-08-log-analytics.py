# -*- coding: utf-8 -*-
"""Week 08 to the Master Standard.

Expected values below came out of week-08-log-analytics/scripts/validate.sh --
the assertion is the expected value. The measured column is what the post and
README already recorded on the day.

Permissions read from the Terraform: this week declares an
azurerm_role_assignment (Monitoring Metrics Publisher on the DCR), so it really
does need User Access Administrator. Week 09 does not. That difference was
stated nowhere before.
"""
GH = ("https://github.com/katta698/Azure-Platform-Engineering-Lab"
      "/tree/main/week-08-log-analytics")

SPEC = {
    "post": "posts/week-08-log-analytics.html",

    "overview_after": """
<table>
  <tbody>
    <tr><td><strong>Difficulty</strong></td><td>Advanced &mdash; custom tables and ingest-time transformations, and two of the steps are only reachable through <code>azapi</code></td></tr>
    <tr><td><strong>Time to complete</strong></td><td>One to two hours. Part of it is unavoidable waiting: the role assignment took <strong>five minutes</strong> to propagate before ingestion stopped returning 403</td></tr>
    <tr><td><strong>Deployment method</strong></td><td>Terraform (<code>azurerm</code> + <code>azapi</code>), state in HCP Terraform, local execution</td></tr>
    <tr><td><strong>Source and lab guide</strong></td><td><a href="%s">week-08-log-analytics on GitHub</a> &mdash; exact prerequisites, variables, commands, expected outputs and cleanup</td></tr>
  </tbody>
</table>

<p><strong>This week is designed to stay up.</strong> Later weeks send their
logs here and an idle workspace costs nothing, so <code>cleanup.sh</code>
refuses to run without <code>--force</code>.</p>
""" % GH,

    "prereqs": """
<ul>
  <li><strong>Permissions:</strong> Contributor <em>and</em> <strong>User
  Access Administrator</strong> on the subscription. The second is not
  optional here &mdash; the lab grants <code>Monitoring Metrics Publisher</code>
  on the data collection rule, and Contributor cannot create role
  assignments.</li>
  <li><strong>A mailbox you can receive at.</strong> <code>alert_email</code>
  is a required variable with no default, because a daily cap that trips
  silently is data loss. It lives in <code>terraform.tfvars</code>, which is
  gitignored.</li>
  <li><strong>Terraform &ge; 1.10</strong>, with <code>azurerm</code> 5.x
  <em>and</em> <code>azapi</code> 2.x. <code>azapi</code> is not optional:
  <code>azurerm_log_analytics_workspace_table</code> has nowhere to put a
  schema, so the two custom tables have to be created through ARM
  directly.</li>
  <li><strong>Two resource providers</strong> on the subscription &mdash;
  <code>Microsoft.OperationalInsights</code> and
  <code>Microsoft.Insights</code>. The deploy script registers them.</li>
  <li><strong>No prior week is required.</strong> This is the one every later
  week depends on, not the other way round.</li>
</ul>

<p>Every variable, the role scope and the table schemas are in the
<a href="%s#2-prerequisites">lab guide on GitHub</a>, which is the reproducible
half of this write-up.</p>
""" % GH,

    "validation": """
<p>A successful <code>terraform apply</code> proves the workspace, the rule and
the tables exist. It proves nothing about whether the transformation actually
filters &mdash; and <strong>a transformation that filters nothing looks
identical in the portal to one that filters everything</strong>. The only way
to know is to send known data and count what survived.</p>

<div class="table-scroll">
<table>
  <thead><tr><th>Test</th><th>Expected</th><th>Actual</th><th>Status</th></tr></thead>
  <tbody>
    <tr><td>Workspace pricing and cap</td><td><code>PerGB2018</code> with a daily cap set</td><td><strong>pay-as-you-go, cap set</strong></td><td>PASS</td></tr>
    <tr><td>Table plans</td><td><code>PlatformLogs_CL</code> on Analytics, <code>PlatformVerbose_CL</code> on Basic</td><td><strong>both on their intended plans</strong></td><td>PASS</td></tr>
    <tr><td>Collection endpoint and rule</td><td>both resolve</td><td><strong>both resolved</strong></td><td>PASS</td></tr>
    <tr><td>Ingestion accepted</td><td>HTTP 204</td><td><strong>204</strong></td><td>PASS</td></tr>
    <tr><td>Transformation drops rows before billing</td><td>only Warning and above stored &mdash; 20 of the 100 sent</td><td><strong>20 stored, 80 dropped</strong> at ingest and never billed</td><td>PASS</td></tr>
    <tr><td>The cap has an alarm that fires</td><td>an <em>enabled</em> query rule wired to an action group</td><td><strong>enabled rule, attached</strong></td><td>PASS</td></tr>
  </tbody>
</table>
</div>
""",

    "edits": [
        # Challenges prose -> the required four-part shape. Same findings,
        # same measured numbers.
        ("""<p><strong>You cannot set a plan on a table that does not exist.</strong> The
first attempt put <code>AzureDiagnostics</code> on Basic and got
<code>ResourceNotFound</code>: a new workspace has no built-in tables, because
they materialise when data of that type first arrives — after the point you
would want the cheap plan in place. The collection rule then failed with a bare
<code>InvalidPayload</code> for the same reason. Hence custom tables, created
with <code>azapi</code>, because
<code>azurerm_log_analytics_workspace_table</code> has nowhere to put a schema.</p>

<p><strong>Ingestion returns 403 until RBAC propagates.</strong> Posting needs
<code>Monitoring Metrics Publisher</code> <em>on the DCR</em>, and granting it is
not instant. Measured: ten attempts over <strong>five minutes</strong>, then 204.</p>

<p><strong>The cap had no alarm, and the check said it did.</strong> An action
group is a destination; nothing fires it without a rule. The test counted action
groups and passed while the cap could still trip in silence. A mailbox is not a
smoke detector, and a check that goes green while the thing it verifies is
missing is worse than no check.</p>""",

         """<p><strong>A plan cannot be set on a table that does not exist yet.</strong></p>

<ul>
  <li><strong>Problem:</strong> putting <code>AzureDiagnostics</code> on the
  Basic plan returned <code>ResourceNotFound</code>, and the collection rule
  then failed with a bare <code>InvalidPayload</code>.</li>
  <li><strong>Root cause:</strong> a new workspace has no built-in tables. They
  materialise when data of that type first arrives &mdash; which is after the
  point you would want the cheap plan already in place.</li>
  <li><strong>Resolution:</strong> custom tables, created with
  <code>azapi</code>, because
  <code>azurerm_log_analytics_workspace_table</code> has nowhere to put a
  schema.</li>
  <li><strong>Lesson learned:</strong> cost controls that depend on a resource
  existing cannot be applied to resources Azure creates on demand. Create the
  table yourself and the plan is yours to set from the start.</li>
</ul>

<p><strong>Ingestion returns 403 until RBAC propagates.</strong></p>

<ul>
  <li><strong>Problem:</strong> posting to the ingestion endpoint returned 403
  immediately after a successful apply.</li>
  <li><strong>Root cause:</strong> posting needs
  <code>Monitoring Metrics Publisher</code> <em>on the DCR</em>, and granting a
  role is not instant.</li>
  <li><strong>Resolution:</strong> retry. Measured: ten attempts over
  <strong>five minutes</strong>, then 204.</li>
  <li><strong>Lesson learned:</strong> a 403 straight after a role assignment
  is a clock, not a misconfiguration. Validation has to retry or it reports a
  correct deployment as broken.</li>
</ul>

<p><strong>The cap had no alarm, and the check said it did.</strong></p>

<ul>
  <li><strong>Problem:</strong> the validation passed while the daily cap could
  still trip in total silence.</li>
  <li><strong>Root cause:</strong> the test counted <em>action groups</em>. An
  action group is a destination; nothing fires it without a rule, and there was
  no rule.</li>
  <li><strong>Resolution:</strong> assert on an <em>enabled query rule wired to
  an action group</em>, which is the thing that actually sends the mail.</li>
  <li><strong>Lesson learned:</strong> a mailbox is not a smoke detector. A
  check that goes green while the thing it verifies is missing is worse than no
  check, because it stops anyone looking.</li>
</ul>"""),
    ],

    "captions": {
        "week-08-architecture.svg":
            "<strong>The whole week on one page.</strong> 100 rows in, 20 out: "
            "the transformation is applied in the collection rule, so the 80 "
            "dropped rows are never billed at all. The two tables below it sit "
            "on different plans, which is the second lever.",
        "03-table-plans.png":
            "<strong>Checkpoint:</strong> the two custom tables on the plans "
            "the Terraform asked for &mdash; <code>PlatformLogs_CL</code> on "
            "Analytics with 30 days interactive, "
            "<code>PlatformVerbose_CL</code> on Basic with none. The six "
            "built-in tables are all stuck on Analytics, which is exactly why "
            "this week creates its own.",
        "04-daily-cap.png":
            "<strong>What the plans are worth, in Azure's own numbers:</strong> "
            "$2.76/GB for Analytics against $0.60 for Basic. The cap is "
            "configured here too &mdash; and the commitment tier that offers a "
            "20% discount starts at 100 GB/day, far above anything this lab "
            "produces.",
    },

    "subheads": {
        "Why — The Problem This Solves": "",
        "What You Need to Know — Skills & Tools": "",
        "Architecture — How It Fits Together": "",
        "How We Built It — In Deployment Order": "",
        "How It's Tested": "What the test actually sends",
        "Security — Controls at Every Layer": "Security",
        "Cost": "Cost",
        "Challenges — What Actually Went Wrong": "",
        "Cleanup": "Cleanup",
        "Key Takeaways": "Key takeaways",
        "References": "References",
    },
}
