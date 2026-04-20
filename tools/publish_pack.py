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
    """Return a consent fingerprint: salted-hash of identity + flags + timestamp.

    The salt is per-laptop, generated once and stored in consent.json (never
    published). Without the salt, a global attacker with a student roster
    could brute-force SHA256(name|email) pairs in milliseconds. With the
    salt, brute-force requires the laptop's specific salt — which only the
    verifier (i.e. the student, verifying their own fingerprint to a
    supervisor) can read.
    """
    name = consent.get("name", "")
    email = consent.get("email", "")
    salt = consent.get("identity_salt", "")  # 64 hex chars; see `ensure_consent_has_salt`
    identity_sha = hashlib.sha256(
        (salt + "|" + name.lower() + "|" + email.lower()).encode("utf-8")
    ).hexdigest()
    return {
        "identity_sha256": identity_sha,
        "salt_present": bool(salt),
        "gemma_acknowledged_at": consent.get("gemma_acknowledged_at"),
        "cloud_enabled": consent.get("cloud_enabled", False),
        "gemma_license_acknowledged": consent.get("gemma_license_acknowledged", False),
    }


def ensure_consent_has_salt(consent_path: Path) -> str:
    """Idempotently add a per-laptop 32-byte salt to consent.json if missing.
    Returns the salt (hex). Called by publish flow and by the wizard."""
    import json as _json
    import secrets
    if not consent_path.is_file():
        return ""
    try:
        data = _json.loads(consent_path.read_text(encoding="utf-8"))
    except (_json.JSONDecodeError, OSError):
        return ""
    salt = data.get("identity_salt")
    if not salt or not isinstance(salt, str) or len(salt) < 32:
        salt = secrets.token_hex(32)
        data["identity_salt"] = salt
        try:
            consent_path.write_text(_json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass
    return salt


def _filter_audit_log(slug: str, e156_root: Path, workbook: Path) -> list[dict]:
    """Return audit entries plausibly associated with this paper.

    We DON'T store raw prompts in the audit log, so exact slug-matching is
    impossible. Instead we use the paper's last-modified window: audit entries
    whose timestamp falls within the paper-dir's mtime window (first touch to
    latest touch, +/- 1 hour slack) are included. Entries from before the
    paper existed or after it was last modified are excluded.

    This matches what a supervisor expects ('filtered' = for THIS paper) without
    requiring the student to have tagged calls at the time of use.
    """
    log = e156_root / "logs" / "ai_calls.jsonl"
    paper = workbook / slug
    if not log.is_file():
        return []
    # Determine paper's time window
    try:
        stat = paper.stat()
        earliest = min(
            (p.stat().st_mtime for p in paper.rglob("*") if p.is_file()),
            default=stat.st_mtime,
        )
        latest = max(
            (p.stat().st_mtime for p in paper.rglob("*") if p.is_file()),
            default=stat.st_mtime,
        )
    except OSError:
        earliest, latest = 0.0, 9_999_999_999.0
    # +/-1 hour slack
    lo = earliest - 3600
    hi = latest + 3600

    entries: list[dict] = []
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts_raw = e.get("ts") or ""
        try:
            # Parse ISO-8601 UTC timestamps with optional offset
            from datetime import datetime
            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00")).timestamp()
        except (ValueError, TypeError):
            # Undated entries land in the window — better over-inclusive than drop
            entries.append(e)
            continue
        if lo <= ts <= hi:
            entries.append(e)
    return entries


def _build_citation_cff(slug: str, bundle_version: str, authorship_data: dict | None) -> str:
    """Emit a CITATION.cff (1.2.0) YAML for the paper.

    GitHub auto-renders a "Cite this repository" button when CITATION.cff exists
    at the repo root. Zenodo auto-consumes it during DOI deposit. This gives
    every published student paper a machine-readable citation record at zero
    extra student effort. Spec: https://citation-file-format.github.io/
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _author_block(a: dict) -> list[str]:
        """Emit a CFF author block from an authorship.json author dict."""
        if not a:
            return []
        full = (a.get("full_name") or "").strip()
        parts = full.split(None, 1)
        given = parts[0] if parts else "Anonymous"
        family = parts[1] if len(parts) > 1 else "Anonymous"
        lines = [
            f"  - family-names: {family}",
            f"    given-names: {given}",
        ]
        if a.get("email"):
            lines.append(f"    email: {a['email']}")
        if a.get("affiliation"):
            lines.append(f"    affiliation: {_yaml_escape(a['affiliation'])}")
        orcid = a.get("orcid")
        if orcid:
            # Normalise to the full URI form CFF expects.
            if not orcid.startswith("https://"):
                orcid = f"https://orcid.org/{orcid}"
            lines.append(f"    orcid: {orcid}")
        return lines

    authors_lines: list[str] = []
    if authorship_data:
        for role in ("first_author", "middle_author", "last_author"):
            authors_lines.extend(_author_block(authorship_data.get(role, {})))
    if not authors_lines:
        authors_lines = [
            "  - family-names: Anonymous",
            "    given-names: Student",
        ]

    cff = [
        "cff-version: 1.2.0",
        "message: \"If you cite this paper, please use the metadata below.\"",
        f"title: \"E156 paper: {slug}\"",
        f"version: \"{bundle_version}\"",
        f"date-released: {now}",
        "type: article",
        "authors:",
    ]
    cff.extend(authors_lines)
    cff.append("keywords:")
    cff.append("  - e156")
    cff.append("  - systematic-review")
    return "\n".join(cff) + "\n"


def _yaml_escape(s: str) -> str:
    """Minimal YAML-safe string escaping for single-line values."""
    if any(ch in s for ch in ":#&*!?|>'\"%@`"):
        return json.dumps(s, ensure_ascii=False)
    return s


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

        # 1. Paper files (includes checklists/ subdirectory by inclusion)
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

        # 4. Audit log filtered (entries within paper's edit window)
        audit_entries = _filter_audit_log(slug, e156_root, workbook)
        (stage / "ai_calls_filtered.jsonl").write_text(
            "\n".join(json.dumps(e) for e in audit_entries) + ("\n" if audit_entries else ""),
            encoding="utf-8",
        )

        # 5. Consent fingerprint (NEVER raw name/email). Salted per-laptop.
        consent_src = e156_root / ".consent.json"
        if consent_src.is_file():
            try:
                # Ensure a salt exists (idempotent; writes once per laptop)
                ensure_consent_has_salt(consent_src)
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

        # 7a.5a. CITATION.cff (GitHub + Zenodo auto-consume)
        # Read the paper's authorship.json if present, to name authors properly.
        authorship_src = paper_dir / "authorship.json"
        authorship_data = None
        if authorship_src.is_file():
            try:
                authorship_data = json.loads(authorship_src.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                authorship_data = None
        (stage / "CITATION.cff").write_text(
            _build_citation_cff(slug, _bundle_version(), authorship_data),
            encoding="utf-8",
        )

        # 7a.5. Bypass log (review H-P0-1: supervisor must see these)
        bypass_log_src = Path(lad) / "e156" / "logs" / "bypass.log"
        bypass_count = 0
        if bypass_log_src.is_file():
            shutil.copy2(bypass_log_src, stage / "bypass.log")
            try:
                bypass_count = sum(
                    1 for line in bypass_log_src.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                )
            except OSError:
                pass

        # 7b. Manifest (SHA256 of every file)
        manifest = {
            "slug": slug,
            "generated_at_utc": ts,
            "bundle_version": _bundle_version(),
            "bypass_count": bypass_count,  # 0 = clean push history
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
