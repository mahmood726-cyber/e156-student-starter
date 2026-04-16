# AGENTS.md — Pipeline Rules (Canonical)

<!-- sentinel:skip-file — agent context doc citing canonical tool paths -->

> **This is the source of truth for agent behavior.** CLAUDE.md / GEMINI.md / CODEX.md are thin pointers; anything that contradicts AGENTS.md loses. Consolidated 2026-04-15 from three previously duplicated files.

## Purpose
Ship OA-first meta-analysis tools as E156 micro-papers + GitHub repos + HTML dashboards on GitHub Pages.

## Session Start
- Check `C:\ProjectIndex\INDEX.md` and `C:\E156\rewrite-workbook.txt`.
- Update both only when the task changes project status or submission state.

## Non-negotiables
1. OA-only.
2. No secrets.
3. Memory != evidence.
4. Fail-closed.
5. Determinism.

## Workbook Protection
- `YOUR REWRITE` sections in `C:\E156\rewrite-workbook.txt` are sacrosanct. Never touch them.
- `CURRENT BODY` is editable unless `SUBMITTED: [x]`.

## Session Recovery
- On usage-limit interruption, save `PROGRESS.md` immediately with done, in-progress, and todo state.
- Add `PROGRESS.md` to `.gitignore` in the project repo.
- For long multi-component sessions, savepoint after each completed component: commit if allowed, otherwise refresh `PROGRESS.md` with the last green test command and next step.

## Scope and Agent Usage
- Keep small requests small.
- Do not turn a one-line fix into portfolio work without explicit approval.
- Use at most 2-3 concurrent sub-agents with exclusive file scopes.
- Check agent output before rewriting code it already touched.
- Batch portfolio work into 3-5 project milestones and checkpoint between batches.

## Data and Implementation Integrity
- Verify data on disk before implementation.
- For nontrivial plans or recovery docs, include a static-vs-dynamic hardcode-disclosure table.
- Never ship simulated, placeholder, filler, or hardcoded fake data as real output.
- No hardcoded local paths in pushed code. Support `C:` and `D:` candidate roots when relevant.
- For CT.gov/AACT work: lowercase intervention types, verify columns exist, search by drug name rather than class.
- Treat trial IDs, NCT IDs, PMIDs, DOIs, and study dates as typed source-backed fields. Validate against source records before shipping code, copy, tests, or dashboards.

## Quality
- Fix related issues in one pass.
- Search before declaring something missing.
- Test after each material change and report pass/fail before claiming completion.
- UI projects must pass `tests/test_ui.py` or an equivalent E2E contract.
- Preflight the working directory, test command, smoke targets, baseline files, and critical imports before verifying or releasing.
- Use bounded verify-fix-rerun loops with a cap; log unresolved blockers to `STUCK_FAILURES.md` or `sentinel-findings.md`.
- For release-facing or data-sensitive work, run a second-pass review focused on identifiers, dates, and statistical claims.
- If push or deploy is part of the task, verify the remote result after push rather than assuming success from local output.

## Browser and File Safety
- Bind servers to `127.0.0.1:8000` and use absolute local URLs in tests.
- Prefer `C:\Users\user\browser_rotator.py` and targeted `driver.quit()` cleanup over global browser kills.
- Use a file-writing path that preserves UTF-8 without BOM. Avoid shell redirection when it risks encoding damage.
- No global `taskkill`/`pkill` for browsers or drivers unless the user explicitly asks for emergency cleanup.

## Enforcement Layer
- **Sentinel** (`C:\Sentinel\`) runs as a pre-push git hook in ≥10 repos and blocks P0 violations (hardcoded paths, placeholder HMAC, silent-failure sentinels, registry drift, committed `.claude/`/`.gemini/` configs, stale agent-config version claims, empty-DataFrame access). 12 rules total (6 YAML + 6 plugin). BLOCK → `STUCK_FAILURES.md`/`.jsonl`; WARN → `sentinel-findings.md`/`.jsonl`. Override: `SENTINEL_BYPASS=1 git push` (logged to `~/.sentinel-logs/bypass.log`; `SENTINEL_BYPASS_LOG` cannot be redirected to `/dev/null` / `NUL` — that path is rejected as a discard target). Install: `python -m sentinel install-hook --repo <path>`. When a BLOCK fires, fix the underlying violation rather than bypass — the rule encodes a past-incident lesson.
- **Overmind** (`C:\overmind\`, v3.1.0) runs nightly verification across the portfolio; its verdict is the ship gate. No project promotes to CERTIFIED / Submission-ready / Shipped without a recent Overmind PASS. Overmind aggregates Sentinel's per-repo `STUCK_FAILURES.jsonl` + `sentinel-findings.jsonl`.
- **Skip-file marker**: files with the literal string `sentinel:skip-file` in their first 1KB are excluded from all Sentinel rules. Use for auto-generated content (Overmind wiki entries, nightly reports) and files that document the patterns Sentinel flags (rule-doc mirrors).

## TruthCert and SHIP
- No naked numbers: important numeric claims need evidence, transformation, and validation.
- On `SHIP`: run tests, demo on fixtures, produce TruthCert (HMAC-signed if `TRUTHCERT_HMAC_KEY` is set), **run `python C:/ProjectIndex/reconcile_counts.py` BEFORE updating `INDEX.md` or quoting any portfolio count** (script fails closed on registry drift or missing paths), then push to GitHub, enable Pages, and update `INDEX.md`, the workbook, and `lessons.md`. The reconcile gate is the SHIP precondition — never quote portfolio counts from agent memory or stale prose.

## Config Safety
- Never commit `.claude/`, `.gemini/`, `.codex/`, memory files, or local secrets to public repos.

---

## Role specialization

Claude and Codex are **execution leads** (implementation, repair, hardening, release). Gemini is the **strategic lead** (discovery, mapping, scaffolding, portfolio review). Do not treat Gemini output as final shipped implementation without execution-lead verification.

### Claude failure modes and counters
- **Giant sessions that hit usage limits mid-task** → batch work, savepoint after each completed component (commit if allowed, otherwise refresh PROGRESS.md), refresh before usage-limit death.
- **Fix-rerun churn** → bounded verify-fix-rerun loops with blocker logs; do not endlessly retry.
- **Windows shell fragility** → prefer project scripts / Python helpers; preflight working dir + test command before long subprocess calls; avoid mixed bash + PowerShell chains; treat `$`, apostrophes, backslashes, child-process inheritance as shell-risk surfaces.
- **Identifier/date/statistics drift in long repair loops** → explicit second-pass release review focused on IDs, dates, statistical claims before treating work as ship-ready.
- **Environment**: Windows-first, Python 3.13. Prefer `scipy` and `statsmodels` over PyMC/PyTensor unless the heavier stack is already proven locally.
- **HTML edits**: scan for empty sections, `{{...}}` placeholders, hardcoded paths, broken DOM/script structure; watch for BOM or encoding damage; keep README/dashboard/code aligned.

### Gemini failure modes and counters
- **Scope inflation / implementation theater** → require ingredient proof (files verified on disk), hardcode-disclosure table, execution-lead verification before ship.
- **"Global"/"full"/"autonomous"/"final" marketing language** → demand hardcode disclosure and exact coverage statements.
- **Schema/semantics/constants inferred from naming** → require source inspection, schema checks, documented calibration.
- **Stacking concepts faster than the repo contract supports** → hand off implementation with a bounded checklist, not open-ended expansion.
- **Anti-simulation**: no hardcoded research outputs (HRs, Ns, p-values, effect sizes, rankings). Real findings must come from external files or live programmatic reads of the source dataset.
- **Data/math safety**: verify schema before implementation and fail closed on missing columns; don't assume sibling columns are safe denominators; use explicit null-safe transforms; prefer `.copy()` when NumPy aliasing is ambiguous; use survival functions for numerical precision; check Jensen-style bias when log-pooling.
- **Handoff discipline**: keep requests scoped; on implementation-heavy or release-facing work, hand off to an execution lead with a concrete checklist (verified ingredient paths, working dir, test command, smoke targets, baseline files, dependency assumptions).

### Codex failure modes and counters
- **Broad edit surface** → keep scope tight; no unrequested refactors.
- **Local-environment assumption** → preflight working dir, command targets, imports, fixtures, baselines before verifying.
- **Green tests without source-level identifier validation** → validate IDs/dates/statistical claims against source records before closing.
- **Dirty worktree** → check `git status`, stage explicit paths, avoid bundling unrelated changes into commits.
- **Integration tests first** for multi-component systems; define shared constants and integration contracts before implementation.
- **Monte Carlo stochastic tests** may use `atol=0.05`; deterministic estimators keep `1e-6`.

## Detailed Rules
- `.claude/rules/rules.md` — consolidated workflow + testing + HTML-apps rules (merged 2026-04-15)
- `.claude/rules/lessons.md` — bug-prevention rules from past sessions
- `.claude/rules/e156.md` — E156 format + pipeline
- `.claude/rules/advanced-stats.md` — statistical gotchas
