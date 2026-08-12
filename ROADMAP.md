# Architecture Series — coverage and roadmap

Where the series stands after 19 posts, what is missing, and roughly a year of
topics chosen to close the gaps.

Written 2026-08-12. The framing target is a Solutions Architect role, so the
question throughout is not "is this an interesting AWS topic" but "does the
body of work argue that this person designs systems".

## What 19 posts actually cover

Domain spread is not the problem. Twelve domains are represented:

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

## The actual problem: the lens, not the subject

|  | Architecture patterns |
|:--|:--|
| Posts #1–9 | **8 of 9** |
| Posts #10–19 | **0 of 10** |

The last ten are five cost posts, four comparisons and one limits post. Not one
of them is *how to design this*. They are all *what this costs and where it
bites*.

That reads as a very capable FinOps or platform engineer. It does not read as
an architect, because an architect is hired to make design decisions under
constraints — and the recent work analyses other people's decisions rather than
making any.

Cost and limits are a real strength and are what make the writing concrete.
They should stay. Roughly one post in five, not five in ten.

## Domains completely absent

These matter more than another comparison in a domain already covered.

- **Migration and modernisation** — the single most common thing an SA is
  actually hired to lead, and there is not one post on it.
- **AI / ML** — and note the blog already *has* a RAG-powered search system
  whose architecture has never been written up.
- **Application-level patterns** — idempotency, saga, outbox, CQRS. Service
  agnostic, and closer to what separates an architect from a strong engineer
  than any single AWS service is.
- **Data platform** — streaming, catalog, lakehouse. Only CUR + Athena so far,
  which is a cost tool rather than a data architecture.
- **API design** — contracts, versioning, deprecation.
- **Hybrid** — Direct Connect, Cloud WAN, Outposts.
- **Well-Architected as a practice** — running a review that changes something,
  rather than reciting six pillars.

## A year of topics

Fifty-two, weighted towards the gaps. Order is a suggestion; the grouping is
the point. Each is a pattern post unless marked otherwise.

### Migration & modernisation — 8
1. The 7 Rs, and why half of every "rehost" list should have been "retire"
2. Dependency mapping before wave planning: the discovery nobody budgets for
3. DMS for heterogeneous migration, and what CDC actually guarantees
4. Application Migration Service: cutover windows, rollback, and the freeze
5. Oracle to Aurora PostgreSQL: the parts that do not convert
6. Strangler fig on AWS: routing, dual-write, and knowing when to cut
7. When not to modernise — the honest case for leaving it alone
8. The cost cliff after lift-and-shift *(cost lens)*

### AI & ML — 6
9. RAG architecture, from this blog's own search system
10. Bedrock: model choice, provisioned throughput, and what it costs *(cost lens)*
11. Vector storage on AWS: OpenSearch, pgvector, S3 Vectors
12. Guardrails, PII and prompt injection in production
13. Bedrock or SageMaker: consume or build
14. Evaluating model output, which is the part everyone skips

### Application patterns — 7
15. Idempotency: the property distributed systems cannot do without
16. Saga, and why two-phase commit is not coming back
17. The outbox pattern, and the dual-write problem it solves
18. CQRS, and the far more common case where it is overkill
19. Retries, backoff, jitter, and the thundering herd you built
20. Event schema evolution: contracts between teams
21. Multi-tenancy: pool, silo, bridge

### Data platform — 6
22. Kinesis, MSK or Firehose
23. Glue catalog and schema drift
24. Iceberg on S3: table formats and why they arrived
25. Redshift or Athena: when a warehouse earns its keep
26. Lake Formation and governed access
27. Streaming versus batch: the latency and cost curve *(cost lens)*

### Resilience & DR — 5
28. RTO and RPO, chosen honestly rather than aspirationally
29. Cell-based architecture and blast radius
30. Multi-region active-active: the consistency bill
31. Fault injection with FIS: testing the failover you claim to have
32. Backup and restore, and the restore nobody has tried

### Security & compliance — 6
33. Zero trust on AWS, past the marketing
34. Landing zones for regulated workloads: PCI and HIPAA
35. Detection and response: GuardDuty, Security Hub, Detective
36. Network Firewall and egress control
37. Certificate management at scale
38. Incident response runbooks that survive an actual incident

### Governance & organisation — 5
39. SCPs: the policy language nobody reads carefully
40. Landing zone design beyond Control Tower
41. A tagging strategy that survives contact with reality
42. Cost allocation and showback that changes behaviour *(cost lens)*
43. Running a Well-Architected review that changes something

### API & integration — 4
44. API Gateway REST, HTTP, or an ALB
45. AppSync and GraphQL: where it fits
46. Versioning and deprecating an API without breaking callers
47. Service mesh: the honest threshold for needing one

### Compute & networking top-up — 5
48. Direct Connect, VPN, or Cloud WAN
49. Global Accelerator versus CloudFront
50. Karpenter and node lifecycle
51. Fargate or EC2 for ECS and EKS *(cost lens)*
52. PrivateLink from the service provider side

## Balance this produces

| Lens | Share |
|:--|:--|
| Pattern / design | ~85% |
| Cost | ~10% |
| Comparison | ~5% |

Against the current run of ten, which is 0% pattern.

## Structural note

Every post so far uses an identical six-section skeleton, enforced by
`REQUIRED_HEADINGS` in `scripts/validate_arch_post.py`. That check was added to
catch a body swallowed by an unclosed comment and became a straitjacket: the
shape now dictates the content, and every topic gets bent into four problems and
a decision table whether it has four problems or not.

Several topics above — the migration ones especially — want a different shape:
a walkthrough, a post-mortem, a single-idea piece. Relaxing the required set to
a smaller core (Architecture and Official AWS Reference) would allow that
without losing the check's original purpose.
