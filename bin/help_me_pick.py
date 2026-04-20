"""Help-me-pick wizard: 3 yes/no questions -> recommend T1..T5 + one recommended badge."""
from __future__ import annotations

import sys


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
    print("\nRecommended template:")
    print(f"  [\u2605 Recommended] {choice} - {_TEMPLATES_HELP[choice]}\n")
    print("All templates:")
    for code, desc in _TEMPLATES_HELP.items():
        mark = "\u2605" if code == choice else " "
        print(f"  {mark} {code} - {desc}")

    confirm = input(f"\nUse {choice}? [Y/n] ").strip().lower()
    if confirm in ("", "y", "yes"):
        print(f"\nGreat - next run: student new --template {choice}")
        return 0
    print("\nNo problem. Run `student new --template TN` when you've picked one.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
