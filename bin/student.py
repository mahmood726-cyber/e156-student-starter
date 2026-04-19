"""e156-student-starter CLI.

Usage:
    student                       # opens the TUI menu (added in Task 4)
    student --version
    student help
    student new [--template T0..T5] [--dry-run]
    student ai <task> "prompt..."
    student data pull aact|who|wb|ihme
    student validate [paper-dir]
    student rules refresh
    student doctor
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make ai/friendly_error importable when run directly
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ai.friendly_error import translate


VERSION = "0.2.0-plan-A"

SUBCOMMANDS = ("new", "ai", "data", "validate", "rules", "doctor", "help")


def _cmd_help(_args) -> int:
    print("e156-student-starter CLI\n")
    print("Subcommands:")
    for sub in SUBCOMMANDS:
        print(f"  {sub}")
    print("\nRun `student <subcommand> --help` for details.")
    return 0


def _cmd_new(args) -> int:
    import os
    if args.template is None:
        print("Let's pick a template for you.")
        if args.dry_run:
            return 0
        from bin.help_me_pick import run as run_picker
        run_picker()
        return 0
    from bin.scaffold import scaffold
    slug = args.slug or input("Pick a short slug (lowercase, hyphens): ").strip()
    workbook = Path(os.environ.get("LOCALAPPDATA", "")) / "e156" / "workbook"
    workbook.mkdir(parents=True, exist_ok=True)
    try:
        target = scaffold(args.template, slug=slug, workbook=workbook,
                          repo_root=Path(__file__).resolve().parents[1])
    except NotImplementedError as e:
        print(f"\n{e}\n")
        return 1
    print(f"Scaffolded: {target}")
    return 0


def _cmd_doctor(_args) -> int:
    from tools.get_unstuck import run as run_diagnostic  # noqa: WPS433
    return run_diagnostic()


def _not_yet(cmd: str):
    def _run(_args) -> int:
        print(f"`student {cmd}` is coming in a later plan. Run: student help")
        return 0
    return _run


HANDLERS = {
    "help":     _cmd_help,
    "new":      _cmd_new,
    "ai":       _not_yet("ai"),          # Plan B
    "data":     _not_yet("data"),        # Plan D
    "validate": _not_yet("validate"),    # Plan C
    "rules":    _not_yet("rules"),       # Plan A task 13
    "doctor":   _cmd_doctor,
}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="student", add_help=False)
    p.add_argument("--version", action="store_true")
    p.add_argument("subcommand", nargs="?")
    p.add_argument("--template", default=None,
                   choices=["T0", "T1", "T2", "T3", "T4", "T5"])
    p.add_argument("--slug", default=None)
    p.add_argument("--dry-run", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    parser = _build_parser()
    args, _rest = parser.parse_known_args(argv)

    if args.version:
        print(VERSION)
        return 0

    if not args.subcommand:
        from bin.tui import run as run_tui  # noqa: WPS433
        return run_tui()

    handler = HANDLERS.get(args.subcommand)
    if handler is None:
        print(f"`{args.subcommand}` isn't a command I know. Run: student help")
        return 2

    try:
        return handler(args)
    except Exception as exc:  # noqa: BLE001
        print(str(translate(exc)))
        return 1


if __name__ == "__main__":
    sys.exit(main())
