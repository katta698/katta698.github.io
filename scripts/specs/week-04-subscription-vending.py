# -*- coding: utf-8 -*-
"""Week 04 to the Master Standard.

Expected values from week-04-subscription-vending/scripts/validate.sh; actual
from the repo README's measured table (7 passed, 0 failed after the vend
stage).

The prerequisite nobody stated: this week creates a REAL Azure subscription,
and a subscription cannot be deleted. vend_new_subscription defaults to false
for that reason, and the whole of "Cleanup" is about decommissioning rather
than removing.

Note on the edits below: replace a challenge heading AND its prose together.
An earlier attempt replaced the heading alone and hid the old one with
`hidden`, which duplicated the content and concealed an element instead of
removing it.
"""
GH = ("https://github.com/katta698/Azure-Platform-Engineering-Lab"
      "/blob/main/week-04-subscription-vending/LAB.md")

OLD_MODULE_CHALLENGE = """<h3>Microsoft's own vending module could not be used at all</h3>

<p><code>Azure/lz-vending/azurerm</code> is the obvious choice for this week. It
is Microsoft's, it has 1.4 million downloads, and its inputs map exactly onto
what vending means. It is unusable here: its <code>role_definitions</code> and
<code>cached_data</code> submodules require
<code>hashicorp/azurerm ~&gt; 4.0</code>, this lab standardised on
<code>~&gt; 5.2</code>, and the two constraints have no overlap.</p>

<pre><code>Could not retrieve the list of available versions for provider
hashicorp/azurerm: no available releases match the given constraints ~&gt; 4.0, ~&gt; 5.2</code></pre>

<p>Not a version to negotiate — <code>terraform init</code> refuses to resolve at
all. Version 7.0.3 is the newest of its 37 releases and predates azurerm 5.
Checked with azurerm at 5.5.0. Last week's post was about what a version pin does
to a consumer; this week opened by <em>being</em> that consumer.</p>"""

NEW_MODULE_CHALLENGE = """<p><strong>Microsoft's own vending module could not be used at all.</strong></p>

<ul>
  <li><strong>Problem:</strong> <code>terraform init</code> refused to resolve
  at all &mdash; <code>no available releases match the given constraints
  ~&gt; 4.0, ~&gt; 5.2</code>.</li>
  <li><strong>Root cause:</strong> <code>Azure/lz-vending/azurerm</code> is the
  obvious choice: Microsoft's own, 1.4 million downloads, inputs that map
  exactly onto what vending means. Its <code>role_definitions</code> and
  <code>cached_data</code> submodules require
  <code>hashicorp/azurerm ~&gt; 4.0</code>; this lab standardised on
  <code>~&gt; 5.2</code>. The constraints have no overlap, and 7.0.3 &mdash;
  newest of its 37 releases &mdash; predates azurerm 5. Checked with azurerm at
  5.5.0.</li>
  <li><strong>Resolution:</strong> write the four resources directly. Vending
  is an alias call, a management group association, a role assignment and a
  budget; the module's value is in everything it adds <em>after</em> that.</li>
  <li><strong>Lesson learned:</strong> a version pin is a compatibility claim
  about the whole dependency tree, not a preference. Week 03's post was about
  what a pin does to a consumer; this week opened by <em>being</em> that
  consumer.</li>
</ul>"""

SPEC = {
    "post": "posts/week-04-subscription-vending.html",

    "overview_after": """
<table>
  <tbody>
    <tr><td><strong>Difficulty</strong></td><td>Advanced &mdash; four resources, but they span three APIs and a billing account</td></tr>
    <tr><td><strong>Time to complete</strong></td><td>About an hour. Subscription creation is asynchronous and placement is not instant</td></tr>
    <tr><td><strong>Deployment</strong></td><td>Terraform (<code>azurerm</code>), two stages, state in HCP Terraform, local execution</td></tr>
    <tr><td><strong>Measured cost</strong></td><td><strong>$0.00</strong> &mdash; an empty subscription and a budget both cost nothing</td></tr>
    <tr><td><strong>Full lab guide</strong></td><td><a href="%s">LAB.md</a> &mdash; prerequisites, variables, commands, expected outputs, validation and cleanup</td></tr>
  </tbody>
</table>

<p><strong>Read this before running it.</strong> This week creates a
<em>real</em> Azure subscription, and <strong>a subscription cannot be
deleted</strong> &mdash; only cancelled, after which it lingers for a retention
window. <code>vend_new_subscription</code> defaults to <code>false</code> for
exactly that reason, and the cleanup section is about decommissioning rather
than removal.</p>
""" % GH,

    "prereqs": """
<ul>
  <li><strong>A Microsoft Customer Agreement billing account</strong>, plus the
  <em>billing profile</em> and <em>invoice section</em> the new subscription
  bills to. All three are required variables with no defaults. They identify
  your billing arrangement, so they live in <code>terraform.tfvars</code>,
  which is gitignored, and never in a <code>.tf</code> file.</li>
  <li><strong>Rights to create subscriptions on that invoice section.</strong>
  This is a <em>billing</em> permission, separate from Entra and from Azure
  RBAC &mdash; being Owner of a tenant does not grant it.</li>
  <li><strong>User Access Administrator</strong> (or Owner), because the lab
  creates a role assignment at subscription scope.</li>
  <li><strong>Write access to the management group hierarchy</strong> the
  subscription is placed into. Week 01 builds one; any hierarchy works.</li>
  <li><strong>Terraform &ge; 1.10</strong> with <code>azurerm</code>
  <strong>~&gt; 5.2</strong>. Microsoft's own
  <code>Azure/lz-vending/azurerm</code> module <em>cannot</em> be used with it
  &mdash; see Troubleshooting.</li>
  <li><strong>Two resource providers:</strong>
  <code>Microsoft.Consumption</code> and
  <code>Microsoft.CostManagement</code>.</li>
  <li><strong>An individual billing account cannot use the DevTest rate.</strong>
  The alias call refuses it outright, so the workload is
  <code>Production</code> whether or not that is what you wanted.</li>
</ul>

<p>Every variable and both stages are in the
<a href="%s#1-prerequisites">lab guide</a>, which is the reproducible half of
this write-up.</p>
""" % GH,

    "validation": """
<p>A successful apply proves an alias call returned. It does not prove the
subscription landed in the right management group, that the budget attached, or
that the grant is at the subscription rather than inherited from above &mdash;
and that last distinction is most of what vending means.</p>

<div class="table-scroll">
<table>
  <thead><tr><th>Test</th><th>Expected</th><th>Actual</th><th>Status</th></tr></thead>
  <tbody>
    <tr><td>A budget exists on every vended target</td><td>a budget on each</td><td><strong><code>25.0</code> on both</strong> the existing and the vended subscription</td><td>PASS</td></tr>
    <tr><td>The landing-zone grant exists at subscription scope</td><td>granted <em>at</em> the subscription, not inherited</td><td><strong>1 Reader on each, at the subscription itself</strong></td><td>PASS</td></tr>
    <tr><td>Placement, from the management group's side</td><td>the group lists the subscription</td><td><strong><code>mg-lz-dev</code> lists it</strong></td><td>PASS</td></tr>
    <tr><td>Placement, from the subscription's own side</td><td>its parent is that group</td><td><strong>parent = <code>.../managementGroups/mg-lz-dev</code></strong></td><td>PASS</td></tr>
    <tr><td>Deployed state matches configuration</td><td>no drift</td><td><strong>none</strong></td><td>PASS</td></tr>
  </tbody>
</table>
</div>

<p><strong>Checks 3 and 4 ask the same question from both ends, deliberately.</strong>
A management group listing a child and a subscription naming its parent are
stored separately, and a vending run that half-finishes can satisfy one without
the other.</p>
""",

    "edits": [(OLD_MODULE_CHALLENGE, NEW_MODULE_CHALLENGE)],

    "captions": {
        "week-04-architecture.svg":
            "<strong>Vending is four operations across three APIs.</strong> "
            "Create through the Subscription Alias API, place through "
            "Management Groups, grant through RBAC, cap through Cost "
            "Management. Nothing does all four, which is why the module market "
            "exists.",
        "01-vended-subscription-placed.png":
            "<strong>Checkpoint:</strong> the vended subscription under "
            "<em>Landing Zones &mdash; Dev</em>. Placement is what makes every "
            "policy on that branch apply to it, so this is the step that turns "
            "a new subscription into a governed one.",
        "02-budget-on-vended.png":
            "<strong>The cap, attached at vend time rather than later.</strong> "
            "A $25 monthly budget on a subscription minutes old. A budget added "
            "when someone gets round to it is the one that is missing when it "
            "matters.",
        "03-decommissioned.png":
            "<strong>What cleanup actually looks like here.</strong> The "
            "subscription has moved into <em>Decommissioned</em>, not "
            "disappeared &mdash; a subscription cannot be deleted. Moving it is "
            "what puts it under the enforcing deny-all.",
    },

    "subheads": {
        "Why — The Problem This Solves": "",
        "What You Need to Know — Skills & Tools": "",
        "Architecture — How It Fits Together": "",
        "How We Built It — Step by Step": "",
        "Security — Controls at Every Layer": "Security",
        "Cost": "Cost",
        "Challenges — What Actually Went Wrong": "",
        "Cleanup — The Interesting Half": "Cleanup — the interesting half",
        "Key Takeaways": "Key takeaways",
        "References": "References",
    },
}
