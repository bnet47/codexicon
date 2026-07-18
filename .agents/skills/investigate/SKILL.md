---
name: investigate
description: Find the root cause of a reproducible bug, failure, or unexplained behavior. Diagnose only unless the user also requests a fix.
argument-hint: "[symptom or failing command]"
---

# Investigate

Announce: "I'm using investigate to identify the root cause before changing behavior."

## 1. Define the symptom

Capture the expected behavior, actual behavior, environment, and smallest known failing command or interaction. Preserve the exact error text.

## 2. Reproduce

Run or create the smallest safe reproduction. If reproduction is impossible, gather the strongest available evidence and label conclusions accordingly; do not claim certainty.

## 3. Form hypotheses

List two to four plausible causes ranked by likelihood. For each, identify the observation that would confirm or reject it.

## 4. Isolate

Test one hypothesis at a time with read-only inspection or the smallest reversible diagnostic. Avoid changing several variables together. Keep notes on evidence and eliminate contradicted hypotheses.

## 5. Conclude

State the root cause in one sentence with the causal chain and evidence. Distinguish the initiating defect from downstream symptoms.

If the user asked only to diagnose, stop here and recommend a fix plus verification. If the user asked to fix, implement the smallest root-cause correction, add a regression test, rerun the original reproduction, then run the relevant full checks.

## Report

```markdown
## Investigation: [symptom]

**Reproduction:** `[command]` — [result]
**Root cause:** [one sentence]
**Evidence:** [observations that isolate it]
**Fix:** [implemented change or recommended correction]
**Verification:** [commands and results, if implemented]
**Uncertainty:** [remaining limitation, or none]
```
