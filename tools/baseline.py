"""Numerical baseline store — record once, diff on revision.

Lock a paper's shipped numbers (pooled estimate, CI, SE, I², tau², Q, k)
into a JSON corpus. On subsequent revisions, diff the new report against
the stored baseline. Any drift beyond tolerance (default 1e-6) is a
`student baseline check` failure — suitable for a pre-push hook.

Answers the reviewer question: "have your numbers changed since last
submission?" deterministically, without needing to eyeball a PDF diff.

Vendored (and pared down) from C:\\MissionCritical\\mission_critical\\baseline.
Kept pure-stdlib so offline students never need `pip install`.

Usage:
  python tools/baseline.py record my-paper --from report.json
  python tools/baseline.py record my-paper --value pooled_estimate=0.75 --value ci_lower=0.62
  python tools/baseline.py check my-paper --from report.json
  python tools/baseline.py show my-paper
  python tools/baseline.py list
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_TOLERANCE = 1e-6
KNOWN_NUMERIC_FIELDS = (
    "pooled_estimate", "ci_lower", "ci_upper", "se", "i2", "tau2", "q", "k",
)


def _default_store_path() -> Path:
    lad = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(lad) / "e156" / "baseline.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_claim_id() -> str:
    return "cl_" + uuid.uuid4().hex[:8]


@dataclass
class BaselineRecord:
    paper_id: str
    recorded_at: str
    commit_sha: str | None
    pooled_estimate: float | None = None
    ci_lower: float | None = None
    ci_upper: float | None = None
    se: float | None = None
    i2: float | None = None
    tau2: float | None = None
    q: float | None = None
    k: int | None = None
    extra: dict[str, float] = field(default_factory=dict)
    claim_id: str = field(default_factory=_new_claim_id)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "BaselineRecord":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in known})

    def numeric_fields(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for name in KNOWN_NUMERIC_FIELDS[:-1]:  # k handled below
            v = getattr(self, name)
            if v is not None:
                out[name] = float(v)
        if self.k is not None:
            out["k"] = float(self.k)
        for key, val in self.extra.items():
            if val is not None:
                out[f"extra.{key}"] = float(val)
        return out


@dataclass
class DiffReport:
    paper_id: str
    tolerance: float
    baseline_fields: dict[str, float]
    new_fields: dict[str, float]
    diffs: dict[str, tuple[float, float, float]]
    max_abs_diff: float
    exceeds_tolerance: bool


class BaselineStore:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else _default_store_path()
        self._records: dict[str, BaselineRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        for paper_id, data in raw.get("records", {}).items():
            self._records[paper_id] = BaselineRecord.from_dict(data)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "0.1",
            "records": {pid: r.to_dict() for pid, r in sorted(self._records.items())},
        }
        self.path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )

    def record(
        self, paper_id: str, *, commit_sha: str | None = None,
        overwrite: bool = False, **numeric_fields: Any,
    ) -> BaselineRecord:
        if paper_id in self._records and not overwrite:
            raise KeyError(
                f"Paper {paper_id!r} already recorded. Pass --overwrite to replace."
            )
        claim_id = self._records[paper_id].claim_id if (
            overwrite and paper_id in self._records
        ) else _new_claim_id()
        known_kw = {k: v for k, v in numeric_fields.items() if k in KNOWN_NUMERIC_FIELDS}
        extra = {k: float(v) for k, v in numeric_fields.items()
                 if k not in KNOWN_NUMERIC_FIELDS and v is not None}
        rec = BaselineRecord(
            paper_id=paper_id, recorded_at=_utc_now(),
            commit_sha=commit_sha, extra=extra, claim_id=claim_id,
            **known_kw,
        )
        self._records[paper_id] = rec
        return rec

    def record_from_report(
        self, paper_id: str, report: dict,
        *, commit_sha: str | None = None, overwrite: bool = False,
    ) -> BaselineRecord:
        src = report.get("pooled") or report.get("python") or report
        return self.record(
            paper_id, commit_sha=commit_sha, overwrite=overwrite,
            pooled_estimate=src.get("pooled_estimate") or src.get("log_or"),
            ci_lower=src.get("ci_lower"),
            ci_upper=src.get("ci_upper"),
            se=src.get("se"),
            i2=src.get("i2"),
            tau2=src.get("tau2"),
            q=src.get("q"),
            k=src.get("k"),
        )

    def get(self, paper_id: str) -> BaselineRecord | None:
        return self._records.get(paper_id)

    def all(self) -> list[BaselineRecord]:
        return sorted(self._records.values(), key=lambda r: r.paper_id)

    def diff(
        self, paper_id: str, new_fields: dict[str, float],
        *, tolerance: float = DEFAULT_TOLERANCE,
    ) -> DiffReport:
        rec = self._records.get(paper_id)
        if rec is None:
            raise KeyError(f"No baseline recorded for paper {paper_id!r}")
        baseline = rec.numeric_fields()
        diffs: dict[str, tuple[float, float, float]] = {}
        max_diff = 0.0
        for key, old_val in baseline.items():
            if key not in new_fields:
                continue
            new_val = float(new_fields[key])
            d = abs(new_val - old_val)
            if d > 0:
                diffs[key] = (old_val, new_val, d)
                if d > max_diff:
                    max_diff = d
        return DiffReport(
            paper_id=paper_id, tolerance=tolerance,
            baseline_fields=baseline,
            new_fields={k: float(v) for k, v in new_fields.items()},
            diffs=diffs, max_abs_diff=max_diff,
            exceeds_tolerance=max_diff > tolerance,
        )


def _parse_kv(pairs: list[str]) -> dict[str, float]:
    out: dict[str, float] = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"Expected key=value, got {pair!r}")
        k, _, v = pair.partition("=")
        out[k.strip()] = float(v.strip())
    return out


def _load_report(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("pooled") or data.get("python") or data


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--store", type=Path, default=None,
                    help=f"JSON store path (default: {_default_store_path()})")
    sub = ap.add_subparsers(dest="cmd", required=True)

    rec = sub.add_parser("record", help="Record or overwrite a paper's baseline.")
    rec.add_argument("paper_id")
    rec.add_argument("--from", dest="from_report", type=Path, default=None)
    rec.add_argument("--commit", default=None)
    rec.add_argument("--overwrite", action="store_true")
    rec.add_argument("--value", action="append", default=[], metavar="KEY=FLOAT")

    chk = sub.add_parser("check", help="Check a new report against the stored baseline.")
    chk.add_argument("paper_id")
    chk.add_argument("--from", dest="from_report", type=Path, default=None)
    chk.add_argument("--value", action="append", default=[], metavar="KEY=FLOAT")
    chk.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE)

    show = sub.add_parser("show", help="Print one paper's baseline.")
    show.add_argument("paper_id")

    sub.add_parser("list", help="List every paper with a baseline.")

    args = ap.parse_args(argv)
    store = BaselineStore(args.store)

    if args.cmd == "record":
        if args.from_report:
            report = _load_report(args.from_report)
            rec = store.record_from_report(
                args.paper_id, report, commit_sha=args.commit, overwrite=args.overwrite,
            )
        else:
            fields = _parse_kv(args.value)
            rec = store.record(
                args.paper_id, commit_sha=args.commit, overwrite=args.overwrite, **fields,
            )
        store.save()
        print(f"Recorded {rec.paper_id} (claim_id={rec.claim_id}) at {rec.recorded_at}")
        return 0

    if args.cmd == "check":
        if args.from_report:
            report = _load_report(args.from_report)
            new_fields = {
                k: v for k, v in {
                    "pooled_estimate": report.get("pooled_estimate") or report.get("log_or"),
                    "ci_lower": report.get("ci_lower"),
                    "ci_upper": report.get("ci_upper"),
                    "se": report.get("se"),
                    "i2": report.get("i2"),
                    "tau2": report.get("tau2"),
                    "q": report.get("q"),
                    "k": report.get("k"),
                }.items() if v is not None
            }
        else:
            new_fields = _parse_kv(args.value)
        try:
            report = store.diff(args.paper_id, new_fields, tolerance=args.tolerance)
        except KeyError as e:
            print(str(e), file=sys.stderr)
            return 2
        if report.exceeds_tolerance:
            print(f"DRIFT: {args.paper_id} max |diff|={report.max_abs_diff:g} > {args.tolerance:g}")
            for key, (old, new, d) in sorted(report.diffs.items()):
                flag = "!" if d > args.tolerance else " "
                print(f"  {flag} {key}: {old} -> {new}  (|d|={d:g})")
            return 1
        print(f"OK: {args.paper_id} within tolerance (max |diff|={report.max_abs_diff:g})")
        return 0

    if args.cmd == "show":
        rec = store.get(args.paper_id)
        if rec is None:
            print(f"No baseline for {args.paper_id!r}", file=sys.stderr)
            return 1
        print(json.dumps(rec.to_dict(), indent=2))
        return 0

    if args.cmd == "list":
        for r in store.all():
            print(f"{r.paper_id}  claim={r.claim_id}  recorded={r.recorded_at}")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
