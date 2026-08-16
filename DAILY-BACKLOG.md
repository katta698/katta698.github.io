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

## A missed daily slot is not missed coverage

Set 2026-08-16, corrected the same day after the first version of this rule got
it wrong.

**The weekly roundup already covers every announcement in its date range.** Its
inventory is built from the raw feed for those dates, so nothing in the window
can be absent from it. When a daily slot takes a held item instead of the day it
was due to cover, that day's news is still in the roundup — what it does not get
is a *deep-dive*.

So there is no gap to fill and no catch-up to publish. The items simply stay in
this file as `open`, and compete for a future daily slot on their merits like
anything else held here.

**What went wrong the first time this was written.** Post #11 took Thursday's S3
announcement into Saturday's slot, leaving Friday 14 August without a deep-dive.
That was recorded here as news needing to be "folded into Saturday's post" — but
weekly #2 had already published that morning, covering 10–14 August, and it
carried Managed Dashboards in both its analysis and its inventory. The news was
never uncovered. Only the deep-dive was missing.

**Never move an item into a later roundup to compensate.** Each roundup covers a
distinct date range, so a 14 August item cannot appear in the roundup for 17–21
August. That is the never-repeat rule in CLAUDE.md, and it is what stops the
series quietly recycling old news.

**Tuesday always starts clean.** Tuesday covers Monday and carries nothing owed
from the week before.

---

## Cadence: five posts, Tuesday to Saturday

Fixed on 2026-08-14. **AWS publishes Monday to Friday, so there are five news
days and there should be five posts.** Each one covers the previous weekday:

| Post publishes | Covers |
| --- | --- |
| Tuesday | Monday |
| Wednesday | Tuesday |
| Thursday | Wednesday |
| Friday | Thursday |
| Saturday | Friday |

**There is no Monday post.** A Monday post has no news of its own: the weekend
is empty, and the previous Friday is already covered by Saturday's post. The
only things it can do are cover stale news, cover nothing, or flush the
backlog. The first is what happened — post #1 published Monday 3 August
covering 30 July news, three days stale, and then fell outside the weekly
roundup's window and had to be linked separately as an orphan. Week two dropped
Monday without anyone deciding to, and settled on this shape by itself.

**Saturday rather than Monday for Friday's news, and this is the part that
matters.** Both Tue–Sat and Mon–Fri are five posts; the difference is where
Friday's news lands. The weekly roundup publishes Saturday covering Monday to
Friday, and it links every daily published to that point. If Friday's daily
waits until Monday, the Saturday roundup discusses an announcement whose
deep-dive does not exist yet — the orphan problem again, in the other
direction. Publishing Friday's daily on Saturday puts it alongside the roundup
that links it.

**The load this creates, and what to cut.** Saturday carries three posts:
architecture, daily and weekly. Monday carries one, architecture only. If a
Saturday is too full, cut the **architecture** post — the roadmap has no date
attached to it and slipping a day costs nothing. Do not cut the daily: it is
the only one with a news window that closes, and the weekly depends on it
existing.

**A quiet day still gets a post, a quiet week still gets a roundup — but
neither gets padding.** If a day produces nothing worth a deep-dive, take the
strongest held item from this file rather than writing up something thin. That
is what the backlog is for. See the never-repeat rules in CLAUDE.md.

---

## 14 August 2026 — no daily deep-dive; covered in weekly #2's inventory

Three announcements. None became a daily: Saturday's slot went to a held item
instead. All three are in weekly #2 (10–14 August), which published the same
morning, so they are covered — they are held here only as candidates for a
future daily deep-dive, not because anything is missing from the record.

| Item | Service | Status | Importance | Reference |
| --- | --- | --- | --- | --- |
| Managed Dashboards — five preconfigured cost dashboards, no setup, no cost | Billing & Cost Management | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-billing-and-cost-management-managed-dashboards/) |
| Click tracking supports custom URL paths for mobile app deep linking | SES | open | Low-Med | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-ses-supports-customurl-deeplinking) |
| Oracle Application Express (APEX) 26.1 support | RDS for Oracle | skipped | Low | version bump |

**Worth revisiting:** Managed Dashboards is the strongest of the three. Five
read-only dashboards arrive populated with account data, and duplicating one to
edit it forks it away from the version AWS maintains, with no drift signal.

---

## 13 August 2026 — nothing outranked the held EKS item; post #10 took that

Eight announcements, none architectural. The best of them, S3 returning more
policy detail in access denied messages, is a genuine quality-of-life fix and is
held as the strongest open item.

| Item | Service | Status | Importance | Reference |
| --- | --- | --- | --- | --- |
| Additional policy details in access denied error messages | S3 | **#11** | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/s3-additional-policy-details-access-denied-error-messages/) |
| CLI, administration controls, faster connections | Client VPN | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-client-vpn-cli/) |
| CVE-2026-18428 — async query validation bypass in the OpenSearch SQL plugin | OpenSearch | open | Med-High | [link](https://aws.amazon.com/security/security-bulletins/rss/2026-081-aws/) |
| Switch from e-mail to DNS validation on an existing certificate | Certificate Manager | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/AWS-Certificate-Manager-Email-DNS-Switch) |
| Minimum aggregation thresholds in custom analysis rules | Clean Rooms | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-clean-rooms-minimum-aggregation-custom-analysis-rules) |
| Spot Placement Score now includes Local Zones | EC2 | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/spot-placement-score-local-zones/) |
| Claude Opus 5 available in GovCloud (US) | Bedrock | skipped | Low-Med | Region expansion |
| Daybreak Red and Daybreak Blue from OpenAI on Bedrock | Bedrock | skipped | Low | catalogue addition |
| Microsoft 365 extensions GA | Amazon Quick | skipped | Low | — |

**Worth revisiting:** the ACM e-mail-to-DNS validation switch is small but removes
a long-standing migration annoyance — e-mail-validated certificates previously
had to be reissued to move to DNS validation.

---

## 12 August 2026 — covered by post #9

First run on the widened source list: 6 What's New announcements, 2 security
bulletins and 17 service-blog posts across 19 feeds. Two items shipped with a
same-day AWS deep-dive blog, which is the signal that separated them from the
rest.

| Item | Service | Status | Importance | Reference |
| --- | --- | --- | --- | --- |
| Role manager creates roles from AWS managed templates; Lambda template attaches `PowerUserAccess` | IAM | **#9** | High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-iam-role-manager) |
| Control plane parameters configurable — scheduler, controller manager, API server | EKS | **#10** | High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-eks-control-plane-configuration-parameters) |
| CVE-2026-19311 — missing authorization in OpenSearch Alerting plugin | OpenSearch | open | Med-High | [link](https://aws.amazon.com/security/security-bulletins/rss/2026-078-aws/) |
| Forensic container checkpointing for incident response | EKS | open | Med-High | [link](https://aws.amazon.com/blogs/containers/forensic-container-checkpointing-on-amazon-eks/) |
| CVE-2026-19642 / 19643 — Base64 decoder memory safety in AWS SDK for C++ | AWS SDK | open | Medium | [link](https://aws.amazon.com/security/security-bulletins/rss/2026-080-aws/) |
| Deny by default for custom permissions | Amazon Quick | open | Medium | [link](https://aws.amazon.com/whats-new/2026/08/amazon-quick-deny-by-default-permissions/) |
| Burst to Region — overflow Outposts workloads to EC2 | Outposts | open | Medium | [link](https://aws.amazon.com/blogs/compute/burst-to-region-overflow-aws-outposts-workloads-to-amazon-ec2/) |
| Aurora PostgreSQL major-version migration with live Debezium CDC connectors | Aurora | open | Medium | [link](https://aws.amazon.com/blogs/database/migrate-amazon-aurora-postgresql-across-major-versions-with-active-debezium-cdc-connectors-using-native-logical-replication/) |
| Oracle Exadata on Exascale for Oracle AI Database@AWS | Oracle@AWS | open | Medium | [link](https://aws.amazon.com/blogs/database/introducing-oracle-exadata-on-exascale-for-oracle-ai-databaseaws/) |
| Data loss prevention with Microsoft Purview | Amazon Quick | open | Low-Med | [link](https://aws.amazon.com/whats-new/2026/08/amazon-quick-dlp-purview/) |
| Interactive map view for Regions and Local Zones | Global View | skipped | Low | console UI only |
| Manual assignment of queued agent-first callbacks | Connect | skipped | Low | — |
| Bedrock cost attribution part 2, Athena and CUDOS | Bedrock | skipped | Low-Med | how-to, not a change |
| Storage Lens + Kiro CLI cost reduction case study | S3 | skipped | Low | customer case study |
| Hybrid ML inferencing with FSx for NetApp ONTAP | FSx | skipped | Low-Med | how-to, not a change |

**Worth revisiting:** EKS control plane configuration is the strongest held
item and the better pure-engineering story — EKS has never exposed scheduler,
controller manager or API server tuning on a managed control plane. It lost
only because IAM reaches every reader and the `PowerUserAccess` default is a
live security decision. Write it before it ages out.

**Correction logged:** the initial ranking described role manager as on by
default. It is not — an administrator enables it once in IAM account settings,
and what happens automatically is its behaviour thereafter inside supported
consoles. Caught by checking AWS's security blog against the announcement
before writing.

---

## 11 August 2026 — a thin day; post #8 used a held item instead

Nine announcements, mostly SageMaker JumpStart catalogue additions and one
Region expansion. Nothing outranked the held AWS Backup item from 6 August, so
post #8 took that instead. This is what the backlog is for.

| Item | Service | Status | Importance | Reference |
| --- | --- | --- | --- | --- |
| Managed external secrets for Jenkins and SonarQube, no rotation code | Secrets Manager | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/secrets-manager-integration-jenkins-sonarqube/) |
| IAM principal cost allocation extended to the bedrock-mantle endpoint | Bedrock | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-bedrock-expands-iam-principal-cost-allocation-bedrock-mantle/) |
| Export privacy-enhanced analysis logs for SQL | Clean Rooms | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-clean-rooms-export-analysis-log-sql) |
| MariaDB 12.3 support | RDS for MariaDB | open | Low-Med | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-rds-mariadb-1232-available/) |
| One-click access to SageMaker Unified Studio from the console | AWS Glue | open | Low-Med | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/smus-glue-access) |
| Performance dashboard for Cases | Connect | open | Low-Med | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-connect-cases-dashboard/) |
| LocateAnything-3B, Qwen-AgentWorld-35B, Qwen3.5-122B; NVIDIA Nemotron 3.5 Lightning | SageMaker JumpStart | skipped | Low | catalogue additions, 2 announcements |
| R8a in Canada (Central) | EC2 | skipped | Low | — |

**Worth revisiting:** Secrets Manager for Jenkins and SonarQube was the best of
the day and is a genuine operational win — rotation for third-party CI tokens
with no custom Lambda. Held only because the AWS Backup item outranked it.

---

## 10 August 2026 — covered by post #7

| Item | Service | Status | Importance | Reference |
| --- | --- | --- | --- | --- |
| Application status checks — 4th check type, HTTP/HTTPS, Auto Scaling replaces impaired | EC2 | **#7** | High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-ec2-application-status-checks) |
| UEFI boot mode now preserved for Linux servers | Elastic Disaster Recovery | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-drs-linux-uefi) |
| Up to 10,000 collections per collection group | OpenSearch Serverless | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-opensearch-serverless-supports-10000-collections-per-collection-group/) |
| Service-managed shader caching | GameLift Streams | open | Low-Med | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/Amazon-GameLift-Streams-Shader-Caching/) |
| FLUX.2-small-decoder, gemma-4-12B-it; langcache-embed-v3-small, Mellum2-12B, LightOnOCR-2-1B; GLM-5.2 FP8, Nemotron-Nano-12B-v2, GLM-OCR | SageMaker JumpStart | skipped | Low | model catalogue additions, 3 announcements |
| High Memory U7i in South America (São Paulo) | EC2 | skipped | Low | — |

**Worth revisiting:** Elastic Disaster Recovery preserving UEFI boot mode is the
classic silent-failure fix — servers that replicate fine and then fail to boot
after failover. Narrow audience, real pain.

**Event news for the weekly:** the 10 August AWS Weekly Roundup covers the AWS
Heroes Summit, plus Dogwood and Kiro Crew. First event news since the series
started — belongs in the Saturday roundup.

---

## 7 August 2026 — covered by post #6

A thin day: only five qualifying items. The winner was clear, but on a day like
this the held items above are worth re-reading before defaulting to the news.

| Item | Service | Status | Importance | Reference |
| --- | --- | --- | --- | --- |
| BGP route protection monitoring and delegated RPKI for BYOIP | VPC IPAM | **#6** | High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-vpc-ipam-bgp-rpki-byoip/) |
| One-click multi-Region for new organization instances | IAM Identity Center | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-iam-identity-center-supports-one-click-multi-region-option-new-organization-instances) |
| Backup and restore, on-demand and automated, incremental | Timestream for InfluxDB | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/07/timestream-influxdb-backup-restore/) |
| Cognito available as a skill in the Agent Toolkit for AWS | Cognito | open | Low-Med | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-auth-agent-skill/) |
| R8i and R8i-Flex in Europe (Milan) | EC2 | skipped | Low | — |

**Worth revisiting:** the IAM Identity Center one-click item pairs naturally with
the 29 July multi-Region directory item still open above — together they would
make a single stronger post on Identity Center resilience than either alone.

---

## 6 August 2026 — covered by post #5

| Item | Service | Status | Importance | Reference |
| --- | --- | --- | --- | --- |
| Fractional GPU scheduling on G6f, 0.125/0.25/0.5 | ECS | **#5** | High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-ecs-fractional-gpu/) |
| Direct read-only access to backup data via S3 Access Points | AWS Backup for S3 | **#8** | High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-backup-amazon-s3-direct-access/) |
| AgentCore runtime instances GA, sessions up to 14 days | Bedrock AgentCore | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-bedrock-agentcore-runtime-instances-generally-available/) |
| Temporal policies and per-user rate limiting | Bedrock AgentCore | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/temporal-policies-agentcore/) |
| Kafka Authorizer Logs — denied requests with client IP and API | MSK | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-msk-kafka-authorizer-logs/) |
| Storage volume initialization visibility after restore | RDS | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-rds-storage-volume-initialization-visibility) |
| Graviton4 M8g, R8g, C8gn nodes | ElastiCache | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-elasticache-graviton4-m8g-r8g-c8gn/) |
| Console-to-IDE integration for Kiro and Cursor | Lambda | open | Low-Med | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-lambda-ide-kiro-cursor/) |
| `isBotEvent` field distinguishes automated opens and clicks | SES | open | Low-Med | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-ses-automated-email-interactions/) |
| Post-launch actions automated via Systems Manager | AWS Transform | open | Low-Med | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-transform-for-migrations-automates-post-launch-actions) |
| Enhanced observability metrics | WorkSpaces, WorkSpaces Applications | skipped | Low | — |
| Schema Registry in ten more Regions; G7 in Spain; air-gapped vaults for Neptune | Glue, EC2, AWS Backup | skipped | Low | — |
| Net payment terms on private offers; Security Agent email MFA; Quick multi-dataset | Marketplace, Security Agent, Quick | skipped | Low | — |

**Worth revisiting:** AWS Backup for S3 direct access is the strongest held item
— reading backups through `GetObject` without a restore changes DR, audit and
forensic patterns, and it carries a subtle operational catch: while an access
point is active the recovery point is protected from deletion, which interacts
with vault lifecycle. Held only because it is in select Regions.

---

## 5 August 2026 — covered by post #4

| Item | Service | Status | Importance | Reference |
| --- | --- | --- | --- | --- |
| Real-time vector search, 4096 dims, `SearchVectors` | DynamoDB | **#4** | High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-dynamodb-vector-search) |
| Scalable network bandwidth, 625 Mbps at 2 GB to 3,000 Mbps at 10 GB | Lambda | open | High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-lambda-network-bandwidth/) |
| Serverless scales to 12 ACUs within a second, then to 256 | Aurora | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aurora-serverless-instant-12-acu-scaling) |
| Account access management optional for new org instances | IAM Identity Center | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-identity-center-accounts-optional/) |
| ETL anomaly detection now free, better predictions | Glue Data Quality | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-glue-data-quality-anomaly-detection-free) |
| AI Insights for pricing on listings | Marketplace | skipped | Low | — |
| Keyspaces in Canada West (Calgary) | Keyspaces | skipped | Low | — |

**Worth revisiting:** the Lambda bandwidth item has two sharp constraints the
headline hides — it applies only to functions **outside a VPC**, needs at least
2 GB of memory, and must be switched on per account via Service Quotas
("Network bandwidth per execution environment"). It is not automatic. That is a
strong post on its own, and a close second today.

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
| I7i in Thailand and Tel Aviv; GameLift Streams stream URLs; SageMaker Unified Studio Teradata connector; Transform Windows offline schema transformation; Context Ontology Accelerator | EC2, GameLift, SageMaker, AWS Transform | skipped | Low | — |

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
