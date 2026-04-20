"""Template scaffolding for `student new --template TN`.

Plan A ships T0 (blank) fully. T1-T5 are stubs that raise NotImplementedError
pointing at Plan E. This keeps the CLI UX consistent while the template
bodies are being designed.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{1,63}$")


def scaffold(template: str, slug: str, workbook: Path, repo_root: Path) -> Path:
    if template not in {"T0", "T1", "T2", "T3", "T4", "T5"}:
        raise ValueError(f"Unknown template: {template}")
    if not SLUG_RE.match(slug):
        raise ValueError(
            f"Bad slug {slug!r}. Use lowercase letters, digits, hyphens only "
            f"(e.g. 'my-first-paper'). 2-64 chars."
        )

    template_dir = repo_root / "templates" / _template_dirname(template)
    if (template_dir / ".stub").exists():
        raise NotImplementedError(
            f"{template} full scaffolding ships in Plan E. "
            f"Run `student new --template T0` for now."
        )

    target = workbook / slug
    if target.exists():
        raise FileExistsError(f"Workbook folder already exists: {target}")

    shutil.copytree(template_dir, target, ignore=shutil.ignore_patterns(".stub"))

    # Git init the workbook if it isn't already a repo
    if not (workbook / ".git").exists():
        subprocess.run(["git", "init", "-q"], cwd=workbook, check=False)
    return target


def _template_dirname(code: str) -> str:
    return {
        "T0": "T0_blank",
        "T1": "T1_pairwise_mini_ma",
        "T2": "T2_trials_audit",
        "T3": "T3_burden_snapshot",
        "T4": "T4_ma_replication",
        "T5": "T5_living_ma_seed",
    }[code]
