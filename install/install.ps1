# install.ps1 — E156 student starter bootstrap (Windows)
#
# What this does, in order:
#   1. Picks a drive with enough free space (prefer D: if it has 20GB+,
#      else C:). This matters for African students on machines where C:
#      is a small SSD and data lives on D:.
#   2. Downloads the PORTABLE Ollama zip (no admin / no UAC prompt).
#   3. Sets OLLAMA_MODELS to live under the chosen drive so the 10GB of
#      model weights doesn't accidentally fill C:.
#   4. Starts Ollama as a background process (no service install).
#   5. Pulls Gemma 2 9B + Qwen 2.5 Coder 7B. Falls back to the :2b and
#      :1.5b variants if --low-ram is passed or if <10GB RAM is detected.
#   6. Runs a one-command smoke test that exercises the router end-to-end.
#
# Run from PowerShell (no admin needed):
#   .\install.ps1                 # full install, prefers D:
#   .\install.ps1 -LowRam         # use the 8GB-laptop model set
#   .\install.ps1 -Drive C        # force install to C:
#   .\install.ps1 -NoModelPull    # set things up without pulling weights
#                                   (useful if you're about to copy them
#                                   from a USB stick — see airgap.md)

[CmdletBinding()]
param(
    [switch]$LowRam,
    [string]$Drive = "",
    [switch]$NoModelPull,
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) { if (-not $Quiet) { Write-Host "==> $msg" -ForegroundColor Cyan } }
function Write-Ok($msg)   { if (-not $Quiet) { Write-Host "    $msg" -ForegroundColor Green } }
function Write-Warn($msg) { Write-Warning $msg }

# --- Step 1: pick drive ----------------------------------------------------

Write-Step "Picking install drive"
$target = $null
if ($Drive -ne "") {
    $target = "${Drive}:\"
    if (-not (Test-Path $target)) {
        throw "Requested drive $target does not exist."
    }
} else {
    foreach ($d in @("D:", "E:", "C:")) {
        if (Test-Path "${d}\") {
            $free = (Get-PSDrive $d.TrimEnd(':')).Free
            if ($free -gt 20GB) {
                $target = "${d}\"
                break
            }
        }
    }
    if (-not $target) {
        throw "No drive with >=20GB free. Pass -Drive C to override (will pull models to C:)."
    }
}
$freeGB = [math]::Round((Get-PSDrive $target.Substring(0,1)).Free / 1GB, 1)
Write-Ok "Using $target ($freeGB GB free)"

$ollamaDir = Join-Path $target "ollama"
$modelsDir = Join-Path $ollamaDir "models"
$starterDir = Join-Path $target "e156-student-starter"
New-Item -ItemType Directory -Force -Path $ollamaDir, $modelsDir, $starterDir | Out-Null

# --- Step 2: download portable Ollama --------------------------------------

$ollamaZip = Join-Path $ollamaDir "ollama-portable.zip"
$ollamaExe = Join-Path $ollamaDir "ollama.exe"

if (-not (Test-Path $ollamaExe)) {
    Write-Step "Downloading portable Ollama (~350 MB, one-time)"
    $url = "https://github.com/ollama/ollama/releases/latest/download/ollama-windows-amd64.zip"
    # Use BITS if available (resumable over flaky connections — important
    # for intermittent African internet), fall back to Invoke-WebRequest.
    try {
        Start-BitsTransfer -Source $url -Destination $ollamaZip -Description "Ollama portable"
    } catch {
        Invoke-WebRequest -Uri $url -OutFile $ollamaZip -UseBasicParsing
    }
    Write-Step "Extracting Ollama to $ollamaDir"
    Expand-Archive -Path $ollamaZip -DestinationPath $ollamaDir -Force
    Remove-Item $ollamaZip -Force
    Write-Ok "Ollama extracted."
} else {
    Write-Ok "Ollama already present at $ollamaExe"
}

# --- Step 3: env vars for the current user ---------------------------------

Write-Step "Setting OLLAMA_MODELS=$modelsDir (user env)"
[Environment]::SetEnvironmentVariable("OLLAMA_MODELS", $modelsDir, "User")
$env:OLLAMA_MODELS = $modelsDir

# --- Step 4: start Ollama as background process ----------------------------

Write-Step "Starting ollama serve (background)"
# If it's already running, skip.
$existing = Get-Process ollama -ErrorAction SilentlyContinue
if ($existing) {
    Write-Ok "ollama already running (PID $($existing.Id))"
} else {
    Start-Process -FilePath $ollamaExe -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 3
    Write-Ok "ollama serve started."
}

# --- Step 5: pull models ---------------------------------------------------

# Detect physical RAM to auto-pick low-RAM mode if the user didn't specify.
$ramGB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 0)
Write-Ok "Detected ${ramGB} GB RAM"
if (-not $LowRam -and $ramGB -lt 12) {
    Write-Warn "Auto-enabling -LowRam (RAM < 12GB)."
    $LowRam = $true
}

if ($LowRam) {
    $proseModel = "gemma2:2b"
    $codeModel  = "qwen2.5-coder:1.5b"
    $quickModel = "qwen2.5-coder:1.5b"
} else {
    $proseModel = "gemma2:9b"
    $codeModel  = "qwen2.5-coder:7b"
    $quickModel = "qwen2.5-coder:1.5b"
}

if ($NoModelPull) {
    Write-Ok "Skipping model pull (as requested). Run:"
    Write-Host "    & '$ollamaExe' pull $proseModel"
    Write-Host "    & '$ollamaExe' pull $codeModel"
    Write-Host "    & '$ollamaExe' pull $quickModel"
} else {
    Write-Step "Pulling $proseModel (~5 GB)"
    & $ollamaExe pull $proseModel
    Write-Step "Pulling $codeModel (~4 GB)"
    & $ollamaExe pull $codeModel
    Write-Step "Pulling $quickModel (~1 GB)"
    & $ollamaExe pull $quickModel
}

# --- Step 6: ensure starter repo files are in place ------------------------

Write-Step "Checking starter repo at $starterDir"
$expectedFiles = @("ai\ai_call.py", "tools\validate_e156.py", "rules\AGENTS.md",
                   "examples\example_paper_01\current_body.txt")
$missing = $expectedFiles | Where-Object { -not (Test-Path (Join-Path $starterDir $_)) }
if ($missing) {
    Write-Warn "Starter repo missing: $($missing -join ', ')"
    Write-Warn "Clone the starter: git clone https://github.com/mahmood726-cyber/e156-student-starter '$starterDir'"
} else {
    Write-Ok "Starter repo files present."
}

# --- Step 7: write a local env file the router reads -----------------------

$envFile = Join-Path $starterDir ".env"
$envContent = @"
# Auto-generated by install.ps1 on $(Get-Date -Format 'yyyy-MM-dd HH:mm')
# Edit this file to override defaults. ai_call.py reads these.
E156_PROSE_MODEL=$proseModel
E156_CODE_MODEL=$codeModel
E156_QUICK_MODEL=$quickModel
OLLAMA_HOST=http://127.0.0.1:11434
# Uncomment and set if you have a GitHub Copilot-for-Students subscription:
# GITHUB_TOKEN=ghp_your_token_here
# Uncomment and set if you have a Gemini API key from aistudio.google.com:
# GEMINI_API_KEY=your_key_here
"@
Set-Content -Path $envFile -Value $envContent -Encoding UTF8
Write-Ok "Wrote $envFile"

# --- Step 8: smoke test ----------------------------------------------------

if (-not $NoModelPull) {
    Write-Step "Running smoke test"
    $smokePrompt = "Reply with exactly the single word: OK"
    $routerPath = Join-Path $starterDir "ai\ai_call.py"
    if (Test-Path $routerPath) {
        $result = & python $routerPath "quick" $smokePrompt 2>&1
        if ($result -match "OK") {
            Write-Ok "Smoke test PASSED: '$result'"
        } else {
            Write-Warn "Smoke test reply was unexpected: '$result'"
        }
    } else {
        Write-Warn "Router not found at $routerPath — skipping smoke test."
    }
}

Write-Host ""
Write-Host "=== INSTALL COMPLETE ===" -ForegroundColor Green
Write-Host "Models:      $modelsDir" -ForegroundColor Gray
Write-Host "Starter:     $starterDir" -ForegroundColor Gray
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. cd '$starterDir\examples\example_paper_01'"
Write-Host "  2. Read README.md and try your first rewrite."
Write-Host ""
Write-Host "If Ollama is not running later, start it with:"
Write-Host "  & '$ollamaExe' serve"
