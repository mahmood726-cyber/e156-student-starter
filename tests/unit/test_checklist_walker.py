"""Reporting-checklist walker — PRISMA 2020, ROB-2, and future additions."""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tools.checklist_walker import (
    CHECKLISTS_DIR, answers_path, compute_coverage,
    fill_interactive, list_available, load, load_answers,
    save_answers, status,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDENT_PY = REPO_ROOT / "bin" / "student.py"


def test_bundled_checklists_include_prisma_and_rob2():
    ids = {m.id for m in list_available()}
    assert "prisma-2020" in ids
    assert "rob-2" in ids


def test_prisma_has_all_27_base_items_plus_subitems():
    c = load("prisma-2020")
    # Collect all item ids across sections
    ids = [i["id"] for sec in c["sections"] for i in sec["items"]]
    # Main numbers 1..27 should all appear (some as sub-items like 10a/10b)
    main_numbers = set()
    for item_id in ids:
        # extract leading integer
        n = ""
        for ch in item_id:
            if ch.isdigit():
                n += ch
            else:
                break
        main_numbers.add(int(n))
    assert main_numbers == set(range(1, 28)), f"missing main numbers: {set(range(1,28)) - main_numbers}"
    # Spot-check sub-items the PRISMA paper mandates
    for sub in ("10a", "10b", "13a", "13b", "13c", "13d", "13e", "13f",
                "16a", "16b", "20a", "20b", "20c", "20d",
                "23a", "23b", "23c", "23d", "24a", "24b", "24c"):
        assert sub in ids, f"missing PRISMA sub-item {sub}"


def test_rob2_has_5_domains():
    c = load("rob-2")
    assert len(c["sections"]) == 5
    # Each domain must have at least 3 signalling questions
    for sec in c["sections"]:
        assert len(sec["items"]) >= 3, f"domain {sec['id']} has too few signalling questions"


def test_load_missing_checklist_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load("not-real")


def test_save_and_reload_answers(isolated_localappdata):
    data = {"responses": {"1": {"answer": "y", "location": "p.1"}}}
    save_answers("slug-x", "prisma-2020", data)
    reloaded = load_answers("slug-x", "prisma-2020")
    assert reloaded["responses"]["1"]["answer"] == "y"
    # Saving added a timestamp
    assert "updated_at_utc" in reloaded


def test_compute_coverage_counts_y_n_na(isolated_localappdata):
    c = load("prisma-2020")
    answers = {"responses": {
        "1":   {"answer": "y"},
        "2":   {"answer": "n"},
        "3":   {"answer": "na"},
        "10a": {"answer": "y"},
    }}
    cov = compute_coverage(c, answers)
    assert cov["responded"] == 4
    assert cov["yes"] == 2
    assert cov["no"] == 1
    assert cov["na"] == 1
    assert cov["total"] > 27  # includes sub-items


def test_fill_interactive_records_answers(isolated_localappdata):
    # Every prompt returns "y"; no location; then after items done.
    answers_feed = iter(["y", "p.1"] * 200)
    def _input(prompt):
        try:
            return next(answers_feed)
        except StopIteration:
            return ""
    path = fill_interactive("prisma-2020", "demo", input_fn=_input)
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    # All items should be recorded
    c = load("prisma-2020")
    total = sum(len(s["items"]) for s in c["sections"])
    assert len(data["responses"]) == total


def test_status_reports_incomplete(isolated_localappdata):
    save_answers("s", "prisma-2020", {"responses": {"1": {"answer": "y"}}})
    s = status("prisma-2020", "s")
    assert s["responded"] == 1
    assert len(s["missing_ids"]) > 25


def test_cli_list_shows_prisma_and_rob2():
    r = subprocess.run(
        [sys.executable, str(STUDENT_PY), "checklist", "list"],
        capture_output=True, text=True, timeout=10,
    )
    assert r.returncode == 0, r.stderr
    assert "prisma-2020" in r.stdout
    assert "rob-2" in r.stdout


def test_cli_show_prisma(tmp_path):
    r = subprocess.run(
        [sys.executable, str(STUDENT_PY), "checklist", "show", "prisma-2020"],
        capture_output=True, text=True, timeout=10,
    )
    assert r.returncode == 0
    assert "PRISMA 2020" in r.stdout
    assert "[1]" in r.stdout
    assert "[27]" in r.stdout


def test_cli_status_partially_filled(isolated_localappdata):
    save_answers("slug-cli", "prisma-2020", {"responses": {"1": {"answer": "y"}}})
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(isolated_localappdata)
    r = subprocess.run(
        [sys.executable, str(STUDENT_PY), "checklist", "status", "prisma-2020", "--slug", "slug-cli"],
        capture_output=True, text=True, timeout=10, env=env,
    )
    assert r.returncode == 1  # incomplete
    assert "coverage:" in r.stdout


def test_pick_invalid_input_returns_none_not_crash(isolated_localappdata):
    from tools.checklist_walker import pick_checklist
    r = pick_checklist(input_fn=lambda _p: "q")
    assert r is None


def test_pick_systematic_review_maps_to_prisma(isolated_localappdata):
    from tools.checklist_walker import pick_checklist
    # First choice is systematic review -> prisma-2020
    r = pick_checklist(input_fn=lambda _p: "1")
    assert r == "prisma-2020"


def test_checklist_subcommand_in_help():
    r = subprocess.run(
        [sys.executable, str(STUDENT_PY), "help"],
        capture_output=True, text=True, timeout=10,
    )
    assert "checklist" in r.stdout


def test_all_bundled_checklists_are_valid_json_and_have_required_keys():
    for m in list_available():
        c = load(m.id)
        assert "id" in c and c["id"] == m.id
        assert "name" in c
        assert "version" in c
        assert "source" in c
        assert "sections" in c and len(c["sections"]) > 0
        for sec in c["sections"]:
            assert "id" in sec
            assert "name" in sec
            assert "items" in sec and len(sec["items"]) > 0
            for it in sec["items"]:
                assert "id" in it
                assert "text" in it
                assert it["text"].strip(), f"empty text on {m.id}:{it['id']}"
