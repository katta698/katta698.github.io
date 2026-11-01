# -*- coding: utf-8 -*-
"""Week 8 to the Master Standard.

Twelve figures against the standard's four-to-seven. The five dropped are the
plan screenshot and the first failed apply (the second apply shows the same
thing and the failure is described in Troubleshooting), the SNS subscription
confirmation, the EventBridge rule, and the Lambda Monitor tab. What is kept
is the evidence a reader cannot reconstruct from the text.
"""

SPEC = {
    "post": "posts/week-08-s3-intelligent-storage.html",

    "services": """
<table>
  <thead><tr><th>Service</th><th>Purpose here</th><th>What it is</th></tr></thead>
  <tbody>
    <tr><td>Amazon S3</td><td>The bucket everything in this lab is about</td><td>Object storage: you put files (objects) into buckets and pay for what you store and for each request, with no disk to size in advance.</td></tr>
    <tr><td>S3 Intelligent-Tiering</td><td>Moves objects between tiers without anyone deciding</td><td>A storage class that watches how often an object is read and moves it to a cheaper tier when it goes cold, for a small per-object monitoring charge.</td></tr>
    <tr><td>S3 Lifecycle rules</td><td>Transitions by age, and the housekeeping</td><td>Rules on a bucket that act on an object's age: change its storage class, expire it, or clean up noncurrent versions and abandoned multipart uploads.</td></tr>
    <tr><td>AWS Lambda</td><td>Tags objects on upload, and reports the bill</td><td>Runs a piece of code on demand with no server to manage. You are billed per request and per millisecond it runs.</td></tr>
    <tr><td>Amazon EventBridge</td><td>Runs the cost report once a day</td><td>An event bus. Services and your own code publish events to it, and rules decide which events reach which targets &mdash; including on a schedule.</td></tr>
    <tr><td>Amazon SNS</td><td>Delivers the daily report by email</td><td>A publish-and-subscribe topic. One message is fanned out to every subscriber &mdash; email, a queue, or a function.</td></tr>
    <tr><td>Amazon SQS</td><td>The dead-letter queue behind the tagger</td><td>A queue that holds messages until something collects them, including the ones a function failed to process.</td></tr>
    <tr><td>Amazon CloudWatch</td><td>Where the storage metrics come from</td><td>AWS's metrics and logs service. Most services publish into it automatically &mdash; S3 storage metrics once a day, not continuously.</td></tr>
  </tbody>
</table>
""",

    "prereqs": """
<table>
  <thead><tr><th>Requirement</th><th>Why</th><th>How to check</th></tr></thead>
  <tbody>
    <tr><td>An HCP Terraform workspace with OIDC into an AWS role</td><td>Keeps credentials out of the repo and out of CI</td><td>The workspace assumes the role on each run; no static keys exist anywhere</td></tr>
    <tr><td>An email address you can read during the apply</td><td>An SNS subscription is <em>pending</em> until the confirmation link is clicked, and an unconfirmed topic delivers nothing while reporting success</td><td><code>aws sns list-subscriptions-by-topic</code> shows an ARN rather than <code>PendingConfirmation</code></td></tr>
    <tr><td>A day of patience before judging the report</td><td>S3 storage metrics in CloudWatch are published roughly daily, so the first report is legitimately empty &mdash; this is not a bug in the reporter</td><td>The first report says so; the second has numbers</td></tr>
    <tr><td>Terraform with the AWS provider</td><td>Everything here is declared; nothing is clicked</td><td><code>terraform version</code></td></tr>
  </tbody>
</table>
""",

    "validation": """
<p>Each row traces to a figure in this post. The lab was destroyed in July 2026,
so these are the results recorded then, not a fresh run.</p>

<table>
  <thead><tr><th>Test</th><th>Expected</th><th>Actual</th><th>Status</th></tr></thead>
  <tbody>
    <tr><td>The platform deploys</td><td>25 resources</td><td>24 on the first apply &mdash; the bucket notification failed on SQS queue-policy propagation &mdash; then all 25 on a re-run with no change to the code</td><td>Pass on retry</td></tr>
    <tr><td>The bucket is hardened</td><td>Versioning on, SSE-S3 encryption, public access fully blocked</td><td>All three confirmed in the console</td><td>Pass</td></tr>
    <tr><td>Intelligent-Tiering is configured</td><td>Archive Instant at 90 days, Deep Archive at 180, bucket-wide</td><td>Applied bucket-wide as declared</td><td>Pass</td></tr>
    <tr><td>Lifecycle rules exist</td><td>Three: <code>logs/</code> transitions, abort incomplete multipart uploads at 7 days, expire noncurrent versions at 30</td><td>All three present</td><td>Pass</td></tr>
    <tr><td>Objects are tagged on upload</td><td><code>content-type</code> and <code>upload-date</code> applied by the tagger</td><td><code>content-type: logs</code>, <code>upload-date: 2026-07-03</code></td><td>Pass</td></tr>
    <tr><td>The tagger has no failures</td><td>An empty dead-letter queue</td><td>DLQ message count zero</td><td>Pass</td></tr>
    <tr><td>The daily report is delivered</td><td>An email, on a schedule, with the bucket's size</td><td>Delivered. <code>StatusCode 200</code>, <code>total_bytes 0</code> &mdash; the report correctly said there was no data yet, because S3 storage metrics lag about 24 hours</td><td>Pass, with nothing to report on day one</td></tr>
  </tbody>
</table>

<p>The empty first report is the result worth keeping. The pipeline was working
end to end; the metric it reads simply did not exist yet, and a reporter that
had invented a number instead would have looked more successful and been
wrong.</p>
""",
}
