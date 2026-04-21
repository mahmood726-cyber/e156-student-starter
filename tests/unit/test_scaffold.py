"""student new --template T0 copies files + creates workbook/<slug>/ with git init."""
from __future__ import annotations

import subprocess
from pathlib import Path
import pytest
from bin.scaffold import scaffold, title_to_slug


def test_t0_copies_files(tmp_path, repo_root):
    workbook = tmp_path / "workbook"
    workbook.mkdir()
    scaffold("T0", slug="my-first-paper", workbook=workbook, repo_root=repo_root)
    paper = workbook / "my-first-paper"
    assert (paper / "README.md").exists()
    assert (paper / "e156_body.md").exists()
    assert (paper / "preanalysis.md").exists()


def test_t1_through_t5_stubs_say_coming_in_plan_E(tmp_path, repo_root):
    workbook = tmp_path / "workbook"
    workbook.mkdir()
    with pytest.raises(NotImplementedError) as exc:
        scaffold("T1", slug="sglt2-hfpef", workbook=workbook, repo_root=repo_root)
    assert "Plan E" in str(exc.value)


def test_scaffold_rejects_unknown_template(tmp_path, repo_root):
    workbook = tmp_path / "workbook"
    workbook.mkdir()
    with pytest.raises(ValueError):
        scaffold("T99", slug="x", workbook=workbook, repo_root=repo_root)


def test_slug_validation(tmp_path, repo_root):
    workbook = tmp_path / "workbook"
    workbook.mkdir()
    with pytest.raises(ValueError):
        scaffold("T0", slug="has spaces and CAPS", workbook=workbook, repo_root=repo_root)


# ---------- title_to_slug ------------------------------------------------

def test_title_to_slug_simple():
    assert title_to_slug("My First Paper") == "my-first-paper"


def test_title_to_slug_punctuation_and_case():
    # Mixed case, punctuation, special chars — all collapse to hyphens.
    assert title_to_slug("Sacubitril/Valsartan in HFrEF!") == "sacubitril-valsartan-in-hfref"


def test_title_to_slug_strips_diacritics():
    assert title_to_slug("Café résumé naïve") == "cafe-resume-naive"


def test_title_to_slug_truncates_to_64():
    long = "x" * 200
    assert len(title_to_slug(long)) == 64


def test_title_to_slug_empty_falls_back_to_timestamp():
    s = title_to_slug("")
    assert s.startswith("paper-")
    # paper-YYYYMMDD-HHMMSS = 6 + 8 + 1 + 6 = 21 chars
    assert len(s) == 21


def test_title_to_slug_single_char_falls_back_to_timestamp():
    # One-char titles are filesystem-legal but fail SLUG_RE, so we fall back.
    s = title_to_slug("a")
    assert s.startswith("paper-")


def test_title_to_slug_leading_digit_falls_back_to_timestamp():
    # SLUG_RE requires a leading letter; a title like "2024 RCT" slugifies to
    # "2024-rct" which would fail the regex. Fall back rather than hand back
    # something the caller can't use.
    s = title_to_slug("2024 RCT")
    assert s.startswith("paper-")


def test_title_to_slug_result_is_accepted_by_scaffold(tmp_path, repo_root):
    """The whole point: slugs produced by title_to_slug are valid for scaffold()."""
    workbook = tmp_path / "workbook"
    workbook.mkdir()
    slug = title_to_slug("Sacubitril/Valsartan in HFrEF!")
    target = scaffold("T0", slug=slug, workbook=workbook, repo_root=repo_root)
    assert target.name == "sacubitril-valsartan-in-hfref"
