# CLAUDE.md — Claude-specific pointer

<!-- sentinel:skip-file — thin pointer to AGENTS.md -->

See **[AGENTS.md](AGENTS.md)** for all rules. It is the canonical source.

This file exists so Claude Code's config-file convention (CLAUDE.md) is honored. It holds **no rules of its own**. When CLAUDE.md and AGENTS.md appear to conflict, AGENTS.md wins.

## Claude-specific notes
- Claude Code reads this file automatically as per-directory context.
- Per AGENTS.md "Role specialization", Claude is an **execution lead** — implementation, repair, hardening, and release checks. Review Gemini scaffolds skeptically.
- Claude-specific failure modes live in AGENTS.md `### Claude failure modes and counters`.
- Convention pre-2026-04-15: CLAUDE.md held a duplicated copy of cross-agent rules. After consolidation, those live in AGENTS.md only — edits here should be Claude-specific overrides only (e.g. a Claude-only tool, a Claude-only shortcut).
