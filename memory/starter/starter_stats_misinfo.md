---
name: Local models produce wrong stats definitions
description: gemma2:2b mislabels I²; verify any stats definition against advanced-stats
type: feedback
---

<!-- sentinel:skip-file — this memory quotes wrong phrasings AS EXAMPLES of what rules catch -->


When you ask `student ai stats` to explain a meta-analysis statistic, the
TINY-tier prose model (`gemma2:2b`) is prone to specific wrong definitions:

- **I²** — the 2B model says "I² measures variance within your study's
  results." Wrong. I² is the *proportion* of between-study variance due to
  heterogeneity, NOT magnitude. It measures inconsistency, not absolute spread.
- **DOR / log-odds sign flips** — both TINY models have been observed stating
  the wrong sign convention in passing.
- **HR direction** — models sometimes swap experimental vs comparator when
  paraphrasing a ClinicalTrials.gov description.

**Why:** Small language models encode the most-frequent-phrasing version of a
concept, which for I² is often wrong in lay summaries on the web. The upstream
rule library in `rules/advanced-stats.md` has the correct definitions.

**How to apply:** Never paste a statistical claim from AI output into your
paper without cross-checking against `rules/advanced-stats.md`. If the AI
mentions I², DOR, HR, HKSJ, or Clopper-Pearson, read the matching section of
advanced-stats.md FIRST, then rewrite the AI output in your own words so you
own the claim. For submission-grade papers, validate numerical claims against
R metafor via `diffmeta` (opt-in add-on).
