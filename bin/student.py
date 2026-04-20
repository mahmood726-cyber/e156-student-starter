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
    student sentinel check [--repo .]   # scan for known-bad patterns (bundled)
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

SUBCOMMANDS = ("new", "ai", "data", "validate", "publish", "baseline", "dashboard", "rules", "sentinel", "memory", "doctor", "help")


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


def _cmd_ai(args) -> int:
    """Dispatch to ai.ai_call.ask with the task kind and prompt.

    Usage:
      student ai <task_kind> "<prompt>"        prose|code|stats|review|quick
      student ai enable-cloud --i-understand-egress
      student ai disable-cloud
    """
    # Support three sub-shapes. First, the consent-flip subcommands.
    try:
        idx = sys.argv.index("ai")
    except ValueError:
        return 2
    rest = sys.argv[idx + 1:]

    if rest and rest[0] == "enable-cloud":
        if "--i-understand-egress" not in rest:
            print("Run: student ai enable-cloud --i-understand-egress")
            print("Enabling cloud means prompt + response data leave your laptop.")
            return 2
        return _toggle_cloud(True)
    if rest and rest[0] == "disable-cloud":
        return _toggle_cloud(False)

    if len(rest) < 2:
        print("Usage: student ai <prose|code|stats|review|quick> \"<prompt>\"")
        return 2
    task_kind = rest[0]
    prompt = " ".join(rest[1:])
    try:
        from ai.ai_call import ask  # noqa: WPS433
        r = ask(task_kind, prompt)
    except ValueError as exc:
        print(str(exc))
        return 2
    except Exception as exc:  # noqa: BLE001
        print(str(translate(exc)))
        return 1
    print(r.text)
    if args.verbose:
        print(f"\n[backend={r.backend} model={r.model} {r.elapsed_ms}ms]", file=sys.stderr)
    return 0


def _toggle_cloud(enable: bool) -> int:
    import json
    import os
    lad = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    consent_path = Path(lad) / "e156" / ".consent.json"
    if not consent_path.is_file():
        print("No .consent.json yet. Run the first-run wizard first.")
        return 2
    data = json.loads(consent_path.read_text(encoding="utf-8"))
    data["cloud_enabled"] = enable
    consent_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Cloud fallback: {'ENABLED' if enable else 'disabled'}")
    return 0


def _cmd_doctor(_args) -> int:
    from tools.get_unstuck import run as run_diagnostic  # noqa: WPS433
    return run_diagnostic()


def _cmd_dashboard(args) -> int:
    """Generate the supervisor HTML dashboard."""
    from tools.dashboard import build, _e156_root  # noqa: WPS433
    html_text = build()
    out = Path(args.out) if args.out else (_e156_root() / "workbook" / "dashboard.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_text, encoding="utf-8")
    print(f"Dashboard written: {out}")
    return 0


def _cmd_baseline(args) -> int:
    """Record/check/show/list numerical baselines per paper. Forwards all args
    after `baseline` on sys.argv to tools.baseline.main."""
    from tools.baseline import main as baseline_main  # noqa: WPS433
    try:
        idx = sys.argv.index("baseline")
    except ValueError:
        return 2
    forwarded = sys.argv[idx + 1:]
    return baseline_main(forwarded)


def _cmd_publish(args) -> int:
    """Build reproducibility pack for a paper in the workbook."""
    from tools.publish_pack import build_pack, _workbook_root  # noqa: WPS433
    if not args.slug and not args.all:
        print("Usage: student publish --slug <name>   OR   student publish --all")
        return 2
    workbook = _workbook_root()
    slugs = [args.slug] if args.slug else [
        p.name for p in workbook.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    ]
    built = []
    for slug in slugs:
        try:
            zp = build_pack(slug)
            print(f"Published: {zp}")
            built.append(zp)
        except FileNotFoundError as exc:
            print(f"Skipped {slug}: {exc}")
    return 0 if built else 1


def _cmd_validate(args) -> int:
    """Run the E156 format validator on a paper body or a workbook."""
    from tools.validate_e156 import validate, _iter_workbook_rewrites  # noqa: WPS433
    target = args.path or "."
    target_path = Path(target)
    if not target_path.exists():
        # Default: look for a current_body.txt in the cwd
        candidate = Path.cwd() / "current_body.txt"
        if candidate.is_file():
            target_path = candidate
        else:
            print(f"error: {target_path} not found (and no current_body.txt in cwd)")
            return 2
    if target_path.is_dir():
        candidate = target_path / "current_body.txt"
        if not candidate.is_file():
            print(f"error: no current_body.txt in {target_path}")
            return 2
        target_path = candidate

    text = target_path.read_text(encoding="utf-8", errors="replace")

    if args.all:
        rewrites = list(_iter_workbook_rewrites(text))
        if not rewrites:
            print("error: no YOUR REWRITE blocks found in this file")
            return 2
        passes = 0
        for label, body in rewrites:
            ok, msgs = validate(body, label=label)
            for m in msgs:
                print(m)
            if ok:
                passes += 1
        print(f"\n{passes}/{len(rewrites)} blocks pass.")
        return 0 if passes == len(rewrites) else 1

    ok, msgs = validate(text, label=str(target_path))
    for m in msgs:
        print(m)
    return 0 if ok else 1


def _cmd_memory(args) -> int:
    """Seed the student's personal memory dir with the starter pack."""
    import os
    import shutil
    bundle_root = Path(__file__).resolve().parents[1]
    source = bundle_root / "memory" / "starter"
    if not source.is_dir():
        print("Starter memory pack missing from bundle.")
        return 2
    target = Path(os.environ.get("LOCALAPPDATA", "")) / "e156" / "memory"
    if target.exists() and not args.force:
        print(f"Memory dir already exists: {target}")
        print("Re-run with --force to overwrite.")
        return 1
    target.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        if item.is_file():
            shutil.copy2(item, target / item.name)
    print(f"Seeded {sum(1 for _ in source.iterdir())} memory files into {target}")
    return 0


def _cmd_sentinel(args) -> int:
    from tools.sentinel_check import main as run_scan  # noqa: WPS433
    repo = args.repo or "."
    scan_argv = ["--repo", repo]
    if args.install_hook:
        scan_argv.append("--install-hook")
    if args.verbose:
        scan_argv.append("--verbose")
    return run_scan(scan_argv)


def _not_yet(cmd: str):
    def _run(_args) -> int:
        print(f"`student {cmd}` is coming in a later plan. Run: student help")
        return 0
    return _run


HANDLERS = {
    "help":     _cmd_help,
    "new":      _cmd_new,
    "ai":       _cmd_ai,
    "data":     _not_yet("data"),        # Plan D
    "validate": _cmd_validate,
    "publish":  _cmd_publish,
    "baseline": _cmd_baseline,
    "dashboard": _cmd_dashboard,
    "rules":    _not_yet("rules"),       # Plan A task 13
    "sentinel": _cmd_sentinel,
    "memory":   _cmd_memory,
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
    p.add_argument("--repo", default=None, help="repo path for `student sentinel`")
    p.add_argument("--install-hook", action="store_true", dest="install_hook",
                   help="install pre-push hook (use with sentinel subcommand)")
    p.add_argument("--force", action="store_true",
                   help="overwrite existing memory dir (use with memory init)")
    p.add_argument("--path", default=None,
                   help="paper body .txt path (for `student validate`)")
    p.add_argument("--out", default=None,
                   help="output path (for `student dashboard`)")
    p.add_argument("--all", action="store_true",
                   help="check every YOUR REWRITE block in a workbook file")
    p.add_argument("--verbose", "-v", action="store_true")
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
