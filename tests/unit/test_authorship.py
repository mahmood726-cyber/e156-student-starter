"""Authorship contract (portfolio pattern #2 from AuthorshipLedger)."""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tools.authorship import (
    AuthorshipIssue, authorship_path, check, enrol_interactive, format_issues,
    save_authorship,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDENT_PY = REPO_ROOT / "bin" / "student.py"


VALID = {
    "first_author": {
        "full_name": "Priscilla Namusoke",
        "email": "p.namusoke@mak.ac.ug",
        "affiliation": "Makerere University",
        "orcid": None, "is_board_member_of_target_journal": False,
    },
    "middle_author": {
        "full_name": "Mahmood Ahmad",
        "email": "mahmood.ahmad2@nhs.net",
        "affiliation": "Tahir Heart Institute",
        "orcid": None, "is_board_member_of_target_journal": True,
    },
    "last_author": {
        "full_name": "Prof. Moses Ssali",
        "email": "moses.ssali@mak.ac.ug",
        "affiliation": "Makerere University",
        "orcid": None, "is_board_member_of_target_journal": False,
    },
    "conflicts_of_interest": {"has_conflicts": False, "statement": ""},
    "funding_sources": [],
    "ai_assistance_disclosed": {
        "used_ai": True,
        "disclosure_sentence": "Gemma 2 and Qwen 2.5 Coder models were used for language editing.",
        "backends": ["ollama"],
    },
    "editorial_board_coi": {
        "any_board_member": True,
        "no_role_paragraph_included": True,
        "journal_name_exact": "Synthesis",
    },
}


def test_missing_authorship_json_blocks(isolated_localappdata):
    issues = check("nonexistent-slug")
    assert any(i.severity == "BLOCK" and "No authorship record" in i.message for i in issues)


def test_valid_authorship_no_issues(isolated_localappdata):
    save_authorship("p", VALID)
    issues = check("p")
    assert issues == [], f"unexpected issues: {issues}"


def test_missing_email_blocks(isolated_localappdata):
    bad = json.loads(json.dumps(VALID))
    bad["first_author"]["email"] = "not an email"
    save_authorship("p", bad)
    issues = check("p")
    assert any(i.severity == "BLOCK" and i.field == "first_author" for i in issues)


def test_bad_orcid_warns(isolated_localappdata):
    bad = json.loads(json.dumps(VALID))
    bad["first_author"]["orcid"] = "not-a-real-orcid"
    save_authorship("p", bad)
    issues = check("p")
    assert any(i.severity == "WARN" and "orcid" in i.message.lower() for i in issues)


def test_coi_has_conflicts_empty_statement_blocks(isolated_localappdata):
    bad = json.loads(json.dumps(VALID))
    bad["conflicts_of_interest"] = {"has_conflicts": True, "statement": ""}
    save_authorship("p", bad)
    issues = check("p")
    assert any(i.severity == "BLOCK" and "conflicts_of_interest" in i.field for i in issues)


def test_ai_used_without_disclosure_blocks(isolated_localappdata):
    bad = json.loads(json.dumps(VALID))
    bad["ai_assistance_disclosed"] = {"used_ai": True, "disclosure_sentence": ""}
    save_authorship("p", bad)
    issues = check("p")
    assert any(i.severity == "BLOCK" and "ai_assistance_disclosed" in i.field for i in issues)


def test_board_member_as_first_author_blocks(isolated_localappdata):
    """A board member of the target journal cannot hold first position."""
    bad = json.loads(json.dumps(VALID))
    bad["first_author"]["is_board_member_of_target_journal"] = True
    save_authorship("p", bad)
    issues = check("p")
    assert any(i.severity == "BLOCK" and i.field == "first_author" for i in issues)


def test_board_member_as_last_author_blocks(isolated_localappdata):
    bad = json.loads(json.dumps(VALID))
    bad["last_author"]["is_board_member_of_target_journal"] = True
    save_authorship("p", bad)
    issues = check("p")
    assert any(i.severity == "BLOCK" and i.field == "last_author" for i in issues)


def test_board_member_as_middle_author_is_fine(isolated_localappdata):
    """Middle is the correct position for a board member — as in this repo's
    actual authorship setup (Mahmood Ahmad is a Synthesis board member)."""
    save_authorship("p", VALID)
    issues = check("p")
    # No BLOCK on first_author or last_author for board-member status
    for i in issues:
        assert not (i.severity == "BLOCK" and i.field in ("first_author", "last_author"))


def test_no_role_paragraph_flag_required_when_board_member(isolated_localappdata):
    bad = json.loads(json.dumps(VALID))
    bad["editorial_board_coi"]["no_role_paragraph_included"] = False
    save_authorship("p", bad)
    issues = check("p")
    assert any(i.severity == "BLOCK" and "no_role_paragraph_included" in i.field for i in issues)


def test_enrol_interactive_writes_file(isolated_localappdata):
    # Simulated input: name/email/aff/orcid/board? for each role, then COI/funding/AI
    answers = iter([
        # first_author
        "Ada Smith", "ada@example.ug", "Makerere", "", "n",
        # middle_author (defaults accepted)
        "", "", "", "", "y",
        # last_author
        "Prof. Okello", "okello@example.ug", "Makerere", "", "n",
        # COI
        "n",
        # Funding
        "",
        # AI
        "y",
        "Local Gemma and Qwen were used via the e156 starter.",
        # board paragraph (triggered because middle marked y)
        "y",
    ])
    def _input(_prompt):
        return next(answers)
    path = enrol_interactive("ada-paper", input_fn=_input)
    assert path.is_file()
    issues = check("ada-paper")
    # Accept WARN/INFO but NOT BLOCK after a valid interactive run
    blocks = [i for i in issues if i.severity == "BLOCK"]
    assert blocks == [], f"unexpected BLOCK after interactive enrol: {blocks}"


def test_student_validate_authorship_cli(isolated_localappdata, tmp_path):
    save_authorship("p", VALID)
    body = tmp_path / "current_body.txt"
    body.write_text(
        "One. Two. Three. Four. Five. Six. Seven.\n", encoding="utf-8",
    )
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(isolated_localappdata)
    r = subprocess.run(
        [sys.executable, str(STUDENT_PY), "validate",
         "--path", str(body), "--authorship", "p"],
        capture_output=True, text=True, timeout=15, env=env,
    )
    assert "authorship" in r.stdout.lower()
    # VALID data should yield OK in authorship; format validator will fail on sentence count — that's fine.


def test_enroll_authors_subcommand_in_help():
    r = subprocess.run(
        [sys.executable, str(STUDENT_PY), "help"],
        capture_output=True, text=True, timeout=10,
    )
    assert "enroll-authors" in r.stdout
