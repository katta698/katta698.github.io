# -*- coding: utf-8 -*-
"""Week 06 to the Master Standard.

Expected values read from week-06-deployment-stacks/scripts/validate.sh and
deploy.sh. The caller's roles in check 5 were recorded by the run itself
("Owner User Access Administrator"), which is what makes the refusal mean
anything.

Permissions here are unusual and were read from deploy.sh: Terraform creates
only the CONTROL pair. The protected half is an `az stack mg create` at
MANAGEMENT GROUP scope, which is a different permission boundary entirely and
was stated nowhere in the post.
"""
GH = ("https://github.com/katta698/Azure-Platform-Engineering-Lab"
      "/blob/main/week-06-deployment-stacks/LAB.md")

SPEC = {
    "post": "posts/week-06-deployment-stacks.html",

    "overview_after": """
<table>
  <tbody>
    <tr><td><strong>Difficulty</strong></td><td>Intermediate &mdash; two resources, but the control lives at management group scope and is created outside Terraform</td></tr>
    <tr><td><strong>Time to complete</strong></td><td>Under an hour. The validation genuinely deletes a storage account, so allow for a redeploy if you re-run it</td></tr>
    <tr><td><strong>Deployment</strong></td><td>Terraform (<code>azurerm</code>) for the control pair; <strong><code>az stack mg create</code></strong> for the protected half &mdash; deployment stacks are an ARM object with no Terraform resource</td></tr>
    <tr><td><strong>Measured cost</strong></td><td><strong>$0.00</strong> &mdash; two empty storage accounts, deleted the same day</td></tr>
    <tr><td><strong>Full lab guide</strong></td><td><a href="%s">LAB.md</a> &mdash; prerequisites, variables, commands, expected outputs, validation and cleanup</td></tr>
  </tbody>
</table>
""" % GH,

    "prereqs": """
<ul>
  <li><strong>A management group you can create a deployment stack in.</strong>
  This is the unusual prerequisite and the one most likely to stop you: the
  protected half is an <code>az stack mg create</code> at
  <strong>management group scope</strong>, not a subscription. You need rights
  at the management group, not just inside the subscription under it.</li>
  <li><strong>Owner on the subscription</strong> &mdash; and here that is a
  <em>test requirement</em> rather than a deployment one. Check 5 asserts that
  the deletion was refused for a caller holding <strong>Owner and User Access
  Administrator</strong>. Run it as a limited principal and the result proves
  nothing, because a limited principal would have been refused anyway.</li>
  <li><strong>Azure CLI 2.60+</strong> with the <code>az stack mg</code>
  commands. Note that <code>create</code> accepts <code>--yes</code> and
  <code>validate</code> does not &mdash; see Troubleshooting.</li>
  <li><strong>Terraform &ge; 1.10</strong> with <code>azurerm</code> 5.x,
  which builds <em>only</em> the control pair. There is no Terraform resource
  for a deployment stack.</li>
  <li><strong>Two resource providers:</strong>
  <code>Microsoft.Resources</code> and <code>Microsoft.Storage</code>.</li>
  <li><strong>Builds on week 01</strong> for the management group hierarchy
  the stack is scoped to (<code>mg-lz-dev</code> here). Any management group
  works.</li>
</ul>

<p>Every variable and the exact stack command are in the
<a href="%s#1-prerequisites">lab guide</a>, which is the reproducible half of
this write-up.</p>
""" % GH,

    "validation": """
<p>A successful deploy proves a stack exists with deny settings on. It proves
nothing about whether the deny actually stops anybody &mdash; so check 3
genuinely deletes a storage account. <strong>A test that only ever attempts the
delete it expects to fail proves nothing about whether deletes work at
all.</strong></p>

<div class="table-scroll">
<table>
  <thead><tr><th>Test</th><th>Expected</th><th>Actual</th><th>Status</th></tr></thead>
  <tbody>
    <tr><td>The stack exists and reports managed resources</td><td>a stack at <code>mg-lz-dev</code>, <code>denyWriteAndDelete</code></td><td><strong>2 managed resources</strong>, mode <code>denyWriteAndDelete</code></td><td>PASS</td></tr>
    <tr><td>Managed resources carry a deny status</td><td>every managed resource reports the deny</td><td><strong>2 of 2</strong>, <code>status=managed denyStatus=denyWriteAndDelete</code></td><td>PASS</td></tr>
    <tr><td>Deleting the <em>control</em> account</td><td><strong>succeeds</strong> &mdash; the control for the whole experiment</td><td><strong>deleted</strong></td><td>PASS</td></tr>
    <tr><td>Deleting the <em>protected</em> account</td><td><strong>refused</strong> by the deny assignment</td><td><strong>REFUSED</strong> &mdash; <code>DenyAssignmentAuthorizationFailed</code></td><td>PASS</td></tr>
    <tr><td>Who the refusal applied to</td><td>a caller holding Owner</td><td><strong>Owner + User Access Administrator</strong>, still refused</td><td>PASS</td></tr>
  </tbody>
</table>
</div>

<p><strong>The third row is why the fourth means anything.</strong> Both
accounts are identical and in the same subscription. The only difference is
which one a stack owns.</p>
""",

    "edits": [
        ("""<p><code>scripts/validate.sh</code> runs five checks, and check 3 genuinely
deletes something. That is the point of it — a test that only ever attempts the
delete it expects to fail proves nothing about whether deletes work at all.</p>""",
         """<p>What the five checks print:</p>"""),

        ("""<h3>ARM rejects the JSON comment convention</h3>

<p>ARM templates have no comments, and the common workaround is a top-level
<code>"//"</code> key. It does not work at template root:</p>

<pre><code>InvalidRequestContent: Could not find member '//' on object of type 'Template'</code></pre>

<p>Commentary has to go in <code>metadata</code>, which is a real schema member.
Slightly annoying, entirely fair.</p>

<h3>Sibling CLI commands with different arguments</h3>

<p><code>az stack mg create</code> accepts <code>--yes</code>. <code>az stack mg
validate</code> does not, and fails with <code>unrecognized arguments:
--yes</code>. They read like the same command with a different verb. They are
not.</p>

<h3>A marker file two scripts disagreed about</h3>

<p><code>deploy.sh</code> writes the generated storage account name to
<code>.protected-storage-account</code> so that <code>validate.sh</code> attempts
to delete the right thing. Deploy wrote it at the week root; validate read it
from <code>scripts/</code>. The result was validation reporting <em>"Could not
resolve both storage accounts. Run deploy.sh first."</em> against a deploy that
had succeeded ninety seconds earlier — an error message pointing confidently at
the wrong cause.</p>""",

         """<p><strong>A marker file two scripts disagreed about.</strong></p>

<ul>
  <li><strong>Problem:</strong> validation reported <em>"Could not resolve both
  storage accounts. Run deploy.sh first."</em> against a deploy that had
  succeeded ninety seconds earlier.</li>
  <li><strong>Root cause:</strong> <code>deploy.sh</code> wrote the generated
  account name to <code>.protected-storage-account</code> at the week root;
  <code>validate.sh</code> read it from <code>scripts/</code>.</li>
  <li><strong>Resolution:</strong> resolve the marker path from the script's
  own location in both scripts, rather than from the working directory.</li>
  <li><strong>Lesson learned:</strong> the error pointed confidently at the
  wrong cause. "Run deploy.sh first" is a guess the script makes when a file is
  absent, and a guess in an error message is read as a diagnosis.</li>
</ul>

<p><strong>Sibling CLI commands that do not take the same arguments.</strong></p>

<ul>
  <li><strong>Problem:</strong> <code>az stack mg validate</code> failed with
  <code>unrecognized arguments: --yes</code>.</li>
  <li><strong>Root cause:</strong> <code>az stack mg create</code> accepts
  <code>--yes</code>; <code>validate</code> does not. They read like one
  command with a different verb and are not.</li>
  <li><strong>Resolution:</strong> drop <code>--yes</code> from the validate
  call.</li>
  <li><strong>Lesson learned:</strong> a shared command prefix is not a shared
  argument list. Check each verb's own help.</li>
</ul>

<p><strong>ARM rejects the JSON comment convention.</strong></p>

<ul>
  <li><strong>Problem:</strong>
  <code>InvalidRequestContent: Could not find member '//' on object of type
  'Template'</code>.</li>
  <li><strong>Root cause:</strong> ARM templates have no comments, and the
  common top-level <code>"//"</code> key is not a schema member at template
  root.</li>
  <li><strong>Resolution:</strong> put commentary in <code>metadata</code>,
  which is a real member.</li>
  <li><strong>Lesson learned:</strong> a convention that works in one JSON
  dialect is not portable to a schema-validated one.</li>
</ul>"""),
    ],

    "captions": {
        "week-06-architecture.svg":
            "<strong>The whole week on one page, and it is a controlled "
            "experiment.</strong> Two identical storage accounts, one caller "
            "holding Owner, two delete attempts. The only variable is which "
            "account a deployment stack owns.",
        "02-control-resource-group.png":
            "<strong>The control.</strong> An ordinary Terraform-built storage "
            "account with nothing protecting it. Check 3 deletes this one "
            "successfully &mdash; which is what makes the refusal in check 4 "
            "evidence rather than coincidence.",
        "01-protected-resource-group.png":
            "<strong>The treatment.</strong> Identical account, same "
            "subscription, same caller &mdash; but created and owned by the "
            "deployment stack.",
        "03-deny-assignment.png":
            "<strong>What actually does the refusing:</strong> a deny "
            "assignment Azure created on the stack's behalf, applying to "
            "<em>All principals</em> with <em>no</em> exclusions. Deny "
            "assignments beat role assignments, which is why Owner loses.",
    },

    "subheads": {
        "Why — The Problem This Solves": "",
        "What You Need to Know — Skills & Tools": "",
        "Architecture — How It Fits Together": "",
        "How We Built It — In Deployment Order": "",
        "The Proof — Two Deletes, One Refusal": "What the five checks print",
        "Security — Controls at Every Layer": "Security",
        "Cost": "Cost",
        "Challenges — What Actually Went Wrong": "",
        "Cleanup": "Cleanup",
        "Key Takeaways": "Key takeaways",
        "References": "References",
    },
}
