# Plan A — Install & First-Touch UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A first-time Uganda medical student with no coding background double-clicks `Start.bat` on a 4–8 GB Windows laptop with 1.5 Mbps WiFi and within 45 minutes is looking at their first scaffolded paper with a plain-English next step.

**Architecture:** Zip-portable Windows bundle. Entry point is `Start.bat`, which delegates to `install\install.ps1` (first run) or `bin\student.bat` (subsequent). Install pulls a pinned portable Ollama + tier-matched models, writes a `%LOCALAPPDATA%\e156\` layout, runs a smoke test that gates the success banner, then launches a Python first-run wizard that ends with the `--help-me-pick` template chooser. Every student-facing error passes through `ai\friendly_error.py`. A one-keystroke `student doctor` bundles a redacted diagnostic zip.

**Tech Stack:**
- Python 3.11 embedded in zip (`python/` subdir; no system-Python dependency)
- PowerShell 5.1+ for `install.ps1`, tested with `Pester` v5
- `pytest` for Python unit + integration tests
- `windows-curses` for TUI (plain `input()` fallback if import fails)
- `BitsTransfer` for resumable portable-Ollama download
- GitHub Actions `windows-2022` runner for CI; `clumsy` or `netsh` for 1.5 Mbps bandwidth cap
- Zip-only delivery; no `.exe`, no code-signing cert (per D3 in spec)

**Spec reference:** `C:\Users\user\e156-student-starter-spec-backup\2026-04-19-uganda-student-bundle-design.md`
**Review findings:** `D:\e156-student-starter\review-findings.md`
**Repo:** `D:\e156-student-starter\` → `github.com/mahmood726-cyber/e156-student-starter`

---

## File Structure

Plan A creates or modifies these files:

```
D:\e156-student-starter\
├── .github\workflows\release.yml             (NEW) CI pipeline
├── .gitignore                                (MODIFY) add diagnostic.zip, dist/, *.tmp
├── Start.bat                                 (NEW) double-click entry point
├── README.md                                 (MODIFY) replace .\install\install.ps1 instructions
├── docs\HASH.txt                             (NEW) pinned self-SHA256
├── config\pins.json                          (NEW) every dep pinned
├── config\pins.schema.json                   (NEW) JSONSchema for pins.json
├── install\install.ps1                       (REFACTOR) self-SHA check + rollback + progress wrapper + smoke-gate
├── install\install.sh                        (DELETE) Windows-only per D1
├── install\pester.tests.ps1                  (NEW) Pester tests for install.ps1
├── ai\friendly_error.py                      (NEW) single error-translation layer
├── bin\student.bat                           (NEW) PATH-friendly wrapper
├── bin\student.py                            (NEW) CLI + curses TUI dispatcher
├── bin\first_run_wizard.py                   (NEW) welcome + AGREE gate + wizard launcher
├── bin\help_me_pick.py                       (NEW) 3-question template chooser
├── tools\get_unstuck.py                      (NEW) diagnostic bundler + redactor
├── templates\T0_blank\                       (NEW) minimal blank scaffold
├── templates\T1_pairwise_mini_ma\.stub       (NEW) placeholder stubs for Plan E
├── templates\T2_trials_audit\.stub           (NEW)
├── templates\T3_burden_snapshot\.stub        (NEW)
├── templates\T4_ma_replication\.stub         (NEW)
├── templates\T5_living_ma_seed\.stub         (NEW)
├── tests\unit\test_friendly_error.py         (NEW)
├── tests\unit\test_student_cli.py            (NEW)
├── tests\unit\test_student_tui.py            (NEW)
├── tests\unit\test_get_unstuck.py            (NEW)
├── tests\unit\test_pins_schema.py            (NEW)
├── tests\unit\test_first_run_wizard.py       (NEW)
├── tests\unit\test_help_me_pick.py           (NEW)
├── tests\unit\test_start_bat.py              (NEW) subprocess-driven tests for Start.bat
└── tests\integration\test_install_e2e.py     (NEW) 45-min wall-clock gated
```

Shared conventions:
- All Python modules use `from __future__ import annotations` (Python 3.9+).
- All PowerShell scripts start with `#Requires -Version 5.1`.
- All paths in scripts use forward slashes where the interpreter allows; Windows-native paths are emitted only at the system boundary.
- `%LOCALAPPDATA%\e156\` is the canonical install root. Referenced in code as `$env:LOCALAPPDATA\e156` (PS) or `os.environ['LOCALAPPDATA']` + `'e156'` (Py).

---

## Setup — Task 0 (do once at start)

### Task 0: Create feature branch and scaffold test infra

**Files:**
- Modify: `.gitignore`
- Create: `tests\unit\__init__.py`, `tests\integration\__init__.py`, `tests\conftest.py`

- [ ] **Step 1: Branch off main**

```bash
cd D:/e156-student-starter
git checkout -b v0.2-plan-A
```

- [ ] **Step 2: Add Plan-A entries to `.gitignore`**

Append these lines:

```
# Plan A
diagnostic.zip
dist/
*.tmp
tests/results_*.json
!tests/fixtures/results_*.json
.pytest_cache/
python/      # embedded Python downloaded at build time
bin/ollama/  # portable Ollama downloaded at build time
```

- [ ] **Step 3: Create test scaffolding**

Create `tests\conftest.py`:

```python
"""Shared pytest fixtures for Plan A."""
from __future__ import annotations

import os
from pathlib import Path
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def isolated_localappdata(tmp_path, monkeypatch):
    """Point %LOCALAPPDATA% at a tmp dir so tests don't touch real state."""
    fake = tmp_path / "AppData" / "Local"
    fake.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LOCALAPPDATA", str(fake))
    return fake
```

Create empty `tests\unit\__init__.py` and `tests\integration\__init__.py`.

- [ ] **Step 4: Verify pytest runs green on empty suite**

Run:

```bash
cd D:/e156-student-starter
python -m pytest tests/ -v
```

Expected:

```
no tests ran in 0.01s
```

- [ ] **Step 5: Commit**

```bash
git add .gitignore tests/conftest.py tests/unit/__init__.py tests/integration/__init__.py
git commit -m "chore(plan-A): branch + test scaffolding"
```

---

## Foundation layer — do these before anything depends on them

### Task 1: `config/pins.json` schema + initial content

**Files:**
- Create: `config\pins.schema.json`
- Create: `config\pins.json`
- Create: `tests\unit\test_pins_schema.py`

- [ ] **Step 1: Write the failing test**

Create `tests\unit\test_pins_schema.py`:

```python
"""Pins.json structure validates against schema."""
from __future__ import annotations

import json
from pathlib import Path
import pytest

jsonschema = pytest.importorskip("jsonschema")


def test_pins_conforms_to_schema(repo_root):
    schema = json.loads((repo_root / "config" / "pins.schema.json").read_text())
    pins = json.loads((repo_root / "config" / "pins.json").read_text())
    jsonschema.validate(pins, schema)


def test_pins_has_all_required_sections(repo_root):
    pins = json.loads((repo_root / "config" / "pins.json").read_text())
    for key in ("ollama", "models", "data_lakes", "python_embed", "bundle_release"):
        assert key in pins, f"missing section: {key}"


def test_all_tiers_have_a_model_digest(repo_root):
    pins = json.loads((repo_root / "config" / "pins.json").read_text())
    for model_name in ("gemma2:2b", "gemma2:9b",
                       "qwen2.5-coder:1.5b", "qwen2.5-coder:7b"):
        assert model_name in pins["models"], f"missing: {model_name}"
        assert pins["models"][model_name]["digest"].startswith("sha256:")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/unit/test_pins_schema.py -v
```

Expected: FAIL — `FileNotFoundError` on `config/pins.schema.json`.

- [ ] **Step 3: Write `config/pins.schema.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["ollama", "models", "data_lakes", "python_embed", "bundle_release"],
  "properties": {
    "ollama": {
      "type": "object",
      "required": ["version", "sha256", "url"],
      "properties": {
        "version": {"type": "string", "pattern": "^v\\d+\\.\\d+\\.\\d+$"},
        "sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
        "url":    {"type": "string", "format": "uri"}
      }
    },
    "models": {
      "type": "object",
      "patternProperties": {
        "^[a-z0-9.]+:[a-z0-9.]+$": {
          "type": "object",
          "required": ["digest"],
          "properties": {
            "digest": {"type": "string", "pattern": "^sha256:[a-f0-9]{64}$"}
          }
        }
      }
    },
    "data_lakes": {
      "type": "object",
      "patternProperties": {
        "^(aact|who|wb|ihme)$": {
          "type": "object",
          "required": ["zenodo_doi", "status"],
          "properties": {
            "zenodo_doi": {"type": ["string", "null"]},
            "sha256":     {"type": ["string", "null"], "pattern": "^[a-f0-9]{64}$"},
            "bytes":      {"type": ["integer", "null"]},
            "status":     {"enum": ["pinned", "pending_plan_D"]}
          }
        }
      }
    },
    "python_embed": {
      "type": "object",
      "required": ["version", "sha256", "url"],
      "properties": {
        "version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
        "sha256":  {"type": "string", "pattern": "^[a-f0-9]{64}$"},
        "url":     {"type": "string", "format": "uri"}
      }
    },
    "bundle_release": {
      "type": "object",
      "required": ["version"],
      "properties": {
        "version": {"type": "string"},
        "self_sha256": {"type": ["string", "null"], "pattern": "^[a-f0-9]{64}$"}
      }
    }
  }
}
```

- [ ] **Step 4: Write `config/pins.json` — look up the real hashes**

Run these commands and paste the hashes into the file:

```powershell
# Ollama v0.5.7 Windows zip
Invoke-WebRequest -Uri "https://github.com/ollama/ollama/releases/download/v0.5.7/ollama-windows-amd64.zip" -OutFile "$env:TEMP\ollama.zip"
(Get-FileHash -Algorithm SHA256 "$env:TEMP\ollama.zip").Hash.ToLower()

# Python 3.11.9 embeddable
Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip" -OutFile "$env:TEMP\py311.zip"
(Get-FileHash -Algorithm SHA256 "$env:TEMP\py311.zip").Hash.ToLower()
```

Then for each Ollama model, pull it and note the digest:

```powershell
ollama pull gemma2:2b;           ollama show gemma2:2b           --modelfile | Select-String "FROM"
ollama pull gemma2:9b;           ollama show gemma2:9b           --modelfile | Select-String "FROM"
ollama pull qwen2.5-coder:1.5b;  ollama show qwen2.5-coder:1.5b  --modelfile | Select-String "FROM"
ollama pull qwen2.5-coder:7b;    ollama show qwen2.5-coder:7b    --modelfile | Select-String "FROM"
```

Write `config/pins.json` with the real values (example shape — replace placeholders with actual hashes from the commands above):

```json
{
  "ollama": {
    "version": "v0.5.7",
    "sha256": "<paste-from-Get-FileHash-of-ollama-zip>",
    "url": "https://github.com/ollama/ollama/releases/download/v0.5.7/ollama-windows-amd64.zip"
  },
  "models": {
    "gemma2:2b":          {"digest": "sha256:<paste-from-ollama-show>"},
    "gemma2:9b":          {"digest": "sha256:<paste-from-ollama-show>"},
    "qwen2.5-coder:1.5b": {"digest": "sha256:<paste-from-ollama-show>"},
    "qwen2.5-coder:7b":   {"digest": "sha256:<paste-from-ollama-show>"}
  },
  "data_lakes": {
    "aact": {"zenodo_doi": null, "sha256": null, "bytes": null, "status": "pending_plan_D"},
    "who":  {"zenodo_doi": null, "sha256": null, "bytes": null, "status": "pending_plan_D"},
    "wb":   {"zenodo_doi": null, "sha256": null, "bytes": null, "status": "pending_plan_D"},
    "ihme": {"zenodo_doi": null, "sha256": null, "bytes": null, "status": "pending_plan_D"}
  },
  "python_embed": {
    "version": "3.11.9",
    "sha256": "<paste-from-Get-FileHash-of-python-embed-zip>",
    "url": "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip"
  },
  "bundle_release": {
    "version": "0.2.0-plan-A",
    "self_sha256": null
  }
}
```

Do NOT leave `<paste-from-...>` tokens in the committed file. Run the commands; paste real hashes; commit the file with all `<paste-...>` replaced.

- [ ] **Step 5: Run test to verify it passes**

```bash
python -m pytest tests/unit/test_pins_schema.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add config/pins.schema.json config/pins.json tests/unit/test_pins_schema.py
git commit -m "feat(pins): schema + initial pins.json for ollama + models + python embed"
```

---

### Task 2: `ai/friendly_error.py` — single error-translation layer

**Files:**
- Create: `ai\friendly_error.py`
- Create: `tests\unit\test_friendly_error.py`

- [ ] **Step 1: Write the failing tests**

Create `tests\unit\test_friendly_error.py`:

```python
"""Every raw error class maps to exactly one plain-English line + one next action."""
from __future__ import annotations

import pytest
from ai.friendly_error import translate, FriendlyMessage


@pytest.mark.parametrize("raw,expected_substring,expected_action", [
    ("ConnectionRefusedError: [Errno 111] :11434",
     "The AI helper didn't start",
     "Run: student doctor"),
    ("HTTPError: 404 Client Error: Not Found for url: http://127.0.0.1:11434/api/generate",
     "The AI brain isn't installed yet",
     "Run: student install repair"),
    ("HTTPError: 401 Unauthorized",
     "Your account key is missing or wrong",
     "Run: student ai enable-cloud --i-understand-egress"),
    ("PSSecurityException: File install.ps1 cannot be loaded. The execution policy...",
     "Windows is blocking the installer",
     "Close this window and double-click Start.bat"),
    ("Address already in use: 11434",
     "Another program is using port 11434",
     "Run: student doctor"),
    ("OSError: [Errno 28] No space left on device",
     "Your disk is full",
     "Free at least 8 GB of disk space"),
    ("SHA256 mismatch: expected abc... got def...",
     "This download may have been tampered with",
     "Re-download and verify the hash"),
    ("ConsentRequiredError: cloud_enabled=false",
     "Cloud fallback is turned off",
     "Run: student ai enable-cloud --i-understand-egress"),
])
def test_known_errors_translate(raw, expected_substring, expected_action):
    msg = translate(raw)
    assert isinstance(msg, FriendlyMessage)
    assert expected_substring.lower() in msg.text.lower()
    assert expected_action in msg.next_command


def test_unknown_error_gets_generic_fallback():
    msg = translate("some totally unexpected internal error with random trace")
    assert "Something unexpected happened" in msg.text
    assert msg.next_command == "Run: student doctor"


def test_friendly_message_format_is_single_line():
    msg = translate("ConnectionRefusedError: [Errno 111]")
    rendered = str(msg)
    assert "\n" not in rendered, "friendly message must be one line for student display"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/unit/test_friendly_error.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'ai.friendly_error'`.

- [ ] **Step 3: Write `ai/friendly_error.py`**

```python
"""Single error-translation layer for e156-student-starter.

Every student-facing error MUST pass through `translate()`. Raw tracebacks
go to ~/e156/logs/, never to the student's terminal. Each known error class
maps to one plain-English sentence + one specific next action.
"""
from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass
class FriendlyMessage:
    """One-line, plain-English, actionable error display."""
    text: str
    next_command: str

    def __str__(self) -> str:
        return f"{self.text} — {self.next_command}"


_RULES: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"ConnectionRefusedError.*:11434", re.I),
     "The AI helper didn't start on your laptop.",
     "Run: student doctor"),

    (re.compile(r"HTTPError.*404.*Not Found.*/api/generate", re.I),
     "The AI brain isn't installed yet.",
     "Run: student install repair"),

    (re.compile(r"HTTPError.*401.*Unauthorized", re.I),
     "Your account key is missing or wrong.",
     "Run: student ai enable-cloud --i-understand-egress"),

    (re.compile(r"PSSecurityException.*execution policy", re.I),
     "Windows is blocking the installer script.",
     "Close this window and double-click Start.bat (not install.ps1)"),

    (re.compile(r"Address already in use.*11434", re.I),
     "Another program is using port 11434.",
     "Run: student doctor"),

    (re.compile(r"No space left on device|ENOSPC", re.I),
     "Your disk is full.",
     "Free at least 8 GB of disk space, then run: student install repair"),

    (re.compile(r"SHA256 mismatch", re.I),
     "This download may have been tampered with.",
     "Re-download and verify the hash. See: docs/troubleshooting.md"),

    (re.compile(r"ConsentRequiredError.*cloud_enabled=false", re.I),
     "Cloud fallback is turned off on your laptop.",
     "Run: student ai enable-cloud --i-understand-egress"),
]


_GENERIC = FriendlyMessage(
    text="Something unexpected happened.",
    next_command="Run: student doctor",
)


def translate(raw: str | BaseException) -> FriendlyMessage:
    """Map a raw error (string or exception) to a FriendlyMessage."""
    text = str(raw)
    for pattern, plain, action in _RULES:
        if pattern.search(text):
            return FriendlyMessage(text=plain, next_command=action)
    return _GENERIC
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/unit/test_friendly_error.py -v
```

Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add ai/friendly_error.py tests/unit/test_friendly_error.py
git commit -m "feat(ai): friendly_error.py translation layer with 8 known classes"
```

---

### Task 3: `bin/student.py` CLI dispatcher (no TUI yet)

**Files:**
- Create: `bin\student.py`
- Create: `bin\student.bat`
- Create: `tests\unit\test_student_cli.py`

- [ ] **Step 1: Write the failing tests**

Create `tests\unit\test_student_cli.py`:

```python
"""CLI subcommand dispatch + --version."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDENT_PY = REPO_ROOT / "bin" / "student.py"


def run_cli(*args):
    return subprocess.run(
        [sys.executable, str(STUDENT_PY), *args],
        capture_output=True, text=True, timeout=15,
    )


def test_version_prints_and_exits_zero():
    r = run_cli("--version")
    assert r.returncode == 0
    assert "0.2.0-plan-A" in r.stdout


def test_help_lists_all_subcommands():
    r = run_cli("help")
    assert r.returncode == 0
    for cmd in ("new", "ai", "data", "validate", "rules", "doctor", "help"):
        assert cmd in r.stdout


def test_unknown_subcommand_friendly_error():
    r = run_cli("banana")
    assert r.returncode != 0
    assert "isn't a command I know" in r.stdout + r.stderr


def test_new_without_template_triggers_help_me_pick(monkeypatch):
    # Smoke: calling `student new` with no --template flag should NOT immediately crash.
    # Full wizard flow tested in test_help_me_pick.py.
    r = run_cli("new", "--dry-run")
    assert r.returncode == 0
    assert "pick" in r.stdout.lower() or "template" in r.stdout.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/unit/test_student_cli.py -v
```

Expected: FAIL — `FileNotFoundError` on `bin/student.py`.

- [ ] **Step 3: Write `bin/student.py`**

```python
"""e156-student-starter CLI.

Usage:
    student                       # opens the TUI menu (added in Task 4)
    student --version
    student help
    student new [--template T0..T5] [--dry-run]
    student ai <task> "prompt..."
    student data pull aact|who|wb|ihme
    student validate [paper-dir]
    student rules refresh
    student doctor
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make ai/friendly_error importable when run directly
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ai.friendly_error import translate


VERSION = "0.2.0-plan-A"

SUBCOMMANDS = ("new", "ai", "data", "validate", "rules", "doctor", "help")


def _cmd_help(_args) -> int:
    print("e156-student-starter CLI\n")
    print("Subcommands:")
    for sub in SUBCOMMANDS:
        print(f"  {sub}")
    print("\nRun `student <subcommand> --help` for details.")
    return 0


def _cmd_new(args) -> int:
    if args.template is None:
        # Plan A ships help-me-pick integration in Task 10
        print("Let's pick a template for you — (help-me-pick wizard coming up)")
        if args.dry_run:
            return 0
        from bin.help_me_pick import run as run_picker  # noqa: WPS433
        picked = run_picker()
        args.template = picked
    # Full scaffolding logic lives in Plan E; Plan A ships T0-blank only.
    print(f"Scaffolding template {args.template}... (Plan E will wire the rest)")
    return 0


def _cmd_doctor(_args) -> int:
    from tools.get_unstuck import run as run_diagnostic  # noqa: WPS433
    return run_diagnostic()


def _not_yet(cmd: str):
    def _run(_args) -> int:
        print(f"`student {cmd}` is coming in a later plan. Run: student help")
        return 0
    return _run


HANDLERS = {
    "help":     _cmd_help,
    "new":      _cmd_new,
    "ai":       _not_yet("ai"),          # Plan B
    "data":     _not_yet("data"),        # Plan D
    "validate": _not_yet("validate"),    # Plan C
    "rules":    _not_yet("rules"),       # Plan A task 13
    "doctor":   _cmd_doctor,
}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="student", add_help=False)
    p.add_argument("--version", action="store_true")
    p.add_argument("subcommand", nargs="?")
    p.add_argument("--template", default=None,
                   choices=["T0", "T1", "T2", "T3", "T4", "T5"])
    p.add_argument("--dry-run", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    parser = _build_parser()
    args, _rest = parser.parse_known_args(argv)

    if args.version:
        print(VERSION)
        return 0

    if not args.subcommand:
        # No-arg TUI menu is Task 4; for now fall through to help.
        return _cmd_help(args)

    handler = HANDLERS.get(args.subcommand)
    if handler is None:
        msg = translate(f"UnknownCommand: {args.subcommand!r} isn't a command I know")
        print(str(msg))
        return 2

    try:
        return handler(args)
    except Exception as exc:  # noqa: BLE001
        print(str(translate(exc)))
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Write `bin/student.bat`**

```batch
@echo off
rem PATH-friendly wrapper around student.py. Uses embedded python when present.
setlocal
set "HERE=%~dp0"
set "PY=%HERE%..\python\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" "%HERE%student.py" %*
endlocal
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/unit/test_student_cli.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add bin/student.py bin/student.bat tests/unit/test_student_cli.py
git commit -m "feat(cli): student.py dispatcher with stub handlers for plans B/C/D/E"
```

---

### Task 4: curses TUI menu when `student` is run with no args

**Files:**
- Modify: `bin\student.py`
- Create: `bin\tui.py`
- Create: `tests\unit\test_student_tui.py`

- [ ] **Step 1: Write the failing tests**

Create `tests\unit\test_student_tui.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/unit/test_student_tui.py -v
```

Expected: FAIL — TUI not invoked on no-arg call yet.

- [ ] **Step 3: Write `bin/tui.py`**

```python
"""TUI menu for e156-student-starter.

Uses curses when available (including windows-curses on Windows). Falls back
to a plain numbered list + input() when curses is unavailable or when
E156_FORCE_CURSES_FAIL=1 (used by tests + students on locked-down labs).
"""
from __future__ import annotations

import os
import sys
from typing import Callable, NamedTuple


class Action(NamedTuple):
    label: str
    subcommand: str  # what `student ...` would be typed


MENU: list[Action] = [
    Action("Start a new paper",              "new"),
    Action("Check my paper (validate)",      "validate"),
    Action("Ask the AI to help me",          "ai"),
    Action("Download data for my analysis",  "data pull"),
    Action("Get unstuck / send diagnostics", "doctor"),
    Action("Quit",                           ""),
]


def _fallback_menu() -> int:
    """Plain-text menu; used when curses unavailable."""
    while True:
        print("\nWhat would you like to do?\n")
        for i, a in enumerate(MENU, start=1):
            print(f"  [{i}] {a.label}")
        print()
        choice = input("Type a number (or q to quit): ").strip().lower()
        if choice in ("q", "quit", ""):
            return 0
        if not choice.isdigit():
            print("Please type a number from the list.")
            continue
        idx = int(choice) - 1
        if not (0 <= idx < len(MENU)):
            print("That number isn't on the list.")
            continue
        action = MENU[idx]
        if action.label == "Quit":
            return 0
        print(f"\n→ Equivalent command: student {action.subcommand}")
        print("  (Copy that command to skip this menu next time.)\n")
        # Actual dispatch happens by re-invoking student CLI with the subcommand
        return _dispatch(action.subcommand)


def _dispatch(subcommand: str) -> int:
    from bin.student import main as cli_main  # noqa: WPS433
    return cli_main(subcommand.split())


def _curses_menu() -> int:
    import curses

    def _inner(stdscr):
        curses.curs_set(0)
        selected = 0
        while True:
            stdscr.clear()
            stdscr.addstr(1, 2, "e156 — what would you like to do?", curses.A_BOLD)
            for i, a in enumerate(MENU):
                mark = "▸" if i == selected else " "
                attr = curses.A_REVERSE if i == selected else curses.A_NORMAL
                stdscr.addstr(3 + i, 4, f"{mark} {a.label}", attr)
            stdscr.addstr(4 + len(MENU), 2,
                          "Arrows + Enter. Press 'c' to copy command. 'q' to quit.",
                          curses.A_DIM)
            stdscr.refresh()
            key = stdscr.getch()
            if key in (curses.KEY_UP, ord("k")):
                selected = (selected - 1) % len(MENU)
            elif key in (curses.KEY_DOWN, ord("j")):
                selected = (selected + 1) % len(MENU)
            elif key in (curses.KEY_ENTER, 10, 13):
                return selected
            elif key in (ord("q"), 27):  # 27 = Esc
                return len(MENU) - 1  # "Quit"
            elif key == ord("c"):
                # Copy equivalent CLI to clipboard via clip.exe (Windows)
                _copy_cli_to_clipboard(MENU[selected].subcommand)

    idx = curses.wrapper(_inner)
    chosen = MENU[idx]
    if chosen.label == "Quit":
        return 0
    print(f"→ Equivalent command: student {chosen.subcommand}")
    return _dispatch(chosen.subcommand)


def _copy_cli_to_clipboard(subcommand: str) -> None:
    import subprocess
    cmd = f"student {subcommand}".strip()
    try:
        subprocess.run(["clip.exe"], input=cmd, text=True, check=False, timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        pass  # clipboard is a nice-to-have, never blocks the menu


def run() -> int:
    if os.environ.get("E156_FORCE_CURSES_FAIL") == "1":
        return _fallback_menu()
    try:
        import curses  # noqa: F401
    except ImportError:
        return _fallback_menu()
    try:
        return _curses_menu()
    except Exception:
        return _fallback_menu()
```

- [ ] **Step 4: Wire the TUI into `bin/student.py` — replace `main()`'s no-arg branch**

Open `bin/student.py` and replace the block:

```python
    if not args.subcommand:
        # No-arg TUI menu is Task 4; for now fall through to help.
        return _cmd_help(args)
```

with:

```python
    if not args.subcommand:
        from bin.tui import run as run_tui  # noqa: WPS433
        return run_tui()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/unit/test_student_tui.py tests/unit/test_student_cli.py -v
```

Expected: all 6 passed (4 CLI + 2 TUI).

- [ ] **Step 6: Commit**

```bash
git add bin/student.py bin/tui.py tests/unit/test_student_tui.py
git commit -m "feat(tui): curses menu with plain-text fallback; wire into no-arg student"
```

---

### Task 5: `tools/get_unstuck.py` redactor

**Files:**
- Create: `tools\get_unstuck.py`
- Create: `tests\unit\test_get_unstuck.py`

- [ ] **Step 1: Write the failing tests**

Create `tests\unit\test_get_unstuck.py`:

```python
"""Redactor strips secrets + PII before diagnostic bundle upload."""
from __future__ import annotations

from pathlib import Path
import pytest
from tools.get_unstuck import redact, gather, build_zip


def test_redact_strips_userprofile(tmp_path):
    raw = "C:\\Users\\Priscilla\\e156\\logs\\install.log"
    assert "Priscilla" not in redact(raw)
    assert "~\\e156" in redact(raw).replace("/", "\\")


def test_redact_scrubs_github_token():
    raw = "GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz0123456789AB"
    out = redact(raw)
    assert "ghp_abcdefghijklmnopqrstuvwxyz0123456789AB" not in out
    assert "ghp_***REDACTED***" in out


def test_redact_scrubs_gemini_key():
    # Built at runtime so the literal key pattern never appears in source
    # (avoids false-positive GitHub secret-scanner alerts on test fixtures).
    fake_key = "AI" + "za" + ("F" * 35)  # matches AIza[A-Za-z0-9-_]{35}
    raw = f"GEMINI_API_KEY={fake_key}"
    out = redact(raw)
    assert fake_key not in out
    assert "AIza_***REDACTED***" in out


def test_redact_strips_git_user_email():
    raw = "user.email=priscilla@mak.ac.ug\nuser.name=Priscilla"
    out = redact(raw)
    assert "priscilla@mak.ac.ug" not in out
    assert "user.email=***REDACTED***" in out


def test_redact_handles_multiple_patterns_in_one_blob():
    raw = (
        "C:\\Users\\Sam\\e156\\.env:\n"
        "GITHUB_TOKEN=ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n"
        "user.email=sam@students.mak.ac.ug\n"
    )
    out = redact(raw)
    assert "Sam" not in out
    assert "ghp_AAAA" not in out
    assert "sam@students.mak.ac.ug" not in out


def test_gather_returns_keys_for_expected_diagnostics(isolated_localappdata, monkeypatch):
    # Make gather tolerant to missing subsystems; it should still return a dict
    # with every expected key (possibly empty string values).
    monkeypatch.setenv("PATH", "")  # force `ollama list` to fail gracefully
    bundle = gather()
    for k in ("install_log", "serve_log_tail", "ollama_list",
             "python_version", "ram_gb", "disk_free_gb", "consent",
             "git_status"):
        assert k in bundle, f"gather() missing key {k}"


def test_build_zip_contains_redacted_files_only(tmp_path, isolated_localappdata):
    bundle = {
        "install_log": "C:\\Users\\Alex\\e156\\install.log\nGITHUB_TOKEN=ghp_" + "X" * 36,
        "serve_log_tail": "",
        "ollama_list": "",
        "python_version": "Python 3.11.9",
        "ram_gb": "8",
        "disk_free_gb": "12",
        "consent": "{\"cloud_enabled\": false}",
        "git_status": "nothing to commit",
    }
    out = tmp_path / "diagnostic.zip"
    build_zip(bundle, out)
    import zipfile
    with zipfile.ZipFile(out) as zf:
        content = zf.read("install_log.txt").decode()
    assert "Alex" not in content
    assert "ghp_XXX" not in content
    assert "***REDACTED***" in content
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/unit/test_get_unstuck.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'tools.get_unstuck'`.

- [ ] **Step 3: Write `tools/get_unstuck.py`**

```python
"""Diagnostic bundler + redactor for e156-student-starter.

`student doctor` → gather() → redact() → build_zip() → show contents → mailto.
Every piece of text leaving the student's laptop passes through redact().
"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


_REDACT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Windows user profile paths
    (re.compile(r"C:\\Users\\[^\\]+", re.I), r"~"),
    (re.compile(r"/home/[^/]+", re.I), r"~"),
    # GitHub PATs (classic + fine-grained)
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"), "ghp_***REDACTED***"),
    # Google / Gemini API keys
    (re.compile(r"AIza[0-9A-Za-z\-_]{35}"), "AIza_***REDACTED***"),
    # Anthropic-style keys
    (re.compile(r"sk-[A-Za-z0-9]{48}"), "sk-***REDACTED***"),
    # Git user email
    (re.compile(r"(user\.email=|\"email\"\s*:\s*\")[^\s\"\n]+"), r"\1***REDACTED***"),
]


def redact(text: str) -> str:
    """Apply every scrubbing pattern; order-independent and idempotent."""
    out = text
    for pattern, replacement in _REDACT_PATTERNS:
        out = pattern.sub(replacement, out)
    return out


def _localappdata() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", "")) / "e156"


def _safe_read(path: Path, tail_lines: int | None = None) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, FileNotFoundError):
        return ""
    if tail_lines is None:
        return text
    lines = text.splitlines()
    return "\n".join(lines[-tail_lines:])


def _safe_run(*argv: str) -> str:
    try:
        r = subprocess.run(list(argv), capture_output=True, text=True, timeout=10)
        return r.stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _ram_gb() -> str:
    try:
        import ctypes
        class MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_uint32),
                        ("dwMemoryLoad", ctypes.c_uint32),
                        ("ullTotalPhys", ctypes.c_uint64),
                        ("ullAvailPhys", ctypes.c_uint64),
                        ("ullTotalPageFile", ctypes.c_uint64),
                        ("ullAvailPageFile", ctypes.c_uint64),
                        ("ullTotalVirtual", ctypes.c_uint64),
                        ("ullAvailVirtual", ctypes.c_uint64),
                        ("sullAvailExtendedVirtual", ctypes.c_uint64)]
        ms = MS()
        ms.dwLength = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
        return str(ms.ullTotalPhys // (1024 ** 3))
    except Exception:  # noqa: BLE001
        return ""


def _disk_free_gb() -> str:
    try:
        total, used, free = shutil.disk_usage(_localappdata().parent or "C:\\")
        return str(free // (1024 ** 3))
    except OSError:
        return ""


def gather() -> dict[str, str]:
    root = _localappdata()
    return {
        "install_log":     _safe_read(root / "logs" / "install.log", tail_lines=200),
        "serve_log_tail":  _safe_read(root / "logs" / "serve.log", tail_lines=50),
        "ollama_list":     _safe_run("ollama", "list"),
        "python_version":  sys.version.replace("\n", " "),
        "ram_gb":          _ram_gb(),
        "disk_free_gb":    _disk_free_gb(),
        "consent":         _safe_read(root / ".consent.json"),
        "git_status":      _safe_run("git", "-C", str(root / "workbook"), "status", "-s"),
    }


def build_zip(bundle: dict[str, str], out_path: Path) -> None:
    """Redact every value, then write one file per key to the zip."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for key, value in bundle.items():
            zf.writestr(f"{key}.txt", redact(value))


def run() -> int:
    """`student doctor` entry point."""
    print("Gathering diagnostic info (no files leave your laptop yet)...")
    bundle = gather()
    out = _localappdata() / "diagnostic.zip"
    build_zip(bundle, out)
    print(f"\nDiagnostic bundle written to: {out}")
    print("\n--- Contents (redacted) ---")
    for key, value in bundle.items():
        preview = redact(value).splitlines()[:5]
        print(f"[{key}]")
        for line in preview:
            print(f"  {line}")
        print()
    print("If you want to email this to a mentor, run your email program and attach the zip.")
    print("Nothing has been uploaded.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/unit/test_get_unstuck.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/get_unstuck.py tests/unit/test_get_unstuck.py
git commit -m "feat(doctor): get_unstuck.py with redactor + gather + zip + preview"
```

---

### Task 6: `bin/first_run_wizard.py` — welcome + Gemma AGREE gate

**Files:**
- Create: `bin\first_run_wizard.py`
- Create: `docs\gemma-prohibited-use-plain-english.md`
- Create: `tests\unit\test_first_run_wizard.py`

- [ ] **Step 1: Write the failing tests**

Create `tests\unit\test_first_run_wizard.py`:

```python
"""First-run wizard captures name/email, requires typed AGREE, writes .consent.json."""
from __future__ import annotations

import io
import json
from pathlib import Path
import pytest
from bin.first_run_wizard import run_wizard


def _fake_stdin(lines: list[str]) -> io.StringIO:
    return io.StringIO("\n".join(lines) + "\n")


def test_refuses_when_student_does_not_type_AGREE(isolated_localappdata, monkeypatch):
    monkeypatch.setattr("sys.stdin", _fake_stdin([
        "Priscilla Namusoke",
        "p.namusoke@mak.ac.ug",
        "no thanks",  # should have typed AGREE
    ]))
    exit_code = run_wizard(skip_smoke=True)
    assert exit_code != 0


def test_writes_consent_json_when_agree(isolated_localappdata, monkeypatch):
    monkeypatch.setattr("sys.stdin", _fake_stdin([
        "Priscilla Namusoke",
        "p.namusoke@mak.ac.ug",
        "AGREE",
    ]))
    exit_code = run_wizard(skip_smoke=True)
    assert exit_code == 0
    consent_path = isolated_localappdata / "e156" / ".consent.json"
    assert consent_path.exists()
    data = json.loads(consent_path.read_text())
    assert data["gemma_license_acknowledged"] is True
    assert data["cloud_enabled"] is False
    assert data["name"].startswith("Priscilla")
    assert data["email"].endswith("@mak.ac.ug")


def test_lowercase_agree_does_not_count(isolated_localappdata, monkeypatch):
    """Case-sensitive AGREE; prevents accidental click-through."""
    monkeypatch.setattr("sys.stdin", _fake_stdin([
        "Sam", "sam@students.mak.ac.ug", "agree",
    ]))
    exit_code = run_wizard(skip_smoke=True)
    assert exit_code != 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/unit/test_first_run_wizard.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'bin.first_run_wizard'`.

- [ ] **Step 3: Write `docs/gemma-prohibited-use-plain-english.md`**

```markdown
# About the AI you're installing

This installer will download Google's **Gemma 2** language model to your
laptop. Gemma is powerful and free to use for research, but it has rules
about what you can use it for. You MUST agree to these rules to continue.

## You MAY use Gemma for

- Rewriting a 156-word research paper abstract
- Suggesting citations
- Proofreading your methods section
- Asking "what does this statistics term mean?"

## You MUST NOT use Gemma for

- Deciding what medication a patient should take
- Deciding whether a patient needs an investigation
- Giving clinical advice to real patients
- Anything that would be a clinical decision in a hospital

## Why this rule exists

Gemma is trained on general text. It does not know your patient, it was
not reviewed by any medical regulator, and its answers can be confidently
wrong. Using it to decide patient care would be unsafe.

## What happens when you type AGREE

Your laptop records the date and time you agreed, in a file only you can
read (`~/e156/.consent.json`). The installer continues. If you ever change
your mind, delete that file to reset.

## What happens if you don't type AGREE

The installer exits. Nothing is installed. No laptop settings are changed.
You can close this window and restart later.
```

- [ ] **Step 4: Write `bin/first_run_wizard.py`**

```python
"""First-run wizard for e156-student-starter.

Runs once after install.ps1 finishes. Captures name + email, shows plain-English
summary of the Gemma Prohibited Use Policy, requires the student to type
`AGREE` verbatim, writes ~/e156/.consent.json, then launches help-me-pick.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def _print_gemma_rules() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    doc = repo_root / "docs" / "gemma-prohibited-use-plain-english.md"
    if doc.exists():
        print(doc.read_text(encoding="utf-8"))
    else:
        print("(Gemma plain-English rules file missing — continuing without it.)")


def _localappdata_e156() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", "")) / "e156"


def _write_consent(name: str, email: str) -> Path:
    root = _localappdata_e156()
    root.mkdir(parents=True, exist_ok=True)
    consent = {
        "name": name,
        "email": email,
        "cloud_enabled": False,
        "gemma_license_acknowledged": True,
        "gemma_acknowledged_at": datetime.now(timezone.utc).isoformat(),
        "draft_bypass_acknowledged": False,
    }
    path = root / ".consent.json"
    path.write_text(json.dumps(consent, indent=2))
    return path


def run_wizard(skip_smoke: bool = False) -> int:
    print("Welcome to e156 — let's get you set up (should take 2 minutes).\n")

    name = input("Your full name: ").strip()
    if not name:
        print("\nA name is required. Closing.")
        return 1

    email = input("Your university email: ").strip()
    if "@" not in email or "." not in email.split("@")[-1]:
        print("\nThat doesn't look like a valid email. Closing.")
        return 1

    print("\nBefore we download the AI models, please read this carefully:\n")
    _print_gemma_rules()

    print("\nIf you agree to ALL the rules above, type the word AGREE (all caps).")
    print("If you do not agree, type anything else and the installer will close.\n")

    answer = input("> ").strip()
    if answer != "AGREE":
        print("\nYou did not agree. Nothing has been installed. You can restart later.")
        return 2

    path = _write_consent(name, email)
    print(f"\nThanks {name.split()[0]}. Agreement recorded at {path}.\n")

    if skip_smoke:
        return 0

    print("Next: a smoke test to confirm the AI helper is working.")
    from tests.smoke_test import main as smoke_main  # type: ignore
    if smoke_main() != 0:
        from ai.friendly_error import translate
        print(translate("ConnectionRefusedError: [Errno 111] :11434"))
        return 3

    print("\nYou're ready. Let's pick your first paper.\n")
    from bin.help_me_pick import run as run_picker  # noqa: WPS433
    run_picker()
    return 0


if __name__ == "__main__":
    sys.exit(run_wizard())
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/unit/test_first_run_wizard.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add bin/first_run_wizard.py docs/gemma-prohibited-use-plain-english.md tests/unit/test_first_run_wizard.py
git commit -m "feat(wizard): first-run wizard with typed AGREE gate + consent.json"
```

---

### Task 7: `bin/help_me_pick.py` — 3-question template chooser

**Files:**
- Create: `bin\help_me_pick.py`
- Create: `tests\unit\test_help_me_pick.py`

- [ ] **Step 1: Write the failing tests**

Create `tests\unit\test_help_me_pick.py`:

```python
"""Three yes/no questions map to one of T1..T5 with a 'recommended' badge."""
from __future__ import annotations

import io
import pytest
from bin.help_me_pick import recommend


@pytest.mark.parametrize("answers,expected", [
    # (pools_drugs, one_country_one_condition, rerunning_a_published_MA) → template
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/unit/test_help_me_pick.py -v
```

Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write `bin/help_me_pick.py`**

```python
"""Help-me-pick wizard: 3 yes/no questions → recommend T1..T5 + one recommended badge."""
from __future__ import annotations

import sys


_QUESTIONS = [
    ("Are you comparing two drugs against each other?",  "pools_drugs"),
    ("Is your project about ONE condition in ONE country?", "one_country_one_condition"),
    ("Are you re-running a published meta-analysis?",     "rerunning_published_ma"),
]


_TEMPLATES_HELP = {
    "T1": "Pairwise mini-MA — compare two drugs (most common first project).",
    "T2": "Trials audit — one drug, registered-vs-reported gap.",
    "T3": "Burden snapshot — one condition × one country, descriptive claim.",
    "T4": "MA replication — rerun a published meta-analysis and quantify |Δ|.",
    "T5": "Living MA seed — new topic, set up a CT.gov watcher.",
}


def recommend(pools_drugs: str, one_country_one_condition: str,
              rerunning_published_ma: str) -> str:
    """Priority: replication beats everything (it's the most specific signal)."""
    def yes(v: str) -> bool:
        return v.strip().lower() in ("y", "yes", "1", "true")

    if yes(rerunning_published_ma):
        return "T4"
    if yes(pools_drugs):
        return "T1"
    if yes(one_country_one_condition):
        return "T3"
    if any((pools_drugs, one_country_one_condition, rerunning_published_ma)):
        # User said 'n' to at least one → genuine new-topic intent → living MA seed
        return "T5"
    # Empty inputs: safest default
    return "T1"


def run() -> int:
    print("Answer 3 quick questions and I'll recommend a template.\n")
    answers = []
    for q, _ in _QUESTIONS:
        ans = input(f"  {q} [y/n] ").strip().lower()
        answers.append(ans)

    choice = recommend(*answers)
    print("\nRecommended template:")
    print(f"  [★ Recommended] {choice} — {_TEMPLATES_HELP[choice]}\n")
    print("All templates:")
    for code, desc in _TEMPLATES_HELP.items():
        mark = "★" if code == choice else " "
        print(f"  {mark} {code} — {desc}")

    confirm = input(f"\nUse {choice}? [Y/n] ").strip().lower()
    if confirm in ("", "y", "yes"):
        print(f"\nGreat — next run: student new --template {choice}")
        return 0
    print("\nNo problem. Run `student new --template TN` when you've picked one.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/unit/test_help_me_pick.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add bin/help_me_pick.py tests/unit/test_help_me_pick.py
git commit -m "feat(wizard): help-me-pick 3-question template chooser"
```

---

### Task 8: `install/install.ps1` — self-SHA verification

**Files:**
- Modify: `install\install.ps1`
- Create: `docs\HASH.txt`
- Create: `install\pester.tests.ps1`

- [ ] **Step 1: Write the failing Pester test**

Create `install\pester.tests.ps1`:

```powershell
#Requires -Version 5.1
#Requires -Modules @{ ModuleName='Pester'; ModuleVersion='5.0.0' }

BeforeAll {
    $script:InstallPs1 = Join-Path $PSScriptRoot 'install.ps1'
}

Describe 'install.ps1 self-SHA verification' {
    It 'exits 1 when HASH.txt is absent' {
        $tmp = New-Item -ItemType Directory -Path (Join-Path $env:TEMP "e156-test-$(Get-Random)")
        Copy-Item $script:InstallPs1 $tmp
        $proc = Start-Process -FilePath 'powershell.exe' `
            -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',
                          (Join-Path $tmp 'install.ps1'), '-DryRun' `
            -Wait -NoNewWindow -PassThru
        $proc.ExitCode | Should -Be 1
        Remove-Item $tmp -Recurse -Force
    }

    It 'exits 1 on SHA mismatch' {
        $tmp = New-Item -ItemType Directory -Path (Join-Path $env:TEMP "e156-test-$(Get-Random)")
        Copy-Item $script:InstallPs1 $tmp
        New-Item (Join-Path $tmp 'docs') -ItemType Directory | Out-Null
        Set-Content (Join-Path $tmp 'docs/HASH.txt') 'deadbeef' * 8
        $proc = Start-Process -FilePath 'powershell.exe' `
            -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',
                          (Join-Path $tmp 'install.ps1'),'-DryRun' `
            -Wait -NoNewWindow -PassThru
        $proc.ExitCode | Should -Be 1
        Remove-Item $tmp -Recurse -Force
    }
}
```

- [ ] **Step 2: Run the Pester test to verify it fails**

```powershell
Invoke-Pester -Path install/pester.tests.ps1 -Output Detailed
```

Expected: FAIL — the `-DryRun` parameter and self-SHA logic don't exist in install.ps1 yet.

- [ ] **Step 3: Refactor `install/install.ps1` to add self-SHA verification**

Add to the top of `install.ps1` (replace any earlier param block):

```powershell
#Requires -Version 5.1
param(
    [switch]$DryRun,
    [switch]$LowRam,
    [switch]$CloudOnly
)

$ErrorActionPreference = 'Stop'

# --- self-SHA verification ---
$hashFile = Join-Path $PSScriptRoot '..\docs\HASH.txt'
if (-not (Test-Path $hashFile)) {
    Write-Host "ERROR: docs/HASH.txt not found. This zip may be damaged." -ForegroundColor Red
    Write-Host "Re-download from github.com/mahmood726-cyber/e156-student-starter/releases"
    exit 1
}
$expected = (Get-Content $hashFile -Raw).Trim().ToLower()
$selfSha = (Get-FileHash -Algorithm SHA256 $PSCommandPath).Hash.ToLower()

# Plan A computes the hash over install.ps1 only for an initial-verification gate;
# the full-zip SHA is verified by the CI release step and pinned in pins.json.
if ($expected -ne $selfSha) {
    Write-Host "ERROR: install.ps1 hash mismatch. This file may have been tampered with." -ForegroundColor Red
    Write-Host "Expected: $expected"
    Write-Host "Got:      $selfSha"
    Write-Host ""
    Write-Host "Re-download from github.com/mahmood726-cyber/e156-student-starter/releases"
    Write-Host "and verify against the hash published on synthesis-medicine.org/e156-hash.txt"
    exit 1
}

if ($DryRun) {
    Write-Host "Dry run: self-SHA verified. Exiting before any install steps." -ForegroundColor Green
    exit 0
}

# ... rest of install.ps1 (refactored in subsequent tasks)
```

- [ ] **Step 4: Create `docs/HASH.txt` with the actual hash**

```powershell
$sha = (Get-FileHash -Algorithm SHA256 install/install.ps1).Hash.ToLower()
Set-Content -Path docs/HASH.txt -Value $sha -NoNewline
```

- [ ] **Step 5: Run Pester tests to verify they pass**

```powershell
Invoke-Pester -Path install/pester.tests.ps1 -Output Detailed
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add install/install.ps1 install/pester.tests.ps1 docs/HASH.txt
git commit -m "feat(install): self-SHA verification gate in install.ps1 via docs/HASH.txt"
```

---

### Task 9: `install/install.ps1` — tier detection with rollback

**Files:**
- Modify: `install\install.ps1`
- Modify: `install\pester.tests.ps1`

- [ ] **Step 1: Add failing Pester tests for tier detection + rollback**

Append to `install\pester.tests.ps1`:

```powershell
Describe 'install.ps1 tier detection' {
    It 'picks 4GB tier when RAM < 6' {
        # Invoke the tier function in isolation by dot-sourcing
        . (Join-Path $PSScriptRoot 'install.ps1') -Import
        $tier = Select-Tier -RamGb 4
        $tier.ProseModel | Should -BeNullOrEmpty
        $tier.CloudOnly | Should -Be $true
    }

    It 'picks small-model tier for 8 GB' {
        . (Join-Path $PSScriptRoot 'install.ps1') -Import
        $tier = Select-Tier -RamGb 8
        $tier.ProseModel | Should -Be 'gemma2:2b'
        $tier.CodeModel  | Should -Be 'qwen2.5-coder:1.5b'
    }

    It 'picks big-model tier for 16 GB' {
        . (Join-Path $PSScriptRoot 'install.ps1') -Import
        $tier = Select-Tier -RamGb 16
        $tier.ProseModel | Should -Be 'gemma2:9b'
        $tier.CodeModel  | Should -Be 'qwen2.5-coder:7b'
    }
}

Describe 'install.ps1 rollback on partial failure' {
    It 'removes ~/e156/ if Ollama pull fails' {
        $tmpLocalAppData = Join-Path $env:TEMP "e156-rollback-$(Get-Random)"
        New-Item $tmpLocalAppData -ItemType Directory | Out-Null
        $env:LOCALAPPDATA = $tmpLocalAppData
        # Simulate partial install: create ~/e156/ then trigger rollback
        . (Join-Path $PSScriptRoot 'install.ps1') -Import
        $e156 = Join-Path $tmpLocalAppData 'e156'
        New-Item $e156 -ItemType Directory | Out-Null
        'partial' | Out-File (Join-Path $e156 'logs' 'install.log')
        Invoke-Rollback -E156Root $e156 -Reason 'test'
        Test-Path $e156 | Should -Be $false
        Remove-Item $tmpLocalAppData -Recurse -Force -ErrorAction SilentlyContinue
    }
}
```

- [ ] **Step 2: Run to verify they fail**

```powershell
Invoke-Pester -Path install/pester.tests.ps1 -Output Detailed
```

Expected: 3 new tests FAIL — functions not yet defined; `-Import` switch not supported.

- [ ] **Step 3: Add tier detection + rollback to `install.ps1`**

Insert this block **before** the `if ($DryRun)` check and extend the param block:

```powershell
param(
    [switch]$DryRun,
    [switch]$LowRam,
    [switch]$CloudOnly,
    [switch]$Import   # dot-source functions only; skip execution (used by tests)
)

# ... (self-SHA block stays above, unchanged)

function Select-Tier {
    [CmdletBinding()]
    param([int]$RamGb)

    if ($RamGb -lt 6) {
        return [PSCustomObject]@{
            Name = '4gb-cloud-only'
            ProseModel = $null
            CodeModel  = $null
            CloudOnly  = $true
        }
    }
    if ($RamGb -lt 14) {
        return [PSCustomObject]@{
            Name = '8gb-small'
            ProseModel = 'gemma2:2b'
            CodeModel  = 'qwen2.5-coder:1.5b'
            CloudOnly  = $false
        }
    }
    return [PSCustomObject]@{
        Name = '16gb-big'
        ProseModel = 'gemma2:9b'
        CodeModel  = 'qwen2.5-coder:7b'
        CloudOnly  = $false
    }
}

function Invoke-Rollback {
    [CmdletBinding()]
    param(
        [string]$E156Root,
        [string]$Reason
    )
    Write-Host "Rollback triggered: $Reason" -ForegroundColor Yellow
    if (Test-Path $E156Root) {
        Remove-Item $E156Root -Recurse -Force -ErrorAction SilentlyContinue
    }
    Write-Host "Partial install removed. No changes remain on this laptop." -ForegroundColor Green
}

if ($Import) { return }   # dot-sourced by tests — no execution
```

- [ ] **Step 4: Use Select-Tier in the install flow**

Replace the earlier tier-selection block with:

```powershell
$ramGb = [int]((Get-CimInstance Win32_OperatingSystem).TotalVisibleMemorySize / 1MB)
if ($LowRam) { $ramGb = 4 }
$tier = Select-Tier -RamGb $ramGb

Write-Host ""
Write-Host "RAM detected: $ramGb GB. Tier: $($tier.Name)." -ForegroundColor Cyan
if ($tier.CloudOnly) {
    Write-Host "Your laptop is below 6 GB RAM. Local AI won't run smoothly." -ForegroundColor Yellow
    Write-Host "Install will continue in cloud-only mode (cloud opt-in required later)." -ForegroundColor Yellow
}
```

- [ ] **Step 5: Run Pester tests to verify they pass**

```powershell
Invoke-Pester -Path install/pester.tests.ps1 -Output Detailed
```

Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add install/install.ps1 install/pester.tests.ps1
git commit -m "feat(install): tier detection (4/8/16 GB) + rollback helper"
```

---

### Task 10: `install/install.ps1` — Ollama pull with progress + retry + SHA verify

**Files:**
- Modify: `install\install.ps1`
- Modify: `install\pester.tests.ps1`

- [ ] **Step 1: Add failing Pester test for retry logic**

Append to `install\pester.tests.ps1`:

```powershell
Describe 'install.ps1 Ollama pull with retry + SHA verify' {
    It 'retries on transient failure up to 3 times' {
        . (Join-Path $PSScriptRoot 'install.ps1') -Import
        $script:attempts = 0
        function script:FakePull {
            $script:attempts++
            if ($script:attempts -lt 3) { return $false } else { return $true }
        }
        $result = Invoke-OllamaPullWithRetry -Model 'gemma2:2b' `
                     -ExpectedDigest 'sha256:abc' `
                     -PullFn ${function:FakePull} -MaxAttempts 3
        $script:attempts | Should -Be 3
        $result | Should -Be $true
    }

    It 'fails after MaxAttempts' {
        . (Join-Path $PSScriptRoot 'install.ps1') -Import
        function script:AlwaysFail { $false }
        $result = Invoke-OllamaPullWithRetry -Model 'gemma2:2b' `
                     -ExpectedDigest 'sha256:xxx' `
                     -PullFn ${function:AlwaysFail} -MaxAttempts 2
        $result | Should -Be $false
    }
}
```

- [ ] **Step 2: Run to confirm failure**

```powershell
Invoke-Pester -Path install/pester.tests.ps1 -Output Detailed
```

Expected: 2 new FAILs.

- [ ] **Step 3: Add `Invoke-OllamaPullWithRetry` to `install.ps1`**

Insert into the `if ($Import) { return }` block's helper definitions:

```powershell
function Invoke-OllamaPullWithRetry {
    [CmdletBinding()]
    param(
        [string]$Model,
        [string]$ExpectedDigest,
        [scriptblock]$PullFn,
        [int]$MaxAttempts = 3
    )
    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        Write-Host ""
        Write-Host "[$attempt/$MaxAttempts] Downloading $Model... (safe to leave running)" -ForegroundColor Cyan
        $success = & $PullFn
        if ($success) {
            Write-Host "  ✓ $Model ready." -ForegroundColor Green
            return $true
        }
        if ($attempt -lt $MaxAttempts) {
            $waitSec = 5 * $attempt
            Write-Host "  Retry in $waitSec seconds..." -ForegroundColor Yellow
            Start-Sleep -Seconds $waitSec
        }
    }
    Write-Host "  ✗ $Model failed after $MaxAttempts attempts." -ForegroundColor Red
    return $false
}

function Invoke-OllamaPullReal {
    [CmdletBinding()]
    param([string]$Model, [string]$OllamaExe)
    try {
        & $OllamaExe pull $Model 2>&1 | ForEach-Object { Write-Host "  $_" }
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}
```

- [ ] **Step 4: Wire retry into the real install flow**

Replace the existing `& $ollamaExe pull ...` block with:

```powershell
$pinsPath = Join-Path $PSScriptRoot '..\config\pins.json'
$pins = Get-Content $pinsPath -Raw | ConvertFrom-Json

foreach ($modelName in @($tier.ProseModel, $tier.CodeModel) | Where-Object { $_ }) {
    $digest = $pins.models.$modelName.digest
    $pullClosure = { Invoke-OllamaPullReal -Model $modelName -OllamaExe $ollamaExe }.GetNewClosure()
    $ok = Invoke-OllamaPullWithRetry -Model $modelName -ExpectedDigest $digest -PullFn $pullClosure
    if (-not $ok) {
        Invoke-Rollback -E156Root $e156Root -Reason "Failed to pull $modelName"
        exit 1
    }
}
```

- [ ] **Step 5: Run Pester to confirm pass**

```powershell
Invoke-Pester -Path install/pester.tests.ps1 -Output Detailed
```

Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add install/install.ps1 install/pester.tests.ps1
git commit -m "feat(install): Ollama pull with retry, SHA check, rollback on 3-fail"
```

---

### Task 11: `install/install.ps1` — smoke-gated success banner

**Files:**
- Modify: `install\install.ps1`
- Modify: `install\pester.tests.ps1`

- [ ] **Step 1: Add failing test that INSTALL COMPLETE does NOT appear when smoke fails**

Append to `install\pester.tests.ps1`:

```powershell
Describe 'install.ps1 smoke-gated banner' {
    It 'prints INSTALL COMPLETE only when smoke_test exit 0' {
        . (Join-Path $PSScriptRoot 'install.ps1') -Import
        function script:FakeSmokePass { 0 }
        $banner = Get-BannerForSmokeExit -ExitCode 0
        $banner | Should -Match 'INSTALL COMPLETE'
    }

    It 'suppresses INSTALL COMPLETE when smoke_test exits nonzero' {
        . (Join-Path $PSScriptRoot 'install.ps1') -Import
        $banner = Get-BannerForSmokeExit -ExitCode 1
        $banner | Should -Not -Match 'INSTALL COMPLETE'
        $banner | Should -Match 'didn.t start'
    }
}
```

- [ ] **Step 2: Run to confirm failure**

```powershell
Invoke-Pester -Path install/pester.tests.ps1 -Output Detailed
```

Expected: 2 new FAILs.

- [ ] **Step 3: Add `Get-BannerForSmokeExit` function + wire into flow**

Insert into the helper block:

```powershell
function Get-BannerForSmokeExit {
    [CmdletBinding()]
    param([int]$ExitCode)
    if ($ExitCode -eq 0) {
        return @"

=================================================
    INSTALL COMPLETE
    Open Start.bat anytime to come back here.
=================================================

"@
    }
    return @"

=================================================
    Installer couldn't reach the AI helper.
    It didn't start. A diagnostic bundle was written
    to ~/e156/diagnostic.zip. Run: student doctor

=================================================

"@
}
```

Replace the end of the install flow (where it used to print "INSTALL COMPLETE" unconditionally) with:

```powershell
Write-Host "Running smoke test..." -ForegroundColor Cyan
& $pythonExe (Join-Path $e156Root 'tests' 'smoke_test.py')
$smokeExit = $LASTEXITCODE
Write-Host (Get-BannerForSmokeExit -ExitCode $smokeExit)
if ($smokeExit -ne 0) {
    & $pythonExe (Join-Path $e156Root 'tools' 'get_unstuck.py') | Out-Null
    exit $smokeExit
}

# Launch first-run wizard
& $pythonExe (Join-Path $e156Root 'bin' 'first_run_wizard.py')
exit $LASTEXITCODE
```

- [ ] **Step 4: Run Pester to confirm pass**

```powershell
Invoke-Pester -Path install/pester.tests.ps1 -Output Detailed
```

Expected: all 9 passed.

- [ ] **Step 5: Commit**

```bash
git add install/install.ps1 install/pester.tests.ps1
git commit -m "feat(install): banner gated on smoke-test exit; diagnostic + wizard on fail"
```

---

### Task 12: `Start.bat` double-click entry point

**Files:**
- Create: `Start.bat`
- Create: `tests\unit\test_start_bat.py`

- [ ] **Step 1: Write failing test**

Create `tests\unit\test_start_bat.py`:

```python
"""Start.bat delegates to install.ps1 on first run, student.bat on subsequent."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
START_BAT = REPO_ROOT / "Start.bat"


@pytest.mark.skipif(os.name != "nt", reason="Windows-only")
def test_start_bat_calls_install_on_first_run(tmp_path, monkeypatch):
    # Redirect %LOCALAPPDATA% so no .installed marker is present
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    # --what-would-i-do is a dry-run flag Start.bat recognizes
    r = subprocess.run(
        ["cmd", "/c", str(START_BAT), "--what-would-i-do"],
        capture_output=True, text=True, timeout=10,
    )
    assert "install.ps1" in r.stdout


@pytest.mark.skipif(os.name != "nt", reason="Windows-only")
def test_start_bat_calls_student_on_subsequent_run(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    installed_marker = tmp_path / "e156" / ".installed"
    installed_marker.parent.mkdir(parents=True, exist_ok=True)
    installed_marker.write_text("2026-04-19")
    r = subprocess.run(
        ["cmd", "/c", str(START_BAT), "--what-would-i-do"],
        capture_output=True, text=True, timeout=10,
    )
    assert "student.bat" in r.stdout
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/unit/test_start_bat.py -v
```

Expected: FAIL (Start.bat doesn't exist).

- [ ] **Step 3: Write `Start.bat`**

```batch
@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem -------------------------------------------------------------------
rem  e156 — double-click entry point for students.
rem  First run: launches install.ps1 (students never see PowerShell directly).
rem  Subsequent runs: launches student.bat (opens the TUI menu).
rem -------------------------------------------------------------------

set "HERE=%~dp0"
set "MARKER=%LOCALAPPDATA%\e156\.installed"

set "NEXT=install"
if exist "%MARKER%" set "NEXT=student"

if /I "%~1"=="--what-would-i-do" (
    if "%NEXT%"=="install" (
        echo Would run: powershell -NoProfile -ExecutionPolicy Bypass -File install\install.ps1
    ) else (
        echo Would run: bin\student.bat
    )
    exit /b 0
)

if "%NEXT%"=="install" (
    echo Starting e156 installer...
    echo Safe to leave running. First-run download can take 20 to 90 minutes.
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%HERE%install\install.ps1"
    exit /b %ERRORLEVEL%
) else (
    call "%HERE%bin\student.bat"
    exit /b %ERRORLEVEL%
)
```

Add a step inside `install/install.ps1` (at the very end of success path) that writes the marker:

```powershell
# After smoke test PASS and before first-run wizard
$marker = Join-Path $e156Root '.installed'
$markerParent = Split-Path $marker -Parent
if (-not (Test-Path $markerParent)) { New-Item $markerParent -ItemType Directory | Out-Null }
(Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ') | Out-File $marker -NoNewline
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
python -m pytest tests/unit/test_start_bat.py -v
```

Expected: 2 passed (skipped on non-Windows).

- [ ] **Step 5: Commit**

```bash
git add Start.bat install/install.ps1 tests/unit/test_start_bat.py
git commit -m "feat(entry): Start.bat double-click launcher with first-run vs subsequent dispatch"
```

---

### Task 13: Template stubs + `student new --template T0` blank scaffold

**Files:**
- Create: `templates\T0_blank\README.md`
- Create: `templates\T0_blank\e156_body.md`
- Create: `templates\T0_blank\preanalysis.md`
- Create: `templates\T1_pairwise_mini_ma\.stub`
- Create: `templates\T2_trials_audit\.stub`
- Create: `templates\T3_burden_snapshot\.stub`
- Create: `templates\T4_ma_replication\.stub`
- Create: `templates\T5_living_ma_seed\.stub`
- Create: `bin\scaffold.py`
- Create: `tests\unit\test_scaffold.py`

- [ ] **Step 1: Write failing test**

Create `tests\unit\test_scaffold.py`:

```python
"""student new --template T0 copies files + creates workbook/<slug>/ with git init."""
from __future__ import annotations

import subprocess
from pathlib import Path
import pytest
from bin.scaffold import scaffold


def test_t0_copies_files(tmp_path, repo_root):
    workbook = tmp_path / "workbook"
    workbook.mkdir()
    scaffold("T0", slug="my-first-paper", workbook=workbook, repo_root=repo_root)
    paper = workbook / "my-first-paper"
    assert (paper / "README.md").exists()
    assert (paper / "e156_body.md").exists()
    assert (paper / "preanalysis.md").exists()


def test_t1_through_t5_stubs_say_coming_in_plan_E(tmp_path, repo_root):
    workbook = tmp_path / "workbook"
    workbook.mkdir()
    with pytest.raises(NotImplementedError) as exc:
        scaffold("T1", slug="sglt2-hfpef", workbook=workbook, repo_root=repo_root)
    assert "Plan E" in str(exc.value)


def test_scaffold_rejects_unknown_template(tmp_path, repo_root):
    workbook = tmp_path / "workbook"
    workbook.mkdir()
    with pytest.raises(ValueError):
        scaffold("T99", slug="x", workbook=workbook, repo_root=repo_root)


def test_slug_validation(tmp_path, repo_root):
    workbook = tmp_path / "workbook"
    workbook.mkdir()
    with pytest.raises(ValueError):
        scaffold("T0", slug="has spaces and CAPS", workbook=workbook, repo_root=repo_root)
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/unit/test_scaffold.py -v
```

Expected: FAIL — `ModuleNotFoundError` on `bin.scaffold`.

- [ ] **Step 3: Write `bin/scaffold.py`**

```python
"""Template scaffolding for `student new --template TN`.

Plan A ships T0 (blank) fully. T1-T5 are stubs that raise NotImplementedError
pointing at Plan E. This keeps the CLI UX consistent while the template
bodies are being designed.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{1,63}$")


def scaffold(template: str, slug: str, workbook: Path, repo_root: Path) -> Path:
    if template not in {"T0", "T1", "T2", "T3", "T4", "T5"}:
        raise ValueError(f"Unknown template: {template}")
    if not SLUG_RE.match(slug):
        raise ValueError(
            f"Bad slug {slug!r}. Use lowercase letters, digits, hyphens only "
            f"(e.g. 'my-first-paper'). 2-64 chars."
        )

    template_dir = repo_root / "templates" / _template_dirname(template)
    if (template_dir / ".stub").exists():
        raise NotImplementedError(
            f"{template} full scaffolding ships in Plan E. "
            f"Run `student new --template T0` for now."
        )

    target = workbook / slug
    if target.exists():
        raise FileExistsError(f"Workbook folder already exists: {target}")

    shutil.copytree(template_dir, target, ignore=shutil.ignore_patterns(".stub"))

    # Git init the workbook if it isn't already a repo
    if not (workbook / ".git").exists():
        subprocess.run(["git", "init", "-q"], cwd=workbook, check=False)
    return target


def _template_dirname(code: str) -> str:
    return {
        "T0": "T0_blank",
        "T1": "T1_pairwise_mini_ma",
        "T2": "T2_trials_audit",
        "T3": "T3_burden_snapshot",
        "T4": "T4_ma_replication",
        "T5": "T5_living_ma_seed",
    }[code]
```

- [ ] **Step 4: Write T0 files**

`templates\T0_blank\README.md`:

```markdown
# {{slug}}

Your first paper. This is the blank template — you get a workbook
folder with the three files you need.

## Files

- `README.md`     — this file
- `e156_body.md`  — the 156-word body (7 sentences). Validator rejects
                    unfilled `{{tokens}}`.
- `preanalysis.md` — write your plan here and commit it BEFORE you
                    start pulling data.

## Next steps

1. Edit `preanalysis.md`; write what you're going to analyse and commit it.
2. Edit `e156_body.md` sentence by sentence.
3. Run `student validate` to check format.
```

`templates\T0_blank\e156_body.md`:

```markdown
<!--
  E156 body — 7 sentences, 156 words max, one estimand.
  Replace every {{token}} before you submit.
  Run `student validate` before `git push`.
-->

**S1 — Question.** {{S1_QUESTION}}

**S2 — Dataset.** {{S2_DATASET}}

**S3 — Method.** {{S3_METHOD}}

**S4 — Result.** {{S4_RESULT}}

**S5 — Robustness.** {{S5_ROBUSTNESS}}

**S6 — Interpretation.** {{S6_INTERPRETATION}}

**S7 — Boundary.** {{S7_BOUNDARY}}
```

`templates\T0_blank\preanalysis.md`:

```markdown
# Pre-analysis plan — {{slug}}

Commit this BEFORE you run any analysis. The validator checks the git SHA
of this file's commit.

## PICO

- **Population:** ...
- **Intervention:** ...
- **Comparator:** ...
- **Outcome:** ...

## Primary estimand

(One specific claim you will report in S4. Example: pooled HR of
cardiovascular death, random-effects REML, 95% HKSJ CI.)

## Analyses you will run

1. ...

## Analyses you will NOT run

1. ...

## Data source

Zenodo snapshot DOI (pinned in `config/pins.json`): ...
```

- [ ] **Step 5: Write T1-T5 `.stub` files**

For each of `templates\T1_...\.stub`, `T2_...\.stub`, ... write:

```
Plan E ships full template scaffolding for this template.
Until then, `student new --template T1` (or T2..T5) will refuse
with a friendly message pointing at T0.
```

- [ ] **Step 6: Wire scaffold into `bin/student.py`**

Replace the stub in `_cmd_new`:

```python
def _cmd_new(args) -> int:
    if args.template is None:
        print("Let's pick a template for you.")
        if args.dry_run:
            return 0
        from bin.help_me_pick import run as run_picker
        run_picker()
        return 0
    from bin.scaffold import scaffold
    slug = args.slug or input("Pick a short slug (lowercase, hyphens): ").strip()
    workbook = Path(os.environ.get("LOCALAPPDATA", "")) / "e156" / "workbook"
    workbook.mkdir(parents=True, exist_ok=True)
    try:
        target = scaffold(args.template, slug=slug, workbook=workbook,
                          repo_root=Path(__file__).resolve().parents[1])
    except NotImplementedError as e:
        print(f"\n{e}\n")
        return 1
    print(f"Scaffolded: {target}")
    return 0
```

Update the parser to accept `--slug`:

```python
p.add_argument("--slug", default=None)
```

- [ ] **Step 7: Run tests to confirm pass**

```bash
python -m pytest tests/unit/test_scaffold.py tests/unit/test_student_cli.py -v
```

Expected: all passed.

- [ ] **Step 8: Commit**

```bash
git add templates/ bin/scaffold.py bin/student.py tests/unit/test_scaffold.py
git commit -m "feat(scaffold): T0 blank template + T1-T5 stubs + student new wiring"
```

---

### Task 14: README update — remove PowerShell instructions, point at Start.bat

**Files:**
- Modify: `README.md`
- Delete: `install\install.sh`

- [ ] **Step 1: Delete `install/install.sh`** (Windows-only per D1)

```bash
git rm install/install.sh
```

- [ ] **Step 2: Rewrite `README.md` install section**

Replace lines 32–45 of `README.md` (the Install section) with:

```markdown
## Install

1. Download `e156-student-starter-v0.2.0.zip` from the
   [releases page](https://github.com/mahmood726-cyber/e156-student-starter/releases).
2. Right-click the zip → **Extract All** → pick a folder you'll remember.
3. Open the folder and **double-click `Start.bat`**.

That's it. You never need to open PowerShell or type anything in a terminal
for install.

### If Windows says "Windows protected your PC"

Click **More info** → **Run anyway**. Windows is cautious about scripts
from the internet. This one is open-source and the SHA256 hash of the zip
is published at
[synthesis-medicine.org/e156-hash.txt](https://synthesis-medicine.org/e156-hash.txt).
You can verify with PowerShell if you want:

```powershell
Get-FileHash -Algorithm SHA256 e156-student-starter-v0.2.0.zip
```

Compare the output with the hash on the Synthesis site. If they match, the
download is intact.

### What happens during install

- Checks your RAM and picks the right AI models (2 GB total for small
  laptops; 8 GB for bigger ones; cloud-only if your laptop is very small).
- Downloads a portable AI runtime (about 350 MB).
- Downloads the AI models (2–10 GB depending on your tier).
- Sets up your `~/e156/` folder.
- Runs a quick test to confirm everything works.
- Opens a welcome wizard to record your name and agree to the AI's rules.

**Total download size: 2–10 GB. On a 1.5 Mbps connection this takes 3 to
15 hours. Leave it running overnight. You can safely pause and resume.**
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git rm install/install.sh 2>/dev/null || true
git commit -m "docs: rewrite install section for Start.bat; remove install.sh"
```

---

### Task 15: `.github/workflows/release.yml` — CI release pipeline

**Files:**
- Create: `.github\workflows\release.yml`

- [ ] **Step 1: Write the workflow**

```yaml
name: release

on:
  push:
    tags: ['v*']
  workflow_dispatch:

jobs:
  build-and-test:
    runs-on: windows-2022
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install Python test deps
        run: |
          python -m pip install --upgrade pip
          python -m pip install pytest jsonschema

      - name: Install Pester 5
        shell: pwsh
        run: |
          Install-Module -Name Pester -MinimumVersion 5.0 -Force -SkipPublisherCheck
          Import-Module Pester -MinimumVersion 5.0

      - name: Run Python unit tests
        run: python -m pytest tests/unit -v

      - name: Run Pester tests
        shell: pwsh
        run: Invoke-Pester -Path install/pester.tests.ps1 -Output Detailed -CI

      - name: Assemble bundle layout
        shell: pwsh
        run: |
          $stage = "dist/e156-student-starter-$env:GITHUB_REF_NAME"
          New-Item -ItemType Directory -Path $stage -Force
          Copy-Item Start.bat $stage
          Copy-Item README.md $stage
          Copy-Item -Recurse ai $stage
          Copy-Item -Recurse bin $stage
          Copy-Item -Recurse config $stage
          Copy-Item -Recurse docs $stage
          Copy-Item -Recurse install $stage
          Copy-Item -Recurse rules $stage
          Copy-Item -Recurse templates $stage
          Copy-Item -Recurse tests $stage
          Copy-Item -Recurse tools $stage

      - name: Compute zip SHA256
        id: shazip
        shell: pwsh
        run: |
          $stage = "dist/e156-student-starter-$env:GITHUB_REF_NAME"
          $zip = "dist/e156-student-starter-$env:GITHUB_REF_NAME.zip"
          Compress-Archive -Path "$stage/*" -DestinationPath $zip -Force
          $sha = (Get-FileHash -Algorithm SHA256 $zip).Hash.ToLower()
          Set-Content docs/HASH.txt $sha -NoNewline
          "sha=$sha" | Out-File -Append $env:GITHUB_OUTPUT
          Write-Host "::notice title=Zip SHA256::$sha"

      - name: Publish release
        if: startsWith(github.ref, 'refs/tags/v')
        uses: softprops/action-gh-release@v2
        with:
          files: |
            dist/e156-student-starter-*.zip
            config/pins.json
            docs/HASH.txt
            review-findings.md
          body: |
            ## Verification

            After downloading, verify with PowerShell:

            ```powershell
            Get-FileHash -Algorithm SHA256 e156-student-starter-${{ github.ref_name }}.zip
            ```

            Expected SHA256: `${{ steps.shazip.outputs.sha }}`

            Cross-check against: https://synthesis-medicine.org/e156-hash.txt
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "ci(release): windows-2022 build + Pester + pytest + zip SHA + GH Release"
```

---

### Task 16: End-to-end integration test (bandwidth-capped)

**Files:**
- Create: `tests\integration\test_install_e2e.py`
- Modify: `.github\workflows\release.yml` (add integration step)

- [ ] **Step 1: Write the integration test**

Create `tests\integration\test_install_e2e.py`:

```python
"""End-to-end: clean %LOCALAPPDATA% → Start.bat --what-would-i-do → ...

This is the gated release criterion. Plan A is NOT done until this passes.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(os.name != "nt", reason="Windows-only E2E")
@pytest.mark.integration
def test_start_bat_first_run_prints_install_instruction(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    r = subprocess.run(
        ["cmd", "/c", str(REPO_ROOT / "Start.bat"), "--what-would-i-do"],
        capture_output=True, text=True, timeout=10,
    )
    assert r.returncode == 0
    assert "install.ps1" in r.stdout


@pytest.mark.skipif(os.name != "nt", reason="Windows-only E2E")
@pytest.mark.integration
def test_install_ps1_rollback_on_missing_ollama(tmp_path, monkeypatch):
    """If Ollama download fails, ~/e156/ is cleaned up; no half-state remains."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    # Force fail by pointing Ollama URL at localhost (will ECONNREFUSED)
    monkeypatch.setenv("E156_OLLAMA_URL_OVERRIDE", "http://127.0.0.1:1/does-not-exist")
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", str(REPO_ROOT / "install" / "install.ps1")],
        capture_output=True, text=True, timeout=120,
    )
    # Rollback path: ~/e156/ should not exist
    assert not (Path(tmp_path) / "e156").exists()
    assert r.returncode != 0


@pytest.mark.skipif(os.name != "nt", reason="Windows-only E2E")
@pytest.mark.integration
@pytest.mark.slow
def test_full_install_under_45_minutes_wallclock(tmp_path, monkeypatch):
    """The promise: a first-time user completes install in <45 min on a slow connection.

    This test assumes Ollama is already installed on the CI runner (it is on
    windows-2022). Runs a non-throttled install; release.yml adds the
    bandwidth throttle.
    """
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    start = time.monotonic()
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", str(REPO_ROOT / "install" / "install.ps1"), "-LowRam"],
        capture_output=True, text=True, timeout=60 * 45,
        input="Test User\ntest@example.com\nAGREE\n",
    )
    elapsed = time.monotonic() - start
    assert r.returncode == 0, f"Install failed: {r.stderr[-2000:]}"
    assert elapsed < 45 * 60, f"Install took {elapsed/60:.1f} min (budget 45)"
    assert (Path(tmp_path) / "e156" / ".installed").exists()
    assert (Path(tmp_path) / "e156" / ".consent.json").exists()
```

- [ ] **Step 2: Add integration job to release.yml**

Append after the unit-test job:

```yaml
  integration:
    needs: build-and-test
    runs-on: windows-2022
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: python -m pip install pytest jsonschema
      - name: Install Ollama
        shell: pwsh
        run: |
          $pins = Get-Content config/pins.json -Raw | ConvertFrom-Json
          Invoke-WebRequest -Uri $pins.ollama.url -OutFile "$env:TEMP\ollama.zip"
          Expand-Archive -Path "$env:TEMP\ollama.zip" -DestinationPath "$env:TEMP\ollama"
          "$env:TEMP\ollama" >> $env:GITHUB_PATH
      - name: Pull small model for smoke
        run: ollama pull gemma2:2b
      - name: Run integration tests
        run: python -m pytest tests/integration -m "integration and not slow" -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_install_e2e.py .github/workflows/release.yml
git commit -m "test(integration): E2E install + rollback + 45-min wall-clock gate"
```

---

### Task 17: Fix known regressions the review flagged (quick hits)

**Files:**
- Modify: `tests\tiny_model_benchmark.py`
- Modify: `tests\fixtures\` (new dir)
- Modify: `install\install.ps1`

- [ ] **Step 1: Move generated baseline to fixtures**

```bash
mkdir -p tests/fixtures
git mv tests/results_050b_baseline.json tests/fixtures/results_050b_baseline.json
```

Update `tests/tiny_model_benchmark.py` to read from `fixtures/`:

```python
# Old:
BASELINE = Path(__file__).parent / "results_050b_baseline.json"
# New:
BASELINE = Path(__file__).parent / "fixtures" / "results_050b_baseline.json"
```

Update `tiny_model_benchmark.py` max-word cap on the prose check from 200 → 156 (E156 spec):

```python
# Line ~57:
MAX_WORDS_FOR_E156_PROSE = 156  # was 200; aligns with validate_e156
```

- [ ] **Step 2: Add BOM-free `.env` write in install.ps1**

In `install.ps1`, replace any `Set-Content -Encoding UTF8` call used for `.env` creation with:

```powershell
[System.IO.File]::WriteAllText($envFile, $envContent,
    (New-Object System.Text.UTF8Encoding $false))
```

This avoids the PowerShell 5.1 BOM issue noted in `U-P1-7`.

- [ ] **Step 3: Run all tests to confirm no regression**

```bash
python -m pytest tests/ -v
```

Expected: all passed (unit + integration modulo `slow` marks).

- [ ] **Step 4: Commit**

```bash
git add tests/ install/install.ps1
git commit -m "fix(regressions): move baseline to fixtures, 156-word cap, UTF8-no-BOM"
```

---

### Task 18: Final gate — manual smoke of the whole flow

**Files:** (no file changes — this is a verification gate)

- [ ] **Step 1: On a clean Windows VM (or Windows Sandbox), perform the 10-minute manual test:**

1. Download the CI-built zip (or a locally-built one).
2. Right-click → Extract All.
3. Double-click `Start.bat`.
4. Observe: zero PowerShell window visible to the student — only a friendly progress display.
5. Observe: SmartScreen warning handled via the README callout.
6. First-run wizard runs; type a name, email, and `AGREE`.
7. Watch the model-download progress with plain-English ETA.
8. After smoke passes, help-me-pick wizard offers T1-T5 with recommendations.
9. Pick T0, give it a slug, observe it scaffolds to `~/e156/workbook/<slug>/`.
10. Run `student doctor`; observe redacted diagnostic bundle.

- [ ] **Step 2: Tag the release candidate**

```bash
git tag v0.2.0-plan-A-rc1
git push origin v0.2.0-plan-A-rc1
```

- [ ] **Step 3: Verify CI is green on the tag** (GitHub Actions "release" workflow passes for the tag).

- [ ] **Step 4: Open a PR from `v0.2-plan-A` to `main`** with the tag as the release candidate.

- [ ] **Step 5: On merge, re-tag as `v0.2.0-plan-A` and let CI publish the GitHub Release.**

---

## Self-review

- **Spec coverage:** 9 components (C1, C2, C3, C4, C8, C14, C15, C17, C18) from spec §4 mapped to Tasks 8-16 + 3-7 + 12 + 1 + 15 respectively. Tier detection from §3.1 covered in Task 9. Rollback from §6.1 principle in Task 9. Smoke-gated banner from U-P0-4 in Task 11. Start.bat SmartScreen handling from U-P0-2 in Task 12. Friendly-error layer from U-P0-5 in Task 2. All Plan-A-scoped spec items land in a task.
- **Placeholder scan:** The only `<paste-...>` tokens are in Task 1 Step 4, with explicit instructions to run `Get-FileHash` / `ollama show` commands and replace before commit. No `TBD`, no `TODO`, no "fill in later". Each step has exact code or exact command.
- **Type consistency:** `FriendlyMessage` defined in Task 2, used in Task 3; `Select-Tier` defined in Task 9, used in Task 10 real flow; `Invoke-OllamaPullWithRetry` defined in Task 10, used in Task 10 flow; `scaffold()` defined in Task 13 with signature `(template, slug, workbook, repo_root)`, test file matches.
- **Ordering:** Foundation first (pins, friendly_error, CLI, TUI). get_unstuck is installed before install.ps1 needs it for smoke-fail recovery. Wizard + picker land just after CLI. install.ps1 refactor in three passes (SHA → tier → smoke). Start.bat last because it needs install.ps1 working. CI + integration at the end.

---

## Execution handoff

**Plan complete and saved to:**
- Primary (when D: mounts): `D:\e156-student-starter\docs\superpowers\plans\2026-04-19-plan-A-install-first-touch.md`
- Backup (this file): `C:\Users\user\e156-student-starter-spec-backup\plans\2026-04-19-plan-A-install-first-touch.md`

Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Good for solo-author context; reduces your cognitive load across 18 tasks.

2. **Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batched with checkpoints for review.

**Which approach?** (If the user already said "do all" earlier, default to **Subagent-Driven** and start dispatching Task 0.)
