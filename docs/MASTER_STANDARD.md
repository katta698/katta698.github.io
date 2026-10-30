# Master Standard — Cloud Engineering Labs

Issued by Jay, 2026-10-25. **Governs AWS, Azure and GCP equally.**

> **This file is the single source of truth for all three cloud series.**
>
> It lives in the publishing repository, which every series shares: the `aws`,
> `azure` and `gcp` branches are three checkouts of one repo. Changing it on one
> branch and pushing propagates it to the other two on their next rebase.
>
> If you are the Azure or GCP window: this is the standard, not a copy of
> somebody else's. Read it before restructuring or writing a lab post.
> If it disagrees with an older instruction, this wins (see Conflict
> resolution at the end).
>
> **Do not keep a private copy in your own lab repository.** That is how the
> three series drifted apart before: the standard was issued once, in chat, and
> each window kept whatever it remembered.

**Supersedes** `LAB_DOCUMENTATION_STANDARD.md` (earlier the same day) and the
2026-09-30 instruction requiring a complete rendered file tree in every post.
Earlier requirements that do not conflict still stand.

> **Primary objective:** technically accurate, concise, reproducible
> documentation that teaches the architecture today and is still useful for
> troubleshooting or redeployment a year later.

---

## 1. Two deliverables

| | **Engineering blog** — what, why, results | **GitHub lab guide** — how to reproduce |
|---|---|---|
| Problem and outcome | yes | — |
| Services and concepts | yes | referenced |
| Architecture / data flow | yes | referenced |
| Implementation | **key steps only** | exact, in deployment order |
| Prerequisites & permissions | **yes, only what is needed** | exact, with versions |
| Config variables / example values | — | yes |
| Deployment commands | essential snippets | **exact and copyable** |
| Validation | **actual results as evidence** | procedures + expected output |
| Security & cost | yes | cost detail, limitations |
| Troubleshooting | important lessons | guidance |
| Cleanup | process + verification | exact commands + verification |
| Production considerations | where relevant | known limitations |

**Do not duplicate the full GitHub guide inside the blog.** Blog target:
**5–8 minutes** reading, roughly **1,500–2,500 words**.

## 2. Mandatory blog structure

1. **Lab Overview** — descriptive technical title; problem; objective; expected
   outcome; technology/deployment method. Purpose clear **within one minute**.
   Use a descriptive subtitle when the title is creative.
2. **Cloud Services and Concepts** — compact table, one row per service, each
   giving **both**: a one-line plain-English definition of what the service
   *is*, then what it does *in this lab* (an `*Here:*` clause). A reader who
   has never used the service must not finish the row still not knowing what it
   is. "Not generic blurb" bans vendor marketing copy — it does not ban
   defining the thing; the section is called Services **and Concepts**.
   Then 1–3 paragraphs on the concepts the findings depend on.
3. **Architecture and Workflow** — **one** primary diagram, drawn in the
   **vendor's own reference-architecture style** (see below);
   application/network/identity/security/observability boundaries; labelled
   flows; no decorative clutter; **4–7 numbered steps**; important design
   decisions. **Must represent what was actually implemented.**
### The diagram follows the vendor's own convention (confirmed 2026-10-30)

Every lab diagram is drawn the way the cloud provider draws its own reference
architectures, so a reader moving between this series and the vendor's
documentation does not have to learn a second visual language:

- **Official service icons, never redrawn.** The colours carry meaning — in AWS,
  orange is Compute, purple Networking, magenta Databases — so an approximated
  icon is a wrong icon. AWS's icon package permits exactly this use; the
  extracted set lives in `_assets/aws-icons/` with its release and date recorded
  in `SOURCE.json`.
- **A cloud boundary**, and inside it the account, Region or VPC groupings that
  actually apply.
- **The service name printed under each icon**, with a short qualifier when the
  distinction matters (`checkout` / `50 ms → 1 slot`).
- **Numbered step circles on the flow**, matching the numbered list beneath.
- **Right-angled or straight connectors** that do not cross labels or enclose
  an unrelated icon.

`scripts/aws_arch.py` composes these for the AWS series: it emits each icon as a
nested `<svg>`, so the finished diagram is one self-contained element with no
external references and renders anywhere the post does. Azure and GCP take the
same approach with their own official icon sets.

4. **Prerequisites** — only what is actually needed: accounts, IAM/RBAC, tools
   and versions, existing infrastructure, region/config assumptions, quotas.
   Make cross-week dependencies explicit.
5. **Implementation** — final working implementation, in deployment order. Per
   major step: **Step / Why / Action / Validation / Screenshot**. Concise
   copyable snippets. **No** complete Terraform files, extensive terminal
   output, debugging history or exhaustive source listings — link to GitHub.
   Include a **compact** repository structure when it helps: major directories
   and architecturally important files only, **no per-file line counts**, no
   exhaustive inventory. Omit the tree entirely if it does not materially help.
6. **Validation and Evidence** — distinguish *infrastructure deployed*,
   *application working*, *security controls working*, *observed behaviour*.
   Per validation: **Test | Expected result | Actual result | Status**. Real
   measurements only. Explain what each result proves.
7. **Security and Cost** — least privilege; managed identities; secrets; network
   exposure; encryption; logging; governance; accepted trade-offs. Costs: main
   billable resources, estimate and assumptions, **actual measured cost if
   available**, free tier, what keeps charging, optimisation. **Distinguish
   estimates from observed billing.**
8. **Troubleshooting and Lessons** — **Problem → Root Cause → Resolution →
   Lesson Learned.** Not a chronological record of every failed attempt.
9. **Cleanup and Key Takeaways** — cleanup process; verification of removal;
   resources preserved; remaining billing risk; **3–5 takeaways**; repo link;
   official references.

## 2b. Canonical section ids — ALL THREE SERIES

The section *headings* were specified; the HTML `id` attributes were not, and
within hours of the standard being issued the series had already diverged:

| Section | GCP used | AWS used |
|---|---|---|
| Implementation | `build` | `implementation` |
| Security and Cost | `security` | `security-cost` |
| Cleanup and Key Takeaways | `takeaways` | `cleanup` |

Both windows believed they were following the standard. Nothing caught it,
because the shape check only inspected one series.

**Update, same day:** the ids turned out to be the wrong thing to standardise.
Azure uses no section wrappers at all and is nonetheless the most faithful of
the three to the standard, because **the standard specifies headings, not ids**.
All three series carry 9/9 of the mandated headings. The shape check now keys on
headings, so no series has to rewrite its markup, and one gate covers all three.

Converge the ids when you next touch a post, not before. Canonical list:

```
overview · services · architecture · prerequisites · implementation
validation · security-cost · troubleshooting · cleanup
```

Ids follow the heading, so "Implementation" is `implementation` and "Security
and Cost" is `security-cost`. A series that has already published posts on the
older ids should converge when it next touches them rather than rewriting
history for an anchor name.

**Why this matters beyond tidiness:** the ids are the anchor links in the
table of contents, and the shape check keys on them. Three series with three
id sets means one check cannot cover all three, which is how the divergence
survived in the first place.

## 3. Design decisions

For important choices state: what was selected, why, alternatives, trade-offs.
Skip trivial decisions.

## 4. Screenshots

Evidence or genuine clarity only. Crop surrounding UI. Readable on **mobile and
desktop**. Concise caption saying what it proves. Place directly after the
relevant discussion. Redact credentials and sensitive identifiers. **Prefer few
meaningful images over many redundant ones — roughly 4–7 for a typical lab**,
but evidence decides. Never fabricate, and never use an image as a substitute
for a reproducible command.

## 5. Repository standards

Overview and architecture reference; versions and dependencies; config variables
with example values; deployment, validation and cleanup commands; known issues
and limitations; design decisions; official links. Exclude secrets and
environment-specific values. Automate validation and cleanup where practical.

> **A successful `terraform apply` does not prove the solution works.**

## 6. Production vs lab

Distinguish a learning lab from production-ready. Where relevant: availability,
scaling, monitoring, backup/DR, hardening, access governance, cost controls,
deployment automation, quotas. **No generic checklists unrelated to the lab.**

## 7. Accuracy

Prioritise official vendor and Terraform documentation. Verify current
behaviour, permissions, APIs, limits and prices. Clearly separate: documented
facts / lab decisions / observed results / estimates / unverified claims.
**Never invent results, costs, references or evidence. If it cannot be verified,
say so.**

## 8. Past, current, future labs

- **Past:** review against this standard. Preserve correct information, real
  evidence, verified measurements, architectural decisions and genuine
  troubleshooting lessons. Improve clarity and reproducibility. **Do not rewrite
  accurate material unnecessarily. Do not manufacture missing evidence** —
  identify the gap instead.
- **Current:** keep aligned as work progresses; keep the verified implementation
  separate from experimentation notes.
- **Future:** problem → services and costs → architecture and security →
  prerequisites and validation criteria → implement → capture evidence →
  document troubleshooting → verify cleanup → publish both deliverables.
  **Never describe planned work as completed.**

## 9. Writing

Professional and direct. Short paragraphs, clear headings. No repetition or
promotional language. Define terms once. Tables for comparison, code blocks for
essential commands. Consistent visual style across all three series. Everything
readable on mobile. Accuracy and clarity beat any word count.

## 10. Final quality gate

| Requirement | Pass/Fail |
|---|---|
| Problem and objective are immediately clear | |
| Services and their purposes are explained | |
| Architecture represents the implemented solution | |
| Important terminology is understandable | |
| Prerequisites and dependencies are explicit | |
| Implementation follows deployment order | |
| GitHub instructions are reproducible | |
| Validation includes actual evidence | |
| Screenshots have clear purposes | |
| Security decisions and trade-offs are explained | |
| Costs are properly qualified | |
| Important troubleshooting lessons are preserved | |
| Design decisions and limitations are recorded | |
| Cleanup is documented and verifiable | |
| Official references are available | |
| Useful for future troubleshooting and redeployment | |

Classify findings **REQUIRED** (technical errors, missing essentials, inaccurate
claims, reproducibility blockers) / **OPTIONAL** (readability, presentation) /
**READY**.

**When it meets the standard, state explicitly: `READY TO PUBLISH — No further
changes required.` Then stop refining.** Reopen only for new evidence, technical
changes, or genuinely important requirements.

## 11. Conflict resolution

Priority order when instructions conflict:

1. Technical accuracy and security
2. Verified implementation and reproducibility
3. Reader comprehension
4. Long-term reference value
5. Formatting and presentation preference

**Conciseness is never permission to remove essential technical information.**

---

**Guiding principle:** document the problem clearly, explain the architecture
simply, implement it reproducibly, validate it with evidence, and preserve the
engineering lessons that matter — for an engineer learning it today and one
returning in a year. Then stop.
