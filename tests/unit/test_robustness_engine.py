"""E156 Tier-C robustness engine — portfolio-pattern #1 from FinRenone.

Checks S4 (Result) has a numeric + an estimand, S7 (Boundary) is substantive,
and the body has no placeholder tokens.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from tools.e156_robustness_engine import run_checks, format_report


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDENT_PY = REPO_ROOT / "bin" / "student.py"


# A body that passes format AND robustness (the sample in test_student_validate).
GOOD_BODY = """\
We asked whether a standardised seven-sentence format improves reporting clarity compared to free prose abstracts.
The study sample comprises 339 meta-analysis projects drawn from Synthesis medicine submissions between 2024 and 2026.
Our primary estimand is the odds ratio of submission acceptance conditional on template compliance.
The pooled odds ratio was 3.2 with a 95 percent confidence interval of 2.1 to 4.8 indicating substantial benefit.
A leave-one-out sensitivity check removing the three largest journals gave a pooled odds ratio of 2.9.
For editors, the takeaway is that fixed templates reduce reviewer decision time and increase acceptance reliability.
This finding does not extend to descriptive case reports, narrative reviews, or preprints outside the Synthesis track.
"""


def _swap_sentence(body: str, idx_1based: int, new: str) -> str:
    lines = [ln for ln in body.strip().splitlines() if ln.strip()]
    lines[idx_1based - 1] = new
    return "\n".join(lines) + "\n"


def test_clean_body_has_no_issues():
    issues = run_checks(GOOD_BODY)
    # GOOD_BODY is expected to pass all Tier-C checks
    block = [i for i in issues if i.severity == "BLOCK"]
    warn = [i for i in issues if i.severity == "WARN"]
    assert len(block) == 0, f"unexpected BLOCK: {block}"
    assert len(warn) == 0, f"unexpected WARN: {warn}"


def test_s4_without_numeric_blocks():
    no_numeric = _swap_sentence(GOOD_BODY, 4,
        "The pooled odds ratio was substantial and showed meaningful benefit.")
    issues = run_checks(no_numeric)
    assert any(i.rule == "S4-no-numeric" and i.severity == "BLOCK" for i in issues)


def test_s4_without_estimand_warns():
    no_estimand = _swap_sentence(GOOD_BODY, 4,
        "The pooled number was 3.2 with a 95 percent range of 2.1 to 4.8.")
    issues = run_checks(no_estimand)
    assert any(i.rule == "S4-no-estimand" and i.severity == "WARN" for i in issues)


def test_s7_generic_disclaimer_warns():
    generic = _swap_sentence(GOOD_BODY, 7,
        "Further research is needed to confirm these findings.")
    issues = run_checks(generic)
    assert any(i.rule == "S7-generic-disclaimer" for i in issues)


def test_s7_substantive_limitation_accepted():
    sub = _swap_sentence(GOOD_BODY, 7,
        "This finding has limitations: a small sample of three trials and short follow-up.")
    issues = run_checks(sub)
    assert not any(i.rule == "S7-generic-disclaimer" for i in issues)


def test_body_placeholder_blocks():
    placeholder = GOOD_BODY.replace(
        "odds ratio of 2.9",
        "odds ratio of {{REPLACE_ME}}",
    )
    issues = run_checks(placeholder)
    assert any(i.rule == "body-placeholder" and i.severity == "BLOCK" for i in issues)


def test_body_tbd_placeholder_blocks():
    placeholder = GOOD_BODY.replace("odds ratio of 2.9", "odds ratio of TBD")
    issues = run_checks(placeholder)
    assert any(i.rule == "body-placeholder" and i.severity == "BLOCK" for i in issues)


def test_fewer_than_7_sentences_early_exit():
    issues = run_checks("One sentence only.")
    assert any(i.rule == "fewer-than-7-sentences" for i in issues)


def test_format_report_human_readable():
    issues = run_checks(_swap_sentence(GOOD_BODY, 4,
        "The pooled result showed a clear effect."))
    report = format_report(issues)
    assert "robustness" in report
    assert "S4" in report


def test_strict_flag_invokes_robustness_via_cli(tmp_path):
    body = tmp_path / "current_body.txt"
    body.write_text(
        _swap_sentence(GOOD_BODY, 4, "The pooled result showed a clear effect."),
        encoding="utf-8",
    )
    r = subprocess.run(
        [sys.executable, str(STUDENT_PY), "validate", "--path", str(body), "--strict"],
        capture_output=True, text=True, timeout=15,
    )
    assert "S4-no-numeric" in r.stdout
    assert r.returncode == 1  # BLOCK from robustness engine


def test_strict_flag_optional_by_default(tmp_path):
    """Without --strict, validate should pass on format-compliant bodies even
    if they'd fail robustness (backwards-compat with existing tests)."""
    body = tmp_path / "current_body.txt"
    body.write_text(
        _swap_sentence(GOOD_BODY, 4, "The pooled result showed a clear effect."),
        encoding="utf-8",
    )
    r = subprocess.run(
        [sys.executable, str(STUDENT_PY), "validate", "--path", str(body)],
        capture_output=True, text=True, timeout=15,
    )
    # Format still passes (7 sentences, 156 words); robustness not invoked
    assert r.returncode == 0
    assert "S4-no-numeric" not in r.stdout
