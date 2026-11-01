# -*- coding: utf-8 -*-
"""One plain-English definition per service, shared by every AWS lab post.

WHY THIS EXISTS (2026-11-01)
----------------------------
Jay asked that the Cloud Services and Concepts section say what each service IS,
not only what the lab did with it, and that it read the same way from week 1
onward. Fifteen posts carried a two-column table under four different headers
("Service or concept | Its job here", "Service | Its job here",
"Service | Purpose in this lab"), and eight posts had no such section at all.

Writing a definition per post would produce eighty-three independent judgements
about the same two dozen services. Writing them once here means Amazon S3 is
described the same way in week 14 as in week 18, and a correction lands
everywhere at once.

HOUSE STYLE, taken from weeks 24 and 25, which Jay approved:

  * Plain English for a reader who has never used the service.
  * Say what it IS first, then the mechanical or billing fact that matters.
  * No vendor marketing copy. The master standard bans the blurb, and it also
    bans leaving the reader not knowing what the thing is.
  * One or two sentences. This is a table cell, not a section.

GROUNDING: service definitions are anchored on AWS's own published service
models in scripts/aws_services.json, which scripts/refresh_aws_services.py
regenerates from botocore and a GitHub workflow keeps current. The wording here
is a plain-English rendering of those, not a copy of them. Concepts that are
not services (IRSA, a conformance pack, an auth policy) are defined from the
mechanism the lab actually exercised.
"""

DEFINITIONS = {
    # -- compute -------------------------------------------------------------
    "AWS Lambda":
        "Runs a piece of code on demand with no server to manage. You are "
        "billed per request and per millisecond it runs, and each in-flight "
        "request occupies one execution environment.",
    "Lambda":
        "Runs a piece of code on demand with no server to manage. You are "
        "billed per request and per millisecond it runs.",
    "Lambda (Python 3.13)":
        "Runs a piece of code on demand with no server to manage, here on the "
        "Python 3.13 runtime. You are billed per request and per millisecond.",
    "AWS Lambda + Function URL":
        "Lambda runs code with no server to manage; a function URL gives that "
        "function its own HTTPS endpoint directly, with no API Gateway in "
        "front and no hourly charge for sitting idle.",
    "Amazon EC2":
        "Virtual machines you rent by the second. You choose the size and the "
        "operating system, and you are responsible for what runs on them.",
    "ECS Fargate":
        "Runs containers without managing servers. You declare how many copies "
        "(tasks) you want and ECS keeps that many running.",
    "Amazon ECS on Fargate":
        "Runs containers without managing servers. You declare how many copies "
        "(tasks) you want and ECS keeps that many running.",
    "AWS Fargate":
        "The serverless engine that runs a container without you providing a "
        "machine for it. There is no node to patch, and nothing that needs a "
        "privileged agent can run on it.",
    "Amazon EKS":
        "Managed Kubernetes. AWS runs the control plane and charges by the "
        "hour for it from the moment the cluster exists; the worker nodes and "
        "what runs on them are still yours.",
    "Application Auto Scaling":
        "Adds and removes capacity for services that do not have their own "
        "scaler, by watching a metric and a target value you set.",

    # -- networking and delivery --------------------------------------------
    "Application Load Balancer":
        "Spreads traffic across the tasks. Its target group is the register of "
        "which tasks exist and which are passing health checks.",
    "Shared ALB, path-based routing":
        "One load balancer serving several applications, choosing a backend "
        "from the URL path rather than from a separate address per service.",
    "Target groups (blue and green)":
        "A target group is the list of backends a load balancer may send to. "
        "Two of them let the same listener point at one version or the other.",
    "Amazon CloudFront":
        "A content delivery network. Requests land at an edge location near "
        "the caller, which answers from cache or forwards to your origin.",
    "API Gateway (HTTP API)":
        "A managed front door that accepts HTTP requests and forwards them to "
        "a backend. The HTTP API flavour is the cheaper, simpler one, billed "
        "per million requests.",
    "API Gateway REST API":
        "A managed front door for HTTP requests. The REST flavour is the older "
        "and dearer one, and it is the only flavour AWS WAF can attach to.",
    "VPC interface and gateway endpoints":
        "Private doors from your network to an AWS service. Traffic reaches "
        "the service without crossing the internet, so no NAT gateway is "
        "needed; gateway endpoints for S3 carry no hourly charge.",
    "NAT Gateway":
        "Lets a private subnet reach the internet outbound while staying "
        "unreachable inbound. It is billed per hour AND per gigabyte, which is "
        "what makes it the expensive component in most small builds.",
    "Amazon VPC Lattice":
        "An application-layer network that connects services to each other and "
        "authenticates every call, instead of relying on subnet and security "
        "group reachability.",
    "Service network":
        "The Lattice object services join in order to reach one another. It "
        "authenticates callers, but on its own it does not decide which caller "
        "is allowed to do what.",
    "Lattice service":
        "A single application registered on the service network, with its own "
        "listener, routes and targets.",
    "Auth policy":
        "A resource policy attached to a Lattice service network or service "
        "that says which signed principals may call it. Without one, "
        "authentication proves who called but nothing refuses them.",

    # -- data and storage ----------------------------------------------------
    "Amazon S3":
        "Object storage: you put files (objects) into buckets and pay for what "
        "you store and for each request, with no disk to size in advance.",
    "Amazon DynamoDB":
        "A managed key-value database with no servers to size. You are billed "
        "per read and write rather than per hour.",
    "DynamoDB":
        "A managed key-value database with no servers to size. You are billed "
        "per read and write rather than per hour.",
    "AWS Glue Data Catalog":
        "A catalogue of table definitions — names, columns and types — that "
        "query engines read so they know how to interpret files in S3.",
    "Amazon Athena":
        "Runs SQL straight against files in S3 with no database to run. You "
        "are billed for the bytes each query scans, so file layout is a cost "
        "decision.",

    # -- events, messaging, orchestration ------------------------------------
    "Amazon EventBridge":
        "An event bus. Services and your own code publish events to it, and "
        "rules decide which events reach which targets.",
    "EventBridge":
        "An event bus. Services and your own code publish events to it, and "
        "rules decide which events reach which targets.",
    "Lambda + EventBridge":
        "EventBridge decides when something should run and Lambda is the thing "
        "that runs, with no server behind either.",
    "AWS Lambda + EventBridge":
        "EventBridge decides when something should run and Lambda is the thing "
        "that runs, with no server behind either.",
    "AWS Lambda and Amazon SQS":
        "Lambda runs the code; SQS is a queue that holds messages until "
        "something collects them, including the ones that failed to deliver.",
    "EventBridge archive and replay":
        "An archive keeps a copy of what was PUBLISHED to a bus, not what was "
        "delivered, and replay pushes those stored events through the rules "
        "again.",
    "Schema discovery":
        "Watches real traffic on a bus and infers the shape of the events "
        "flowing through it, recording what producers actually send rather "
        "than what they were supposed to send.",
    "Step Functions":
        "Runs a workflow as an explicit state machine, so each step, its retry "
        "behaviour and its failure path are declared rather than buried in "
        "code.",
    "Amazon SNS":
        "A publish-and-subscribe topic. One message is fanned out to every "
        "subscriber — email, a queue, or a function.",
    "SNS":
        "A publish-and-subscribe topic. One message is fanned out to every "
        "subscriber — email, a queue, or a function.",
    "SNS / SQS":
        "SNS fans one message out to many subscribers; SQS is a queue that "
        "holds messages until something collects them.",
    "SNS + SQS":
        "SNS fans one message out to many subscribers; SQS is a queue that "
        "holds messages until something collects them.",

    # -- observability -------------------------------------------------------
    "Amazon CloudWatch":
        "AWS's metrics and logs service. Most services publish numbers into it "
        "automatically, without being asked to.",
    "CloudWatch":
        "AWS's metrics and logs service. Most services publish numbers into it "
        "automatically, without being asked to.",
    "CloudWatch alarm":
        "Reads a metric, summarises each fixed window with a statistic, and "
        "fires after N bad windows. Not a live tripwire.",
    "CloudWatch alarms":
        "Reads a metric, summarises each fixed window with a statistic, and "
        "fires after N bad windows. Not a live tripwire.",
    "CloudWatch + SNS":
        "CloudWatch watches a metric and decides when it is wrong; SNS is how "
        "that decision reaches a person.",
    "AWS Lambda + CloudWatch":
        "Lambda runs the code; CloudWatch stores the metrics and logs it "
        "produces.",
    "CloudWatch OAM (sink + link)":
        "Observability Access Manager lets one account READ another account's "
        "logs and metrics in place. A sink receives the share, a link grants "
        "it, and nothing is copied.",
    "Logs centralization rules":
        "An account-level rule that copies log events into a destination log "
        "group as they arrive, so the copy survives the source account.",
    "Logs Insights":
        "A query language for CloudWatch log groups, for asking questions "
        "across many log streams at once.",
    "VPC Flow Logs":
        "A record of every network flow a VPC accepted or rejected — addresses, "
        "ports, bytes and the verdict. Record version 11 adds fields such as "
        "the instance tag and the next-hop family.",
    "AWS CloudTrail":
        "Records who called which AWS API, when, and from where. It answers "
        "who did it, not what the data contained.",
    "AWS CloudTrail (organization trail)":
        "One CloudTrail that records API calls for every account in an "
        "organization, including accounts created after the trail was made.",
    "AWS CloudTrail / Config / CloudWatch":
        "CloudTrail records who called what, Config records how resources were "
        "configured, and CloudWatch holds the metrics and logs.",

    # -- security and governance --------------------------------------------
    "IAM":
        "AWS's permission system. Every call is signed by a principal, and a "
        "policy decides whether that principal may make it.",
    "IAM Identity Center":
        "AWS's sign-in and assignment layer for people. Users and groups are "
        "defined once, and assignments grant them a role in each account.",
    "AWS Organizations":
        "Groups AWS accounts under one management account, so policy and "
        "billing apply across all of them rather than account by account.",
    "AWS Config":
        "Records the configuration of your resources over time and evaluates "
        "them against rules, so drift is visible rather than inferred.",
    "Conformance pack":
        "A bundle of Config rules, and their remediation, deployed as one "
        "object. The pack owns its rules, so none are left behind to drift.",
    "SSM Automation":
        "A runbook AWS executes on your behalf — the mechanism Config uses to "
        "put a non-compliant resource back the way it should be.",
    "Security Hub CSPM":
        "Collects findings from other security services and from its own "
        "standards checks, and gives them one format and one place to live.",
    "Amazon GuardDuty":
        "Watches account and network activity for signs of active compromise, "
        "and raises a finding when it sees one.",
    "Amazon Inspector":
        "Scans workloads and container images for known software "
        "vulnerabilities, continuously rather than on request.",
    "AWS WAF":
        "A web application firewall. Rules are evaluated in order against each "
        "request, and each rule can block, allow or merely count.",
    "AWS Shield Standard":
        "Always-on protection against network and transport layer floods, "
        "included for every account at no charge. There is nothing to deploy "
        "and it does not read HTTP.",
    "AWS Signer":
        "Signs artefacts, such as container images, so a consumer can verify "
        "where they came from and that they have not changed.",
    "Amazon ECR":
        "A private registry for container images, with per-repository rules "
        "such as refusing to overwrite a tag that already exists.",
    "AWS CodeBuild":
        "Runs build and test commands on AWS-managed machines, billed per "
        "build minute.",
    "EKS Pod Identity":
        "The newer way to give a Kubernetes pod an AWS role: an agent on the "
        "node hands out credentials, so no per-cluster trust policy is needed. "
        "The agent is a privileged DaemonSet.",
    "IRSA":
        "IAM Roles for Service Accounts: the pod's Kubernetes identity is "
        "exchanged for an AWS role through an OIDC provider registered per "
        "cluster. It needs no agent, so it is the only option on Fargate.",
    "ResourceQuota / NetworkPolicy":
        "Kubernetes objects that cap what a namespace may consume and which "
        "pods may talk to it. They limit a tenant; they are not an account "
        "boundary.",

    # -- cost ----------------------------------------------------------------
    "AWS Cost Explorer API":
        "The programmatic way to read your own spend. Unlike most read calls "
        "it is metered, at a per-request charge, which is why answers are "
        "worth caching.",

    # -- agents and tooling --------------------------------------------------
    "AWS DevOps Agent":
        "An AWS-run agent that investigates an operational problem and reports "
        "what it believes the cause to be. It recommends; it does not change "
        "anything.",
    "Agent space":
        "The boundary an agent works inside. Everything the associated account "
        "can reach is in scope, which makes the association the blast radius.",
    "AWS Lambda, EventBridge, SSM, S3":
        "The workload being watched: EventBridge triggers, Lambda runs, "
        "Systems Manager holds the configuration, and S3 holds the output.",
    "EKS Capability for Argo CD":
        "Argo CD run by AWS outside your cluster, billed per hour and per "
        "application-hour. Its custom resource definitions are still installed "
        "into your cluster, where they are cluster-scoped and shared.",
    "Argo CD (self-managed)":
        "The upstream GitOps controller, installed into your own cluster by "
        "Helm. The software is free; the pods it runs are not.",
    "AWS Fault Injection Service":
        "Managed fault injection. You define a target, an action and a stop "
        "condition.",
    "Terraform / HCP Terraform":
        "Terraform declares infrastructure as code; HCP Terraform runs it on "
        "HashiCorp's machines and keeps the state file.",
    "HCP Terraform":
        "HashiCorp's hosted Terraform. It runs plans and applies on its own "
        "machines and keeps the state file, and it assumes an AWS role by "
        "OIDC so no static keys exist anywhere.",
}


def definition(name):
    """The definition for a table's service name, or None if we have none.

    Returning None rather than a placeholder is deliberate: a cell reading
    "TODO" would ship, and a missing one fails the check that calls this.
    """
    return DEFINITIONS.get(name.strip())


def missing(names):
    return sorted({n for n in names if definition(n) is None})
