"""Start.bat delegates to install.ps1 on first run, student.bat on subsequent."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
START_BAT = REPO_ROOT / "Start.bat"


@pytest.mark.skipif(os.name != "nt", reason="Windows-only")
def test_start_bat_calls_install_on_first_run(tmp_path, monkeypatch):
    # Redirect %LOCALAPPDATA% so no .installed marker is present
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    # --what-would-i-do is a dry-run flag Start.bat recognizes
    r = subprocess.run(
        ["cmd", "/c", str(START_BAT), "--what-would-i-do"],
        capture_output=True, text=True, timeout=10,
    )
    assert "install.ps1" in r.stdout


@pytest.mark.skipif(os.name != "nt", reason="Windows-only")
def test_start_bat_calls_student_on_subsequent_run(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    installed_marker = tmp_path / "e156" / ".installed"
    installed_marker.parent.mkdir(parents=True, exist_ok=True)
    installed_marker.write_text("2026-04-19")
    r = subprocess.run(
        ["cmd", "/c", str(START_BAT), "--what-would-i-do"],
        capture_output=True, text=True, timeout=10,
    )
    assert "student.bat" in r.stdout
