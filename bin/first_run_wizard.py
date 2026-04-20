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
        print("(Gemma plain-English rules file missing - continuing without it.)")


def _localappdata_e156() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", "")) / "e156"


def _prewarm_prose_model() -> None:
    """Fire-and-forget background thread that loads the prose model into Ollama RAM
    while the student reads the Gemma rules and types AGREE.

    First-call-ever latency for gemma2:9b is ~60s cold vs ~5s warm. By the time
    the wizard finishes its 30-60s of interactive prompts, Ollama has the model
    resident and the first `student ai prose` call returns fast.

    Silent on failure — pre-warm is a UX nicety, not a correctness dep.
    """
    import threading
    import urllib.request
    import urllib.error

    def _fire() -> None:
        try:
            model = os.environ.get("E156_PROSE_MODEL", "gemma2:2b")
            host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
            body = json.dumps({"model": model, "prompt": "ok", "stream": False}).encode()
            req = urllib.request.Request(
                f"{host}/api/generate", data=body,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=120).read()
        except (urllib.error.URLError, TimeoutError, OSError):
            pass

    t = threading.Thread(target=_fire, daemon=True)
    t.start()


def _offer_hook_install() -> None:
    """Opt-in pre-push hook install. Safe to answer no; student can run
    `student sentinel install-hook` any time later."""
    print("Before every `git push`, a tiny scanner can flag common AI-assisted")
    print("mistakes (hardcoded paths, empty-DataFrame bugs, placeholder text).")
    print("Takes 2 seconds, blocks only on serious issues, skippable per push.\n")
    answer = input("Install the pre-push safety net? [Y/n] ").strip().lower()
    if answer and answer not in ("y", "yes"):
        print("Skipped. Run `student sentinel install-hook` later if you change your mind.\n")
        return

    workbook = _localappdata_e156() / "workbook"
    workbook.mkdir(parents=True, exist_ok=True)
    import subprocess
    if not (workbook / ".git").is_dir():
        subprocess.run(["git", "init", "-q"], cwd=workbook, check=False)

    from tools.sentinel_check import install_hook  # noqa: WPS433
    try:
        target = install_hook(workbook)
        print(f"Hook installed at {target}.\n")
    except (FileNotFoundError, RuntimeError) as e:
        print(f"Couldn't install hook: {e}. Run `student sentinel install-hook` later.\n")


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


def run_wizard(skip_smoke: bool = False, prewarm: bool = True) -> int:
    print("Welcome to e156 - this wizard takes about 2 minutes of your time.\n")
    print("(The big model download already happened in the installer before this.)\n")

    if prewarm:
        _prewarm_prose_model()

    # Consent-in-the-right-order: show Gemma rules + gate AGREE BEFORE we
    # capture any PII. A student who refuses has written nothing to disk.
    print("Before anything is installed or any identity is captured, please")
    print("read the Gemma Prohibited Use Policy below carefully:\n")
    _print_gemma_rules()

    print("\nIf you agree to ALL the rules above, type the word AGREE (all caps).")
    print("If you do not agree, type anything else and the installer will close")
    print("without writing your name, email, or any files to this laptop.\n")

    answer = input("> ").strip()
    if answer != "AGREE":
        print("\nYou did not agree. Nothing has been installed. You can restart later.")
        return 2

    # Only AFTER AGREE do we ask for identity.
    name = input("Your full name: ").strip()
    if not name:
        print("\nA name is required. Closing.")
        return 1

    email = input("Your university email: ").strip()
    if "@" not in email or "." not in email.split("@")[-1]:
        print("\nThat doesn't look like a valid email. Closing.")
        return 1

    path = _write_consent(name, email)
    print(f"\nThanks {name.split()[0]}. Agreement recorded at {path}.\n")

    _offer_hook_install()

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
