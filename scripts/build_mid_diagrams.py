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


BUILDERS = [w09, w10, w11, w12]


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
