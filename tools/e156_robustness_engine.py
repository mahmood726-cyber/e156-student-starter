# sentinel:skip-file — regex literals include the very tokens the rule catches
"""Tier-C robustness validator for E156 bodies (pattern #1 from portfolio survey).

Extends `tools/validate_e156.py` from a format checker (7 sentences, 156 words,
no citations) into a *quality* checker that catches:

  - S4 (Result) missing a numeric outcome or a named estimand
  - S7 (Boundary) being a generic disclaimer instead of a specific limitation
  - Placeholder tokens anywhere in the body

Pure stdlib. Returns a list of Issue objects; caller decides how to render.

Usage (library):
    from tools.e156_robustness_engine import run_checks
    issues = run_checks(body_text)
    for i in issues:
        print(i.severity, i.sentence_idx, i.message)

Usage (via CLI):
    student validate --path my.txt --strict
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Issue:
    severity: str      # BLOCK | WARN | INFO
    sentence_idx: int  # 1..7 or 0 for body-level
    rule: str          # short rule id
    message: str


# --- S4: Result sentence ---------------------------------------------------

# Numeric patterns we consider valid "result" content. Matches integers,
# floats, percentages, p-values, ORs/HRs/RRs/SMDs/MDs with or without CIs.
_NUMERIC = re.compile(
    r"(\d+(?:\.\d+)?%|"                 # 45%, 12.3%
    r"\bp\s*[<>=]\s*0?\.\d+|"           # p<0.05, p = .01
    r"\b\d+(?:,\d{3})*(?:\.\d+)?\b|"     # 19,112 or 3.14
    r"\bCI\b|\bconfidence\s+interval\b)", # mentions of CI
    re.I,
)

# Canonical effect-measure names. S4 must name the estimand.
_ESTIMAND_RE = re.compile(
    r"\b(?:"
    r"OR|odds\s+ratio|"
    r"HR|hazard\s+ratio|"
    r"RR|risk\s+ratio|relative\s+risk|"
    r"RD|risk\s+difference|"
    r"SMD|standardi[sz]ed\s+mean\s+difference|"
    r"MD|mean\s+difference|"
    r"proportion|prevalence|incidence|"
    r"sensitivity|specificity|AUC|"
    r"beta|coefficient|"
    r"difference|reduction|increase"
    r")\b",
    re.I,
)


def _check_result_sentence(s4: str) -> list[Issue]:
    issues: list[Issue] = []
    if not _NUMERIC.search(s4):
        issues.append(Issue(
            "BLOCK", 4, "S4-no-numeric",
            "S4 (Result) must contain a numeric value — a percentage, a CI, "
            "a p-value, or a headline number. Right now it's all prose.",
        ))
    if not _ESTIMAND_RE.search(s4):
        issues.append(Issue(
            "WARN", 4, "S4-no-estimand",
            "S4 (Result) does not name an estimand (OR, HR, RR, SMD, MD, "
            "proportion, etc.). Readers need to know what is being reported.",
        ))
    return issues


# --- S7: Boundary sentence -------------------------------------------------

# Generic, non-substantive boundary phrases we flag.
_GENERIC_BOUNDARY = re.compile(
    r"further\s+research\s+is\s+needed"
    r"|more\s+studies?\s+are\s+needed"
    r"|additional\s+research\s+is\s+(?:warranted|required)"
    r"|limitations\s+exist"
    r"|has\s+(?:some\s+)?limitations\b",
    re.I,
)

# Substantive limitation markers: if S7 contains one of these, we trust it.
_SUBSTANTIVE_LIMITATIONS = re.compile(
    r"\b(?:"
    r"small\s+sample|limited\s+sample|underpowered|"
    r"short\s+follow[-\s]?up|brief\s+follow[-\s]?up|"
    r"single[-\s]?arm|non[-\s]?randomi[sz]ed|observational\s+data|"
    r"publication\s+bias|selection\s+bias|attrition\s+bias|"
    r"missing\s+data|loss\s+to\s+follow[-\s]?up|"
    r"generali[sz]ability|external\s+validity|"
    r"heterogen|inconsisten|"
    r"applies?\s+only\s+to|not\s+extend\s+to|not\s+applicable\s+to|"
    r"excludes?\b|exclud(?:ed|ing)\b|"
    r"does\s+not\s+(?:include|cover|address|generali[sz]e)|"
    r"limited\s+to|confined\s+to|restricted\s+to"
    r")\b",
    re.I,
)


def _check_boundary_sentence(s7: str) -> list[Issue]:
    issues: list[Issue] = []
    if _GENERIC_BOUNDARY.search(s7) and not _SUBSTANTIVE_LIMITATIONS.search(s7):
        issues.append(Issue(
            "WARN", 7, "S7-generic-disclaimer",
            "S7 (Boundary) uses a generic 'further research needed' phrase. "
            "Replace with a specific limitation: small sample, short follow-up, "
            "single-arm, observational data, publication bias, generalizability, etc.",
        ))
    elif not _SUBSTANTIVE_LIMITATIONS.search(s7):
        issues.append(Issue(
            "INFO", 7, "S7-substance-uncertain",
            "S7 (Boundary) may not name a specific limitation. Check that it "
            "identifies WHO this result does NOT apply to, not just repeats "
            "the finding.",
        ))
    return issues


# --- Body-level placeholder scan -------------------------------------------

_PLACEHOLDER_TOKENS = re.compile(
    r"\{\{[^}]+\}\}"                  # {{REPLACE_ME}}, {{estimand}}
    r"|\bREPLACE_ME\b"
    r"|\bTBD\b"
    r"|\bTODO\b"
    r"|\[TO\s+BE\s+FILLED\]"
    r"|\bFIXME\b"
    r"|\b__(?:placeholder|pending|stub)__\b",
    re.I,
)


def _check_body_placeholders(body: str) -> list[Issue]:
    matches = _PLACEHOLDER_TOKENS.findall(body)
    if not matches:
        return []
    return [Issue(
        "BLOCK", 0, "body-placeholder",
        f"Body contains unresolved placeholder token(s): "
        f"{', '.join(sorted(set(matches))[:4])}. Replace before submission.",
    )]


# --- Public entry point ----------------------------------------------------

def run_checks(body: str) -> list[Issue]:
    """Run every robustness check on the E156 body. Returns all issues found."""
    # Use validate_e156's sentence splitter so our sentence indexing matches.
    from tools.validate_e156 import split_sentences  # noqa: WPS433

    issues: list[Issue] = []
    issues.extend(_check_body_placeholders(body))

    sents = split_sentences(body)
    if len(sents) < 7:
        issues.append(Issue(
            "BLOCK", 0, "fewer-than-7-sentences",
            f"Only {len(sents)} sentences; robustness checks need 7. "
            "Fix format before running --strict.",
        ))
        return issues

    issues.extend(_check_result_sentence(sents[3]))   # S4 (0-indexed idx 3)
    issues.extend(_check_boundary_sentence(sents[6])) # S7
    return issues


def format_report(issues: list[Issue]) -> str:
    """Return a human-readable multi-line report."""
    if not issues:
        return "[robustness] 0 issues — body passes Tier-C checks."
    lines = [f"[robustness] {len(issues)} issue(s):"]
    for i in issues:
        loc = f"S{i.sentence_idx}" if i.sentence_idx > 0 else "BODY"
        lines.append(f"  [{i.severity}] {loc} {i.rule}: {i.message}")
    return "\n".join(lines)
