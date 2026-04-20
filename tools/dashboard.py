"""Supervisor dashboard — single-file offline HTML snapshot of a workbook.

Reads a student's %LOCALAPPDATA%\\e156\\ state (workbook papers, baseline
corpus, audit log, consent fingerprint) and renders a self-contained
HTML file with no CDN references. A supervisor can open it in any
browser offline and see:

  - Every paper, its E156-validate verdict, word/sentence counts
  - Sentinel scan findings (if the pre-push log exists)
  - Baseline corpus with drift status per paper
  - Audit log timeline (hash-only, no prompt/response text)
  - Consent fingerprint (SHA256 only)

Usage:
  python tools/dashboard.py                       # writes to workbook/dashboard.html
  python tools/dashboard.py --out report.html     # custom output path
  student dashboard --out report.html             # via CLI

Emits zero external requests. Styles are inline. Safe for airgap review.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _e156_root() -> Path:
    lad = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(lad) / "e156"


def _gather_papers(workbook: Path) -> list[dict]:
    """Walk the workbook and collect one dict per paper."""
    papers: list[dict] = []
    if not workbook.is_dir():
        return papers
    for d in sorted(workbook.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        body_path = d / "current_body.txt"
        info: dict = {
            "slug": d.name,
            "has_body": body_path.is_file(),
            "e156_pass": None,
            "sentence_count": None,
            "word_count": None,
            "messages": [],
        }
        if body_path.is_file():
            try:
                from tools.validate_e156 import (
                    split_sentences, word_count, validate,
                )
                text = body_path.read_text(encoding="utf-8", errors="replace")
                info["sentence_count"] = len(split_sentences(text))
                info["word_count"] = word_count(text)
                ok, msgs = validate(text, label=d.name)
                info["e156_pass"] = ok
                info["messages"] = msgs
            except Exception as exc:  # noqa: BLE001
                info["messages"] = [f"validator error: {exc}"]
        papers.append(info)
    return papers


def _gather_baselines(e156_root: Path) -> list[dict]:
    bl = e156_root / "baseline.json"
    if not bl.is_file():
        return []
    try:
        data = json.loads(bl.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    out = []
    for paper_id, rec in sorted((data.get("records") or {}).items()):
        out.append({
            "paper_id": paper_id,
            "claim_id": rec.get("claim_id"),
            "recorded_at": rec.get("recorded_at"),
            "commit_sha": rec.get("commit_sha"),
            "pooled_estimate": rec.get("pooled_estimate"),
            "ci_lower": rec.get("ci_lower"),
            "ci_upper": rec.get("ci_upper"),
            "k": rec.get("k"),
            "i2": rec.get("i2"),
        })
    return out


def _gather_audit(e156_root: Path, *, limit: int = 50) -> list[dict]:
    log = e156_root / "logs" / "ai_calls.jsonl"
    if not log.is_file():
        return []
    entries: list[dict] = []
    try:
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    # Newest first, capped.
    return list(reversed(entries))[:limit]


def _gather_consent(e156_root: Path) -> dict | None:
    c = e156_root / ".consent.json"
    if not c.is_file():
        return None
    try:
        data = json.loads(c.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    # Fingerprint only, not raw name/email.
    import hashlib
    name = data.get("name", "")
    email = data.get("email", "")
    identity_sha = hashlib.sha256(
        (name.lower() + "|" + email.lower()).encode("utf-8")
    ).hexdigest()
    return {
        "identity_sha256": identity_sha,
        "cloud_enabled": data.get("cloud_enabled", False),
        "gemma_acknowledged_at": data.get("gemma_acknowledged_at"),
    }


def _gather_sentinel_findings(workbook: Path, *, limit: int = 50) -> list[dict]:
    f = workbook / "sentinel-findings.jsonl"
    if not f.is_file():
        return []
    out: list[dict] = []
    for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(out))[:limit]


def render_html(state: dict) -> str:
    """Return a complete HTML document string."""
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    esc = html.escape

    def _row_paper(p: dict) -> str:
        verdict = (
            "<span class='ok'>PASS</span>" if p["e156_pass"] is True
            else "<span class='fail'>FAIL</span>" if p["e156_pass"] is False
            else "<span class='na'>no body</span>"
        )
        msgs = "<br>".join(esc(m) for m in p["messages"]) or "&mdash;"
        return (
            f"<tr><td>{esc(p['slug'])}</td>"
            f"<td>{verdict}</td>"
            f"<td>{p['sentence_count'] if p['sentence_count'] is not None else '&mdash;'}</td>"
            f"<td>{p['word_count'] if p['word_count'] is not None else '&mdash;'}</td>"
            f"<td class='msgs'>{msgs}</td></tr>"
        )

    def _row_baseline(b: dict) -> str:
        pe = b["pooled_estimate"]
        pe_str = f"{pe:.4g}" if pe is not None else "&mdash;"
        if b["ci_lower"] is not None and b["ci_upper"] is not None:
            ci = f"[{b['ci_lower']:.4g}, {b['ci_upper']:.4g}]"
        else:
            ci = "&mdash;"
        k_str = str(b["k"]) if b["k"] is not None else "&mdash;"
        return (
            f"<tr><td>{esc(b['paper_id'])}</td>"
            f"<td><code>{esc(b['claim_id'] or '')}</code></td>"
            f"<td>{esc(b['recorded_at'] or '')}</td>"
            f"<td>{pe_str}</td>"
            f"<td>{ci}</td>"
            f"<td>{k_str}</td></tr>"
        )

    def _row_audit(e: dict) -> str:
        return (
            f"<tr><td class='mono'>{esc(e.get('ts',''))}</td>"
            f"<td>{esc(e.get('task_kind',''))}</td>"
            f"<td>{esc(e.get('backend',''))}</td>"
            f"<td>{esc(e.get('model',''))}</td>"
            f"<td class='mono'>{esc(e.get('prompt_sha_prefix',''))}</td>"
            f"<td class='mono'>{esc(e.get('response_sha_prefix',''))}</td>"
            f"<td>{e.get('response_words','')}</td>"
            f"<td>{e.get('elapsed_ms','')}</td></tr>"
        )

    def _row_finding(f: dict) -> str:
        sev = f.get("severity", "")
        sev_class = "sev-block" if sev == "BLOCK" else "sev-warn"
        return (
            f"<tr><td class='{sev_class}'>{esc(sev)}</td>"
            f"<td><code>{esc(f.get('rule_id',''))}</code></td>"
            f"<td class='mono'>{esc(f.get('path',''))}</td>"
            f"<td>{esc(str(f.get('line_no','')))}</td></tr>"
        )

    papers_rows = "\n".join(_row_paper(p) for p in state["papers"])
    baselines_rows = "\n".join(_row_baseline(b) for b in state["baselines"])
    audit_rows = "\n".join(_row_audit(e) for e in state["audit"])
    findings_rows = "\n".join(_row_finding(f) for f in state["findings"])

    consent = state["consent"]
    consent_block = (
        f"<p>Identity SHA256: <code>{esc(consent['identity_sha256'])}</code></p>"
        f"<p>Cloud enabled: <b>{consent['cloud_enabled']}</b></p>"
        f"<p>Gemma AGREE timestamp: {esc(consent.get('gemma_acknowledged_at') or 'none')}</p>"
        if consent else "<p><em>No consent record on this laptop.</em></p>"
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>e156 workbook dashboard</title>
<style>
body {{ font-family: -apple-system, system-ui, "Segoe UI", sans-serif; max-width: 1100px; margin: 2em auto; padding: 0 1em; color: #222; }}
h1 {{ border-bottom: 2px solid #335; padding-bottom: 0.2em; }}
h2 {{ margin-top: 2em; color: #335; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 14px; }}
th, td {{ border: 1px solid #ccc; padding: 6px 10px; text-align: left; vertical-align: top; }}
th {{ background: #f4f4f8; }}
tr:nth-child(even) td {{ background: #fafafc; }}
.ok {{ color: #0a7d0a; font-weight: bold; }}
.fail {{ color: #c00; font-weight: bold; }}
.na {{ color: #888; }}
.sev-block {{ color: #c00; font-weight: bold; }}
.sev-warn {{ color: #b80; font-weight: bold; }}
.mono {{ font-family: Consolas, Menlo, monospace; font-size: 12px; }}
.msgs {{ font-size: 13px; color: #555; }}
code {{ font-family: Consolas, Menlo, monospace; font-size: 12px; background: #f0f0f4; padding: 1px 4px; border-radius: 3px; }}
.meta {{ color: #666; font-size: 13px; }}
footer {{ margin-top: 3em; border-top: 1px solid #ccc; padding-top: 1em; font-size: 13px; color: #666; }}
</style>
</head>
<body>
<h1>e156 workbook dashboard</h1>
<p class="meta">Generated {esc(generated)} &middot; offline-safe, no external requests.</p>

<h2>Papers &amp; E156 compliance</h2>
{f"<table><thead><tr><th>Slug</th><th>Verdict</th><th>Sentences</th><th>Words</th><th>Validator messages</th></tr></thead><tbody>{papers_rows}</tbody></table>" if state["papers"] else "<p><em>No papers in the workbook yet.</em></p>"}

<h2>Numerical baselines</h2>
{f"<table><thead><tr><th>Paper</th><th>Claim ID</th><th>Recorded</th><th>Pooled</th><th>CI</th><th>k</th></tr></thead><tbody>{baselines_rows}</tbody></table>" if state["baselines"] else "<p><em>No baselines recorded yet. Use <code>student baseline record</code>.</em></p>"}

<h2>Pre-push sentinel findings (last 50)</h2>
{f"<table><thead><tr><th>Severity</th><th>Rule</th><th>Path</th><th>Line</th></tr></thead><tbody>{findings_rows}</tbody></table>" if state["findings"] else "<p><em>No findings log yet.</em></p>"}

<h2>AI call audit log (last 50, newest first)</h2>
{f"<table><thead><tr><th>UTC</th><th>Kind</th><th>Backend</th><th>Model</th><th>Prompt SHA</th><th>Response SHA</th><th>Words</th><th>ms</th></tr></thead><tbody>{audit_rows}</tbody></table>" if state["audit"] else "<p><em>No audit entries yet.</em></p>"}

<h2>Consent fingerprint</h2>
{consent_block}

<footer>
Generated by <code>tools/dashboard.py</code>. Opening this file in a browser makes zero external requests. Hashes only; no raw prompts, responses, names, or emails are included in this document.
</footer>
</body>
</html>
"""


def build(workbook: Path | None = None, *, e156_root: Path | None = None) -> str:
    e156 = e156_root or _e156_root()
    wb = workbook or (e156 / "workbook")
    state = {
        "papers":   _gather_papers(wb),
        "baselines": _gather_baselines(e156),
        "audit":    _gather_audit(e156),
        "findings": _gather_sentinel_findings(wb),
        "consent":  _gather_consent(e156),
    }
    return render_html(state)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=None,
                    help="output HTML path (default: <workbook>/dashboard.html)")
    args = ap.parse_args(argv)

    html_text = build()
    out = args.out
    if out is None:
        wb = _e156_root() / "workbook"
        wb.mkdir(parents=True, exist_ok=True)
        out = wb / "dashboard.html"
    out.write_text(html_text, encoding="utf-8")
    print(f"Dashboard written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
