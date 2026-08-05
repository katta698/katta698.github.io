# AWS Daily Intelligence — backlog and change log

A running record of every AWS change ranked during a daily run, whether or not
it became a post. One post ships per day; everything else lands here.

**Why this exists.** The AWS What's New feed only returns about a week of
items. Anything ranked but not written silently ages out of the feed and is
lost. This file is the durable reference — both a to-write queue and a log of
what changed and when.

**Status values:** `#N` a post shipped · `open` still worth writing ·
`aged out` no longer current, kept for reference · `skipped` filtered out
deliberately.

**Maintenance.** Add the day's full ranking after each run. Check this file
before picking a topic — a held item can beat the day's news, and anything
approaching a week old is about to become unwritable.

---

## 4 August 2026 — covered by post #3

| Item | Service | Status | Importance | Reference |
| --- | --- | --- | --- | --- |
| RFC 9151 / CNSA 1.0 TLS security policies | ALB, NLB | **#3** | High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-application-network/) |
| Supply chain security added as 10th category (Chainguard, Socket) | Security Hub Extended | open | High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-security-hub-extended-adds-supply-chain-security) |
| Forward Proxy, no-source-preservation mode — **Preview**, us-east-2 only | Network Firewall | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-network-firewall-forward-proxy-preview/) |
| Web Search for GPT models, AWS-operated index, zero data egress | Bedrock | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-bedrock-web/) |
| Spark Connect for interactive sessions | EMR on EC2 | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-emr-ec2-spark-connect/) |
| S3 Vectors in European Sovereign Cloud (Germany) | S3 | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-s3-vectors-european-sovereign-cloud-germany/) |
| Case export to CSV; 15/30-minute interval capacity planning | Connect | skipped | Low-Med | — |
| C8g, I8g regional expansions | EC2 | skipped | Low | — |

**Worth revisiting:** Network Firewall Forward Proxy is the most
architecturally interesting item of the day but is Preview in one Region.
Re-rank it on GA.

---

## 3 August 2026 — covered by post #2

| Item | Service | Status | Importance | Reference |
| --- | --- | --- | --- | --- |
| Provisioned Mode for SQS ESM: 2,000 → 10,000 event pollers | Lambda | **#2** | High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-Lambda-provisioned-sqs-esm-max-pollers/) |
| Recommended resilience tests, FIS integration, AZ/Regional impairment | Resilience Hub | open | High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-resilience-hub/) |
| Image layers up to 200 GB (Docker push only; `UploadLayerPart` stays 50 GB) | ECR | open | High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-ecr-image-layers/) |
| 1M token context for GPT-5.6 Sol/Terra/Luna | Bedrock | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/gpt-sol-terra-luna-long-context-bedrock) |
| Full fine-tuning in serverless customization, 25+ open models | SageMaker AI | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-sagemaker-fft) |
| Continuous modernization GA — repo-wide tech debt analysis, opens PRs | AWS Transform | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/7/aws-transform-continuous-general-available) |
| 15 new resource types; auto-recorded if recording all types | Config | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-config-new-resource-types) |
| Max account quota visible in Service Quotas — us-east-1 only | Organizations | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-organizations/) |
| Miggo Security managed rule groups for AI/ML apps | WAF | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/07/aws-waf-miggo-managed-rule-groups) |

**Worth revisiting:** ECR's 200 GB layers has a sharp asymmetry worth a post —
Docker push reaches 200 GB while the SDK/CLI `UploadLayerPart` path stays at
50 GB. Relevant to anyone packaging model weights into images.

---

## 27–31 July 2026 — covered by post #1

| Item | Service | Status | Importance | Reference |
| --- | --- | --- | --- | --- |
| Policy-Based Routing GA | Transit Gateway | **#1** | High | [link](https://aws.amazon.com/about-aws/whats-new/2026/07/aws-transit-gateway-policy-based-routing/) |
| Managed Prometheus collectors, OTLP format, hourly collector charge | CloudWatch | open | High | [link](https://aws.amazon.com/about-aws/whats-new/2026/07/cloudwatch-managed-collectors/) |
| Java 8/11/17 on AL2023; AL2 runtimes supported to 30 June 2027 | Lambda | open | High | [link](https://aws.amazon.com/about-aws/whats-new/2026/07/aws-lambda-java-amazon-linux/) |
| Multi-Region support for the Identity Center directory | IAM Identity Center | open | High | [link](https://aws.amazon.com/about-aws/whats-new/2026/07/aws-iam-identity-center-extends-multi-region-support-to-identity-center-directory) |
| Policy Simulator moves to IAM console, adds SCP and condition-key testing | IAM | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/07/iam-policy-simulator-iam-console/) |
| Multicloud connectivity to OCI GA — us-east-1 only | AWS Interconnect | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/07/aws-announces-AWS-interconnect-multicloud-OCI-GA/) |
| PrivateLink for the cluster OIDC endpoint (IRSA without internet egress) | EKS | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/07/amazon-eks-oidc-endpoint-privatelink) |
| BGP route visibility on VIFs, `ListVirtualInterfaceRoutes` | Direct Connect | cited in #1 | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/07/aws-direct-connect-bgp-visibility/) |
| Variant data type for Apache Iceberg V3 | S3 Tables | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/07/amazon-s3-tables-variant-iceberg-v3/) |
| Multi-Region clusters in 4 more Regions (16 total) | Aurora DSQL | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/07/amazon-aurora-dsql-adds-multi-region-clusters-four-more-regions/) |
| MCP App for exposure findings — **Preview** | Security Hub | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/07/aws-security-hub-mcp-app/) |
| Pre-parse and new text transformations | WAF | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/07/aws-waf/) |
| Instance Refresh support in CloudFormation | EC2 Auto Scaling | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/07/ec2-auto-scaling-instance-refresh-cloudformation) |
| Express brokers deliver to S3 and to Iceberg streaming tables | MSK | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/07/aws-msk-express-brokers-delivers-to-amazon-s3) |
| Standard to Enterprise Edition upgrade | Managed Microsoft AD | open | Low | [link](https://aws.amazon.com/about-aws/whats-new/2026/07/aws-microsoft-ad-edition-upgrade/) |

**Worth revisiting:** the Lambda Java AL2023 item carries a hard deadline —
AL2-based Java runtimes are supported only to 30 June 2027. Worth writing well
before that date rather than after.

---

## Standing candidates

Items held here deliberately, independent of the daily cycle. Useful when a
day produces no significant news.

- **Network Firewall Forward Proxy** — write on GA and wider Region support.
- **CloudWatch managed Prometheus collectors** — strong operations topic,
  competes well any day it is not beaten by something GA and free.
- **Lambda Java on AL2023** — deadline-driven, 30 June 2027.
- **EKS PrivateLink for OIDC** — closes a well-known private-cluster gap.
