# Operating Rules (Workflow + Testing + HTML Apps)

<!-- sentinel:skip-file — this doc lists the patterns Sentinel flags; scanning it creates dogfooding BLOCKs -->

> Consolidated 2026-04-15 from `workflow.md` + `testing.md` + `html-apps.md`.
> Domain-specific catalogs stay separate: `lessons.md` (past-incident bug prevention), `e156.md` (E156 format), `advanced-stats.md` (statistical gotchas).
> Derived from 129-session insights. The #1 friction source across that history has been **130 buggy-code instances** — testing rules (below) exist to cut that.

---

## Workflow

### Fix-all-in-one-pass
- Apply **every fix** in one pass. Track with IDs (P0-1, P1-3).

### Scope discipline
- Keep small requests small. Do not expand into unrelated audits, manuscript waves, or parallel agent swarms without explicit user approval.
- Portfolio-wide work should be split into batches (3-5 projects or one milestone) with a checkpoint after each batch.
- Define "done" before starting. One project at a time. Front-load highest priority.

### Request confirmation
- Before substantial work, restate the deliverable, non-goals, and whether the task is read-only or edit-allowed. Keep non-goals visible so work does not drift.

### Ingredient proof and claim discipline
- Verify required source data exists on disk before implementation or documentation claims.
- For nontrivial plans, recovery docs, or audits, include a static-vs-dynamic hardcode-disclosure table.
- Keep README claims, dashboard copy, and code scope aligned.

### Search before declaring missing
- Apps are 20-50K lines — grep for function names, DOM IDs, patterns before reporting absent.
- Verify actual data model (grep field names) before writing accessor code.
- Run structural check (div balance, script integrity) after HTML edits.

### Identifier and metadata validation
- Treat trial IDs, NCT IDs, PMIDs, DOIs, exact dates, and cohort labels as typed fields, not approximate text.
- Cross-check identifier or date edits against the source dataset, registry entry, fixture, or cited paper before changing code, tests, README copy, or dashboards.
- If a test only passes after changing an identifier or date, record the source evidence for that change in the commit message, review notes, or TruthCert output.

### Git hygiene
- Keep `git status` readable. If temp/system noise dominates the worktree, fix `.gitignore` or redirect outputs before continuing.
- **Commit after each completed batch/milestone, not at session end.** If a script evolves v1→v5 entirely within the working tree before its first commit, that is a violation. Self-triggering signal: "I just finished batch-N, moving to batch-(N+1)" → commit batch-N first. Measure: if `git status` at session-end shows unrelated uncommitted work bundled together with your changes, you waited too long. (Learned 2026-04-14.)

### Long-running & external services
- Prefer resumable/background commands plus a recorded checkpoint over tight polling loops for slow downloads or builds. Report exact command, state, and next action so another session can resume cleanly.
- For APIs, downloads, or remote services: use retries with bounded backoff, resumable state, caching, and explicit throughput estimates before large rewrites.
- Handle auth expiry, rate limits, Cloudflare blocks, 413/429/502, and HTML error payloads explicitly. Fail closed on partial downloads or malformed remote payloads — never treat an error page as valid data.

### Session checkpoints — during work
- Long sessions: write `PROGRESS.md` in the project dir with completed/in-progress/remaining; make it self-contained so another session can resume without re-explaining context.
- Include: task list with status, last file touched, next step, partial state (e.g. "3/8 projects pushed").
- **On usage-limit hit**: refresh `PROGRESS.md` immediately before the session dies.
- Add `PROGRESS.md` to `.gitignore` in every repo — may contain local paths and internal state.
- Before re-running analysis, check for existing `PROGRESS.md` / `sentinel-findings.md`. Re-verify critical claims before acting on them (memory != evidence).

### Session checkpoints — at completion
- Savepoint after each completed component, not just at the end. Preferred order: commit if repo state is appropriate; otherwise refresh `PROGRESS.md` with the last green test command, touched files, and next step. Do not let a 5-10 task session depend on one final commit.
- If push or deploy is part of the task, verify the remote branch, release artifact, or Pages output after the push — do not assume success from local logs.

### Registry & lifecycle gates

**Authoritative sources:**
- Portfolio count: `C:\ProjectIndex\agent-records\restart-manifest.json` (`overview.projectCount`).
- Dev status: `C:\ProjectIndex\INDEX.md`. Submission status: `C:\E156\rewrite-workbook.txt`. On conflict: INDEX.md wins for dev, workbook wins for submission.

**Gate: run `python C:\ProjectIndex\reconcile_counts.py`** before citing any portfolio count, promoting any lifecycle status, or launching portfolio-wide verifier runs. Script fails closed (exit 1) on missing paths or registry disagreement. Do NOT quote numbers from INDEX.md prose, workbook headers, or agent memory without a fresh reconcile run.

**Path contract:** Before implementation, verification, or status changes, confirm the exact project path resolves consistently in INDEX.md, `repo-status.json`, SubmissionCockpit, and the workbook when those systems apply. If the path is generic/stale/moved, repair the registry first.

**Lifecycle evidence:** Do not mark a project Active, Submission ready, or Shipped unless the exact path exists and current evidence is explicit. If the latest Overmind verdict is missing/FAIL/REJECT, mark the project unverified or triage-needed. Numerical witness skips due to missing baselines are NOT release evidence.

### Enforcement layer (Sentinel + Overmind)
- **Sentinel** (`C:\Sentinel\`) is the pre-push rule engine. 12 rules (6 YAML + 6 plugin) block P0 violations and surface P1/P2 WARNs (hardcoded paths, placeholder HMAC, silent-failure sentinels, committed `.claude/` configs, stale agent-config version claims, empty-DataFrame access). Active in ≥10 repos. BLOCK → `STUCK_FAILURES.md`/`.jsonl`; WARN → `sentinel-findings.md`/`.jsonl`. Override: `SENTINEL_BYPASS=1 git push` (logged to `~/.sentinel-logs/bypass.log`; the log path cannot be redirected to `/dev/null` / `NUL` — discard targets are rejected). Install/uninstall: `python -m sentinel install-hook --repo <path>` / `uninstall-hook`. When a Sentinel BLOCK fires, fix the underlying violation rather than bypassing — the rule encodes a past-incident lesson.
- **Overmind** (`C:\overmind\`) is the nightly portfolio verifier. Its verdict is the authoritative ship gate. Overmind reads Sentinel's per-repo `STUCK_FAILURES.jsonl` as one of its witnesses.
- Before citing project-health claims (test count, rule count, BLOCK count), re-run `python -m sentinel scan --repo <path>` or check the Overmind nightly — do not quote memory counts. Memory records drift across sessions.

---

## Testing

### Core
- **Never say "done" without running full test suite** and reporting pass/fail counts.
- **Test after EACH change** — not batched at end.
- All existing tests must pass (no regressions). New features require new tests.

### Verification readiness preflight
- Before running a verifier or saying a repo is verification-ready, confirm the working directory, declared test command, and target files all exist.
- Confirm smoke-test module lists, fixture paths, and numerical baselines exist before expecting those witnesses to pass.
- Confirm critical imports and runtime dependencies resolve before long verify loops. Missing prerequisites are blockers, not normal failures.
- Default smoke and test paths must run from the repo root or a documented working directory without user-home files, manual path edits, or repo-external data hacks.
- Optional dependencies must be declared by the repo setup or explicitly excluded from default verification with a clear skip reason.
- Default smoke/import verification should finish within 120 seconds and the default verify path within 300 seconds unless the project contract documents a different bound.

### Bounded verify-fix-rerun
- Default loop: run the relevant suite, diagnose one failure, apply a fix, rerun the narrow failing target, then continue.
- Cap local retries per failure and cap outer full-suite reruns. When the cap is reached, stop and log the blocker to `STUCK_FAILURES.md` or `sentinel-findings.md`.
- Do not hide repeated failures behind endless reruns or optimistic "probably fixed" claims.

### High-friction regression targets
- Add or preserve regression coverage for division-by-zero, encoding, subprocess hangs, incorrect trial IDs, incorrect dates, and statistics edge cases when those bugs appear.
- Do not change expected trial IDs, PMIDs, DOIs, or dates just to make tests pass. Cross-check them against the source fixture or record first.
- For release-facing or data-sensitive work, do a second-pass review of identifiers, dates, and statistical claims after the suite is green.

### Common regression traps
- When those surfaces are touched, add targeted checks for encoding or BOM drift, identifier and date parsing, division-by-zero, empty datasets, missing columns, and Windows path or quoting behavior.
- If a verifier failure traces to a missing dependency, missing module, or missing baseline, fix the project contract or log the blocker instead of masking it with a looser test.

### Numerical baseline contract
- Any project that ships quantitative claims should keep at least one version-controlled numerical baseline or reference fixture for verifier checks.
- A numerical witness SKIP because the baseline is missing is not a release pass and does not justify promoting the project status.

### Browser testing
- Use `python` not `python3`. Set UTF-8 stdout.
- Chrome: `--headless=new`, `goog:loggingPrefs` for console capture.
- Prefer `C:\Users\user\browser_rotator.py` or an equivalent shared driver helper for multi-agent runs.
- Run sequentially unless the harness explicitly isolates ports, profiles, and browser instances. Set 60s timeout per test.
- Use `WebDriverWait` for stable selectors and wrap driver lifecycle in `try/finally` with `driver.quit()`.
- Do not use global `taskkill` or `pkill` for browsers or drivers unless the user explicitly asks for emergency cleanup.
- Try Edge or Firefox as fallback when Chrome is unavailable.

### R validation
- Compare against metafor/meta/mada with tolerance 1e-6.
- Edge cases: k=1, k=2, tau2=0. Use real published datasets.

### Monte Carlo & stochastic tests
- Use relaxed tolerances: `atol=0.05` for coverage/rejection-rate simulations — NOT for deterministic estimator validation (keep `1e-6` there per R validation).
- Use 3-sigma bounds for Monte Carlo assertions, not tight point estimates.
- Pin seeds for reproducibility but accept inherent variance in stochastic methods.

### Integration tests first (multi-component systems)
- When building multi-component systems (dashboard + engine + manuscript), write integration tests FIRST.
- Tests must define the contracts between modules: shared field names, data formats, placeholder names.
- Catch placeholder mismatches, missing fields, and API format issues before full implementation.

### Regression snapshots
- Save metrics before optimization. Rollback if any metric regresses >2%.

### Review gate before completion
- Before declaring completion, run a final review for statistical and claim correctness, data integrity, and high-friction edge cases.
- Explicitly check placeholders, hardcoded values, wrong identifiers, wrong dates, empty inputs, missing fields, and division-by-zero paths when those surfaces are in scope.

---

## HTML apps (large single-file)

### Structure
- Use line offsets when reading 50K+ files. Unique localStorage keys per variant.
- Module pattern: `<div class="module-slides" data-module="N">`.

### Safety checks after edits
1. Div balance: `<div[\s>]` vs `</div>` (exclude JS regex)
2. Script integrity: no literal `</script>` in template literals
3. Function/ID uniqueness across entire file
4. Event listener cleanup on modal close
5. No unpopulated template tokens (`{{...}}`, `REPLACE_ME`, `__PLACEHOLDER__`) in shipped files
6. No BOM or hardcoded local paths in shipped HTML/CSS/JS assets

### Copy-paste discipline
- Fix bugs in ALL variants in same pass
- Verify localStorage keys, IDs, export filenames are variant-specific
- Verify all placeholders and empty sections are populated before commit

### Performance
- Seeded PRNG (xoshiro128**) for determinism. GOSH: random sampling for k>15.
- Cache keys: include ALL settings. Revoke Blob URLs after use.

### GitHub Pages
- `index.html` in root or `/docs`. Fully offline — no external CDN.
- Include Open Graph meta tags. Test deployed version.
