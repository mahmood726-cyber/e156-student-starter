"""Drift detector tests."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from tools.drift_detector import snapshot, check, format_report


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDENT_PY = REPO_ROOT / "bin" / "student.py"


def _mk_paper(wb: Path, slug: str, body: str = "body v1") -> Path:
    p = wb / slug
    p.mkdir(parents=True, exist_ok=True)
    (p / "current_body.txt").write_text(body, encoding="utf-8")
    return p


def test_no_prior_snapshot_reports_none(isolated_localappdata):
    wb = isolated_localappdata / "e156" / "workbook"
    _mk_paper(wb, "p")
    r = check("p")
    assert r.last_snapshot_ts is None
    assert not r.drifted


def test_snapshot_then_check_clean(isolated_localappdata):
    wb = isolated_localappdata / "e156" / "workbook"
    _mk_paper(wb, "p", "body v1")
    snapshot("p")
    r = check("p")
    assert r.last_snapshot_ts is not None
    assert not r.drifted
    assert r.body_similarity_pct == 100.0


def test_body_change_detected(isolated_localappdata):
    wb = isolated_localappdata / "e156" / "workbook"
    _mk_paper(wb, "p", "body v1 original")
    snapshot("p")
    time.sleep(0.02)  # ensure distinct timestamps
    (wb / "p" / "current_body.txt").write_text(
        "body v1 totally different content now", encoding="utf-8",
    )
    r = check("p")
    assert r.drifted
    assert any(f == "body_sha256" for f, *_ in r.changes)


def test_minor_typo_fix_still_below_90pct_may_or_may_not_drift(isolated_localappdata):
    """If the similarity stays >= 90%, body-sha still changes so drifted flag
    fires via the SHA diff. This test documents the current behaviour: any
    SHA diff is drift, regardless of word-level similarity."""
    wb = isolated_localappdata / "e156" / "workbook"
    _mk_paper(wb, "p", "body content original")
    snapshot("p")
    (wb / "p" / "current_body.txt").write_text(
        "body content orignal", encoding="utf-8",  # typo
    )
    r = check("p")
    assert r.drifted is True


def test_baseline_change_detected(isolated_localappdata):
    """Editing the baseline store should surface as a drift field."""
    from tools.baseline import BaselineStore
    wb = isolated_localappdata / "e156" / "workbook"
    _mk_paper(wb, "p", "body")
    bl = BaselineStore()
    bl.record("p", pooled_estimate=0.5)
    bl.save()
    snapshot("p")
    # Overwrite with new value
    bl2 = BaselineStore()
    bl2.record("p", pooled_estimate=0.7, overwrite=True)
    bl2.save()
    r = check("p")
    assert r.drifted
    assert any("baseline.pooled_estimate" == f for f, *_ in r.changes)


def test_cli_snapshot_and_check(isolated_localappdata):
    wb = isolated_localappdata / "e156" / "workbook"
    _mk_paper(wb, "p", "body initial")
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(isolated_localappdata)

    # snapshot
    r = subprocess.run(
        [sys.executable, str(STUDENT_PY), "drift", "snapshot", "--slug", "p"],
        capture_output=True, text=True, timeout=15, env=env,
    )
    assert r.returncode == 0, r.stderr
    assert "Snapshot:" in r.stdout

    # check (clean)
    r = subprocess.run(
        [sys.executable, str(STUDENT_PY), "drift", "check", "--slug", "p"],
        capture_output=True, text=True, timeout=15, env=env,
    )
    assert r.returncode == 0
    assert "no material drift" in r.stdout

    # modify body, check should now fail
    (wb / "p" / "current_body.txt").write_text("body DIFFERENT", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(STUDENT_PY), "drift", "check", "--slug", "p"],
        capture_output=True, text=True, timeout=15, env=env,
    )
    assert r.returncode == 1
    assert "DRIFT" in r.stdout


def test_drift_subcommand_in_help():
    r = subprocess.run(
        [sys.executable, str(STUDENT_PY), "help"],
        capture_output=True, text=True, timeout=10,
    )
    assert "drift" in r.stdout
