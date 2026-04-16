"""End-to-end smoke test for the student starter.

Run this after install to verify everything works. Designed to be:
  - Deterministic (fixed prompts, checked for known-good shapes)
  - Informative on failure (print which step died + suggested fix)
  - Usable offline (never asks the network unless a cloud backend is set)
  - Honest about degraded modes (if you only have small models, we still
    PASS but print a soft-warning)

Exit codes:
  0  — all checks passed (possibly with warnings)
  1  — a core check failed
  2  — bootstrap incomplete (Ollama not running, no models pulled, etc.)
"""
from __future__ import annotations
import os
import subprocess
import sys
import time
from pathlib import Path

STARTER = Path(__file__).resolve().parents[1]
AI_CALL = STARTER / "ai" / "ai_call.py"
VALIDATOR = STARTER / "tools" / "validate_e156.py"
EXAMPLE = STARTER / "examples" / "example_paper_01" / "current_body.txt"


def step(msg: str) -> None:
    print(f"==> {msg}", flush=True)


def ok(msg: str) -> None:
    print(f"    [PASS] {msg}", flush=True)


def fail(msg: str, suggestion: str = "") -> None:
    print(f"    [FAIL] {msg}", flush=True)
    if suggestion:
        print(f"           try: {suggestion}", flush=True)


def warn(msg: str) -> None:
    print(f"    [warn] {msg}", flush=True)


def run_cmd(args: list[str], timeout: int = 120) -> tuple[int, str]:
    """Run a subprocess and return (exit_code, stdout+stderr)."""
    try:
        p = subprocess.run(
            args, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout,
        )
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout}s"
    except FileNotFoundError as e:
        return 127, str(e)


def check_files() -> bool:
    step("Check 1/5 — required files present")
    missing = []
    for f in [AI_CALL, VALIDATOR, EXAMPLE, STARTER / "README.md"]:
        if not f.is_file():
            missing.append(str(f))
    if missing:
        fail(f"missing: {', '.join(missing)}",
             "re-run install.ps1 / install.sh from install/ dir")
        return False
    ok("all required files present")
    return True


def check_ollama() -> tuple[bool, bool]:
    """Return (ollama_up, at_least_one_model_pulled)."""
    step("Check 2/5 — Ollama server reachable")
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2) as r:
            body = r.read().decode()
    except Exception as e:
        fail(f"Ollama not reachable ({type(e).__name__}: {e})",
             "run: ollama serve")
        return False, False
    ok("Ollama is running")

    # Sub-check: at least one model is pulled.
    import json
    try:
        models = json.loads(body).get("models", [])
    except Exception:
        models = []
    if not models:
        warn("no models pulled yet — run: ollama pull gemma2:9b")
        return True, False
    ok(f"models available: {', '.join(m['name'] for m in models)}")
    return True, True


def check_validator() -> bool:
    step("Check 3/5 — E156 format validator")
    rc, out = run_cmd([sys.executable, str(VALIDATOR), str(EXAMPLE)])
    if rc != 0 or "PASS" not in out:
        fail(f"validator failed (rc={rc}): {out[:200]}",
             "the example body should PASS — file may be corrupted")
        return False
    ok(out.strip())
    return True


def check_router_quick() -> bool:
    step("Check 4/5 — AI router (quick model, ~1s)")
    env = os.environ.copy()
    env["E156_AI_DEBUG"] = "1"
    start = time.time()
    rc, out = run_cmd(
        [sys.executable, str(AI_CALL), "quick", "Reply with exactly: OK"],
        timeout=60,
    )
    elapsed = time.time() - start
    if rc != 0:
        fail(f"router call failed (rc={rc}): {out[:300]}",
             "check Ollama is running and a model is pulled")
        return False
    if "OK" not in out.upper():
        warn(f"router responded but answer was unexpected: {out[:100]!r}")
        # Not a hard fail — the quick model may add pleasantries.
    ok(f"router responded in {elapsed:.1f}s: {out.strip()[:80]}")
    return True


def check_router_prose() -> bool:
    step("Check 5/5 — prose model (Gemma, ~5-30s on CPU)")
    env = os.environ.copy()
    env["E156_AI_DEBUG"] = "1"
    start = time.time()
    rc, out = run_cmd(
        [sys.executable, str(AI_CALL), "prose",
         "In one sentence: what does the phrase 'evidence-based medicine' mean?"],
        timeout=180,
    )
    elapsed = time.time() - start
    if rc != 0:
        fail(f"prose call failed (rc={rc}): {out[:300]}")
        return False
    if len(out.strip()) < 20:
        warn(f"prose reply seems very short: {out.strip()!r}")
    ok(f"prose responded in {elapsed:.1f}s ({len(out.strip())} chars)")
    return True


def main() -> int:
    print("=" * 60)
    print("E156 Student Starter — smoke test")
    print("=" * 60)

    all_ok = True
    if not check_files():
        return 2

    ollama_up, models_ready = check_ollama()
    if not ollama_up:
        return 2
    if not models_ready:
        warn("skipping router checks until a model is pulled")
        print("\nPartial PASS. Run `ollama pull gemma2:9b` then re-run this test.")
        return 2

    if not check_validator():
        all_ok = False
    if not check_router_quick():
        all_ok = False
    # Prose model test is slow; make it optional via env.
    if os.environ.get("E156_SMOKE_SKIP_PROSE", "") != "1":
        if not check_router_prose():
            all_ok = False

    print()
    if all_ok:
        print("=" * 60)
        print("ALL CHECKS PASSED — you're ready to claim a paper.")
        print("Next: cd examples/example_paper_01 && cat README.md")
        print("=" * 60)
        return 0
    print("=" * 60)
    print("Some checks failed — see messages above.")
    print("=" * 60)
    return 1


if __name__ == "__main__":
    sys.exit(main())
