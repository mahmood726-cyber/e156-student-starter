"""Citation verifier — regex extraction + PubMed lookup with cache + offline fallback."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import citation_verify as cv


def test_extract_parens_with_et_al():
    cits = cv.extract_citations("We replicate (Neuenschwander et al. 2010) findings.")
    assert len(cits) == 1
    assert cits[0].first_author == "Neuenschwander"
    assert cits[0].year == "2010"


def test_extract_parens_with_and():
    cits = cv.extract_citations("Following (Sterne and Page 2019).")
    assert len(cits) == 1
    assert cits[0].first_author == "Sterne"
    assert cits[0].year == "2019"


def test_extract_author_year_with_parens_after():
    cits = cv.extract_citations("Page et al. (2021) published PRISMA 2020.")
    assert any(c.first_author == "Page" and c.year == "2021" for c in cits)


def test_extract_inline_comma():
    cits = cv.extract_citations("Supported by Smith et al., 2015 in their meta-analysis.")
    assert any(c.first_author == "Smith" and c.year == "2015" for c in cits)


def test_extract_dedupes_across_patterns():
    text = "Page et al. (2021). Also (Page et al. 2021). Also Page et al., 2021."
    cits = cv.extract_citations(text)
    assert len(cits) == 1


def test_extract_ignores_table_figure_noise():
    # "(Table 2)" or "(Figure 1)" should not be treated as a citation
    cits = cv.extract_citations("See (Table 2) and (Figure 1) for details.")
    assert cits == []


def test_extract_ignores_single_year_mentions():
    cits = cv.extract_citations("Enrolled between 2015 and 2020.")
    assert cits == []


def test_cache_hit_avoids_network(isolated_localappdata, monkeypatch):
    cit = cv.Citation("Neuenschwander 2010", "Neuenschwander", "2010")
    # Seed cache
    cv._cache_put(cit.cache_key(), {
        "verified": True, "pmid": "20054810", "title": "MAP priors", "note": "seeded",
    })
    # Now patch urlopen to raise — proves we never hit network
    def _boom(*a, **kw):
        raise AssertionError("network call attempted despite cache hit")
    monkeypatch.setattr(cv.urllib.request, "urlopen", _boom)
    v = cv.verify_pubmed(cit)
    assert v.verified is True
    assert v.pmid == "20054810"
    assert "[cache]" in v.note


def test_network_error_returns_unverified_not_raises(isolated_localappdata, monkeypatch):
    class _FakeURLError(Exception): pass
    monkeypatch.setattr(cv.urllib.error, "URLError", _FakeURLError)
    def _boom(*a, **kw):
        raise _FakeURLError("simulated DNS failure")
    monkeypatch.setattr(cv.urllib.request, "urlopen", _boom)
    cit = cv.Citation("Xyzzy 2099", "Xyzzy", "2099")
    v = cv.verify_pubmed(cit, use_cache=False)
    assert v.verified is False
    assert "network" in v.note.lower()


def test_no_idlist_marks_unverified_hallucination(isolated_localappdata, monkeypatch):
    import io
    class _Resp:
        def __init__(self, body): self._body = body.encode("utf-8")
        def read(self): return self._body
        def __enter__(self): return self
        def __exit__(self, *a): pass
    def _fake_urlopen(url, timeout=10.0):
        return _Resp(json.dumps({"esearchresult": {"idlist": []}}))
    monkeypatch.setattr(cv.urllib.request, "urlopen", _fake_urlopen)
    cit = cv.Citation("Smith 2099", "Smith", "2099")
    v = cv.verify_pubmed(cit, use_cache=False)
    assert v.verified is False
    assert "no PubMed match" in v.note


def test_match_records_pmid_and_caches(isolated_localappdata, monkeypatch):
    class _Resp:
        def __init__(self, body): self._body = body.encode("utf-8")
        def read(self): return self._body
        def __enter__(self): return self
        def __exit__(self, *a): pass
    def _fake_urlopen(url, timeout=10.0):
        return _Resp(json.dumps({"esearchresult": {"idlist": ["33782057"]}}))
    monkeypatch.setattr(cv.urllib.request, "urlopen", _fake_urlopen)
    cit = cv.Citation("Page 2021", "Page", "2021")
    v = cv.verify_pubmed(cit)
    assert v.verified is True
    assert v.pmid == "33782057"
    # Second call must hit cache — patch urlopen to explode
    def _boom(*a, **kw):
        raise AssertionError("second call should hit cache")
    monkeypatch.setattr(cv.urllib.request, "urlopen", _boom)
    v2 = cv.verify_pubmed(cit)
    assert v2.verified is True


def test_format_report_summary():
    cits = [cv.Citation("Page 2021", "Page", "2021"),
            cv.Citation("Smith 2099", "Smith", "2099")]
    vs = [
        cv.Verification(citation=cits[0], verified=True, pmid="33782057", note="PubMed match"),
        cv.Verification(citation=cits[1], verified=False, note="no PubMed match"),
    ]
    out = cv.format_report(vs)
    assert "1/2 verified" in out
    assert "OK" in out
    assert "FAIL" in out


def test_student_verify_citations_cli_hallucination_exits_1(isolated_localappdata, tmp_path, monkeypatch):
    import subprocess, sys, os
    # Seed cache with one hallucinated citation so CLI doesn't hit network
    cit_bad = cv.Citation("Xyzzy 2099", "Xyzzy", "2099")
    cv._cache_put(cit_bad.cache_key(), {"verified": False, "pmid": None, "note": "no PubMed match"})

    body = tmp_path / "body.txt"
    body.write_text("As shown in (Xyzzy et al. 2099) this is fabricated.", encoding="utf-8")
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(isolated_localappdata)
    REPO = Path(__file__).resolve().parents[2]
    STUDENT_PY = REPO / "bin" / "student.py"
    r = subprocess.run(
        [sys.executable, str(STUDENT_PY), "verify-citations", "--path", str(body)],
        capture_output=True, text=True, timeout=15, env=env,
    )
    assert r.returncode == 1
    assert "FAIL" in r.stdout
    assert "Xyzzy" in r.stdout


def test_verify_citations_subcommand_in_help():
    import subprocess, sys
    REPO = Path(__file__).resolve().parents[2]
    r = subprocess.run(
        [sys.executable, str(REPO / "bin" / "student.py"), "help"],
        capture_output=True, text=True, timeout=10,
    )
    assert "verify-citations" in r.stdout
