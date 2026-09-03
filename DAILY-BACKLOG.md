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

## 2 September 2026 — covered by post #24

| Item | Service | Status | Importance | Reference |
| --- | --- | --- | --- | --- |
| SnapStart for container image functions — Java 11+, Python 3.12+, .NET 8+, images up to 10 GB; the packaging used by the functions with the heaviest init | Lambda | **#24** | High | [link](https://aws.amazon.com/about-aws/whats-new/2026/07/aws-lambda-snapstart-container/) |
| 60 new resource types recorded — an account recording all supported types picks these up automatically, with the cost that implies | Config | open | High | [link](https://aws.amazon.com/about-aws/whats-new/2026/09/aws-config-new-resource-types/) |
| Managing identity source transition for IAM Identity Center (Security Blog) — moving between identity sources without losing assignments | IAM Identity Center | open | Med-High | [link](https://aws.amazon.com/blogs/security/managing-identity-source-transition-for-aws-iam-identity-center/) |
| CVE-2026-84851 — uncontrolled recursion in the Ion reader, Amazon Ion-C before 1.1.6 | Ion-C | open | Medium | [link](https://aws.amazon.com/security/security-bulletins/rss/2026-094-aws/) |
| Agentic CX designer reaches GA | Connect Customer | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/09/agentic-cx-designer/) |
| Gateway Load Balancer TCP Reset to reduce traffic interruptions (Networking Blog) | Gateway Load Balancer | open | Medium | [link](https://aws.amazon.com/blogs/networking-and-content-delivery/reduce-traffic-interruptions-with-gateway-load-balancer-tcp-reset/) |
| Second-generation Outposts racks reach the GovCloud (US) Regions | Outposts | open | Low-Med | [link](https://aws.amazon.com/about-aws/whats-new/2026/09/aws-outposts-govcloud-us-regions/) |
| Tool settings and MCP sync for connectors; Unified Studio CI/CD notebook promotion; Web Search in GovCloud; UXC in all commercial Regions; Connect Malay evaluations; RDS SQL Server trace flags | Quick, SageMaker, Bedrock, Connect, RDS | skipped | Low | — |

**Worth revisiting:** the Config resource-type expansion is the strongest
unwritten item and connects directly to arch #40 and #41 — an account recording
all supported types starts recording 60 more without anyone deciding to, which
is the right default and a cost change nobody approved. Worth a post that puts a
number on it.

---

## 1 September 2026 — covered by post #23

| Item | Service | Status | Importance | Reference |
| --- | --- | --- | --- | --- |
| CVE-2026-83551 — HMAC signing key stored in cleartext in pipeline definitions, readable via `DescribePipeline`; a describe permission becomes code execution in another user's pipeline context. Fixed 3.11.0 / 2.256.0, and the fix needs a `pipeline.upsert()` per pipeline | SageMaker Python SDK | **#23** | High | [link](https://aws.amazon.com/security/security-bulletins/rss/2026-093-aws/) |
| Warm-up periods for alarms — delay evaluation for 1 to 2,880 minutes after creation, ending early once the evaluation window fills | CloudWatch | open | High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-cloudwatch-alarms-warmup-period) |
| Protecting more than 1,000 S3 buckets per account | AWS Backup | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/09/aws-backup-more-than-1000-s3-buckets/) |
| Dry run to validate API requests without executing them | Kinesis Data Streams | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/09/amazon-kinesis-data-streams-api/) |
| Database Insights extends to self-managed PostgreSQL on EC2 | CloudWatch | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/database-insights-self-managed-postgresql/) |
| Claude Fable 5.1 available on AWS | Bedrock | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/09/claude-fable-5-1-aws/) |
| MCP went stateless: is your MCP server deployment well-architected (Architecture Blog) | MCP / Well-Architected | open | Medium | [link](https://aws.amazon.com/blogs/architecture/mcp-went-stateless-is-your-aws-mcp-server-deployment-well-architected/) |
| Apache Airflow 3.3.1 | MWAA | open | Low-Med | [link](https://aws.amazon.com/about-aws/whats-new/2026/09/amazon-mwaa-apache-airflow-3-3-1/) |
| Custom apps from natural language; Deadline Cloud job bundle sharing; Connect dashboard compact mode; RDS Custom SQL Server CU and GDR | Quick, Deadline Cloud, Connect, RDS Custom | skipped | Low | — |

**Worth revisiting:** CloudWatch alarm warm-up periods is the strongest unwritten
item and is a genuinely good architecture topic — every team has worked around
alarms firing during startup by lengthening evaluation periods, which suppresses
false positives by trading away detection latency. A native warm-up separates
the two concerns, and the 1-to-2,880-minute range plus the early-exit default
are worth a proper post. It does not age.

---

## 31 August 2026 — covered by post #22

A heavy Monday: 19 announcements, the most in a single day since 19 August.

| Item | Service | Status | Importance | Reference |
| --- | --- | --- | --- | --- |
| GA — private governed catalog for agents, tools, skills and MCP servers; org-wide auto-detection, approval lifecycle, native MCP endpoint, 5 Regions | AWS Agent Registry | **#22** | High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-agent-registry-generally-available) |
| Agents and MCP servers from the registry surfaced in Amazon Quick — the consumer half of the item above | AWS Agent Registry | cited in #22 | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-agent-registry-agents-mcp-servers-quick/) |
| R9g and R9gd memory optimized instances on Graviton5 — a new processor generation, with its own News Blog post | EC2 | open | High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-ec2-r9g-and-r9gd-memory-optimized-instances-are-now-available/) |
| CVE-2026-83497 — unrestricted Java deserialization in the SQL plugin's cursor pagination; authenticated read/search is enough | OpenSearch | open | High | [link](https://aws.amazon.com/security/security-bulletins/rss/2026-092-aws/) |
| Multicloud connectivity with Microsoft Azure — **Preview** | AWS Interconnect | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-announces-AWS-interconnect-multicloud-microsoft-azure-preview/) |
| Machine-to-machine authorization without a user pool domain | Cognito | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-cognito-get-client-token/) |
| Apache Iceberg v3 tables | Redshift | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-redshift-supports-apache-iceberg-v3) |
| IAM Identity Center authentication with enhanced VPC routing | Redshift | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-redshift-supports-idc-evr) |
| Direct major version upgrades to 8.0 | DocumentDB | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/documentdb-major-version-upgrade-8-0/) |
| Cross-region routing of contacts across two active Regions | Connect Global Resiliency | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-connect-global-resiliency-cross-region-routing/) |
| Recursive loop detection now in all commercial Regions | Lambda | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/lambda-recursion-regions) |
| Workload Credentials Provider as a one-click install for Linux and Windows | AWS | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/workload-credentials-provider-install/) |
| Cluster Insights for faster diagnosis of cluster status | OpenSearch | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/opensearch-cluster-status-insight/) |
| AI Toolkit for custom remediations | Automated Security Response | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/automated-security-response-adds-AI-toolkit/) |
| Active Directory domain join for Windows Server environments | Elastic Beanstalk | open | Low-Med | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/elastic-beanstalk-active-directory-domain-join/) |
| Connector restart support | MSK Connect | open | Low-Med | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-msk-connect-restart/) |
| 30% better performance and smarter scaling in additional Regions | Aurora Serverless | open | Low-Med | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-aurora-serverless-performance-improvement-additional-regions/) |
| Timestream for InfluxDB in 8 more Regions; WorkSpaces Applications in 3 more; Partner Revenue Measurement user agent expansion | Timestream, WorkSpaces, Partner | skipped | Low | — |

**Worth revisiting:** the Graviton5 R9g launch is the strongest unwritten item and
does not age quickly — a new processor generation is worth a proper price and
performance post once the pricing pages settle. The OpenSearch CVE was ranked
High and deliberately not taken: post #21 was already a security bulletin, and
two consecutive CVE posts would make the series read as a vulnerability feed. It
is in the September weekly's action list instead, which is the right home for
"patch this" without a deep-dive.

Saturday 29 August produced one announcement (Kinesis Data Streams delivery to
general purpose S3 buckets) and Sunday 30 August none.

---

## 28 August 2026 — covered by post #21

| Item | Service | Status | Importance | Reference |
| --- | --- | --- | --- | --- |
| CVE-2026-81849 — path traversal in the `aws:downloadContent` plugin; restricted SendCommand callers write files as root. Affects 2.0.767.0–3.3.4364.0, fixed 3.3.4515.0, no workaround | amazon-ssm-agent | **#21** | High | [link](https://aws.amazon.com/security/security-bulletins/rss/2026-091-aws/) |
| CVE-2026-81838 — Zip Slip in awsdac 0.10–0.23, fixed 0.24; cited alongside #21 as the same defect class | awsdac | cited in #21 | Medium | [link](https://aws.amazon.com/security/security-bulletins/rss/2026-090-aws/) |
| Data perimeter extended to the Management Console with Private Access (Security Blog) | Console / VPC | open | High | [link](https://aws.amazon.com/blogs/security/extend-your-data-perimeter-to-the-aws-management-console-with-private-access/) |
| Fine-grained access control — per-user and per-tenant memory isolation through AgentCore Gateway, Cedar policies over 12 Memory operations | Bedrock AgentCore Memory | open | High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/agentcorememory-fine-grained-access-control) |
| Flexible namespace variables — the other half of the isolation story, same day | Bedrock AgentCore Memory | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/agentcorememory-flexible-namespaces) |
| CloudWatch agent adds journald log support | CloudWatch | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-cloudwatch-agent-journald/) |
| Aurora MySQL 3.13, compatible with MySQL 8.0.45, GA | Aurora | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-aurora-mysql-313-available/) |
| Detect stalled S3 live replication before it becomes a storage bill (Storage Blog) | S3 | open | Medium | [link](https://aws.amazon.com/blogs/storage/detect-stalled-amazon-s3-live-replication-to-prevent-unexpected-storage-costs/) |
| Continuous modernization pipeline with AWS Transform custom (DevOps Blog) | AWS Transform | open | Medium | [link](https://aws.amazon.com/blogs/devops/build-your-own-continuous-modernization-pipeline-with-aws-transform-custom/) |
| FedRAMP Class C scope | AWS Transform | open | Low-Med | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-transform-fedramp-class-c/) |
| Batch write and discover records in Feature Store; Multi-AZ HA with Inference Components (ML Blog) | SageMaker | skipped | Low-Med | — |
| C8gn in Paris; P6-B300 in additional Regions; Grok 4.6 on Bedrock in GovCloud; Decathlon Chronos-2 case study; Razor Group lakehouse case study | EC2, Bedrock, Big Data | skipped | Low | — |

**Worth revisiting:** the two AgentCore Memory items are one story — per-tenant
memory isolation, with namespaces as the shape and Cedar policies as the
enforcement — and should be written as a single post, not two. The Management
Console data perimeter item is the strongest unwritten security topic of the
day and does not age quickly.

---

## 27 August 2026 — covered by post #20

| Item | Service | Status | Importance | Reference |
| --- | --- | --- | --- | --- |
| Foreign key constraints on new and existing tables; NO ACTION/RESTRICT/CASCADE/SET NULL/SET DEFAULT, MATCH FULL/SIMPLE, deferrable | Aurora DSQL | **#20** | High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aurora-dsql-foreign-key-constraints/) |
| Recovery Plans for orchestrated application recovery — ordering and dependencies across waves | Elastic Disaster Recovery | open | High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/elastic-disaster-recovery-plans/) |
| Cross-Region and cross-account backup copy | FSx for NetApp ONTAP | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/fsx-ontap-cross-region-backup-copy/) |
| Cross-Region and cross-account backup support for FSx for NetApp ONTAP — the AWS Backup half of the pair above | AWS Backup | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-backup-amazon-fsx-netapp-cross-account-region/) |
| Streaming ingestion accepts 10MiB records from Kinesis Data Streams | Redshift | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/redshift-streaming-supports-kds-10mib-records) |
| Agent Toolkit for AWS integration for AI-assisted warehouse management | Redshift | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/redshift-agenttoolkit-for-ai-assisted-datawarehouse-mgmt) |
| Guardrails extended to tool interactions via the Strands Agents SDK (Security Blog) | Bedrock | open | Medium | [link](https://aws.amazon.com/blogs/security/extend-amazon-bedrock-guardrails-to-tool-interactions-using-the-strands-agents-sdk/) |
| Geospatial and variant types in Iceberg v3 on Glue 6.0 (Big Data Blog) | Glue | open | Medium | [link](https://aws.amazon.com/blogs/big-data/build-with-geospatial-and-variant-types-in-iceberg-v3-on-aws-glue-6-0/) |
| AgentCore expands to two new Regions | Bedrock | skipped | Low-Med | — |
| X8i in Milan and Spain; EVS adds i7i.metal-48xl; Connect Cape Town analytics and scheduling metric refresh; Cosmos3 and Muse-Glimmer/Qwen models on JumpStart | EC2, EVS, Connect, SageMaker | skipped | Low | — |

**Worth revisiting:** Elastic Disaster Recovery Recovery Plans is the strongest
unwritten item of the day — orchestrated, dependency-ordered recovery is a real
architecture topic and DR has had one post (#8, Route 53 ARC) in the whole
series. The two FSx/Backup items are one story told twice and should be written
as a single post on cross-account backup isolation, not as two.

---

## 26 August 2026 — covered by post #19

Six announcements, three of them Amazon Connect items or Region expansions.
A thin day; the top item still earned the slot on its own merits.

| Item | Service | Status | Importance | Reference |
| --- | --- | --- | --- | --- |
| `AdminDeleteSoftwareToken` — admin API to reset a user's TOTP MFA | Cognito | **#19** | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-cognito-totp-reset/) |
| Memory usage controls, automatic or user-defined | Mountpoint for S3 | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/mountpoint-for-S3-adds-memory-usage-controls) |
| Cross-Region backup copy and logically air-gapped vault for DocumentDB, nine more Regions | AWS Backup | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-backup-cross-region-air-gapped-docdb/) |
| Glue 5.1 in European Sovereign Cloud Region | Glue | open | Low-Med | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-glue-5-1-european-sovereign-cloud) |
| Unplanned shrinkage in agent schedules | Connect | skipped | Low | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-connect-customer-unplanned-shrinkage/) |
| Points-based scoring in performance evaluations | Connect | skipped | Low | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-connect-customer-points-based-scoring-evaluations/) |

**Why Cognito won a thin day.** The previous recovery path for a lost TOTP
device was recreating the account, so the gap being closed was unusually large
for a single API operation. The post's substance is not the operation though —
it is that the outcome branches. `AdminDeleteSoftwareToken` removes the software
token *and* the TOTP preference but leaves other registered factors intact, so
an account with SMS registered is silently downgraded rather than reset, and the
API returns an empty HTTP 200 either way.

**Mountpoint is the strongest held item from this day.** It would have broken a
run of three identity-adjacent posts (#17 EKS OIDC, #18 Lambda resource-based
policies, #19 Cognito MFA) and is worth a slot on a day the news is thinner
still.

**Non-announcement items worth noting from the same day's blogs**, held here
because they are AWS engineering posts rather than launches: in-place
ZooKeeper-to-KRaft cluster upgrades for MSK, break-glass access for EKS when
federated identity fails, and cross-service signal correlation for detecting
multi-stage attacks. None are announcements, so none belong in a weekly
inventory, but each is a viable deep-dive subject.

---

## 25 August 2026 — covered by post #18

Fourteen announcements plus 11 blog posts and one security bulletin. Tuesday's
news, and the only item that changes an architecture rather than a
configuration: Lambda functions accepting full IAM resource-based policies. The
announcement sells it as flexibility and omits the part that matters
operationally — `PutResourcePolicy` replaces the entire existing policy,
including every statement S3, EventBridge, SNS and API Gateway appended through
`AddPermission` when their triggers were configured.

| Item | Service | Status | Importance | Reference |
| --- | --- | --- | --- | --- |
| Full IAM resource-based policies on functions — Deny, multiple principals, all condition keys | Lambda | **#18** | High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-lambda-full-iam-resource-based-policies/) |
| Capacity Reservation Resource Groups accept Capacity Blocks and interruptible reservations | EC2 | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/capacity-reservation-resource-groups-ec2) |
| MicroVMs support PrivateLink | Lambda | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/lambda-microvms-supports-privatelink) |
| CVE-2026-78379 — consent bypass in Strands Agents Tools `python_repl` | Security bulletin | open | Med-High | [link](https://aws.amazon.com/security/security-bulletins/rss/2026-089-aws/) |
| Managed runtimes in public preview for Node.js 26 and Python 3.15 | Lambda | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-lambda-node-js-python-public-preview/) |
| Batch runs on ECS Managed Instances | Batch | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-batch-on-ecs-managed-instances/) |
| Java plugin for the AWS SDK | IAM Roles Anywhere | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/iam-roles-anywhere-java/) |
| Managed external secrets for Cisco Security Platform and Netskope | Secrets Manager | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/secrets-manager-cisco-netskope/) |
| Native InfluxDB routing for time-series data | IoT Core | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-iot-core-influxdb/) |
| Cross-cloud analytics with S3 Tables and BigQuery, parts 1 and 2 — part 2 is Lake Formation-based | Big Data blog | open | Medium | [link](https://aws.amazon.com/blogs/big-data/enable-cross-cloud-analytics-with-amazon-s3-tables-and-google-bigquery-part-2-access-control-with-lake-formation/) |
| Enhanced DDoS Protection | GameLift Servers | open | Low-Med | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-gamelift-servers-enhanced-ddos-protection) |
| Customer profile updates on open cases | Connect | skipped | Low | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-connect-cases-flexible-profiles/) |
| PostgreSQL 18.6/17.11/16.15/15.19/14.24; latest SQL Server CU; Oracle July 2026 RU | RDS | skipped | Low | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-rds-postgresql-18-6-17-11-16-15-15-19-14-24/) |
| M8i and M8i-flex in Canada West (Calgary) | EC2 | skipped | Low | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/ec2-m8i-m8i-flex-canada-west/) |

**Worth revisiting:** the Capacity Reservation Resource Groups change is the
strongest held item from this day. Mixing Capacity Blocks for ML, interruptible
ODCRs and standard ODCRs in one group with a prioritisation order and automatic
fallback to On-Demand is a real capacity-planning pattern, and the announcement
does not explain what happens at the boundaries between reservation types.

---

## 24 August 2026 — covered by post #17

Nine announcements plus 12 blog posts. Monday's news, and a genuinely
architectural winner: EKS lifting the one-external-OIDC-provider-per-cluster
limit to ten. The announcement omits all three of the things that decide how you
plan it — a Kubernetes 1.32 floor, a 12 KB configuration budget shared by all
ten providers, and the fact that `usernamePrefix` stops being cosmetic the
moment a second directory exists.

The version floor turned out to be smaller than it reads. Checked against the
release calendar, 1.31 is the only still-runnable version excluded, and its
extended support ends 26 November 2026 — so the gate is a deadline the estate
already had.

| Item | Service | Status | Importance | Reference |
| --- | --- | --- | --- | --- |
| Multiple external OIDC identity providers per cluster, up to 10 | EKS | **#17** | High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-eks-multiple-oidc-providers) |
| Automatic detection and repair of container instances with impaired agent connectivity | ECS | open | High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-ecs-agent-connectivity-health) |
| Shared DNS views for multi-account environments with Route 53 Global Resolver | Route 53 | open | Med-High | [link](https://aws.amazon.com/blogs/networking-and-content-delivery/shared-dns-views-for-multi-account-environments-with-amazon-route-53-global-resolver/) |
| CloudFront Functions unified logging | CloudFront | open | Medium | [link](https://aws.amazon.com/blogs/networking-and-content-delivery/cloudfront-functions-unified-logging/) |
| MLflow now supports customer managed keys | SageMaker | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/sagemaker-mlflow-custom-keys) |
| Preserving RAM shares and Lake Formation permissions through an Organizations migration | AWS Organizations | open | Medium | [link](https://aws.amazon.com/blogs/architecture/how-a-global-payment-processor-preserved-aws-ram-shares-and-lake-formation-permissions-during-an-aws-organizations-migration/) |
| PostgreSQL 18.4, 17.10, 16.14, 15.18 and 14.23 | Aurora | skipped | Low-Med | Minor version support |
| Enhanced support for Ray | SageMaker HyperPod | skipped | Low-Med | Narrow audience |
| GPT-5.6 Terra and Luna in GovCloud (US) | Bedrock | skipped | Low | Region expansion |
| MySQL minor version 8.4.11; ParallelCluster 3.16 on-node diagnostics; Connect information extraction | RDS, ParallelCluster, Connect | skipped | Low | — |

**Worth revisiting:** the ECS agent-connectivity repair item is the strongest
held candidate from this day. An instance whose agent has lost connectivity but
whose EC2 status checks still pass is the classic ECS failure that looks healthy
from every direction except the one that matters, and automatic remediation of
it is worth a post on its own. Route 53 Global Resolver shared DNS views is the
other: multi-account DNS is solved badly almost everywhere.

---

## 21 August 2026 — covered by post #16

A thin day: six announcements plus 15 blog posts, with one clear winner. Three
security bulletins, against the 85 the feed reported for 20 August — which
confirms that count was the feed-generation-timestamp artifact and not a real
day of bulletins.

Glue 6.0 was chosen on merit, and the migration guide turned out to contradict
the launch post in two useful ways: Python is 3.13 rather than 3.12, and the
Iceberg v3 headline is narrower than announced — Athena cannot read v3 tables
at all.

| Item | Service | Status | Importance | Reference |
| --- | --- | --- | --- | --- |
| 6.0 GA — Spark 4.1.1, Iceberg v3, 30% price reduction | Glue | **#16** | High | [link](https://aws.amazon.com/blogs/aws/aws-glue-6-0-now-available-with-30-lower-price-and-full-apache-iceberg-v3-support/) |
| Reduced pricing for OpenAI GPT-5.6 Sol | Bedrock | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/bedrock-openai-gpt-56-sol-reduced-pricing/) |
| Argo CD capability now supports custom configuration | EKS | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-eks-argo-cd-configuration) |
| Open and click tracking override parameters | SES | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-ses-adds-open-click-tracking-override/) |
| Client-side network failure visibility with NEL | CloudFront | open | Medium | [link](https://aws.amazon.com/blogs/networking-and-content-delivery/gain-visibility-into-client-side-network-failures-with-nel/) |
| Managers can chat with their data | Connect | skipped | Low-Med | Feature announcement |
| Automatic download status tracking in Monitor | Deadline Cloud | skipped | Low | Narrow |

**Worth revisiting:** SES open and click tracking overrides. Link rewriting for
click tracking breaks more transactional mail than people expect — it changes
the URL a recipient sees, and per-message control over it is the kind of thing
teams have previously solved by running a second configuration set. NEL is the
other one worth a look: client-side failures are the errors that never reach
your logs at all, which makes them the ones nobody has numbers for.

---

## 20 August 2026 — covered by post #15

Twelve announcements plus 15 blog posts. The held Network Firewall item from
17 August finally became writable: AWS published a Security Blog post for it,
which is the documentation whose absence blocked it three days ago.

A note on the feed: `fetch_week.py` reported 85 security bulletins dated
20 August. That is the feed-generation-timestamp artifact — the bulletins feed
stamps every entry with the fetch time rather than its publication date, the
same fault documented for the GCP bulletins feed. Those were excluded from the
ranking and should be excluded from the weekly inventory too.

| Item | Service | Status | Importance | Reference |
| --- | --- | --- | --- | --- |
| Rule hit count — on by default, free, all Regions except UAE and Bahrain | Network Firewall | **#15** | High | [link](https://aws.amazon.com/blogs/security/aws-network-firewall-now-supports-rule-hit-count/) |
| Inbound prefix controls and higher prefix scale | Direct Connect | open | High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-direct-connect-new-prefix-controls) |
| Certificate authority (CA) rotation with automated lifecycle management | EKS | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-eks-certificate-authority-ca-rotation-automated-lifecycle-management) |
| Origin Access Control for S3 Multi-Region Access Points | CloudFront | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-cloudfront-oac-s3-mrap) |
| RDS Switchover Read Replica execution block | ARC Region switch | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/region-switch-rds-switchover-execution-block/) |
| Default SSM parameter now tracks the latest kernel | Amazon Linux | open | Medium | [link](https://aws.amazon.com/blogs/compute/amazon-linux-default-ssm-parameter-will-now-track-the-latest-kernel/) |
| Customer managed keys | Timestream for InfluxDB | open | Low-Med | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-timestream-influxdb-cmk/) |
| Long-term system table retention with S3 Tables | Redshift | open | Low-Med | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/redshift-long-term-system-table-retention/) |
| New Local Zone in Las Vegas, Nevada | Local Zones | skipped | Low | Footprint expansion |
| C8gd/M8gd/R8gd and P6-B300 in additional Regions | EC2 | skipped | Low | Region expansions |
| Category-based notifications, multi-channel delivery for partners | Marketplace | skipped | Low | Partner tooling |
| Partner Central agents MCP Server supports OAuth with AWS Sign-In | Partner Central | skipped | Low | Partner tooling |

**Worth revisiting:** Direct Connect inbound prefix controls is now the
strongest held item. Prefix limits are a constraint people actually hit on
hybrid designs, and a control that filters what a customer gateway can
advertise changes who can break your routing. The Amazon Linux SSM parameter
change is quieter but sharper than it looks — it changes behaviour under
automation that nobody will re-read.

---

## 19 August 2026 — covered by post #14

Sixteen announcements, no security bulletins, 14 blog posts. Third IAM item in
four days: role manager, Policy Autopilot, and now the managed-policy quota.

| Item | Service | Status | Importance | Reference |
| --- | --- | --- | --- | --- |
| Managed policies per role: 20 by default, 25 max; users and groups unchanged | IAM | **#14** | High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-iam-quota-increase/) |
| Cost Anomaly Detection supports third-party models on Bedrock | Cost Management | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-cost-anomaly-detection-bedrock-3P/) |
| Trusted identity propagation for notebooks | SageMaker | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-sagemaker/) |
| FIPS-compliant private connectivity for Tape and Volume Gateway | Storage Gateway | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/storage-gateway-fips-privatelink/) |
| Log group tag propagation in centralization | CloudWatch | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-cloudwatch-centralization-tag-propogation/) |
| GeoIP, RDS and XML processors for pipelines | CloudWatch | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/cloudwatch-geoip-rds-xml/) |
| External Web Access for Web Search | Bedrock | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-bedrock-web-access-web-search/) |
| New Availability Zone in Europe (London) | AWS Global | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-new-availability-zone-europe/) |
| Deny by default for custom permissions | Amazon Quick | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-quick-deny-by-default/) |
| Marketplace support for Lightsail | Marketplace | open | Low-Med | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-marketplace-launch-ami-amazon-lightsail) |
| Web Search domain and date filtering, Europe and Asia Pacific | Bedrock AgentCore | skipped | Low-Med | incremental |
| In-console monitoring | WorkSpaces Applications | skipped | Low-Med | — |
| Lambda MicroVMs +5 Regions; R8a Taipei; OpenSearch Ingestion GovCloud; Grok 4.6 | various | skipped | Low | Region and catalogue expansions |

**Worth revisiting:** Storage Gateway FIPS over PrivateLink is the strongest held
item. Narrow audience, but FIPS plus private connectivity is a combination
regulated environments actively wait for, and it is rarely written about.

---

## 18 August 2026 — covered by post #13

Eleven announcements, two security bulletins, ~14 blog posts. Second IAM item in
two days: Monday gave role manager creating roles, Tuesday gives a tool that
derives policy from a Terraform plan.

| Item | Service | Status | Importance | Reference |
| --- | --- | --- | --- | --- |
| Policy Autopilot accepts Terraform plan files, scoped to the plan's CRUD functions | IAM | **#13** | High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/iam-policy-autopilot-now-supports-terraform-plan-files) |
| AgentCore payments reaches GA | Bedrock AgentCore | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/bedrock-agentcore-payments-ga/) |
| Supply Chain Security added as the tenth category | Security Hub Extended | open | Med-High | [link](https://aws.amazon.com/blogs/security/security-hub-extended-adds-supply-chain-security-as-its-tenth-category/) |
| CVE-2026-75935 / 75936 — memory-amplification denial of service in ion-java | Amazon ion-java | open | Med-High | [link](https://aws.amazon.com/security/security-bulletins/rss/2026-083-aws/) |
| Identity federation to external services in European Sovereign Cloud | IAM | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-iam-european-sovereign-cloud/) |
| CVE-2026-75897 — uncontrolled resource consumption, OpenSearch Dashboards | OpenSearch | open | Medium | [link](https://aws.amazon.com/security/security-bulletins/rss/2026-082-aws/) |
| Nested virtualization | WorkSpaces | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/nested-virtualization-workspaces/) |
| August critical security patch updates | Corretto | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-corretto-august-2026-security-updates) |
| PythonOperator and BashOperator support | MWAA Serverless | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/mwaa-serverless-pythonoperator-bashoperator/) |
| Data profiling and anomaly detection | SageMaker Unified Studio | open | Low-Med | [link](https://aws.amazon.com/about-aws/whats-new/2026/05/smus-data-profiling) |
| PostgreSQL 19 Beta 3 in the preview environment | RDS | skipped | Low-Med | beta, preview environment |
| R8i in Israel (Tel Aviv); S3 Metadata in GovCloud; Bedrock OpenAI in India | EC2, S3, Bedrock | skipped | Low | Region expansions |

**Worth revisiting:** the ion-java CVEs. Ion is embedded in more AWS SDK paths
than most teams realise, so "do we even use this?" is a real question and a
short post could answer it usefully.

---

## 17 August 2026 — covered by post #12

Ten announcements plus 14 blog posts. The strongest item could not be written:
Network Firewall stateful rule hit counts has no documentation yet — the
CloudWatch metrics page lists no such metric and four candidate doc URLs
redirect — so post #12 took the sign-in change instead.

| Item | Service | Status | Importance | Reference |
| --- | --- | --- | --- | --- |
| Stateful rule hit counts — enabled by default, all Regions except UAE and Bahrain | Network Firewall | **#15** (20 Aug, once documented) | High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-network-firewall-stateful-rule-hit-counts/) |
| Redesigned sign-in: email entry point, third-party providers, session page | AWS Sign-In | **#12** | Med-High | [link](https://aws.amazon.com/blogs/security/updates-to-your-aws-sign-in-experience/) |
| Batch instance termination | EC2 Auto Scaling | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-ec2-auto-scaling-batch-termination) |
| Cross-Region Inferencing for OpenAI models, expanded API support | Bedrock | open | Med-High | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-bedrock-cross-region-openai-v2/) |
| Custom domain names for Provisioned clusters | MSK | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/17/amazon-msk-custom-domain-names/) |
| Automatic semantic enrichment for VPC domains | OpenSearch | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-opensearch-service-vpc/) |
| Replication rules per registry raised to 25 | ECR | open | Medium | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-ecr-increased-replication-rules-limit) |
| Built-in visual file editor | CloudShell | open | Low-Med | [link](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-cloudshell-visual-file-editor/) |
| Routing steps and agent proficiency reporting | Connect | skipped | Low-Med | — |
| R8i and R8i-Flex in Canada West; Quick M365 extensions GA | EC2, Quick | skipped | Low | Region and GA expansions |

**Worth revisiting:** ~~Network Firewall hit counts~~ — **written as post #15
on 21 August**, once AWS published a Security Blog post for it. Holding it for
three days was correct: the announcement alone could not be verified, and the
documentation turned out to contain the part that mattered — hit counts derive
from alert logs, so pass rules and stateless rules report zero while fully
live. Writing it on the announcement would have produced a post recommending
exactly the deletion that breaks production.

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
