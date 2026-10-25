# -*- coding: utf-8 -*-
"""Week 09 to the Master Standard.

Only three things were missing: the Lab Overview facts, a Prerequisites
section, and captions on two figures. The validation table existed but carried
What / Measured; the standard asks for Test / Expected / Actual / Status.

Every Expected value below was read out of week-09-container-apps/scripts/
validate.sh -- the assertion IS the expected value. Nothing here is estimated.
Permissions were read from the Terraform: the week declares no
azurerm_role_assignment, so Contributor is genuinely sufficient, which is the
opposite of week 10.
"""
GH = ("https://github.com/katta698/Azure-Platform-Engineering-Lab"
      "/tree/main/week-09-container-apps")

SPEC = {
    "post": "posts/week-09-container-apps.html",

    # The facts table reads better after the paragraph that states the problem.
    "overview_after": """
<table>
  <tbody>
    <tr><td><strong>Difficulty</strong></td><td>Intermediate &mdash; assumes containers and Terraform; the scaling behaviour is what the week is about</td></tr>
    <tr><td><strong>Time to complete</strong></td><td>About an hour. The scale-to-zero test cannot be hurried: it waits for the idle timer, which took <strong>602 seconds</strong> here</td></tr>
    <tr><td><strong>Deployment method</strong></td><td>Terraform (<code>azurerm</code>), state in HCP Terraform, local execution</td></tr>
    <tr><td><strong>Source and lab guide</strong></td><td><a href="%s">week-09-container-apps on GitHub</a> &mdash; exact prerequisites, variables, commands, expected outputs and cleanup</td></tr>
  </tbody>
</table>
""" % GH,

    "prereqs": """
<ul>
  <li><strong>Permissions:</strong> <strong>Contributor</strong> on the
  workload subscription is enough. This week creates no role assignment, so it
  does not need User Access Administrator &mdash; worth saying, because the
  following week does.</li>
  <li><strong>Reader</strong> on the resource group holding the Log Analytics
  workspace. The workspace is read through a data source and never
  modified.</li>
  <li><strong>An existing Log Analytics workspace.</strong> This week sends its
  logs to the one week 8 built rather than creating its own. One subscription
  works fine; the lab splits the workload and the workspace across two.</li>
  <li><strong>Terraform &ge; 1.10</strong> with <code>azurerm</code> 5.x
  (1.16.6 was the version that actually ran here). azurerm 5.x requires an
  explicit <code>subscription_id</code> on every provider block.</li>
  <li><strong>Four resource providers</strong> on the workload subscription
  &mdash; <code>Microsoft.App</code>, <code>Microsoft.Insights</code>,
  <code>Microsoft.ManagedIdentity</code> and
  <code>Microsoft.OperationalInsights</code>. The deploy script registers them
  and waits; registration is per subscription and is a real precondition.</li>
  <li><strong>Builds on week 8</strong> (the workspace and its table plans).
  Week 8 does not need to still be deployed, only to exist.</li>
</ul>

<p>Versions, every variable and the role scopes are in the
<a href="%s#2-prerequisites">lab guide on GitHub</a>, which is the reproducible
half of this write-up.</p>
""" % GH,

    "validation": """
<p>A successful <code>terraform apply</code> proves the resources exist. It
says nothing about whether the app refuses plain HTTP, whether replicas
actually reach zero, or whether the logs land in the right tables &mdash; so
those are tested separately.</p>
""",

    "edits": [
        # What / Measured becomes the standard's four columns. Expected comes
        # from validate.sh; Actual is what was recorded on the day.
        ("""<table>
  <thead><tr><th>What</th><th>Measured</th></tr></thead>
  <tbody>
    <tr><td>HTTPS <code>GET /</code></td><td><strong>200</strong></td></tr>
    <tr><td>Plain HTTP on port 80</td><td><strong>301</strong> — never served in the clear</td></tr>
    <tr><td>Warm request, average of 3</td><td><strong>0.13 s</strong></td></tr>
    <tr><td>Idle before replicas reached 0</td><td><strong>602 s</strong></td></tr>
    <tr><td>First request after idle</td><td><strong>16.94 s</strong>, still a 200</td></tr>
    <tr><td>The penalty, stated plainly</td><td><strong>16.81 s</strong> on one request</td></tr>
    <tr><td>Log rows in week 8's workspace</td><td><strong>3</strong></td></tr>
    <tr><td>Rows in shared <code>AzureDiagnostics</code></td><td><strong>0</strong></td></tr>
  </tbody>
</table>""",
         """<table>
  <thead><tr><th>Test</th><th>Expected</th><th>Actual</th><th>Status</th></tr></thead>
  <tbody>
    <tr><td>HTTPS <code>GET /</code></td><td>200</td><td><strong>200</strong></td><td>PASS</td></tr>
    <tr><td>Plain HTTP on port 80</td><td>redirected or refused &mdash; never 200</td><td><strong>301</strong>, never served in the clear</td><td>PASS</td></tr>
    <tr><td>Warm request, average of 3</td><td>under 5 s</td><td><strong>0.13 s</strong></td><td>PASS</td></tr>
    <tr><td>Replicas reach 0 when idle</td><td>0 replicas within the cooldown</td><td><strong>602 s</strong> to zero</td><td>PASS</td></tr>
    <tr><td>First request after idle</td><td>still a 200, however slow</td><td><strong>16.94 s</strong>, still a 200</td><td>PASS</td></tr>
    <tr><td>Log rows in week 8's workspace</td><td>more than zero</td><td><strong>3</strong></td><td>PASS</td></tr>
    <tr><td>Rows in shared <code>AzureDiagnostics</code></td><td>0 &mdash; dedicated tables only</td><td><strong>0</strong></td><td>PASS</td></tr>
    <tr><td>The cold-start penalty</td><td>&mdash;</td><td><strong>16.81 s</strong> on one request</td><td>derived from the two rows above, not asserted</td></tr>
  </tbody>
</table>"""),
    ],

    "captions": {
        "week-09-architecture.svg":
            "<strong>The whole week on one page.</strong> One request path in, "
            "two log categories out across a subscription boundary. The arrow "
            "that matters is the one that stops: at zero replicas there is "
            "nothing running and nothing billing.",
        "01-hcp-workspace.png":
            "<strong>Checkpoint:</strong> the workspace reports <em>Local</em> "
            "execution and six objects &mdash; the five resources this week "
            "creates plus the data source that reads week 8's workspace. "
            "Reading it, rather than owning it, is the whole point of that "
            "last one.",
    },

    # The old h2 text is dropped where the new heading already says it.
    "subheads": {
        "Why — The Problem This Solves": "",
        "What You Need to Know — Skills & Tools": "",
        "Architecture — How It Fits Together": "",
        "How We Built It — In Deployment Order": "",
        "How It's Tested": "",
        "Security — Controls at Every Layer": "Security",
        "Cost": "Cost",
        "Challenges — What Actually Went Wrong": "",
        "Cleanup": "Cleanup",
        "Key Takeaways": "Key takeaways",
        "References": "References",
    },
}
