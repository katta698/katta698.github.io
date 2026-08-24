# GCP Architecture Series — roadmap

Written 2026-08-14, before post #1; expanded to a daily year on the same day.
The numbering below is a decision made once: post numbers appear in published
URLs, in the sidebar progress widget and in readers' localStorage read-lists, so
**#12 cannot be inserted between #11 and #12 later**. The AWS series grew
organically and now has gaps that are awkward to backfill; this file exists so
this one does not.

Revising the *content* of an unwritten number is expected and fine. Renumbering
a published post is not.

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

Pages are **custom-built** from `_templates/arch-post-template.html`, like the
AWS and Azure arch series — `gcp-` is in the `externally_built` tuple in
`sync_blog.py`, so sync never overwrites them. Build with
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

Everything else carries over unchanged from `CLAUDE.md`: every printed figure
needs a `verified_claim`, derived figures carry `derive:`/`expect:`, diagrams are
standalone SVG files, no process commentary, and
`python scripts/validate_arch_post.py --series gcp` must report 0 errors.

## Cadence — one post a day, every day, for a year

365 posts, starting Friday 14 August 2026, finishing **Friday 13 August 2027**.
Same rhythm as the Azure series, beginner to advanced in order.

| Phase | Posts | Window |
| --- | --- | --- |
| 1 Foundations and governance | #1–#30 | 14 Aug – 12 Sep 2026 |
| 2 Identity and access | #31–#60 | 13 Sep – 12 Oct 2026 |
| 3 Networking | #61–#110 | 13 Oct – 1 Dec 2026 |
| 4 Compute | #111–#150 | 2 Dec 2026 – 10 Jan 2027 |
| 5 Containers and Kubernetes | #151–#180 | 11 Jan – 9 Feb 2027 |
| 6 Storage | #181–#210 | 10 Feb – 11 Mar 2027 |
| 7 Databases and data platform | #211–#255 | 12 Mar – 25 Apr 2027 |
| 8 Serverless, integration and messaging | #256–#285 | 26 Apr – 25 May 2027 |
| 9 Security and compliance | #286–#320 | 26 May – 29 Jun 2027 |
| 10 Observability and operations | #321–#345 | 30 Jun – 24 Jul 2027 |
| 11 Cost management and FinOps | #346–#355 | 25 Jul – 3 Aug 2027 |
| 12 Reliability and disaster recovery | #356–#365 | 4 Aug – 13 Aug 2027 |

**A daily cadence changes what a post is.** At one a week a post can be a
2,500-word treatment of a whole domain. At one a day it cannot, and pretending
otherwise is how a daily series quietly becomes a weekly one with gaps. Each
post here is **one idea, properly checked** — the topics below are deliberately
narrow for that reason. A post that needs three diagrams and nine sourced
figures is two posts.

**A missed day is a missed day, not a doubled one.** Publishing two to catch up
is how the verification becomes a formality, which is the specific failure the
badge exists to prevent. Slip the schedule and carry on; the phase windows are
guides, not commitments.

### This series is written while learning, and that raises the stakes

The AWS series is written from years of production experience. This one is not:
it starts from no Google Cloud experience at all, and the curriculum below is
built to end, in a year, at the level the AWS series is written from.

That changes how the posts get written, not what they claim.

- **The badge is the thing that must not bend.** There is no experience here to
  catch a wrong figure, so `verified_claims` are the only thing standing between
  a reader and a confidently-worded guess. If a day's checking did not happen,
  the post ships with no `verified:` and no figures — not with a badge and a
  hopeful number.
- **Derived figures carry their arithmetic** (`derive:` / `expect:`).
  Break-evens and effective rates are where every error in the AWS series
  actually happened, and that was with experience behind them.
- **Build it before writing it.** Each post's subject should exist in a real
  project first. This is the first rule daily pressure will break, and it is
  also the rule that catches what nothing else catches.
- **A thin post beats a padded one.** Some topics are not a day's writing.
  Publishing short and correct is better than reaching for detail nobody checked.

### Running two clouds daily

Azure and GCP both publish daily, alongside the AWS daily and weekly series.
Every one of those posts carries the badge, and the badge means a human
personally checked every printed figure against vendor documentation.

That is the real constraint on this schedule, and it is worth naming rather than
discovering in November. Two mitigations, both cheap:

- **Stagger the verification, not just the publishing.** Check a post's figures
  the day before it goes out, so a bad day costs one post's slippage rather than
  two posts' accuracy.
- **A post with no figures needs no badge.** Plenty of the topics below are
  conceptual — routing order, schema design, the shape of an event-driven
  system — and carry no price, quota or limit at all. Those are the days to
  schedule when the week is heavy.

## Phase 1 — Foundations and governance (#1–#30)

1. Organizations, folders and projects: why the project is the unit that matters — **published**
2. Cloud Identity and Google Workspace as the identity source — **published**
3. The Resource Manager API: the control plane every request passes through — **published**
4. Enabling services, and why an API must be turned on before it exists — **published**
5. Project IDs, numbers and names, and which of them are permanent — **published**
6. Project lifecycle: creation, soft delete, restore and purge — **published**
7. Liens: preventing the deletion nobody meant to make — **published**
8. Zonal, regional and global: the location scope of a resource — **published**
9. Multi-region and dual-region locations — **published**
10. Google's network, and the Premium versus Standard network tiers — **published**
11. Billing accounts, subaccounts and the payments profile — **published**
12. Linking billing, and what breaks the moment it is disabled
13. Billing export to BigQuery, and why the console is not the source of truth
14. Reading a Google Cloud invoice
15. Quotas: allocation versus rate, and where each is counted
16. Requesting a quota increase, and designing so you do not have to
17. Labels versus tags: two systems that look alike and are not
18. Resource naming standards that survive three years
19. Organization Policy Service: constraints and how they inherit
20. Boolean, list and custom constraints
21. Dry-run mode: testing a policy before it denies anything
22. The organization policies worth setting on day one
23. Cloud Asset Inventory: what exists, and what changed
24. Asset feeds and change notifications
25. Terraform on Google Cloud: the provider and where state lives
26. Infrastructure Manager: managed Terraform
27. Config Connector: Kubernetes as the control plane
28. gcloud, the REST API, and what the console quietly does for you
29. The enterprise foundations blueprint, section by section
30. Landing zone design for a real organisation

## Phase 2 — Identity and access (#31–#60)

31. IAM principals: users, groups, domains and service accounts
32. Roles: basic, predefined and custom
33. Allow policies, bindings, and the union rule
34. Inheritance in practice: tracing why an account has access
35. Custom roles: launch stages, and the permissions you cannot grant
36. Deny policies: syntax, evaluation order and denial conditions
37. IAM Conditions: attribute-based access control
38. Policy Troubleshooter and Policy Analyzer
39. Service accounts: what they are, and what they are not
40. Service account keys, and why they are the wrong default
41. Service account impersonation
42. Short-lived credentials and token generation
43. Workload Identity Federation for AWS
44. Workload Identity Federation for OIDC providers and CI systems
45. Workload Identity for GKE
46. Attached service accounts on Compute Engine
47. Application Default Credentials, and how libraries find them
48. Service agents: the accounts Google creates on your behalf
49. Cloud Identity: users, groups and domain verification
50. Directory synchronisation from on-premises
51. Single sign-on with a third-party identity provider
52. Google Groups as the unit of access
53. Context-aware access
54. Privileged Access Manager and just-in-time elevation
55. Organization-level roles, and the super admin problem
56. Break-glass accounts, designed properly
57. IAM Recommender: role right-sizing
58. Policy Intelligence and access insights
59. Auditing IAM: who granted what, and when
60. An IAM design for a multi-team organisation

## Phase 3 — Networking (#61–#110)

61. VPC networks: global scope, regional subnets
62. Auto mode versus custom mode networks
63. Subnet design and primary IP ranges
64. Secondary ranges and alias IP
65. Expanding a subnet, and what cannot be undone
66. The addresses reserved in every subnet
67. Internal and external IP addresses, static and ephemeral
68. Routes: system-generated and custom
69. Routing order and route priority
70. Firewall rules: structure, direction and priority
71. The implied rules, and the default network's rules
72. Targeting by network tag versus by service account
73. Hierarchical firewall policies
74. Global and regional network firewall policies
75. Firewall Insights and rule hygiene
76. Firewall rules logging
77. VPC Flow Logs: sampling, and what they cost
78. Packet Mirroring
79. Shared VPC: host projects and service projects
80. Shared VPC IAM, and the network admin split
81. VPC Network Peering, and its non-transitivity
82. Network Connectivity Center: hubs and spokes
83. Cloud Router and BGP fundamentals
84. Dynamic routing mode: regional versus global
85. Cloud VPN: Classic versus HA VPN
86. HA VPN topologies and their SLAs
87. Cloud Interconnect: Dedicated
88. Cloud Interconnect: Partner
89. Cross-Cloud Interconnect
90. Private Google Access
91. Private Google Access for on-premises hosts
92. Restricted and private VIPs, and the DNS records behind them
93. Private Service Connect: consumer endpoints
94. Private Service Connect: published services
95. Private Service Connect for Google APIs
96. Service networking, and the peering managed services create
97. Cloud DNS: public zones
98. Cloud DNS: private zones and visibility
99. DNS peering and forwarding zones
100. Inbound and outbound DNS server policies
101. Cloud NAT: how ports are allocated
102. Cloud NAT sizing, and the port exhaustion failure
103. Load balancing: the decision tree
104. The global external Application Load Balancer
105. Regional external and internal Application Load Balancers
106. Network Load Balancers: passthrough and proxy
107. Backend services, health checks and capacity
108. Cloud CDN and cache modes
109. Cloud Armor: policies, rules and the WAF
110. Network Intelligence Center and connectivity tests

## Phase 4 — Compute (#111–#150)

111. Compute Engine machine families: how to read the names
112. General-purpose families: E2, N2, N4 and C4
113. Compute-optimised and memory-optimised families
114. Custom machine types and extended memory
115. Machine images, custom images and image families
116. Boot disks and operating system choice
117. Instance metadata and startup scripts
118. Shielded VM and integrity monitoring
119. Sole-tenant nodes
120. GPUs and TPUs attached to instances
121. Local SSD: the performance, and the data you will lose
122. Persistent Disk types and their performance envelopes
123. Hyperdisk and provisioned IOPS
124. Snapshots and snapshot schedules
125. Regional persistent disks
126. Instance templates
127. Managed instance groups: zonal and regional
128. Autohealing and health checks
129. Autoscaling signals, and what they actually measure
130. Rolling updates and canary releases in a MIG
131. Stateful managed instance groups
132. Unmanaged instance groups, and when they are right
133. Spot VMs: behaviour and interruption
134. From preemptible to Spot: what changed
135. Sustained use discounts
136. Committed use discounts: spend-based and resource-based
137. Reservations, and how they interact with commitments
138. Right-sizing recommendations
139. Live migration and host maintenance policy
140. Instance scheduling, suspend and resume
141. OS Login and SSH key management
142. IAP TCP forwarding, and life without public IPs
143. OS Config: patch management and inventory
144. VM Manager
145. Batch: the managed batch service
146. Bare Metal Solution
147. Google Cloud VMware Engine
148. Migrate to Virtual Machines
149. Confidential VMs
150. A compute design for a real workload

## Phase 5 — Containers and Kubernetes (#151–#180)

151. Artifact Registry: repositories and formats
152. Building images with Cloud Build
153. Image vulnerability scanning
154. GKE Autopilot versus Standard
155. Cluster architecture: control plane and nodes
156. Regional and zonal clusters
157. Node pools and node auto-provisioning
158. VPC-native clusters and IP address planning
159. GKE Dataplane V2
160. Private clusters and control plane access
161. Ingress, the Gateway API, and load balancer integration
162. Services and network endpoint groups
163. Network policy in GKE
164. Workload Identity in practice
165. Autoscaling in GKE: HPA, VPA and the cluster autoscaler
166. Spot nodes and graceful termination
167. Release channels and version upgrades
168. Node upgrade strategies: surge and blue-green
169. Storage in GKE: persistent volumes and CSI drivers
170. Backup for GKE
171. Config Sync and GitOps
172. Policy Controller
173. GKE Enterprise and fleets
174. Multi-cluster Services and multi-cluster Gateway
175. Cloud Service Mesh
176. Binary Authorization for GKE
177. GKE cost: what you are actually billed for
178. GKE observability and control plane metrics
179. Cloud Run versus GKE, chosen honestly
180. A GKE platform design end to end

## Phase 6 — Storage (#181–#210)

181. Cloud Storage: buckets, objects and the global namespace
182. Location types: regional, dual-region and multi-region
183. Storage classes, and what retrieval costs
184. Autoclass
185. Object lifecycle management rules
186. Object versioning and soft delete
187. Retention policies and Bucket Lock
188. Uniform bucket-level access versus ACLs
189. Signed URLs and signed policy documents
190. Public access prevention
191. Customer-managed encryption keys on buckets
192. Requester Pays
193. Object composition and parallel uploads
194. Storage Transfer Service
195. Transfer Appliance
196. The gcloud storage command, and performance tuning
197. Cloud Storage FUSE
198. Object change notifications and Eventarc triggers
199. Filestore tiers
200. Filestore backups and snapshots
201. NetApp Volumes
202. Parallelstore and HPC storage
203. Backup and DR Service: the model
204. Backup plans and backup vaults
205. Persistent Disk asynchronous replication
206. Storage Insights and inventory reports
207. Egress: the cost nobody budgets for
208. Data residency for stored data
209. Choosing a storage product: the decision table
210. A storage design for a data platform

## Phase 7 — Databases and data platform (#211–#255)

211. Choosing a database on Google Cloud
212. Cloud SQL: editions and machine types
213. Cloud SQL high availability
214. Cloud SQL read replicas and cross-region replicas
215. Cloud SQL backups and point-in-time recovery
216. Cloud SQL maintenance windows and upgrades
217. Cloud SQL connectivity: public IP, private IP and the Auth Proxy
218. Cloud SQL IAM database authentication
219. Database Migration Service
220. AlloyDB architecture
221. AlloyDB and the columnar engine
222. AlloyDB read pools and high availability
223. Spanner: architecture and splits
224. Spanner schema design, and the primary key you cannot revisit
225. Spanner interleaved tables and secondary indexes
226. Spanner consistency and TrueTime
227. Spanner instance configurations and compute capacity
228. Spanner change streams
229. Bigtable: rows, column families and the row key
230. Bigtable performance and hotspotting
231. Bigtable replication and app profiles
232. Firestore: documents, collections and queries
233. Firestore indexes, and the ones you must define yourself
234. Firestore security rules
235. Memorystore for Redis and Valkey
236. Memorystore for Memcached
237. BigQuery: storage and compute, separated
238. BigQuery datasets, tables and table types
239. Partitioning
240. Clustering
241. BigQuery on-demand pricing
242. BigQuery Editions, slots and reservations
243. Materialized views and BI Engine
244. External tables and BigLake
245. BigQuery Omni and cross-cloud analytics
246. BigQuery ML
247. Query optimisation and reading the execution plan
248. Dataflow: one model for batch and streaming
249. Dataflow templates and Flex Templates
250. Dataproc and managed Spark
251. Dataproc Serverless
252. Cloud Composer and orchestration
253. Datastream and change data capture
254. Dataplex and data governance
255. A data platform design end to end

## Phase 8 — Serverless, integration and messaging (#256–#285)

256. Cloud Run: the request model
257. Cloud Run services versus jobs
258. Concurrency and CPU allocation
259. Scaling, minimum instances and cold starts
260. Revisions and traffic splitting
261. VPC egress and Direct VPC networking
262. Private ingress and internal-only services
263. Cloud Run functions: what became of Cloud Functions
264. Function triggers and Eventarc
265. Volume mounts on Cloud Run
266. GPU workloads on Cloud Run
267. App Engine standard and flexible, and what they are still for
268. Pub/Sub: topics, subscriptions and delivery semantics
269. Push versus pull subscriptions
270. Ordering keys and exactly-once delivery
271. Dead-letter topics and retry policy
272. Pub/Sub Lite, and whether it fits
273. Eventarc: sources, triggers and CloudEvents
274. Cloud Tasks and rate-limited work
275. Cloud Scheduler
276. Workflows: orchestration without a server
277. Application Integration
278. API Gateway
279. Apigee: architecture and deployment models
280. Apigee policies and API products
281. Cloud Endpoints
282. Firebase as a managed application backend
283. Edge caching for dynamic content
284. Idempotency and retries in an event-driven system
285. An event-driven architecture end to end

## Phase 9 — Security and compliance (#286–#320)

286. The shared responsibility model on Google Cloud
287. Security Command Center tiers
288. Security Health Analytics
289. Event Threat Detection
290. Container Threat Detection and VM Threat Detection
291. Attack path simulation and exposure scoring
292. VPC Service Controls: perimeters explained
293. VPC Service Controls: ingress and egress rules
294. VPC Service Controls: dry-run mode and rollout
295. Access Context Manager and access levels
296. Cloud KMS: key rings, keys and key versions
297. Key rotation and destruction
298. Cloud HSM and external key managers
299. CMEK across services
300. Confidential Computing
301. Secret Manager: versions and rotation
302. Secret Manager replication and regional secrets
303. Certificate Authority Service
304. Certificate Manager and managed certificates
305. Binary Authorization and attestations
306. Software supply chain: SLSA levels and build provenance
307. Artifact Analysis and vulnerability findings
308. Cloud Audit Logs: admin activity, data access and system events
309. Enabling data access logs, and what they cost
310. Access Transparency and Access Approval
311. Assured Workloads
312. Data residency and sovereign controls
313. Sensitive Data Protection: inspection
314. Sensitive Data Protection: de-identification
315. reCAPTCHA and bot management
316. Web Security Scanner
317. Google Security Operations
318. Incident response on Google Cloud
319. Compliance frameworks, and the reports you can actually obtain
320. A security architecture review

## Phase 10 — Observability and operations (#321–#345)

321. Cloud Logging: the log routing model
322. Log buckets, views and retention
323. Log sinks and exclusion filters
324. Log Analytics: querying logs in SQL
325. Structured logging and severity
326. Cloud Monitoring: metrics, monitored resources and labels
327. Metrics scopes across projects
328. Custom and user-defined metrics
329. Managed Service for Prometheus
330. Dashboards as code
331. Alerting policies and notification channels
332. Alert fatigue, and what is actually worth paging on
333. SLIs, SLOs and error budgets
334. Uptime checks and synthetic monitoring
335. Cloud Trace and distributed tracing
336. Cloud Profiler
337. Error Reporting
338. OpenTelemetry on Google Cloud
339. The Ops Agent: installation and configuration
340. Controlling observability cost
341. Incident management and on-call
342. Change management and deployment safety
343. Recommender and Active Assist across services
344. Support tiers, and what each one buys
345. An observability design end to end

## Phase 11 — Cost management and FinOps (#346–#355)

346. The Google Cloud pricing model, service by service
347. The billing export schema, and the queries worth saving
348. Budgets, alerts and programmatic responses
349. Cost attribution with labels and projects
350. Committed use discounts: analysis and risk
351. Discount sharing across projects
352. Egress and inter-region traffic costs
353. FinOps: the loop, and who owns it
354. Cost anomaly detection
355. Cutting a bill: the order to look in

## Phase 12 — Reliability and disaster recovery (#356–#365)

356. The Google Cloud SLA model, service by service
357. Composite availability across a real architecture
358. RTO and RPO, stated honestly
359. Backup strategy across products
360. Multi-region active-passive patterns
361. Multi-region active-active patterns
362. Failover testing and game days
363. Fault injection and chaos engineering
364. Failure mode analysis for a real workload
365. A year of Google Cloud architecture, reviewed

## This series is not an AWS comparison

Google Cloud is explained on its own terms, from first principles, for a reader
who may never have opened an AWS or Azure console. There is no running
translation table and no "the AWS equivalent is".

This is a real temptation here specifically, because the material is being
learned against an AWS background, and a comparison is the fastest way to
understand something yourself. It is not the fastest way to explain it. Write the
post from the GCP model outward.

A comparison is allowed only where the GCP design is genuinely unintelligible
without it, and it earns its place sentence by sentence. Workload Identity
Federation for AWS (#43) and Cross-Cloud Interconnect (#89) are the topics where
more than one cloud is legitimately the subject.

## Notes on sequencing

- **#1–#30 must ship in order.** Everything later assumes the hierarchy from #1,
  the location-scope model from #8 and the organization policy model from #19.
- Within a phase, order is a preference, not a dependency, except where a post
  names an earlier one.
- **A post may be moved forward only into an unpublished number.** If a topic
  turns out to be thin, replace that number's topic; do not renumber around it.
- **Every post carries a diagram.** If a topic does not produce a diagram worth
  drawing, it is probably a section of a neighbouring post rather than its own
  number — merge it and give the freed number to something in the overflow list
  below.
- **Overflow.** Topics that deserve a number but did not get one this year:
  Vertex AI quota and provisioned throughput, Gemini grounding and RAG
  architectures, Vertex AI Search, Agent Builder, multi-tenant SaaS patterns,
  Migration Center and the seven Rs, Google Distributed Cloud, Anthos on
  bare metal, Cloud Deploy and delivery pipelines, Looker and BI, Apache Iceberg
  on BigQuery, and cross-cloud connectivity to Azure. These are the first
  candidates when a number is freed, and the basis of year two.
