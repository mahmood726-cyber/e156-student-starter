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
    print("Welcome to e156 - let's get you set up (should take 2 minutes).\n")

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
