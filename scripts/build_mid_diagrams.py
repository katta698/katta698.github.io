# -*- coding: utf-8 -*-
"""Redraw weeks 9-20 in the AWS reference style with official icons.

These twelve were the last lab diagrams still hand-authored: dense, text-heavy,
and the only ones carrying no official AWS icon. Each builder returns
(slug_prefix, svg, figcaption); assert_clean() runs on every one.
"""
import io, os, re, sys
sys.path.insert(0, r"C:\Projects\Engineering\katta698-aws\scripts")
from aws_arch import Diagram, RED, GREEN, MUTED, SQUID

POSTS = r"C:\Projects\Engineering\katta698-aws\posts"


# ----------------------------------------------------------------- week 9 ---
def w09():
    d = Diagram(960, 480,
        "A ServiceNow ticket reaches an Amazon API Gateway endpoint as an "
        "HMAC-signed webhook. A receiver AWS Lambda function checks the "
        "signature and starts an AWS Step Functions workflow, which invokes a "
        "provisioner function. That function creates an Amazon ECS Fargate "
        "task in a private subnet behind an Application Load Balancer, with "
        "VPC endpoints for Amazon ECR, Amazon CloudWatch Logs and Amazon S3 "
        "instead of a NAT gateway.")
    d.component(20, 96, 116, 56, "ServiceNow", "ticket submitted")
    d.cloud(150, 14, 796, 430)
    d.group(180, 58, 736, 360, "Region: us-east-1")

    d.arrow(140, 124, 202, 124, step="1")
    d.icon(210, 104, "api-gateway", "API Gateway", "HMAC webhook")
    d.icon(350, 104, "lambda", "receiver", "checks signature")
    d.icon(490, 104, "step-functions", "Step Functions", "orchestrates")
    d.icon(630, 104, "lambda", "provisioner", "creates resources")
    d.arrow(262, 128, 344, 128, step="2")
    d.arrow(402, 128, 484, 128, step="3")
    d.arrow(542, 128, 624, 128, step="4")

    d.group(200, 250, 716, 150, "VPC \u2014 private subnets, no NAT gateway")
    d.component(20, 276, 120, 52, "End user", "requests the URL")
    d.arrow(144, 300, 232, 300)
    d.icon(240, 276, "elb", "Load Balancer", "path routing", size=44)
    d.icon(440, 276, "ecs", "ECS Fargate", "runs the container", size=44)
    d.icon(660, 276, "vpc", "VPC endpoints", "ECR \u00b7 Logs \u00b7 S3", size=44)
    d.arrow(290, 298, 432, 298)
    d.arrow(490, 298, 652, 298)
    d.elbow(678, 128, 760, 244)

    d.note(20, 462, "No NAT gateway: the task reaches ECR, Logs and S3 over "
           "VPC endpoints, so the private subnet needs no route out.",
           size=11.5, colour=MUTED)
    d.assert_clean()
    return ("week-09-ecs-fargate-self-service", d.render(),
            "A ticket becomes a running container. The private subnet never "
            "gets a route to the internet.")


# ---------------------------------------------------------------- week 10 ---
def w10():
    d = Diagram(960, 470,
        "In a member account an Amazon EventBridge schedule invokes a log "
        "generator AWS Lambda function every five minutes, writing structured "
        "JSON to an Amazon CloudWatch log group. Two paths leave that account: "
        "a CloudWatch Observability Access Manager link shares logs and metrics "
        "in place with a monitoring sink in the management account, and a "
        "centralization rule copies the log events into a central log group "
        "there. Amazon Athena queries the copies.")
    d.cloud(14, 14, 932, 400)
    d.group(44, 58, 420, 330, "Member account \u00b7 Dev OU")

    d.icon(76, 110, "eventbridge", "EventBridge", "rate(5 minutes)")
    d.arrow(132, 134, 214, 134, step="1")
    d.icon(222, 110, "lambda", "log generator", "structured JSON")
    d.arrow(278, 134, 360, 134, step="2")
    d.icon(368, 110, "cloudwatch", "App log group", "14-day retention")

    d.component(90, 268, 374, 56, "OAM link \u00b7 opt-in per account",
                "shares logs and metrics in place \u2014 no copy is made")
    # Leave from the icon's right edge, not from under it: a connector dropped
    # straight down from an icon runs through its own label and sub-label.
    d.elbow(428, 134, 448, 262)

    d.group(508, 58, 408, 330, "Management account \u00b7 monitoring sink")
    d.icon(548, 110, "cloudwatch", "Central log group", "30-day retention")
    # Both paths leave the same icon edge, so the split is visible as a fork
    # rather than as a second arrow appearing out of the account boundary.
    d.arrow(428, 134, 540, 134, step="3")
    d.icon(720, 110, "s3", "S3 bucket", "the queryable copy")
    d.arrow(604, 134, 712, 134, step="4")
    d.icon(788, 258, "athena", "Athena", "one query, every account")
    d.elbow(768, 134, 812, 250)

    d.note(548, 272, "Two paths, two reasons:", size=11, weight="600")
    d.note(548, 292, "OAM is for looking now.", size=11, colour=MUTED)
    d.note(548, 310, "The copy is for keeping.", size=11, colour=MUTED)

    d.note(20, 452, "A shared log is readable while the source account exists. "
           "A copied log outlives it \u2014 which is the one an auditor asks for.",
           size=11.5, colour=MUTED)
    d.assert_clean()
    return ("week-10-centralized-logging", d.render(),
            "Sharing in place and copying for keeps answer different "
            "questions, so this build does both.")


# ---------------------------------------------------------------- week 11 ---
def w11():
    d = Diagram(960, 490,
        "Amazon GuardDuty findings and AWS Security Hub control failures are "
        "ingested by Security Hub, where an automation rule raises production "
        "findings to CRITICAL before routing. Amazon EventBridge matches on "
        "finding content and invokes one of three AWS Lambda functions: one "
        "revokes world-open security group ingress, one applies S3 Block "
        "Public Access, and one sends an Amazon SNS notification without "
        "changing anything. Each remediator writes the finding back as "
        "RESOLVED.")
    d.cloud(14, 14, 932, 420)
    d.group(44, 58, 340, 350, "Detection")

    d.icon(80, 104, "guardduty", "GuardDuty", "active threats")
    d.icon(240, 104, "security-hub", "Security Hub", "FSBP controls")
    d.arrow(134, 128, 232, 128, step="1")
    d.note(80, 216, "automation rule:", size=11, weight="600")
    d.note(80, 234, "prod findings become", size=11, colour=MUTED)
    d.note(80, 252, "CRITICAL before routing", size=11, colour=MUTED)

    d.icon(432, 104, "eventbridge", "EventBridge", "content routing")
    d.arrow(300, 128, 424, 128, step="2")

    d.group(560, 58, 356, 350, "Response \u2014 tag-gated")
    d.icon(600, 86, "lambda", "sg remediator", "revoke 0.0.0.0/0", size=44)
    d.icon(600, 196, "lambda", "s3 remediator", "block public access", size=44)
    d.icon(600, 306, "lambda", "notifier", "escalate, never mutate", size=44)
    d.arrow(480, 128, 592, 108)
    d.arrow(480, 128, 592, 218)
    d.arrow(480, 128, 592, 328)

    d.icon(830, 306, "sns", "SNS", "email", size=44)
    d.arrow(678, 328, 822, 328)

    d.note(20, 452, "Only resources tagged auto-remediate=true are changed. "
           "Everything else raises a notification.", size=11.5, colour=MUTED)
    d.note(20, 472, "A remediator that cannot be scoped is a remediator you "
           "will turn off.", size=11, colour=RED)
    d.assert_clean()
    return ("week-11-security-hub-guardduty", d.render(),
            "Routing happens on finding content; whether anything is changed "
            "happens on a tag.")


# ---------------------------------------------------------------- week 12 ---
def w12():
    d = Diagram(960, 520,
        "An AWS Config recorder records all resource types and evaluates a "
        "conformance pack of three rules. A required-tags rule notifies only. "
        "Two Amazon S3 rules, for versioning and server-side encryption, are "
        "scoped to resources tagged auto-remediate=true and are fixed "
        "automatically through AWS Systems Manager Automation. A reporter AWS "
        "Lambda function on a daily Amazon EventBridge schedule discovers the "
        "rules from the pack and sends an Amazon SNS digest.")
    d.cloud(14, 14, 932, 450)
    d.group(44, 58, 380, 380, "Recording and evaluation")

    d.icon(80, 110, "config", "AWS Config", "all resource types")
    d.arrow(136, 134, 232, 134, step="1")
    d.icon(240, 110, "config", "Conformance pack", "three rules")
    d.note(80, 236, "The pack defines its own rules,", size=11, weight="600")
    d.note(80, 254, "so there is no standalone rule", size=11, colour=MUTED)
    d.note(80, 272, "left behind to drift apart from it.", size=11, colour=MUTED)

    d.group(468, 58, 448, 380, "Outcome per rule")
    d.component(500, 86, 384, 56, "required-tags \u2014 notify only",
                "scope: every resource, so a fix would be a guess")
    d.component(500, 166, 384, 56, "s3-bucket-versioning-enabled",
                "scope: auto-remediate=true \u2014 fixed automatically",
                accent=GREEN)
    d.component(500, 246, 384, 56, "s3-bucket-sse-enabled",
                "scope: auto-remediate=true \u2014 fixed automatically",
                accent=GREEN)
    # From the icon's edge, not from its caption: starting the fan-out at
    # x=306 put all three arrowheads on top of the words "Conformance pack".
    d.arrow(288, 134, 492, 114, step="2")
    d.arrow(288, 134, 492, 194)
    d.arrow(288, 134, 492, 274)

    d.icon(500, 340, "systems-manager", "SSM Automation", "applies the fix",
           size=44)
    d.arrow(522, 302, 522, 334)
    d.icon(640, 340, "eventbridge", "EventBridge", "daily schedule", size=44)
    d.icon(760, 340, "lambda", "reporter", "reads the pack", size=44)
    d.icon(860, 340, "sns", "SNS", "plain text", size=44)
    d.arrow(690, 362, 752, 362)
    d.arrow(810, 362, 852, 362)

    d.note(20, 496, "The two rules that get fixed are the two whose correct "
           "state is not in dispute. The one about ownership only notifies.",
           size=11.5, colour=MUTED)
    d.assert_clean()
    return ("week-12-config-compliance-automation", d.render(),
            "Three rules, two of them safe to fix without asking. The third "
            "needs a human.")


# ---------------------------------------------------------------- week 13 ---
def w13():
    d = Diagram(960, 500,
        "A normal user reaches an Amazon CloudFront distribution carrying a "
        "web ACL in CLOUDFRONT scope, which forwards to an Amazon API Gateway "
        "REST API carrying a second web ACL in REGIONAL scope with the same "
        "rules. A caller who knows the origin URL skips CloudFront and meets "
        "the second web ACL instead. AWS Shield Standard protects both at "
        "layers 3 and 4. Blocked and counted requests raise Amazon CloudWatch "
        "alarms that notify through Amazon SNS.")
    d.component(20, 96, 164, 52, "Normal user", "via the CloudFront URL")
    d.component(20, 300, 164, 52, "Origin URL holder", "skips the edge")
    d.cloud(200, 14, 746, 450)
    d.group(230, 58, 686, 380, "Region: us-east-1")

    d.arrow(188, 124, 274, 124, step="1")
    d.icon(280, 110, "cloudfront", "CloudFront", "the edge")
    d.component(230, 210, 170, 56, "Edge web ACL", "CLOUDFRONT scope")
    d.elbow(280, 134, 250, 204)

    d.arrow(334, 134, 492, 134, step="2")
    d.icon(500, 110, "api-gateway", "API Gateway", "REST, not HTTP")
    d.component(440, 210, 170, 56, "Origin web ACL", "REGIONAL scope")
    d.elbow(500, 134, 460, 204)

    d.icon(690, 110, "lambda", "echo", "answers if it got through")
    d.arrow(554, 134, 682, 134, step="3")

    # The bypass meets the second web ACL, which is the whole point: it lands
    # on that box, not on the API behind it.
    d.elbow(188, 326, 524, 272)

    d.component(640, 210, 270, 56, "Shield Standard",
                "L3/L4, always on, nothing to deploy")
    d.icon(590, 310, "cloudwatch", "CloudWatch", "Blocked + Counted", size=44)
    d.icon(750, 310, "sns", "SNS", "email alert", size=44)
    d.arrow(634, 332, 742, 332)
    d.arrow(570, 266, 608, 304)

    d.note(20, 482, "The same five rules sit at both scopes, so knowing the "
           "origin URL buys nothing — which is the only way the edge is "
           "worth deploying.", size=11.5, colour=MUTED)
    d.assert_clean()
    return ("week-13-waf-shield-protection", d.render(),
            "Two web ACLs, the same five rules. The bypass meets the second "
            "one.")


# ---------------------------------------------------------------- week 14 ---
def w14():
    d = Diagram(1040, 520,
        "Inside one Amazon VPC, an exposed Amazon EC2 instance in a public "
        "subnet is scanned from the internet and rejects every unsolicited "
        "packet, while a generator instance in a private subnet reaches out "
        "through a NAT gateway that carries most of the build's cost. VPC "
        "flow logs in record version 11 are delivered to Amazon S3 in Parquet "
        "format, partitioned, and queried with Amazon Athena.")
    d.component(20, 110, 120, 52, "The internet", "200 scanning IPs")
    d.cloud(160, 14, 864, 450)
    d.group(190, 58, 440, 380, "VPC — the observed network")

    d.arrow(144, 132, 222, 132)
    d.icon(230, 110, "ec2", "exposed host", "public subnet", size=44)
    d.note(214, 212, "every packet REJECTed", size=11, colour=RED,
           weight="600")
    d.note(214, 230, "— the denial is the signal", size=11, colour=MUTED)

    d.icon(230, 282, "ec2", "generator", "private subnet", size=44)
    d.component(400, 276, 200, 56, "NAT gateway", "$0.045/hr + per GB")
    d.arrow(276, 304, 392, 304)

    d.group(670, 58, 324, 380, "The record, and the query")
    d.arrow(630, 132, 702, 132, step="1")
    d.icon(710, 110, "vpc", "Flow logs", "v11 · 32 fields", size=44)
    d.icon(890, 110, "s3", "S3", "Parquet", size=44)
    d.arrow(754, 132, 882, 132, step="2")
    d.icon(936, 282, "athena", "Athena", "one query", size=44)
    d.elbow(934, 132, 958, 274)

    d.note(690, 230, "Record version 11 carries the", size=11, weight="600")
    d.note(690, 248, "instance tag and the next-hop", size=11, colour=MUTED)
    d.note(690, 266, "family — so the bill has an owner.", size=11,
           colour=MUTED)

    d.note(20, 500, "The NAT gateway is most of this build's cost, and "
           "nothing on the charge itself says who caused it. The flow log "
           "does.", size=11.5, colour=MUTED)
    d.assert_clean()
    return ("week-14-vpc-flow-logs-intelligence", d.render(),
            "Two instances, two shapes of traffic. The expensive one is the "
            "one with no name on the bill.")


# ---------------------------------------------------------------- week 15 ---
def w15():
    d = Diagram(960, 400,
        "A management account defines an AWS CloudTrail organization trail "
        "covering six member accounts and any account created later. The "
        "trail records management events only, across every Region, with "
        "log-file validation on. Events are delivered to an Amazon S3 bucket "
        "that is private, versioned, TLS-only and set to expire after 365 "
        "days, and are queried with Amazon Athena.")
    d.cloud(14, 14, 932, 330)
    d.group(44, 58, 380, 240, "The organization")

    d.icon(80, 104, "organizations", "Organizations", "management account")
    d.component(230, 104, 170, 56, "6 member accounts", "no per-account setup")
    d.note(64, 236, "One trail covers every account,", size=11, weight="600")
    d.note(64, 254, "including ones created tomorrow.", size=11, colour=MUTED)

    d.arrow(424, 128, 492, 128, step="1")
    d.icon(500, 104, "cloudtrail", "CloudTrail", "org trail · multi-Region")

    d.group(620, 58, 296, 240, "The delivered log")
    d.icon(660, 104, "s3", "S3", "365-day expiry")
    d.arrow(556, 128, 652, 128, step="2")
    d.icon(820, 104, "athena", "Athena", "the query layer")
    d.arrow(708, 128, 812, 128, step="3")
    d.note(640, 236, "Management events only.", size=11, weight="600")
    d.note(640, 254, "Data events are off: they bill", size=11, colour=MUTED)
    d.note(640, 272, "from the very first copy.", size=11, colour=MUTED)

    d.note(20, 372, "The bucket outlives the console's own 90-day history, "
           "which is the only reason the trail answers a question asked a "
           "year later.", size=11.5, colour=MUTED)
    d.assert_clean()
    return ("week-15-cloudtrail-audit-forensics", d.render(),
            "One trail, every account, including the ones that do not exist "
            "yet.")


# ---------------------------------------------------------------- week 16 ---
def w16():
    d = Diagram(1000, 520,
        "An Amazon EventBridge schedule invokes an order processor AWS Lambda "
        "function every five minutes. The function reads its configuration "
        "from an AWS Systems Manager parameter and writes order records to "
        "Amazon S3, with an Amazon CloudWatch alarm on errors. A human "
        "deletes the inline policy that allowed the configuration read, and "
        "the AWS DevOps Agent investigates from an operator app through an "
        "agent space scoped to one account association.")
    d.cloud(14, 14, 972, 450)
    d.group(44, 58, 500, 380, "The observed workload")

    d.icon(80, 110, "eventbridge", "EventBridge", "rate(5 minutes)", size=44)
    d.icon(240, 110, "lambda", "order processor", "reads its config", size=44)
    d.arrow(126, 132, 232, 132, step="1")
    d.icon(400, 110, "systems-manager", "SSM Parameter", "processing-mode",
           size=44)
    d.arrow(286, 132, 392, 132, step="2")

    d.icon(298, 264, "s3", "S3", "order records", size=44)
    d.elbow(286, 132, 320, 256)
    d.icon(440, 264, "cloudwatch", "CloudWatch", "Errors, 300 s", size=44)
    d.arrow(364, 286, 432, 286)

    d.note(64, 356, "The break: a human deletes the config-read policy.",
           size=11.5, colour=RED, weight="600")
    d.note(64, 376, "The code never changed.", size=11, colour=MUTED)

    d.group(584, 58, 392, 380,
            "The agent — the association is the blast radius")
    d.component(620, 120, 320, 56, "Operator App",
                "where a human asks the question")
    d.component(620, 200, 320, 56, "AgentSpace · week16-agent",
                "no budget or duration cap")
    d.component(620, 280, 320, 56, "Association · one AWS account",
                "everything the agent can reach")
    d.arrow(780, 180, 780, 196)
    d.arrow(780, 260, 780, 276)
    d.note(620, 376, "It found the cause. I still had to check it.",
           size=11.5, weight="600")

    d.note(20, 500, "Deployed through awscc, not the AWS provider: the "
           "hashicorp/aws provider ships no DevOps Agent resources.",
           size=11.5, colour=MUTED)
    d.assert_clean()
    return ("week-16-devops-agent-investigations", d.render(),
            "The workload, the break a human caused, and the agent whose "
            "reach is one association wide.")


# ---------------------------------------------------------------- week 17 ---
def w17():
    d = Diagram(1000, 420,
        "An MCP client signs its requests with SigV4 and calls an AWS Lambda "
        "function URL protected by AWS_IAM authentication; an unsigned call is "
        "refused with 403. The function exposes four read-only tools, which "
        "read AWS Cost Explorer, the Resource Groups Tagging API and Amazon "
        "CloudWatch alarm state. Cost Explorer charges per request, so answers "
        "are cached in an Amazon DynamoDB table with a one-hour time to live "
        "and the cache is checked first.")
    d.component(20, 110, 150, 52, "MCP client", "signs with SigV4")
    d.cloud(190, 14, 796, 360)
    d.group(220, 58, 736, 290, "Region: us-east-1")

    d.arrow(174, 134, 252, 134, step="1")
    d.icon(260, 110, "lambda", "Function URL", "AWS_IAM auth")
    d.note(244, 212, "four read-only tools", size=11, colour=MUTED)
    d.note(244, 232, "unsigned = 403", size=11, colour=RED, weight="600")

    d.icon(520, 86, "cost-explorer", "Cost Explorer", "$0.01 per request",
           size=44)
    d.component(480, 170, 260, 52, "Resource Groups Tagging",
                "what runs, and what has no owner")
    d.icon(520, 250, "cloudwatch", "CloudWatch", "alarm state", size=44)
    d.arrow(308, 134, 512, 100)
    d.arrow(308, 134, 472, 190)
    d.arrow(308, 134, 512, 264)

    d.icon(800, 86, "dynamodb", "DynamoDB", "TTL 1 hour", size=44)
    d.arrow(586, 108, 792, 108)
    d.note(760, 230, "A repeated cost question", size=11, weight="600")
    d.note(760, 248, "costs $0.00.", size=11, colour=MUTED)

    d.note(20, 400, "An LLM decides when to call a tool, so a metered read "
           "needs a cache rather than only a budget.", size=11.5, colour=MUTED)
    d.assert_clean()
    return ("week-17-mcp-platform-ops", d.render(),
            "Four read-only tools behind a signed URL, and the one of them "
            "that costs money every time it runs.")


# ---------------------------------------------------------------- week 18 ---
def w18():
    d = Diagram(1000, 480,
        "One Amazon EKS cluster running Kubernetes 1.36 hosts two tenants. "
        "Tenant A runs on a managed Amazon EC2 node and uses EKS Pod Identity. "
        "Tenant B runs on AWS Fargate and must use IRSA, because the Pod "
        "Identity agent is a privileged DaemonSet and Fargate runs neither "
        "DaemonSets nor privileged pods. Each namespace has its own "
        "ResourceQuota, NetworkPolicy and ServiceAccount.")
    d.cloud(14, 14, 972, 410)
    d.group(44, 58, 912, 350,
            "One EKS cluster · $0.10/hr from the moment it exists")

    d.icon(76, 92, "eks", "EKS cluster", "Kubernetes 1.36", size=44)

    d.group(76, 190, 400, 200, "tenant-a · on EC2")
    d.icon(110, 230, "ec2", "Managed node", "t3.small", size=44)
    d.component(230, 224, 220, 56, "Pod Identity", "what AWS recommends")
    d.arrow(164, 252, 222, 252)
    d.note(110, 340, "namespace tenant-a", size=11, weight="600")
    d.note(110, 358, "ResourceQuota · NetworkPolicy", size=11, colour=MUTED)
    d.note(110, 376, "ServiceAccount", size=11, colour=MUTED)

    d.group(524, 190, 400, 200, "tenant-b · on Fargate")
    d.icon(558, 230, "fargate", "Fargate", "no node to manage", size=44)
    d.component(678, 224, 220, 56, "IRSA", "one OIDC provider per cluster")
    d.arrow(612, 252, 670, 252)
    d.note(558, 340, "namespace tenant-b", size=11, weight="600")
    d.note(558, 358, "ResourceQuota · NetworkPolicy", size=11, colour=MUTED)
    d.note(558, 376, "ServiceAccount", size=11, colour=MUTED)

    d.note(20, 452, "Pod Identity cannot run on Fargate: its agent is a "
           "privileged DaemonSet, and Fargate runs neither. The namespace is "
           "a quota, not a boundary.", size=11.5, colour=RED)
    d.assert_clean()
    return ("week-18-eks-self-service", d.render(),
            "Two tenants, one cluster, and two different identity mechanisms "
            "for the same reason.")


# ---------------------------------------------------------------- week 19 ---
def w19():
    d = Diagram(1000, 480,
        "The same Git repository drives two ways of running Argo CD against "
        "one Amazon EKS cluster. The EKS capability for Argo CD runs its "
        "controllers in AWS infrastructure, costs per hour and per "
        "application-hour, places no pods on your nodes, and signs in only "
        "through IAM Identity Center. The self-managed Helm install runs seven "
        "pods on your own nodes and needs a larger one. Either way the Argo CD "
        "CRDs end up installed in the cluster, cluster-scoped and shared.")
    d.component(20, 200, 180, 52, "Git repository",
                "gitops/workloads/podinfo")
    d.cloud(220, 14, 766, 420)

    d.group(250, 58, 706, 160, "AWS-managed · outside your cluster")
    d.icon(290, 96, "eks", "EKS capability", "Argo CD, run by AWS", size=44)
    d.note(400, 120, "$0.03/hr + $0.0015 per Application-hour", size=11,
           weight="600")
    d.note(400, 140, "0 pods on your nodes", size=11, colour=GREEN)
    d.note(400, 160, "Identity Center is the only sign-in", size=11,
           colour=MUTED)
    d.note(400, 180, "its CRDs are still installed in your cluster", size=11,
           colour=RED)

    d.group(250, 248, 706, 160, "Self-managed · on your nodes")
    d.icon(290, 286, "eks", "Argo CD 3.5.3", "Helm chart 10.9.1", size=44)
    d.note(400, 310, "Free software, not free to run", size=11, weight="600")
    d.note(400, 330, "7 pods on your nodes", size=11, colour=MUTED)
    d.note(400, 350, "needs a bigger node: +$0.0208/hr", size=11, colour=MUTED)
    d.note(400, 370, "every feature upstream has", size=11, colour=GREEN)

    d.arrow(204, 214, 282, 120)
    d.arrow(204, 238, 282, 300)

    d.note(20, 462, "The CRDs are cluster-scoped either way, so the choice is "
           "about who runs the controllers — not about staying out of the "
           "cluster.", size=11.5, colour=MUTED)
    d.assert_clean()
    return ("week-19-gitops-argocd", d.render(),
            "One repository, two places to run the controllers, and the same "
            "CRDs in the cluster at the end of both.")


# ---------------------------------------------------------------- week 20 ---
def w20():
    d = Diagram(1000, 500,
        "A publisher calls PutEvents against a custom Amazon EventBridge bus. "
        "An orders rule matches on source and detail-type and invokes a "
        "consumer AWS Lambda function, with an Amazon SQS dead-letter queue "
        "for delivery failures. A catch-all rule matches everything else into "
        "an Amazon CloudWatch log group, so no event is unaccounted for. An "
        "archive keeps what was published rather than what was delivered.")
    d.component(20, 180, 150, 52, "publisher", "PutEvents → 200")
    d.cloud(190, 14, 796, 440)
    d.group(220, 58, 736, 370, "Region: us-east-1")

    d.arrow(174, 204, 252, 204, step="1")
    d.icon(260, 180, "eventbridge", "week20-bus", "a custom bus")

    d.component(560, 120, 380, 56, "rule: orders",
                "source and detail-type must both match")
    d.arrow(316, 192, 552, 150, step="2")
    d.icon(600, 210, "lambda", "consumer", "the function", size=44)
    d.arrow(622, 180, 622, 204)
    d.icon(760, 210, "sqs", "DLQ", "delivery failures only", size=44)
    d.arrow(646, 232, 752, 232)

    d.component(560, 352, 280, 52, "rule: catch-all",
                "so nothing is unaccounted for")
    d.elbow(316, 216, 560, 348)
    d.icon(870, 330, "cloudwatch", "log group", "unmatched = 0", size=44)
    d.arrow(844, 374, 866, 356)

    d.component(240, 300, 280, 52, "archive",
                "keeps what was published")
    d.elbow(308, 204, 360, 294)
    d.note(252, 382, "published is not delivered:", size=11, weight="600")
    d.note(252, 400, "the archive holds the first,", size=11, colour=MUTED)
    d.note(252, 418, "the DLQ reports the second.", size=11, colour=MUTED)

    d.note(20, 482, "A catch-all rule is what turns “nobody wanted it” "
           "into a number you can alarm on.", size=11.5, colour=MUTED)
    d.assert_clean()
    return ("week-20-eventbridge-accountable-bus", d.render(),
            "Every event lands somewhere: a rule, a queue, or the log group "
            "that proves nothing was dropped.")


BUILDERS = [w09, w10, w11, w12, w13, w14, w15, w16, w17, w18, w19, w20]


def install(prefix, svg, caption):
    cands = []
    for f in sorted(os.listdir(POSTS)):
        if not (f.startswith(prefix) and f.endswith(".html")):
            continue
        t = io.open(os.path.join(POSTS, f), encoding="utf-8").read()
        fm = t.split("---", 2)[1] if t.count("---") >= 2 else ""
        if "AWS Weekly Lab" in fm:
            cands.append((f, t))
    if len(cands) != 1:
        raise SystemExit("expected one AWS lab post for %r, got %s"
                         % (prefix, [c[0] for c in cands]))
    fn, t = cands[0]
    path = os.path.join(POSTS, fn)
    m = re.search(r'<figure class="diagram">.*?</figure>', t, re.S)
    if m:
        block = ('<figure class="diagram">\n' + svg + "\n"
                 "      <figcaption>" + caption + "</figcaption>\n    </figure>")
        t = t[:m.start()] + block + t[m.end():]
    else:
        start = end = None
        depth = 0
        i = 0
        while i < len(t):
            if t.startswith("<svg", i):
                if depth == 0:
                    open_at = i
                depth += 1
            elif t.startswith("</svg>", i):
                depth -= 1
                if depth == 0:
                    if start is None or (i + 6 - open_at) > (end - start):
                        start, end = open_at, i + 6
            i += 1
        if start is None:
            raise SystemExit("no <svg> found in %s" % fn)
        t = t[:start] + svg + t[end:]
    io.open(path, "w", encoding="utf-8", newline="\n").write(t)
    return fn


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    write = "--write" in sys.argv
    for b in BUILDERS:
        prefix, svg, cap = b()
        if args and not any(a in prefix for a in args):
            continue
        if write:
            fn = install(prefix, svg, cap)
            print("  installed %-46s %6d chars" % (fn, len(svg)))
        else:
            print("  built     %-46s %6d chars" % (prefix, len(svg)))
