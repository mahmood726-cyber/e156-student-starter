"""Audit log records every AI call, safely, without storing prompt/response text."""
from __future__ import annotations

import json
from pathlib import Path

from ai import audit_log


def test_record_appends_hashed_entry(isolated_localappdata):
    ok = audit_log.record(
        task_kind="prose", backend="ollama", model="gemma2:2b",
        prompt="rewrite this please", response="here is the rewrite",
        elapsed_ms=1234,
    )
    assert ok is True
    log = isolated_localappdata / "e156" / "logs" / "ai_calls.jsonl"
    assert log.is_file()
    entries = list(audit_log.iter_entries())
    assert len(entries) == 1
    e = entries[0]
    assert e["task_kind"] == "prose"
    assert e["backend"] == "ollama"
    assert e["model"] == "gemma2:2b"
    assert e["elapsed_ms"] == 1234
    assert e["response_words"] == 4
    assert len(e["prompt_sha_prefix"]) == 16
    assert len(e["response_sha_prefix"]) == 16


def test_record_does_NOT_store_raw_content(isolated_localappdata):
    secret = "PATIENT MRN 12345 diagnosed with rare condition"
    audit_log.record(
        task_kind="prose", backend="ollama", model="gemma2:2b",
        prompt=secret, response=secret, elapsed_ms=100,
    )
    log_text = (isolated_localappdata / "e156" / "logs" / "ai_calls.jsonl").read_text(encoding="utf-8")
    assert "PATIENT" not in log_text
    assert "MRN" not in log_text
    assert "12345" not in log_text
    assert "rare condition" not in log_text


def test_record_appends_not_overwrites(isolated_localappdata):
    for i in range(3):
        audit_log.record(
            task_kind="code", backend="ollama", model="qwen2.5-coder:1.5b",
            prompt=f"call {i}", response=f"resp {i}", elapsed_ms=10,
        )
    assert len(list(audit_log.iter_entries())) == 3


def test_record_same_prompt_yields_same_hash(isolated_localappdata):
    """Deterministic hashes let students correlate audit entries to code/responses."""
    audit_log.record(
        task_kind="prose", backend="ollama", model="gemma2:2b",
        prompt="identical prompt", response="r", elapsed_ms=1,
    )
    audit_log.record(
        task_kind="prose", backend="ollama", model="gemma2:2b",
        prompt="identical prompt", response="r", elapsed_ms=1,
    )
    entries = list(audit_log.iter_entries())
    assert entries[0]["prompt_sha_prefix"] == entries[1]["prompt_sha_prefix"]


def test_record_safe_when_localappdata_unset(monkeypatch, tmp_path):
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))  # fallback via expanduser
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    ok = audit_log.record(
        task_kind="quick", backend="ollama", model="gemma2:2b",
        prompt="x", response="y", elapsed_ms=1,
    )
    # Either it wrote to $HOME/e156/logs (ok=True) or swallowed the error (ok=False).
    # Both are acceptable; what matters is no exception leaked.
    assert ok in (True, False)
