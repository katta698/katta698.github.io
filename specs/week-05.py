# -*- coding: utf-8 -*-
"""Week 5 to the Master Standard.

Seven of the nine sections already exist under numbered headings and carry
across. This supplies Prerequisites and Validation and Evidence, and the
three-column services table.
"""

SPEC = {
    "post": "posts/week-5-cost-anomaly-detection-with-aws-cost-explorer-sns-and.html",

    "services": """
<table>
  <thead><tr><th>Service</th><th>Purpose here</th><th>What it is</th></tr></thead>
  <tbody>
    <tr><td>AWS Cost Anomaly Detection</td><td>Decides what counts as unusual, so no threshold has to be guessed</td><td>A free Cost Explorer feature that learns each service's normal spend pattern and raises an anomaly when actual cost departs from it.</td></tr>
    <tr><td>Anomaly monitor</td><td>Watches every service in the account</td><td>The object that defines what is being watched. A DIMENSIONAL monitor covers all services; other types narrow it to linked accounts, tags or cost categories.</td></tr>
    <tr><td>Alert subscription</td><td>Decides when you hear about it</td><td>The threshold and frequency attached to a monitor &mdash; here, immediate delivery for anything above $10 of absolute impact.</td></tr>
    <tr><td>Amazon SNS</td><td>Two topics: one AWS writes to, one a human reads</td><td>A publish-and-subscribe topic. One message is fanned out to every subscriber &mdash; email, a queue, or a function.</td></tr>
    <tr><td>AWS Lambda</td><td>Turns the raw anomaly into a readable email</td><td>Runs a piece of code on demand with no server to manage. You are billed per request and per millisecond it runs.</td></tr>
    <tr><td>HCP Terraform</td><td>Provisioning, with no static keys</td><td>HashiCorp's hosted Terraform. It runs plans and applies on its own machines and keeps the state file, and it assumes an AWS role by OIDC so no static keys exist anywhere.</td></tr>
  </tbody>
</table>

<p>The idea the build rests on is that a budget alert answers "have I spent more
than X", which is a question you have to know the answer to in advance. Anomaly
detection answers "is this unlike me", which does not need a number at all
&mdash; and is the question that catches a service you forgot you were running.</p>
""",

    "prereqs": """
<table>
  <thead><tr><th>Requirement</th><th>Why</th><th>How to check</th></tr></thead>
  <tbody>
    <tr><td>Cost Explorer enabled on the account</td><td>Anomaly detection is part of it, and nothing can be created until it is switched on &mdash; a one-time action in the console</td><td>The Cost Management console shows cost data rather than an enable prompt</td></tr>
    <tr><td>Billing data history</td><td>The detector learns a normal pattern before it can call anything abnormal, so a brand-new account has nothing to compare against</td><td>Expect no anomalies at all on the first days</td></tr>
    <tr><td>An email address to subscribe</td><td>An SNS subscription stays pending until the confirmation link is clicked, and an unconfirmed topic delivers nothing while reporting success</td><td><code>aws sns list-subscriptions-by-topic</code> shows an ARN, not <code>PendingConfirmation</code></td></tr>
    <tr><td>An HCP Terraform workspace with OIDC</td><td>Keeps credentials out of the repo; the workspace is VCS-connected, so destroy is driven from the HCP UI</td><td>The run page shows an applied run against the committed configuration</td></tr>
  </tbody>
</table>
""",

    "validation": """
<p>Each row traces to a figure here. The lab was destroyed in June 2026; these
are the results recorded then.</p>

<table>
  <thead><tr><th>Test</th><th>Expected</th><th>Actual</th><th>Status</th></tr></thead>
  <tbody>
    <tr><td>The stack deploys</td><td>A clean apply from a VCS-connected workspace</td><td>Applied successfully on <code>week-05-dev</code></td><td>Pass</td></tr>
    <tr><td>The monitor exists and covers everything</td><td>A DIMENSIONAL monitor across all services</td><td>Present and monitoring all services</td><td>Pass</td></tr>
    <tr><td>The subscription has the intended threshold</td><td>Immediate delivery above $10 of absolute impact</td><td><code>IMMEDIATE</code> frequency, $10 absolute impact</td><td>Pass</td></tr>
    <tr><td>Both topics exist and are separate</td><td>One topic AWS publishes to, one a person subscribes to</td><td><code>raw-anomaly</code> and <code>cost-alert</code> both created</td><td>Pass</td></tr>
    <tr><td>The formatter runs</td><td>A test invocation publishes to the formatted topic</td><td>Execution succeeded and published</td><td>Pass</td></tr>
    <tr><td>A human gets something readable</td><td>Expected against actual spend, with a root cause</td><td>Email delivered showing expected versus actual with the breakdown</td><td>Pass</td></tr>
    <tr><td>A real anomaly is detected end to end</td><td>AWS raises one by itself and the mail arrives</td><td>Not observed. The alert path was proved with a test invocation; no genuine anomaly occurred during the lab's lifetime</td><td>Not observed</td></tr>
    <tr><td>Teardown</td><td>Everything removed</td><td>12 resources destroyed, nothing left billing</td><td>Pass</td></tr>
  </tbody>
</table>
""",
}
