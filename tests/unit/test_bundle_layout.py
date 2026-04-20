"""Regression tests: the release-assembly Copy-Item list in release.yml must
cover every runtime-required directory. These tests fire on dev-machine
pytest and on CI before any zip is built."""
from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"

# Directories that MUST be in the shipped zip for the student CLI to work.
# When a new runtime-required directory is added at repo root, append it here.
REQUIRED_BUNDLE_DIRS = (
    "ai",          # friendly_error, ai_call
    "bin",         # student.py, wizard, scaffold, tui, help_me_pick
    "config",      # pins.json, sentinel/ rules + hook template
    "docs",        # HASH.txt + user docs
    "install",     # install.ps1 itself
    "memory",      # starter memory pack (student memory subcommand)
    "rules",       # user rule library
    "templates",   # T0 scaffold source
    "tests",       # smoke_test.py
    "tools",       # get_unstuck.py, sentinel_check.py, sentinel_safety_benchmark.py
)


def _assembled_dirs_from_workflow() -> set[str]:
    """Parse release.yml; return the set of directories listed in Copy-Item -Recurse <dir> $stage."""
    text = WORKFLOW.read_text(encoding="utf-8")
    # Only the build-and-test job's assembly block. It lives between the header
    # "Assemble bundle layout" and the next named step.
    block = re.search(
        r"Assemble bundle layout.*?(?=- name:)", text, re.DOTALL,
    )
    assert block, "Could not find bundle-assembly block in release.yml"
    dirs = set(re.findall(r"Copy-Item\s+-Recurse\s+(\S+)\s+\$stage", block.group(0)))
    return dirs


@pytest.mark.parametrize("dirname", REQUIRED_BUNDLE_DIRS)
def test_required_dir_exists_in_repo(dirname: str):
    assert (REPO_ROOT / dirname).is_dir(), \
        f"Repo is missing required top-level dir: {dirname}"


@pytest.mark.parametrize("dirname", REQUIRED_BUNDLE_DIRS)
def test_required_dir_copied_in_workflow(dirname: str):
    copied = _assembled_dirs_from_workflow()
    assert dirname in copied, (
        f"release.yml's Copy-Item list is missing `{dirname}`. "
        f"rc3 shipped without `memory/` because of this class of omission; "
        f"any new runtime-required top-level dir must be added to BOTH "
        f"REQUIRED_BUNDLE_DIRS in this test AND the workflow's Copy-Item block."
    )


def test_starter_memory_files_exist():
    """Memory dir must have the 6 seed files the `student memory` subcommand copies."""
    starter = REPO_ROOT / "memory" / "starter"
    assert starter.is_dir()
    md_files = list(starter.glob("starter_*.md"))
    assert len(md_files) >= 5, f"Expected >=5 seed memories, got {len(md_files)}"
    assert (starter / "MEMORY.md").exists()
