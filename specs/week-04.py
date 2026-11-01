# -*- coding: utf-8 -*-
"""Week 4 to the Master Standard.

Sixteen figures against the standard's four to seven, and one of them
(12-step-functions.png) appears twice. The seven kept are the ones that show
something a reader cannot infer: the deploy, the raw data arriving, the
catalog, the ETL succeeding, the curated Parquet, the ticket closing itself,
and the query that answers the original question.
"""

SPEC = {
    "post": "posts/week-4-building-a-fleet-intelligence-platform-with-aws-glue-.html",

    "services": """
<table>
  <thead><tr><th>Service</th><th>Purpose here</th><th>What it is</th></tr></thead>
  <tbody>
    <tr><td>SSM Resource Data Sync</td><td>Gets fleet inventory out of Systems Manager and into S3</td><td>A Systems Manager feature that writes inventory and compliance data to an S3 bucket on a schedule, so it can be queried like any other data.</td></tr>
    <tr><td>Amazon S3</td><td>Two buckets: raw as delivered, curated as Parquet</td><td>Object storage: you put files into buckets and pay for what you store and for each request, with no disk to size in advance.</td></tr>
    <tr><td>AWS Glue crawler and Data Catalog</td><td>Works out the shape of the raw data</td><td>A crawler reads files and infers their columns and types; the Data Catalog is where those table definitions live so query engines can read them.</td></tr>
    <tr><td>AWS Glue ETL</td><td>Turns the raw JSON into partitioned Parquet</td><td>Managed Spark. You supply a script and AWS runs it on workers you size, billed per DPU-hour.</td></tr>
    <tr><td>Amazon Athena</td><td>The actual question-answering layer</td><td>Runs SQL straight against files in S3 with no database to run. You are billed for the bytes each query scans, so file layout is a cost decision.</td></tr>
    <tr><td>AWS Step Functions</td><td>Orchestrates crawler, ETL and notification in order</td><td>Runs a workflow as an explicit state machine, so each step, its retry behaviour and its failure path are declared rather than buried in code.</td></tr>
    <tr><td>AWS Lambda</td><td>Receives the webhook and closes the ticket</td><td>Runs a piece of code on demand with no server to manage. You are billed per request and per millisecond it runs.</td></tr>
  </tbody>
</table>

<p>Two ideas carry the build. Partitioning decides what a query costs, because
Athena bills for bytes scanned and a partition it can skip is a partition it
does not read. And a catalog is just a description: the data stays in S3, and
nothing is loaded into a database.</p>
""",

    "prereqs": """
<table>
  <thead><tr><th>Requirement</th><th>Why</th><th>How to check</th></tr></thead>
  <tbody>
    <tr><td>Managed instances reporting to Systems Manager</td><td>With no fleet there is no inventory, and every downstream stage succeeds on an empty bucket</td><td><code>aws ssm describe-instance-information</code> returns instances</td></tr>
    <tr><td>Patience for the first sync</td><td>Resource Data Sync has an initial delay of up to 30 minutes. An empty bucket during that window is expected, not a fault</td><td>Objects appear under the <code>ssm/</code> prefix</td></tr>
    <tr><td>The sync role's permissions</td><td>The role needs <code>ssm:PutComplianceItems</code> on the target instances, or data never arrives and nothing reports an error</td><td>Check the role's policy before waiting out the delay</td></tr>
    <tr><td>The Glue script uploaded before Terraform runs</td><td>Terraform creates the Glue job with a script location; it does not upload the script, and the job fails at run time if nothing is there</td><td>The deploy workflow copies it to S3 before <code>terraform apply</code></td></tr>
  </tbody>
</table>
""",

    "validation": """
<p>Each row traces to a figure in this post. The lab was destroyed in June 2026,
so these are the results recorded then, not a fresh run.</p>

<table>
  <thead><tr><th>Test</th><th>Expected</th><th>Actual</th><th>Status</th></tr></thead>
  <tbody>
    <tr><td>The platform deploys</td><td>Terraform applies cleanly from CI</td><td>10 resources created</td><td>Pass</td></tr>
    <tr><td>Fleet data reaches S3</td><td>SSM inventory under the raw prefix</td><td><code>AWS:ComplianceSummary</code>, <code>AWS:InstanceInformation</code> and other types present</td><td>Pass</td></tr>
    <tr><td>The catalog describes it</td><td>Tables discovered without being declared</td><td>Tables present in the Data Catalog, inferred by the crawler</td><td>Pass</td></tr>
    <tr><td>The ETL runs</td><td>A successful Glue run</td><td><code>SUCCEEDED</code>, on Glue 4.0 with 2 &times; G.1X workers</td><td>Pass</td></tr>
    <tr><td>Output is partitioned Parquet</td><td>Columnar files under a partitioned prefix</td><td>Parquet partitions for patch compliance, inventory and fleet summary</td><td>Pass</td></tr>
    <tr><td>The ticket closes itself</td><td>The requester gets an answer without an engineer</td><td>Closed automatically, with the Athena query URL in the close notes</td><td>Pass</td></tr>
    <tr><td>The question is answerable</td><td>Patch compliance across the fleet, in SQL</td><td>Compliance status returned broken down across the fleet</td><td>Pass</td></tr>
    <tr><td>Query cost</td><td>Low, because partitions let Athena skip data</td><td>Not recorded at the time. The partitioning is in place; the bytes-scanned figure was never captured</td><td>Not measured</td></tr>
  </tbody>
</table>
""",
}
