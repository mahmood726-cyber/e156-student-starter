"""ORCID verifier (stdlib urllib, no auth, public-record only).

Validates an ORCID iD:
  1. Checksum via ISO 7064 MOD 11-2 (offline — no network needed).
  2. Live public-record lookup at https://pub.orcid.org/v3.0/<id>/record
     with Accept: application/json. Returns name + verified flag.

Cached at %LOCALAPPDATA%\\e156\\logs\\orcid-cache\\<id>.json so a student
who looked up an ORCID once can verify offline thereafter.

Usage:
    python tools/orcid_verify.py --orcid 0000-0001-2345-6789
    from tools.orcid_verify import verify_orcid, validate_checksum
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from tools.project_paths import e156_state_root


_ORCID_FULL_RE = re.compile(r"^(https://orcid\.org/)?(\d{4}-\d{4}-\d{4}-\d{3}[0-9X])$")
_PUB_ORCID_URL = "https://pub.orcid.org/v3.0/{id}/record"


@dataclass
class OrcidResult:
    orcid: str                 # normalised bare iD, e.g. 0000-0001-2345-6789
    valid_format: bool
    verified: bool             # True if live public record matched
    name: str | None = None
    note: str = ""


def normalise(orcid: str) -> str | None:
    """Strip optional URL prefix; uppercase the check digit (X). Return None if malformed."""
    if not orcid:
        return None
    s = orcid.strip()
    # Uppercase only the trailing check-digit slot; preserve URL scheme case.
    if len(s) >= 1:
        s = s[:-1] + s[-1].upper()
    m = _ORCID_FULL_RE.match(s)
    if not m:
        return None
    return m.group(2)


def validate_checksum(orcid: str) -> bool:
    """ISO 7064 MOD 11-2 check digit. Works offline."""
    bare = normalise(orcid)
    if bare is None:
        return False
    digits = bare.replace("-", "")
    if len(digits) != 16:
        return False
    total = 0
    for ch in digits[:-1]:
        if not ch.isdigit():
            return False
        total = (total + int(ch)) * 2
    remainder = total % 11
    result = (12 - remainder) % 11
    expected = "X" if result == 10 else str(result)
    return digits[-1] == expected


def _cache_dir() -> Path:
    d = e156_state_root() / "logs" / "orcid-cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def verify_orcid(orcid: str, *, timeout: float = 10.0,
                 use_cache: bool = True) -> OrcidResult:
    bare = normalise(orcid)
    if bare is None:
        return OrcidResult(orcid=orcid, valid_format=False, verified=False,
                           note="malformed ORCID iD")
    if not validate_checksum(bare):
        return OrcidResult(orcid=bare, valid_format=False, verified=False,
                           note="checksum failed")

    cache_file = _cache_dir() / f"{bare}.json"
    if use_cache and cache_file.is_file():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            return OrcidResult(
                orcid=bare, valid_format=True,
                verified=bool(data.get("verified")),
                name=data.get("name"),
                note=(data.get("note", "") + " [cache]").strip(),
            )
        except (OSError, json.JSONDecodeError):
            pass

    url = _PUB_ORCID_URL.format(id=bare)
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "e156-student-starter/0.3",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        note = f"HTTP {e.code}"
        if e.code == 404:
            out = {"verified": False, "name": None, "note": "ORCID iD not found"}
            try:
                cache_file.write_text(json.dumps(out), encoding="utf-8")
            except OSError:
                pass
            return OrcidResult(orcid=bare, valid_format=True, verified=False,
                               name=None, note=out["note"])
        return OrcidResult(orcid=bare, valid_format=True, verified=False,
                           note=note)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return OrcidResult(orcid=bare, valid_format=True, verified=False,
                           note=f"network: {type(e).__name__}")

    # v3 shape: person.name.given-names.value, person.name.family-name.value
    name = None
    try:
        pn = data.get("person", {}).get("name", {}) or {}
        given = (pn.get("given-names") or {}).get("value") or ""
        family = (pn.get("family-name") or {}).get("value") or ""
        if given or family:
            name = f"{given} {family}".strip()
    except (AttributeError, TypeError):
        pass

    out = {"verified": True, "name": name, "note": "ORCID public record matched"}
    try:
        cache_file.write_text(json.dumps(out), encoding="utf-8")
    except OSError:
        pass
    return OrcidResult(orcid=bare, valid_format=True, verified=True,
                       name=name, note=out["note"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--orcid", required=True)
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args(argv)
    r = verify_orcid(args.orcid, use_cache=not args.no_cache)
    flag = "OK " if r.verified else "FAIL"
    print(f"[{flag}] {r.orcid}  valid_format={r.valid_format}  name={r.name or '-'}  {r.note}")
    return 0 if r.verified else 1


if __name__ == "__main__":
    sys.exit(main())
