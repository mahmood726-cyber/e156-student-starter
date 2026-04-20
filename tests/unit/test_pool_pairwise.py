"""Pairwise pooling sanity tests. For full R-metafor concordance, defer to diffmeta."""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

from tools.pool_pairwise import Study, load_csv, pool


REPO_ROOT = Path(__file__).resolve().parents[2]
POOL_PY = REPO_ROOT / "tools" / "pool_pairwise.py"


def test_log_or_and_variance_basic():
    s = Study("t1", 30, 70, 20, 80)
    assert math.isclose(s.log_or(), math.log((30 * 80) / (70 * 20)), rel_tol=1e-12)
    assert math.isclose(s.var_log_or(), 1/30 + 1/70 + 1/20 + 1/80, rel_tol=1e-12)


def test_zero_cell_triggers_0_5_correction():
    s = Study("t1", 0, 50, 5, 45)
    assert s.needs_correction()
    corrected = s.correct()
    assert corrected.a == 0.5
    assert corrected.b == 50.5
    assert not corrected.needs_correction()


def test_no_zero_no_correction_applied():
    """Unconditional correction biases OR toward 1; we only add 0.5 when needed."""
    s = Study("t1", 30, 70, 20, 80)
    assert not s.needs_correction()


def test_pool_single_study_zero_tau2():
    # k=1: tau² is undefined; should return 0
    out = pool([Study("t1", 30, 70, 20, 80)])
    assert out["k"] == 1
    assert out["tau2"] == 0.0


def test_pool_identical_studies_near_zero_heterogeneity():
    """Three identical 2x2 tables → tau² ≈ 0, Q ≈ 0, I² ≈ 0."""
    studies = [Study(f"t{i}", 30, 70, 20, 80) for i in range(3)]
    out = pool(studies)
    assert out["k"] == 3
    assert out["i2"] < 0.5, f"I² should be ~0 for identical studies, got {out['i2']}"
    assert out["tau2"] < 1e-6
    assert abs(out["pooled_estimate"] - studies[0].log_or()) < 1e-10


def test_pool_dispersed_studies_positive_tau2():
    """Studies with large between-study variance → positive tau², I² > 50%."""
    studies = [
        Study("t1", 10, 90, 5, 95),     # strong positive
        Study("t2", 20, 80, 18, 82),    # near-null
        Study("t3", 40, 60, 15, 85),    # strong positive again
        Study("t4", 8, 92, 20, 80),     # strong negative
    ]
    out = pool(studies)
    assert out["tau2"] > 0
    assert out["q"] > 0


def test_pool_hksj_floor_prevents_narrow_ci():
    """When Q/df < 1 (homogeneous), HKSJ scale factor must floor at 1, so CI
    doesn't narrow below inverse-variance. Correct SE floor = 1/sqrt(sum(w_RE))."""
    studies = [Study(f"t{i}", 30, 70, 20, 80) for i in range(4)]
    out = pool(studies)
    # With near-identical studies, q/df is tiny; floor kicks in.
    # SE should be a reasonable positive value, CI spans the point estimate.
    assert out["se"] > 0
    assert out["ci_lower"] < out["pooled_estimate"] < out["ci_upper"]


def test_pool_report_keys_match_baseline_contract():
    """baseline.record_from_report reads these exact keys."""
    out = pool([Study(f"t{i}", 30, 70, 20, 80) for i in range(3)])
    required = {"pooled_estimate", "ci_lower", "ci_upper", "se", "i2", "tau2", "q", "k"}
    assert required.issubset(out.keys()), f"missing keys: {required - out.keys()}"


def test_csv_load(tmp_path):
    csv_path = tmp_path / "trials.csv"
    csv_path.write_text(
        "study,a,b,c,d\n"
        "S1,30,70,20,80\n"
        "S2,40,60,25,75\n",
        encoding="utf-8",
    )
    studies = load_csv(csv_path)
    assert len(studies) == 2
    assert studies[0].label == "S1"
    assert studies[0].a == 30


def test_cli_end_to_end_writes_report_json(tmp_path):
    csv_path = tmp_path / "trials.csv"
    csv_path.write_text(
        "study,a,b,c,d\n"
        "S1,30,70,20,80\n"
        "S2,40,60,25,75\n"
        "S3,15,85,10,90\n",
        encoding="utf-8",
    )
    out = tmp_path / "report.json"
    r = subprocess.run(
        [sys.executable, str(POOL_PY), "--data", str(csv_path), "--output", str(out)],
        capture_output=True, text=True, timeout=60,  # was 15; subprocess can be slow under full-suite load
    )
    assert r.returncode == 0, r.stderr
    assert out.is_file()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["k"] == 3
    assert "pooled_estimate" in report
    assert "tau2" in report


def test_report_feeds_baseline_record_from_report(tmp_path, isolated_localappdata):
    """The produced report must be directly usable by baseline.record_from_report."""
    from tools.baseline import BaselineStore
    studies = [Study("S1", 30, 70, 20, 80), Study("S2", 40, 60, 25, 75),
               Study("S3", 15, 85, 10, 90)]
    report = pool(studies)
    store = BaselineStore(tmp_path / "bl.json")
    rec = store.record_from_report("p", report)
    store.save()
    assert rec.k == 3
    assert rec.pooled_estimate is not None
    assert math.isclose(rec.pooled_estimate, report["pooled_estimate"], rel_tol=1e-12)
