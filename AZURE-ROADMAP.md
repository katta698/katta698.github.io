# Azure Architecture Series — roadmap

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

## Cadence — one post a day, every day, for a year

Jay works in AWS day to day and does not want Azure to go cold. The series is
therefore paced as **learning, not output**: one post a day, every day including
weekends, beginner to advanced in order, mirroring the AWS Daily Intelligence
rhythm.

365 posts, starting Friday 14 August 2026, finishing **Friday 13 August 2027**.

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

**Azure and GCP both run daily, and that is the constraint to manage.** Decided
2026-08-14, superseding an earlier note here that said not to. Every post carries
the badge, and the badge means a human personally checked every printed figure
against vendor documentation — two of those a day, on top of the AWS daily and
weekly series, is the tightest thing on this schedule. Two mitigations, both
cheap: verify a post's figures the day before it publishes, so a bad day costs
slippage rather than accuracy; and schedule the conceptual topics, which carry no
price or quota and therefore need no badge, for the heavy weeks. See the matching
section in `GCP-ROADMAP.md`.

## This series is not an AWS comparison

Azure is explained on its own terms, from first principles. There is no running
translation table, no "the AWS equivalent is", and no assumption that the reader
knows AWS at all — a reader who has never opened an AWS console should lose
nothing.

A comparison is allowed only where the Azure design is genuinely unintelligible
without it, and it earns its place sentence by sentence. In practice that should
be rare. Cross-cloud connectivity and identity federation is the one topic where
both clouds are legitimately the subject.

---

# The 365

## Phase 1 — Foundations and governance (#1–#30)

1. Tenants, management groups, subscriptions and resource groups — **published**
2. Microsoft Entra ID as the identity plane: tenant, directory and subscription trust
3. Azure Resource Manager: the control plane every request passes through
4. Resource providers, registration, and what "not registered" really means
5. Resource types, API versions, and why a template pins one
6. Regions, geographies and sovereign clouds
7. Availability zones: what a zone is and what it guarantees
8. Paired regions, and what pairing does and does not promise
9. Subscription types: EA, MCA, CSP and pay-as-you-go
10. Billing accounts, billing profiles and invoice sections
11. Quotas and limits: where they are counted, and how to raise them
12. Resource naming standards that survive three years
13. Tagging strategy, and the tags that do not inherit
14. Azure Policy: definitions, assignments and effects
15. Policy initiatives and compliance state
16. Policy remediation tasks and their managed identities
17. Deny, audit or deployIfNotExists: choosing an effect
18. Azure RBAC: role definitions, assignments and scope
19. The built-in roles worth knowing, and the ones routinely misused
20. Custom roles: assignable scopes and their limits
21. Deny assignments, and what replaced Blueprints
22. Management locks: CanNotDelete and ReadOnly
23. Resource moves: what can move, what cannot, and what breaks
24. Deployment scopes: tenant, management group, subscription, resource group
25. ARM templates: structure, parameters and outputs
26. Bicep: modules, loops, and what it compiles to
27. Terraform on Azure: the AzureRM provider and state
28. Deployment Stacks and managed resources
29. What-if, preflight validation and deployment history
30. Landing zones and the Cloud Adoption Framework accelerator

## Phase 2 — Identity and access (#31–#60)

31. Entra ID editions: Free, P1, P2, and what each unlocks
32. Users, groups and administrative units
33. Dynamic group membership rules
34. App registrations and service principals
35. Managed identities: system-assigned versus user-assigned
36. Managed identity on VMs, App Service, Functions and AKS
37. Workload identity federation
38. App roles, scopes and consent
39. OAuth 2.0 and OpenID Connect flows on Entra
40. Tokens: access, ID and refresh, and their lifetimes
41. Conditional Access: signals, decisions and enforcement
42. Named locations, device filters and risk conditions
43. Multifactor authentication methods and authentication strength
44. Passwordless: FIDO2, Windows Hello and Authenticator
45. Privileged Identity Management: eligible versus active
46. PIM approval workflows and access reviews
47. Break-glass accounts and their exclusions
48. Entra ID Protection: risk detections and policies
49. Hybrid identity: Entra Connect sync topologies
50. Password hash sync, pass-through authentication and federation
51. Seamless SSO, and what it needs on-premises
52. Entra Domain Services versus domain controllers on VMs
53. B2B collaboration and guest access governance
54. Entra External ID and customer-facing identity
55. Cross-tenant access settings and trust
56. Entitlement management and access packages
57. Lifecycle workflows for joiners, movers and leavers
58. Entra logs: sign-ins, audit and provisioning
59. Enterprise applications and SSO configuration
60. Identity governance across a multi-subscription estate

## Phase 3 — Networking (#61–#110)

61. VNets, subnets, and the five addresses Azure reserves
62. Address planning that survives growth and peering
63. Subnet delegation and service injection
64. Network Security Groups: rules and evaluation order
65. The default NSG rules everyone forgets
66. Application Security Groups
67. Effective security rules, and diagnosing a blocked flow
68. Default outbound access and its retirement
69. Public IPs: Basic versus Standard, static versus dynamic
70. NAT Gateway and SNAT port exhaustion
71. VNet peering, global peering, and what it costs
72. Peering, VPN or ExpressRoute: three ways to join networks
73. Site-to-site VPN gateways and SKUs
74. Point-to-site VPN and client configuration
75. ExpressRoute circuits, peerings and providers
76. ExpressRoute Direct, FastPath and Global Reach
77. Hub-and-spoke topology
78. User-defined routes and route tables
79. Forced tunnelling and its consequences
80. BGP on Azure gateways
81. Azure Virtual WAN: hubs and connectivity
82. Virtual WAN routing intent and policies
83. Network Virtual Appliances and high availability
84. Azure Firewall: SKUs, rules and policy hierarchy
85. Firewall Manager and secured hubs
86. Web Application Firewall on Front Door and Application Gateway
87. DDoS Protection: IP and Network tiers
88. Azure DNS public zones
89. Private DNS zones and virtual network links
90. DNS Private Resolver and hybrid resolution
91. Private Endpoints: what they actually change
92. Private Link service and consumer approval
93. Service Endpoints versus Private Endpoints
94. The private endpoint DNS problem, end to end
95. Load Balancer: SKUs, rules and health probes
96. Load Balancer outbound rules
97. Application Gateway: listeners, rules and backend pools
98. Application Gateway v2 autoscaling and zone redundancy
99. Front Door: routing, caching and the rules engine
100. Traffic Manager profiles and routing methods
101. Choosing between the four balancing services
102. Network Watcher: connection troubleshoot and packet capture
103. VNet flow logs and traffic analytics
104. Network segmentation patterns for regulated workloads
105. Bastion: SKUs, native client and shareable links
106. Just-in-time VM access
107. Cross-region connectivity and latency
108. IPv6 on Azure networking
109. Azure Route Server
110. Connectivity for a multi-region hub-and-spoke

## Phase 4 — Compute (#111–#150)

111. VM series, and how the letters map to real hardware
112. vCPU quotas, families and regional capacity
113. VM sizing: the mistakes that recur
114. Ephemeral OS disks
115. Generation 1 versus Generation 2 VMs, and Trusted Launch
116. VM images: marketplace, specialised and generalised
117. Azure Compute Gallery and image versioning
118. Building images with Packer and Image Builder
119. Availability sets, update domains and fault domains
120. Zonal, zone-redundant and regional deployments
121. Virtual Machine Scale Sets: uniform versus flexible
122. Autoscale rules, and what a metric really measures
123. Scale-in policies and instance protection
124. Spot VMs: eviction policies and pricing
125. Reserved instances and instance size flexibility
126. Savings plans for compute
127. Azure Hybrid Benefit
128. Dedicated hosts and isolated VMs
129. Proximity placement groups
130. Accelerated networking
131. Disk types: Ultra, Premium SSD v2, Premium, Standard SSD, HDD
132. Disk bursting: on-demand and credit-based
133. Disk performance, and the VM's own IOPS ceiling
134. Host caching, and when it hurts
135. Shared disks and clustered workloads
136. Disk encryption: SSE, ADE and encryption at host
137. Azure Backup for virtual machines
138. VM extensions and the guest agent
139. Update Manager and patching at scale
140. Run Command and the serial console
141. Boot diagnostics, and recovering a broken VM
142. Azure Automation and runbooks
143. Desired State Configuration and its alternatives
144. App Service plans: tiers, and what they share
145. App Service deployment slots and swap
146. App Service networking: VNet integration and access restrictions
147. App Service scaling, Always On and health checks
148. Azure Functions hosting plans compared
149. Cold starts, Premium plan prewarming and Flex Consumption
150. Batch and HPC workloads

## Phase 5 — Containers and Kubernetes (#151–#180)

151. Container Registry: tiers, geo-replication and tasks
152. Registry authentication and image pull identity
153. Container Instances, and where they fit
154. Container Apps: environments and revisions
155. Container Apps scaling with KEDA
156. Container Apps or AKS: where the line is
157. AKS architecture: control plane and node pools
158. AKS networking: kubenet, Azure CNI and Overlay
159. CNI Overlay versus node subnet: the choice made once
160. AKS ingress: Application Gateway, NGINX and Gateway API
161. AKS egress: load balancer, NAT gateway, user-defined routing
162. Node pools: system, user, spot, taints and tolerations
163. Cluster Autoscaler and Node Autoprovisioning
164. Karpenter on AKS
165. AKS upgrades, surge settings and maintenance windows
166. AKS storage: Disk, Files and Blob CSI drivers
167. Persistent volumes and storage classes on AKS
168. Workload identity on AKS
169. Azure Policy for Kubernetes and Gatekeeper
170. Network policy on AKS: Azure, Calico and Cilium
171. Private clusters and API server access control
172. Container Insights and managed Prometheus
173. Managed Grafana and dashboards that get used
174. AKS cost: node right-sizing and bin packing
175. Multi-tenancy: namespaces versus clusters
176. AKS backup and disaster recovery
177. GitOps on AKS with Flux
178. Service mesh: the Istio add-on and the alternatives
179. AKS Automatic, and what it decides for you
180. Windows node pools

## Phase 6 — Storage (#181–#210)

181. Storage account types and performance tiers
182. Redundancy: LRS, ZRS, GRS, GZRS and read-access variants
183. What a storage failover actually does, and the RPO
184. Blob access tiers: hot, cool, cold and archive
185. Lifecycle management policies
186. Archive rehydration priorities and cost
187. Blob versioning, soft delete and snapshots
188. Immutable storage and legal holds
189. Object replication
190. Blob index tags and metadata
191. Storage account networking and firewalls
192. Private endpoints for storage sub-resources
193. SAS tokens: account, service and user delegation
194. Authorising storage access: keys, SAS or Entra RBAC
195. Data Lake Storage Gen2 and the hierarchical namespace
196. ACLs on Data Lake Storage
197. Azure Files: SMB, NFS and identity-based access
198. Azure File Sync and cloud tiering
199. Azure NetApp Files: service levels and capacity pools
200. Choosing between Files, NetApp Files and Blob NFS
201. Queue storage and Table storage
202. Storage performance targets and throttling
203. AzCopy, Storage Explorer and Data Box
204. Azure Storage Mover and migration
205. Storage encryption: platform, customer-managed and infrastructure
206. Customer-managed key rotation and its failure modes
207. Storage logs, metrics and diagnostic settings
208. Static website hosting and CDN
209. The storage cost model: capacity, transactions and egress
210. Storage reservations

## Phase 7 — Databases and data platform (#211–#255)

211. Azure SQL Database: the purchasing models
212. DTU versus vCore, with the arithmetic
213. Serverless SQL Database and auto-pause
214. Elastic pools, and when they pay
215. Hyperscale: architecture and limits
216. Business Critical and read replicas
217. SQL Database high availability and zone redundancy
218. Active geo-replication and failover groups
219. SQL Managed Instance: what it adds, and what it costs
220. SQL Server on Azure VMs and the IaaS agent
221. Choosing between SQL Database, Managed Instance and SQL on VM
222. SQL backups, retention and point-in-time restore
223. Long-term retention, and testing a restore
224. SQL security: auditing, TDE and Always Encrypted
225. SQL networking: private endpoints and public access
226. Azure Database for PostgreSQL flexible server
227. PostgreSQL HA modes and failover behaviour
228. PostgreSQL read replicas and connection pooling
229. Azure Database for MySQL flexible server
230. MySQL HA, replicas and maintenance windows
231. Cosmos DB: request units and provisioning modes
232. Cosmos DB partition keys: the irreversible decision
233. Cosmos DB consistency levels, priced
234. Cosmos DB global distribution and multi-region writes
235. Cosmos DB indexing policies
236. Cosmos DB APIs: NoSQL, MongoDB, Cassandra, Gremlin, Table
237. Cosmos DB change feed
238. Azure Cache for Redis: tiers and clustering
239. Redis persistence, failover and the Enterprise tiers
240. Azure Managed Redis
241. Data Factory: pipelines, activities and integration runtimes
242. Self-hosted integration runtime and hybrid data movement
243. Mapping data flows and what they cost
244. Synapse Analytics: dedicated versus serverless SQL pools
245. Synapse Spark pools
246. Microsoft Fabric: what it is, and what it replaces
247. OneLake and the lakehouse model
248. Fabric capacities, F SKUs and bursting
249. Databricks on Azure: workspaces and Unity Catalog
250. Delta Lake and the medallion architecture
251. Event-driven ingestion: Event Hubs into storage
252. Stream Analytics jobs and windowing
253. Purview: data catalogue and lineage
254. Data classification and sensitivity labels
255. Data residency and sovereignty in a data platform

## Phase 8 — Serverless, integration and messaging (#256–#285)

256. Functions triggers and bindings
257. Durable Functions: orchestrations and patterns
258. Functions networking and private endpoints
259. Functions scaling: target-based and event-driven
260. Functions Flex Consumption
261. Logic Apps: Consumption versus Standard
262. Logic Apps connectors and the on-premises data gateway
263. Service Bus queues, topics and subscriptions
264. Sessions, dead-lettering and duplicate detection
265. Service Bus tiers and messaging units
266. Event Grid: topics, system topics and event schemas
267. Event Grid namespaces and MQTT
268. Event Hubs: partitions, consumer groups and Capture
269. Throughput units, processing units and premium tiers
270. Choosing between Service Bus, Event Grid and Event Hubs
271. API Management: tiers, and what changes between them
272. API Management policies and the policy pipeline
273. API Management networking modes
274. The self-hosted gateway and hybrid APIs
275. API versioning and revisions
276. Developer portal, products and subscriptions
277. Front Door in front of API Management
278. SignalR Service and Web PubSub
279. Notification Hubs
280. Azure Communication Services
281. Static Web Apps and their API model
282. App Configuration and feature flags
283. Azure Relay and hybrid connections
284. Choreography versus orchestration
285. Idempotency, retries and poison messages

## Phase 9 — Security and compliance (#286–#320)

286. Key Vault: keys, secrets and certificates
287. Key Vault RBAC versus access policies
288. Soft delete and purge protection
289. Managed HSM, and when it is required
290. Certificate lifecycle and auto-rotation
291. Key Vault networking and firewall
292. Encryption at rest across Azure services
293. Customer-managed keys: the patterns and the pitfalls
294. Double encryption and infrastructure encryption
295. Confidential computing: enclaves and confidential VMs
296. Confidential containers
297. Microsoft Defender for Cloud: CSPM and the plans
298. Secure Score, used honestly
299. Defender for Servers: tiers and agents
300. Defender for Containers
301. Defender for Storage and malware scanning
302. Defender for SQL and open-source databases
303. Defender for APIs
304. External Attack Surface Management
305. Microsoft Sentinel: workspace design
306. Sentinel data connectors and normalisation
307. Analytics rules, incidents and entity mapping
308. Sentinel automation and playbooks
309. Sentinel cost: commitment tiers and ingestion control
310. Auxiliary logs and the basic logs tier
311. Data collection rules for security telemetry
312. Just-enough and just-in-time administration
313. Attack paths and exposure management
314. Compliance Manager and regulatory frameworks
315. Azure Policy as compliance evidence
316. The landing zone security baseline
317. Vulnerability management and image scanning
318. Secrets scanning and rotation practices
319. Incident response in Azure: which logs, in which order
320. Security for multi-tenant and shared platforms

## Phase 10 — Observability and operations (#321–#345)

321. Azure Monitor: metrics, logs and the data model
322. Log Analytics workspace design and access modes
323. Table plans, retention and archive
324. Data collection rules and endpoints
325. Migrating to the Azure Monitor Agent
326. KQL fundamentals for operators
327. KQL for cost and capacity questions
328. Application Insights: instrumentation and sampling
329. Distributed tracing and OpenTelemetry on Azure
330. Availability tests and synthetic monitoring
331. Alerts: metric, log, activity log and health
332. Alert processing rules and suppression
333. Action groups and on-call integration
334. Dashboards, workbooks and reports
335. Managed Prometheus and Managed Grafana
336. Service Health, Resource Health and advisories
337. Diagnostic settings at scale
338. Change Analysis and change tracking
339. Azure Resource Graph queries
340. Operational automation: runbooks, Functions and Logic Apps
341. Azure Arc: servers, Kubernetes and data services
342. Arc-enabled governance and policy at the edge
343. Azure Local and hybrid infrastructure
344. Update Manager across a hybrid estate
345. Operational readiness reviews

## Phase 11 — Cost management and FinOps (#346–#355)

346. Cost Management: scopes, views and exports
347. Cost allocation without tag inheritance
348. Budgets, alerts and automated responses
349. Reservations: purchase, exchange and refund rules
350. Savings plans versus reservations
351. Cost anomaly detection
352. Rightsizing recommendations and their blind spots
353. Egress and inter-region traffic charges
354. Chargeback and showback models
355. A FinOps operating rhythm on Azure

## Phase 12 — Reliability and disaster recovery (#356–#365)

356. The Well-Architected reliability pillar, applied
357. SLAs and composite SLA arithmetic
358. RTO and RPO, stated honestly
359. Backup vaults and the Azure Backup service model
360. Site Recovery: replication and failover
361. Multi-region active-passive patterns
362. Multi-region active-active patterns
363. Chaos Studio and fault injection
364. Failure mode analysis for a real workload
365. A year of Azure architecture, reviewed

## Notes on sequencing

- **#1–#30 must ship in order.** Everything later assumes the scope model from
  #1 and the RBAC model from #18.
- Within a phase, order is a preference, not a dependency, except where a post
  names an earlier one.
- **A post may be moved forward only into an unpublished number.** If a topic
  turns out to be thin, replace that number's topic; do not renumber around it.
- **Every post carries a diagram.** If a topic does not produce a diagram worth
  drawing, it is probably a section of a neighbouring post rather than its own
  number — merge it and give the freed number to something in the overflow list
  below.
- **Overflow.** Topics that deserve a number but did not get one this year:
  Azure OpenAI quota and PTU, AI Foundry grounding architectures, AI Search,
  multi-tenant SaaS patterns, Azure Migrate and the assessment, VMware Solution,
  Azure DevOps and GitHub Actions for Azure, Dev Box and deployment
  environments, IoT Hub and Digital Twins, Azure Virtual Desktop, and
  cross-cloud connectivity to AWS. These are the first candidates when a number
  is freed, and the basis of year two.
