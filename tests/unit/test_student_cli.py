"""CLI subcommand dispatch + --version."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDENT_PY = REPO_ROOT / "bin" / "student.py"


def run_cli(*args):
    return subprocess.run(
        [sys.executable, str(STUDENT_PY), *args],
        capture_output=True, text=True, timeout=15,
    )


def test_version_prints_and_exits_zero():
    r = run_cli("--version")
    assert r.returncode == 0
    assert "0.2.0-plan-A" in r.stdout


def test_help_lists_all_subcommands():
    r = run_cli("help")
    assert r.returncode == 0
    for cmd in ("new", "ai", "data", "validate", "rules", "doctor", "help"):
        assert cmd in r.stdout


def test_unknown_subcommand_friendly_error():
    r = run_cli("banana")
    assert r.returncode != 0
    assert "isn't a command I know" in r.stdout + r.stderr


def test_new_without_template_triggers_help_me_pick(monkeypatch):
    # Smoke: calling `student new` with no --template flag should NOT immediately crash.
    # Full wizard flow tested in test_help_me_pick.py.
    r = run_cli("new", "--dry-run")
    assert r.returncode == 0
    assert "pick" in r.stdout.lower() or "template" in r.stdout.lower()
