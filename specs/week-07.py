# -*- coding: utf-8 -*-
"""Week 7 to the Master Standard.

Seven of the nine sections already existed under older headings and are carried
across byte-for-byte. This supplies the two that never existed -- Prerequisites
and Validation and Evidence -- plus the three-column services table.

Every cell in the validation table traces to a figure caption already in the
post. The lab was destroyed in July 2026 and cannot be re-measured, so nothing
here is a fresh observation; where the post never recorded a number, the table
says so rather than carrying an invented one.
"""

SPEC = {
    "post": "posts/week-7-iam-identity-center-sso-multi-account-permission-sets.html",

    "services": """
<table>
  <thead><tr><th>Service</th><th>Purpose here</th><th>What it is</th></tr></thead>
  <tbody>
    <tr><td>IAM Identity Center</td><td>Defines who exists and what they may do, once, for every account</td><td>AWS's sign-in and assignment layer for people. Users and groups are defined once, and assignments grant them a role in each account.</td></tr>
    <tr><td>Permission set</td><td>The three access levels, written once each</td><td>A reusable role template &mdash; a policy plus a session duration &mdash; that exists on its own until it is assigned to an account.</td></tr>
    <tr><td>Account assignment</td><td>Binds a group to a permission set in one target account</td><td>The link between a group and a permission set, scoped to a single account. Making one is what causes AWS to provision the real role.</td></tr>
    <tr><td>AWSReservedSSO role</td><td>What actually exists inside the target account</td><td>The IAM role Identity Center creates in the target account when an assignment is made. You never declare it, and it is auditable in that account's own IAM.</td></tr>
    <tr><td>AWS access portal</td><td>Where a person signs in</td><td>One sign-in page that lists only the accounts and roles the signed-in user's own group memberships grant.</td></tr>
    <tr><td>AWS Organizations</td><td>Supplies the target accounts</td><td>Groups AWS accounts under one management account, so policy and billing apply across all of them rather than account by account.</td></tr>
    <tr><td>HCP Terraform</td><td>Provisioning, with no static keys</td><td>HashiCorp's hosted Terraform. It runs plans and applies on its own machines and keeps the state file, and it assumes an AWS role by OIDC so no static keys exist anywhere.</td></tr>
  </tbody>
</table>
""",

    "prereqs": """
<table>
  <thead><tr><th>Requirement</th><th>Why</th><th>How to check</th></tr></thead>
  <tbody>
    <tr><td>An AWS Organization with at least one active account in the target OU</td><td>An assignment needs somewhere to land; Week 6's vending machine is what produces these</td><td><code>aws organizations list-accounts-for-parent --parent-id &lt;ou-id&gt;</code></td></tr>
    <tr><td>IAM Identity Center enabled in the management account</td><td>A one-time manual switch. No <code>aws_ssoadmin_*</code> resource can create the instance itself, so Terraform fails before it starts without it</td><td><code>aws sso-admin list-instances</code> returns an instance ARN</td></tr>
    <tr><td>An HCP Terraform workspace with OIDC into the AWS role</td><td>Keeps credentials out of the repo and out of CI</td><td>The role's trust policy already wildcards <code>workspace:*</code>, so a new workspace inherits it with no IAM change</td></tr>
    <tr><td>An email address for the test user</td><td>Identity Center users created by Terraform have no password and no MFA device; the invitation is sent to this address</td><td>Kept in <code>terraform.tfvars</code>, which is gitignored</td></tr>
  </tbody>
</table>
""",

    "validation": """
<p>Each row below traces to a figure in this post. The lab was destroyed in
July 2026, so these are the results recorded at the time rather than a fresh
run.</p>

<table>
  <thead><tr><th>Test</th><th>Expected</th><th>Actual</th><th>Status</th></tr></thead>
  <tbody>
    <tr><td>Terraform creates the identity objects</td><td>Three groups and three permission sets</td><td>All three groups and all three permission sets present in Identity Center, each with its managed policy</td><td>Pass</td></tr>
    <tr><td>Assignments reach the target account</td><td>Each group bound to its permission set on the target account</td><td>All three groups listed against the target account</td><td>Pass</td></tr>
    <tr><td>AWS provisions the role itself</td><td>An <code>AWSReservedSSO</code> role per permission set, created by Identity Center and never declared in Terraform</td><td>Three <code>AWSReservedSSO</code> roles present in the target account's own IAM console</td><td>Pass</td></tr>
    <tr><td>The portal scopes by group membership</td><td>The test user sees only the role her own group grants</td><td>Signed in as <code>jane.engineer</code>, the portal showed the target account with the Engineers role only</td><td>Pass</td></tr>
    <tr><td>No static credential is issued</td><td>A temporary federated session, and no IAM user or access key in the target account</td><td>Federated console session issued by Identity Center; no IAM user or access key was created in any target account</td><td>Pass</td></tr>
    <tr><td>Session durations differ by privilege</td><td>BreakGlassAdmins shorter than Engineers</td><td>Configured at 1 hour against 4 hours. Not recorded at the time whether a session was observed expiring</td><td>Configured, not observed</td></tr>
  </tbody>
</table>
""",
}
