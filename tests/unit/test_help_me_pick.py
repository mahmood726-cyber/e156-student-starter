"""Three yes/no questions map to one of T1..T5 with a 'recommended' badge."""
from __future__ import annotations

import io
import pytest
from bin.help_me_pick import recommend


@pytest.mark.parametrize("answers,expected", [
    # (pools_drugs, one_country_one_condition, rerunning_a_published_MA) -> template
    (("n", "n", "n"), "T5"),   # Living MA seed
    (("y", "n", "n"), "T1"),   # Pairwise mini-MA
    (("n", "y", "n"), "T3"),   # Burden snapshot
    (("n", "n", "y"), "T4"),   # Replication
    (("y", "n", "y"), "T4"),   # Replication wins over pairwise if rerunning
    (("n", "y", "y"), "T4"),   # Replication wins over burden if rerunning
])
def test_recommend_maps_answers_to_template(answers, expected):
    assert recommend(*answers) == expected


def test_default_is_T1_when_nothing_picked():
    # If all answers are empty / ambiguous, fall back to T1 (most common first project)
    assert recommend("", "", "") == "T1"


def test_is_stub_detects_stub_marker():
    """All T1..T5 ship as stubs in v0.4.0-rc1; T0 is real. Rule: if .stub exists, it's a stub."""
    from bin.help_me_pick import is_stub
    for code in ("T1", "T2", "T3", "T4", "T5"):
        assert is_stub(code), f"{code} should be reported as a stub"
    assert not is_stub("T0"), "T0_blank is a real template, not a stub"


def test_run_shows_honest_status_when_recommendation_is_stub(monkeypatch, capsys):
    """When recommend() returns a stub, run() must NOT badge it as Recommended,
    must say so, and must offer T0 as the actually-runnable fallback."""
    import bin.help_me_pick as hmp
    # Three "y" answers + accept the suggested template
    answers = iter(["y", "n", "n", "y"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    rc = hmp.run()
    out = capsys.readouterr().out
    assert rc == 0
    # T1 is a stub — must NOT carry the recommended badge
    assert "[\u2605 Recommended] T1" not in out
    assert "NOT YET IMPLEMENTED" in out
    # Fallback to T0 must be visible AND in the next-run command
    assert "T0" in out
    assert "student new --template T0" in out
