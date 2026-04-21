#Requires -Version 5.1
# install.ps1 - E156 student starter bootstrap (Windows)
#
# Run from PowerShell (no admin needed):
#   .\install.ps1                 # CLOUD-ONLY default -- no 1.92 GB Ollama download
#   .\install.ps1 -LocalAI        # opt-in: download Ollama + models for offline use
#   .\install.ps1 -LowRam         # force 4 GB tier (cloud-only, no model pulls)
#   .\install.ps1 -DryRun         # just verify SHA gate, exit 0
#   .\install.ps1 -Import         # dot-source helpers only (used by tests)
#   .\install.ps1 -CloudOnly      # deprecated alias -- same as default
#   .\install.ps1 -NonInteractive # skip the Gemini key prompt (for CI / unattended)
#
# Rationale for cloud-only default (v0.4.1): upstream Ollama Windows zip is
# 1.92 GB. On 5 Mbps residential connections (typical outside major African
# cities) that's 3-15 hours. For most students the cloud-only path -- <2 MB
# install footprint + Gemini free tier -- is the right default. Power users
# with fast connections or offline needs opt in with -LocalAI.

[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$LowRam,
    [switch]$CloudOnly,   # kept for backwards compat; now redundant with default
    [switch]$LocalAI,     # opt into the 1.92 GB Ollama download
    [switch]$NonInteractive,
    [switch]$Import
)

$ErrorActionPreference = 'Stop'

# --- self-SHA verification --------------------------------------------------
# Skipped in -Import mode so tests can dot-source from a tmp dir.
if (-not $Import) {
    $hashFile = Join-Path $PSScriptRoot '..\docs\HASH.txt'
    if (-not (Test-Path $hashFile)) {
        Write-Host "ERROR: docs/HASH.txt not found. This zip may be damaged." -ForegroundColor Red
        Write-Host "Re-download from github.com/mahmood726-cyber/e156-student-starter/releases"
        exit 1
    }
    $expected = (Get-Content $hashFile -Raw).Trim().ToLower()
    $selfSha = (Get-FileHash -Algorithm SHA256 $PSCommandPath).Hash.ToLower()

    if ($expected -ne $selfSha) {
        Write-Host "ERROR: install.ps1 hash mismatch. This file may have been tampered with." -ForegroundColor Red
        Write-Host "Expected: $expected"
        Write-Host "Got:      $selfSha"
        Write-Host ""
        Write-Host "Re-download from github.com/mahmood726-cyber/e156-student-starter/releases"
        Write-Host "and verify against the hash published on synthesis-medicine.org/e156-hash.txt"
        exit 1
    }

    if ($DryRun) {
        Write-Host "Dry run: self-SHA verified. Exiting before any install steps." -ForegroundColor Green
        exit 0
    }
}

# --- helpers (dot-sourceable in -Import mode) ------------------------------

function Select-Tier {
    [CmdletBinding()]
    param([int]$RamGb)

    if ($RamGb -lt 6) {
        return [PSCustomObject]@{
            Name = '4gb-cloud-only'
            ProseModel = $null
            CodeModel  = $null
            CloudOnly  = $true
        }
    }
    if ($RamGb -lt 14) {
        return [PSCustomObject]@{
            Name = '8gb-small'
            ProseModel = 'gemma2:2b'
            CodeModel  = 'qwen2.5-coder:1.5b'
            CloudOnly  = $false
        }
    }
    return [PSCustomObject]@{
        Name = '16gb-big'
        ProseModel = 'gemma2:9b'
        CodeModel  = 'qwen2.5-coder:7b'
        CloudOnly  = $false
    }
}

function Invoke-Rollback {
    [CmdletBinding()]
    param(
        [string]$E156Root,
        [string]$Reason
    )
    Write-Host "Rollback triggered: $Reason" -ForegroundColor Yellow
    if (Test-Path $E156Root) {
        Remove-Item $E156Root -Recurse -Force -ErrorAction SilentlyContinue
    }
    Write-Host "Partial install removed. No changes remain on this laptop." -ForegroundColor Green
}

function Invoke-OllamaPullWithRetry {
    [CmdletBinding()]
    param(
        [string]$Model,
        [string]$ExpectedDigest,
        [scriptblock]$PullFn,
        [int]$MaxAttempts = 3
    )
    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        Write-Host ""
        Write-Host "[$attempt/$MaxAttempts] Downloading $Model... (safe to leave running)" -ForegroundColor Cyan
        $success = & $PullFn
        if ($success) {
            Write-Host "  OK $Model ready." -ForegroundColor Green
            return $true
        }
        if ($attempt -lt $MaxAttempts) {
            $waitSec = 5 * $attempt
            Write-Host "  Retry in $waitSec seconds..." -ForegroundColor Yellow
            Start-Sleep -Seconds $waitSec
        }
    }
    Write-Host "  FAIL $Model after $MaxAttempts attempts." -ForegroundColor Red
    return $false
}

function Invoke-OllamaPullReal {
    [CmdletBinding()]
    param([string]$Model, [string]$OllamaExe)
    try {
        & $OllamaExe pull $Model 2>&1 | ForEach-Object { Write-Host "  $_" }
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Get-BannerForSmokeExit {
    [CmdletBinding()]
    param([int]$ExitCode)
    if ($ExitCode -eq 0) {
        return @"

=================================================
    INSTALL COMPLETE
    Open Start.bat anytime to come back here.
=================================================

"@
    }
    return @"

=================================================
    Installer couldn't reach the AI helper.
    It didn't start. A diagnostic bundle was written
    to ~/e156/diagnostic.zip. Run: student doctor

=================================================

"@
}

if ($Import) { return }   # dot-sourced by tests - no execution

# === Real install flow =====================================================

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Write-Warn2($msg){ Write-Warning $msg }

$bundleRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$e156Root   = Join-Path $env:LOCALAPPDATA 'e156'
$logsDir    = Join-Path $e156Root 'logs'
$ollamaDir  = Join-Path $e156Root 'ollama'
$modelsDir  = Join-Path $ollamaDir 'models'

New-Item -ItemType Directory -Force -Path $e156Root, $logsDir, $ollamaDir, $modelsDir | Out-Null

# --- Step 1: tier detection ------------------------------------------------

$ramGb = [int]((Get-CimInstance Win32_OperatingSystem).TotalVisibleMemorySize / 1MB)
if ($LowRam) { $ramGb = 4 }
$tier = Select-Tier -RamGb $ramGb

# Cloud-only is now the DEFAULT. Local Ollama requires explicit -LocalAI.
# Rationale: 1.92 GB Ollama download is a 3-15 hour blocker on typical
# African student connections. Gemini free tier gives them AI in <2 min.
$cloudOnly = (-not $LocalAI) -or $tier.CloudOnly -or $CloudOnly

Write-Host ""
Write-Host "RAM detected: $ramGb GB. Tier: $($tier.Name)." -ForegroundColor Cyan
if ($cloudOnly) {
    if ($LocalAI) {
        Write-Host "NOTE: -LocalAI passed but RAM is too low for local models. Falling back to cloud." -ForegroundColor Yellow
    } else {
        Write-Host "Mode: cloud AI (Gemini free tier). No Ollama download." -ForegroundColor Green
        Write-Host "      (Re-run with -LocalAI if you want offline / local models.)" -ForegroundColor DarkGray
    }
    $tier = [PSCustomObject]@{ Name = $tier.Name; ProseModel = $null; CodeModel = $null; CloudOnly = $true }
} else {
    Write-Host "Mode: local AI (Ollama + $($tier.ProseModel) + $($tier.CodeModel)). Expect ~1.92 GB download." -ForegroundColor Yellow
}

# --- Step 2: download portable Ollama (skipped in cloud-only mode) -------

$pinsPath = Join-Path $bundleRoot 'config\pins.json'
if (-not (Test-Path $pinsPath)) {
    Write-Host "ERROR: config/pins.json missing. Re-download the bundle." -ForegroundColor Red
    exit 1
}
$pins = Get-Content $pinsPath -Raw | ConvertFrom-Json

$ollamaExe = Join-Path $ollamaDir 'ollama.exe'

if ($cloudOnly) {
    Write-Step "Cloud-only mode: skipping Ollama download (~1.92 GB saved)"
    # fall through to Step 5 (.env) and Step 7 (cloud consent flow)
}

if (-not $cloudOnly) {

# Build the ordered list of (URL, SHA, source) tuples to try.
# Mirror first (content-stable, strict SHA), upstream second (mutable, WARN-not-BLOCK).
# E156_OLLAMA_URL_OVERRIDE short-circuits both for test injection.
if ($env:E156_OLLAMA_URL_OVERRIDE) {
    $ollamaSources = @(@{ Url = $env:E156_OLLAMA_URL_OVERRIDE; Sha = $null; Source = 'override' })
} else {
    $ollamaSources = @()
    if ($pins.ollama.mirror_url) {
        $ollamaSources += @{
            Url    = $pins.ollama.mirror_url
            Sha    = $pins.ollama.mirror_sha256
            Source = 'mirror'
        }
    }
    $ollamaSources += @{
        Url    = $pins.ollama.url
        Sha    = $pins.ollama.sha256
        Source = 'upstream'
    }
}

if (-not (Test-Path $ollamaExe)) {
    Write-Step "Downloading portable Ollama $($pins.ollama.version)"
    $ollamaZip = Join-Path $ollamaDir 'ollama-portable.zip'

    $extracted = $false
    foreach ($attempt in $ollamaSources) {
        Write-Host "  source: $($attempt.Source) -> $($attempt.Url)" -ForegroundColor DarkGray

        # Step A: download
        try {
            try {
                Start-BitsTransfer -Source $attempt.Url -Destination $ollamaZip -Description "Ollama portable ($($attempt.Source))" -ErrorAction Stop
            } catch {
                Invoke-WebRequest -Uri $attempt.Url -OutFile $ollamaZip -UseBasicParsing -TimeoutSec 60
            }
        } catch {
            Write-Warning "Download from $($attempt.Source) failed: $($_.Exception.Message)"
            if (Test-Path $ollamaZip) { Remove-Item $ollamaZip -Force -ErrorAction SilentlyContinue }
            continue
        }

        # Step B: SHA gate (skip for override; mirror = strict; upstream = WARN-not-BLOCK)
        $shaOk = $true
        if ($attempt.Source -ne 'override') {
            $actualSha = (Get-FileHash -Algorithm SHA256 $ollamaZip).Hash.ToLower()
            if ($actualSha -ne $attempt.Sha) {
                if ($attempt.Source -eq 'mirror') {
                    Write-Warning "Mirror SHA mismatch; falling through to upstream."
                    Write-Host "  Expected: $($attempt.Sha)"
                    Write-Host "  Got:      $actualSha"
                    Remove-Item $ollamaZip -Force
                    $shaOk = $false
                } else {
                    # Upstream SHA mismatch -- v0.5.7 mutable-asset reality. WARN-not-BLOCK.
                    Write-Warning "Upstream Ollama zip SHA differs from pinned value."
                    Write-Host "  Expected: $($attempt.Sha)"
                    Write-Host "  Got:      $actualSha"
                    if ($env:E156_OLLAMA_REQUIRE_SHA_MATCH -eq '1') {
                        Invoke-Rollback -E156Root $e156Root -Reason 'Ollama SHA mismatch (strict mode)'
                        exit 1
                    }
                    Write-Host "  Continuing install (strict mode off). Set"
                    Write-Host "  E156_OLLAMA_REQUIRE_SHA_MATCH=1 to enforce byte match."
                }
            } else {
                Write-Ok "SHA verified ($($attempt.Source) = $actualSha)"
            }
        }
        if (-not $shaOk) { continue }

        # Step C: extract. Critical lesson from v0.4.0-rc1 stress test:
        # SHA-match does NOT prove ZIP integrity -- a truncated download can
        # hash-match the previous truncated capture. If Expand-Archive fails
        # with a content-stable source, we know the mirror is corrupt and
        # should fall through to upstream rather than rollback.
        try {
            Expand-Archive -Path $ollamaZip -DestinationPath $ollamaDir -Force -ErrorAction Stop
            Remove-Item $ollamaZip -Force
            Write-Ok "Ollama extracted to $ollamaDir (source: $($attempt.Source))"
            $extracted = $true
            break
        } catch {
            Write-Warning "Extract from $($attempt.Source) failed: $($_.Exception.Message)"
            if (Test-Path $ollamaZip) { Remove-Item $ollamaZip -Force -ErrorAction SilentlyContinue }
            # Clean any partial extracted files before retry
            Get-ChildItem $ollamaDir -Filter "*.dll" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
            Get-ChildItem $ollamaDir -Filter "*.exe" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
            continue
        }
    }

    if (-not $extracted) {
        Invoke-Rollback -E156Root $e156Root -Reason 'All Ollama sources failed download or extract (mirror + upstream).'
        exit 1
    }
} else {
    Write-Ok "Ollama already present at $ollamaExe"
}
}  # end of: if (-not $cloudOnly)  for Step 2

# --- Step 3: env + start ollama serve (skipped in cloud-only mode) -------

if (-not $cloudOnly) {
    [Environment]::SetEnvironmentVariable('OLLAMA_MODELS', $modelsDir, 'User')
    $env:OLLAMA_MODELS = $modelsDir

    $existing = Get-Process ollama -ErrorAction SilentlyContinue
    if (-not $existing) {
        Start-Process -FilePath $ollamaExe -ArgumentList 'serve' -WindowStyle Hidden
        Start-Sleep -Seconds 3
        Write-Ok 'ollama serve started.'
    } else {
        Write-Ok "ollama already running (PID $($existing.Id))"
    }
}

# --- Step 4: pull models with retry ----------------------------------------

if (-not $tier.CloudOnly) {
    foreach ($modelName in @($tier.ProseModel, $tier.CodeModel) | Where-Object { $_ }) {
        $digest = $pins.models.$modelName.digest
        $captured = $modelName
        $pullClosure = { Invoke-OllamaPullReal -Model $captured -OllamaExe $ollamaExe }.GetNewClosure()
        $ok = Invoke-OllamaPullWithRetry -Model $modelName -ExpectedDigest $digest -PullFn $pullClosure
        if (-not $ok) {
            Invoke-Rollback -E156Root $e156Root -Reason "Failed to pull $modelName"
            exit 1
        }
    }
}

# --- Step 5: write .env ----------------------------------------------------

$envFile = Join-Path $e156Root '.env'
$proseLine = if ($tier.ProseModel) { "E156_PROSE_MODEL=$($tier.ProseModel)" } else { "# E156_PROSE_MODEL= (cloud-only mode)" }
$codeLine  = if ($tier.CodeModel)  { "E156_CODE_MODEL=$($tier.CodeModel)" }   else { "# E156_CODE_MODEL= (cloud-only mode)" }
if ($cloudOnly) {
    $ollamaLine = "# OLLAMA_HOST= (cloud-only mode -- no local Ollama)"
} else {
    $ollamaLine = "OLLAMA_HOST=http://127.0.0.1:11434"
}
$envContent = @"
# Auto-generated by install.ps1 on $(Get-Date -Format 'yyyy-MM-dd HH:mm')
$proseLine
$codeLine
$ollamaLine
# Cloud provider keys (filled in by the wizard below, or add by hand):
# GEMINI_API_KEY=AIzaSy...
# GITHUB_TOKEN=ghp_...
"@
[System.IO.File]::WriteAllText($envFile, $envContent, (New-Object System.Text.UTF8Encoding $false))
Write-Ok "Wrote $envFile"

# --- Step 5b: cloud-key wizard (cloud-only default path) ------------------
# Writes .consent.json with cloud_enabled=true + appends GEMINI_API_KEY to .env
# if the student pastes one. Skipped under -NonInteractive (CI) and when
# stdin isn't a TTY (piped or redirected -- common in pytest subprocess calls).

function Add-GeminiKeyToEnv {
    param([string]$EnvPath, [string]$Key)
    $text = Get-Content -Raw -Path $EnvPath
    $text = $text -replace '(?m)^# GEMINI_API_KEY=.*$', "GEMINI_API_KEY=$Key"
    [System.IO.File]::WriteAllText($EnvPath, $text, (New-Object System.Text.UTF8Encoding $false))
}

function Write-CloudConsent {
    param([string]$E156Root, [bool]$Enabled)
    $consentPath = Join-Path $E156Root '.consent.json'
    $payload = @{ cloud_enabled = $Enabled; set_at = (Get-Date -Format 'o') } | ConvertTo-Json -Compress
    [System.IO.File]::WriteAllText($consentPath, $payload, (New-Object System.Text.UTF8Encoding $false))
}

if ($cloudOnly -and -not $NonInteractive -and [Console]::IsInputRedirected -eq $false) {
    Write-Host ""
    Write-Host "======================================================"
    Write-Host "  Cloud AI setup (takes ~30 seconds)"
    Write-Host "======================================================"
    Write-Host ""
    Write-Host "You can get a free Gemini API key here:"
    Write-Host "  https://aistudio.google.com/apikey"
    Write-Host ""
    Write-Host "Free tier = 1 million tokens/day (plenty for writing papers)."
    Write-Host "Paste your key below, or press Enter to skip (you can add it"
    Write-Host "later with: student ai enable-cloud --i-understand-egress)."
    Write-Host ""
    $key = Read-Host "Gemini API key (starts with AIzaSy) or Enter to skip"
    $key = $key.Trim()
    if ($key -match '^AIzaSy[A-Za-z0-9_-]{33}$') {
        Add-GeminiKeyToEnv -EnvPath $envFile -Key $key
        Write-CloudConsent -E156Root $e156Root -Enabled $true
        Write-Ok "Gemini key saved. Cloud AI ready."
    } elseif ($key -ne '') {
        Write-Warning "That doesn't look like a Gemini API key (expected AIzaSy + 33 chars)."
        Write-Host "  You can add it later with: student ai enable-cloud --i-understand-egress"
        Write-CloudConsent -E156Root $e156Root -Enabled $false
    } else {
        Write-Host "No key entered. You can add one later with:"
        Write-Host "  student ai enable-cloud --i-understand-egress"
        Write-CloudConsent -E156Root $e156Root -Enabled $false
    }
} elseif ($cloudOnly) {
    # Non-interactive / CI / piped stdin -- just write consent=false, no key.
    Write-CloudConsent -E156Root $e156Root -Enabled $false
}

# --- Step 6: smoke test + gated banner -------------------------------------

$smokeScript = Join-Path $bundleRoot 'tests\smoke_test.py'
$smokeExit = 0
if (Test-Path $smokeScript) {
    Write-Host ""
    Write-Host "Running smoke test..." -ForegroundColor Cyan
    & python $smokeScript
    $smokeExit = $LASTEXITCODE
} else {
    Write-Warn2 "Smoke test script not found at $smokeScript - skipping."
}

Write-Host (Get-BannerForSmokeExit -ExitCode $smokeExit)

if ($smokeExit -ne 0) {
    $diag = Join-Path $bundleRoot 'tools\get_unstuck.py'
    if (Test-Path $diag) {
        & python $diag | Out-Null
    }
    exit $smokeExit
}

# Mark install complete (Start.bat reads this on subsequent runs).
Set-Content -Path (Join-Path $e156Root '.installed') -Value (Get-Date -Format 'o') -NoNewline -Encoding UTF8

# Launch first-run wizard.
$wizard = Join-Path $bundleRoot 'bin\first_run_wizard.py'
if (Test-Path $wizard) {
    & python $wizard
    exit $LASTEXITCODE
}
exit 0
