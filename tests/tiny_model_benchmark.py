"""Benchmark the tiny-model stack (gemma2:2b + qwen2.5-coder:1.5b).

This is the 8GB-laptop path. If the tiny models can do the real student
workflow acceptably, the starter is ready to ship.

Runs four realistic tasks and prints timing + sample output:
  1. Prose rewrite — rewrite a 156-word abstract in plainer language
  2. Code debug — identify a pandas bug
  3. Stats explain — explain heterogeneity I² in plain language
  4. E156 check — validate a 7-sentence 156-word rewrite structure

Usage:
  python tiny_model_benchmark.py
  python tiny_model_benchmark.py --prose-model gemma2:2b --code-model qwen2.5-coder:0.5b
  python tiny_model_benchmark.py --save results.json
"""
from __future__ import annotations
import argparse
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Per lessons.md#data-handling: Windows cp1252 console crashes on
# non-ASCII. Wrap stdout/stderr in a UTF-8 writer that replaces
# unmappable characters with '?' rather than raising.
if sys.platform == "win32" and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STARTER = Path(__file__).resolve().parents[1]
AI_CALL = STARTER / "ai" / "ai_call.py"

EXAMPLE_BODY = (STARTER / "examples" / "example_paper_01" / "current_body.txt").read_text(encoding="utf-8").strip()


TASKS = [
    {
        "id": "prose_rewrite",
        "kind": "prose",
        "prompt": (
            "Rewrite the following methods-paper abstract in plainer English for a "
            "practising clinician. Keep the same 7-sentence structure. Keep it under "
            "156 words. Output ONLY the rewritten body, no commentary.\n\n"
            + EXAMPLE_BODY
        ),
        "min_words": 50,
        "max_words": 156,  # E156 spec hard cap; was 200 (review U-P1-7)
    },
    {
        "id": "code_debug",
        "kind": "code",
        "prompt": (
            "What bug does the following Python function contain? Give one short "
            "sentence of diagnosis and one short fix.\n\n"
            "```python\n"
            "import pandas as pd\n"
            "def first_trial(df, nct_id):\n"
            "    return df[df.nct_id == nct_id].iloc[0]\n"
            "```"
        ),
        "keywords_expected": ["empty", "IndexError", "iloc"],
    },
    {
        "id": "stats_explain",
        "kind": "stats",
        "prompt": (
            "Explain I-squared (I²) in meta-analysis in 3 plain-English sentences "
            "for a clinician. Mention one common misinterpretation."
        ),
        "keywords_expected": ["heterogeneity", "variance", "percent"],
    },
    {
        "id": "e156_check",
        "kind": "prose",
        "prompt": (
            "Check whether the following text follows the E156 format: exactly 7 "
            "sentences in this order (Question, Dataset, Method, Result, Robustness, "
            "Interpretation, Boundary), at most 156 words, single paragraph, no "
            "citations or URLs in the prose. Report: (a) sentence count, (b) whether "
            "the S1-S7 order is correct, (c) one change that would improve it. "
            "Keep reply under 80 words.\n\n"
            + EXAMPLE_BODY
        ),
        "keywords_expected": ["7", "seven", "sentence"],
    },
]


def run_task(task: dict, prose_model: str, code_model: str) -> dict:
    """Run a single task via the router and collect timing + output."""
    env = os.environ.copy()
    env["E156_PROSE_MODEL"] = prose_model
    env["E156_CODE_MODEL"] = code_model
    env["E156_QUICK_MODEL"] = code_model  # quick falls through too
    env["E156_AI_DEBUG"] = "1"
    start = time.time()
    try:
        p = subprocess.run(
            [sys.executable, str(AI_CALL), task["kind"], task["prompt"]],
            env=env, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=180,
        )
        elapsed = time.time() - start
        output = (p.stdout or "").strip()
        debug = (p.stderr or "").strip()
        backend_line = next(
            (ln for ln in debug.splitlines() if ln.startswith("[ai_call]")),
            "",
        )
        return {
            "id": task["id"],
            "kind": task["kind"],
            "prose_model": prose_model,
            "code_model": code_model,
            "elapsed_s": round(elapsed, 2),
            "exit_code": p.returncode,
            "backend_line": backend_line,
            "output": output,
            "output_words": len(output.split()),
            "output_preview": output[:400],
        }
    except subprocess.TimeoutExpired:
        return {
            "id": task["id"], "kind": task["kind"],
            "prose_model": prose_model, "code_model": code_model,
            "elapsed_s": 180.0, "exit_code": 124,
            "backend_line": "", "output": "", "output_words": 0,
            "output_preview": "[TIMEOUT after 180s]",
        }


def evaluate(task: dict, result: dict) -> list[str]:
    """Return a list of warnings/issues with this result (empty = clean)."""
    issues = []
    if result["exit_code"] != 0:
        issues.append(f"exit code {result['exit_code']}")
    wc = result["output_words"]
    if "min_words" in task and wc < task["min_words"]:
        issues.append(f"output too short: {wc} words < {task['min_words']}")
    if "max_words" in task and wc > task["max_words"]:
        issues.append(f"output too long: {wc} words > {task['max_words']}")
    if "keywords_expected" in task:
        lc = result["output"].lower()
        missing = [kw for kw in task["keywords_expected"] if kw.lower() not in lc]
        if missing and len(missing) == len(task["keywords_expected"]):
            issues.append(f"missed ALL expected keywords: {missing}")
    return issues


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prose-model", default="gemma2:2b")
    ap.add_argument("--code-model", default="qwen2.5-coder:1.5b")
    ap.add_argument("--save", help="save full results as JSON to this path")
    args = ap.parse_args()

    print(f"Benchmarking with:")
    print(f"  prose: {args.prose_model}")
    print(f"  code:  {args.code_model}")
    print()

    # Check models are pulled.
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=3) as r:
            tags = [m["name"] for m in json.loads(r.read()).get("models", [])]
    except Exception as e:
        print(f"ERROR: Ollama not reachable: {e}", file=sys.stderr)
        return 2
    for needed in (args.prose_model, args.code_model):
        if needed not in tags:
            print(f"WARN: {needed} not pulled. Available: {tags}", file=sys.stderr)
            print(f"      run: ollama pull {needed}", file=sys.stderr)
    print(f"Models available: {', '.join(tags)}\n")

    results = []
    total_elapsed = 0.0
    for task in TASKS:
        print(f"--- {task['id']} ({task['kind']}) ---")
        r = run_task(task, args.prose_model, args.code_model)
        issues = evaluate(task, r)
        status = "PASS" if not issues else "WARN"
        print(f"  [{status}] {r['elapsed_s']}s  {r['backend_line']}")
        if issues:
            for i in issues:
                print(f"         ! {i}")
        print(f"  preview: {r['output_preview']}")
        print()
        r["issues"] = issues
        results.append(r)
        total_elapsed += r["elapsed_s"]

    # Summary
    passes = sum(1 for r in results if not r["issues"])
    print("=" * 60)
    print(f"Summary: {passes}/{len(results)} pass, total elapsed {total_elapsed:.1f}s")
    print("=" * 60)

    if args.save:
        Path(args.save).write_text(
            json.dumps(
                {
                    "prose_model": args.prose_model,
                    "code_model": args.code_model,
                    "passes": passes,
                    "total": len(results),
                    "total_elapsed_s": round(total_elapsed, 2),
                    "results": results,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nSaved: {args.save}")

    return 0 if passes == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
