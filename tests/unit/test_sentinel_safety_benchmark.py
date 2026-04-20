"""Safety-net benchmark: AI outputs routed through Sentinel must flag known-bad cases."""
from __future__ import annotations

import json
from pathlib import Path

from tools.sentinel_safety_benchmark import measure_tier


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures"


def test_tiny_tier_code_debug_triggers_empty_df_rule():
    """The 1.5B's wrong `.iloc[0].values[0]` fix MUST be flagged."""
    report = measure_tier(FIXTURES / "results_tiny_tier.json")
    code_task = next(t for t in report["per_task"] if t["task_id"] == "code_debug")
    assert "P1-empty-dataframe-access" in code_task["rules_triggered"]


def test_tiny_tier_stats_explain_triggers_stats_rule():
    """The 2B's 'I² measures variance within' MUST be flagged."""
    report = measure_tier(FIXTURES / "results_tiny_tier.json")
    stats_task = next(t for t in report["per_task"] if t["task_id"] == "stats_explain")
    assert "P1-stats-misinformation" in stats_task["rules_triggered"]


def test_standard_tier_code_correct_still_pattern_matches():
    """Even the 7B's correct fix includes `.iloc[0]` (with a guard) and gets flagged as WARN.
    That's fine — WARN is advisory, prompts the student to verify the guard exists."""
    report = measure_tier(FIXTURES / "results_standard_tier.json")
    code_task = next(t for t in report["per_task"] if t["task_id"] == "code_debug")
    # The 7B's answer DOES include .iloc[0] pattern (before the empty guard)
    assert "P1-empty-dataframe-access" in code_task["rules_triggered"]


def test_at_least_one_finding_per_tier():
    """Safety net must catch SOMETHING on every known-problematic benchmark run."""
    for fixture in ("results_tiny_tier.json", "results_standard_tier.json"):
        report = measure_tier(FIXTURES / fixture)
        assert report["total_findings"] > 0, \
            f"Safety net failed on {fixture}: no rules fired; library may be broken"
