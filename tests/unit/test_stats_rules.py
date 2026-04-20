"""Each stats-misinfo rule fires on known wrong phrasings, silent on correct ones."""
from __future__ import annotations

from pathlib import Path

from tools import sentinel_check as sc


REPO_ROOT = Path(__file__).resolve().parents[2]


def _scan_text(tmp_path: Path, text: str, filename: str = "body.md") -> list[sc.Finding]:
    (tmp_path / filename).write_text(text, encoding="utf-8")
    rules = sc.load_rules(REPO_ROOT / "config" / "sentinel" / "rules")
    return sc.scan(tmp_path, rules)


def test_dor_sign_wrong_flagged(tmp_path):
    findings = _scan_text(tmp_path, "The DOR is computed as DOR = exp(mu1 - mu2).")
    assert any(f.rule_id == "P1-stats-dor-sign" for f in findings)


def test_dor_sign_correct_silent(tmp_path):
    findings = _scan_text(tmp_path, "The DOR is computed as DOR = exp(mu1 + mu2).")
    assert not any(f.rule_id == "P1-stats-dor-sign" for f in findings)


def test_fisher_z_wrong_flagged(tmp_path):
    findings = _scan_text(tmp_path, "The variance of Fisher z is 1/(n-2).")
    assert any(f.rule_id == "P1-stats-fisher-z-variance" for f in findings)


def test_fisher_z_correct_silent(tmp_path):
    findings = _scan_text(tmp_path, "The variance of Fisher z is 1/(n-3).")
    assert not any(f.rule_id == "P1-stats-fisher-z-variance" for f in findings)


def test_or_to_smd_wrong_flagged(tmp_path):
    findings = _scan_text(tmp_path, "Convert log OR to SMD via log-OR * sqrt(3/pi).")
    assert any(f.rule_id == "P1-stats-or-smd-constant" for f in findings)


def test_or_to_smd_correct_silent(tmp_path):
    findings = _scan_text(tmp_path, "Convert log OR to SMD via log-OR * sqrt(3) / pi.")
    assert not any(f.rule_id == "P1-stats-or-smd-constant" for f in findings)


def test_dl_small_k_flagged(tmp_path):
    findings = _scan_text(tmp_path,
        "With five studies we used DerSimonian-Laird random-effects pooling.")
    assert any(f.rule_id == "P1-stats-dl-small-k" for f in findings)


def test_dl_large_k_silent(tmp_path):
    findings = _scan_text(tmp_path,
        "With 30 studies we used DerSimonian-Laird random-effects pooling.")
    assert not any(f.rule_id == "P1-stats-dl-small-k" for f in findings)
