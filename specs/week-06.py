# -*- coding: utf-8 -*-
"""Week 6 to the Master Standard.

The validation table records two failures, because two things failed: the
account never got created (the organization was at its account quota) and the
workflow's own failure path errored before it could report that. Both are in
the post's figures. A validation table that showed only the passes would be
the more flattering and less true one.
"""

SPEC = {
    "post": "posts/week-6-account-vending-machine-with-aws-organizations-and-scps.html",

    "services": """
<table>
  <thead><tr><th>Service</th><th>Purpose here</th><th>What it is</th></tr></thead>
  <tbody>
    <tr><td>AWS Organizations</td><td>Owns the OU tree and creates the accounts</td><td>Groups AWS accounts under one management account, so policy and billing apply across all of them rather than account by account.</td></tr>
    <tr><td>Service control policy</td><td>The guardrail attached to the Sandbox OU</td><td>An organization policy that sets the ceiling on what any principal in an account may do. It grants nothing on its own; it only takes permissions away.</td></tr>
    <tr><td>AWS Step Functions</td><td>Orchestrates vending, including the failure path</td><td>Runs a workflow as an explicit state machine, so each step, its retry behaviour and its failure path are declared rather than buried in code.</td></tr>
    <tr><td>AWS Lambda</td><td>Receives the webhook and calls CreateAccount</td><td>Runs a piece of code on demand with no server to manage. You are billed per request and per millisecond it runs.</td></tr>
    <tr><td>Amazon API Gateway</td><td>The HMAC-signed webhook endpoint</td><td>A managed front door that accepts HTTP requests and forwards them to a backend.</td></tr>
    <tr><td>Amazon CloudWatch</td><td>Where the real error was found</td><td>AWS's metrics and logs service. Most services publish into it automatically, without being asked to.</td></tr>
    <tr><td>HCP Terraform</td><td>Provisioning, with no static keys</td><td>HashiCorp's hosted Terraform. It runs plans and applies on its own machines and keeps the state file, and it assumes an AWS role by OIDC so no static keys exist anywhere.</td></tr>
  </tbody>
</table>
""",

    "prereqs": """
<table>
  <thead><tr><th>Requirement</th><th>Why</th><th>How to check</th></tr></thead>
  <tbody>
    <tr><td>An AWS Organization with all features enabled</td><td>Service control policies do not exist in consolidated-billing mode</td><td><code>aws organizations describe-organization</code> reports <code>FeatureSet: ALL</code></td></tr>
    <tr><td>The SCP policy type enabled on the root</td><td>A one-time manual switch. Terraform can create a policy while the type is disabled, and attaching it then fails</td><td><code>aws organizations list-roots</code> shows <code>SERVICE_CONTROL_POLICY</code> as <code>ENABLED</code></td></tr>
    <tr><td>Headroom in the organization's account quota</td><td>This is what stopped the lab. <code>CreateAccount</code> returns <code>ConstraintViolationException</code> when the organization is at its limit, and the quota is raised by a support request, not by Terraform</td><td>Organizations console &rarr; Settings, or raise the quota before running</td></tr>
    <tr><td>An HCP Terraform workspace with OIDC into the AWS role</td><td>Keeps credentials out of the repo and out of CI</td><td>The workspace is VCS-connected, so apply and destroy are both driven from the HCP UI</td></tr>
    <tr><td>A shared secret for the webhook</td><td>The endpoint accepts only HMAC-signed requests; <code>scripts/test_webhook.sh</code> signs with the same secret</td><td>Stored as a sensitive workspace variable, never in the repo</td></tr>
  </tbody>
</table>
""",

    "validation": """
<p>Each row traces to a figure in this post. The lab was destroyed in June 2026,
so these are the results recorded then, not a fresh run.</p>

<table>
  <thead><tr><th>Test</th><th>Expected</th><th>Actual</th><th>Status</th></tr></thead>
  <tbody>
    <tr><td>The OU tree is created</td><td>Sandbox and Production nested under the existing Workloads OU</td><td>Sandbox present at Root &rarr; Workloads-OU &rarr; Sandbox, inside the existing structure rather than beside it</td><td>Pass</td></tr>
    <tr><td>The guardrail is attached</td><td><code>sandbox-guardrail-scp</code> attached to the Sandbox OU</td><td>Shown as "Attached directly" on the OU's Policies tab, alongside the inherited <code>FullAWSAccess</code></td><td>Pass</td></tr>
    <tr><td>The webhook authenticates and starts the workflow</td><td>An HMAC-signed POST returns 200 and a Step Functions execution ARN</td><td>200 OK with the execution ARN returned</td><td>Pass</td></tr>
    <tr><td>An account is vended</td><td>A new account appears in the Sandbox OU</td><td>No account was created. <code>CreateAccount</code> returned <code>ConstraintViolationException</code> &mdash; the organization was at its account quota</td><td>Fail &mdash; quota, not code</td></tr>
    <tr><td>The failure path reports the failure</td><td><code>CreateAccount</code>'s Catch routes to <code>VendingFailed</code>, which closes the ticket with the reason</td><td><code>VendingFailed</code> itself errored with <code>States.Runtime</code>, so the real error never reached the ticket and was only visible in CloudWatch Logs</td><td>Fail &mdash; see Troubleshooting</td></tr>
    <tr><td>Teardown removes everything</td><td>A clean destroy</td><td>39 resources destroyed, 0 added, 0 changed</td><td>Pass</td></tr>
  </tbody>
</table>

<p>The quota failure is the useful result. The pipeline did everything it could
be asked to do; the organization simply could not hold another account, and that
is a support request rather than a code change.</p>
""",
}
