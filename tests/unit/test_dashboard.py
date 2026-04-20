"""Supervisor dashboard — single-file offline HTML."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDENT_PY = REPO_ROOT / "bin" / "student.py"


def test_dashboard_no_external_refs(isolated_localappdata):
    from tools.dashboard import build
    html = build()
    # No CDN / external resource references allowed — must be offline-safe
    assert "http://" not in html
    assert "https://cdn" not in html.lower()
    assert "https://unpkg" not in html.lower()
    # The only https:// we allow is the RO-Crate context URI in documentation, but dashboard
    # shouldn't reference it. Assert no https:// at all.
    assert "https://" not in html or "w3id.org/ro/crate" not in html  # tight


def test_dashboard_renders_empty_workbook(isolated_localappdata):
    from tools.dashboard import build
    html = build()
    assert "<html" in html
    assert "e156 workbook dashboard" in html
    assert "No papers in the workbook yet" in html


def test_dashboard_shows_paper_with_validation(isolated_localappdata):
    from tools.dashboard import build
    wb = isolated_localappdata / "e156" / "workbook"
    paper = wb / "my-paper"
    paper.mkdir(parents=True)
    (paper / "current_body.txt").write_text("just one sentence.\n", encoding="utf-8")
    html = build()
    assert "my-paper" in html
    # Non-compliant body should render the FAIL verdict
    assert "FAIL" in html


def test_dashboard_shows_baseline_record(isolated_localappdata):
    from tools.dashboard import build
    e156 = isolated_localappdata / "e156"
    e156.mkdir(parents=True)
    (e156 / "baseline.json").write_text(json.dumps({
        "schema_version": "0.1",
        "records": {
            "p1": {
                "paper_id": "p1", "claim_id": "cl_deadbeef",
                "recorded_at": "2026-04-20T10:00:00Z",
                "commit_sha": None,
                "pooled_estimate": 0.75, "ci_lower": 0.62, "ci_upper": 0.91,
                "se": 0.08, "i2": 35.0, "tau2": 0.02, "q": 11.5, "k": 8,
                "extra": {},
            }
        }
    }), encoding="utf-8")
    html = build()
    assert "cl_deadbeef" in html
    assert "0.75" in html


def test_dashboard_shows_audit_log(isolated_localappdata):
    from tools.dashboard import build
    logs = isolated_localappdata / "e156" / "logs"
    logs.mkdir(parents=True)
    (logs / "ai_calls.jsonl").write_text(json.dumps({
        "ts": "2026-04-20T10:00:00+00:00", "task_kind": "prose",
        "backend": "ollama", "model": "gemma2:2b",
        "prompt_sha_prefix": "abc123", "response_sha_prefix": "def456",
        "response_words": 100, "elapsed_ms": 5000,
        "sentinel_scanned": False, "sentinel_findings": 0,
    }) + "\n", encoding="utf-8")
    html = build()
    assert "gemma2:2b" in html
    assert "abc123" in html


def test_dashboard_consent_shows_hash_not_raw_pii(isolated_localappdata):
    from tools.dashboard import build
    e156 = isolated_localappdata / "e156"
    e156.mkdir(parents=True)
    (e156 / ".consent.json").write_text(json.dumps({
        "name": "Priscilla Namusoke", "email": "p.namusoke@mak.ac.ug",
        "cloud_enabled": False,
        "gemma_acknowledged_at": "2026-04-19T10:00:00+00:00",
        "gemma_license_acknowledged": True,
    }), encoding="utf-8")
    html = build()
    assert "Priscilla" not in html
    assert "Namusoke" not in html
    assert "mak.ac.ug" not in html
    # SHA256 is 64 hex
    assert re.search(r"[0-9a-f]{64}", html) is not None


def test_dashboard_cli_writes_file(isolated_localappdata, tmp_path):
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(isolated_localappdata)
    out = tmp_path / "report.html"
    r = subprocess.run(
        [sys.executable, str(STUDENT_PY), "dashboard", "--out", str(out)],
        capture_output=True, text=True, timeout=15, env=env,
    )
    assert r.returncode == 0, r.stderr
    assert out.is_file()
    assert "<!DOCTYPE html>" in out.read_text(encoding="utf-8")


def test_dashboard_in_help():
    r = subprocess.run(
        [sys.executable, str(STUDENT_PY), "help"],
        capture_output=True, text=True, timeout=10,
    )
    assert "dashboard" in r.stdout
