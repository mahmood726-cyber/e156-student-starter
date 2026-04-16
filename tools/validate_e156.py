"""E156 format validator — pure stdlib, no AI needed.

Checks the 4 rules of the E156 micro-paper format:
  1. Exactly 7 sentences (S1 Question, S2 Dataset, S3 Method,
     S4 Result, S5 Robustness, S6 Interpretation, S7 Boundary).
  2. At most 156 words.
  3. Single paragraph (no double-blank lines inside the body).
  4. No citation markers ([1], (Smith 2020)), URLs, or code fences
     in the body text — those belong in SUBMISSION METADATA, not prose.

Usage:
  python validate_e156.py path/to/your_rewrite.txt
  python validate_e156.py path/to/workbook.txt --all  (check every
     YOUR REWRITE block in a workbook file)

Exit codes:
  0   every check passed
  1   one or more checks failed (details printed)
  2   bad arguments
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


MAX_WORDS = 156
EXPECTED_SENTENCES = 7


_CITATION_PATTERNS = [
    re.compile(r"\[\d+(?:[,\-]\d+)*\]"),       # [1], [1,2], [1-3]
    re.compile(r"\([A-Z][a-zA-Z\-]+\s+(?:et al\.?\s+)?\d{4}[a-z]?\)"),  # (Smith 2020)
    re.compile(r"https?://\S+"),                # URLs
    re.compile(r"```"),                         # code fences
    re.compile(r"doi:\s*10\.\d+"),              # DOIs
]


def split_sentences(text: str) -> list[str]:
    """Naive sentence splitter that handles common abbreviations.

    We deliberately don't use nltk — keeping this pure-stdlib so students
    don't need to `pip install` anything to run the validator offline.
    """
    cleaned = re.sub(r"\s+", " ", text.strip())
    if not cleaned:
        return []
    # Protect common abbreviations so we don't over-split.
    protected = cleaned
    for abbr in ("e.g.", "i.e.", "vs.", "Dr.", "Fig.", "No.", "Eq.",
                 "Ref.", "St.", "Mr.", "Mrs.", "Ms.", "cf.", "et al."):
        protected = protected.replace(abbr, abbr.replace(".", "\x00"))
    # Protect decimal numbers (1.5, 95.2) — lambda because \xNN in a
    # regex replacement template is parsed, not emitted literally.
    protected = re.sub(
        r"(\d)\.(\d)", lambda m: m.group(1) + "\x00" + m.group(2), protected
    )
    # Split on sentence-final punctuation followed by whitespace + capital letter.
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", protected)
    # Restore dots.
    return [p.replace("\x00", ".").strip() for p in parts if p.strip()]


def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text.strip()))


def check_citations(text: str) -> list[str]:
    """Return a list of offending spans (empty if clean)."""
    out = []
    for pat in _CITATION_PATTERNS:
        for m in pat.finditer(text):
            out.append(m.group(0))
    return out


def validate(body: str, *, label: str = "body") -> tuple[bool, list[str]]:
    """Return (pass?, list_of_messages)."""
    msgs: list[str] = []
    body = body.strip()
    if not body:
        return False, [f"{label}: empty"]

    # Rule 1: exactly 7 sentences.
    sents = split_sentences(body)
    if len(sents) != EXPECTED_SENTENCES:
        msgs.append(
            f"{label}: expected {EXPECTED_SENTENCES} sentences, "
            f"got {len(sents)}"
        )

    # Rule 2: ≤ 156 words.
    n = word_count(body)
    if n > MAX_WORDS:
        msgs.append(f"{label}: {n} words > max {MAX_WORDS}")

    # Rule 3: single paragraph (no blank line mid-body).
    if re.search(r"\n\s*\n", body):
        msgs.append(f"{label}: contains a blank line — must be single paragraph")

    # Rule 4: no citations / URLs / code fences.
    offenders = check_citations(body)
    if offenders:
        msgs.append(
            f"{label}: remove citation/URL/code markers from prose body: "
            + ", ".join(repr(o) for o in offenders[:5])
        )

    if not msgs:
        msgs.append(
            f"{label}: PASS ({len(sents)} sentences, {n} words, "
            f"{n} <= {MAX_WORDS})"
        )
    return (len(msgs) == 1 and msgs[0].endswith("<= 156)")), msgs


def _iter_workbook_rewrites(text: str):
    """Yield (entry_label, rewrite_body) for each `YOUR REWRITE` block.

    Block shape (from C:/E156/rewrite-workbook.txt):

        [N/M] ProjectName
        ...
        YOUR REWRITE (at most 156 words, 7 sentences):

        <body here>

        SUBMISSION METADATA:
    """
    blocks = re.split(r"\n={60,}\n", text)
    for block in blocks:
        m_head = re.search(r"\[(\d+)/\d+\]\s+(\S+)", block)
        m_body = re.search(
            r"YOUR REWRITE\s*\(at most 156 words, 7 sentences\):\s*\n(.+?)\n\s*\n",
            block,
            re.DOTALL,
        )
        if m_head and m_body:
            yield f"[{m_head.group(1)}] {m_head.group(2)}", m_body.group(1).strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="path to a .txt file OR a workbook file with --all")
    ap.add_argument("--all", action="store_true",
                    help="if path is a workbook, check every YOUR REWRITE block")
    args = ap.parse_args()

    path = Path(args.path)
    if not path.is_file():
        print(f"error: {path} is not a file", file=sys.stderr)
        return 2

    text = path.read_text(encoding="utf-8", errors="replace")

    all_pass = True
    if args.all:
        rewrites = list(_iter_workbook_rewrites(text))
        if not rewrites:
            print("error: no YOUR REWRITE blocks found in this file", file=sys.stderr)
            return 2
        passes = 0
        for label, body in rewrites:
            ok, msgs = validate(body, label=label)
            for m in msgs:
                print(m)
            if ok:
                passes += 1
            else:
                all_pass = False
        print(f"\n{passes}/{len(rewrites)} blocks pass.")
    else:
        ok, msgs = validate(text, label=str(path))
        for m in msgs:
            print(m)
        if not ok:
            all_pass = False

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
