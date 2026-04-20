"""`student validate` wiring — exits 0 on compliant body, 1 on non-compliant."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDENT_PY = REPO_ROOT / "bin" / "student.py"


COMPLIANT_BODY = """\
We asked whether a standardised seven-sentence format improves reporting clarity compared to free prose abstracts.
The study sample comprises 339 meta-analysis projects drawn from Synthesis medicine submissions between 2024 and 2026.
Our primary estimand is the odds ratio of submission acceptance conditional on template compliance.
The pooled odds ratio was 3.2 with a 95 percent confidence interval of 2.1 to 4.8 indicating substantial benefit.
A leave-one-out sensitivity check removing the three largest journals gave a pooled odds ratio of 2.9.
For editors, the takeaway is that fixed templates reduce reviewer decision time and increase acceptance reliability.
This finding does not extend to descriptive case reports, narrative reviews, or preprints outside the Synthesis track.
"""


NON_COMPLIANT_TOO_MANY_SENTENCES = """\
We asked question one.
We asked question two.
We asked question three.
We asked question four.
We asked question five.
We asked question six.
We asked question seven.
We asked question eight.
"""


def run_cli(*args):
    return subprocess.run(
        [sys.executable, str(STUDENT_PY), *args],
        capture_output=True, text=True, timeout=15,
    )


def test_validate_passes_compliant_body(tmp_path):
    body = tmp_path / "current_body.txt"
    body.write_text(COMPLIANT_BODY, encoding="utf-8")
    r = run_cli("validate", "--path", str(body))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PASS" in r.stdout


def test_validate_fails_too_many_sentences(tmp_path):
    body = tmp_path / "current_body.txt"
    body.write_text(NON_COMPLIANT_TOO_MANY_SENTENCES, encoding="utf-8")
    r = run_cli("validate", "--path", str(body))
    assert r.returncode == 1
    assert "expected 7 sentences" in r.stdout


def test_validate_fails_embedded_citation(tmp_path):
    body = tmp_path / "current_body.txt"
    # Compliant 7-sentence body EXCEPT for one citation marker inside
    text = COMPLIANT_BODY.replace(
        "reduce reviewer decision time",
        "reduce reviewer decision time [1]",
    )
    body.write_text(text, encoding="utf-8")
    r = run_cli("validate", "--path", str(body))
    assert r.returncode == 1
    assert "citation" in r.stdout.lower() or "[1]" in r.stdout


def test_validate_discovers_current_body_in_dir(tmp_path):
    body = tmp_path / "current_body.txt"
    body.write_text(COMPLIANT_BODY, encoding="utf-8")
    r = run_cli("validate", "--path", str(tmp_path))
    assert r.returncode == 0


def test_validate_help_lists_subcommand():
    r = run_cli("help")
    assert r.returncode == 0
    assert "validate" in r.stdout
