# -*- coding: utf-8 -*-
"""Week 1 to the Master Standard.

The first post of the series, written before any of it existed. It has six
images, all still served from the Blogger CDN this site was migrated off and
none of them in the lab repo, so they cannot be re-hosted from here. They are
captioned and kept; the dependency is recorded in SESSION_CONTEXT.

Its validation evidence is thinner than later weeks and the table says so
rather than filling the gaps.
"""

SPEC = {
    "post": "posts/week-1-from-ticket-to-ec2-in-6-minutes-enterprise-self-servi.html",

    "overview": """
<p>Someone needs an EC2 instance. What stands between them and having one?</p>

<p><strong>The problem.</strong> Usually a ticket, a queue and an engineer who
runs the same handful of API calls they ran last week. The work takes minutes;
the waiting takes days, and the engineer is the bottleneck by design rather than
by accident.</p>

<p><strong>The objective.</strong> A ServiceNow catalogue item that produces a
real, tagged, governed EC2 instance with no one in the middle, and a ticket that
closes itself with the instance details.</p>

<p><strong>The outcome.</strong> Ticket to running instance in about six
minutes. One thing does not work: the ServiceNow developer instance will not
accept the write-back, which is a limitation of the free tier rather than of the
pipeline, and the post says so.</p>
""",

    "services": """
<table>
  <thead><tr><th>Service</th><th>Purpose here</th><th>What it is</th></tr></thead>
  <tbody>
    <tr><td>Amazon EC2</td><td>The thing being provisioned</td><td>Virtual machines you rent by the second. You choose the size and the operating system, and you are responsible for what runs on them.</td></tr>
    <tr><td>AWS Step Functions</td><td>Runs provisioning as declared steps</td><td>Runs a workflow as an explicit state machine, so each step, its retry behaviour and its failure path are declared rather than buried in code.</td></tr>
    <tr><td>AWS Lambda</td><td>Receives the request and calls the AWS APIs</td><td>Runs a piece of code on demand with no server to manage. You are billed per request and per millisecond it runs.</td></tr>
    <tr><td>Amazon API Gateway</td><td>The endpoint ServiceNow posts to</td><td>A managed front door that accepts HTTP requests and forwards them to a backend.</td></tr>
    <tr><td>AWS Systems Manager</td><td>Reaches the instance without SSH</td><td>Manages instances through an agent already on them, so there is no inbound port to open and no key to distribute.</td></tr>
    <tr><td>Terraform</td><td>Declares all 74 resources</td><td>Infrastructure as code: you describe the resources you want and Terraform works out what to create, change or destroy to get there.</td></tr>
  </tbody>
</table>

<p>The idea the whole series starts from is that self-service is not a UI
problem. The catalogue item is the easy part; what makes it safe is that the
instance arrives already tagged, already governed and already reachable without
a key, because the pipeline had no way to produce one that was not.</p>
""",

    "prereqs": """
<table>
  <thead><tr><th>Requirement</th><th>Why</th><th>How to check</th></tr></thead>
  <tbody>
    <tr><td>A ServiceNow instance</td><td>The catalogue item is the front door. A free developer instance works for everything here except the write-back</td><td>The catalogue item appears in the portal</td></tr>
    <tr><td>A VPC with subnets the instance can launch into</td><td>Provisioning assumes somewhere to put it</td><td><code>aws ec2 describe-subnets</code> returns them</td></tr>
    <tr><td>An instance profile allowing Systems Manager</td><td>Without it the instance launches and is then unreachable, because this build opens no SSH port at all</td><td>The instance appears in Fleet Manager</td></tr>
    <tr><td>Terraform, and credentials that can create 74 resources</td><td>The whole stack is declared; nothing is clicked</td><td><code>terraform plan</code> completes</td></tr>
  </tbody>
</table>
""",

    "validation": """
<p>This is the first post in the series and its evidence is thinner than later
weeks. The rows below are what the post actually recorded; where nothing was
captured, the table says so rather than guessing.</p>

<table>
  <thead><tr><th>Test</th><th>Expected</th><th>Actual</th><th>Status</th></tr></thead>
  <tbody>
    <tr><td>A request can be submitted</td><td>The catalogue item accepts a request and raises a ticket</td><td>Submitted from the ServiceNow portal</td><td>Pass</td></tr>
    <tr><td>The request reaches AWS</td><td>The workflow starts and completes</td><td>Step Functions execution completed</td><td>Pass</td></tr>
    <tr><td>An instance is created</td><td>A running, tagged EC2 instance</td><td>The instance is present and running in the console</td><td>Pass</td></tr>
    <tr><td>End-to-end time</td><td>Minutes rather than days</td><td>About six minutes from submission to a running instance</td><td>Pass</td></tr>
    <tr><td>The ticket is updated</td><td>The requester is told, in the ticket, what they got</td><td>Fails. The ServiceNow developer instance refuses the write-back; the pipeline makes the call and the instance rejects it</td><td>Fail &mdash; free-tier limitation</td></tr>
    <tr><td>Teardown</td><td>Everything removed</td><td>Destroy completed</td><td>Pass</td></tr>
    <tr><td>No SSH path exists</td><td>Access only through Systems Manager</td><td>Not recorded at the time. No inbound SSH rule was created, but no access attempt was made to prove it</td><td>Not tested</td></tr>
  </tbody>
</table>
""",
}
