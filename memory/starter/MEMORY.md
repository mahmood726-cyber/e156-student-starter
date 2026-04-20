# Starter memory index

When you run `student memory init` (or first-run wizard opt-in), these seed
memories are copied to your personal memory dir at:

  `~/.claude/projects/e156-<your-slug>/memory/`

Each one records a mistake that students before you have made — and what to
do instead. They're named `starter_*.md` so you can tell which are yours vs
which were seeded.

## Seeded memories

- [E156 format rules](starter_e156_format.md) — 7 sentences, 156 words, S1-S7 order
- [Ollama model quirks](starter_ollama_tier_quirks.md) — the 1.5B code model gets pandas `.iloc[0]` wrong
- [Stats misinfo from local models](starter_stats_misinfo.md) — I² is NOT variance magnitude
- [Cite before paste](starter_cite_before_paste.md) — AI output can fabricate refs; verify
- [Don't edit YOUR REWRITE once submitted](starter_workbook_protection.md) — workbook contract
- [When to check cloud fallback](starter_cloud_fallback.md) — the egress flag matters

Each memory has a `type:` frontmatter so the agent knows how to apply it:
- `user` — facts about you
- `feedback` — how you want agents to behave
- `project` — context about your ongoing work
- `reference` — pointers to external systems
