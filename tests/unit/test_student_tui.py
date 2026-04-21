"""TUI menu renders action list; falls back to input() prompt when curses unavailable."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDENT_PY = REPO_ROOT / "bin" / "student.py"


def test_tui_fallback_runs_when_curses_missing(monkeypatch):
    """If curses import fails, TUI falls back to plain text menu and does not crash."""
    env = {**__import__("os").environ, "E156_FORCE_CURSES_FAIL": "1"}
    r = subprocess.run(
        [sys.executable, str(STUDENT_PY)],
        capture_output=True, text=True, timeout=5,
        env=env, input="q\n",
    )
    assert r.returncode == 0
    assert "Start a new paper" in r.stdout
    assert "Get unstuck" in r.stdout


def test_tui_shows_all_actions_in_fallback():
    env = {**__import__("os").environ, "E156_FORCE_CURSES_FAIL": "1"}
    r = subprocess.run(
        [sys.executable, str(STUDENT_PY)],
        capture_output=True, text=True, timeout=5,
        env=env, input="q\n",
    )
    for action in ("Start a new paper",
                   "Check my paper",
                   "Ask the AI",
                   "Download data",
                   "Get unstuck",
                   "Quit"):
        assert action in r.stdout


def test_tui_exposes_every_cli_subcommand():
    """TUI coherence gate: every student CLI subcommand (except 'help') must be
    reachable from the menu. Closes the v0.3.2 review finding that 9 subcommands
    were CLI-only."""
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from bin.student import SUBCOMMANDS  # noqa: WPS433
        from bin.tui import MENU  # noqa: WPS433
    finally:
        sys.path.pop(0)

    menu_subcommands = set()
    for action in MENU:
        if not action.subcommand:
            continue
        # `data pull` -> `data` (subcommand root)
        menu_subcommands.add(action.subcommand.split()[0])

    missing = set(SUBCOMMANDS) - menu_subcommands - {"help"}
    assert not missing, f"TUI missing CLI subcommands: {sorted(missing)}"
