# Design — `e156-student-starter` v0.2 (Uganda student bundle)

**Date:** 2026-04-19
**Author:** Mahmood Ahmad (with Claude Opus 4.7)
**Status:** Spec locked; ready for implementation-plan phase
**Target cohort:** Uganda medical students (MBChB-level, first-time coders)
**Downstream consumer:** *Synthēsis* journal (Methods Notes)
**Primary location:** `D:\e156-student-starter\docs\superpowers\specs\2026-04-19-uganda-student-bundle-design.md`
**Backup location (this file):** `C:\Users\user\e156-student-starter-spec-backup\` — written because D: drive flapped after the primary write
**Source review:** `D:\e156-student-starter\review-findings.md` (25 P0, 22 P1 across 5 personas)

> **User's final constraint (2026-04-19):** *"decide all for me and proceed but make sure install and usage is really easy."*
>
> This spec is designed around that constraint. The "ease" decisions are:
> D3 (zip-only, no .exe), C1 (Start.bat double-click — student never sees
> PowerShell), C3 (first-run wizard with plain-English prompts + typed
> AGREE gates), C4 (help-me-pick template wizard — 3 yes/no questions),
> C8 (friendly-error translation layer — no stack traces ever reach the
> student), C14 (TUI curses menu when `student` is run with no arguments —
> arrow keys, Enter, Esc), C15 (one-button Get-unstuck that redacts PII
> and opens a pre-populated mailto). All six are in **Plan A** — the first
> thing that ships. Ease is a Plan A correctness requirement, not a
> polish pass.

---

## 1. Summary

A zip-portable, Windows-only bundle that lets medical students with no
coding background produce format-valid, methodologically-linted, policy-
compliant E156 micro-papers using local Gemma 2 + Qwen 2.5 Coder models,
with optional Zenodo-hosted data lakes (AACT, WHO, WB, IHME). Ships a
first-run wizard, a `student` CLI with `curses` menu, a 10-pass composite
validator, an integrity-locked Sentinel pre-push hook, and a diagnostic
bundler for supervisor handoff.

The bundle explicitly does NOT ship a web dashboard in v0.2 (deferred to
v0.3 after 2-3 student pilots validate the CLI/TUI UX). It also does NOT
ship an `.exe` installer — only a signed `.zip` whose SHA256 is published
out-of-band on the Synthēsis journal landing page.

## 2. Locked decisions

| # | Decision | Answer |
|---|---|---|
| D1 | Operating system | Windows only |
| D2 | Hardware | Auto-detect tier: 4 GB (cloud-only), 8 GB (Gemma 2B + Qwen 1.5B), 16 GB+ (Gemma 9B + Qwen 7B) |
| D3 | Delivery format | `.zip` portable only; `Start.bat` entry point; no `.exe` / no code-signing |
| D4 | Data lakes | Zenodo-hosted full snapshots (pinned DOI per release) + ~50 MB bundled starter slice |
| D5 | Pre-upload testing | `student validate` CLI **and** integrity-locked pre-push Sentinel hook (block P0/P1, warn P2, explicit `--i-understand` bypass) |
| D6 | UX layers | v0.2: CLI + `curses` TUI menu (no-arg `student`) + first-run wizard. v0.3: add web dashboard after pilot |
| D7 | Dashboard default (v0.3) | Default on for first 5 launches, then graduation prompt stored in `~/e156/.prefs.json` |
| D8 | Project templates | Five: (T1) pairwise mini-MA, (T2) trials audit, (T3) burden snapshot, (T4) MA replication, (T5) living-MA seed. Plus hidden T0 blank template |
| D9 | Gemma license | Ship as-is + explicit Gemma Prohibited Use Policy file + plain-English "do not use for clinical decisions" banner shown at first run (student types `AGREE`) |
| D10 | Cloud fallback consent | Default disabled. Opt-in via `student ai enable-cloud --i-understand-egress` with typed `AGREE`. Per-call `[CLOUD→...]` warning. Hard-block on task types `patient`/`ipd`/`dossier`/`raw_case` regardless of consent |
| D11 | Integrity | SHA256 pinned and published out-of-band on Synthesis landing page; students verify with `Get-FileHash`. No code-signing cert |
| **D12** | **Ease-of-use priority** | **"Install and usage must be really easy" is a Plan A correctness requirement. Every ease component (Start.bat, first-run wizard, help-me-pick, friendly errors, TUI, get-unstuck) ships in v0.2 first batch, not later.** |

## 3. Architecture

### 3.1 Distribution and install

```
GitHub Release  mahmood726-cyber/e156-student-starter
   │
   └─ e156-student-starter-v0.2.0.zip  (≈50 MB)
      │
      ▼
   student downloads, right-click → Extract All → double-click Start.bat
      │
      ▼
Start.bat calls: powershell -ExecutionPolicy Bypass -File install\install.ps1
      │
      ▼
install.ps1:
   1. verify self-SHA256 against value pinned in docs/HASH.txt
      and cross-check with synthesis-medicine.org/e156-hash.txt
   2. detect RAM → pick tier
   3. pull portable Ollama (pinned version, pinned SHA256)
   4. pull tier-matched models (pinned digests)
   5. write ~/e156/ layout
   6. install integrity-locked pre-push hook into ~/e156/workbook/.git
   7. run smoke_test.py (gates install-complete banner)
   8. launch first-run wizard
```

### 3.2 Installed layout (`%LOCALAPPDATA%\e156\`)

```
~/e156/                                (= %LOCALAPPDATA%\e156\)
├── ai/                                 AI router + cloud subprocess + friendly errors
│   ├── ai_call.py
│   ├── cloud_subprocess.py            isolated; only process that sees GITHUB_TOKEN
│   └── friendly_error.py
├── bin/
│   ├── student.bat                    PATH-friendly entry point
│   ├── student.py                     CLI; curses TUI when called without args
│   └── ollama/                        portable Ollama runtime
├── config/
│   └── pins.json                      every dependency pinned (SHA256 + version)
├── data/
│   ├── starter/                       ~50 MB slice bundled in zip
│   ├── aact/                          empty; populated by `student data pull aact`
│   ├── who/
│   ├── wb/
│   └── ihme/
├── docs/                               read-only; refreshable via `student rules refresh`
├── examples/
│   └── example_paper_01/              30-minute walkthrough
├── logs/                               rotated; scrubbed before diagnostic.zip
├── models/                             Ollama model store (or relative link)
├── rules/                              read-only; refreshable
├── templates/
│   ├── T0_blank/
│   ├── T1_pairwise_mini_ma/
│   ├── T2_trials_audit/
│   ├── T3_burden_snapshot/
│   ├── T4_ma_replication/
│   └── T5_living_ma_seed/
├── tools/
│   ├── validate.py                    composite 10-pass gate
│   ├── lints/                         pluggable per-pass linters
│   ├── stats_helpers.py               R-metafor-validated reference impls
│   ├── aact_safe_extract.py           negation-lookbehind safe scraper
│   ├── data_pull.py                   Zenodo downloader
│   └── get_unstuck.py                 diagnostic bundler + redactor
├── workbook/                           student's git repo (their papers)
├── .consent.json                       cloud consent + bypass-acknowledged
└── .prefs.json                         UI preferences (v0.3)

%LOCALAPPDATA%\e156-sentinel-lock\
└── sentinel.lock                       pre-push hook SHA256; only install.ps1
                                        can write this (integrity lock)
```

### 3.3 Daily-use entry points

```
No arguments                    student                 → curses TUI menu
New paper                       student new [--template T1|T2|T3|T4|T5]
Help picking a template         student new --help-me-pick
AI assistance                   student ai <task> "..."
Data lake pull                  student data pull aact|who|wb|ihme
Validate                        student validate [<paper-dir>]
Diagnostic / unstick            student doctor
Rules refresh                   student rules refresh
Cloud opt-in                    student ai enable-cloud --i-understand-egress
Version                         student --version
```

## 4. Components

Nineteen components (including ease-critical ones). Status column:
**E**xisting (needs reshape), **N**ew, or **R**efactor.

### 4.1 Entry & install — EASE-CRITICAL (5)

| # | Component | Status | Purpose + interface |
|---|---|---|---|
| C1 | `Start.bat` | N | Zip-root launcher. On first run, calls `install.ps1` with `-ExecutionPolicy Bypass`. On subsequent runs, calls `bin\student.bat`. **Student never sees PowerShell.** |
| C2 | `install\install.ps1` | E→R | One-shot bootstrapper. Verifies self-SHA against `docs/HASH.txt` + Synthesis landing page. Detects RAM. Pulls Ollama (pinned). Pulls tier models (pinned digests). Writes `~/e156/` with rollback on partial failure. Installs hook. Gates success banner on smoke-test exit 0. **Progress wrapper parses `ollama pull` output to show plain-English ETA.** |
| C3 | First-run wizard | N | Runs once after install.ps1. Plain-English flow: welcome → name/email → tier chosen → **Gemma Prohibited Use Policy acknowledgement (typed `AGREE`)** → model download with parsed progress + ETA → smoke test → "You're ready. Click here for your first paper." Launches `student new --help-me-pick` |
| C4 | `Help me pick` wizard | N | 3 yes/no questions → recommends T1–T5. Plain-English subtitles, one "recommended" badge, "I'm not sure" button |
| C5 | `install\uninstall.ps1` | N | Removes `~/e156/`, unsets user-scope env vars, removes Firewall rule, removes sentinel.lock. Preserves `workbook/` unless `--purge-papers` |

### 4.2 AI router (3)

| # | Component | Status | Purpose + interface |
|---|---|---|---|
| C6 | `ai\ai_call.py` | E→R | Task-typed router. **Post-review changes:** (a) `stats` task REFUSES to run, points to `tools/stats_helpers.py` + Rscript; (b) secret env vars `GITHUB_TOKEN` / `GEMINI_API_KEY` dropped from parent process before any model call; (c) cloud path spawns `cloud_subprocess.py`; (d) reads `~/e156/.consent.json` before cloud call; (e) hard-blocks `patient`/`ipd`/`dossier`/`raw_case` from cloud regardless; (f) prints `[CLOUD→Gemini]` warning per call; (g) all student-facing errors routed through `friendly_error.py` |
| C7 | `ai\cloud_subprocess.py` | N | Isolated Python subprocess spawned by `ai_call.py` for cloud calls. Only process with `GITHUB_TOKEN`/`GEMINI_API_KEY` in env. Outbound HTTP uses domain allowlist (`api.github.com`, `generativelanguage.googleapis.com` — nothing else). JSON IPC with parent. Refuses HTTP 3xx redirects to non-allowlisted hosts |
| C8 | `ai\friendly_error.py` — EASE-CRITICAL | N | Single translation layer. Maps common raw errors (ECONNREFUSED :11434, HTTP 404 model, HTTP 401, PS ExecutionPolicy, Ollama port collision, disk-full, SHA-mismatch, consent-required) to plain-English single-line remediation. Every student-facing error passes through this; raw trace goes to `~/e156/logs/` |

### 4.3 Validator (3)

| # | Component | Status | Purpose + interface |
|---|---|---|---|
| C9 | `tools\validate.py` | N | Composite gate. Usage: `student validate [paper]` or `--submission`. Runs 10 lints in order, produces unified JSON + human-readable `validation-report.md`. Exit codes: 0=PASS, 1=BLOCK (P0/P1), 2=WARN (P2). Each lint is a pluggable module under `tools/lints/`. **Plain-English report: "Your paper isn't ready yet because: <specific reason>. Fix: <one action>."** |
| C10 | `tools\lints\*` | E→R+N | Ten modules: `format_lint.py` (existing `validate_e156.py` logic), `placeholder_lint.py` (`TBD`, `REPLACE_ME`, `{{...}}`, `request mentor`), `methods_lint.py` (DL k<10, HKSJ df, OR→SMD 0.5513, Fisher-z 1/(n-3), zero-cell, log-scale pooling), `authorship_lint.py` (first≠MA, last≠MA, supervisor not placeholder, ORCID present), `coi_lint.py` (Synthesis editorial-board paragraph verbatim), `ai_disclosure_lint.py` (ICMJE Dec 2023), `data_doi_lint.py` (pinned DOI present), `ethics_lint.py` (typed enum), `prereg_lint.py` (git SHA of `preanalysis.md` recorded before data pull), `dedup_lint.py` (5-gram shingle overlap <40% against 485-entry workbook) |
| C11 | `tools\stats_helpers.py` | N | Reference implementations validated against R `metafor` at tolerance 1e-6. Covers: DL/REML pooling, HKSJ with t-df and Q/(k-1) floor, OR→SMD conversion with constant 0.5513, Fisher-z with r clamp to ±0.9999, logit clamp to [1e-10, 1−1e-10], Haldane 0.5 correction applied only if any zero cell, PI formula `t_{k-2}`, empty-DF safe `.iat` wrappers |

### 4.4 Data + safe scrapers (2)

| # | Component | Status | Purpose + interface |
|---|---|---|---|
| C12 | `tools\aact_safe_extract.py` | N | Wraps common AACT extraction patterns with negation-lookbehind for `not\|non\|never` within 30 chars. Used by T1, T2, T5 scaffolds. Unit-tested with the "Not Randomized 1,807" corpus from `lessons.md` 2026-04-15 |
| C13 | `tools\data_pull.py` | N | `student data pull aact\|who\|wb\|ihme`. Reads DOI from `config/pins.json` (not student input). Resumable via urllib + Range header with SHA verify chunks. Refuses HTTP redirects off `zenodo.org`. No symlink extraction. Writes `~/e156/data/<lake>/snapshot.json` with DOI + SHA + fetch date + byte count. **Plain-English progress + honest ETA.** |

### 4.5 Student CLI + diagnostic — EASE-CRITICAL (2)

| # | Component | Status | Purpose + interface |
|---|---|---|---|
| C14 | `bin\student.py` | N | Single CLI entry point. Subcommands: `new`, `ai`, `data`, `validate`, `rules`, `doctor`, `help`, `--version`. **When called with no args, opens `curses` TUI menu with the same actions as clickable rows. TUI has a "Show me the command" option that copies the equivalent CLI invocation to clipboard (teaches CLI gradually).** |
| C15 | `tools\get_unstuck.py` — EASE-CRITICAL | N | Student clicks "Get unstuck" or runs `student doctor`. Gathers: install log, last 50 lines of `serve.log`, `ollama list`, `python --version`, RAM/disk, consent state, git status of workbook. Runs redactor: strips `%USERPROFILE%` → `~`, scrubs `ghp_*`/`AIza*` patterns, strips git `user.email`. **Shows student redacted zip CONTENTS before offering to open pre-populated mailto (`mentors-e156@...`)** |

### 4.6 Project templates (1, containing 6)

| # | Component | Status | Purpose + interface |
|---|---|---|---|
| C16 | `templates/T0`–`T5` | N | Each template directory copied by `student new --template TN`. Contains: `scaffold.py` (copy logic), `README.md` (one-paragraph plain-English purpose + success-criteria checklist), `example.ipynb` + `example.txt` (guided walkthrough — runs in Jupyter or terminal), `analysis.py` with `# TODO(student): ...` markers, `e156_body.md` with `{{S1_QUESTION}}` tokens the validator rejects, `preanalysis.md` blank template (must be committed before `student data pull`), starter-slice data subset (~5-10 MB). T0 hidden behind "I know what I'm doing" button |

### 4.7 Build, hook, pins (3)

| # | Component | Status | Purpose + interface |
|---|---|---|---|
| C17 | `config\pins.json` | N | Every external dep pinned: Ollama version + SHA, per-model digest, per-lake Zenodo DOI + SHA + byte count, Python embed version + SHA, bundle-release self-SHA written at build time. Single source of truth |
| C18 | `.github\workflows\release.yml` | N | Fresh `windows-2022` runner. Steps: checkout → assemble `~/e156/` layout → bundle portable Python 3.11 embed + Ollama → zip → compute SHA256 → update `pins.json` with self-SHA → attach `.zip` + `pins.json` + `HASH.txt` + `review-findings.md` to GitHub Release → write SHA to a gist in a **different** repo (out-of-band verification source) → post reminder to manually update Synthesis landing page hash |
| C19 | Pre-push hook (integrity-locked) | N | Installed by `install.ps1` into `~/e156/workbook/.git/hooks/pre-push`. On every run, verifies its own SHA256 against `%LOCALAPPDATA%\e156-sentinel-lock\sentinel.lock`. Refuses to run if SHAs differ. Invokes `tools/validate.py --submission`. Blocks on exit 1. Bypass is `E156_DRAFT=1` only if `~/e156/.consent.json` has `draft_bypass_acknowledged: true` |

## 5. Data flow

Six principal flows. See primary spec file for full ASCII. Summary:

1. **Install** → Start.bat → install.ps1 (SHA check → tier → pull → layout → hook → smoke → wizard)
2. **Daily use** → `student` TUI → pick template → scaffold → preanalysis commit → analysis (Qwen-assisted) → body → validate → git push (hook re-validates)
3. **AI call** → task type check (patient/ipd/dossier hard-blocked from cloud) → local first → cloud via isolated subprocess with allowlists + per-call warning
4. **Data pull** → read pinned DOI → resumable download → SHA verify → unpack (no symlinks) → write snapshot.json
5. **Pre-push** → hook self-SHA check → validate.py --submission → 10 lints → exit 0 pass, 1 block, 2 warn
6. **Get-unstuck** → gather → redact → show contents → mailto

## 6. Error handling — principles

1. **Every student-facing message passes through `friendly_error.py`.**
2. **Fail closed, not open.** Never degrade silently.
3. **Every error suggests exactly one next action.**
4. **Diagnostic bundle is one keystroke away** from every error state.
5. **Bypass is explicit and audited.** Not env-var-driven.
6. **Log rotation + redaction.**

Full error-class table in primary spec file.

## 7. Security & privacy

- Three-location SHA pin: `docs/HASH.txt`, `pins.json`, `synthesis-medicine.org/e156-hash.txt` (out-of-band)
- Secret isolation: `GITHUB_TOKEN`/`GEMINI_API_KEY` only in `cloud_subprocess.py`, passed via stdin not env
- Domain allowlist: `api.github.com` + `generativelanguage.googleapis.com` only
- Consent gates: cloud default off; typed `AGREE`; per-call warning; task-type hard-blocks
- Hook tamper-resistance: self-SHA check against `%LOCALAPPDATA%\e156-sentinel-lock\sentinel.lock`
- Redactor: strips `%USERPROFILE%`, `ghp_*`, `AIza*`, git email, workbook bodies

## 8. Legal & licensing

- Code: MIT
- Docs, rules, templates: CC-BY-4.0
- Gemma 2: Google Terms of Use + Prohibited Use Policy (ship verbatim + plain-English; student types AGREE)
- Qwen 2.5 Coder: Apache-2.0
- Ollama: MIT
- AACT: CC0; WHO GHO: attribution; WB: CC-BY-4.0; IHME: per-dataset

Gemma Prohibited Use Policy includes "clinical decision support" — directly relevant for med students. Banner is mandatory and acknowledged.

## 9. Testing — three layers

1. **Unit** (per-module, 90% coverage target, R metafor validation at 1e-6)
2. **Integration** (end-to-end install → scaffold → validate → push in Windows Sandbox VM)
3. **Release gate** (windows-2022 CI + 1.5 Mbps bandwidth cap + 5 templates round-trip; branch protection enforces green CI before any release)

## 10. Risks carried forward

- Zenodo throttling → Cloudflare R2 mirror as fallback
- `curses` on Windows → `windows-curses` bundled; plain `input()` fallback
- Ollama portability → pinned version; annual re-verification
- Gemma license changes → monthly CI diff check
- Editorial capacity at Synthesis → v0.3 concern

## 11. Out of scope for v0.2

Web dashboard, supervisor triage queue, real-time supervisor email, ORCID automation, rules auto-update, non-Windows, Copilot OAuth.

## 12. Implementation-plan decomposition — EASE-FIRST ORDERING

Writing-plans phase splits v0.2 into **five sub-plans**. Ordering reflects
the ease-of-use mandate: **Plan A ships everything a brand-new student
touches in their first session, before anything else.** Plans B–E are
quality, security, and scale work that runs in parallel with student
pilots.

1. **Plan A — Install & first-touch UX (EASE-CRITICAL).** Components:
   C1 Start.bat, C2 install.ps1 with progress wrapper, C3 first-run
   wizard, C4 help-me-pick, C8 friendly-error layer, C14 student CLI +
   TUI, C15 get-unstuck, C17 pins.json, C18 CI pipeline. Goal: a first-
   time Uganda student double-clicks Start.bat on a 4–8 GB laptop with
   1.5 Mbps WiFi and, within 45 minutes, is looking at their first
   scaffolded paper with a plain-English next step.

2. **Plan B — AI router hardening.** C6 ai_call.py refactor, C7
   cloud_subprocess.py, consent flow. Goal: secret isolation verified;
   domain allowlist tested with subdomain-attack fixtures; cloud consent
   flow proven; `stats` task refuses LLM routing.

3. **Plan C — Composite validator.** C9 validate.py, C10 ten lints, C11
   stats_helpers.py, C12 aact_safe_extract.py. Goal: 10 lints green on a
   golden corpus; R metafor parity at 1e-6; negated-counts regression
   blocked.

4. **Plan D — Data lakes + get-unstuck polish.** C13 data_pull.py +
   Cloudflare R2 fallback mirror. Goal: Zenodo + R2 pull proven,
   resumable, SHA-verified, redirect-safe.

5. **Plan E — Templates + pre-push hook.** C16 T0–T5 template set, C19
   integrity-locked pre-push hook. Goal: five templates scaffold end-to-
   end with starter-slice data; validator green; hook tamper test passes.

Plans B–E assume Plan A has landed; they reuse C8 friendly-error and
C14 CLI. Plan A is the definition-of-done for a student pilot.

## 13. Open questions (non-blocking)

- [ ] Cloudflare R2 mirror URL/credentials (Plan D)
- [ ] Synthesis OJS endpoint for out-of-band hash (Plan A)
- [ ] Ethics-field enum: fold `IRB_waived_chart_review` under `IRB_waived`? (Plan C)
- [ ] Pre-analysis: OSF Registries now or v0.3? (Plan E)
- [ ] Mentor mailto destination (Plan D)

## 14. Self-review checklist

- ✅ No TBD/REPLACE_ME/XXXX placeholders in this spec
- ✅ All 25 P0 findings from review-findings.md mapped to a component or section (see primary spec Appendix B)
- ✅ Ease-of-use is a Plan A correctness requirement, not a v0.3 polish pass
- ✅ Internal consistency: TUI is v0.2 (curses), dashboard is v0.3 (deferred)
- ✅ Scope: 19 components, but decomposed into 5 independently-shippable plans

---

*Next: invoke `superpowers:writing-plans` with Plan A first (ease-critical).
Plans B–E specified but planned after Plan A lands.*
