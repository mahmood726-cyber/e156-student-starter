"""End-to-end: clean %LOCALAPPDATA% -> Start.bat dispatch -> install rollback.

This is the gated release criterion. Plan A is NOT done until tests 1+2 pass
on Windows; the slow 45-min test runs in CI nightly only.
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(os.name != "nt", reason="Windows-only E2E")
@pytest.mark.integration
def test_start_bat_first_run_prints_install_instruction(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    r = subprocess.run(
        ["cmd", "/c", str(REPO_ROOT / "Start.bat"), "--what-would-i-do"],
        capture_output=True, text=True, timeout=10,
    )
    assert r.returncode == 0, r.stderr
    assert "install.ps1" in r.stdout


@pytest.mark.skipif(os.name != "nt", reason="Windows-only E2E")
@pytest.mark.integration
def test_install_ps1_rollback_on_unreachable_ollama(tmp_path, monkeypatch):
    """If the Ollama download URL is unreachable AND -LocalAI is opted in,
    %LOCALAPPDATA%\\e156\\ is cleaned up.

    v0.4.1 note: cloud-only is now the default, which skips the Ollama download
    entirely — the rollback path only fires under -LocalAI, so the test must
    pass that flag explicitly to exercise the branch under test.
    """
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("E156_OLLAMA_URL_OVERRIDE", "http://127.0.0.1:1/does-not-exist")
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", str(REPO_ROOT / "install" / "install.ps1"), "-LocalAI", "-NonInteractive"],
        capture_output=True, text=True, timeout=120,
    )
    assert not (tmp_path / "e156").exists(), \
        f"e156 dir should be removed by rollback; install stdout:\n{r.stdout}\nstderr:\n{r.stderr}"
    assert r.returncode != 0


@pytest.mark.skipif(os.name != "nt", reason="Windows-only E2E")
@pytest.mark.integration
@pytest.mark.slow
def test_full_install_under_45_minutes_wallclock(tmp_path, monkeypatch):
    """The promise: a first-time user completes install in <45 min on a fast connection.

    Assumes Ollama is available on PATH and gemma2:2b is pre-pulled (CI fixture).
    Runs without bandwidth throttle here; release.yml adds the throttle in nightly.

    The wallclock assertion remains 45 min — that's the user-facing promise.
    The pytest subprocess timeout is generous (3 hours) so we still SEE the
    install fail vs. CI just killing it, on residential connections where the
    upstream Ollama download (1.92 GB as of 2026-04-21, was 380 MB pre-v0.5.x)
    can take >45 min. The assertion still flags slow-network failures; the
    timeout just lets us read install.ps1's stderr.
    """
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    start = time.monotonic()
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", str(REPO_ROOT / "install" / "install.ps1"), "-LowRam"],
        capture_output=True, text=True, timeout=60 * 180,  # 3-hour outer cap
        input="Test User\ntest@example.com\nAGREE\n",
    )
    elapsed = time.monotonic() - start
    assert r.returncode == 0, f"Install failed (elapsed {elapsed:.1f}s):\n{r.stderr[-2000:]}\nstdout tail:\n{r.stdout[-2000:]}"
    assert elapsed < 45 * 60, f"Install took {elapsed/60:.1f} min (user-facing promise: < 45 min)"
    assert (tmp_path / "e156" / ".installed").exists()
