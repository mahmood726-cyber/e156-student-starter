"""CITATION.cff auto-emission in publish_pack."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

from tools.publish_pack import build_pack


def _mk_paper(wb: Path, slug: str) -> Path:
    p = wb / slug
    p.mkdir(parents=True)
    (p / "current_body.txt").write_text("body\n", encoding="utf-8")
    return p


def test_pack_includes_citation_cff(isolated_localappdata):
    wb = isolated_localappdata / "e156" / "workbook"
    _mk_paper(wb, "cff-slug")
    zp = build_pack("cff-slug")
    with zipfile.ZipFile(zp) as zf:
        assert "CITATION.cff" in zf.namelist()
        cff = zf.read("CITATION.cff").decode("utf-8")
    # CFF 1.2 required fields
    assert "cff-version: 1.2.0" in cff
    assert "title:" in cff
    assert "authors:" in cff
    assert "date-released:" in cff


def test_cff_pulls_authors_from_authorship_json(isolated_localappdata):
    wb = isolated_localappdata / "e156" / "workbook"
    paper = _mk_paper(wb, "author-slug")
    (paper / "authorship.json").write_text(json.dumps({
        "first_author":  {"full_name": "Priscilla Namusoke", "email": "p@mak.ac.ug",
                          "affiliation": "Makerere University", "orcid": None},
        "middle_author": {"full_name": "Mahmood Ahmad", "email": "m@nhs.net",
                          "affiliation": "Tahir Heart Institute",
                          "orcid": "https://orcid.org/0000-0001-2345-6789"},
        "last_author":   {"full_name": "Moses Ssali", "email": "ssali@mak.ac.ug",
                          "affiliation": "Makerere University", "orcid": None},
    }), encoding="utf-8")
    zp = build_pack("author-slug")
    with zipfile.ZipFile(zp) as zf:
        cff = zf.read("CITATION.cff").decode("utf-8")
    assert "Priscilla" in cff
    assert "Namusoke" in cff
    assert "Mahmood" in cff
    assert "Ahmad" in cff
    assert "Moses" in cff
    assert "https://orcid.org/0000-0001-2345-6789" in cff
    # affiliation preserved
    assert "Makerere University" in cff
    assert "Tahir Heart Institute" in cff


def test_cff_falls_back_when_no_authorship(isolated_localappdata):
    wb = isolated_localappdata / "e156" / "workbook"
    _mk_paper(wb, "noauthor")
    zp = build_pack("noauthor")
    with zipfile.ZipFile(zp) as zf:
        cff = zf.read("CITATION.cff").decode("utf-8")
    assert "Anonymous" in cff
    # Must still be structurally valid
    assert "cff-version:" in cff
