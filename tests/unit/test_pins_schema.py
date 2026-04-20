"""Pins.json structure validates against schema."""
from __future__ import annotations

import json
from pathlib import Path
import pytest

jsonschema = pytest.importorskip("jsonschema")


def test_pins_conforms_to_schema(repo_root):
    schema = json.loads((repo_root / "config" / "pins.schema.json").read_text())
    pins = json.loads((repo_root / "config" / "pins.json").read_text())
    jsonschema.validate(pins, schema)


def test_pins_has_all_required_sections(repo_root):
    pins = json.loads((repo_root / "config" / "pins.json").read_text())
    for key in ("ollama", "models", "data_lakes", "python_embed", "bundle_release"):
        assert key in pins, f"missing section: {key}"


def test_all_tiers_have_a_model_digest(repo_root):
    pins = json.loads((repo_root / "config" / "pins.json").read_text())
    for model_name in ("gemma2:2b", "gemma2:9b",
                       "qwen2.5-coder:1.5b", "qwen2.5-coder:7b"):
        assert model_name in pins["models"], f"missing: {model_name}"
        assert pins["models"][model_name]["digest"].startswith("sha256:")
