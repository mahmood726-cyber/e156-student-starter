"""Unit tests for tools/sentinel_check.py — the lightweight bundled scanner."""
from __future__ import annotations

from pathlib import Path
import pytest

from tools import sentinel_check as sc


def test_glob_matches_root_level_py(tmp_path):
    assert sc.path_matches("student.py", ("**/*.py",))


def test_glob_matches_nested_py(tmp_path):
    assert sc.path_matches("src/foo/bar.py", ("**/*.py",))


def test_glob_does_not_cross_segment_with_single_star():
    assert not sc.path_matches("src/foo.py", ("*.py",))


def test_double_star_in_middle():
    assert sc.path_matches("a/b/c/d.py", ("a/**/d.py",))


def test_windows_separator_normalised():
    assert sc.path_matches("src\\foo.py", ("**/*.py",))


def test_loads_vendored_rules(repo_root):
    rules = sc.load_rules(repo_root / "config" / "sentinel" / "rules")
    rule_ids = {r.rule_id for r in rules}
    assert "P0-hardcoded-local-path" in rule_ids
    assert "P1-empty-dataframe-access" in rule_ids
    assert "P1-unpopulated-placeholder" in rule_ids
    assert "P1-silent-failure-sentinel" in rule_ids


def test_catches_ollama_wrong_fix(tmp_path, repo_root):
    """The 1.5B model's `.iloc[0].values[0]` 'fix' must be flagged."""
    bad = tmp_path / "student_code.py"
    bad.write_text(
        "import pandas as pd\n"
        "def first_trial(df, nct_id):\n"
        "    return df[df.nct_id == nct_id].iloc[0].values[0]\n",
        encoding="utf-8",
    )
    rules = sc.load_rules(repo_root / "config" / "sentinel" / "rules")
    findings = sc.scan(tmp_path, rules, rule_id="P1-empty-dataframe-access")
    assert len(findings) == 1
    assert findings[0].severity == "WARN"
    assert findings[0].line_no == 3


def test_skip_file_marker_honoured(tmp_path, repo_root):
    code = tmp_path / "docs.py"
    code.write_text(
        "# sentinel:skip-file — this file intentionally has the pattern\n"
        "x = df.iloc[0]\n",
        encoding="utf-8",
    )
    rules = sc.load_rules(repo_root / "config" / "sentinel" / "rules")
    findings = sc.scan(tmp_path, rules)
    assert findings == []


def test_block_exits_1(tmp_path, repo_root, monkeypatch, capsys):
    bad = tmp_path / "loader.py"
    bad.write_text(r'DATA = r"C:\Users\alice\Projects\data.csv"' + "\n", encoding="utf-8")
    monkeypatch.chdir(repo_root)
    exit_code = sc.main(["--repo", str(tmp_path)])
    assert exit_code == 1
    out = capsys.readouterr().out
    assert "BLOCK" in out
    assert "P0-hardcoded-local-path" in out


def test_clean_repo_exits_0(tmp_path, repo_root, monkeypatch, capsys):
    monkeypatch.chdir(repo_root)
    (tmp_path / "x.py").write_text("print('hello')\n", encoding="utf-8")
    exit_code = sc.main(["--repo", str(tmp_path)])
    assert exit_code == 0
