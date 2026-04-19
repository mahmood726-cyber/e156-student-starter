"""student new --template T0 copies files + creates workbook/<slug>/ with git init."""
from __future__ import annotations

import subprocess
from pathlib import Path
import pytest
from bin.scaffold import scaffold


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
