# -*- coding: utf-8 -*-
"""Week 2 to the Master Standard.

Eight figures, which is inside the budget, so all are kept. The post was
missing Lab Overview, Cloud Services and Concepts, Prerequisites and an
Implementation section with that name; its build content lived under
"How It Works" and "Aurora Architecture Deep Dive".
"""

SPEC = {
    "post": "posts/week-2-automating-postgresql-provisioning-with-servicenow-an.html",

    "overview": """
<p>A developer needs a Postgres database. How long until they have one, and who
has to be awake for it to happen?</p>

<p><strong>The problem.</strong> The usual answer is a ticket, a DBA, and a
wait measured in days &mdash; most of it queueing rather than working. The work
itself is a handful of API calls that never vary.</p>

<p><strong>The objective.</strong> A ServiceNow catalogue item in, a real
database on a shared Aurora cluster out, credentials in Secrets Manager, and the
ticket closed with the connection details. No engineer in the path.</p>

<p><strong>The outcome.</strong> End to end in 12 seconds, and five separate
things had to be fixed first &mdash; including one that is a Git Bash behaviour
rather than an AWS one.</p>
""",

    "services": """
<table>
  <thead><tr><th>Service</th><th>Purpose here</th><th>What it is</th></tr></thead>
  <tbody>
    <tr><td>Amazon Aurora PostgreSQL</td><td>One cluster, a database per tenant</td><td>A managed PostgreSQL-compatible database where storage grows on its own and AWS handles replication and failover.</td></tr>
    <tr><td>AWS Secrets Manager</td><td>Holds each tenant's credentials</td><td>Stores a secret, controls who may read it with IAM, and can rotate it. The application is given a name to look up rather than a password.</td></tr>
    <tr><td>AWS Step Functions</td><td>Provision, then update the ticket, in order</td><td>Runs a workflow as an explicit state machine, so each step, its retry behaviour and its failure path are declared rather than buried in code.</td></tr>
    <tr><td>AWS Lambda</td><td>Runs the SQL and calls ServiceNow back</td><td>Runs a piece of code on demand with no server to manage. You are billed per request and per millisecond it runs.</td></tr>
    <tr><td>Amazon API Gateway</td><td>The endpoint ServiceNow posts to</td><td>A managed front door that accepts HTTP requests and forwards them to a backend.</td></tr>
    <tr><td>Amazon RDS Query Editor</td><td>How the result was checked</td><td>A browser SQL console for RDS and Aurora, which needs no bastion host and no database client installed.</td></tr>
  </tbody>
</table>

<p>The idea the build rests on is that a database is not the unit of isolation
here &mdash; the cluster is shared, and what separates tenants is a database
plus a role plus a secret, created together. That is cheap enough to do per
request, which is what makes self-service affordable at all.</p>
""",

    "prereqs": """
<table>
  <thead><tr><th>Requirement</th><th>Why</th><th>How to check</th></tr></thead>
  <tbody>
    <tr><td>An Aurora cluster already running</td><td>This provisions a database inside a cluster; it does not create one per request, which is what keeps the cost sane</td><td><code>aws rds describe-db-clusters</code> returns the cluster</td></tr>
    <tr><td>The provisioning Lambda inside the VPC, with reachability to the cluster</td><td>It connects as a normal Postgres client, so the security group has to allow it</td><td>A test invocation connects rather than timing out</td></tr>
    <tr><td>A ServiceNow instance and a shared secret</td><td>The endpoint accepts only signed requests from the catalogue item</td><td>Held as a sensitive variable, never in the repo</td></tr>
    <tr><td>An admin credential for the cluster in Secrets Manager</td><td><code>CREATE DATABASE</code> and <code>CREATE ROLE</code> need an account that can do both</td><td>The function reads it by name; nothing is passed in the request</td></tr>
  </tbody>
</table>
""",
}
