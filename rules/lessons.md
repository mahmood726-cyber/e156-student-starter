# Accumulated Lessons (mistake-prevention rules)

<!-- sentinel:skip-file — this doc lists the patterns Sentinel flags; scanning it creates false-positive dogfooding BLOCKs -->

> Bug-prevention from past sessions. Stats gotchas in advanced-stats.md.

## JavaScript / HTML
- **`</script>` in template literals/comments**: Use `${'<'}/script>`. Never write literal `</script>` inside `<script>`.
- **`?? ... ||` mixing**: SyntaxError. Always wrap: `a ?? (b || c)`.
- **`|| fallback` drops zero**: Use `??` (nullish coalescing) for numeric values.
- **`parseFloat(x) || null`**: Drops 0.0. Use `isFinite(parsed) ? parsed : null`.
- **Float `===`**: Use tolerance: `Math.abs(a-b) < epsilon`.
- **Div balance**: Count `<div[\s>]` vs `</div>` after HTML edits (exclude JS regex).
- **Hyphen in function names**: Parsed as minus. Use camelCase.
- **`a.click()` detached**: Fails in Firefox. `appendChild(a)` first.

## Python
- **`all()` on empty list**: Returns True. Check `len(items) > 0` first.
- **`if value:` drops 0.0**: Use `is not None` for numeric fields.
- **numpy array `or`/`and`**: Raises ValueError. Use `x if x is not None else fallback`.
- **`isinstance(True, int)`**: Returns True. Exclude explicitly.
- **`datetime.fromisoformat()`**: Python <3.11 can't parse `+00:00`. Strip it.

## Statistics
- **DOR = exp(mu1 + mu2)** - NOT mu1 - mu2.
- **SROC sign**: logit(Spec) = -logit(FPR). Sign flips on conversion.
- **Bivariate prediction region**: `sqrt(chi2_{alpha,2})` not univariate z.
- **HSROC AUC**: Use normalCDF (Phi), NOT logistic. ~2-4% difference.
- **Fragility Index**: Modify ONE arm only.
- **Design effect**: REDUCES N_eff (N/DEFF), not inflates.
- **CT.gov HR**: Always experimental/comparator. Swap labels only, never invert HR.

## Data Handling
- **Windows cp1252**: Unicode chars crash `print()`. Use `io.TextIOWrapper(stdout, encoding='utf-8', errors='replace')`.
- **European decimal regex**: `(\d),(\d{1,2})` corrupts CI commas. Add lookbehind.
- **ReDoS**: `[\w\s]+?` with nesting -> catastrophic backtracking. Use bounded `{1,80}`.
- **CSV formula injection**: Prepend `'` to cells starting with `=+@\t\r` (NOT `-`).
- **Derived HR fallback**: Must null out CI too - HR and CI must come from same source.
- **Negated-counts silent corruption (learned 2026-04-15)**: Regex patterns like `(\d+) subjects randomized` silently match `Not Randomized 1,807` in disposition tables — the negated count becomes the extracted N. All value-extraction regexes that match a number followed by a keyword must check the preceding 30 chars for negation words (`not`, `non`, `never`). Otherwise you get schema-valid (positive int) rows with semantically wrong values that pass all downstream validation. Discovered in DossierGap Verquvo VICTORIA EPAR where "Not Randomized 1,807" was extracted instead of the real N=5,050. Applies to N-randomized, event counts, dropout counts — any "X <metric>" extraction.

## CT.gov / AACT Queries
- **Lowercase intervention types**: AACT uses lowercase (`drug`, `biological`), not titlecase.
- **Verify columns exist**: Check `information_schema` or `PRAGMA` before querying - column names change between AACT snapshots.
- **Drug names, not class names**: Search by specific drug/intervention name (e.g., `empagliflozin`), not therapeutic class (e.g., `SGLT2 inhibitor`).
- **Validate >0 rows**: Always check query returns results before proceeding to analysis.
- **Do not hardcode one drive**: Large local snapshots such as AACT may live on `C:` or `D:`. Use config, candidate-root discovery, or explicit path inputs and fail closed if no snapshot is found.

## Code Quality
- **No hardcoded local paths in deployable code**: Never ship `C:\Users\...` or `/home/...` in HTML, dashboards, or GitHub-pushed files. Use relative paths or config.
- **Shared constants for multi-component builds**: When parallel agents build components independently, define shared field names / placeholder names / path references in a constants file FIRST.

## Agent Workflow
- **Agent false positives**: Agents claim correct code is wrong (DOR, Clayton, Clopper-Pearson). Verify math independently.
- **Contract Drift (Marketing vs Code)**: Gemini often uses "Grand Unified", "Quantum", "7D", or "Global" descriptors for basic arithmetic or graph traversal. **Fix:** Force Gemini to use specific, grounded terminology (e.g., "7-Country Pilot", "Heuristic Scorecard", "Graph Propagation") and add a "Static vs. Dynamic" table to every plan.
- **Simulated Claims**: Gemini claims 204-country coverage while hardcoding 7. **Fix:** Mandate `grep` of source data row-counts before documentation generation.
- **TruthCert Memory Verification**: Don't trust project status in memory or INDEX.md without a fresh `grep` or `pytest` of the claims.
- **No-Marketing Rule**: Scrub "Global", "Full", "Complete", and "Integrated" from agent-generated READMEs/Plans unless implementation supports it *now*.
- **Throttle parallel agents**: Max 2-3 concurrent sub-agents. More causes rate-limit cascades and duplicate work.
- **Check agent output before rewriting**: If an agent completed a module, read its output before manually rewriting.
- **Preflight external prereqs BEFORE starting a multi-task plan**: Evidence Forecast Phase-1 planned 19 TDD tasks assuming `C:\cardiosynth\cardiosynth\engine.py::pool_for_pico` and `C:\MetaAudit\outputs\pairs.csv` existed. Neither did. We discovered this at Task 17 (live integration) after 16 tasks of scaffolding, which meant Task 17 had to become a dev-mode bootstrap and ship thresholds (AUC ≥ 0.70) were deferred to an unquantified future session. Fix: for any plan whose final task depends on an external integration, add a Task 0 that scripts the prereq check (`python -c "from cardiosynth.engine import pool_for_pico"` and similar) and fails closed with a specific user-action list if any prereq is missing. Do this before writing a single test.
- **Hardcoded batch lists in reusable scripts (learned 2026-04-14)**: If a script has a hardcoded list of targets (project names, file paths, test cases) and you find yourself editing that list more than once in a session, refactor to CLI args / config file BEFORE the next edit. Multiple edits to the same hardcoded list = guaranteed git-diff noise and committed dead code paths. Fix at the point of the second edit, not after the fourth. Self-triggering signal: "I'm about to edit this list for the Nth time" → STOP and parametrise instead.

## Platform (Windows)
- Use `python` not `python3`. Use ASCII in console or set UTF-8.
- **Git Bash heredocs**: `<< 'EOF'` (quoted) to prevent expansion.
- **Python 3.13 WMI deadlock**: Monkey-patch `platform._wmi_query` BEFORE scipy import.

## Portfolio Registry (learned 2026-04-14)
- **Registry drift is systemic**: INDEX.md, `restart-manifest.json`, `rewrite-workbook.txt`, and `push_all_repos.py` disagreed by 45+ projects (517 stale in INDEX.md vs 472 true in manifest). Workbook header said 465 but entries denominated [n/449] and [n/387]. Run `python C:\ProjectIndex\reconcile_counts.py` before citing any portfolio count or promoting any status. Script fails closed on drift or missing paths.
- **Path-exists gate before status promotion**: 6 projects were marked Shipped/Submission-ready with directories that did not exist on disk (WinError 267). Never promote lifecycle status without first verifying the exact path resolves on disk. The reconcile script now enforces this.
- **Workbook entries survive status changes**: When demoting a project to MISSING/triage, preserve the workbook entry — it's the submission history record. Only toggle `SUBMITTED: [x]` when actually submitted.
- **Broken git shells fool existence checks**: A directory with a `.git/` subdir but zero tracked files (or no HEAD commit) passes path-exists and shows as a no-remote repo, but is effectively dead. Typical causes: aborted backup, failed init, crashed clone. The `registry_first_rct_meta.corrupt-bak-20260410` folder sat unnoticed for 4 days because `push_all_repos.py --report` only flags missing-remote, not missing-content. `reconcile_counts.py::check_broken_git_shells` now fails closed on these.
- **GitHub-only survival audit**: Before declaring cleanup done, diff `gh repo list <user>` against locally-discovered repos via `C:\Users\user\missing_local_audit.py`. Session 2026-04-14 found 42 GitHub repos with no local clone — some intentionally superseded (v1 → v2), some genuine loss (e.g. AlBurhan, metasprint-autopilot as a `nul`-file stub). Explicit SCAN_DIRS in `push_all_repos.py` drifts; combine with one-level recursion so umbrella folders (`C:\Projects\africa-e156\<topic>`) are auto-discovered.

## Cryptography / Signing (learned 2026-04-14)
- **HMAC key must not come from the bundle itself**: A prior TruthCert impl used `cert_id` as the HMAC key, but `cert_id` is emitted in the bundle — anyone seeing the output can forge. Keys must come from env var (`TRUTHCERT_HMAC_KEY`) or a gitignored file. Fail closed if neither present; never silent-default.
- **Placeholder signatures are a security bug, not a TODO**: `"signature_placeholder": "SIG_RSA_SHA256_..."` shipping in production claims signed-ness without providing it. Treat as P0 and block promotion until replaced with real HMAC/Ed25519.
- **Delete forgeable artifacts after crypto migration**: Old `*_cert.json` files signed under the weak key scheme are forgery templates. Delete or regenerate; don't leave them in the repo alongside the new signer.
- **Constant-time comparison**: Always `hmac.compare_digest`, never `==`, when comparing MACs.

## Integration Contracts (learned 2026-04-14)
- **Field-name contract tests between modules**: MetaReproducer's P0-1 silently corrupted 465 reviews because `effect_inference.py` expected raw RDA keys but the caller passed renamed StudyDict keys. Write a contract test that builds a minimal production-shaped input, calls the inference entrypoint, and asserts the output is NOT a silent-failure sentinel (`unknown_ratio`, `None`, empty dict). One such test per module boundary.
- **Silent failure sentinels are the enemy**: `return "unknown_ratio"` on schema mismatch is worse than raising — it lets the pipeline complete with corrupted output. Prefer raising `KeyError` with the expected-vs-received key diff on unrecognized schema.

## Verdict Schema (learned 2026-04-15)
- **SKIP-as-pass arbitrator bug**: Overmind's `cert_bundle.Arbitrator` previously returned `verdict="PASS"` for tier-3 (high-risk + math ≥10) projects whose numerical witness SKIPPED because the baseline file was missing. `nightly_verify.py` line 448 then counted `verdict in ("CERTIFIED", "PASS")` as success — projects shipped with a "release pass" they had never actually earned. Fix: introduce a distinct `verdict="UNVERIFIED"` for that exact case (test_suite + smoke PASS, numerical SKIP) and exclude it from the success set. Lesson: any time the success predicate is a verdict-membership test (`v in (...)`), enumerate the failure modes ESPECIALLY for the "almost-pass" cases (skip due to missing input, partial pass, downgraded pass). A missing baseline is not a pass; encode that distinction in the verdict, not in a comment.
- **Empty-DataFrame access (P1-empty-dataframe-access Sentinel rule)**: Listed in MEMORY.md#top-5-cross-project-defects alongside XSS, hardcoded paths, localStorage collision, SE_FLOOR. `.iloc[0]` / `.iloc[-1]` / `.values[0]` raises IndexError on empty filter results. Sentinel can't see upstream guards (`if df.empty`, `len(df) > 0`, early-return), so the rule is WARN — surfaces unchecked positional accesses for human review. Fix at point of use: guard before, OR use `.iat[0]` after a length check, OR add `sentinel:skip-file` if the file is provably non-empty by upstream contract.

## Editorial / Authorship Disclosure (learned 2026-04-15)
- **Editor-board author needs structural separation, not just disclosure**: Disclosure-only ("MA on editorial board") is necessary but insufficient when an author also serves on the journal's editorial board. The credible-handling guarantee comes from ALSO removing the author from first/last (senior) author positions on submissions to that journal — middle-author only — so the author has no positional claim to interpretive primacy. Apply to E156 (Synthēsis), and to any future workbook where a journal-board overlap exists. Disclosure wording must include (a) editorial-board membership of the target journal, (b) explicit "no role in editorial decisions on this manuscript", (c) confirmation that handling was done by an independent editor of the journal. Use the journal's exact name (e.g. `Synthēsis` with macron, not `Synthesis`).
