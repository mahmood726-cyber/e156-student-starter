"""Generic reporting-checklist walker (pattern ported from EQUATOR + Cochrane).

Reads any checklist JSON from config/checklists/<id>.json and walks the student
through its items, saving responses to:
    %LOCALAPPDATA%\\e156\\workbook\\<slug>\\checklists\\<id>.json

Each response records: item id, answer (y/n/na OR free text), location in paper
(page/line reference), and a timestamp. `student publish` bundles the whole
`checklists/` directory into the reproducibility pack.

Supports:
    student checklist list                        list all available checklists
    student checklist show prisma-2020            print the checklist items
    student checklist fill prisma-2020 --slug X   walk the student through it
    student checklist status prisma-2020 --slug X print coverage vs. items
    student checklist pick                        EQUATOR-style picker
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from tools.project_paths import bundle_root, paper_dir


CHECKLISTS_DIR = bundle_root() / "config" / "checklists"


@dataclass
class ChecklistMeta:
    id: str
    name: str
    version: str
    applies_to: list[str]
    source: str
    sections: int
    items: int


def list_available() -> list[ChecklistMeta]:
    out: list[ChecklistMeta] = []
    if not CHECKLISTS_DIR.is_dir():
        return out
    for path in sorted(CHECKLISTS_DIR.glob("*.json")):
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        items = sum(len(s.get("items", [])) for s in d.get("sections", []))
        out.append(ChecklistMeta(
            id=d["id"], name=d["name"], version=d.get("version", ""),
            applies_to=list(d.get("applies_to", [])),
            source=d.get("source", ""),
            sections=len(d.get("sections", [])),
            items=items,
        ))
    return out


def load(checklist_id: str) -> dict:
    path = CHECKLISTS_DIR / f"{checklist_id}.json"
    if not path.is_file():
        raise FileNotFoundError(
            f"checklist `{checklist_id}` not found at {path}. "
            f"Run `student checklist list` to see available checklists."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def answers_path(slug: str, checklist_id: str) -> Path:
    return paper_dir(slug) / "checklists" / f"{checklist_id}.json"


def load_answers(slug: str, checklist_id: str) -> dict:
    path = answers_path(slug, checklist_id)
    if not path.is_file():
        return {"checklist_id": checklist_id, "slug": slug, "responses": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_answers(slug: str, checklist_id: str, data: dict) -> Path:
    path = answers_path(slug, checklist_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def compute_coverage(checklist: dict, answers: dict) -> dict:
    total = sum(len(s.get("items", [])) for s in checklist.get("sections", []))
    responded = 0
    yes = 0
    no = 0
    na = 0
    for sec in checklist.get("sections", []):
        for item in sec.get("items", []):
            r = answers.get("responses", {}).get(item["id"])
            if not r:
                continue
            responded += 1
            ans = (r.get("answer") or "").lower()
            if ans in ("y", "yes"):
                yes += 1
            elif ans in ("n", "no"):
                no += 1
            elif ans in ("na", "n/a", "n_a"):
                na += 1
    pct = (responded / total * 100.0) if total else 0.0
    return {"total": total, "responded": responded, "pct": pct,
            "yes": yes, "no": no, "na": na}


def fill_interactive(checklist_id: str, slug: str, *, input_fn=input) -> Path:
    """Walk the student through every item, prompting for y/n/na + location."""
    checklist = load(checklist_id)
    answers = load_answers(slug, checklist_id)
    responses = answers.setdefault("responses", {})

    print(f"Filling {checklist['name']} for paper `{slug}`.")
    print(f"For each item, answer: y = reported, n = not reported, na = not applicable, skip = come back later.")
    allowed_choices = checklist.get("answer_choices")
    if allowed_choices:
        print(f"(This checklist accepts nuanced choices: {', '.join(allowed_choices)}.)")
    print()

    for sec in checklist["sections"]:
        print(f"\n== {sec['name']} ==")
        for item in sec["items"]:
            topic = item.get("topic", "")
            prev = responses.get(item["id"])
            prev_note = f" [prev: {prev.get('answer','')}]" if prev else ""
            print(f"\n  [{item['id']}] {topic}")
            print(f"    {item['text']}")
            ans = input_fn(f"    answer{prev_note}: ").strip().lower() or (prev.get("answer") if prev else "")
            if ans == "skip":
                continue
            loc = input_fn("    location (page/line, blank to skip): ").strip() or (prev.get("location") if prev else "")
            responses[item["id"]] = {
                "answer": ans,
                "location": loc or None,
                "note": (prev.get("note") if prev else None),
            }

    path = save_answers(slug, checklist_id, answers)
    cov = compute_coverage(checklist, answers)
    print(f"\n[checklist] saved to {path}")
    print(f"[checklist] coverage {cov['responded']}/{cov['total']} items ({cov['pct']:.0f}%) "
          f"- yes={cov['yes']} no={cov['no']} na={cov['na']}")
    return path


def show(checklist_id: str) -> None:
    checklist = load(checklist_id)
    print(f"\n{checklist['name']} ({checklist['version']})")
    print(f"source: {checklist.get('source','')}")
    print(f"applies_to: {', '.join(checklist.get('applies_to', []))}")
    for sec in checklist["sections"]:
        print(f"\n== {sec['name']} ==")
        for item in sec["items"]:
            print(f"  [{item['id']}] {item.get('topic','')}: {item['text']}")


def status(checklist_id: str, slug: str) -> dict:
    checklist = load(checklist_id)
    answers = load_answers(slug, checklist_id)
    cov = compute_coverage(checklist, answers)
    missing = []
    for sec in checklist["sections"]:
        for item in sec["items"]:
            if item["id"] not in answers.get("responses", {}):
                missing.append(item["id"])
    cov["missing_ids"] = missing
    return cov


# ---------------- EQUATOR picker ----------------

_PICK_TREE = [
    # (asked_question, answer_hints, child_id)
    # Root node id "root" -> one of several design types.
    # Design types map to canonical checklist ids.
    ("What best describes your paper?",
     ["systematic review of studies", "meta-analysis of RCTs or observational studies",
      "randomised controlled trial", "observational cohort/case-control/cross-sectional study",
      "diagnostic-test-accuracy study", "case report or case series"],
     ["prisma-2020", "prisma-2020", "consort-2010", "strobe", "stard-2015", "care"]),
]


def pick_checklist(input_fn=input) -> str | None:
    """Very small decision tree. Returns checklist_id or None if user abandons."""
    q, choices, mapping = _PICK_TREE[0]
    print(q)
    for i, c in enumerate(choices, 1):
        print(f"  {i}. {c}")
    ans = input_fn("Pick a number (or q to abort): ").strip().lower()
    if ans == "q":
        return None
    try:
        idx = int(ans) - 1
        cid = mapping[idx]
    except (ValueError, IndexError):
        print("Unrecognised choice.")
        return None
    try:
        load(cid)
        print(f"\nRecommended: {cid}")
        return cid
    except FileNotFoundError:
        print(f"\nRecommended checklist: {cid} (not yet bundled; coming soon).")
        return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list all bundled checklists")

    show_p = sub.add_parser("show", help="print items of a checklist")
    show_p.add_argument("checklist_id")

    fill_p = sub.add_parser("fill", help="walk through a checklist for a paper")
    fill_p.add_argument("checklist_id")
    fill_p.add_argument("--slug", required=True)

    status_p = sub.add_parser("status", help="coverage report for a paper's checklist")
    status_p.add_argument("checklist_id")
    status_p.add_argument("--slug", required=True)

    sub.add_parser("pick", help="decision-tree picker (EQUATOR-style)")

    args = ap.parse_args(argv)

    if args.cmd == "list":
        for m in list_available():
            print(f"  {m.id:<15} {m.name}  ({m.items} items, applies to {', '.join(m.applies_to)})")
        return 0

    if args.cmd == "show":
        try:
            show(args.checklist_id)
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        return 0

    if args.cmd == "fill":
        try:
            fill_interactive(args.checklist_id, args.slug)
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        return 0

    if args.cmd == "status":
        try:
            s = status(args.checklist_id, args.slug)
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(f"coverage: {s['responded']}/{s['total']} ({s['pct']:.0f}%)")
        print(f"  yes={s['yes']}  no={s['no']}  na={s['na']}")
        if s["missing_ids"]:
            print(f"  missing: {', '.join(s['missing_ids'][:15])}{'...' if len(s['missing_ids']) > 15 else ''}")
        return 0 if s["responded"] == s["total"] else 1

    if args.cmd == "pick":
        cid = pick_checklist()
        return 0 if cid else 1

    return 2


if __name__ == "__main__":
    sys.exit(main())
