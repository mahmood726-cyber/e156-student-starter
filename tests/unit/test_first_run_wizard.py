"""First-run wizard captures name/email, requires typed AGREE, writes .consent.json."""
from __future__ import annotations

import io
import json
from pathlib import Path
import pytest
from bin.first_run_wizard import run_wizard


def _fake_stdin(lines: list[str]) -> io.StringIO:
    return io.StringIO("\n".join(lines) + "\n")


def test_refuses_when_student_does_not_type_AGREE(isolated_localappdata, monkeypatch):
    monkeypatch.setattr("sys.stdin", _fake_stdin([
        "Priscilla Namusoke",
        "p.namusoke@mak.ac.ug",
        "no thanks",  # should have typed AGREE
    ]))
    exit_code = run_wizard(skip_smoke=True)
    assert exit_code != 0


def test_writes_consent_json_when_agree(isolated_localappdata, monkeypatch):
    monkeypatch.setattr("sys.stdin", _fake_stdin([
        "Priscilla Namusoke",
        "p.namusoke@mak.ac.ug",
        "AGREE",
        "n",  # decline hook install (tested separately)
    ]))
    exit_code = run_wizard(skip_smoke=True)
    assert exit_code == 0
    consent_path = isolated_localappdata / "e156" / ".consent.json"
    assert consent_path.exists()
    data = json.loads(consent_path.read_text())
    assert data["gemma_license_acknowledged"] is True
    assert data["cloud_enabled"] is False
    assert data["name"].startswith("Priscilla")
    assert data["email"].endswith("@mak.ac.ug")


def test_wizard_installs_hook_when_yes(isolated_localappdata, monkeypatch):
    monkeypatch.setattr("sys.stdin", _fake_stdin([
        "Ama", "ama@students.mak.ac.ug", "AGREE", "y",
    ]))
    exit_code = run_wizard(skip_smoke=True)
    assert exit_code == 0
    hook = isolated_localappdata / "e156" / "workbook" / ".git" / "hooks" / "pre-push"
    assert hook.exists()
    assert "SENTINEL_BYPASS" in hook.read_text(encoding="utf-8")


def test_wizard_skips_hook_on_no(isolated_localappdata, monkeypatch):
    monkeypatch.setattr("sys.stdin", _fake_stdin([
        "Ama", "ama@students.mak.ac.ug", "AGREE", "n",
    ]))
    exit_code = run_wizard(skip_smoke=True)
    assert exit_code == 0
    hook = isolated_localappdata / "e156" / "workbook" / ".git" / "hooks" / "pre-push"
    assert not hook.exists()


def test_lowercase_agree_does_not_count(isolated_localappdata, monkeypatch):
    """Case-sensitive AGREE; prevents accidental click-through."""
    monkeypatch.setattr("sys.stdin", _fake_stdin([
        "Sam", "sam@students.mak.ac.ug", "agree",
        # no hook-install answer — AGREE rejected before reaching that prompt
    ]))
    exit_code = run_wizard(skip_smoke=True)
    assert exit_code != 0
