"""Numerical baseline store — record once, diff on revision."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools.baseline import BaselineStore, DEFAULT_TOLERANCE


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDENT_PY = REPO_ROOT / "bin" / "student.py"


def test_record_then_read_back(tmp_path):
    store = BaselineStore(tmp_path / "bl.json")
    store.record("my-paper", pooled_estimate=0.75, ci_lower=0.62, ci_upper=0.91,
                 se=0.08, i2=35.0, tau2=0.02, q=11.5, k=8)
    store.save()

    reloaded = BaselineStore(tmp_path / "bl.json")
    rec = reloaded.get("my-paper")
    assert rec is not None
    assert rec.pooled_estimate == 0.75
    assert rec.k == 8
    assert rec.claim_id.startswith("cl_")


def test_duplicate_record_rejected_without_overwrite(tmp_path):
    store = BaselineStore(tmp_path / "bl.json")
    store.record("x", pooled_estimate=1.0)
    with pytest.raises(KeyError):
        store.record("x", pooled_estimate=2.0)


def test_overwrite_preserves_claim_id(tmp_path):
    store = BaselineStore(tmp_path / "bl.json")
    r1 = store.record("x", pooled_estimate=1.0)
    r2 = store.record("x", pooled_estimate=2.0, overwrite=True)
    assert r1.claim_id == r2.claim_id


def test_diff_exceeds_tolerance(tmp_path):
    store = BaselineStore(tmp_path / "bl.json")
    store.record("p", pooled_estimate=0.75, ci_lower=0.62, ci_upper=0.91)
    rep = store.diff("p", {"pooled_estimate": 0.7502, "ci_lower": 0.62, "ci_upper": 0.91},
                     tolerance=1e-4)
    assert rep.exceeds_tolerance
    assert "pooled_estimate" in rep.diffs


def test_diff_within_tolerance(tmp_path):
    store = BaselineStore(tmp_path / "bl.json")
    store.record("p", pooled_estimate=0.75)
    rep = store.diff("p", {"pooled_estimate": 0.75 + 1e-9}, tolerance=DEFAULT_TOLERANCE)
    assert not rep.exceeds_tolerance


def test_diff_missing_paper_raises(tmp_path):
    store = BaselineStore(tmp_path / "bl.json")
    with pytest.raises(KeyError):
        store.diff("never-recorded", {"pooled_estimate": 0.5})


def test_cli_record_and_check_flow(isolated_localappdata):
    import os
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(isolated_localappdata)

    # Record via CLI
    r = subprocess.run(
        [sys.executable, str(STUDENT_PY), "baseline", "record", "my-paper",
         "--value", "pooled_estimate=0.75", "--value", "ci_lower=0.62",
         "--value", "ci_upper=0.91", "--value", "k=8"],
        capture_output=True, text=True, timeout=15, env=env,
    )
    assert r.returncode == 0, r.stderr
    assert "Recorded my-paper" in r.stdout

    # Check drift triggers exit 1
    r = subprocess.run(
        [sys.executable, str(STUDENT_PY), "baseline", "check", "my-paper",
         "--value", "pooled_estimate=0.7502", "--value", "ci_lower=0.62",
         "--value", "ci_upper=0.91", "--value", "k=8",
         "--tolerance", "1e-4"],
        capture_output=True, text=True, timeout=15, env=env,
    )
    assert r.returncode == 1
    assert "DRIFT" in r.stdout


def test_cli_within_tolerance_passes(isolated_localappdata):
    import os
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(isolated_localappdata)

    subprocess.run(
        [sys.executable, str(STUDENT_PY), "baseline", "record", "p",
         "--value", "pooled_estimate=0.75"],
        capture_output=True, text=True, timeout=15, env=env,
    )
    r = subprocess.run(
        [sys.executable, str(STUDENT_PY), "baseline", "check", "p",
         "--value", "pooled_estimate=0.75"],
        capture_output=True, text=True, timeout=15, env=env,
    )
    assert r.returncode == 0
    assert "OK:" in r.stdout


def test_baseline_help_includes_all_subcmds():
    r = subprocess.run(
        [sys.executable, str(STUDENT_PY), "help"],
        capture_output=True, text=True, timeout=10,
    )
    assert "baseline" in r.stdout
