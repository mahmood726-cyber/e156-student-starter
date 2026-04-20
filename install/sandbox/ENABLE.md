# Enabling Windows Sandbox — one-time, requires admin + reboot

Your automated Claude session **cannot** enable Windows Sandbox on its own:
the DISM/`Enable-WindowsOptionalFeature` call requires an elevated PowerShell
and then a reboot. This file documents the exact steps so you can run them
yourself in 30 seconds, and then the automated smoke in `smoke.wsb` will work.

## Prerequisites (check once)

- Windows 10 Pro/Enterprise or Windows 11 Pro/Enterprise (not Home)
- Hardware virtualization enabled in BIOS (Intel VT-x / AMD-V)
- At least 4 GB RAM, 1 GB free disk

## Enable the feature

1. Press `Win` → type `powershell` → **right-click** "Windows PowerShell" → **Run as administrator**
2. Paste and run exactly this:

```powershell
Enable-WindowsOptionalFeature -Online -FeatureName Containers-DisposableClientVM -All
```

3. The command will prompt `Do you want to restart the computer to complete this operation now?`. Type `Y` and press Enter. Your machine reboots.

## Verify it worked (after reboot)

Open a normal (non-elevated) PowerShell and run:

```powershell
Get-Command WindowsSandbox.exe
```

You should see a source path like `C:\Windows\System32\WindowsSandbox.exe`. If
you get an error, the feature didn't install — re-run step 2 and check for
errors there.

## Run the automated smoke

Once Sandbox is available:

1. Download the latest release zip + `RELEASE-HASH.txt` from
   <https://github.com/mahmood726-cyber/e156-student-starter/releases> into
   `C:\Users\<you>\Downloads\`.
2. Double-click `D:\e156-student-starter\install\sandbox\smoke.wsb`.
3. Sandbox boots in ~20 s, `run_smoke.ps1` executes automatically, log lands
   at `D:\e156-student-starter\install\sandbox\smoke-out\smoke.log` on the
   HOST (mapped read-write from inside the Sandbox).

## What the smoke covers vs. still needs human eyes

Covered automatically:
- Zip integrity (SHA vs. `RELEASE-HASH.txt`)
- `install.ps1 -DryRun` self-SHA gate
- `Start.bat --what-would-i-do` dispatch
- `student sentinel` on the extracted bundle
- `student memory --force` seeds the pack

Still requires human eyes (the remaining Task 18 checks):
- SmartScreen warning behaviour on the extracted `Start.bat`
- Visual progress display during the actual 2–10 GB model download
- Typing name/email/AGREE in the first-run wizard (interactive, not scripted)
- `help-me-pick` wizard + scaffold into a T0 paper
