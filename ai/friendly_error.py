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
        return f"{self.text} \u2014 {self.next_command}"


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
