# sentinel:skip-file - scanner references {{BUNDLE_ROOT}} as legitimate code
"""Lightweight Sentinel-compatible scanner for the student starter bundle.

Reads YAML rule files from config/sentinel/rules/ and scans a repo for
pattern violations. Designed to be self-contained: requires only PyYAML.
The full upstream Sentinel at C:\\Sentinel has 20 rules and a plugin system;
this scanner covers only the 4 vendored YAML rules a student actually
needs, in under 200 LOC.

Usage:
  python tools/sentinel_check.py                # scan cwd
  python tools/sentinel_check.py --repo <path>  # scan specific repo
  python tools/sentinel_check.py --rule P1-empty-dataframe-access  # single rule

Exit codes:
  0  no BLOCK findings (WARNs don't affect exit)
  1  at least one BLOCK finding
  2  scanner error (bad YAML, missing repo, etc.)
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
RULES_DIR = REPO_ROOT / "config" / "sentinel" / "rules"

# Directories we never scan (matches Sentinel upstream's GLOBAL_EXCLUDES).
GLOBAL_EXCLUDES = (
    ".git/*", ".git/**",
    "**/__pycache__/*", "**/__pycache__/**",
    "**/.venv/*", "**/.venv/**",
    "**/node_modules/*", "**/node_modules/**",
    "**/dist/*", "**/dist/**",
    "**/build/*", "**/build/**",
    "**/.pytest_cache/*", "**/.pytest_cache/**",
    # Sentinel's own output files (mirror upstream behaviour)
    "STUCK_FAILURES.md", "STUCK_FAILURES.jsonl",
    "sentinel-findings.md", "sentinel-findings.jsonl",
    "**/STUCK_FAILURES.md", "**/STUCK_FAILURES.jsonl",
    "**/sentinel-findings.md", "**/sentinel-findings.jsonl",
)

# Patterns skipped because they're meant to contain the very patterns the
# rule flags (test fixtures, conftest, the rules dir itself).
COMMON_EXCLUDES = (
    "tests/*", "tests/**", "**/tests/*", "**/tests/**",
    "fixtures/*", "fixtures/**", "**/fixtures/*", "**/fixtures/**",
    "conftest.py", "**/conftest.py",
    "config/sentinel/**",
)

SKIP_FILE_MARKER = "sentinel:skip-file"


@dataclass
class Rule:
    rule_id: str
    severity: str
    pattern: re.Pattern[str]
    files: tuple[str, ...]
    exclude: tuple[str, ...]
    fix_hint: str
    source: str


@dataclass
class Finding:
    rule_id: str
    severity: str
    path: Path
    line_no: int
    line: str
    fix_hint: str


def load_rules(rules_dir: Path = RULES_DIR) -> list[Rule]:
    rules: list[Rule] = []
    for rule_file in sorted(rules_dir.glob("*.yaml")):
        with rule_file.open(encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        rules.append(Rule(
            rule_id=raw["id"],
            severity=raw["severity"],
            pattern=re.compile(raw["pattern"]),
            files=tuple(raw.get("files", ())),
            exclude=tuple(raw.get("exclude", ())),
            fix_hint=(raw.get("fix_hint") or "").strip(),
            source=(raw.get("source") or "").strip(),
        ))
    return rules


_GLOB_CACHE: dict[str, re.Pattern[str]] = {}


def _glob_to_regex(glob: str) -> re.Pattern[str]:
    """Translate a gitignore-style glob to regex: `**` spans any dirs, `*` stays within one segment."""
    cached = _GLOB_CACHE.get(glob)
    if cached is not None:
        return cached
    # Normalise separators to forward slash (we compare against posix paths).
    glob = glob.replace("\\", "/")
    i, out = 0, []
    while i < len(glob):
        c = glob[i]
        if glob[i:i+3] == "**/":
            out.append("(?:.*/)?")
            i += 3
        elif glob[i:i+2] == "**":
            out.append(".*")
            i += 2
        elif c == "*":
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    pattern = re.compile("^" + "".join(out) + "$")
    _GLOB_CACHE[glob] = pattern
    return pattern


def path_matches(rel: str, patterns: tuple[str, ...]) -> bool:
    rel = rel.replace("\\", "/")
    return any(_glob_to_regex(p).match(rel) for p in patterns)


def scan(repo: Path, rules: list[Rule], rule_id: str | None = None) -> list[Finding]:
    findings: list[Finding] = []
    repo = repo.resolve()
    for rule in rules:
        if rule_id and rule.rule_id != rule_id:
            continue
        for path in repo.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(repo).as_posix()
            if path_matches(rel, GLOBAL_EXCLUDES):
                continue
            if path_matches(rel, COMMON_EXCLUDES):
                continue
            if not path_matches(rel, rule.files):
                continue
            if path_matches(rel, rule.exclude):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if SKIP_FILE_MARKER in text[:1024]:
                continue
            for line_no, line in enumerate(text.splitlines(), start=1):
                if rule.pattern.search(line):
                    findings.append(Finding(
                        rule_id=rule.rule_id,
                        severity=rule.severity,
                        path=path.relative_to(repo),
                        line_no=line_no,
                        line=line.strip()[:120],
                        fix_hint=rule.fix_hint,
                    ))
    return findings


def format_finding(f: Finding) -> str:
    tag = "[BLOCK]" if f.severity == "BLOCK" else "[WARN]"
    return f"  {tag} {f.rule_id}  {f.path}:{f.line_no}  {f.line}"


def install_hook(repo: Path, bundle_root: Path = REPO_ROOT) -> Path:
    """Install pre-push hook into repo/.git/hooks/pre-push, substituting {{BUNDLE_ROOT}}."""
    hook_template = bundle_root / "config" / "sentinel" / "hooks" / "pre-push"
    if not hook_template.is_file():
        raise FileNotFoundError(f"hook template missing: {hook_template}")
    git_dir = repo / ".git"
    if not git_dir.is_dir():
        raise RuntimeError(f"{repo} is not a git repo (.git/ missing)")
    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    target = hooks_dir / "pre-push"
    content = hook_template.read_text(encoding="utf-8")
    content = content.replace("{{BUNDLE_ROOT}}", bundle_root.as_posix())
    target.write_text(content, encoding="utf-8")
    try:
        target.chmod(0o755)
    except OSError:
        pass  # Windows may not support chmod; git will honour the file anyway
    return target


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=".", help="Repo root to scan (default: cwd)")
    ap.add_argument("--rule", help="Run a single rule by id")
    ap.add_argument("--verbose", "-v", action="store_true", help="Show fix_hint for each finding")
    ap.add_argument("--install-hook", action="store_true",
                    help="Install Sentinel pre-push hook into <repo>/.git/hooks/")
    args = ap.parse_args(argv)

    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        print(f"error: {repo} is not a directory", file=sys.stderr)
        return 2

    if args.install_hook:
        try:
            target = install_hook(repo)
        except (FileNotFoundError, RuntimeError) as e:
            print(f"error installing hook: {e}", file=sys.stderr)
            return 2
        print(f"[sentinel-check] pre-push hook installed: {target}")
        return 0

    try:
        rules = load_rules()
    except Exception as e:
        print(f"error loading rules: {e}", file=sys.stderr)
        return 2

    findings = scan(repo, rules, rule_id=args.rule)
    blocks = [f for f in findings if f.severity == "BLOCK"]
    warns = [f for f in findings if f.severity == "WARN"]

    print(f"[sentinel-check] scanning {repo} with {len(rules)} rule(s)")
    for f in findings:
        print(format_finding(f))
        if args.verbose and f.fix_hint:
            print(f"    fix: {f.fix_hint[:200]}")
    print(f"[sentinel-check] verdicts: BLOCK={len(blocks)} WARN={len(warns)}")
    return 1 if blocks else 0


if __name__ == "__main__":
    sys.exit(main())
