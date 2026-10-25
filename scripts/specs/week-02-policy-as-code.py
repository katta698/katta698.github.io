# -*- coding: utf-8 -*-
"""Week 02 to the Master Standard.

Actual values from the repo README's stage tables, measured 2026-08-25.
Expected values from scripts/validate.sh's check names and the stage design.

This week's three stages ARE the evidence: audit (nothing changes),
the deliberate failure (the identity exists but cannot act), and remediation
with the grants in place. The validation table is built around that, because
the middle row is the one that proves the other two mean something.
"""
GH = ("https://github.com/katta698/Azure-Platform-Engineering-Lab"
      "/blob/main/week-02-policy-as-code/LAB.md")

SPEC = {
    "post": "posts/week-02-policy-as-code.html",

    "overview_after": """
<table>
  <tbody>
    <tr><td><strong>Difficulty</strong></td><td>Advanced &mdash; nine resources, three stages, and the interesting part is what the identity is <em>not</em> allowed to do</td></tr>
    <tr><td><strong>Time to complete</strong></td><td>Two to three hours. Compliance scans are not instant, and the lab forces one per stage</td></tr>
    <tr><td><strong>Deployment</strong></td><td>Terraform (<code>azurerm</code>), three stages, state in HCP Terraform, local execution</td></tr>
    <tr><td><strong>Measured cost</strong></td><td><strong>$0.00</strong> &mdash; policy, identities and two empty storage accounts are free; the workspace stays inside the 30-day retention floor</td></tr>
    <tr><td><strong>Full lab guide</strong></td><td><a href="%s">LAB.md</a> &mdash; prerequisites, variables, commands, expected outputs, validation and cleanup</td></tr>
  </tbody>
</table>
""" % GH,

    "prereqs": """
<ul>
  <li><strong>A management group hierarchy</strong> to assign policy at. The
  lab assigns at a dev landing-zone group; any group works, and the root group
  is a deliberate non-default because a mistake there reaches
  everything.</li>
  <li><strong>Permission to write policy at that scope</strong> &mdash;
  Resource Policy Contributor or Owner on the management group, not merely on
  the subscription underneath it.</li>
  <li><strong>User Access Administrator</strong> (or Owner), because stage 3
  grants three roles to the remediation identity. <strong>Those grants are the
  whole experiment</strong>: stage 2 deliberately runs without them.</li>
  <li><strong>Contributor</strong> on the subscription holding the test bed.</li>
  <li><strong>Terraform &ge; 1.10</strong> with <code>azurerm</code>
  <strong>~&gt; 5.2</strong>.</li>
  <li><strong>Five resource providers:</strong>
  <code>Microsoft.PolicyInsights</code>, <code>Microsoft.Storage</code>,
  <code>Microsoft.OperationalInsights</code>, <code>Microsoft.Insights</code>
  and <code>Microsoft.ManagedIdentity</code>.</li>
  <li><strong>Patience with compliance scans.</strong> Policy evaluation is
  asynchronous; the scripts force a scan and wait rather than asking once and
  concluding the policy does not work.</li>
</ul>

<p>Every variable and all three stages are in the
<a href="%s#1-prerequisites">lab guide</a>, which is the reproducible half of
this write-up.</p>
""" % GH,

    "validation": """
<p>A successful apply proves two definitions, an initiative and an assignment
exist. It proves nothing about whether the policy evaluates, whether the
identity can act, or whether anything was actually changed &mdash; and the
middle one is the claim worth testing, because an identity that exists is not
an identity that can do anything.</p>

<p><strong>The three stages are the experiment.</strong> Stage 2 is a
deliberate failure, and without it the other two prove much less.</p>

<div class="table-scroll">
<table>
  <thead><tr><th>Stage / test</th><th>Expected</th><th>Actual</th><th>Status</th></tr></thead>
  <tbody>
    <tr><td><strong>1. Audit</strong> &mdash; compliance after a forced scan</td><td>non-compliant, nothing changed</td><td><strong>Non-compliant, 0% (0 of 2)</strong>; <code>storage-diagnostics</code> flags 2 accounts</td><td>PASS</td></tr>
    <tr><td>1. Resources changed by an audit</td><td><strong>none</strong></td><td><strong>none</strong></td><td>PASS</td></tr>
    <tr><td>1. The assignment carries an identity even in audit mode</td><td>identity present, <strong>zero grants</strong></td><td><strong>present, no role assignments</strong></td><td>PASS</td></tr>
    <tr><td><strong>2. The deliberate failure</strong> &mdash; remediation with no grants</td><td>the identity exists and <em>cannot act</em></td><td><strong>remediation fails</strong></td><td>PASS (by design)</td></tr>
    <tr><td><strong>3. Remediation</strong> &mdash; <code>storage-diagnostics</code></td><td>both accounts remediated</td><td><strong>2 resources, 2 succeeded, 0 failed</strong></td><td>PASS</td></tr>
    <tr><td>3. Remediation &mdash; <code>inherit-tag</code></td><td>every in-scope resource tagged</td><td><strong>4 resources, 4 succeeded, 0 failed</strong></td><td>PASS</td></tr>
    <tr><td>3. Compliance after a forced re-scan</td><td>compliant</td><td><strong>Compliant, 100% (5 of 5), 0 non-compliant</strong></td><td>PASS</td></tr>
  </tbody>
</table>
</div>

<p><strong>Read back from the resources, not from the tasks.</strong> A
remediation task reporting success says the task ran; it does not say the
resource changed:</p>

<pre><code>stwk02a…  diag-to-law -> law-wk02-dev-scus-001   cost-center=platform-lab
stwk02b…  diag-to-law -> law-wk02-dev-scus-001   cost-center=platform-lab
law-wk02-dev-scus-001                            cost-center=platform-lab
id-wk02-policy-remediation                       cost-center=platform-lab</code></pre>

<p><strong>What stage 2 establishes.</strong> Nothing changed between stages 2
and 3 except three role assignments &mdash; same definitions, same initiative,
same assignment, same identity. So what makes a policy identity dangerous is
<em>not its presence</em> but its grants, and an audit-only assignment that
holds an identity with no roles is genuinely inert.</p>
""",

    "captions": {},

    "subheads": {
        "Why — The Problem This Solves": "",
        "What You Need to Know — Skills & Tools": "",
        "Architecture — How It Fits Together": "",
        "How We Built It — Step by Step": "",
        "How We Built It — In Deployment Order": "",
        "Security — Controls at Every Layer": "Security",
        "Cost": "Cost",
        "Challenges — What Actually Went Wrong": "",
        "Cleanup": "Cleanup",
        "Key Takeaways": "Key takeaways",
        "References": "References",
    },
}
