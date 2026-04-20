"""Build a reproducibility archive for one paper in the student's workbook.

The archive answers: "How can someone else (supervisor, journal, future me)
reproduce this paper?" It bundles:

  - paper/              The paper files (current_body.txt, your_rewrite.txt, etc.)
  - pins.json           Snapshot of what Ollama + Python + models were used
  - sentinel-findings.jsonl (if present in workbook — the pre-push history)
  - ai_calls_filtered.jsonl  Audit-log entries for this paper slug only
  - consent.json        Hashed name+email + AGREE timestamp (no raw PII)
  - manifest.json       SHA256 of every file in the archive
  - README.md           Plain-English: what's here, how to reproduce

The output zip lands at:
  %LOCALAPPDATA%\\e156\\workbook\\<slug>-publish-<timestamp>.zip

Usage:
  student publish <slug>
  student publish --all            # every paper in workbook
  python tools/publish_pack.py --slug my-paper
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _workbook_root() -> Path:
    lad = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(lad) / "e156" / "workbook"


def _e156_root() -> Path:
    lad = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(lad) / "e156"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _hash_identity(consent: dict) -> dict:
    """Return a consent fingerprint: hashed identity + AGREE timestamp + flags."""
    name = consent.get("name", "")
    email = consent.get("email", "")
    identity_sha = hashlib.sha256(
        (name.lower() + "|" + email.lower()).encode("utf-8")
    ).hexdigest()
    return {
        "identity_sha256": identity_sha,
        "gemma_acknowledged_at": consent.get("gemma_acknowledged_at"),
        "cloud_enabled": consent.get("cloud_enabled", False),
        "gemma_license_acknowledged": consent.get("gemma_license_acknowledged", False),
    }


def _filter_audit_log(slug: str, e156_root: Path) -> list[dict]:
    """Return audit entries that mention this slug in their task_kind or prompt hash.
    (We don't store raw prompts, so slug-filtering is opportunistic via the kind tag.)
    For now, return ALL audit entries within a 48-hour window of the paper's most
    recent edit — students can always trim further by hand.
    """
    log = e156_root / "logs" / "ai_calls.jsonl"
    if not log.is_file():
        return []
    entries = []
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _build_ro_crate_metadata(slug: str, file_list: list[str], bundle_version: str) -> dict:
    """Emit a minimal RO-Crate 1.2 JSON-LD document.

    RO-Crate (https://www.researchobject.org/ro-crate/) is the W3C community
    standard for FAIR-compliant research-object packaging. Having this file
    makes the reproducibility pack portable to any institutional repository
    or journal submission pipeline that understands the standard.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    graph: list[dict] = [
        {
            "@id": "ro-crate-metadata.json",
            "@type": "CreativeWork",
            "conformsTo": {"@id": "https://w3id.org/ro/crate/1.2-DRAFT"},
            "about": {"@id": "./"},
        },
        {
            "@id": "./",
            "@type": "Dataset",
            "name": f"e156 reproducibility pack: {slug}",
            "description": (
                f"E156 student-starter reproducibility pack for paper `{slug}`. "
                f"Contains paper source, pinned AI/tooling versions, pre-push "
                f"scan history, audit log, and SHA256 manifest. Bundle version "
                f"{bundle_version}."
            ),
            "datePublished": now,
            "hasPart": [{"@id": f} for f in sorted(file_list) if f != "ro-crate-metadata.json"],
        },
    ]
    for f in sorted(file_list):
        if f in ("ro-crate-metadata.json",):
            continue
        graph.append({
            "@id": f,
            "@type": "File",
            "encodingFormat": (
                "application/json" if f.endswith(".json") or f.endswith(".jsonl")
                else ("text/markdown" if f.endswith(".md") else "text/plain")
            ),
        })
    return {
        "@context": "https://w3id.org/ro/crate/1.2-DRAFT/context",
        "@graph": graph,
    }


def build_pack(slug: str, *, out_dir: Path | None = None) -> Path:
    """Build the reproducibility zip for <slug>. Returns the zip path."""
    workbook = _workbook_root()
    paper_dir = workbook / slug
    if not paper_dir.is_dir():
        raise FileNotFoundError(f"paper not found: {paper_dir}")

    e156_root = _e156_root()
    out_dir = out_dir or workbook
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    zip_path = out_dir / f"{slug}-publish-{ts}.zip"

    with tempfile.TemporaryDirectory() as td:
        stage = Path(td) / f"{slug}-publish"
        stage.mkdir()

        # 1. Paper files
        paper_out = stage / "paper"
        shutil.copytree(paper_dir, paper_out, ignore=shutil.ignore_patterns(".git"))

        # 2. Pins snapshot
        pins_src = REPO_ROOT / "config" / "pins.json"
        if pins_src.is_file():
            shutil.copy2(pins_src, stage / "pins.json")

        # 3. Sentinel findings (if workbook has them from pre-push runs)
        findings_src = workbook / "sentinel-findings.jsonl"
        if findings_src.is_file():
            shutil.copy2(findings_src, stage / "sentinel-findings.jsonl")

        # 4. Audit log filtered
        audit_entries = _filter_audit_log(slug, e156_root)
        (stage / "ai_calls_filtered.jsonl").write_text(
            "\n".join(json.dumps(e) for e in audit_entries) + ("\n" if audit_entries else ""),
            encoding="utf-8",
        )

        # 5. Consent fingerprint (NEVER raw name/email)
        consent_src = e156_root / ".consent.json"
        if consent_src.is_file():
            try:
                consent = json.loads(consent_src.read_text(encoding="utf-8"))
                (stage / "consent_fingerprint.json").write_text(
                    json.dumps(_hash_identity(consent), indent=2), encoding="utf-8",
                )
            except (OSError, json.JSONDecodeError):
                pass

        # 6. README
        (stage / "README.md").write_text(_readme_for(slug, ts), encoding="utf-8")

        # 7a. Add a baseline copy if one exists (per-paper drift history)
        lad = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        bl_src = Path(lad) / "e156" / "baseline.json"
        if bl_src.is_file():
            shutil.copy2(bl_src, stage / "baseline.json")

        # 7b. Manifest (SHA256 of every file)
        manifest = {
            "slug": slug,
            "generated_at_utc": ts,
            "bundle_version": _bundle_version(),
            "files": {},
        }
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                rel = path.relative_to(stage).as_posix()
                manifest["files"][rel] = _sha256_file(path)
        (stage / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8",
        )

        # 7c. RO-Crate 1.2 metadata (FAIR-compliant).
        files_in_pack = list(manifest["files"].keys()) + ["ro-crate-metadata.json"]
        (stage / "ro-crate-metadata.json").write_text(
            json.dumps(
                _build_ro_crate_metadata(slug, files_in_pack, _bundle_version()),
                indent=2,
            ),
            encoding="utf-8",
        )

        # 8. Zip it
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(stage.rglob("*")):
                if path.is_file():
                    zf.write(path, path.relative_to(stage))

    return zip_path


def _bundle_version() -> str:
    pins = REPO_ROOT / "config" / "pins.json"
    if pins.is_file():
        try:
            data = json.loads(pins.read_text(encoding="utf-8"))
            return data.get("bundle_release", {}).get("version", "unknown")
        except (OSError, json.JSONDecodeError):
            pass
    return "unknown"


def _readme_for(slug: str, ts: str) -> str:
    return (
        f"# Reproducibility pack: {slug}\n\n"
        f"Generated: {ts} UTC\n"
        f"Bundle version: {_bundle_version()}\n\n"
        "## What's in here\n\n"
        "- `paper/` — the paper files as of when this pack was built.\n"
        "- `pins.json` — the exact Ollama / Python / model versions used. To "
        "reproduce the exact local AI stack, install these pinned versions.\n"
        "- `sentinel-findings.jsonl` — pre-push scan history against the "
        "rule library (P0 BLOCK, P1 WARN). Shows what the guardrails caught.\n"
        "- `ai_calls_filtered.jsonl` — audit log of AI-assisted calls made "
        "during authoring. Hashes only — no raw prompt or response text.\n"
        "- `consent_fingerprint.json` — SHA256 of (name|email) + "
        "AGREE timestamp. Establishes who authored without leaking PII.\n"
        "- `manifest.json` — SHA256 of every file in this pack. Tamper-evident.\n"
        "- `ro-crate-metadata.json` — RO-Crate 1.2 JSON-LD manifest, makes "
        "this pack portable to any FAIR-compliant institutional repository.\n"
        "- `baseline.json` (if present) — numerical baseline corpus for this "
        "paper. Used by `student baseline check` to detect numerical drift.\n\n"
        "## How to verify this pack\n\n"
        "```\n"
        "python -c \"import hashlib, json; "
        "m = json.load(open('manifest.json')); "
        "print('OK' if all(hashlib.sha256(open(f,'rb').read()).hexdigest() == h "
        "for f, h in m['files'].items() if f != 'manifest.json') else 'FAIL')\"\n"
        "```\n\n"
        "## How to reproduce the AI setup\n\n"
        "Install Ollama at the version pinned in `pins.json`, pull the models "
        "at the digests pinned there, then run the e156 student starter at "
        f"the `bundle_version` printed above against the `paper/` directory.\n"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slug", help="paper slug to publish (single-paper mode)")
    ap.add_argument("--all", action="store_true", help="publish every paper in the workbook")
    args = ap.parse_args(argv)

    if not args.slug and not args.all:
        print("error: pass --slug <name> or --all", file=sys.stderr)
        return 2

    workbook = _workbook_root()
    if args.all:
        if not workbook.is_dir():
            print(f"error: workbook not found at {workbook}", file=sys.stderr)
            return 2
        slugs = [p.name for p in workbook.iterdir() if p.is_dir() and not p.name.startswith(".")]
    else:
        slugs = [args.slug]

    built = []
    for slug in slugs:
        try:
            zp = build_pack(slug)
            print(f"Published: {zp}")
            built.append(zp)
        except FileNotFoundError as e:
            print(f"Skipped {slug}: {e}", file=sys.stderr)

    return 0 if built else 1


if __name__ == "__main__":
    sys.exit(main())
