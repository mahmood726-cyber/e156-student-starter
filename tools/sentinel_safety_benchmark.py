"""Measure what fraction of Ollama model outputs trigger Sentinel rules.

Reads the per-tier benchmark JSON in tests/fixtures/results_*_tier.json,
writes each model output to a throwaway file, runs the bundled Sentinel
scanner against it, and reports per-tier + per-task catch rates.

This is the closing-the-loop metric that says: "how often does the
rule library catch an AI model's wrong answer?"

Usage:
  python tools/sentinel_safety_benchmark.py
  python tools/sentinel_safety_benchmark.py --save tests/fixtures/safety_net_report.json
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.sentinel_check import load_rules, scan  # noqa: E402

TASK_FILE_EXT = {
    "prose_rewrite": ".md",
    "e156_check":    ".md",
    "stats_explain": ".md",
    "code_debug":    ".py",
}


def measure_tier(results_path: Path) -> dict:
    data = json.loads(results_path.read_text(encoding="utf-8"))
    rules = load_rules()

    per_task = []
    total_findings = 0
    tasks_with_findings = 0

    for task_result in data["results"]:
        task_id = task_result["id"]
        output = task_result.get("output") or ""
        ext = TASK_FILE_EXT.get(task_id, ".txt")

        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            tmpfile = tmpdir / f"{task_id}{ext}"
            tmpfile.write_text(output, encoding="utf-8")
            findings = scan(tmpdir, rules)

        rules_triggered = sorted({f.rule_id for f in findings})
        n_findings = len(findings)
        total_findings += n_findings
        if n_findings > 0:
            tasks_with_findings += 1

        per_task.append({
            "task_id": task_id,
            "kind": task_result.get("kind"),
            "output_words": task_result.get("output_words", 0),
            "findings": n_findings,
            "rules_triggered": rules_triggered,
        })

    return {
        "tier_model_prose": data["prose_model"],
        "tier_model_code":  data["code_model"],
        "total_tasks": len(data["results"]),
        "tasks_with_findings": tasks_with_findings,
        "total_findings": total_findings,
        "per_task": per_task,
    }


def print_report(reports: list[dict]) -> None:
    print(f"{'='*70}")
    print(f"{'SENTINEL SAFETY-NET BENCHMARK':^70}")
    print(f"{'='*70}")
    for r in reports:
        print()
        print(f"Tier: prose={r['tier_model_prose']}  code={r['tier_model_code']}")
        print(f"  Tasks with Sentinel findings: {r['tasks_with_findings']}/{r['total_tasks']}")
        print(f"  Total findings across tier:  {r['total_findings']}")
        for t in r["per_task"]:
            flag = "OK " if t["findings"] == 0 else "HIT"
            rules_str = ", ".join(t["rules_triggered"]) if t["rules_triggered"] else "-"
            print(f"    [{flag}] {t['task_id']:<16} {t['findings']} finding(s)  rules={rules_str}")
    print(f"\n{'='*70}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fixtures-dir", default="tests/fixtures",
                    help="dir containing results_*_tier.json (default: tests/fixtures)")
    ap.add_argument("--save", help="write full report as JSON to this path")
    args = ap.parse_args(argv)

    fixtures = Path(args.fixtures_dir)
    if not fixtures.is_dir():
        fixtures = REPO_ROOT / args.fixtures_dir
    if not fixtures.is_dir():
        print(f"error: fixtures dir {fixtures} not found", file=sys.stderr)
        return 2

    tier_files = sorted(fixtures.glob("results_*_tier.json"))
    if not tier_files:
        print(f"error: no results_*_tier.json in {fixtures}", file=sys.stderr)
        print("Run `python tests/tiny_model_benchmark.py --save <...>` first.", file=sys.stderr)
        return 2

    reports = [measure_tier(p) for p in tier_files]
    print_report(reports)

    if args.save:
        Path(args.save).write_text(
            json.dumps({"tiers": reports}, indent=2), encoding="utf-8",
        )
        print(f"Saved: {args.save}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
