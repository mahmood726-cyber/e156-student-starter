---
name: E156 format rules
description: The 7-sentence, 156-word contract every E156 paper must satisfy
type: reference
---

Every E156 paper is **exactly 7 sentences, at most 156 words, single paragraph,
no citations or URLs in the prose.** Sentence order is fixed:

- S1 Question (~22w) — "We asked whether..."
- S2 Dataset (~20w) — what data, from when, how many units
- S3 Method (~20w) — the single named primary estimand
- S4 Result (~30w) — the estimate + CI + a plain-language magnitude
- S5 Robustness (~22w) — one sensitivity check that could overturn S4
- S6 Interpretation (~22w) — what a clinician/policy-maker should take away
- S7 Boundary (~20w) — who this does NOT apply to

**Why:** E156 is a micro-paper format. Enforcing the shape is what gives it its signal — readers can compare 40 papers in 40 minutes because every one looks the same. Breaking the shape is the single most common submission rejection.

**How to apply:** Before you ask the AI to rewrite your paper, run `student validate` on it to see which sentences are missing or out of order. If the AI's rewrite adds citations, URLs, or an 8th sentence, it violated the spec — reject the rewrite and re-prompt with the format rules pasted in.
