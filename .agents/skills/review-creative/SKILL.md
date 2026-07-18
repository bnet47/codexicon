---
name: review-creative
description: Audit customer-facing work for UX, accessibility, brand fit, credibility, and generic AI output. Use for design, marketing, document, presentation, or visual review.
---

# Review creative work

Review evidence, not personal taste. Identify customer-facing weaknesses that reduce comprehension, trust, usability, distinctiveness, or conversion. Do not modify files.

## 1. Establish the review contract

Read the request or brief, audience, primary task or action, product and brand constraints, source material, and artifact under review. Establish whether the surface is **brand** or **product**, because expressive marketing and repeated-use product UI require different judgments.

Build an evidence packet from what is available:

- approved brief and acceptance conditions;
- running or rendered artifact at representative sizes;
- relevant source, tokens, and interaction behavior;
- factual sources, claim approvals, customer evidence, and channel rules;
- baseline or earlier version when the request claims improvement.

State missing context that limits the review. Do not invent a brand strategy and criticize the work for not following it.

Read only the applicable sections of [references/review-rubric.md](references/review-rubric.md).

## 2. Run deterministic and functional checks

For interface source, run the bundled scanner when Python is available:

```text
python .agents/skills/review-creative/scripts/scan_interface.py <files-or-directories>
```

Treat its output as investigation leads, not verdicts. Confirm each finding in context and ignore justified patterns. Also run the project's real lint, accessibility, performance, and browser checks when they exist and are within scope.

Inspect the primary flow and key states at representative mobile and desktop sizes. Check keyboard behavior, focus, zoom, reduced motion, loading, empty, error, success, stale data, and recovery. Render documents, decks, images, and other visual artifacts through their specialist workflow; source files alone are not visual proof.

## 3. Run two independent review passes

### Pass A: comprehension, operation, and truth

Check whether the audience can understand the offer or task, complete it, recover from failure, and trust the result. Verify behavior, accessibility, claims, proof, links, terms, platform constraints, approvals, and data integrity.

### Pass B: craft, coherence, and specificity

Review hierarchy, narrative, typography, color, spacing, imagery, iconography, motion, density, responsive composition, voice, and brand fit. Check both reflex levels:

1. Is the output predictable from its category?
2. Is it predictable from the category plus a request to avoid obvious clichés?

Report common patterns only when they make the work less specific, coherent, usable, or credible. Do not treat novelty as quality or ban a justified pattern by name.

When a baseline exists, compare task success and evidence before comparing surface style. A different design is not automatically an improved design.

## 4. Determine readiness

Report only actionable issues with observed evidence, customer impact, and a correction direction. Order by severity:

- **P1:** blocks release because it materially misleads, excludes, breaks the core task, or creates serious brand, privacy, legal, or compliance risk;
- **P2:** materially weakens usability, credibility, differentiation, accessibility, comprehension, or conversion;
- **P3:** localized craft problem with a clear customer-facing impact.

Do not assign decorative scores or manufacture criticism. Separate confirmed defects from verification gaps and optional opportunities.

Use:

```markdown
## Findings

### [P2] [Short title]
`artifact-or-file:location` — [Observation, evidence, customer impact, and correction direction.]

## Verification gaps
- [Missing evidence and what would verify it.]

## Verdict
READY | NEEDS WORK — [one sentence]
```

If no actionable issue remains, return `READY — no material creative-quality gaps found.`
