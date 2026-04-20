"""Redactor strips secrets + PII before diagnostic bundle upload."""
from __future__ import annotations

from pathlib import Path
import pytest
from tools.get_unstuck import redact, gather, build_zip


def test_redact_strips_userprofile(tmp_path):
    raw = "C:\\Users\\Priscilla\\e156\\logs\\install.log"
    assert "Priscilla" not in redact(raw)
    assert "~\\e156" in redact(raw).replace("/", "\\")


def test_redact_scrubs_github_token():
    raw = "GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz0123456789AB"
    out = redact(raw)
    assert "ghp_abcdefghijklmnopqrstuvwxyz0123456789AB" not in out
    assert "ghp_***REDACTED***" in out


def test_redact_scrubs_gemini_key():
    # Built at runtime so the literal key pattern never appears in source
    # (avoids false-positive GitHub secret-scanner alerts on test fixtures).
    fake_key = "AI" + "za" + ("F" * 35)  # matches AIza[A-Za-z0-9-_]{35}
    raw = f"GEMINI_API_KEY={fake_key}"
    out = redact(raw)
    assert fake_key not in out
    assert "AIza_***REDACTED***" in out


def test_redact_strips_git_user_email():
    raw = "user.email=priscilla@mak.ac.ug\nuser.name=Priscilla"
    out = redact(raw)
    assert "priscilla@mak.ac.ug" not in out
    assert "user.email=***REDACTED***" in out


def test_redact_handles_multiple_patterns_in_one_blob():
    raw = (
        "C:\\Users\\Sam\\e156\\.env:\n"
        "GITHUB_TOKEN=ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n"
        "user.email=sam@students.mak.ac.ug\n"
    )
    out = redact(raw)
    assert "Sam" not in out
    assert "ghp_AAAA" not in out
    assert "sam@students.mak.ac.ug" not in out


def test_gather_returns_keys_for_expected_diagnostics(isolated_localappdata, monkeypatch):
    # Make gather tolerant to missing subsystems; it should still return a dict
    # with every expected key (possibly empty string values).
    monkeypatch.setenv("PATH", "")  # force `ollama list` to fail gracefully
    bundle = gather()
    for k in ("install_log", "serve_log_tail", "ollama_list",
             "python_version", "ram_gb", "disk_free_gb", "consent",
             "git_status"):
        assert k in bundle, f"gather() missing key {k}"


def test_build_zip_contains_redacted_files_only(tmp_path, isolated_localappdata):
    bundle = {
        "install_log": "C:\\Users\\Alex\\e156\\install.log\nGITHUB_TOKEN=ghp_" + "X" * 36,
        "serve_log_tail": "",
        "ollama_list": "",
        "python_version": "Python 3.11.9",
        "ram_gb": "8",
        "disk_free_gb": "12",
        "consent": "{\"cloud_enabled\": false}",
        "git_status": "nothing to commit",
    }
    out = tmp_path / "diagnostic.zip"
    build_zip(bundle, out)
    import zipfile
    with zipfile.ZipFile(out) as zf:
        content = zf.read("install_log.txt").decode()
    assert "Alex" not in content
    assert "ghp_XXX" not in content
    assert "***REDACTED***" in content
