# sentinel:skip-file — one-shot scratch script with a dev-machine default path
"""Generate authorship.json + README.md for the 10 example papers.
One-shot scratch script; run directly, do not import.
"""
from __future__ import annotations

import json
import pathlib
import sys

REPO = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(r"C:\Users\user\AppData\Local\Temp\e156-examples-repo")
PAPERS = REPO / "papers"

TOPICS = {
    "sickle-hu-ssa":        "Hydroxyurea for sickle-cell pain crises in Sub-Saharan African children",
    "malaria-rdt-u5":       "Malaria rapid-diagnostic-test accuracy in Ugandan under-5s vs thick-film microscopy",
    "art-pmtct-uga":        "Integrase-inhibitor vs efavirenz-based ART in rural Ugandan PMTCT at 18 months",
    "cs-ssi-lmic":          "Pre-incision vs post-cord-clamp cefazolin for caesarean SSI in LMIC settings",
    "tb-hiv-ipt":           "6-month vs 36-month isoniazid preventive therapy in TB/HIV co-infected adults",
    "cholera-refugee":      "Single-dose vs two-dose oral cholera vaccine in East African refugee children",
    "neonatal-sepsis-abx":  "Ampicillin-gentamicin vs ampicillin-cefotaxime empirical neonatal-sepsis therapy",
    "htn-rural-uga":        "Nurse-led task-shifting vs physician-only hypertension care in rural Uganda",
    "cervical-via-hpv":     "VIA vs HPV DNA primary screening for cervical cancer in unvaccinated women 30-50",
    "tb-xpert-smear":       "Xpert MTB/RIF vs direct sputum microscopy for time-to-TB-treatment in Uganda",
}


def authorship_for(slug: str) -> dict:
    return {
        "first_author": {
            "full_name": "Student Example", "email": "student@example.ug",
            "affiliation": "Example University", "orcid": None,
            "credit_roles": ["conceptualization", "investigation",
                             "formal-analysis", "writing-original-draft"],
            "is_board_member_of_target_journal": False,
        },
        "middle_author": {
            "full_name": "Mahmood Ahmad", "email": "mahmood.ahmad2@nhs.net",
            "affiliation": "Tahir Heart Institute", "orcid": None,
            "credit_roles": ["methodology", "writing-review-editing"],
            "is_board_member_of_target_journal": True,
        },
        "last_author": {
            "full_name": "Mentor Example", "email": "mentor@example.ug",
            "affiliation": "Example University", "orcid": None,
            "credit_roles": ["supervision", "writing-review-editing"],
            "is_board_member_of_target_journal": False,
        },
        "conflicts_of_interest": {"has_conflicts": False, "statement": ""},
        "funding_sources": [],
        "ai_assistance_disclosed": {
            "used_ai": True,
            "disclosure_sentence": (
                "Local Gemma 2 and Qwen 2.5 Coder models via the e156 student "
                "starter were used for language editing; the authors accept "
                "full responsibility for all content."
            ),
            "backends": ["ollama"],
        },
        "editorial_board_coi": {
            "any_board_member": True,
            "no_role_paragraph_included": True,
            "journal_name_exact": "Synthesis",
        },
    }


README_TEMPLATE = """# {topic}

**Example paper** produced by the [e156 student starter](https://github.com/mahmood726-cyber/e156-student-starter).

This directory demonstrates what the bundle outputs end-to-end:

- `current_body.txt` — the 7-sentence, ~156-word E156 body.
- `authorship.json` — authorship contract (first/middle/last + CRediT roles + AI disclosure).
- `reproducibility-pack.zip` — the full pack emitted by `student publish --slug {slug}`, containing:
  - `paper/` — body + metadata
  - `manifest.json` — SHA256 of every file (tamper-evident)
  - `ro-crate-metadata.json` — FAIR-compliant RO-Crate 1.2 JSON-LD
  - `pins.json` — exact Ollama + Python + model versions
  - `CITATION.cff` — machine-readable citation for GitHub + Zenodo
  - `README.md` — human-readable manifest
  - `ai_calls_filtered.jsonl` — hash-only audit log (no raw PII)

## The body ({slug})

```text
{body}
```

> ⚠ **NOTE:** This is a DEMONSTRATION paper, not a real submission. Numbers are plausible but fabricated for example purposes. Do not cite.

## Reproducing this paper

Install the e156 starter (see the [main README](https://github.com/mahmood726-cyber/e156-student-starter)), then run:

```
student new --template T0 --slug {slug}
# ... draft current_body.txt ...
student validate --path current_body.txt --strict
student baseline record {slug} --from report.json
student verify-citations --path current_body.txt
student enroll-authors --slug {slug}
student publish --slug {slug}
```

The published zip's `manifest.json` SHA256s will match byte-for-byte across
reproductions if the paper content is identical.
"""


def main() -> int:
    for slug, topic in TOPICS.items():
        d = PAPERS / slug
        if not d.is_dir():
            print(f"skip {slug}: dir missing")
            continue
        (d / "authorship.json").write_text(
            json.dumps(authorship_for(slug), indent=2), encoding="utf-8"
        )
        body = (d / "current_body.txt").read_text(encoding="utf-8").strip()
        (d / "README.md").write_text(
            README_TEMPLATE.format(topic=topic, slug=slug, body=body),
            encoding="utf-8",
        )
    print(f"wrote metadata + READMEs for {len(TOPICS)} papers under {PAPERS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
