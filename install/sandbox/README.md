<!-- sentinel:skip-file — instructional doc showing example Windows paths -->
# Windows Sandbox automated smoke

Runs the e156 release zip through a scripted install inside a Windows Sandbox
VM — no host-state bleed. Useful for CI-adjacent validation on a dev machine
and for release-candidate sanity checks before tagging final.

## One-time setup

Windows Sandbox needs to be enabled. In an **elevated** PowerShell:

```powershell
Enable-WindowsOptionalFeature -Online -FeatureName Containers-DisposableClientVM -All
```

Restart Windows. Afterwards `WindowsSandbox.exe` should be on PATH.

Requirements: Windows 10/11 Pro or Enterprise, virtualization enabled in BIOS,
4+ GB RAM, ~1 GB free disk.

## Running the smoke

1. **Download the release zip** (and `RELEASE-HASH.txt` if you want integrity
   cross-check) from
   <https://github.com/mahmood726-cyber/e156-student-starter/releases> to
   `C:\Users\<you>\Downloads\`.

2. **Double-click `smoke.wsb`** (or `Open with → Windows Sandbox`).

3. The Sandbox boots in ~20 seconds. `run_smoke.ps1` runs automatically and:
   - Verifies the zip SHA against `RELEASE-HASH.txt` (if present).
   - Extracts the zip to `C:\e156-extract\`.
   - Runs `install.ps1 -DryRun` to exercise the self-SHA gate.
   - Runs `Start.bat --what-would-i-do` to confirm dispatch logic.
   - Runs `student sentinel` against the extracted bundle.
   - Runs `student memory` to confirm the starter pack seeds correctly.

4. **Read results** on the host at `smoke-out/smoke.log` (mapped read-write
   into the Sandbox). No need to copy anything by hand — the log is already
   on your D: drive after Sandbox exits.

5. **Close the Sandbox** (just `X` out). All Sandbox state vaporises; your
   host is untouched.

## What this covers vs. Task 18 manual smoke

Covers:
- Zip integrity (SHA of shipped artifact matches RELEASE-HASH.txt)
- install.ps1 self-SHA gate survives extraction
- CLI dispatch logic (Start.bat, install.ps1 -DryRun)
- `student` subcommands work on the shipped layout
- Memory starter pack seeding works end-to-end

Does **not** cover (still needs human eyes):
- SmartScreen warning behaviour on first launch
- Visual UX (is the install window friendly? is the progress display clear?)
- Interactive wizard typing (name, email, typed AGREE)
- Full Ollama model pull (needs host-scale network + disk)
- First-run → help-me-pick → T0 scaffold flow end-to-end

For those, follow Task 18's 10-step checklist in
`docs/superpowers/plans/2026-04-19-plan-A-install-first-touch.md`.

## Troubleshooting

- **"WindowsSandbox.exe not found"** — feature not enabled; see One-time setup.
- **Sandbox boots but LogonCommand doesn't run** — check the host path in
  `smoke.wsb` matches where you've extracted the repo on disk.
- **"no release zip found in Downloads"** — download the zip first, then
  re-open `smoke.wsb`.
