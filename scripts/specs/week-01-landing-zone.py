# -*- coding: utf-8 -*-
"""Week 01 to the Master Standard.

Expected values from week-01-landing-zone/scripts/validate.sh, which runs
three parameterised attempts with a stated expectation each (two deny, one
allow). Actual from the post's own figures.

No "overview" injection: the post already has a Why section, and the tool
prepends, which would state the problem twice. No compliance rows in the
table either -- the carried-over prose analyses them better than a table row
could, and repeating them would be the same duplication in miniature.
"""
GH = ("https://github.com/katta698/Azure-Platform-Engineering-Lab"
      "/blob/main/week-01-landing-zone/LAB.md")

SPEC = {
    "post": "posts/week-01-azure-landing-zone.html",

    "overview_after": """
<table>
  <tbody>
    <tr><td><strong>Difficulty</strong></td><td>Intermediate &mdash; seven resources, but policy scope and evaluation timing are where the surprises are</td></tr>
    <tr><td><strong>Time to complete</strong></td><td>About 90 minutes, most of it waiting for compliance to evaluate</td></tr>
    <tr><td><strong>Deployment</strong></td><td>Terraform (<code>azurerm</code>), state in HCP Terraform, local execution</td></tr>
    <tr><td><strong>Measured cost</strong></td><td><strong>$0.00</strong> &mdash; management groups, policy and an empty VNet are all free</td></tr>
    <tr><td><strong>Full lab guide</strong></td><td><a href="%s">LAB.md</a> &mdash; prerequisites, variables, commands, expected outputs, validation and cleanup</td></tr>
  </tbody>
</table>
""" % GH,

    "prereqs": """
<ul>
  <li><strong>Permission to create management groups in the tenant.</strong>
  By default only the Global Administrator can, and it has to be
  <em>elevated</em> once at the tenant root before Azure RBAC applies there at
  all. This is the step that stops most people, and it is not a subscription
  permission.</li>
  <li><strong>Resource Policy Contributor or Owner</strong> at the management
  groups the assignments target &mdash; again, not on the subscription
  beneath them.</li>
  <li><strong>Contributor</strong> on a subscription for the test bed, which
  is where the deny attempts are made.</li>
  <li><strong>Terraform &ge; 1.10</strong> with <code>azurerm</code>
  <strong>~&gt; 5.2</strong>.</li>
  <li><strong>Four resource providers:</strong>
  <code>Microsoft.PolicyInsights</code>, <code>Microsoft.Resources</code>,
  <code>Microsoft.Network</code> and <code>Microsoft.Storage</code>.</li>
  <li><strong>Patience, and a way to force a scan.</strong> A deny is instant,
  because policy evaluates on write. The compliance <em>scan</em> of resources
  that already exist is scheduled &mdash; roughly 15 minutes after a resource
  changes, 30 after a subscription moves, and every 24 hours otherwise.
  <strong>An empty compliance report means "not scanned yet", not
  "compliant".</strong></li>
  <li><strong>No prior week is required.</strong> This is the first one.</li>
</ul>

<p>Every variable and the enforcement switch are in the
<a href="%s#1-prerequisites">lab guide</a>, which is the reproducible half of
this write-up.</p>
""" % GH,

    "validation": """
<p>A successful apply proves an assignment exists. It does not prove the
assignment <em>refuses</em> anything &mdash; so the validation attempts three
real creations against the live policy, stating its expectation before each
one.</p>

<div class="table-scroll">
<table>
  <thead><tr><th>Attempt</th><th>Expected</th><th>Actual</th><th>Status</th></tr></thead>
  <tbody>
    <tr><td>A NIC carrying a public IP</td><td><strong>denied</strong></td><td><strong>denied by policy</strong></td><td>PASS</td></tr>
    <tr><td>A storage account in <code>westeurope</code>, not an allowed location</td><td><strong>denied</strong></td><td><strong>denied by policy</strong></td><td>PASS</td></tr>
    <tr><td>A NIC with no public IP, in an allowed region</td><td><strong>allowed</strong></td><td><strong>created</strong></td><td>PASS</td></tr>
  </tbody>
</table>
</div>

<p><strong>The third attempt is the one most labs skip, and it is what makes
the first two mean anything.</strong> A policy that denied everything would
pass both deny tests and be useless.</p>
""",

    "captions": {},

    "subheads": {
        "Why — The Problem This Solves": "",
        "What You Need to Know — Skills & Tools": "",
        "Architecture — How It Fits Together": "",
        "How We Built It — Step by Step": "",
        "What Compliance Actually Reported": "What compliance actually reported",
        "Security — Controls at Every Layer": "Security",
        "Cost": "Cost",
        "Challenges — What Actually Went Wrong": "",
        "Cleanup": "Cleanup",
        "Key Takeaways": "Key takeaways",
        "References": "References",
    },
}
