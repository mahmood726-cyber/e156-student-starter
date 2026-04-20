"""Review H-P0-1: bypass.log must land in the publish pack with a count."""
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


def test_publish_pack_includes_bypass_log_when_present(isolated_localappdata):
    wb = isolated_localappdata / "e156" / "workbook"
    wb.mkdir(parents=True)
    _mk_paper(wb, "bypass-slug")

    # Create a bypass log at the new location (outside .git).
    logs = isolated_localappdata / "e156" / "logs"
    logs.mkdir(parents=True)
    (logs / "bypass.log").write_text(
        "2026-04-20T10:00:00Z bypass repo=local head=abc123\n"
        "2026-04-20T11:00:00Z bypass repo=local head=def456\n",
        encoding="utf-8",
    )

    zp = build_pack("bypass-slug")
    with zipfile.ZipFile(zp) as zf:
        names = set(zf.namelist())
        assert "bypass.log" in names
        manifest = json.loads(zf.read("manifest.json"))
        assert manifest["bypass_count"] == 2


def test_publish_pack_bypass_count_zero_when_clean(isolated_localappdata):
    wb = isolated_localappdata / "e156" / "workbook"
    wb.mkdir(parents=True)
    _mk_paper(wb, "clean-slug")
    zp = build_pack("clean-slug")
    with zipfile.ZipFile(zp) as zf:
        manifest = json.loads(zf.read("manifest.json"))
        assert manifest["bypass_count"] == 0
        assert "bypass.log" not in zf.namelist()
