# Master LinkedIn Publishing Standard — Cloud Engineering Labs

Issued by Jay, 2026-10-25. **Governs AWS, Azure and GCP equally.**

Lives in the publishing repository, which all three series share as worktrees
of one git directory, so a change here reaches every window on its next rebase.

**Supersedes the earlier LinkedIn guidance** where they conflict — specifically
the ~2,900-character target, the general-audience framing, the
challenge/tools/security/cost labelled sections, and the "Knowledge & Concepts"
section. Those described a different, longer post. See §Superseded at the end.

---

## Objective

One professional LinkedIn post per completed lab, built from the **actual blog
article, implementation and verified results**.

It must read like an engineer sharing real hands-on experience — **not a
marketing article, and not AI-generated promotional content.**

## Structure

**1. Series and title.** The correct series name and week number from the
source material, plus a short technical topic title.

Use the form the series already uses. Do not re-style it; open the previous
week's draft and copy the line.

```
Week 25 of my 52-week AWS Platform Engineering Lab
Week 12 of my 52-week Azure Platform Engineering Lab
Week 11 of my 52-week GCP Platform Engineering Lab
```

The AWS lab has opened this way for fifteen consecutive weeks (9 through 23).
Week 24 shipped as "AWS Architecture Series | Week 24", which is both a
different shape and the wrong series name for a lab post, and this document
had been carrying that one-off as its example -- so the error propagated into
week 25. The weekly lab and the daily architecture series are different
series; a lab post never announces itself as the architecture one.

**2. Opening hook.** An interesting technical finding, unexpected behaviour,
real engineering problem, or misconception the lab demonstrated. **Never**
"Excited to share", "Thrilled to announce", "Another amazing week".

**3. What I implemented.** Two or three sentences: the services used, what was
built, what was being validated. Only services relevant to the main finding.

**4. What I observed.** Three to five concise findings **from actual lab
evidence**. Prioritise unexpected service behaviour, measured results,
architectural decisions, security implications, operational limitations,
troubleshooting discoveries. Use real measurements. **Do not invent results or
exaggerate conclusions.**

**5. Key engineering takeaway.** One clear conclusion another cloud engineer
should learn or consider in a real environment. **Distinguish lab-observed
behaviour from general production recommendations.**

**6. Blog reference.** A natural invitation to read the full article, with the
actual URL. **Never invent a URL.** If none has been supplied, use a clearly
labelled placeholder.

**7. Hashtags.** Three to five relevant technical ones. No excess, nothing
unrelated.

## Writing rules

- **Roughly 120–180 words**, excluding the blog URL and hashtags.
- First person when describing the actual implementation or findings.
- Authentic, confident, practical engineering tone.
- Short paragraphs, suitable for mobile.
- Technical specifics, not generic explanation.
- **No emojis, hype, motivational language or promotional expressions.**
- No clickbait, exaggerated claims or unnecessary questions.
- Do not explain every service or reproduce the blog.
- No technical claim unsupported by the source material.
- **Preserve uncertainty, limitations and unsuccessful results accurately.**
- The opening must be understandable without opening the blog.

## Source of truth

Read the completed blog, the repository documentation and the available
validation evidence **before drafting**. Use only facts the source supports.

**If the blog and the repository disagree, flag the discrepancy rather than
silently choosing one.**

Never describe planned or unverified work as successfully implemented.

## Output

**One draft.** No alternatives unless explicitly requested. No commentary
explaining why the post is good.

Check before delivering:

1. Is the main engineering lesson immediately clear?
2. Does it accurately describe what was implemented?
3. Are measurements and technical claims supported?
4. Is it concise and readable on mobile?
5. Does it avoid repetitive, promotional language?
6. Correct series, week number and blog link?
7. Would another cloud engineer gain a practical takeaway without reading the
   article?

If all pass, deliver the copy-ready post. **Then stop — do not keep suggesting
refinements once it meets this standard.**

## Delivery (carried over, does not conflict)

Hand it over in a fenced code block, paste-ready, plain ASCII. The repository
link belongs alongside the blog link.

`docs/linkedin/` stays gitignored — drafts are local only.

---

## Superseded

These earlier instructions described a longer, more general post and **no
longer apply** to weekly lab posts:

| Earlier guidance | Replaced by |
|---|---|
| ~2,900 characters, under a 3,000 limit | **120–180 words** excluding URL and hashtags |
| Write for a general audience | Engineers; technical specifics |
| Sections: challenge / how I dealt with it / tools / how to implement / security / cost / what it found | The seven-part structure above |
| A "Knowledge & Concepts" section | Not part of this standard |

What carries over unchanged: open on something concrete rather than a
definition, never use emojis or hype, hand it over paste-ready in a fenced
block, and include both the blog and repository links.
