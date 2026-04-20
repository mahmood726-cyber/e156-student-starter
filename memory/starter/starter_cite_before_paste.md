---
name: Verify citations before pasting AI output
description: Local Ollama models hallucinate citations; every reference needs a primary-source check
type: feedback
---

When the AI produces a rewrite or explanation that mentions a study, author,
journal, or year — **do not trust it.** Local models (and cloud LLMs) are
known to fabricate plausible-looking citations: the author exists, the journal
exists, but the specific paper they cite for this specific claim does not.

**Why:** A past session found an AI-generated e156 draft citing "Neuenschwander
2008" for a MAP-prior claim where the actual citation is Neuenschwander 2010.
The AI guessed the year and it was off by two. For a submission paper, wrong
citations is worse than wrong numbers — it's an integrity issue, not an
accuracy one.

**How to apply:** For every author-year-ish thing the AI mentions:
1. Search PubMed or Google Scholar for the exact citation.
2. Open the paper and confirm the sentence the AI is attributing to it.
3. If the AI says "Smith et al. 2019 found X" and Smith et al. 2019 said Y or
   didn't say anything about X, DELETE the claim. Do not "fix" the year.
4. For e156 papers, citations go in the references block (outside the
   7-sentence body). The body itself is citation-free by spec.
