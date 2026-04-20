"""Citation verifier via PubMed E-utilities (stdlib-only, cached, offline-aware).

Extracts author-year citations from an E156 body and checks each against
PubMed. Hallucinated citations (no PMID match) are flagged as BLOCK.

Design decisions (per portfolio survey):
  - No Biopython dep (too heavy for Uganda laptop).
  - Pure urllib + json + xml.etree. Works offline against the cache if the
    student lost connectivity mid-draft.
  - Cache lives at %LOCALAPPDATA%\\e156\\logs\\citation-cache\\<sha-of-query>.json
    Never expires (student re-runs offline = cached result).
  - Rate-limited to 3 req/s (PubMed no-key limit). Honours `tool=` and `email=`
    etiquette params.
  - Backends: pubmed (default), openalex (optional, future).

Extraction patterns (regex on the body):
  - `(Smith 2020)`, `(Smith and Jones 2020)`, `(Smith et al. 2020)`
  - `Smith et al., 2020`, `Smith 2020`

Usage:
    from tools.citation_verify import extract_citations, verify_all
    cits = extract_citations(open('body.txt').read())
    results = verify_all(cits)
    for c, r in zip(cits, results):
        print(c, r)

CLI:
    python tools/citation_verify.py --body path/to/body.txt --backend pubmed
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from tools.project_paths import e156_state_root


_UA_TOOL = "e156-student-starter"
_UA_EMAIL = "noreply@synthesis-medicine.org"  # NCBI etiquette; can override
_PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_MIN_INTERVAL_S = 0.34  # 3 req/sec cap
_last_request_ts = 0.0


_SURNAME = r"[A-Z][a-zA-Z'\-]{1,40}"
_YEAR = r"(?:19|20)\d{2}[a-z]?"

_CITATION_PATTERNS: list[re.Pattern[str]] = [
    # (Smith et al. 2020), (Smith et al., 2020), (Smith and Jones 2020)
    re.compile(
        rf"\((?P<first>{_SURNAME})(?:\s+(?:et\s+al\.?|and\s+{_SURNAME}))?,?\s+(?P<year>{_YEAR})\)"
    ),
    # Smith et al. (2020), Smith and Jones (2020)
    re.compile(
        rf"(?P<first>{_SURNAME})(?:\s+(?:et\s+al\.?|and\s+{_SURNAME}))?\s+\((?P<year>{_YEAR})\)"
    ),
    # Smith et al., 2020 (prose inline with comma)
    re.compile(
        rf"(?P<first>{_SURNAME})\s+et\s+al\.?,?\s+(?P<year>{_YEAR})"
    ),
]


@dataclass
class Citation:
    raw: str
    first_author: str
    year: str

    def cache_key(self) -> str:
        return hashlib.sha256(
            f"{self.first_author.lower()}|{self.year}".encode("utf-8")
        ).hexdigest()[:16]


@dataclass
class Verification:
    citation: Citation
    verified: bool
    pmid: str | None = None
    title: str | None = None
    note: str = ""


def extract_citations(text: str) -> list[Citation]:
    """Return deduped citations found in `text`, preserving first-seen order."""
    seen: set[tuple[str, str]] = set()
    out: list[Citation] = []
    for pat in _CITATION_PATTERNS:
        for m in pat.finditer(text):
            first = m.group("first")
            year = m.group("year")
            if first in {"Table", "Figure", "Equation", "Appendix"}:
                continue
            key = (first.lower(), year)
            if key in seen:
                continue
            seen.add(key)
            out.append(Citation(raw=m.group(0), first_author=first, year=year))
    return out


def _cache_dir() -> Path:
    d = e156_state_root() / "logs" / "citation-cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_get(key: str) -> dict | None:
    p = _cache_dir() / f"{key}.json"
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
    return None


def _cache_put(key: str, payload: dict) -> None:
    p = _cache_dir() / f"{key}.json"
    try:
        p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        pass


def _throttle() -> None:
    global _last_request_ts
    dt = time.monotonic() - _last_request_ts
    if dt < _MIN_INTERVAL_S:
        time.sleep(_MIN_INTERVAL_S - dt)
    _last_request_ts = time.monotonic()


def verify_pubmed(cit: Citation, *, timeout: float = 10.0,
                  use_cache: bool = True) -> Verification:
    """Look up `cit` on PubMed via E-utilities esearch. Cached; offline-safe."""
    key = cit.cache_key()
    if use_cache:
        cached = _cache_get(key)
        if cached is not None:
            return Verification(
                citation=cit, verified=cached["verified"],
                pmid=cached.get("pmid"), title=cached.get("title"),
                note=cached.get("note", "") + " [cache]",
            )

    # Query: `<first_author>[Author] AND <year>[dp]`
    term = f'{cit.first_author}[Author] AND {cit.year}[dp]'
    params = {
        "db": "pubmed", "term": term, "retmode": "json", "retmax": "3",
        "tool": _UA_TOOL, "email": _UA_EMAIL,
    }
    url = f"{_PUBMED_ESEARCH}?{urllib.parse.urlencode(params)}"
    _throttle()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        # Network failure -> treat as "unknown" rather than "hallucinated"
        return Verification(
            citation=cit, verified=False, note=f"network: {type(e).__name__}",
        )
    idlist = data.get("esearchresult", {}).get("idlist", [])
    if not idlist:
        result = {"verified": False, "pmid": None, "title": None,
                  "note": "no PubMed match"}
    else:
        pmid = idlist[0]
        result = {"verified": True, "pmid": pmid, "title": None,
                  "note": "PubMed match"}
    _cache_put(key, result)
    return Verification(
        citation=cit, verified=result["verified"],
        pmid=result.get("pmid"), title=result.get("title"),
        note=result["note"],
    )


def verify_all(citations: list[Citation], *, backend: str = "pubmed",
               use_cache: bool = True) -> list[Verification]:
    if backend != "pubmed":
        raise ValueError(f"unknown backend {backend!r} (only 'pubmed' implemented)")
    return [verify_pubmed(c, use_cache=use_cache) for c in citations]


def format_report(verifications: list[Verification]) -> str:
    if not verifications:
        return "[citations] no author-year citations found in body."
    verified = sum(1 for v in verifications if v.verified)
    unverified = len(verifications) - verified
    lines = [f"[citations] {verified}/{len(verifications)} verified "
             f"({unverified} unverified):"]
    for v in verifications:
        flag = "OK " if v.verified else "FAIL"
        pmid = f" PMID:{v.pmid}" if v.pmid else ""
        lines.append(f"  [{flag}] {v.citation.first_author} {v.citation.year}  "
                     f"{v.note}{pmid}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--body", type=Path, required=True)
    ap.add_argument("--backend", default="pubmed", choices=["pubmed"])
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args(argv)

    text = args.body.read_text(encoding="utf-8", errors="replace")
    cits = extract_citations(text)
    verifications = verify_all(cits, backend=args.backend, use_cache=not args.no_cache)
    print(format_report(verifications))
    # Exit 1 if any unverified citation
    return 0 if all(v.verified for v in verifications) else 1


if __name__ == "__main__":
    sys.exit(main())
