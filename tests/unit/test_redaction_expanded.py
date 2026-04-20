"""Expanded redaction patterns in tools/get_unstuck.py (review H-P1-1)."""
from __future__ import annotations

from tools.get_unstuck import redact


def test_github_fine_grained_pat_redacted():
    raw = "token=github_pat_11ABCDEFGHIJKLMNOPQRSTU_abc123XYZ456"
    out = redact(raw)
    assert "github_pat_11" not in out
    assert "REDACTED" in out


def test_openai_project_key_redacted():
    raw = "OPENAI_API_KEY=sk-proj-abc123XYZ456DEF789ghi"
    out = redact(raw)
    assert "sk-proj-abc" not in out


def test_anthropic_key_redacted():
    raw = "ANTHROPIC_API_KEY=sk-ant-api03-abcdefghij1234567890"
    out = redact(raw)
    assert "sk-ant-api03" not in out


def test_huggingface_token_redacted():
    raw = "HF_TOKEN=hf_abcdefghijklmnopqrstuvwxyz123456789"
    out = redact(raw)
    assert "hf_abc" not in out


def test_openssh_private_key_block_redacted():
    raw = """-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
-----END OPENSSH PRIVATE KEY-----"""
    out = redact(raw)
    assert "b3BlbnNz" not in out
    assert "REDACTED-SSH-PRIVKEY" in out


def test_rsa_private_key_block_redacted():
    raw = """-----BEGIN RSA PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC
-----END RSA PRIVATE KEY-----"""
    out = redact(raw)
    assert "MIIEvgIBA" not in out


def test_existing_patterns_still_work():
    # Windows user path + Google key + classic ghp_ PAT still redacted
    raw = r"C:\Users\alice key=AIzaSyABC123DEF456GHI789JKL012MNO345PQR678 pat=ghp_abcdefghij1234567890klmnopqrstuvwxyz12"
    out = redact(raw)
    assert r"C:\Users\alice" not in out
    assert "AIzaSy" not in out
    assert "ghp_abcdefghij" not in out  # redacted
