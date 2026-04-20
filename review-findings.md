<!-- sentinel:skip-file — review doc discusses the exact patterns rules catch -->
## Multi-Persona Design Review: e156-student-starter bundle

### Date: 2026-04-19
### Summary: 25 P0, 22 P1, ~18 P2
### Status: OPEN — pre-implementation design review

**Scope.** Design-time review of the planned expansion of `e156-student-starter`
(single-click Windows bundle for Uganda medical students shipping Gemma/Qwen
via Ollama + validator + Sentinel pre-push hook + 5 project templates +
optional Zenodo data lakes). Reviewed by five personas against existing
scaffold + locked design decisions.

**Personas:** Methodologist (M), Security (S), UX/Accessibility/Pedagogy (U),
Software Engineering/DevOps (E), Domain Expert/Editor (D).

---

## Cross-persona convergent themes

Where multiple personas flagged the same underlying defect, that's the
strongest signal for priority.

1. **Validator is a word-counter, not a quality gate.** `tools/validate_e156.py`
   checks sentences + word count + citation markers. Zero coverage of methods
   linting, authorship rules, COI, placeholder tokens, AI disclosure, ethics
   fields, or reporting-guideline alignment. Flagged by M (P0-1, P0-5), D
   (P0-1, P0-2, P0-3, P1-1, P1-2, P1-3, P1-4). This is THE single biggest
   design gap.

2. **Security/signing chain is absent.** Unsigned `.exe`, no pinned hash, no
   out-of-band verification, no integrity-verified pre-push hook, no CI
   workflow, no code-signing pipeline. Flagged by S (P0-1, P0-2, P0-3) and E
   (P0-2). The current "ship" path teaches students to bypass SmartScreen — a
   trained vulnerability that outlives this project.

3. **LLM trust surface is undefended.** `stats` task routes to prose LLM, cloud
   fallback is silent data egress, env-var secrets live in the same process
   that consumes attacker-controlled text. Flagged by M (P0-2) and S (P0-4,
   P0-5). Indirect prompt injection via PDF/dossier text is the canonical
   exfil path.

4. **"Portable" and "cross-platform" claims are fictions.** Ollama Windows
   build is not truly portable (writes to `%LOCALAPPDATA%`); `install.ps1` and
   `install.sh` are functionally non-equivalent (shell path pipes
   `curl | sh`). Flagged by E (P0-1, P0-4). Matches `lessons.md` "Contract
   Drift" rule.

5. **UX and install funnel are broken before we enhance them.** No progress UI
   on 10 GB model pull, misleading "15-45 min" ETA at 1.5 Mbps, smoke-test
   failure claims success, no friendly-error layer, no SmartScreen guidance.
   Flagged by U (P0-2, P0-3, P0-4, P0-5). The 3-layer UX (dashboard/TUI/CLI)
   I proposed does not exist in the repo — U-P0-1 explicitly calls this
   Contract Drift.

6. **AACT extraction edge cases + snapshot pinning.** Negated-counts
   corruption, drug-name-vs-class, lowercase intervention types, no pinned
   DOI for data snapshots. Flagged by M (P0-4, P1-2, P1-3) and D (P1-6).
   Directly from `lessons.md` 2026-04-15.

7. **Legal / licensing.** Gemma Prohibited Use Policy explicitly restricts
   medical-diagnosis/treatment use — directly relevant to medical students.
   README claims MIT/CC-BY but ships a non-OSI-approved model. Flagged by
   D (P0-4). A real legal hazard if the bundle is USB-redistributed.

---

## P0 — Critical (ship-blockers, 25 items)

### Methodologist
- **M-P0-1** Validator has zero statistical scope; 156-word body can PASS format
  while being numerically wrong. Fix: `methods_lint` pass enforcing DL-with-k<10
  block, HKSJ df check, OR→SMD constant, zero-cell correction.
- **M-P0-2** `ai_call.py` line 214-217: `stats` task aliased to `prose` → Gemma
  will confidently hand students wrong formulas. Fix: `stats` routes to
  pinned R-backed tool (metafor/meta via Rscript), never degrades to LLM.
- **M-P0-3** Template 4 (MA replication) will publish SKIP-as-PASS if baseline
  fixture missing. Fix: fail closed on missing baseline; never render `|Δ| = NA`.
- **M-P0-4** Negated-counts corruption: Qwen-written regex `(\d+) randomized`
  matches `Not Randomized 1,807`. Fix: ship vetted `aact_safe_extract.py`
  with negation-lookbehind; validator BLOCKs un-guarded regexes.
- **M-P0-5** Placeholder tokens (`{{...}}`, `REPLACE_ME`, `TBD`) can ship in
  a 156-word body. Fix: add `_SHIPPING_BLOCKERS` regex set to validator.
- **M-P0-6** Zero-cell 0.5 correction and Fisher-z r=±1 clamp invisible to
  validator. Fix: reference implementation in `tools/stats_helpers.py`;
  templates import from it.

### Security
- **S-P0-1** Unsigned `.exe` teaches "Run anyway" as muscle memory. Fix: buy
  EV/OV cert (~$200/yr via Azure Trusted Signing is cheapest solo-author path)
  OR drop `.exe` entirely, ship zip-portable only.
- **S-P0-2** No pinned hash + no out-of-band verification. Fix: publish SHA256
  + minisign/Sigstore sig on (i) Synthesis journal page, (ii) DOI'd Zenodo
  record, (iii) different GitHub repo. Students verify against out-of-band
  value, not the release page itself.
- **S-P0-3** `E156_DRAFT=1` bypass silently-disableable by any post-install
  script. Fix: integrity-verified pre-push hook; bypass requires interactive
  `--i-understand` token; log bypass events append-only.
- **S-P0-4** `ai_call.py` reads `GITHUB_TOKEN`/`GEMINI_API_KEY` into same
  process as attacker-controlled text. Indirect prompt-injection exfil
  vector. Fix: drop secrets via `os.environ.pop` before model-call
  subprocess; cloud fallback in subprocess with env allowlist; outbound
  HTTP domain allowlist.
- **S-P0-5** Cloud fallback is silent data egress (potential Uganda DPA 2019
  breach). Fix: opt-in per install via `student ai enable-cloud
  --i-understand-egress`; every cloud call prints `[CLOUD→Gemini]` warning;
  task types `patient`/`ipd`/`dossier` hard-blocked from cloud.
- **S-P0-6** Zenodo downloader lacks pinned hash + DOI-typo exploitable.
  Fix: DOI is constant in code (not student input); file-level SHA256 at
  release time; refuse HTTP redirects to non-zenodo.org hosts; no symlink
  extraction.

### UX/Accessibility/Pedagogy
- **U-P0-1** Dashboard, TUI, and 5-card template picker do NOT exist in repo.
  Contract drift. Fix: either implement minimal stdlib `http.server`
  dashboard with one dominant "Start my first paper" CTA and scope other 4
  cards to P2, OR rewrite spec + README to match what actually ships
  (CLI-only).
- **U-P0-2** SmartScreen funnel not addressed; README.md:37-40 just says
  `.\install\install.ps1` with no ExecutionPolicy note. Fix: add 3-line "If
  Windows blocks this" callout at README:41; `install.ps1:31` self-checks
  `Get-ExecutionPolicy` and prints remedy before throwing.
- **U-P0-3** 10 GB model pull has no progress UI and no honest ETA;
  README:57 claims "15-45 minutes" which is a lie at 1.5 Mbps (10 GB ≈ 15h).
  Fix: wrap `ollama pull` with progress parser; print ETA in plain English;
  correct README:57 time range.
- **U-P0-4** Smoke-test failure is a dead end; `install.ps1:177-190`
  continues to `=== INSTALL COMPLETE ===` on smoke fail. Fix: gate success
  banner on smoke exit-0; write `diagnostic.zip` on fail; link to
  `docs/troubleshooting.md`.
- **U-P0-5** No plain-English translation for errors. `troubleshooting.md:4-9`
  literally tells students they'll see `Ollama not reachable at
  http://127.0.0.1:11434`. Fix: `friendly_error.py` maps ECONNREFUSED,
  404 model, 401 to plain-English remediation.

### Engineering/DevOps
- **E-P0-1** "Portable Ollama" is a fiction — `install.ps1:75` unzips to
  `D:\ollama` but Ollama Windows build writes to `%LOCALAPPDATA%\Programs\
  Ollama` and registers tray icon. USB-copy fails silently. Fix: pin
  known-portable Ollama release; use relative `OLLAMA_HOME`; test USB
  relocation in CI; or document "portable-ish" honestly.
- **E-P0-2** No code-signing pipeline; no `.github/workflows/` exists at
  all. `.exe` + Inno Setup + Zenodo pull claimed in spec, all unimplemented.
  Fix: `.github/workflows/release.yml` with Azure Trusted Signing (~$10/mo,
  no HW token) + pinned Inno Setup action.
- **E-P0-3** No resumable download for model weights; no retry/rollback on
  70%-failed pull leaving corrupt blob. Ollama then crashes on next start
  (known upstream bug). Fix: retry-with-bounded-backoff, `ollama list`
  digest verification, delete-on-partial-fail.
- **E-P0-4** `install.sh:58` pipes `curl | sh` from ollama.com. Supply-chain
  exposure + functionally non-equivalent to Windows path. Fix: pin SHA256
  for Linux installer; OR drop `install.sh` entirely (Windows-only is
  locked decision anyway).

### Domain Expert/Editor
- **D-P0-1** Authorship rule is prose-only (README:84-86). Validator has zero
  author logic. Example `your_rewrite.txt` has no metadata block at all.
  Fix: ship `templates/submission_metadata.md` mirroring workbook format;
  `validate_e156.py --submission` refuses pass if first==MA, last==MA, or
  supervisor field is TBD/empty.
- **D-P0-2** `TBD - request mentor` placeholder is a forgery channel
  (README:77-78). Fix: hard-fail validator on `TBD|REPLACE_ME|{{.*}}|
  request mentor` in metadata.
- **D-P0-3** Editorial-board COI statement not auto-inserted. Per
  `feedback_e156_authorship.md`, every submission requires the exact
  "MA serves on editorial board..." paragraph. Bundle never emits it;
  validator doesn't check. ICMJE/COPE-complaint-grade defect.
- **D-P0-4** Gemma 2 license incompatibility. README:147-148 claims
  MIT+CC-BY-4.0 but ships `gemma2:9b` under Google's Gemma Terms of Use +
  Prohibited Use Policy, which explicitly restricts medical-diagnosis/
  treatment use — directly relevant to medical students! USB redistribution
  (`docs/airgap.md:43`) likely breaches redistribution terms. Fix: surface
  license; README warning: "Gemma prose must be human-rewritten; MUST NOT
  be used for clinical decision making."

---

## P1 — Important (22 items)

### Methodologist
- **M-P1-1** 50 MB AACT starter slice can't support Template 1 for most
  conditions — k=2 pools give CI dominated by τ² prior.
- **M-P1-2** Template 2 students will search by class (`'%SGLT2%'`) not
  drug name; silent 0-row failure.
- **M-P1-3** Lowercase intervention types in AACT (`'drug'` not `'Drug'`).
- **M-P1-4** HR without PH check, RMST without τ*, I² misinterpreted as
  "high/low heterogeneity" in S5.
- **M-P1-5** Synthesis editorial-board COI not enforced by bundle.
- **M-P1-6** Sentinel rule P1-empty-dataframe-access must ship enabled in
  student bundle, not just core Sentinel's 6 YAML rules.

### Security
- **S-P1-1** `.env` leak via `git add .`. Fix: template `git init` commits
  `.gitignore` as first commit; Sentinel rule for GITHUB_TOKEN patterns
  blocks at COMMIT not just push.
- **S-P1-2** `diagnostic.zip` PII leakage (username paths, email, patient
  identifiers). Fix: redactor runs before zip; show student contents
  before upload.
- **S-P1-3** `OLLAMA_HOST=0.0.0.0` foot-gun. Fix: installer writes
  127.0.0.1 user-scope; Windows Firewall rule denying inbound on 11434;
  README never shows 0.0.0.0.
- **S-P1-4** HMAC key sourcing in Sentinel bundle (lessons.md). Fix:
  per-install key in `%LOCALAPPDATA%\e156\sentinel.key` (0600).
- **S-P1-5** No auto-update = stale Ollama CVEs; auto-update = fleet RCE.
  Fix: notify-only updater with signed manifest; never auto-install.

### UX/Accessibility
- **U-P1-1** Template card overload without "Help me pick" wizard.
- **U-P1-2** Graduation prompt unspecified.
- **U-P1-3** Sentinel block messages are raw; need student wrapper.
- **U-P1-4** No `get_unstuck.py` / diagnostic.zip / mentor mailto.
- **U-P1-5** Locale: no DD/MM/YYYY for 42-day deadline display.
- **U-P1-6** README hardware table misleads 4GB users; `install.ps1:115-118`
  silently `-LowRam` but still pulls 2GB+ onto unusable 4GB laptop.
- **U-P1-7** `install.ps1:172` `Set-Content -Encoding UTF8` writes BOM on
  Windows PowerShell 5.1; Python dotenv parsers choke.

### Engineering
- **E-P1-1** No Zenodo integration anywhere in repo — entire data-pull
  feature is vapor. 40 students × 16 GB concurrent = Zenodo throttle. Fix:
  mirror on Cloudflare R2 (free egress ≤10 TB/mo); `aria2c -c` resumable.
- **E-P1-2** No dependency pinning; `releases/latest` at install.ps1:75.
  Fix: `config/pins.json` with Ollama + model digests.
- **E-P1-4** Working-directory ambiguity; `install.ps1:65` hardcodes D:\;
  `install.sh:18` may be OneDrive-synced. Fix: `%LOCALAPPDATA%\e156`;
  warn on OneDrive detection.
- **E-P1-5** Python not bundled; student's system `python` with
  `scipy` + 3.13 = WMI deadlock. Fix: bundle embedded Python 3.11.
- **E-P1-6** No CI/build reproducibility; supervisor can't rebuild.
- **E-P1-7** No update mechanism for `rules/` — stale rules day 180.
- **E-P1-8** Log hygiene; install has no log file; `serve.log` never
  rotated; crash bundles may leak token substrings.

### Domain Expert
- **D-P1-1** No IRB/ethics field enforcement; Template 3 burden-snapshot in
  Uganda → chart-review without IRB.
- **D-P1-2** AI disclosure absent; ICMJE Dec 2023 violation.
- **D-P1-3** Reporting-guideline fit (PRISMA/CONSORT/STROBE) not
  addressed; Synthesis Methods-Note exemption undocumented.
- **D-P1-4** No GRADE / certainty-of-evidence hook for S5.
- **D-P1-5** No pre-registration scaffold; garden-of-forking-paths.
- **D-P1-6** Data-snapshot DOI not pinned; irreproducible.
- **D-P1-7** No duplicate-submission / plagiarism check against the
  485-entry workbook.

---

## P2 — Minor (~18 items)

Selected highlights (full list in persona outputs):

- **U-P2-2** README references `docs/getting-started.md` which does not exist.
- **U-P2-3** README:74 E156 student board is networked dep; cache at install.
- **U-P2-4** Example walkthrough has no "expected output" blocks.
- **U-P2-5** No "what it looks like if it went wrong" contrast panel.
- **U-P2-7** `install.sh:58` `curl | sh` pattern — see S-P0-1 and E-P0-4.
- **E-P2-1** `tiny_model_benchmark.py` marks prose PASS with 200-word cap,
  laxer than validate_e156's 156-word spec.
- **E-P2-3** `results_050b_baseline.json` committed as generated artifact;
  move to `tests/fixtures/`.
- **E-P2-5** No SHA verification on Ollama zip download.
- **E-P2-6** User-scope env vars not cleaned up on uninstall.
- **D-P2-1** ORCID onboarding not guided.
- **D-P2-6** `validate_e156.py` sentence splitter brittle on abbreviations.
- **M-P2-4** Clopper-Pearson alpha/2 — do NOT lint this; agents false-flag
  it (per `lessons.md`).

---

## False Positive Watch (per lessons.md — do NOT re-flag)

- DOR = exp(μ1 + μ2) IS correct
- Clayton copula theta = 2·tau/(1−tau) IS correct
- Clopper-Pearson uses α/2 (two-sided) IS correct
- qbeta/pchisq may be defined elsewhere — grep before claiming missing
- Bootstrap arrays may be sorted elsewhere

---

## Top-3 design-reshaping recommendations

Before moving to Section 2 (Components), the design must absorb these three:

1. **Validator expansion.** `validate_e156.py` becomes a composite gate:
   (a) format lint (existing), (b) methods lint, (c) placeholder lint,
   (d) authorship/metadata lint, (e) COI lint, (f) AI-disclosure lint,
   (g) data-DOI lint, (h) ethics-field lint, (i) pre-registration check,
   (j) duplicate-submission check. Each is a pluggable pass; student sees
   a unified PASS/BLOCK/WARN report.

2. **Security chain.** Every release is signed (Azure Trusted Signing);
   every artifact has a pinned SHA256 published out-of-band on Synthesis
   journal page; every env-var secret is isolated from LLM-consuming
   processes; every cloud call is opt-in per-install with consent record.
   Without this, we do not ship — even to a pilot cohort.

3. **Honesty on UX + Ollama portability.** Either implement the dashboard/
   TUI as described or strike them from the spec. Either verify portable
   Ollama works on a fresh USB-copied Windows install or document
   "portable-ish" honestly. Contract drift between README and code is the
   single most lesson-repeated mistake in the portfolio.

---

*Next action: user decides which P0 findings reshape the component design
(Section 2 of brainstorming) before writing the spec doc.*
