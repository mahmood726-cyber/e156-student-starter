# Vendored Sentinel rule pack

This directory ships 4 pre-push rules curated for student workflows. They
catch the specific classes of bug that local AI models (gemma2:2b,
qwen2.5-coder:1.5b) commonly produce in the E156 workflow.

## What's here

| Rule | Severity | Catches |
|------|----------|---------|
| `P0-hardcoded-local-path` | BLOCK | `C:\Users\...` or `/home/...` paths that leak dev-env details |
| `P1-empty-dataframe-access` | WARN | `.iloc[0]`, `.values[0]` — IndexError on empty filter |
| `P1-unpopulated-placeholder` | WARN | `TODO:`, `REPLACE_ME`, `{{template_var}}` shipping to production |
| `P1-silent-failure-sentinel` | WARN | `return "unknown_ratio"` and similar — errors disguised as values |

These were copied from Sentinel upstream (`C:\Sentinel\sentinel\rules\yaml\`)
on 2026-04-20 and will drift if Sentinel upstream updates. Re-vendor with:

```
cp C:\Sentinel\sentinel\rules\yaml\<rule>.yaml config\sentinel\rules\
```

## How a student uses them

After `student install repair` (or fresh install), the student gets a
`student sentinel check` command that scans their workbook for these
patterns. Takes ~2 seconds.

If the student installed the pre-push hook during the first-run wizard,
these rules ALSO run automatically on every `git push` and block pushes
that violate them.

## Why these four

Chosen after benchmarking the TINY tier (gemma2:2b + qwen2.5-coder:1.5b)
against the 4 realistic E156 tasks in `tests/tiny_model_benchmark.py`:

1. **empty-dataframe-access** — The 1.5B model gave a wrong "fix" to the
   pandas `.iloc[0]` bug; its suggestion still used `.iloc[0].values[0]`
   which also raises IndexError. Rule catches both the original bug and
   the bad fix.
2. **unpopulated-placeholder** — TINY tier often leaves `{{model_output}}`
   style tokens when asked to fill a template.
3. **silent-failure-sentinel** — Models fall back to "unknown" or empty-
   string returns rather than raising; those propagate bad data.
4. **hardcoded-local-path** — When a student shares their paper repo, any
   `C:\Users\<name>\...` leaks their identity and breaks on another laptop.

## Rules we chose NOT to include

- `P0-claude-config-committed` — students don't use Claude Code directly
- `P0-placeholder-hmac` — no TruthCert signing in student workflow
- `P2-autogen-tracked` — student has no autogen artifacts
- Plugin (Python) rules — require Sentinel full install; the 4 YAMLs above
  can be read by a ~50-line matcher stub if the full Sentinel isn't available
