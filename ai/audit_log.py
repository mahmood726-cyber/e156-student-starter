"""Append-only audit log for every successful ai_call.

The log is content-hashed, not content-stored, so student prompts and
responses never land in a file that might leak patient data or PII. Each
line records: timestamp, backend, model, kind, prompt SHA256 (prefix), and
response SHA256 (prefix), latency, and response word count.

The log exists so a student can later prove:
  1. Which AI call produced which output (hash matches).
  2. Whether they routed that output through `student sentinel check`.
  3. Timing history for reporting in manuscript methods sections.

Location: %LOCALAPPDATA%\\e156\\logs\\ai_calls.jsonl

Failures are swallowed — the audit log must never break an AI call.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _log_path() -> Path:
    lad = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(lad) / "e156" / "logs" / "ai_calls.jsonl"


def _sha_prefix(text: str, n: int = 16) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:n]


def record(
    *,
    task_kind: str,
    backend: str,
    model: str,
    prompt: str,
    response: str,
    elapsed_ms: int,
    sentinel_scanned: bool = False,
    sentinel_findings: int = 0,
) -> bool:
    """Append a single audit entry. Returns True on success, False on any failure."""
    try:
        log = _log_path()
        log.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "task_kind": task_kind,
            "backend": backend,
            "model": model,
            "prompt_sha_prefix": _sha_prefix(prompt),
            "response_sha_prefix": _sha_prefix(response),
            "response_words": len(response.split()),
            "elapsed_ms": elapsed_ms,
            "sentinel_scanned": sentinel_scanned,
            "sentinel_findings": sentinel_findings,
        }
        with log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
        return True
    except Exception:
        return False


def iter_entries():
    """Yield each log entry as a dict. Missing log file yields nothing."""
    log = _log_path()
    if not log.is_file():
        return
    with log.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue
