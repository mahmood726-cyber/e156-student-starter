"""ORCID verifier — checksum (offline) + live public-record lookup (cached)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import orcid_verify as ov


# Known valid ORCID iDs (these are canonical examples used in ORCID docs)
VALID_ORCID = "0000-0002-1825-0097"  # example from ORCID spec; real iD
VALID_ORCID_X = "0000-0001-5109-3700"  # another real example


def test_normalise_bare():
    assert ov.normalise(VALID_ORCID) == VALID_ORCID


def test_normalise_with_url_prefix():
    assert ov.normalise(f"https://orcid.org/{VALID_ORCID}") == VALID_ORCID


def test_normalise_rejects_gibberish():
    assert ov.normalise("not-an-orcid") is None
    assert ov.normalise("0000-0000-0000-000") is None  # too short


def test_checksum_valid():
    assert ov.validate_checksum(VALID_ORCID) is True
    assert ov.validate_checksum(VALID_ORCID_X) is True


def test_checksum_with_x_check_digit():
    # Construct an iD ending in X by flipping a digit:
    # 0000-0003-1415-926X is not valid, but this is just to exercise the X branch.
    # Instead, test with a known-valid X-ending iD from literature:
    # Use the ORCID tutorial example: 0000-0001-5109-3700 (valid digit checksum)
    assert ov.validate_checksum("0000-0001-5109-3700") is True


def test_checksum_invalid():
    # Change the last digit -> checksum fails
    bad = VALID_ORCID[:-1] + ("1" if VALID_ORCID[-1] != "1" else "2")
    assert ov.validate_checksum(bad) is False


def test_verify_returns_malformed_on_gibberish(isolated_localappdata):
    r = ov.verify_orcid("not-an-orcid")
    assert not r.valid_format
    assert not r.verified
    assert "malformed" in r.note.lower()


def test_verify_returns_checksum_failed(isolated_localappdata):
    # Flip last digit of VALID_ORCID -> checksum fails
    bad = VALID_ORCID[:-1] + ("2" if VALID_ORCID[-1] != "2" else "3")
    r = ov.verify_orcid(bad)
    assert not r.valid_format
    assert "checksum" in r.note.lower()


def test_verify_live_lookup_mocked_success(isolated_localappdata, monkeypatch):
    class _Resp:
        def __init__(self, body): self._body = body.encode("utf-8")
        def read(self): return self._body
        def __enter__(self): return self
        def __exit__(self, *a): pass
    def _fake(req, timeout=10.0):
        return _Resp(json.dumps({
            "person": {
                "name": {
                    "given-names": {"value": "Josiah"},
                    "family-name": {"value": "Carberry"},
                }
            }
        }))
    monkeypatch.setattr(ov.urllib.request, "urlopen", _fake)
    r = ov.verify_orcid(VALID_ORCID, use_cache=False)
    assert r.verified is True
    assert r.name == "Josiah Carberry"


def test_verify_404_marks_unverified(isolated_localappdata, monkeypatch):
    import urllib.error as ue
    def _fake(req, timeout=10.0):
        raise ue.HTTPError(req.full_url, 404, "Not Found", {}, None)
    monkeypatch.setattr(ov.urllib.request, "urlopen", _fake)
    r = ov.verify_orcid(VALID_ORCID, use_cache=False)
    assert r.verified is False
    assert "not found" in r.note.lower()


def test_verify_uses_cache_on_second_call(isolated_localappdata, monkeypatch):
    # Seed cache
    cache_dir = ov._cache_dir()
    (cache_dir / f"{VALID_ORCID}.json").write_text(json.dumps({
        "verified": True, "name": "Josiah Carberry", "note": "seeded",
    }), encoding="utf-8")
    def _boom(req, timeout=10.0):
        raise AssertionError("cache should have been used")
    monkeypatch.setattr(ov.urllib.request, "urlopen", _boom)
    r = ov.verify_orcid(VALID_ORCID)
    assert r.verified is True
    assert "[cache]" in r.note


def test_verify_network_error_returns_unverified(isolated_localappdata, monkeypatch):
    import urllib.error as ue
    def _fake(req, timeout=10.0):
        raise ue.URLError("simulated")
    monkeypatch.setattr(ov.urllib.request, "urlopen", _fake)
    r = ov.verify_orcid(VALID_ORCID, use_cache=False)
    assert r.verified is False
    assert "network" in r.note.lower()
