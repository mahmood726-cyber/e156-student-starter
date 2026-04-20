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
