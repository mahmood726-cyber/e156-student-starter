"""`student memory` seeds the starter pack into %LOCALAPPDATA%\\e156\\memory."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDENT_PY = REPO_ROOT / "bin" / "student.py"


def run_cli(*args, env=None):
    return subprocess.run(
        [sys.executable, str(STUDENT_PY), *args],
        capture_output=True, text=True, timeout=15, env=env,
    )


def test_memory_init_seeds_starter_pack(isolated_localappdata, monkeypatch):
    import os
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(isolated_localappdata)
    r = run_cli("memory", env=env)
    assert r.returncode == 0, r.stderr
    mem = isolated_localappdata / "e156" / "memory"
    assert (mem / "MEMORY.md").exists()
    assert (mem / "starter_e156_format.md").exists()
    assert (mem / "starter_ollama_tier_quirks.md").exists()


def test_memory_init_refuses_without_force(isolated_localappdata):
    import os
    mem = isolated_localappdata / "e156" / "memory"
    mem.mkdir(parents=True)
    (mem / "my_memory.md").write_text("mine\n", encoding="utf-8")
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(isolated_localappdata)
    r = run_cli("memory", env=env)
    assert r.returncode == 1
    # Preserved
    assert (mem / "my_memory.md").exists()


def test_memory_init_force_overwrites(isolated_localappdata):
    import os
    mem = isolated_localappdata / "e156" / "memory"
    mem.mkdir(parents=True)
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(isolated_localappdata)
    r = run_cli("memory", "--force", env=env)
    assert r.returncode == 0
    assert (mem / "starter_e156_format.md").exists()
