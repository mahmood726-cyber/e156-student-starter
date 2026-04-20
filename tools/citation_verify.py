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
_PUBMED_ESEARCH  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_PUBMED_ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
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
    title_hint: str | None = None  # optional title hint for tighter matching

    def cache_key(self) -> str:
        key = f"{self.first_author.lower()}|{self.year}"
        if self.title_hint:
            key += "|" + self.title_hint.lower()[:80]
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _normalise_title(t: str) -> str:
    """Lowercase, strip punctuation and common stopwords for title comparison."""
    t = re.sub(r"[^\w\s]", " ", t.lower())
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _title_similarity(a: str, b: str) -> float:
    """Return 0.0-1.0 similarity of two titles, based on word-multiset Jaccard."""
    from collections import Counter
    wa = Counter(_normalise_title(a).split())
    wb = Counter(_normalise_title(b).split())
    if not wa or not wb:
        return 0.0
    inter = sum((wa & wb).values())
    union = sum((wa | wb).values())
    return inter / union if union else 0.0


@dataclass
class Verification:
    citation: Citation
    verified: bool
    pmid: str | None = None
    title: str | None = None
    note: str = ""
    # Confidence of the match: "high" (title matches title_hint),
    # "medium" (author+year match + esummary retrieved title),
    # "low" (surname+year only; multiple candidates exist), None if unverified.
    confidence: str | None = None
    candidate_pmids: list[str] = field(default_factory=list)


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


def _fetch_titles(pmids: list[str], *, timeout: float = 10.0) -> dict[str, str]:
    """Second-pass: fetch titles for candidate PMIDs via esummary."""
    if not pmids:
        return {}
    params = {
        "db": "pubmed", "id": ",".join(pmids), "retmode": "json",
        "tool": _UA_TOOL, "email": _UA_EMAIL,
    }
    url = f"{_PUBMED_ESUMMARY}?{urllib.parse.urlencode(params)}"
    _throttle()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return {}
    result = data.get("result", {})
    out: dict[str, str] = {}
    for pid in pmids:
        rec = result.get(pid)
        if isinstance(rec, dict):
            title = rec.get("title", "")
            if title:
                out[pid] = title
    return out


def verify_pubmed(cit: Citation, *, timeout: float = 10.0,
                  use_cache: bool = True, retmax: int = 5) -> Verification:
    """Look up `cit` on PubMed via E-utilities esearch+esummary.

    Two passes:
      1. esearch with `author[Author] AND year[dp]` -> up to `retmax` candidate PMIDs
      2. If title_hint is present, esummary the candidates and pick the one
         whose title best matches the hint (Jaccard on word multiset).
      3. If no hint, flag confidence=low when multiple candidates exist.

    Cached by cache_key (hash of author+year+title_hint[:80]). Network failures
    return unverified with note, never raise.
    """
    key = cit.cache_key()
    if use_cache:
        cached = _cache_get(key)
        if cached is not None:
            return Verification(
                citation=cit, verified=cached["verified"],
                pmid=cached.get("pmid"), title=cached.get("title"),
                note=cached.get("note", "") + " [cache]",
                confidence=cached.get("confidence"),
                candidate_pmids=cached.get("candidate_pmids", []),
            )

    term = f'{cit.first_author}[Author] AND {cit.year}[dp]'
    params = {
        "db": "pubmed", "term": term, "retmode": "json", "retmax": str(retmax),
        "tool": _UA_TOOL, "email": _UA_EMAIL,
    }
    url = f"{_PUBMED_ESEARCH}?{urllib.parse.urlencode(params)}"
    _throttle()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return Verification(
            citation=cit, verified=False, note=f"network: {type(e).__name__}",
        )
    idlist = data.get("esearchresult", {}).get("idlist", [])
    if not idlist:
        result = {"verified": False, "pmid": None, "title": None,
                  "note": "no PubMed match", "confidence": None,
                  "candidate_pmids": []}
        _cache_put(key, result)
        return Verification(citation=cit, **result)

    # Second pass: fetch titles for candidates, score against title_hint
    titles = _fetch_titles(idlist, timeout=timeout)
    best_pmid = idlist[0]
    best_title = titles.get(best_pmid)
    confidence = "low"
    note = f"PubMed match ({len(idlist)} candidate{'s' if len(idlist) != 1 else ''})"

    if cit.title_hint and titles:
        scored = [(pid, _title_similarity(cit.title_hint, titles.get(pid, ""))) for pid in idlist]
        scored.sort(key=lambda x: -x[1])
        top_pid, top_sim = scored[0]
        if top_sim >= 0.5:
            best_pmid = top_pid
            best_title = titles.get(top_pid)
            confidence = "high"
            note = f"PubMed match title-similarity={top_sim:.2f}"
        elif top_sim >= 0.25:
            best_pmid = top_pid
            best_title = titles.get(top_pid)
            confidence = "medium"
            note = f"PubMed match title-similarity={top_sim:.2f} (partial)"
        else:
            # No candidate's title matches hint -> treat as unverified hallucination
            result = {"verified": False, "pmid": None, "title": titles.get(idlist[0]),
                      "note": f"author+year matched but title_hint unmatched (best sim={top_sim:.2f})",
                      "confidence": None, "candidate_pmids": idlist}
            _cache_put(key, result)
            return Verification(citation=cit, **result)
    elif len(idlist) == 1:
        confidence = "medium"
        note = "PubMed unique match"

    result = {"verified": True, "pmid": best_pmid, "title": best_title,
              "note": note, "confidence": confidence, "candidate_pmids": idlist}
    _cache_put(key, result)
    return Verification(citation=cit, **result)


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
        conf = f" ({v.confidence})" if v.confidence else ""
        lines.append(f"  [{flag}] {v.citation.first_author} {v.citation.year}{conf}  "
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
