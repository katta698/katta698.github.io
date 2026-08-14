# GCP Architecture Series — roadmap

Written 2026-08-14, before post #1. The numbering below is a decision made once:
post numbers appear in published URLs, in the sidebar progress widget and in
readers' localStorage read-lists, so **#12 cannot be inserted between #11 and #12
later**. The AWS series grew organically and now has gaps that are awkward to
backfill; this file, like `AZURE-ROADMAP.md`, exists so this one does not.

Revising the *content* of an unwritten number is expected and fine. Renumbering a
published post is not.

## The learning arc this series is

The AWS series was written from years of production experience. This one is not:
it starts from no Google Cloud experience at all, and the curriculum below is
built to end, within a year, at the level the AWS series is written from.

That changes how the posts get written, not what they claim.

- **Cadence is daily, on weekdays.** Starting Friday 14 August 2026, #1–#52 runs
  to **Monday 26 October 2026** — the numbered curriculum is done inside three
  months, not twelve.
- **Every figure is verified against `cloud.google.com` before publishing.** This
  matters more here, not less. There is no experience to fall back on, so the
  badge and its `verified_claims` are the only thing standing between a reader
  and a confidently-worded guess. A post whose figures were not personally
  checked gets no badge — see `CLAUDE.md`.
- **Derived figures carry their arithmetic** (`derive:` / `expect:`). Break-evens
  and effective rates are where every error in the AWS series actually happened,
  and that was with experience behind them.
- **Build it before writing it.** Each post's architecture should exist in a real
  project first. A post describing a console flow nobody walked is where the
  wrong details come from, and they are the details readers notice.
- **Order is not optional early on.** #1–#9 are prerequisites for everything
  after them, and are also the topics where GCP differs most from what AWS
  experience would lead you to assume. Read the roadmap's phase-1 entries as the
  unlearning list.

### Where the year actually goes

The goal is expert-level in a year, and a daily cadence does not deliver that by
finishing sooner — it delivers a complete *map* sooner. Roughly:

| Window | What it is |
| --- | --- |
| Weeks 1–11 (#1–#52) | The map. Every major service placed, with its real constraints and its real prices |
| Months 4–12 (#53+) | The depth. Phase 7 continues daily, and this is the part that produces expertise |

Phase 7 is deliberately open-ended for exactly this reason. It is not a leftovers
list; it is where the second three-quarters of the year lives, and it should grow
as the earlier phases turn up things worth their own post.

Slipping is fine. Reordering within a phase is fine. Renumbering is not.

### What daily costs, stated plainly

A post a day, on material being learned from scratch, against a badge that
asserts every printed figure was personally checked against `cloud.google.com`,
is the tightest constraint on this site. It is worth naming before it bites:

- **The badge is the thing that must not bend.** If a day's checking did not
  happen, the post ships with no `verified:` and no figures — not with a badge
  and a hopeful number. `CLAUDE.md` already says this; a daily cadence is the
  condition under which it gets tested.
- **A thin post beats a padded one.** Some of these topics are not a day's
  writing. Publishing a short, correct post is better than reaching for detail
  that was not verified.
- **The build-it-first rule is the first thing daily pressure will break.** It is
  also the rule that catches the errors nothing else catches.

## Conventions

| | Value |
| --- | --- |
| Source file | `posts/gcp-NNN-short-topic.html` |
| Slug | `gcp-architecture-<short-topic>` |
| Served page | `blog/gcp-architecture-<short-topic>/index.html` |
| Labels | `[GCP, "GCP Architecture Series"]` — exact, every post |
| Title | `GCP Architecture Series #N — <Topic>` (em dash) — same shape as the AWS and Azure series |
| Diagram | `blog/assets/diagrams/gcp-NNN-<topic>.svg` |
| Reference heading | `Official Google Cloud Reference` |

The label string is what the filter pill, the sidebar progress widget and the
card accent all match on, literally. The accent (`.cloud-gcp`, olive sage) is
already in `blog/assets/blog.css` and is applied by `CLOUD_BY_LABEL` in
`build_index_page()` — use the exact label and it appears by itself. Do not add
CSS for it.

The slug prefix `gcp-architecture-` contains no `week-<digits>`, so it cannot be
picked up by `_week_num()` in `sync_blog.py`.

Pages are **custom-built** from `_templates/arch-post-template.html`, like the AWS
and Azure arch series — `gcp-` is in the `externally_built` tuple in
`sync_blog.py`, so sync never overwrites them. It only updates their cards on
`blog/index.html` and re-stamps their `?v=` asset tokens. Build with
`scripts/build_arch_post.py`, which rewrites the template's AWS literals for this
series via `CLOUD_SERIES`.

Verification hosts for this series are `cloud.google.com` and
`docs.cloud.google.com` (`doc_hosts` on the `gcp` entry in
`scripts/validate_arch_post.py`).

**Cite `docs.cloud.google.com`.** Measured 2026-08-14 while verifying #1,
`cloud.google.com/*/docs/*` answers 301 Moved Permanently to
`docs.cloud.google.com` — that is where the documentation now lives, and it is
the URL a reader lands on. Marketing and pricing pages stay on
`cloud.google.com`, so both hosts are allowed, but a docs claim pointed at the
old host is citing a redirect.

Measured the same day against two known-bad URLs on each host, both return an
honest HTTP 404, so `--check-links` judges them on status code and the series
declares no `shell_hosts` — the body-size heuristic is a property of
`docs.aws.amazon.com` and does not transfer.

`python scripts/validate_arch_post.py --series gcp` must report 0 errors before
publishing.

## Phase 1 — Foundations (#1–#9)

The resource model and the things every later post assumes. These are also the
posts where an AWS reader's instincts are most likely to be wrong.

| # | Topic | The decision the post is really about |
| --- | --- | --- |
| 1 | Organization, folders, projects and resources | Why the project — not the account — is the unit of isolation, billing and quota, and where the blast radius really sits |
| 2 | Cloud Identity, Workspace and what a principal is | Where identity comes from before any of it reaches Google Cloud, and why that is a separate product |
| 3 | IAM: allow policies, deny policies, roles and inheritance | Inheritance down the hierarchy as the thing that grants access nobody meant to grant |
| 4 | Service accounts, impersonation and the keyless default | Why a downloaded key is the failure, and what impersonation replaces it with |
| 5 | Organization Policy Service and constraints | Guardrails that prevent, as distinct from IAM, which permits — two systems people conflate |
| 6 | Landing zones and the enterprise foundations blueprint | What the blueprint actually deploys, and which parts survive contact with a real org |
| 7 | Labels, billing accounts and cost allocation | Labels as the only workable chargeback key, where they do not propagate, and billing export as the real source of truth |
| 8 | Regions, zones and the global/regional/zonal property | Every resource has a location scope, and it is the property that decides most later designs |
| 9 | Terraform, Infrastructure Manager and Config Connector | Why Terraform is the default here, what Deployment Manager's retirement changed, and what drift means |

## Phase 2 — Networking (#10–#18)

The phase with the largest genuine divergence from other clouds: the VPC is
global.

| # | Topic | The decision |
| --- | --- | --- |
| 10 | VPC, global scope, regional subnets and IP planning | A global network with regional subnets, and the address sizing you cannot change later |
| 11 | Firewall rules and hierarchical firewall policies | Evaluation order, priorities, and targeting by service account rather than by tag |
| 12 | Shared VPC, VPC Peering and Network Connectivity Center | Three ways to join networks, and why Shared VPC is the org-scale answer |
| 13 | Cloud VPN and Cloud Interconnect | Dedicated vs Partner, and what each guarantees |
| 14 | Hub-and-spoke, Cloud Router and dynamic routing mode | Why regional vs global dynamic routing is the setting that breaks hybrid connectivity |
| 15 | Private Google Access and Private Service Connect | Reaching Google APIs without public egress, and the DNS problem underneath it |
| 16 | Cloud DNS, private zones and hybrid resolution | Inbound and outbound forwarding, and why hybrid DNS is the recurring outage |
| 17 | Cloud Load Balancing and network tiers | Which layer you are balancing at, global vs regional, and what Premium tier is actually buying |
| 18 | Cloud NAT, Cloud Armor and the edge | Egress without public IPs, and where request filtering belongs |

## Phase 3 — Compute (#19–#26)

| # | Topic | The decision |
| --- | --- | --- |
| 19 | Compute Engine machine families and custom machine types | How the families map to real hardware, and when a custom shape beats a predefined one |
| 20 | Managed instance groups, templates and autoscaling | What a scaling signal really measures, and what a rolling update does to it |
| 21 | Sustained use discounts, CUDs and Spot VMs | The discount model that has no equivalent elsewhere, with the arithmetic shown |
| 22 | Cloud Run | The default landing place for a container, and where its request model stops fitting |
| 23 | Cloud Run functions and event-driven compute | Eventarc, triggers, and the cold-start question answered honestly |
| 24 | GKE Standard vs Autopilot | Where you stop paying for nodes and start paying for pods, and what you give up |
| 25 | GKE networking and IP planning | VPC-native clusters, secondary ranges, and the sizing decision made at creation and never again |
| 26 | App Engine, Batch and the older runtimes | What still belongs there, and what is inertia |

## Phase 4 — Data and storage (#27–#36)

| # | Topic | The decision |
| --- | --- | --- |
| 27 | Cloud Storage classes, Autoclass and lifecycle | Where colder tiers save money and where retrieval and early-deletion erase the saving |
| 28 | Persistent Disk, Hyperdisk and Local SSD | Provisioned IOPS as a separate decision from capacity, and the disk as the usual bottleneck |
| 29 | Filestore and shared filesystems | The tiers, and what NFS costs at scale |
| 30 | Cloud SQL: HA, replicas and maintenance | What a failover actually does to open connections |
| 31 | AlloyDB | What it adds over Cloud SQL for Postgres, and what it costs to find out |
| 32 | Spanner | Splits, the primary-key decision you cannot revisit, and what external consistency is priced at |
| 33 | Bigtable and Firestore | Two NoSQL answers to two different questions, and the row-key/index decisions behind each |
| 34 | BigQuery architecture | Storage and compute separated, partitioning and clustering as the whole performance story |
| 35 | BigQuery pricing: on-demand vs Editions | The purchasing-model choice, with the break-even arithmetic |
| 36 | Pub/Sub and Dataflow | The streaming path, delivery guarantees, and where the bill comes from |

## Phase 5 — Security and governance (#37–#44)

| # | Topic | The decision |
| --- | --- | --- |
| 37 | Workload Identity Federation | Ending long-lived service account keys, including from outside Google Cloud |
| 38 | Secret Manager | Rotation, versions, and what replication location means |
| 39 | Cloud KMS, CMEK and Cloud HSM | What customer-managed keys buy, and the key-rotation failure mode |
| 40 | VPC Service Controls | Perimeters as a data-exfiltration control — the GCP-specific idea with no clean equivalent, and the one most often misconfigured |
| 41 | Security Command Center | What each tier detects, and what the free tier really gives |
| 42 | IAM Conditions and just-in-time access | Standing access as the thing to eliminate, and the break-glass path |
| 43 | Binary Authorization and supply chain | Attestation as a deploy-time gate, and what it does not prove |
| 44 | Assured Workloads, residency and sovereignty | When the compliance boundary is worth its constraints |

## Phase 6 — Operations and reliability (#45–#52)

| # | Topic | The decision |
| --- | --- | --- |
| 45 | Cloud Logging: buckets, sinks and retention | Log routing as an architecture decision, and where the ingestion bill comes from |
| 46 | Cloud Monitoring, metrics and dashboards | Metric scopes across projects, and what is actually collected by default |
| 47 | SLOs, error budgets and alerting policies | Alert fatigue as an architecture problem, not a tuning problem |
| 48 | Cloud Trace, Profiler and Error Reporting | What instrumentation costs and what it returns |
| 49 | Backup and DR Service, snapshots and retention | RPO/RTO stated honestly, with what each product actually guarantees |
| 50 | Multi-region architecture and failover | Active-active vs active-passive on Google Cloud, priced |
| 51 | SLAs and composite availability | The arithmetic across a real multi-service application |
| 52 | Cost management, Recommender and the FinOps loop | Where the cost data lags, and which recommendations are safe to act on |

## Phase 7 — Advanced and cross-cutting (#53+)

Deliberately open-ended. Numbered as written, in whatever order the material
justifies:

- GKE Enterprise, fleets and multi-cluster operations
- Cloud Service Mesh
- Apigee and API management
- Vertex AI: quota, provisioned throughput, and data boundaries
- Grounding and RAG architectures on Google Cloud
- Migration Center and the seven Rs on Google Cloud
- Google Distributed Cloud and hybrid
- Multi-tenant SaaS architecture on Google Cloud
- Policy at scale: Config Controller across many projects
- Cross-cloud: GCP ↔ AWS and Azure connectivity and identity federation

## This series is not an AWS comparison

Google Cloud is explained on its own terms, from first principles, for a reader
who may never have opened an AWS or Azure console. There is no running
translation table and no "the AWS equivalent is".

This is a real temptation here specifically, because the material is being
learned against an AWS background, and a comparison is the fastest way to
understand something yourself. It is not the fastest way to explain it. Write the
post from the GCP model outward.

A comparison is allowed only where the GCP design is genuinely unintelligible
without it, and it earns its place sentence by sentence. Cross-cloud
connectivity and identity federation, in Phase 7, is the one topic where more
than one cloud is the subject.

## Notes on sequencing

- **#1–#9 must ship in order.** Everything later assumes the hierarchy from #1,
  the IAM model from #3 and the location-scope model from #8.
- Within a phase, order is a preference, not a dependency, except where a post
  names an earlier one.
- **A post may be moved forward only into an unpublished number.** If a topic
  turns out to be thin, replace that number's topic; do not renumber around it.
- Every post carries a diagram. If a topic does not produce a diagram worth
  drawing, that is a signal the topic is too small to be its own number.
