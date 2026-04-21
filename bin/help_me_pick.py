"""Help-me-pick wizard: 3 yes/no questions -> recommend T1..T5 + one recommended badge.

Templates may be stubs (see _TEMPLATE_DIRS / .stub marker). When the recommended
template is a stub, the wizard switches to honesty mode: no [Recommended] badge,
explicit 'not implemented yet' note, and a T0 fallback for users who want to
start now.
"""
from __future__ import annotations

import sys
from pathlib import Path


_QUESTIONS = [
    ("Are you comparing two drugs against each other?",  "pools_drugs"),
    ("Is your project about ONE condition in ONE country?", "one_country_one_condition"),
    ("Are you re-running a published meta-analysis?",     "rerunning_published_ma"),
]


_TEMPLATES_HELP = {
    "T1": "Pairwise mini-MA - compare two drugs (most common first project).",
    "T2": "Trials audit - one drug, registered-vs-reported gap.",
    "T3": "Burden snapshot - one condition x one country, descriptive claim.",
    "T4": "MA replication - rerun a published meta-analysis and quantify |Delta|.",
    "T5": "Living MA seed - new topic, set up a CT.gov watcher.",
}

_TEMPLATE_DIRS = {
    "T0": "T0_blank",
    "T1": "T1_pairwise_mini_ma",
    "T2": "T2_trials_audit",
    "T3": "T3_burden_snapshot",
    "T4": "T4_ma_replication",
    "T5": "T5_living_ma_seed",
}

_FALLBACK_CODE = "T0"


def _templates_root() -> Path:
    return Path(__file__).resolve().parent.parent / "templates"


def is_stub(code: str) -> bool:
    """True iff the template directory exists and contains a .stub marker."""
    dirname = _TEMPLATE_DIRS.get(code)
    if dirname is None:
        return False
    return (_templates_root() / dirname / ".stub").is_file()


def recommend(pools_drugs: str, one_country_one_condition: str,
              rerunning_published_ma: str) -> str:
    """Priority: replication beats everything (it's the most specific signal)."""
    def yes(v: str) -> bool:
        return v.strip().lower() in ("y", "yes", "1", "true")

    if yes(rerunning_published_ma):
        return "T4"
    if yes(pools_drugs):
        return "T1"
    if yes(one_country_one_condition):
        return "T3"
    if any((pools_drugs, one_country_one_condition, rerunning_published_ma)):
        # User said 'n' to at least one -> genuine new-topic intent -> living MA seed
        return "T5"
    # Empty inputs: safest default
    return "T1"


def run() -> int:
    print("Answer 3 quick questions and I'll recommend a template.\n")
    answers = []
    for q, _ in _QUESTIONS:
        ans = input(f"  {q} [y/n] ").strip().lower()
        answers.append(ans)

    choice = recommend(*answers)
    choice_is_stub = is_stub(choice)

    print("\nRecommended template:")
    if choice_is_stub:
        # Honesty mode: don't claim the template is ready when it isn't.
        print(f"  {choice} - {_TEMPLATES_HELP[choice]}")
        print(f"    (NOT YET IMPLEMENTED - this template is a stub.)")
        print(f"    Falling back to {_FALLBACK_CODE} (blank scaffold) so you can start now.")
    else:
        print(f"  [\u2605 Recommended] {choice} - {_TEMPLATES_HELP[choice]}")

    print("\nAll templates:")
    for code, desc in _TEMPLATES_HELP.items():
        status = "[stub]" if is_stub(code) else "[ready]"
        mark = "\u2605" if (code == choice and not choice_is_stub) else " "
        print(f"  {mark} {code} {status:7s} - {desc}")

    actual = _FALLBACK_CODE if choice_is_stub else choice
    confirm = input(f"\nUse {actual}? [Y/n] ").strip().lower()
    if confirm in ("", "y", "yes"):
        print(f"\nGreat - next run: student new --template {actual}")
        return 0
    print("\nNo problem. Run `student new --template TN` when you've picked one.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
