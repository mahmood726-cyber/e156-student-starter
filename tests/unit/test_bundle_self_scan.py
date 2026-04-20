"""The bundle must pass `student sentinel check` on itself, with zero BLOCKs.

This is a regression test for a v0.2.1 ship bug: new files in install/sandbox/
and tools/e156_robustness_engine.py contained Windows paths or literal
placeholder-regex tokens that tripped the shipped rules. Students extracting
the zip and running `student sentinel --repo .` would see 4 BLOCKs.

Any new file that legitimately needs to quote such patterns must include a
`sentinel:skip-file` marker in its first ~1 KB. This test catches violators.
"""
from __future__ import annotations

from pathlib import Path

from tools.sentinel_check import load_rules, scan


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_bundle_self_scan_zero_blocks():
    rules = load_rules()
    findings = scan(REPO_ROOT, rules)
    blocks = [f for f in findings if f.severity == "BLOCK"]
    msg = "\n".join(f"  {f.rule_id}  {f.path}:{f.line_no}  {f.line}" for f in blocks)
    assert blocks == [], (
        f"Bundle has {len(blocks)} BLOCK finding(s) on its own tree. Either fix "
        f"the offending content or add a `sentinel:skip-file` marker in the "
        f"first 1 KB of the file.\nFindings:\n{msg}"
    )


def test_bundle_self_scan_warns_are_known_and_small():
    """Non-zero WARN is acceptable but should stay small (≤2) and the remaining
    WARNs should all come from files we already know need special handling.
    Tightening this bound catches regressions where a new file accidentally
    starts tripping a rule."""
    rules = load_rules()
    findings = scan(REPO_ROOT, rules)
    warns = [f for f in findings if f.severity == "WARN"]
    # Currently exactly 1 WARN: ai/ai_call.py docstring references .iloc[0] as
    # an example student prompt. Adjust the bound if we intentionally accept more.
    assert len(warns) <= 2, (
        f"Bundle now has {len(warns)} WARN(s); either fix the new offenders or "
        f"relax this bound:\n"
        + "\n".join(f"  {f.rule_id}  {f.path}:{f.line_no}" for f in warns)
    )
