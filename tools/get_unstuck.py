"""Diagnostic bundler + redactor for e156-student-starter.

`student doctor` -> gather() -> redact() -> build_zip() -> show contents -> mailto.
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
    # GitHub classic PATs (ghp_, gho_, ghu_, ghs_, ghr_)
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"), "ghp_***REDACTED***"),
    # GitHub fine-grained PATs (review H-P1-1: not caught by the gh[pousr]_ pattern)
    (re.compile(r"github_pat_[A-Za-z0-9_]{22,}"), "github_pat_***REDACTED***"),
    # Google / Gemini API keys
    (re.compile(r"AIza[0-9A-Za-z\-_]{35}"), "AIza_***REDACTED***"),
    # OpenAI project-scoped keys (sk-proj-) — review H-P1-1
    (re.compile(r"sk-proj-[A-Za-z0-9_\-]{20,}"), "sk-proj-***REDACTED***"),
    # Anthropic API keys (sk-ant-) — review H-P1-1
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"), "sk-ant-***REDACTED***"),
    # HuggingFace tokens
    (re.compile(r"\bhf_[A-Za-z0-9]{30,}"), "hf_***REDACTED***"),
    # Generic OpenAI-classic keys (sk- + 48 alnum) — retained; narrow match last
    (re.compile(r"sk-[A-Za-z0-9]{48}"), "sk-***REDACTED***"),
    # OpenSSH private-key blocks (review H-P1-1)
    (re.compile(r"-----BEGIN OPENSSH PRIVATE KEY-----.*?-----END OPENSSH PRIVATE KEY-----",
                re.DOTALL), "-----REDACTED-SSH-PRIVKEY-----"),
    # Other private-key formats
    (re.compile(r"-----BEGIN (RSA|EC|DSA|PGP) PRIVATE KEY-----.*?-----END \1 PRIVATE KEY-----",
                re.DOTALL), "-----REDACTED-PRIVKEY-----"),
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
