# -*- coding: utf-8 -*-
"""Week 05 to the Master Standard.

This post had NO validation section at all -- the five checks were recorded in
the repo's README and never in the article. The table below is built from
scripts/validate.sh (expected) and that README (actual). Nothing is invented.

The prerequisite that matters most here is a cost one: deploy_firewall
defaults to false, and turning it on starts a $0.405/hour meter. That was
stated in the repo and not in the post.
"""
GH = ("https://github.com/katta698/Azure-Platform-Engineering-Lab"
      "/blob/main/week-05-hub-network/LAB.md")

SPEC = {
    "post": "posts/week-05-hub-network.html",

    "overview_after": """
<table>
  <tbody>
    <tr><td><strong>Difficulty</strong></td><td>Advanced &mdash; 22 resources across two subscriptions, and the firewall has requirements Basic does not advertise</td></tr>
    <tr><td><strong>Time to complete</strong></td><td>About two hours. The firewall alone takes most of an hour to provision, and it bills the whole time</td></tr>
    <tr><td><strong>Deployment</strong></td><td>Terraform (<code>azurerm</code>), two provider aliases, state in HCP Terraform, local execution</td></tr>
    <tr><td><strong>Measured cost</strong></td><td><strong>$0.72</strong> &mdash; the firewall ran 1 h 47 m against a planned hour. Both causes were process, not Azure</td></tr>
    <tr><td><strong>Full lab guide</strong></td><td><a href="%s">LAB.md</a> &mdash; prerequisites, variables, commands, expected outputs, validation and cleanup</td></tr>
  </tbody>
</table>

<p><strong>Read the cost note before you deploy this one.</strong> It is the
only week in the lab with a meter that runs whether or not you are using it:
Azure Firewall Basic is <strong>$0.405/hour</strong> from the moment it
provisions. Both the firewall and the private DNS estate are gated behind
variables that default to <code>false</code>, so a plain apply builds the free
layer and nothing else.</p>
""" % GH,

    "prereqs": """
<ul>
  <li><strong>Two Azure subscriptions</strong> &mdash; one for the hub
  (<code>sub-connectivity</code> here) and one for the spoke
  (<code>sub-lab-dev</code>). That split is the point: hub and spoke can be
  owned by different teams on different lifecycles. One subscription works if
  you point both variables at it, and you lose the thing the week
  demonstrates.</li>
  <li><strong>Contributor on both.</strong> No role assignments are created,
  so User Access Administrator is not needed.</li>
  <li><strong>A billing alert you trust.</strong> This is the one week that
  bills while idle. <code>deploy_firewall</code> defaults to
  <code>false</code>; setting it true starts a <strong>$0.405/hour</strong>
  meter that does not stop because you walked away.</li>
  <li><strong>Terraform &ge; 1.10</strong> with <code>azurerm</code> 5.x, and
  <strong>two provider aliases</strong> &mdash; 5.x requires an explicit
  <code>subscription_id</code> on each.</li>
  <li><strong>Azure CLI 2.60+.</strong> Note that
  <code>az network firewall</code> lives in an <em>extension</em>, which
  matters for scripting &mdash; see Troubleshooting.</li>
  <li><strong>One resource provider:</strong>
  <code>Microsoft.Network</code>.</li>
  <li><strong>Non-overlapping address space.</strong> Hub
  <code>10.0.0.0/16</code> and spoke <code>10.1.0.0/16</code> by default.
  Peering refuses to create if they overlap, and it refuses at apply time
  rather than at plan time.</li>
</ul>

<p>Every variable, both subscription roles and the layered deploy commands are
in the <a href="%s#1-prerequisites">lab guide</a>, which is the reproducible
half of this write-up.</p>
""" % GH,

    "validation": """
<p>A successful <code>terraform apply</code> proves 22 resources exist. It
does not prove that a peering carries traffic, that a route points anywhere
real, or that the firewall's subnets are sized the way Azure silently
requires. <code>validate.sh</code> checks those separately &mdash;
<strong>5 passed / 0 failed</strong> with the firewall deployed.</p>

<div class="table-scroll">
<table>
  <thead><tr><th>Test</th><th>Expected</th><th>Actual</th><th>Status</th></tr></thead>
  <tbody>
    <tr><td>Both peerings report Connected</td><td>both sides <code>Connected</code>, not <code>Initiated</code></td><td><strong>hub &rarr; spoke and spoke &rarr; hub, both Connected</strong></td><td>PASS</td></tr>
    <tr><td>Every private DNS zone links to both VNets</td><td>every zone linked twice</td><td><strong>6 zones, 12 links</strong></td><td>PASS</td></tr>
    <tr><td>Firewall subnets named and sized as Azure requires</td><td>exact names, <code>/26</code> each</td><td><strong><code>AzureFirewallSubnet 10.0.0.0/26</code>, <code>AzureFirewallManagementSubnet 10.0.0.64/26</code></strong></td><td>PASS</td></tr>
    <tr><td>The spoke's default route points at the firewall</td><td>next hop equals the firewall's private IP</td><td><strong>next hop <code>10.0.0.4</code> = firewall <code>10.0.0.4</code></strong></td><td>PASS</td></tr>
    <tr><td>Deployed state matches configuration</td><td>no drift</td><td><strong>none</strong></td><td>PASS</td></tr>
  </tbody>
</table>
</div>

<p><strong>Without the firewall the same script reports 4 passed and skips
check 4.</strong> That is deliberate: with no firewall there should be no
<code>0.0.0.0/0</code> route, so its absence is the correct state rather than
a gap. A check that failed here would be teaching you to ignore it.</p>

<p><strong>A peering is two resources, not one.</strong> Each side is declared
independently and the link only carries traffic when both exist &mdash; one
side alone sits in <code>Initiated</code>, a resource that exists, reports
healthy, and moves no packets. That is why check 1 reads the <em>state</em>
rather than the existence.</p>
""",

    "edits": [
        ("""<h3>The teardown failed, and the script reported success</h3>""",
         """<p><strong>The teardown failed, and the script reported
success.</strong> This is the one worth the whole post.</p>

<ul>
  <li><strong>Problem:</strong> cleanup died with
  <code>FirewallPolicyUpdateFailed &mdash; Failed with 1 faulted referenced
  firewalls</code>. The firewall stayed up and kept billing, and the script
  still <strong>exited 0</strong>, so nothing signalled a problem.</li>
  <li><strong>Root cause:</strong> <em>two</em> independent failures lined up.
  Terraform tried to update the child policy while the firewall still
  referenced it, so the destroy aborted. And the safety check that existed to
  catch exactly that could not run: it used
  <code>az network firewall list</code>, which needs the
  <code>azure-firewall</code> extension and, in a non-interactive shell, dies
  on the dynamic-install prompt with
  <code>EOFError: EOF when reading a line</code>.</li>
  <li><strong>Resolution:</strong> recovery was
  <code>az resource delete --ids &lt;firewall&gt;</code>, which needs no
  extension, then a re-apply. Eight minutes, and part of the $0.72. The script
  now checks the apply's exit code explicitly and verifies with
  <code>az resource list</code>.</li>
  <li><strong>Lesson learned:</strong> either failure alone would have been
  caught by the other. A verification step is itself a dependency, and one
  that cannot run is worse than none &mdash; it reports clean.</li>
</ul>

<h3 style="display:none">The teardown failed, and the script reported success</h3>"""),
    ],

    "captions": {
        "week-05-architecture.svg":
            "<strong>The whole week on one page, split by what it costs.</strong> "
            "The permanent layer &mdash; VNets, peerings, DNS &mdash; bills "
            "about nothing and can stay. The billable layer, firewall and "
            "public IPs, is a separate apply you turn on and off.",
        "06-hcp-workspace.png":
            "<strong>Checkpoint:</strong> <em>Execution mode: Local</em>, with "
            "the hub resources listed. Two subscriptions are driven from this "
            "one workspace through separate provider aliases.",
        "01-peering-connected.png":
            "<strong>Why the check reads state, not existence.</strong> "
            "<em>Fully Synchronized</em> and <em>Connected</em> is what a "
            "working peering looks like. Declare only one side and you get a "
            "resource that exists, reports healthy, and moves no packets.",
        "02-private-dns-estate.png":
            "<strong>Six zones that were costing $3.00/month to hold "
            "nothing.</strong> Each contained only the SOA record Azure "
            "creates itself, with zero private endpoints anywhere. They are "
            "now gated behind a flag that defaults to false.",
        "03-firewall-basic-deployed.png":
            "<strong>What Basic quietly requires:</strong> <em>two</em> "
            "subnets and <em>two</em> public IPs, not one of each. The "
            "management subnet is not optional on Basic, and nothing warns you "
            "before the apply fails.",
        "04-policy-hierarchy.png":
            "<strong>The parent/child policy split.</strong> The child names "
            "its parent, so org-wide rules are inherited rather than copied. "
            "Note the tier: a Basic policy cannot offer TLS inspection or "
            "IDPS, which is the real limit of this SKU.",
        "05-spoke-route-via-firewall.png":
            "<strong>The route that makes the firewall load-bearing.</strong> "
            "<code>0.0.0.0/0</code> with next hop <em>VirtualAppliance</em> at "
            "the firewall's private IP. Without this the firewall exists, "
            "bills, and inspects nothing.",
    },

    "subheads": {
        "Why — The Problem This Solves": "",
        "What You Need to Know — Skills & Tools": "",
        "Architecture — How It Fits Together": "",
        "How We Built It — In Deployment Order": "",
        "Security — Controls at Every Layer": "Security",
        "Cost — And What It Really Came To": "Cost — and what it really came to",
        "Challenges — What Actually Went Wrong": "",
        "Cleanup": "Cleanup",
        "Key Takeaways": "Key takeaways",
        "References": "References",
    },
}
