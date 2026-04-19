"""Shared pytest fixtures for Plan A."""
from __future__ import annotations

import os
from pathlib import Path
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def isolated_localappdata(tmp_path, monkeypatch):
    """Point %LOCALAPPDATA% at a tmp dir so tests don't touch real state."""
    fake = tmp_path / "AppData" / "Local"
    fake.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LOCALAPPDATA", str(fake))
    return fake
