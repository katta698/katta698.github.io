# -*- coding: utf-8 -*-
"""Rebuild the weeks 1-8 lab diagrams in AWS's reference style."""
import sys
sys.path.insert(0, r"C:\Projects\Engineering\katta698-aws\scripts")
sys.path.insert(0, r"C:\Users\katta\AppData\Local\Temp\wk24probe")
from aws_arch import Diagram, RED, GREEN, MUTED
from build_diagrams import install


def ticket_pipeline(desc, region_label, tail_icons, tail_note=None,
                    sf_sub="4 states", note_y=320, straight_tail=True):
    """The shape weeks 1, 2, 3, 4 and 6 share: a ServiceNow ticket arriving
    through API Gateway and Lambda into Step Functions, then whatever that
    week actually provisions. Drawn once so those five diagrams agree.

    Columns are 150px apart, not 108. At the tighter spacing a sub-label of
    more than about twenty characters overlapped its neighbour, and six of
    those collisions came back from assert_clean() on the first build.
    """
    d = Diagram(1000, 430, desc)
    d.cloud(14, 14, 972, 402)
    d.component(40, 150, 136, 62, "ServiceNow", "catalog request")
    d.arrow(180, 182, 218, 182)
    d.step(199, 152, "1")

    d.group(228, 58, 746, 330, region_label)

    d.icon(252, 158, "api-gateway", "API Gateway", "signed POST", size=48)
    d.arrow(308, 182, 394, 182)
    d.step(351, 152, "2")

    d.icon(402, 158, "lambda", "webhook receiver", "validates", size=48)
    d.arrow(458, 182, 544, 182)
    d.step(501, 152, "3")

    d.icon(552, 158, "step-functions", "Step Functions", sf_sub, size=48)
    if straight_tail:
        d.arrow(608, 182, 694, 182)
    d.step(651, 152, "4")

    for (x, y, slug, label, sub) in tail_icons:
        d.icon(x, y, slug, label, sub, size=48)
    if tail_note:
        for i, line in enumerate(tail_note):
            d.note(252, note_y + i * 18, line, size=11,
                   colour=MUTED if i else None, weight="400" if i else "600")
    return d


def w1():
    d = ticket_pipeline(
        "A ServiceNow catalog request is posted to Amazon API Gateway, "
        "validated by an AWS Lambda function and handed to AWS Step Functions. "
        "The workflow pauses on a task token while GitHub Actions runs "
        "Terraform to create the Amazon EC2 instance, then resumes and writes "
        "the result back to the ticket.",
        "Region: us-east-1",
        [(702, 158, "ec2", "EC2 instance", "Terraform-built")],
        ["The workflow pauses on waitForTaskToken while Terraform runs.",
         "GitHub Actions calls back with the result, and only then does the",
         "ticket close -- so the ticket reflects the build, not the request."])
    d.component(700, 70, 236, 56, "GitHub Actions", "runs terraform apply")
    d.arrow(608, 170, 694, 112)
    d.arrow(760, 128, 734, 150, dashed=True, colour=GREEN)
    d.note(788, 150, "calls back with the token", size=10.5, colour=GREEN)
    d.assert_clean()
    return ("week-1-from-ticket", d.render(),
            "The ticket is the trigger and the record: the workflow waits for "
            "Terraform and writes the real outcome back.")


def w2():
    d = ticket_pipeline(
        "A ServiceNow request reaches Amazon API Gateway and an AWS Lambda "
        "function, which starts an AWS Step Functions workflow. The workflow "
        "provisions a database on Amazon Aurora Serverless v2 and stores the "
        "per-tenant credentials in AWS Secrets Manager.",
        "Region: us-east-1",
        [(702, 88, "aurora", "Aurora Serverless", "v2, 0.5 to 16 ACUs"),
         (702, 240, "secrets-manager", "Secrets Manager", "per tenant")],
        ["Ticket closed in about 12 seconds.",
         "The password is never in the ticket, the logs or the state file --",
         "the workflow writes it straight into Secrets Manager."],
        straight_tail=False)
    d.arrow(608, 170, 694, 124)
    d.arrow(608, 194, 694, 264)
    d.assert_clean()
    return ("week-2-automating-postgresql", d.render(),
            "One request creates the database and its secret; the credential "
            "never passes through the ticket.")


def w3():
    d = ticket_pipeline(
        "A ServiceNow request reaches Amazon API Gateway and an AWS Lambda "
        "function, which starts an AWS Step Functions workflow. The workflow "
        "runs an AWS Systems Manager automation that onboards or patches the "
        "Amazon EC2 fleet, with no SSH access anywhere.",
        "Region: us-east-1",
        [(702, 158, "systems-manager", "SSM Automation", "onboard or patch"),
         (852, 158, "ec2", "EC2 fleet", "no SSH")],
        ["No SSH anywhere: the SSM agent is the only way in,",
         "so access is an IAM decision rather than a key on someone's laptop.",
         "The ticket closes with the compliance report attached."])
    d.arrow(758, 182, 844, 182)
    d.step(801, 152, "5")
    d.assert_clean()
    return ("week-3-self-service-ec2-fleet", d.render(),
            "Patching driven from a ticket, reaching the fleet through the SSM "
            "agent rather than a shell.")


def w4():
    d = ticket_pipeline(
        "A ServiceNow request reaches Amazon API Gateway and an AWS Lambda "
        "function, which starts an AWS Step Functions workflow. The workflow "
        "runs an AWS Glue crawler and ETL job over raw data in Amazon S3, and "
        "the results are queried with Amazon Athena.",
        "Region: us-east-1",
        [(702, 100, "glue", "Glue crawler + ETL", "raw to Parquet"),
         (702, 240, "s3", "Amazon S3", "raw and curated"),
         (862, 170, "athena", "Amazon Athena", "queries it")],
        ["The workflow polls each Glue stage rather than assuming it finished,",
         "and PATCHes the ticket to Closed Complete only when the ETL really ends."],
        note_y=352, straight_tail=False)
    d.arrow(608, 170, 694, 136)
    d.arrow(608, 194, 694, 264)
    d.arrow(758, 140, 854, 182)
    d.arrow(758, 264, 854, 206)
    d.step(806, 146, "5")
    d.assert_clean()
    return ("week-4-building-a-fleet-intelligence", d.render(),
            "Each Glue stage is polled to completion before the ticket is "
            "allowed to close.")


def w6():
    d = ticket_pipeline(
        "A ServiceNow account request reaches Amazon API Gateway and an AWS "
        "Lambda function, which starts an AWS Step Functions workflow. The "
        "workflow creates the account through AWS Organizations, moves it into "
        "the target organizational unit, and closes the ticket.",
        "Management account",
        [(702, 158, "organizations", "Organizations", "CreateAccount"),
         (862, 92, "iam", "SCPs on the OU", "guardrails")],
        ["CreateAccount is asynchronous, so the workflow polls its status",
         "before moving the account -- a create that returned is not an",
         "account that exists yet."])
    d.arrow(758, 170, 854, 124)
    d.step(806, 130, "5")
    d.component(790, 232, 164, 56, "Workloads OU", "Sandbox / Prod")
    d.arrow(758, 194, 784, 246)
    d.assert_clean()
    return ("week-6-account-vending-machine", d.render(),
            "An account is created, polled until it exists, then moved into "
            "the OU whose guardrails apply from that moment.")


def w5():
    d = Diagram(920, 400,
        "AWS Cost Explorer builds a machine-learning baseline of spend per "
        "service, per day and per region. A Cost Anomaly Monitor compares "
        "actual spend against it and publishes to an Amazon SNS topic. An AWS "
        "Lambda function enriches the raw notification and republishes it to a "
        "second topic that emails a human.")
    d.cloud(14, 14, 892, 372)
    d.group(44, 58, 380, 300, "Detection")

    d.icon(100, 128, "cost-explorer", "Cost Explorer", "ML spend baseline", size=48)
    d.arrow(124, 212, 124, 248)
    d.step(124, 230, "1")
    d.icon(100, 256, "cost-explorer", "Cost Anomaly Monitor", "DIMENSIONAL / SERVICE",
           size=48)
    d.note(80, 352, "threshold: $10 above expected", size=10.5, colour=MUTED)

    d.group(452, 58, 454, 300, "Alerting")
    d.icon(486, 128, "sns", "SNS: raw-anomaly", "AWS publishes here", size=48)
    d.arrow(160, 280, 478, 160)
    d.step(320, 206, "2")

    d.icon(486, 256, "lambda", "enricher", "adds service and delta", size=48)
    d.arrow(510, 212, 510, 248)
    d.step(510, 230, "3")

    d.icon(700, 256, "sns", "SNS: alerts", "email to a human", size=48)
    d.arrow(542, 280, 692, 280)
    d.step(617, 250, "4")

    d.note(640, 140, "The raw notification is JSON", size=11, weight="600")
    d.note(640, 158, "with no service name in it,", size=11, colour=MUTED)
    d.note(640, 176, "which is why the enricher", size=11, colour=MUTED)
    d.note(640, 194, "exists at all.", size=11, colour=MUTED)

    d.assert_clean()
    return ("week-5-cost-anomaly-detection", d.render(),
            "AWS raises the anomaly; the Lambda turns it into something a human "
            "can act on without opening the console.")


def w7():
    d = Diagram(920, 462,
        "Terraform declares groups, users and permission sets once. AWS IAM "
        "Identity Center provisions the matching assignments into every target "
        "account, creating the AWSReservedSSO role in each one. A user signs "
        "in at the AWS access portal and receives a federated console session "
        "with temporary credentials.")
    d.cloud(14, 14, 892, 434)
    d.component(40, 150, 160, 70, "Terraform", "groups{} + users{} in tfvars")
    d.arrow(204, 184, 246, 184)
    d.step(225, 154, "1")

    d.group(256, 58, 400, 330, "Management account")
    d.icon(320, 136, "iam-identity-center", "IAM Identity Center",
           "permission sets, groups", size=48)
    d.note(392, 150, "one assignment per", size=11, colour=MUTED)
    d.note(392, 168, "group x target account", size=11, colour=MUTED)

    d.icon(320, 282, "iam", "account assignment", "setproduct(groups, accounts)",
           size=48)
    d.arrow(344, 222, 344, 274)
    d.step(344, 250, "2")

    # 230 wide put this group's right edge exactly on the cloud border, and
    # centring the icon at x=728 pushed both its captions out through the
    # group's left edge. The captions are the widest thing in the box, so the
    # icon is placed from them: 153px of sub-label needs 76px of clearance
    # either side.
    d.group(676, 58, 210, 170, "Target account")
    d.icon(752, 112, "iam", "AWSReservedSSO role", "created by Identity Center",
           size=48)
    d.arrow(388, 300, 744, 152)
    d.step(530, 214, "3")

    d.icon(752, 290, "user", "the engineer", "one sign-in, one role", size=44)
    d.arrow(776, 228, 776, 282)
    d.step(776, 258, "4")
    d.note(500, 418, "Temporary credentials. No static key is ever issued.",
           size=11.5, weight="600", anchor="middle")

    d.assert_clean()
    return ("week-7-iam-identity-center", d.render(),
            "Identity is declared once and provisioned everywhere it is "
            "assigned; the role in each account is never written by hand.")


def w8():
    d = Diagram(960, 462,
        "An Amazon S3 bucket uses Intelligent-Tiering and lifecycle rules. "
        "Object-created events go to an Amazon SQS queue, which buffers them "
        "for an AWS Lambda tagger; failures land in a dead-letter queue that "
        "raises a CloudWatch alarm. Separately, Amazon EventBridge runs a "
        "daily Lambda that reports the storage cost delta to an SNS topic.")
    d.cloud(14, 14, 932, 434)
    d.group(44, 58, 420, 346, "Storage")

    d.icon(80, 120, "s3", "Amazon S3", "versioned, encrypted, private", size=48)
    d.note(68, 216, "Intelligent-Tiering: Frequent to IA at 30d,", size=10.5,
           colour=MUTED)
    d.note(68, 233, "Archive IR at 90d, Deep at 180d", size=10.5, colour=MUTED)
    d.note(68, 252, "Lifecycle: abort incomplete uploads at 7d,", size=10.5,
           colour=MUTED)
    d.note(68, 269, "expire noncurrent versions at 30d", size=10.5, colour=MUTED)
    d.note(68, 310, "The tiering is automatic. The lifecycle rules", size=11,
           weight="600")
    d.note(68, 328, "are the part that actually deletes anything.", size=11,
           colour=MUTED)

    d.icon(504, 96, "sqs", "SQS queue", "buffers the events", size=48)
    d.arrow(140, 140, 496, 120)
    d.step(320, 110, "1")

    d.icon(650, 96, "lambda", "object tagger", "content-type, upload-date", size=48)
    d.arrow(560, 120, 642, 120)
    d.step(601, 90, "2")

    d.icon(800, 96, "sqs", "dead-letter queue", "after 3 failures", size=48)
    d.arrow(706, 120, 792, 120)
    d.icon(800, 220, "cloudwatch", "alarm", "DLQ depth above 0", size=48)
    d.arrow(824, 176, 824, 212)
    d.step(824, 194, "3")

    d.icon(504, 290, "eventbridge", "EventBridge", "rate(1 day)", size=48)
    d.icon(650, 290, "lambda", "cost reporter", "reads the cost delta", size=48)
    d.arrow(560, 314, 642, 314)
    d.step(601, 284, "4")
    d.icon(800, 350, "sns", "SNS", "daily email", size=40)
    d.arrow(706, 320, 792, 356)

    d.assert_clean()
    return ("week-08-s3-intelligent-storage", d.render(),
            "Two paths off one bucket: an event path that tags objects and a "
            "scheduled path that reports what the storage costs.")


BUILDERS = [w1, w2, w3, w4, w5, w6, w7, w8]

if __name__ == "__main__":
    for b in BUILDERS:
        prefix, svg, cap = b()
        print("  rebuilt %-42s %6d chars" % (install(prefix, svg, cap), len(svg)))
