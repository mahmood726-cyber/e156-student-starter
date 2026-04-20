"""Portable path resolution for the e156 student starter.

Pattern #5 from the portfolio survey. Centralises every path the bundle uses
so new code doesn't hardcode `C:\\Users\\...` and tests can redirect
`%LOCALAPPDATA%` safely.

Never call `Path.home()` or `os.path.expanduser("~")` directly from other
modules in this bundle — use one of the helpers below.
"""
from __future__ import annotations

import os
from pathlib import Path


def bundle_root() -> Path:
    """The e156 starter bundle root (dir containing Start.bat and install/)."""
    return Path(__file__).resolve().parents[1]


def e156_state_root() -> Path:
    """Student state dir: %LOCALAPPDATA%\\e156 (or ~/.e156 on POSIX)."""
    lad = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(lad) / "e156"


def workbook_root() -> Path:
    """The workbook dir inside the student state root."""
    return e156_state_root() / "workbook"


def paper_dir(slug: str) -> Path:
    return workbook_root() / slug


def logs_dir() -> Path:
    return e156_state_root() / "logs"


def audit_log_path() -> Path:
    return logs_dir() / "ai_calls.jsonl"


def bypass_log_path() -> Path:
    return logs_dir() / "bypass.log"


def baseline_store_path() -> Path:
    return e156_state_root() / "baseline.json"


def consent_path() -> Path:
    return e156_state_root() / ".consent.json"


def installed_marker_path() -> Path:
    return e156_state_root() / ".installed"


def dashboard_path() -> Path:
    return workbook_root() / "dashboard.html"


def submission_snapshots_dir(slug: str) -> Path:
    return paper_dir(slug) / ".submission_snapshots"
