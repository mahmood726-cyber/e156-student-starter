"""Living-paper drift detector (portfolio pattern #4 from Tricuspid TEER).

Snapshot a paper's numerical + metadata state on submission; on subsequent
validate/publish runs, diff the current state against the last snapshot.
Students see exactly what changed between submission and resubmission —
no more "I forgot I renamed the outcome before submitting v2".

Snapshot store: %LOCALAPPDATA%\\e156\\workbook\\<slug>\\.submission_snapshots\\
  <timestamp>.json  (append-only; never delete)

Usage:
    python tools/drift_detector.py snapshot --slug my-paper
    python tools/drift_detector.py check    --slug my-paper
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from tools.project_paths import paper_dir, submission_snapshots_dir


@dataclass
class DriftReport:
    slug: str
    last_snapshot_ts: str | None
    changes: list[tuple[str, object, object]]  # (field, old, new)
    body_similarity_pct: float | None

    @property
    def drifted(self) -> bool:
        return bool(self.changes) or (
            self.body_similarity_pct is not None and self.body_similarity_pct < 90.0
        )


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _body_similarity(a: str, b: str) -> float:
    """Return % overlap of word multisets. Typo-tolerant but catches rewrites."""
    from collections import Counter
    wa, wb = Counter(a.lower().split()), Counter(b.lower().split())
    if not wa and not wb:
        return 100.0
    common = sum((wa & wb).values())
    total = max(sum(wa.values()), sum(wb.values()))
    return 100.0 * common / total if total else 0.0


def _current_fingerprint(slug: str) -> dict:
    """Collect the fields we track for drift."""
    pd = paper_dir(slug)
    if not pd.is_dir():
        raise FileNotFoundError(f"paper not found: {pd}")
    body_path = pd / "current_body.txt"
    meta_path = pd / "metadata.yaml"
    fp: dict = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "slug": slug,
        "body_sha256": _file_sha(body_path) if body_path.is_file() else None,
        "body_text": body_path.read_text(encoding="utf-8") if body_path.is_file() else "",
    }
    if meta_path.is_file():
        fp["metadata_sha256"] = _file_sha(meta_path)
        fp["metadata_raw"] = meta_path.read_text(encoding="utf-8")
    # Attach the baseline record if one exists — drift in pooled_estimate is the headline.
    from tools.baseline import BaselineStore  # noqa: WPS433
    store = BaselineStore()
    bl = store.get(slug)
    if bl is not None:
        fp["baseline"] = {
            "pooled_estimate": bl.pooled_estimate,
            "ci_lower": bl.ci_lower, "ci_upper": bl.ci_upper,
            "k": bl.k, "i2": bl.i2, "tau2": bl.tau2, "q": bl.q,
        }
    return fp


def snapshot(slug: str) -> Path:
    """Write a new snapshot for <slug>. Returns the snapshot path."""
    fp = _current_fingerprint(slug)
    snaps = submission_snapshots_dir(slug)
    snaps.mkdir(parents=True, exist_ok=True)
    path = snaps / f"{fp['timestamp_utc'].replace(':', '')}.json"
    path.write_text(json.dumps(fp, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _latest_snapshot(slug: str) -> dict | None:
    snaps = submission_snapshots_dir(slug)
    if not snaps.is_dir():
        return None
    files = sorted(snaps.glob("*.json"))
    if not files:
        return None
    return json.loads(files[-1].read_text(encoding="utf-8"))


def _diff_fields(prev: dict, curr: dict) -> list[tuple[str, object, object]]:
    """Compare the fields we care about between two fingerprints."""
    changes: list[tuple[str, object, object]] = []
    for key in ("body_sha256", "metadata_sha256"):
        if prev.get(key) != curr.get(key):
            changes.append((key, prev.get(key), curr.get(key)))
    prev_bl = prev.get("baseline") or {}
    curr_bl = curr.get("baseline") or {}
    for key in ("pooled_estimate", "ci_lower", "ci_upper", "k"):
        if prev_bl.get(key) != curr_bl.get(key):
            changes.append((f"baseline.{key}", prev_bl.get(key), curr_bl.get(key)))
    return changes


def check(slug: str) -> DriftReport:
    prev = _latest_snapshot(slug)
    curr = _current_fingerprint(slug)
    if prev is None:
        return DriftReport(slug, None, [], None)
    changes = _diff_fields(prev, curr)
    sim = _body_similarity(prev.get("body_text", ""), curr.get("body_text", "")) \
        if prev.get("body_text") and curr.get("body_text") else None
    return DriftReport(slug, prev["timestamp_utc"], changes, sim)


def format_report(r: DriftReport) -> str:
    if r.last_snapshot_ts is None:
        return (f"[drift] no prior snapshot for `{r.slug}`. "
                f"Run: student drift snapshot --slug {r.slug}")
    if not r.drifted:
        extra = f" Body similarity {r.body_similarity_pct:.1f}%" if r.body_similarity_pct is not None else ""
        return f"[drift] OK: no material drift since {r.last_snapshot_ts}.{extra}"
    lines = [f"[drift] DRIFT detected since {r.last_snapshot_ts}:"]
    for field, old, new in r.changes:
        lines.append(f"  ! {field}: {old} -> {new}")
    if r.body_similarity_pct is not None:
        lines.append(f"  body similarity: {r.body_similarity_pct:.1f}%")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    snap_p = sub.add_parser("snapshot", help="Record a snapshot of the current paper state.")
    snap_p.add_argument("--slug", required=True)
    chk_p = sub.add_parser("check", help="Compare current state against latest snapshot.")
    chk_p.add_argument("--slug", required=True)
    args = ap.parse_args(argv)

    if args.cmd == "snapshot":
        try:
            path = snapshot(args.slug)
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(f"Snapshot: {path}")
        return 0

    if args.cmd == "check":
        try:
            report = check(args.slug)
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(format_report(report))
        return 1 if report.drifted else 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
