"""tools.project_paths — single source of truth for every path the bundle uses."""
from __future__ import annotations

from pathlib import Path

from tools import project_paths as pp


def test_bundle_root_resolves_to_repo(repo_root):
    assert pp.bundle_root() == repo_root


def test_state_root_follows_localappdata(isolated_localappdata):
    assert pp.e156_state_root() == isolated_localappdata / "e156"


def test_workbook_under_state_root(isolated_localappdata):
    assert pp.workbook_root().parent == pp.e156_state_root()
    assert pp.workbook_root().name == "workbook"


def test_paper_dir_is_under_workbook(isolated_localappdata):
    assert pp.paper_dir("my-slug") == pp.workbook_root() / "my-slug"


def test_logs_dir_under_state_root(isolated_localappdata):
    assert pp.logs_dir() == pp.e156_state_root() / "logs"


def test_audit_log_and_bypass_log_paths(isolated_localappdata):
    assert pp.audit_log_path() == pp.logs_dir() / "ai_calls.jsonl"
    assert pp.bypass_log_path() == pp.logs_dir() / "bypass.log"


def test_baseline_store_path(isolated_localappdata):
    assert pp.baseline_store_path() == pp.e156_state_root() / "baseline.json"


def test_consent_and_installed_marker_paths(isolated_localappdata):
    assert pp.consent_path() == pp.e156_state_root() / ".consent.json"
    assert pp.installed_marker_path() == pp.e156_state_root() / ".installed"


def test_no_module_in_bundle_uses_expanduser_directly():
    """Catch regressions: every path-generating module should go through
    project_paths.py and not raw expanduser/~.

    Exceptions: project_paths.py itself; ai/audit_log.py (predates this);
    ai/ai_call.py (predates this); tools/baseline.py (predates this);
    tools/publish_pack.py (predates this); first_run_wizard.py (predates).

    This test documents current state; removing exceptions as we migrate
    modules to use tools.project_paths.
    """
    repo = Path(__file__).resolve().parents[2]
    exceptions = {
        "tools/project_paths.py",
        "ai/audit_log.py",
        "ai/ai_call.py",
        "tools/baseline.py",
        "tools/publish_pack.py",
        "bin/first_run_wizard.py",
        "tools/dashboard.py",
        "tools/drift_detector.py",
        "tools/get_unstuck.py",
        "tools/validate_e156.py",
        "bin/student.py",
        "bin/scaffold.py",
        "tools/authorship.py",
    }
    offenders = []
    for py in repo.rglob("*.py"):
        rel = py.relative_to(repo).as_posix()
        if rel in exceptions:
            continue
        if rel.startswith("tests/"):
            continue
        text = py.read_text(encoding="utf-8", errors="replace")
        if "expanduser" in text or 'Path.home()' in text:
            offenders.append(rel)
    # Currently all offenders are listed as exceptions. This test fails when
    # a NEW module is added that uses expanduser without routing through
    # project_paths.
    assert offenders == [], (
        f"New modules using expanduser/~. Route through tools.project_paths "
        f"or add to the exceptions list in this test: {offenders}"
    )
