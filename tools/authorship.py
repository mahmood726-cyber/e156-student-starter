"""Authorship enrol + check (portfolio pattern #2 from AuthorshipLedger).

Enforces the E156 authorship contract:

  1. Three positional roles required: first, middle, last.
  2. Name + email + affiliation required for each.
  3. ORCID optional but in `https://orcid.org/0000-0000-0000-0000` format.
  4. COI statement substance: if has_conflicts=true, statement must be non-empty.
  5. AI-disclosure: if used_ai=true, disclosure_sentence must be set.
  6. Editorial-board special rule: a board member cannot be first OR last.

Enrol flow writes to %LOCALAPPDATA%\\e156\\workbook\\<slug>\\authorship.json.
Check flow returns BLOCK/WARN/OK issues for `student validate --authorship`.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_ORCID_RE = re.compile(r"^(https://orcid\.org/)?\d{4}-\d{4}-\d{4}-\d{3}[0-9X]$")


@dataclass
class AuthorshipIssue:
    severity: str   # BLOCK | WARN
    field: str
    message: str


def _workbook_root() -> Path:
    lad = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(lad) / "e156" / "workbook"


def authorship_path(slug: str) -> Path:
    return _workbook_root() / slug / "authorship.json"


def _validate_author(role: str, a: dict) -> list[AuthorshipIssue]:
    out: list[AuthorshipIssue] = []
    if not isinstance(a, dict):
        out.append(AuthorshipIssue("BLOCK", role, f"{role} missing"))
        return out
    name = (a.get("full_name") or "").strip()
    email = (a.get("email") or "").strip()
    aff = (a.get("affiliation") or "").strip()
    if len(name) < 2:
        out.append(AuthorshipIssue("BLOCK", role, f"{role}.full_name missing or too short"))
    if not _EMAIL_RE.match(email):
        out.append(AuthorshipIssue("BLOCK", role, f"{role}.email invalid: {email!r}"))
    if len(aff) < 2:
        out.append(AuthorshipIssue("BLOCK", role, f"{role}.affiliation missing"))
    orcid = a.get("orcid")
    if orcid and not _ORCID_RE.match(orcid):
        out.append(AuthorshipIssue("WARN", role,
            f"{role}.orcid {orcid!r} does not look like a valid ORCID; "
            "expected `https://orcid.org/0000-0001-2345-6789`"))
    # CRediT roles, if given, must be from the canonical vocabulary
    roles = a.get("credit_roles") or []
    if not isinstance(roles, list):
        out.append(AuthorshipIssue("WARN", role,
            f"{role}.credit_roles must be a list (got {type(roles).__name__})"))
    else:
        valid_ids = {"conceptualization", "data-curation", "formal-analysis",
                     "funding-acquisition", "investigation", "methodology",
                     "project-administration", "resources", "software",
                     "supervision", "validation", "visualization",
                     "writing-original-draft", "writing-review-editing"}
        for r in roles:
            if r not in valid_ids:
                out.append(AuthorshipIssue("WARN", role,
                    f"{role}.credit_roles contains non-canonical id {r!r}; "
                    "see https://credit.niso.org/"))
    return out


def check(slug: str) -> list[AuthorshipIssue]:
    """Validate the authorship.json for <slug>. Returns list of issues."""
    path = authorship_path(slug)
    if not path.is_file():
        return [AuthorshipIssue("BLOCK", "authorship.json",
            f"No authorship record for `{slug}`. Run: student enroll-authors --slug {slug}")]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [AuthorshipIssue("BLOCK", "authorship.json",
            f"authorship.json is malformed: {e}")]

    out: list[AuthorshipIssue] = []
    for role in ("first_author", "middle_author", "last_author"):
        out.extend(_validate_author(role, data.get(role, {})))

    coi = data.get("conflicts_of_interest") or {}
    if coi.get("has_conflicts") is True and not (coi.get("statement") or "").strip():
        out.append(AuthorshipIssue("BLOCK", "conflicts_of_interest",
            "has_conflicts=true but statement is empty"))

    ai = data.get("ai_assistance_disclosed") or {}
    if ai.get("used_ai") is True and not (ai.get("disclosure_sentence") or "").strip():
        out.append(AuthorshipIssue("BLOCK", "ai_assistance_disclosed",
            "used_ai=true but disclosure_sentence is empty (ICMJE 2023)"))

    # Editorial-board rule
    board = data.get("editorial_board_coi") or {}
    if board.get("any_board_member") is True:
        for role in ("first_author", "last_author"):
            a = data.get(role) or {}
            if a.get("is_board_member_of_target_journal") is True:
                out.append(AuthorshipIssue("BLOCK", role,
                    f"{role} is a board member of the target journal; board members "
                    "must not hold first OR last position on submissions to that journal"))
        if not board.get("no_role_paragraph_included"):
            out.append(AuthorshipIssue("BLOCK", "editorial_board_coi.no_role_paragraph_included",
                "any_board_member=true but the no-role-in-editorial-decisions paragraph flag is not set"))
    return out


def save_authorship(slug: str, data: dict) -> Path:
    path = authorship_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


_CREDIT_ROLE_IDS = (
    "conceptualization", "data-curation", "formal-analysis", "funding-acquisition",
    "investigation", "methodology", "project-administration", "resources", "software",
    "supervision", "validation", "visualization", "writing-original-draft",
    "writing-review-editing",
)


def enrol_interactive(slug: str, *, input_fn=input, orcid_verify=True) -> Path:
    """Interactive enrol prompt. Pass input_fn for tests. Pass orcid_verify=False to
    skip live ORCID lookup (useful offline / in tests)."""
    print(f"Enrolling authors for paper `{slug}`.")
    print("The E156 contract requires three authors in fixed positions:")
    print("  first = you (the student)   middle = Mahmood Ahmad   last = your faculty supervisor")
    print("Press Ctrl+C to abort at any time; nothing is saved until you finish.\n")

    def ask_author(role_label: str, default_name: str = "", default_email: str = "",
                   default_aff: str = "") -> dict:
        print(f"--- {role_label} ---")
        name = input_fn(f"  Full name [{default_name}]: ").strip() or default_name
        email = input_fn(f"  Email [{default_email}]: ").strip() or default_email
        aff = input_fn(f"  Affiliation [{default_aff}]: ").strip() or default_aff
        orcid_raw = input_fn("  ORCID (optional, e.g. https://orcid.org/0000-0001-2345-6789): ").strip() or None
        orcid = orcid_raw
        orcid_ok: bool | None = None
        orcid_note: str | None = None
        if orcid_raw and orcid_verify:
            try:
                from tools.orcid_verify import verify_orcid  # noqa: WPS433
                r = verify_orcid(orcid_raw)
                orcid = r.orcid
                orcid_ok = r.verified
                orcid_note = r.note
                if r.verified:
                    print(f"    ORCID verified: {r.name or '(no public name)'}")
                else:
                    print(f"    ORCID NOT verified: {r.note}")
            except Exception as e:
                orcid_note = f"verifier error: {e}"
        board = input_fn("  On the editorial board of the target journal? [y/N]: ").strip().lower() == "y"
        # CRediT roles
        print("  CRediT roles (https://credit.niso.org/), comma-separated. Examples:")
        print("    conceptualization, methodology, formal-analysis, writing-original-draft")
        roles_raw = input_fn("  CRediT roles (blank for none): ").strip()
        roles = [r.strip() for r in roles_raw.split(",") if r.strip()]
        bad = [r for r in roles if r not in _CREDIT_ROLE_IDS]
        if bad:
            print(f"    WARN: unknown CRediT role(s) {bad}; accepted anyway — fix by hand if needed.")
        return {
            "full_name": name, "email": email, "affiliation": aff,
            "orcid": orcid, "orcid_verified": orcid_ok, "orcid_note": orcid_note,
            "is_board_member_of_target_journal": board,
            "credit_roles": roles,
        }

    data = {
        "first_author":  ask_author("First author (student)"),
        "middle_author": ask_author("Middle author", "Mahmood Ahmad", "mahmood.ahmad2@nhs.net", "Tahir Heart Institute"),
        "last_author":   ask_author("Last author (faculty supervisor)"),
    }

    has_coi = input_fn("\nAny conflicts of interest? [y/N]: ").strip().lower() == "y"
    coi_stmt = ""
    if has_coi:
        coi_stmt = input_fn("  COI statement (<=400 chars): ").strip()
    data["conflicts_of_interest"] = {"has_conflicts": has_coi, "statement": coi_stmt}

    funding_raw = input_fn("\nFunding sources (comma-separated; blank if none): ").strip()
    data["funding_sources"] = [s.strip() for s in funding_raw.split(",") if s.strip()]

    used_ai = input_fn("\nDid you use AI tools in drafting? [Y/n]: ").strip().lower() != "n"
    disclosure = ""
    if used_ai:
        disclosure = input_fn(
            "  Disclosure sentence (ICMJE 2023 requires; example: "
            "'Local Gemma 2 and Qwen 2.5 Coder models via the e156 student starter were used for language editing; authors accept full responsibility for all content.'): "
        ).strip()
    data["ai_assistance_disclosed"] = {
        "used_ai": used_ai,
        "disclosure_sentence": disclosure,
        "backends": ["ollama"] if used_ai else [],
    }

    any_board = any(
        (data[role].get("is_board_member_of_target_journal") is True)
        for role in ("first_author", "middle_author", "last_author")
    )
    data["editorial_board_coi"] = {
        "any_board_member": any_board,
        "no_role_paragraph_included": bool(any_board and input_fn(
            "\nAny author is on the target journal's editorial board. "
            "Have you included the 'no role in editorial decisions' paragraph? [y/N]: "
        ).strip().lower() == "y"),
        "journal_name_exact": "Synthesis",
    }
    return save_authorship(slug, data)


def format_issues(issues: list[AuthorshipIssue]) -> str:
    if not issues:
        return "[authorship] OK — contract satisfied."
    lines = [f"[authorship] {len(issues)} issue(s):"]
    for i in issues:
        lines.append(f"  [{i.severity}] {i.field}: {i.message}")
    return "\n".join(lines)
