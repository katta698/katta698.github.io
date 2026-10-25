# -*- coding: utf-8 -*-
"""Week 07 to the Master Standard.

Expected values read from week-07-workload-identity/scripts/validate.sh. The
assertion is the expected value; the measured column is what the post already
recorded.

Permissions read from the Terraform: this week declares an
azurerm_role_assignment (Reader on the resource group), so it needs User
Access Administrator -- same as weeks 08 and 10, unlike week 09.
"""
GH = ("https://github.com/katta698/Azure-Platform-Engineering-Lab"
      "/blob/main/week-07-workload-identity/LAB.md")

SPEC = {
    "post": "posts/week-07-workload-identity.html",

    "overview_after": """
<table>
  <tbody>
    <tr><td><strong>Difficulty</strong></td><td>Intermediate &mdash; four resources, but the trust relationship spans GitHub and Entra and has to match exactly</td></tr>
    <tr><td><strong>Time to complete</strong></td><td>Under an hour, most of it spent on the subject claim. The proving workflow itself runs in <strong>19 seconds</strong></td></tr>
    <tr><td><strong>Deployment</strong></td><td>Terraform (<code>azurerm</code>), state in HCP Terraform, local execution</td></tr>
    <tr><td><strong>Measured cost</strong></td><td><strong>$0.00</strong> &mdash; managed identities and federated credentials are free</td></tr>
    <tr><td><strong>Full lab guide</strong></td><td><a href="%s">LAB.md</a> &mdash; prerequisites, variables, commands, expected outputs, validation and cleanup</td></tr>
  </tbody>
</table>
""" % GH,

    "prereqs": """
<ul>
  <li><strong>Permissions:</strong> Contributor <em>and</em> <strong>User
  Access Administrator</strong> on the subscription. The lab grants
  <code>Reader</code> to the identity it creates, and Contributor cannot
  create role assignments.</li>
  <li><strong>A GitHub repository you can run Actions in</strong>, and
  permission to add a workflow to it. The federated credential is pinned to
  one <em>org, repo and branch</em>, so you need to know all three before
  deploying.</li>
  <li><strong>The GitHub CLI (<code>gh</code>), authenticated.</strong> Not
  optional: the subject claim must be <em>read from GitHub</em>, not
  constructed by hand. See Troubleshooting for what happens otherwise.</li>
  <li><strong>Terraform &ge; 1.10</strong> with <code>azurerm</code> 5.x.
  The workspace must be set to <strong>local execution</strong> &mdash; a new
  HCP workspace defaults to remote, and there is no Azure CLI on HCP's
  runners.</li>
  <li><strong>One resource provider:</strong>
  <code>Microsoft.ManagedIdentity</code>, registered by the deploy script.</li>
  <li><strong>No prior week is required.</strong> This one is depended on
  rather than depending: it is the identity later weeks would build in CI
  under.</li>
</ul>

<p>Every variable &mdash; including the three GitHub ones with no defaults
&mdash; is in the <a href="%s#1-prerequisites">lab guide</a>, which is the
reproducible half of this write-up.</p>
""" % GH,

    "validation": """
<p>A successful <code>terraform apply</code> proves four resources exist. It
proves nothing about whether GitHub can actually authenticate with them, which
is the entire claim of the week. The checks below are split accordingly: the
first five run against Azure, and the last two run on a real GitHub
runner.</p>

<div class="table-scroll">
<table>
  <thead><tr><th>Test</th><th>Expected</th><th>Actual</th><th>Status</th></tr></thead>
  <tbody>
    <tr><td>The managed identity exists</td><td>present, client ID resolves</td><td><strong>present</strong>, client ID resolved</td><td>PASS</td></tr>
    <tr><td>Federated credential count and shape</td><td>exactly <strong>1</strong>, issuer <code>token.actions.githubusercontent.com</code>, audience <code>api://AzureADTokenExchange</code></td><td><strong>one credential</strong>, both correct</td><td>PASS</td></tr>
    <tr><td>Subject names this repo and branch</td><td>matches the subject GitHub actually presents</td><td><strong>matched</strong></td><td>PASS</td></tr>
    <tr><td>There is no secret to steal</td><td><strong>0</strong> password credentials on the service principal</td><td><strong>0</strong></td><td>PASS</td></tr>
    <tr><td>Role scope</td><td><code>Reader</code> and nothing else</td><td><strong>Reader alone</strong></td><td>PASS</td></tr>
    <tr><td>GitHub Actions can log in with no secret</td><td>workflow succeeds, no secrets configured</td><td><strong>Success</strong> in <strong>19 s</strong>, <code>secrets: none configured</code></td><td>PASS</td></tr>
    <tr><td>The identity cannot write</td><td>a resource group create is <em>refused</em></td><td><strong>refused, as designed</strong> &mdash; the workflow fails the build if it succeeds</td><td>PASS</td></tr>
  </tbody>
</table>
</div>

<p><strong>The fourth row is the one that cannot be achieved by discipline.</strong>
A managed identity <em>cannot</em> hold a password &mdash; the API has nowhere
to put one. In an app registration, "no secret" is a rule somebody has to keep
keeping.</p>
""",

    "edits": [
        ("""<p><code>validate.sh</code> runs five checks. The one that matters is the
fourth:</p>""",
         """<p>What two of those checks print:</p>"""),

        # Challenges -> the required four-part shape.
        ("""<p><strong>The first run failed at login, not at apply.</strong></p>""",
         """<p><strong>The first run failed at login, not at apply.</strong></p>

<ul>
  <li><strong>Problem:</strong> Terraform applied cleanly and the workflow
  then failed authenticating, with <code>AADSTS700213: No matching federated
  identity record found</code>.</li>
  <li><strong>Root cause:</strong> GitHub now defaults to <strong>immutable
  subject claims</strong> &mdash; the owner and repository each carry their
  numeric ID. A credential built from the documented
  <code>repo:owner/repo</code> form applies cleanly and matches nothing a
  runner actually presents.</li>
  <li><strong>Resolution:</strong> read the subject from GitHub instead of
  constructing it.</li>
  <li><strong>Lesson learned:</strong> a trust relationship has two ends, and
  only one of them is in your Terraform. The half you did not write is the
  half to go and read.</li>
</ul>"""),
    ],

    "captions": {
        "week-07-architecture.svg":
            "<strong>The whole week on one page.</strong> Follow the token: "
            "GitHub mints it, Entra checks issuer, audience and an exact "
            "subject against the federated credential, and returns an Azure "
            "token. Nothing stored, nothing to rotate, nothing to leak.",
        "06-hcp-workspace.png":
            "<strong>Checkpoint:</strong> <em>Execution mode: Local</em>. A new "
            "HCP workspace defaults to <em>remote</em>, and a remote plan here "
            "fails with <code>az: executable file not found</code> &mdash; "
            "which reads exactly like a broken laptop and is not.",
        "02-managed-identity.png":
            "<strong>The identity CI authenticates as.</strong> "
            "User-assigned, so it outlives any one deployment. Client and "
            "object IDs are redacted here, but the client ID is not a secret "
            "&mdash; the workflow passes it as a plain variable.",
        "01-federated-credential.png":
            "<strong>What the trust is actually pinned to:</strong> one "
            "credential, GitHub as issuer, and a subject beginning "
            "<code>repo:katta698@63027619</code>. That numeric suffix is the "
            "immutable owner ID, and it is why a hand-built subject does not "
            "match.",
        "04-actions-history.png":
            "<strong>The fix, as history.</strong> The first run failed on the "
            "subject claim; the next one, titled for reading the subject from "
            "GitHub rather than building it, succeeded. Two runs is the whole "
            "distance between assuming and asking.",
    },

    "subheads": {
        "Why — The Problem This Solves": "",
        "What You Need to Know — Skills & Tools": "",
        "Architecture — How It Fits Together": "",
        "How We Built It — In Deployment Order": "",
        "How It's Tested": "What the checks print",
        "Security — Controls at Every Layer": "Security",
        "Cost": "Cost",
        "Challenges — What Actually Went Wrong": "",
        "Cleanup": "Cleanup",
        "Key Takeaways": "Key takeaways",
        "References": "References",
    },
}
