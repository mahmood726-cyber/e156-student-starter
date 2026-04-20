"""Pre-warm is fire-and-forget — wizard must not block on it and must survive
a missing Ollama endpoint without error.
"""
from __future__ import annotations

import io
import time

from bin import first_run_wizard


def _fake_stdin(lines):
    return io.StringIO("\n".join(lines) + "\n")


def test_prewarm_does_not_block(monkeypatch):
    """Pre-warm spawns a thread; the function itself must return in well under 1s."""
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:1")  # unreachable port
    start = time.monotonic()
    first_run_wizard._prewarm_prose_model()
    elapsed = time.monotonic() - start
    assert elapsed < 1.0, f"_prewarm_prose_model blocked for {elapsed:.2f}s"


def test_wizard_with_prewarm_disabled_flag(isolated_localappdata, monkeypatch):
    """prewarm=False lets tests skip the thread entirely for cleanliness."""
    monkeypatch.setattr("sys.stdin", _fake_stdin([
        "AGREE", "Ada", "ada@mak.ac.ug", "n",
    ]))
    exit_code = first_run_wizard.run_wizard(skip_smoke=True, prewarm=False)
    assert exit_code == 0


def test_wizard_with_prewarm_enabled_survives_no_ollama(isolated_localappdata, monkeypatch):
    """With prewarm=True but Ollama unreachable, the wizard still succeeds."""
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:1")
    monkeypatch.setattr("sys.stdin", _fake_stdin([
        "AGREE", "Ada", "ada@mak.ac.ug", "n",
    ]))
    exit_code = first_run_wizard.run_wizard(skip_smoke=True, prewarm=True)
    assert exit_code == 0
