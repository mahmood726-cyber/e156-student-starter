"""S-P0-4 closure test: cloud credentials must not be importable from ai_call.

The v0.3.2 review flagged that GITHUB_TOKEN / GEMINI_API_KEY were held as
module-level constants in ai_call.py — any code in the same Python process
could `from ai.ai_call import GITHUB_TOKEN`. v0.4.0-rc1 moves the actual
HTTP call to ai/cloud_subproc.py and removes the module-level constants.
This test pins that contract."""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _import_path():
    sys.path.insert(0, str(REPO_ROOT))
    yield
    sys.path.pop(0)


def test_ai_call_does_not_expose_github_token_module_constant():
    """If a malicious package imports ai.ai_call, it must not get GITHUB_TOKEN."""
    if "ai.ai_call" in sys.modules:
        del sys.modules["ai.ai_call"]
    os.environ["GITHUB_TOKEN"] = "should-not-leak-into-module-namespace"
    try:
        mod = importlib.import_module("ai.ai_call")
        assert not hasattr(mod, "GITHUB_TOKEN"), \
            "ai_call.GITHUB_TOKEN must not exist as a module-level constant"
    finally:
        os.environ.pop("GITHUB_TOKEN", None)


def test_ai_call_does_not_expose_gemini_api_key_module_constant():
    if "ai.ai_call" in sys.modules:
        del sys.modules["ai.ai_call"]
    os.environ["GEMINI_API_KEY"] = "should-not-leak-into-module-namespace"
    try:
        mod = importlib.import_module("ai.ai_call")
        assert not hasattr(mod, "GEMINI_API_KEY"), \
            "ai_call.GEMINI_API_KEY must not exist as a module-level constant"
    finally:
        os.environ.pop("GEMINI_API_KEY", None)


def test_cloud_subproc_script_exists_and_is_callable():
    """The subprocess that does the actual HTTP call must exist and parse stdin."""
    import subprocess
    child = REPO_ROOT / "ai" / "cloud_subproc.py"
    assert child.is_file(), f"missing {child}"
    proc = subprocess.run(
        [sys.executable, str(child)],
        input='{"provider":"unknown","model":"x","prompt":"y"}',
        capture_output=True, text=True, timeout=10,
    )
    assert proc.returncode == 0
    import json
    out = json.loads(proc.stdout)
    assert out["ok"] is False
    assert "unknown provider" in out["error"]
