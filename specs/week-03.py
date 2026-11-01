# -*- coding: utf-8 -*-
"""Week 3 to the Master Standard.

Fifteen images against the standard's four to seven. The eight dropped are the
ones a sentence covers as well as a picture does: the Terraform outputs, the
two instances showing Online, three individual Step Functions runs (the
executions list shows all three), the Patch Manager view between two states,
the CloudWatch dashboard, and the ticket in its Open state.

The seven kept are a before-and-after pair: not compliant, no tags, tags
applied, three instances, all compliant, the audit trail, and the ticket
closing itself with the numbers in it.
"""

SPEC = {
    "post": "posts/week-3-self-service-ec2-fleet-patching-with-aws-ssm.html",

    "services": """
<table>
  <thead><tr><th>Service</th><th>Purpose here</th><th>What it is</th></tr></thead>
  <tbody>
    <tr><td>AWS Systems Manager</td><td>Does the patching, and reports who is compliant</td><td>A set of tools for managing instances through an agent already on them: running commands, applying patches and reporting what state each one is in.</td></tr>
    <tr><td>Patch Manager and patch baselines</td><td>Decides what "patched" means, per group</td><td>A baseline is the rule for which patches are approved; a patch group is the tag that says which baseline an instance follows.</td></tr>
    <tr><td>Maintenance window</td><td>Decides when patching may happen</td><td>A recurring schedule Systems Manager runs tasks inside, so patching lands in a window someone has agreed to rather than whenever a ticket arrives.</td></tr>
    <tr><td>AWS Step Functions</td><td>Routes the three request types and keeps the audit trail</td><td>Runs a workflow as an explicit state machine, so each step, its retry behaviour and its failure path are declared rather than buried in code.</td></tr>
    <tr><td>AWS Lambda</td><td>Receives the webhook, onboards, reports back</td><td>Runs a piece of code on demand with no server to manage. You are billed per request and per millisecond it runs.</td></tr>
    <tr><td>Amazon API Gateway</td><td>The signed endpoint ServiceNow calls</td><td>A managed front door that accepts HTTP requests and forwards them to a backend.</td></tr>
    <tr><td>VPC interface endpoints</td><td>Lets private instances reach Systems Manager with no NAT gateway</td><td>Private doors from your network to an AWS service. Traffic reaches the service without crossing the internet, and no per-GB NAT charge applies.</td></tr>
  </tbody>
</table>

<p>One idea runs through the build: in Systems Manager a tag is not
documentation, it is configuration. <code class="inline">PatchGroup</code> is
what binds an instance to a baseline, so an untagged instance is not
mis-patched &mdash; it is unmanaged, and reports nothing at all.</p>
""",

    "prereqs": """
<table>
  <thead><tr><th>Requirement</th><th>Why</th><th>How to check</th></tr></thead>
  <tbody>
    <tr><td>The SSM agent running, with an instance profile that allows it</td><td>Systems Manager reaches an instance through its agent and the agent's role. Without the role the instance is simply invisible, with no error anywhere</td><td>It appears in Fleet Manager as <code>Online</code></td></tr>
    <tr><td>A network path to the Systems Manager endpoints</td><td>The agent has to reach the service. This build uses VPC interface endpoints rather than a NAT gateway, which removes the per-GB charge entirely</td><td>The instance registers without a public route</td></tr>
    <tr><td>A <code>PatchGroup</code> tag on anything you expect to be patched</td><td>The tag is what associates an instance with a baseline. An untagged instance reports no compliance state rather than a bad one</td><td>Patch Manager lists the instance against a baseline</td></tr>
    <tr><td>A shared secret for the webhook</td><td>The endpoint accepts only signed requests</td><td>Held as a sensitive variable, never in the repo</td></tr>
  </tbody>
</table>
""",

    "validation": """
<p>Each row traces to a figure here. The lab was destroyed in June 2026; these
are the results recorded then.</p>

<table>
  <thead><tr><th>Test</th><th>Expected</th><th>Actual</th><th>Status</th></tr></thead>
  <tbody>
    <tr><td>Starting state is honest</td><td>Instances that have never been scanned report as such</td><td>Patch Manager showed <code>Never reported</code> before any scan ran</td><td>Pass</td></tr>
    <tr><td>An unmanaged instance is invisible, not wrong</td><td>An instance with only a <code>Name</code> tag has no baseline</td><td>No <code>PatchGroup</code>, no <code>ManagedBy</code>, and no baseline assigned in Patch Manager</td><td>Pass</td></tr>
    <tr><td>Onboarding tags it</td><td>The workflow applies the tags that make it managed</td><td><code>PatchGroup</code>, <code>ManagedBy</code> and <code>OnboardedAt</code> all present afterwards</td><td>Pass</td></tr>
    <tr><td>The fleet grows by one</td><td>Patch Manager counts the new instance with the others</td><td>Three instances listed, the manual one alongside the fleet</td><td>Pass</td></tr>
    <tr><td>Patching reaches compliance</td><td>Every instance compliant, nothing missing</td><td>All three <code>Compliant</code>, <code>MissingCount</code> zero</td><td>Pass</td></tr>
    <tr><td>Every request is auditable</td><td>One execution per request, each with a timestamp</td><td>All three executions <code>SUCCEEDED</code> in the executions list</td><td>Pass</td></tr>
    <tr><td>The requester gets the answer</td><td>The ticket closes carrying the compliance result</td><td>Closed with the report in its work notes: 6 compliant, 472 patches installed</td><td>Pass</td></tr>
  </tbody>
</table>
""",
}
