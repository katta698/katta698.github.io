# -*- coding: utf-8 -*-
"""Week 03 to the Master Standard.

Expected values from week-03-module-factory/scripts/validate.sh; actual from
the repo README's measured table (8 passed, 0 failed across both stages).

Note the check count: validate.sh declares seven numbered checks and the run
reports eight assertions. The table below lists the seven checks and quotes
the recorded results; it does not claim "8 checks".
"""
GH = ("https://github.com/katta698/Azure-Platform-Engineering-Lab"
      "/blob/main/week-03-module-factory/LAB.md")

SPEC = {
    "post": "posts/week-03-module-factory.html",

    "overview_after": """
<table>
  <tbody>
    <tr><td><strong>Difficulty</strong></td><td>Intermediate &mdash; the Terraform is small; the version discipline is the lab</td></tr>
    <tr><td><strong>Time to complete</strong></td><td>About an hour, including publishing two module versions to the registry</td></tr>
    <tr><td><strong>Deployment</strong></td><td>Terraform (<code>azurerm</code>, <code>azapi</code>, <code>random</code>), two stages, HCP Terraform private module registry, local execution</td></tr>
    <tr><td><strong>Measured cost</strong></td><td><strong>$0.00</strong> &mdash; two empty storage accounts and a workspace inside the free retention floor</td></tr>
    <tr><td><strong>Full lab guide</strong></td><td><a href="%s">LAB.md</a> &mdash; prerequisites, variables, commands, expected outputs, validation and cleanup</td></tr>
  </tbody>
</table>
""" % GH,

    "prereqs": """
<ul>
  <li><strong>An HCP Terraform organization with a private module
  registry.</strong> This is the one prerequisite that is not Azure at all:
  the week publishes two versions of a module and then consumes them by
  version, so a registry you can publish to is the whole exercise.</li>
  <li><strong>A token that can publish modules</strong> &mdash; publishing is
  by tag, through the registry API, not through the UI.</li>
  <li><strong>Contributor</strong> on the subscription. No role assignments
  are created, so User Access Administrator is not needed.</li>
  <li><strong>Terraform &ge; 1.10</strong> with <code>azurerm</code>
  <strong>~&gt; 5.2</strong>, plus <code>azapi</code>, <code>random</code> and
  <code>modtm</code> &mdash; the last three arrive transitively through the
  Azure Verified Module this week wraps, which is itself the point about
  dependency trees.</li>
  <li><strong>Three resource providers:</strong>
  <code>Microsoft.Storage</code>, <code>Microsoft.OperationalInsights</code>
  and <code>Microsoft.Insights</code>.</li>
  <li><strong>No prior week is required</strong>, though the Log Analytics
  workspace here is this week's own and is not week 08's.</li>
</ul>

<p>Every variable, both stages and the publish commands are in the
<a href="%s#1-prerequisites">lab guide</a>, which is the reproducible half of
this write-up.</p>
""" % GH,

    "validation": """
<p>A successful apply proves two storage accounts exist. It proves nothing
about the thing this week is actually claiming &mdash; that a pinned major
version protects an existing consumer from a breaking change in a new one. So
the checks compare the two consumers against each other rather than against a
specification.</p>

<div class="table-scroll">
<table>
  <thead><tr><th>Test</th><th>Expected</th><th>Actual</th><th>Status</th></tr></thead>
  <tbody>
    <tr><td>Both versions published and usable</td><td>both resolve from the registry</td><td><strong><code>1.0.0 ok</code>, <code>2.0.0 ok</code></strong></td><td>PASS</td></tr>
    <tr><td>The baseline the module decides</td><td>applied to both accounts regardless of version</td><td><strong>both <code>TLS1_2</code></strong>, no public blob access, <code>cost-center=platform-lab</code></td><td>PASS</td></tr>
    <tr><td>The 1.0.0 consumer's diagnostics</td><td>none &mdash; 1.0.0 allowed the workspace to be omitted</td><td><strong>0</strong> on the account, <strong>0</strong> on the blob service</td><td>PASS</td></tr>
    <tr><td>The 2.0.0 consumer's diagnostics</td><td>two, on two different resources</td><td><strong>1</strong> on the account (<code>Transaction</code>), <strong>1</strong> on the blob service (<code>audit</code>)</td><td>PASS</td></tr>
    <tr><td><strong>The silent break</strong></td><td>shared-key access differs between versions</td><td><strong>1.0.0 <code>True</code>, 2.0.0 <code>False</code></strong></td><td>PASS</td></tr>
    <tr><td><strong>The loud break</strong></td><td>1.0.0's exact inputs fail against 2.0.0 <em>before</em> planning</td><td><strong><code>Missing required argument</code></strong></td><td>PASS</td></tr>
    <tr><td>Deployed state matches configuration</td><td>no drift</td><td><strong>none</strong></td><td>PASS</td></tr>
  </tbody>
</table>
</div>

<p><strong>The two breaks are different animals, and that is the lesson.</strong>
The loud one stops you at <code>init</code> with a missing argument. The silent
one applies cleanly and quietly turns off shared-key access &mdash; same inputs,
different behaviour, no error. A consumer who skimmed the changelog meets the
second one in production.</p>

<p><strong>And adding the new major changed nothing about the old consumer.</strong>
The stage-v2 plan, read as JSON rather than eyeballed:</p>

<pre><code>module.app_a changes in this plan: 0</code></pre>

<p>Four resources created, all of them <code>module.app_b</code>. That is the
property the pin buys &mdash; and it is a claim about a <em>plan</em>, which is
why <code>deploy.sh</code> saves the plan and reports on it before applying.
After the apply, the plan is gone.</p>
""",

    "captions": {
        "week-03-architecture.svg":
            "<strong>The whole week on one page.</strong> This lab's module "
            "wraps an exactly pinned Azure Verified Module, publishes by tag "
            "through the registry API, and is consumed twice &mdash; once at "
            "1.0.0 and once at 2.0.0.",
        "04-hcp-registry.png":
            "<strong>Checkpoint:</strong> both versions live in the private "
            "registry, so a consumer can pin either. A module that exists only "
            "on someone's laptop cannot be pinned, which is the problem the "
            "registry solves.",
        "01-both-accounts-deployed.png":
            "<strong>The two consumers side by side.</strong> Identical inputs, "
            "different module majors &mdash; and from the portal's resource "
            "list alone you cannot tell which is which. That is what makes the "
            "silent break silent.",
        "02-v1-shared-key-enabled.png":
            "<strong>1.0.0: shared key access Enabled.</strong> Nobody asked "
            "for this; it is simply what the older major left alone.",
        "03-v2-shared-key-disabled.png":
            "<strong>2.0.0: the same input, Disabled.</strong> No error, no "
            "warning, no changed argument &mdash; the new major decided "
            "differently. Anything authenticating with a key stops working on "
            "upgrade.",
    },

    "subheads": {
        "Why — The Problem This Solves": "",
        "What You Need to Know — Skills & Tools": "",
        "Architecture — How It Fits Together": "",
        "How We Built It — Step by Step": "",
        "Security — Controls at Every Layer": "Security",
        "Cost": "Cost",
        "Challenges — What Actually Went Wrong": "",
        "Cleanup": "Cleanup",
        "Key Takeaways": "Key takeaways",
        "References": "References",
    },
}
