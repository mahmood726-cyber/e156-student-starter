---
name: Ollama TINY-tier code-model quirks
description: The 1.5B code model misdiagnoses pandas empty-DataFrame bugs; trust the 7B or Sentinel
type: feedback
---

When you ask `student ai code` for help debugging a pandas snippet, the TINY
tier (`qwen2.5-coder:1.5b`) sometimes **suggests a "fix" that is still broken**.
Most common example: when the bug is `IndexError` on `.iloc[0]` against an
empty-filter result, the 1.5B model often says "it returns the wrong value"
and proposes `.iloc[0].values[0]` — which also raises IndexError.

**Why:** The 1.5B is too small to reliably recognise the empty-DataFrame bug
class. The 7B code model gets it right (benchmarked 2026-04-20). Sentinel's
`P1-empty-dataframe-access` rule catches both the original bug AND the bad
fix — run `student sentinel check` before accepting any AI code diff.

**How to apply:** If you're on an 8 GB laptop (TINY tier forced), ALWAYS run
`student sentinel check` after pasting AI-generated code. If it flags
`.iloc[0]` or `.values[0]`, the AI missed the empty-filter case — wrap with
`if df.empty: return None` before the access, or use `.iat[0]` after a
length check.
