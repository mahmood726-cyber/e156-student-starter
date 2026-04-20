#Requires -Version 5.1
# Automated smoke script invoked by smoke.wsb at Sandbox boot.
# Writes all output to C:\smoke-out\smoke.log so the host can read it after.

$ErrorActionPreference = 'Continue'
$out = 'C:\smoke-out'
New-Item -ItemType Directory -Force -Path $out | Out-Null
$log = Join-Path $out 'smoke.log'
Start-Transcript -Path $log -Force | Out-Null

function Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }

Step "Sandbox environment"
Write-Host "Hostname: $(hostname)"
Write-Host "User: $env:USERNAME"
Write-Host "Python: $((Get-Command python -ErrorAction SilentlyContinue).Source)"

Step "Locate release zip"
$zip = Get-ChildItem -Path 'C:\Users\WDAGUtilityAccount\Downloads\e156-student-starter-*.zip' `
    -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $zip) {
    Write-Host "FAIL: no release zip found in Downloads. Place one there and re-run." -ForegroundColor Red
    Stop-Transcript | Out-Null
    exit 1
}
Write-Host "Using: $($zip.FullName)"

Step "Verify zip SHA against RELEASE-HASH.txt (if sibling file present)"
$sibling = Join-Path $zip.Directory 'RELEASE-HASH.txt'
if (Test-Path $sibling) {
    $expected = (Get-Content $sibling -Raw).Trim().ToLower()
    $actual = (Get-FileHash -Algorithm SHA256 $zip.FullName).Hash.ToLower()
    if ($expected -eq $actual) {
        Write-Host "OK: zip SHA matches RELEASE-HASH.txt ($actual)" -ForegroundColor Green
    } else {
        Write-Host "FAIL: zip SHA mismatch" -ForegroundColor Red
        Write-Host "  expected: $expected"
        Write-Host "  actual:   $actual"
    }
} else {
    Write-Host "SKIP: RELEASE-HASH.txt sibling not found; skipping zip-SHA cross-check."
}

Step "Extract zip"
$extract = 'C:\e156-extract'
if (Test-Path $extract) { Remove-Item -Recurse -Force $extract }
Expand-Archive -Path $zip.FullName -DestinationPath $extract -Force
Write-Host "Extracted to $extract"
Get-ChildItem $extract | Format-Table Name, Mode -AutoSize

Step "install.ps1 -DryRun (self-SHA gate only)"
$installPs1 = Join-Path $extract 'install\install.ps1'
if (Test-Path $installPs1) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installPs1 -DryRun
    Write-Host "Exit: $LASTEXITCODE"
} else {
    Write-Host "FAIL: install.ps1 not found at $installPs1" -ForegroundColor Red
}

Step "Start.bat --what-would-i-do"
Push-Location $extract
& cmd.exe /c 'Start.bat --what-would-i-do'
Write-Host "Exit: $LASTEXITCODE"
Pop-Location

Step "student sentinel scan on extracted bundle"
$studentPy = Join-Path $extract 'bin\student.py'
if (Test-Path $studentPy) {
    & python $studentPy sentinel --repo $extract
    Write-Host "Exit: $LASTEXITCODE"
}

Step "student memory (seed starter pack)"
$env:LOCALAPPDATA = 'C:\Users\WDAGUtilityAccount\AppData\Local'
& python $studentPy memory --force
Write-Host "Exit: $LASTEXITCODE"
$memTarget = Join-Path $env:LOCALAPPDATA 'e156\memory'
if (Test-Path $memTarget) {
    Write-Host "Seeded files:"
    Get-ChildItem $memTarget | Select-Object -ExpandProperty Name | ForEach-Object { Write-Host "  $_" }
}

Step "Copy logs back to mapped folder"
Write-Host "Log: $log"
Write-Host "Sandbox can now be closed; read logs at HOST\\install\\sandbox\\smoke-out\\smoke.log"

Stop-Transcript | Out-Null
