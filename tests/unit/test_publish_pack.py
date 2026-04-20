"""student publish — reproducibility pack for one paper."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from tools.publish_pack import build_pack, _workbook_root


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDENT_PY = REPO_ROOT / "bin" / "student.py"


def _make_paper(workbook: Path, slug: str) -> Path:
    paper = workbook / slug
    paper.mkdir(parents=True)
    (paper / "current_body.txt").write_text("body text\n", encoding="utf-8")
    (paper / "metadata.yaml").write_text("slug: " + slug + "\n", encoding="utf-8")
    return paper


def test_build_pack_produces_zip_with_expected_files(isolated_localappdata):
    wb = isolated_localappdata / "e156" / "workbook"
    wb.mkdir(parents=True)
    _make_paper(wb, "my-first")
    zp = build_pack("my-first")
    assert zp.is_file()
    with zipfile.ZipFile(zp) as zf:
        names = set(zf.namelist())
    assert "paper/current_body.txt" in names
    assert "paper/metadata.yaml" in names
    assert "manifest.json" in names
    assert "README.md" in names
    assert "pins.json" in names
    assert "ai_calls_filtered.jsonl" in names
    assert "ro-crate-metadata.json" in names  # FAIR metadata


def test_ro_crate_metadata_is_valid_json_ld(isolated_localappdata):
    wb = isolated_localappdata / "e156" / "workbook"
    wb.mkdir(parents=True)
    _make_paper(wb, "fair-slug")
    zp = build_pack("fair-slug")
    with zipfile.ZipFile(zp) as zf:
        crate = json.loads(zf.read("ro-crate-metadata.json"))
    assert crate["@context"].startswith("https://w3id.org/ro/crate/")
    assert any(
        node.get("@id") == "./" and node.get("@type") == "Dataset"
        for node in crate["@graph"]
    )


def test_manifest_sha256_matches_actual_file_contents(isolated_localappdata):
    wb = isolated_localappdata / "e156" / "workbook"
    wb.mkdir(parents=True)
    _make_paper(wb, "slug-one")
    zp = build_pack("slug-one")
    with zipfile.ZipFile(zp) as zf:
        manifest = json.loads(zf.read("manifest.json"))
        for rel, expected in manifest["files"].items():
            if rel == "manifest.json":
                continue
            actual = hashlib.sha256(zf.read(rel)).hexdigest()
            assert actual == expected, f"hash mismatch on {rel}"


def test_consent_fingerprint_does_NOT_leak_raw_pii(isolated_localappdata):
    wb = isolated_localappdata / "e156" / "workbook"
    wb.mkdir(parents=True)
    _make_paper(wb, "priv")
    consent = isolated_localappdata / "e156" / ".consent.json"
    consent.write_text(json.dumps({
        "name": "Priscilla Namusoke",
        "email": "p.namusoke@mak.ac.ug",
        "gemma_acknowledged_at": "2026-04-19T10:00:00+00:00",
        "cloud_enabled": False,
        "gemma_license_acknowledged": True,
    }), encoding="utf-8")
    zp = build_pack("priv")
    with zipfile.ZipFile(zp) as zf:
        fp = json.loads(zf.read("consent_fingerprint.json"))
        full = "\n".join(zf.read(n).decode("utf-8", errors="replace") for n in zf.namelist())
    assert "Priscilla" not in full
    assert "Namusoke" not in full
    assert "p.namusoke" not in full
    assert "mak.ac.ug" not in full
    assert len(fp["identity_sha256"]) == 64
    assert fp["cloud_enabled"] is False


def test_missing_paper_raises(isolated_localappdata):
    wb = isolated_localappdata / "e156" / "workbook"
    wb.mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        build_pack("nonexistent")


def test_student_publish_cli_end_to_end(isolated_localappdata):
    import os
    wb = isolated_localappdata / "e156" / "workbook"
    wb.mkdir(parents=True)
    _make_paper(wb, "cli-slug")
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(isolated_localappdata)
    r = subprocess.run(
        [sys.executable, str(STUDENT_PY), "publish", "--slug", "cli-slug"],
        capture_output=True, text=True, timeout=30, env=env,
    )
    assert r.returncode == 0, r.stderr
    assert "Published:" in r.stdout
    # The published zip lives in the workbook
    zips = list(wb.glob("cli-slug-publish-*.zip"))
    assert len(zips) == 1


def test_student_publish_all_finds_every_paper(isolated_localappdata):
    import os
    wb = isolated_localappdata / "e156" / "workbook"
    wb.mkdir(parents=True)
    _make_paper(wb, "paper-a")
    _make_paper(wb, "paper-b")
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(isolated_localappdata)
    r = subprocess.run(
        [sys.executable, str(STUDENT_PY), "publish", "--all"],
        capture_output=True, text=True, timeout=30, env=env,
    )
    assert r.returncode == 0
    assert "paper-a" in r.stdout
    assert "paper-b" in r.stdout


def test_publish_subcommand_in_help():
    r = subprocess.run(
        [sys.executable, str(STUDENT_PY), "help"],
        capture_output=True, text=True, timeout=10,
    )
    assert "publish" in r.stdout
