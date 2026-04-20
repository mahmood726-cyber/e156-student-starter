@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem -------------------------------------------------------------------
rem  e156 - double-click entry point for students.
rem  First run: launches install.ps1 (students never see PowerShell directly).
rem  Subsequent runs: launches student.bat (opens the TUI menu).
rem -------------------------------------------------------------------

set "HERE=%~dp0"
set "MARKER=%LOCALAPPDATA%\e156\.installed"

set "NEXT=install"
if exist "%MARKER%" set "NEXT=student"

if /I "%~1"=="--what-would-i-do" (
    if "%NEXT%"=="install" (
        echo Would run: powershell -NoProfile -ExecutionPolicy Bypass -File install\install.ps1
    ) else (
        echo Would run: bin\student.bat
    )
    exit /b 0
)

if "%NEXT%"=="install" (
    echo Starting e156 installer...
    echo Safe to leave running. First-run download is 3 to 15 hours on 1.5 Mbps WiFi.
    echo You can pause and resume anytime (Ctrl+C, re-run Start.bat). Overnight is ideal.
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%HERE%install\install.ps1"
    exit /b %ERRORLEVEL%
) else (
    call "%HERE%bin\student.bat"
    exit /b %ERRORLEVEL%
)
