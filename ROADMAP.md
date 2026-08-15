# Architecture Series — coverage and roadmap

Where the series stands after 19 posts, and a year of topics aimed at covering
the AWS surface rather than a favourite corner of it.

Written 2026-08-12. The framing target is a Solutions Architect role, so the
question throughout is not "is this an interesting AWS topic" but "does the body
of work argue that this person designs systems".

## Cadence, and what it makes possible

Nineteen posts in eighteen days — one a day, unbroken. At that rate a year is
about **365 posts**, which changes what is realistic. AWS has roughly 240
services. Comprehensive coverage is not a fantasy at this cadence; it is a
scheduling problem.

The plan below allocates that year: about 200 posts anchored on services, about
100 on architecture that belongs to no single service, and the rest as slack for
re:Invent, launches, and topics that turn out to deserve two posts.

## What 19 posts cover today

Twelve domains are represented, so breadth was never the problem:

| Domain | Posts |
|:--|:--|
| Security & Identity | 3 — IAM Identity Center, KMS, Secrets vs Parameter Store |
| Networking | 2 — Transit Gateway, VPC endpoints vs NAT |
| Compute & Containers | 2 — ECS vs EKS, Graviton + Spot |
| Integration | 2 — EventBridge, SQS/SNS/EventBridge |
| Data | 2 — Aurora Global, DynamoDB capacity |
| Serverless | 2 — Step Functions types, Lambda concurrency |
| Cost | 1 — CUR + Athena |
| Resilience & DR | 1 — Route 53 ARC |
| Governance | 1 — Control Tower + AFT |
| Observability | 1 — CloudWatch vs OpenTelemetry |
| Edge | 1 — CloudFront + WAF |
| Storage | 1 — S3 storage classes |

## The problem is the lens, not the subject

|  | Architecture patterns |
|:--|:--|
| Posts #1–9 | **8 of 9** |
| Posts #10–19 | **0 of 10** |

The last ten are five cost posts, four comparisons and one limits post. Not one
says *how to design this*; they all say *what this costs and where it bites*.

That reads as a very capable FinOps or platform engineer. An architect is hired
to make design decisions under constraints, and the recent work analyses other
people's decisions rather than making any.

Cost and limits are a genuine strength and are what keep the writing concrete.
They stay — as roughly one post in five, not five in ten.

## Coverage plan by AWS category

Service counts are approximate and move constantly; treat them as scale, not
inventory. "Posts" is the allocation for the year.

| Category | ~Services | Posts | Approach |
|:--|--:|--:|:--|
| Security, Identity & Compliance | 30 | 45 | Deepest coverage. Identity, detection, encryption, network security, compliance. Most services earn their own post |
| Management & Governance | 25 | 40 | Observability, config, org structure, IaC, resilience tooling |
| Machine Learning | 25 | 35 | Bedrock and SageMaker in depth; the AI services grouped by task |
| Networking & Content Delivery | 20 | 35 | VPC design, hybrid, edge, service networking |
| Database | 15 | 30 | Each engine on its own terms, plus data modelling patterns |
| Analytics | 20 | 28 | Streaming, catalog, lakehouse, warehouse, BI |
| Compute | 15 | 25 | Instance families, scaling, serverless compute, edge compute |
| Application Integration | 12 | 22 | Messaging, orchestration, API surfaces, event patterns |
| Storage | 10 | 20 | Object, block, file, archive, transfer, backup |
| Migration & Transfer | 10 | 18 | The 7 Rs, discovery, database and server migration, cutover |
| Developer Tools | 12 | 15 | Pipelines, artifacts, IaC, testing, developer experience |
| Containers | 6 | 14 | Orchestration, registry, scaling, mesh, runtime security |
| Cloud Financial Management | 8 | 12 | Allocation, forecasting, commitment, unit economics |
| IoT | 12 | 6 | Grouped: ingest, device management, edge, industrial |
| Front-End & Mobile | 6 | 5 | Amplify, AppSync, identity for clients |
| Media Services | 10 | 4 | Grouped: the Elemental pipeline end to end |
| End User Computing | 6 | 3 | WorkSpaces and AppStream as VDI architecture |
| Business Applications | 8 | 3 | SES and Connect as integration surfaces |
| Customer Enablement | 5 | 2 | Support models, Well-Architected reviews |
| Games, Blockchain, Quantum, Satellite, Robotics | 8 | 1 | One honest round-up. Niche for this audience, and pretending otherwise wastes a post |
| **Cross-cutting architecture** | — | **~30** | Patterns that belong to no service: idempotency, saga, outbox, CQRS, multi-tenancy, cell-based design, schema evolution, backpressure |

Roughly 365, allowing slack.

## Order for the next quarter

The gaps decide the order, not the categories. Absent domains first.

### Migration & modernisation — nothing written, most common SA responsibility
1. The 7 Rs, and why half of every "rehost" list should have been "retire"
2. Discovery and dependency mapping before wave planning
3. Discovery after Application Discovery Service — agentless vs agent, and the home Region *(written as #22; the original title named a service AWS closed to new customers on 7 November 2025, so the slot covers the decisions that outlived it rather than the product)*
4. DMS for heterogeneous migration, and what CDC actually guarantees
5. AWS Transform MGN: cutover, rollback, and the freeze window *(the service formerly called Application Migration Service — renamed, not closed. Checked 14 August 2026: the user guide is titled "What Is AWS Transform MGN?" and it is live in 36 Regions including both GovCloud partitions. Topic unchanged; only the product name moved.)*
6. Oracle to Aurora PostgreSQL: the parts that do not convert
7. Mainframe modernisation after the managed runtime closed: what a new customer can actually buy *(checked 14 August 2026. Both AWS Mainframe Modernization experiences are closed to new customers, and the two banners point at each other — the Managed Runtime notice sends new customers to the Self-Managed experience, whose own notice says it is closed too. The live paths are AWS Transform for mainframe (refactor) and vendor-direct offerings; replatform runs on Rocket Software, formerly Micro Focus. "Refactor, replatform, or leave it" is no longer a choice a new customer has, so the slot covers what remains buyable rather than a decision that has been made for them.)*
8. DataSync and Transfer Family: moving the data that is not a database
9. Moving data when the network is genuinely the bottleneck: Data Transfer Terminal, DataSync, and the end of Snowball *(checked 14 August 2026. AWS Snowball Edge is no longer available to new customers; AWS directs them to DataSync for online transfers, **AWS Data Transfer Terminal** for secure physical transfers, AWS Partner solutions, or Outposts for edge compute. The premise of the original item survives — the network really is sometimes the bottleneck — but AWS's answer changed shape from a shipped appliance to a facility you carry drives to. Data Transfer Terminal appears nowhere else in this roadmap and is the substance of this slot. Note the redirect also makes DataSync the default for a job Snowball used to own, which item 8 should reflect.)*
10. Strangler fig on AWS: routing, dual-write, and knowing when to cut
11. When not to modernise — the honest case for leaving it alone
12. The cost cliff after lift-and-shift *(cost lens)*

### AI & ML — absent, and the blog already runs a RAG system
13. RAG architecture, from this blog's own search
14. Bedrock: model choice, provisioned throughput, and cost *(cost lens)*
15. Vector storage: OpenSearch, pgvector, S3 Vectors
16. Guardrails, PII and prompt injection in production
17. Bedrock or SageMaker: consume or build
18. Evaluating model output, the part everyone skips
19. Comprehend, Textract, Rekognition: the task-shaped services
20. Inference endpoints: real-time, serverless, batch, async

### Application patterns — absent, and closest to architecture thinking
21. Idempotency: the property distributed systems cannot do without
22. Saga, and why two-phase commit is not coming back
23. The outbox pattern and the dual-write problem
24. CQRS, and the commoner case where it is overkill
25. Retries, backoff, jitter, and the thundering herd you built
26. Event schema evolution: contracts between teams
27. Multi-tenancy: pool, silo, bridge
28. Backpressure, and what a queue is really telling you

### Data platform — only a cost tool so far
29. Kinesis, MSK or Firehose
30. Glue catalog and schema drift
31. Iceberg on S3: why table formats arrived
32. Redshift or Athena: when a warehouse earns its keep
33. Lake Formation and governed access
34. Streaming versus batch: the latency and cost curve *(cost lens)*

## Balance this produces

| Lens | Share |
|:--|:--|
| Pattern / design | ~80% |
| Cost | ~12% |
| Comparison | ~8% |

Against the current run of ten, which is 0% pattern.

## Two honest constraints

**Every service is not worth a post.** Ground Station, Braket and RoboMaker are
real services and irrelevant to this audience; one round-up is more honest than
five posts pretending otherwise. The same applies to the long tail of ML
services that are one API call each — grouped by task, they make one good post
rather than eight thin ones.

**The template constrains what can be written.** Every post so far uses an
identical six-section skeleton, enforced by `REQUIRED_HEADINGS` in
`scripts/validate_arch_post.py`. That check was added to catch a body swallowed
by an unclosed comment and became a straitjacket: the shape now dictates the
content, and every topic gets bent into four problems and a decision table
whether it has four problems or not. The migration posts especially want a
walkthrough or post-mortem shape. Relaxing the required set to a smaller core —
Architecture and Official AWS Reference — would allow that without losing the
check's original purpose.
