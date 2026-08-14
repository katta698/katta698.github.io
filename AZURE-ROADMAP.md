# Azure Architecture Series — roadmap

Written 2026-08-14, before post #1. The numbering below is a decision made once:
post numbers appear in published URLs, in the sidebar progress widget and in
readers' localStorage read-lists, so **#12 cannot be inserted between #11 and #12
later**. The AWS series grew organically and now has gaps that are awkward to
backfill; this file exists so this one does not.

Revising the *content* of an unwritten number is expected and fine. Renumbering a
published post is not.

## Conventions

| | Value |
| --- | --- |
| Source file | `posts/az-NNN-short-topic.html` |
| Slug | `azure-architecture-<short-topic>` |
| Served page | `blog/azure-architecture-<short-topic>/index.html` |
| Labels | `[Azure, "Azure Architecture Series"]` — exact, every post |
| Title | `Azure Architecture Series #N — <Topic>` (em dash) — same shape as the AWS series |
| Diagram | `blog/assets/diagrams/az-NNN-<topic>.svg` |
| Reference heading | `Official Azure Reference` |

The slug prefix `azure-architecture-` contains no `week-<digits>`, so it cannot
be picked up by `_week_num()` in `sync_blog.py`.

Pages are **custom-built** from `_templates/arch-post-template.html`, like the
AWS arch series — `az-` is in the `externally_built` tuple in `sync_blog.py`, so
sync never overwrites them. It only updates their cards on `blog/index.html` and
re-stamps their `?v=` asset tokens.

Verification hosts for this series are `learn.microsoft.com` and
`azure.microsoft.com` (`doc_hosts` on the `az` entry in
`scripts/validate_arch_post.py`). Measured 2026-08-14, both return an honest
HTTP 404 for a missing page, so `--check-links` judges them on status code and
declares no `shell_hosts` — the body-size heuristic is a property of
`docs.aws.amazon.com` and does not transfer.

Everything else carries over unchanged from `CLAUDE.md`: every printed figure
needs a `verified_claim`, derived figures carry `derive:`/`expect:`, diagrams are
standalone SVG files, no process commentary, and
`python scripts/validate_arch_post.py --series az` must report 0 errors.

## Phase 1 — Foundations (#1–#8)

The account model and the things every later post assumes.

| # | Topic | The decision the post is really about |
| --- | --- | --- |
| 1 | Tenants, management groups, subscriptions and resource groups | Where the blast radius boundary actually sits, and why subscription is not the unit people assume |
| 2 | Entra ID as the identity plane | Tenant vs directory vs subscription, and what "one tenant, many subscriptions" costs |
| 3 | RBAC, scope inheritance and custom roles | Why role assignment scope beats role definition in almost every design |
| 4 | Azure Policy and initiatives | Guardrails that prevent vs guardrails that report, and what `deny` breaks |
| 5 | Landing zones and the Cloud Adoption Framework | What the accelerator actually deploys, and which parts to keep |
| 6 | Resource naming, tagging and cost allocation | Tags as the only workable chargeback key, and where they do not propagate |
| 7 | Regions, availability zones and paired regions | What a paired region guarantees and what it does not |
| 8 | ARM, Bicep and Terraform on Azure | Why the resource-provider model shapes all three, and what drift means here |

## Phase 2 — Networking (#9–#17)

| # | Topic | The decision |
| --- | --- | --- |
| 9 | VNets, subnets and address planning | Why Azure reserves five addresses per subnet, and sizing you cannot change later |
| 10 | Network Security Groups and Application Security Groups | Rule evaluation order, and the default rules people forget exist |
| 11 | VNet peering vs VPN vs ExpressRoute | The three ways to join networks, priced and compared |
| 12 | Hub-and-spoke topology | Why the hub exists, and what forced tunnelling does to it |
| 13 | Azure Virtual WAN | When the managed hub beats the one you built in #12 |
| 14 | Private Endpoints and Private Link | The DNS problem that makes or breaks every private-endpoint design |
| 15 | Azure DNS, private zones and resolution | Conditional forwarding, and why hybrid DNS is the recurring outage |
| 16 | Load Balancer, Application Gateway, Front Door and Traffic Manager | Four products, one question: which layer are you balancing at |
| 17 | Azure Firewall and network segmentation | Where the firewall belongs, and what it costs to route everything through it |

## Phase 3 — Compute (#18–#25)

| # | Topic | The decision |
| --- | --- | --- |
| 18 | Virtual machines, series and sizing | How the series letters map to real hardware, and the sizing mistake that recurs |
| 19 | Scale sets, flexible orchestration and autoscale | Why flexible replaced uniform, and what a scaling rule really measures |
| 20 | Reservations, savings plans and spot | Committed-spend arithmetic, break-evens shown |
| 21 | App Service and its plans | The shared-plan trap, and where scaling is actually configured |
| 22 | Azure Functions hosting models | Consumption vs Premium vs Dedicated, cold starts and the real cost curve |
| 23 | Container Apps vs AKS | The line where managed stops being enough |
| 24 | AKS architecture | Node pools, CNI choice, and the networking decision made at cluster creation and never again |
| 25 | Availability sets, zones and update domains | What each protects against, and what neither does |

## Phase 4 — Data and storage (#26–#34)

| # | Topic | The decision |
| --- | --- | --- |
| 26 | Storage accounts, redundancy and access tiers | LRS/ZRS/GRS/GZRS priced against the failure each survives |
| 27 | Blob lifecycle management and rehydration | Where archive saves money and where retrieval erases the saving |
| 28 | Managed disks, tiers and performance | Bursting, and why the disk is usually the bottleneck people blame on the VM |
| 29 | Azure Files and NetApp Files | The two ways to do SMB/NFS, and what each costs at scale |
| 30 | Azure SQL Database, Managed Instance and SQL on VM | What you give up at each step toward managed |
| 31 | DTU vs vCore, serverless and elastic pools | The purchasing-model choice, with the arithmetic |
| 32 | Cosmos DB partitioning and consistency | Partition key as the decision you cannot revisit; five consistency levels priced |
| 33 | PostgreSQL and MySQL flexible servers | HA modes, and what a zone-redundant failover actually does to connections |
| 34 | Data platform: Data Factory, Synapse, Fabric | Which one, and what "Fabric replaces it" means in practice |

## Phase 5 — Security and governance (#35–#42)

| # | Topic | The decision |
| --- | --- | --- |
| 35 | Managed identities, system vs user-assigned | Why user-assigned is the default for anything that redeploys |
| 36 | Key Vault, RBAC vs access policies, and HSM tiers | The permission-model migration, and what soft-delete guarantees |
| 37 | Conditional Access and PIM | Standing access as the thing to eliminate, and the break-glass account |
| 38 | Microsoft Defender for Cloud | What the plans cost per resource, and what free tier really gives |
| 39 | Microsoft Sentinel and log ingestion cost | The pricing model that decides your logging architecture |
| 40 | Encryption: platform keys, customer-managed keys, double encryption | What CMK buys, and the key-rotation failure mode |
| 41 | Confidential computing and data protection boundaries | When the hardware boundary is worth its constraints |
| 42 | Compliance, Blueprints' retirement and Deployment Stacks | The current answer for governed, repeatable deployment |

## Phase 6 — Operations and reliability (#43–#50)

| # | Topic | The decision |
| --- | --- | --- |
| 43 | Azure Monitor, metrics, logs and workspaces | Workspace design, retention tiers, and where the bill comes from |
| 44 | Log Analytics query and data collection rules | What DCRs changed, and filtering at the agent |
| 45 | Alerts, action groups and alert processing rules | Alert fatigue as an architecture problem |
| 46 | Backup and Site Recovery | RPO/RTO stated honestly, with what each product actually guarantees |
| 47 | Business continuity across regions | Active-active vs active-passive on Azure, priced |
| 48 | Resource Health, Service Health and the SLA | Composite SLA arithmetic across a real multi-service application |
| 49 | Cost management, budgets and the FinOps loop | Where Azure's cost data lags, and what to do about it |
| 50 | Well-Architected Framework review in practice | The five pillars applied to one of the architectures built earlier in this series |

## Phase 7 — Advanced and cross-cutting (#51+)

Deliberately open-ended. These are numbered as they are written, in whatever
order the material justifies:

- Azure Arc and hybrid resource governance
- Azure Local (formerly Azure Stack HCI)
- Multi-tenant SaaS architecture on Azure
- Event-driven architecture: Event Grid, Event Hubs, Service Bus compared
- API Management: tiers, self-hosted gateway, and the VNet decision
- Azure OpenAI: quota, PTU vs pay-as-you-go, and data boundaries
- AI Foundry and grounding architectures
- Migration: Azure Migrate, the assessment, and the seven Rs on Azure
- Landing zone at scale: multi-subscription platform operations
- Cross-cloud: AWS ↔ Azure connectivity and identity federation

## This series is not an AWS comparison

Azure is explained on its own terms, from first principles. There is no running
translation table, no "the AWS equivalent is", and no assumption that the reader
knows AWS at all — a reader who has never opened an AWS console should lose
nothing.

A comparison is allowed only where the Azure design is genuinely unintelligible
without it, and it earns its place sentence by sentence. In practice that should
be rare. Cross-cloud connectivity and identity federation, in Phase 7, is the one
topic where both clouds are the subject.

## Notes on sequencing

- **#1–#8 must ship in order.** Everything later assumes the scope model from #1
  and the RBAC model from #3.
- Within a phase, order is a preference, not a dependency, except where a post
  names an earlier one.
- **A post may be moved forward only into an unpublished number.** If a topic
  turns out to be thin, replace that number's topic; do not renumber around it.
- Every post carries a diagram. If a topic does not produce a diagram worth
  drawing, that is a signal the topic is too small to be its own number.
