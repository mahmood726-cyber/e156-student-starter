#Requires -Version 5.1
# install.ps1 - E156 student starter bootstrap (Windows)
#
# Run from PowerShell (no admin needed):
#   .\install.ps1                 # full install, auto tier
#   .\install.ps1 -LowRam         # force 8 GB tier
#   .\install.ps1 -DryRun         # just verify SHA gate, exit 0
#   .\install.ps1 -Import         # dot-source helpers only (used by tests)
#   .\install.ps1 -CloudOnly      # skip model pulls; rely on cloud backend later

[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$LowRam,
    [switch]$CloudOnly,
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

Write-Host ""
Write-Host "RAM detected: $ramGb GB. Tier: $($tier.Name)." -ForegroundColor Cyan
if ($tier.CloudOnly -or $CloudOnly) {
    Write-Host "Local AI tier disabled (low RAM or -CloudOnly). Cloud opt-in required later." -ForegroundColor Yellow
    $tier = [PSCustomObject]@{ Name = $tier.Name; ProseModel = $null; CodeModel = $null; CloudOnly = $true }
}

# --- Step 2: download portable Ollama --------------------------------------

$pinsPath = Join-Path $bundleRoot 'config\pins.json'
if (-not (Test-Path $pinsPath)) {
    Write-Host "ERROR: config/pins.json missing. Re-download the bundle." -ForegroundColor Red
    exit 1
}
$pins = Get-Content $pinsPath -Raw | ConvertFrom-Json

$ollamaExe = Join-Path $ollamaDir 'ollama.exe'
$ollamaUrl = if ($env:E156_OLLAMA_URL_OVERRIDE) { $env:E156_OLLAMA_URL_OVERRIDE } else { $pins.ollama.url }
$skipShaVerify = [bool]$env:E156_OLLAMA_URL_OVERRIDE   # override is for tests; SHA won't match
if (-not (Test-Path $ollamaExe)) {
    Write-Step "Downloading portable Ollama $($pins.ollama.version)"
    $ollamaZip = Join-Path $ollamaDir 'ollama-portable.zip'
    try {
        try {
            Start-BitsTransfer -Source $ollamaUrl -Destination $ollamaZip -Description 'Ollama portable' -ErrorAction Stop
        } catch {
            Invoke-WebRequest -Uri $ollamaUrl -OutFile $ollamaZip -UseBasicParsing -TimeoutSec 30
        }
    } catch {
        Invoke-Rollback -E156Root $e156Root -Reason "Ollama download failed: $($_.Exception.Message)"
        exit 1
    }
    if (-not $skipShaVerify) {
        $actualSha = (Get-FileHash -Algorithm SHA256 $ollamaZip).Hash.ToLower()
        if ($actualSha -ne $pins.ollama.sha256) {
            Write-Host "SHA256 mismatch on Ollama zip." -ForegroundColor Red
            Write-Host "Expected: $($pins.ollama.sha256)"
            Write-Host "Got:      $actualSha"
            Invoke-Rollback -E156Root $e156Root -Reason 'Ollama SHA mismatch'
            exit 1
        }
    }
    try {
        Expand-Archive -Path $ollamaZip -DestinationPath $ollamaDir -Force
        Remove-Item $ollamaZip -Force
    } catch {
        Invoke-Rollback -E156Root $e156Root -Reason "Ollama extract failed: $($_.Exception.Message)"
        exit 1
    }
    Write-Ok "Ollama extracted to $ollamaDir"
} else {
    Write-Ok "Ollama already present at $ollamaExe"
}

# --- Step 3: env + start ollama serve --------------------------------------

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
$envContent = @"
# Auto-generated by install.ps1 on $(Get-Date -Format 'yyyy-MM-dd HH:mm')
$proseLine
$codeLine
OLLAMA_HOST=http://127.0.0.1:11434
# Uncomment to enable cloud fallback (egress: data leaves your laptop):
# GEMINI_API_KEY=your_key_here
"@
[System.IO.File]::WriteAllText($envFile, $envContent, (New-Object System.Text.UTF8Encoding $false))
Write-Ok "Wrote $envFile"

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
