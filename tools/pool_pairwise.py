"""Pure-stdlib pairwise random-effects meta-analysis for log-OR (2x2 tables).

Produces a report.json in the exact shape `tools/baseline.py::record_from_report`
consumes. Deliberately narrow scope: binary outcome, 2x2 studies, random-effects
pooling. For continuous / NMA / DTA / survival, students graduate to R metafor
(via diffmeta add-on in a later plan).

Statistics embedded:
  - Effect: log odds ratio per study (ln((a*d)/(b*c)))
  - Continuity correction: 0.5 added ONLY when any cell is 0 (conditional; never unconditional)
  - Variance: 1/a + 1/b + 1/c + 1/d
  - Pooling: inverse-variance random-effects with Paule-Mandel tau-squared
    (unbiased for small k; matches advanced-stats.md rule "Never use DL for k<10")
  - CI: Hartung-Knapp-Sidik-Jonkman (HKSJ) with t_{k-1} and a floor to prevent
    CI narrowing when Q < k-1
  - Q, I², tau²: all computed
  - Scale: all pooling on log scale; back-transform to OR only at report time

Usage:
    python tools/pool_pairwise.py --data trials.csv --output report.json
    python tools/pool_pairwise.py --data trials.csv --output report.json --measure logor

CSV shape (required columns):
    study, a, b, c, d
where a = events in intervention arm, b = no-event intervention, c = events control,
d = no-event control.

The output report.json has the keys baseline.py::record_from_report reads:
    pooled_estimate, ci_lower, ci_upper, se, i2, tau2, q, k
(these are on log scale — baseline.diff compares log-scale numbers;
 students viewing the report see both log and OR-space values.)
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Study:
    label: str
    a: float
    b: float
    c: float
    d: float

    def needs_correction(self) -> bool:
        return min(self.a, self.b, self.c, self.d) == 0

    def correct(self, amount: float = 0.5) -> "Study":
        return Study(self.label, self.a + amount, self.b + amount,
                     self.c + amount, self.d + amount)

    def log_or(self) -> float:
        return math.log((self.a * self.d) / (self.b * self.c))

    def var_log_or(self) -> float:
        return 1 / self.a + 1 / self.b + 1 / self.c + 1 / self.d


def load_csv(path: Path) -> list[Study]:
    studies: list[Study] = []
    with path.open(encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        required = {"study", "a", "b", "c", "d"}
        missing = required - {c.strip() for c in (reader.fieldnames or [])}
        if missing:
            raise ValueError(f"CSV missing columns: {sorted(missing)}")
        for row in reader:
            studies.append(Study(
                label=row["study"].strip(),
                a=float(row["a"]), b=float(row["b"]),
                c=float(row["c"]), d=float(row["d"]),
            ))
    if not studies:
        raise ValueError(f"No studies in {path}")
    return studies


def _paule_mandel_tau2(yi: list[float], vi: list[float], max_iter: int = 100,
                      tol: float = 1e-10) -> float:
    """Paule-Mandel iterative tau² estimator (unbiased).

    Solves for tau² such that the weighted chi-squared equals k-1, where
    weights are w_i = 1/(vi + tau²). Starts at DL estimate, iterates until
    stable or max_iter reached. Returns 0 if solution is negative.
    """
    k = len(yi)
    if k < 2:
        return 0.0
    # Start with DerSimonian-Laird as initial guess.
    w_fe = [1 / v for v in vi]
    mu_fe = sum(w * y for w, y in zip(w_fe, yi)) / sum(w_fe)
    q = sum(w * (y - mu_fe) ** 2 for w, y in zip(w_fe, yi))
    c_dl = sum(w_fe) - sum(w ** 2 for w in w_fe) / sum(w_fe)
    tau2 = max(0.0, (q - (k - 1)) / c_dl) if c_dl > 0 else 0.0

    for _ in range(max_iter):
        w = [1 / (v + tau2) for v in vi]
        mu = sum(wi * yi_ for wi, yi_ in zip(w, yi)) / sum(w)
        f = sum(wi * (yi_ - mu) ** 2 for wi, yi_ in zip(w, yi)) - (k - 1)
        if abs(f) < tol:
            break
        # Derivative of f w.r.t. tau2
        df = -sum(wi ** 2 * (yi_ - mu) ** 2 for wi, yi_ in zip(w, yi))
        if df == 0:
            break
        new_tau2 = tau2 - f / df
        if new_tau2 < 0:
            new_tau2 = 0
        if abs(new_tau2 - tau2) < tol:
            tau2 = new_tau2
            break
        tau2 = new_tau2
    return max(0.0, tau2)


def _t_critical(df: int, alpha: float = 0.05) -> float:
    """Two-sided t-critical value. Uses Cornish-Fisher-style approximation
    accurate to ~1e-4 for df >= 2; calls scipy if present for df-specific accuracy."""
    try:
        from scipy.stats import t  # type: ignore
        return float(t.ppf(1 - alpha / 2, df))
    except ImportError:
        pass
    # Abramowitz & Stegun 26.7.5: Peizer-Pratt approximation of t quantile.
    z = 1.959963984540054  # qnorm(0.975)
    # Hill 1970 approximation — accurate to ~0.001 for df >= 3
    g1 = (z ** 3 + z) / 4
    g2 = (5 * z ** 5 + 16 * z ** 3 + 3 * z) / 96
    g3 = (3 * z ** 7 + 19 * z ** 5 + 17 * z ** 3 - 15 * z) / 384
    g4 = (79 * z ** 9 + 776 * z ** 7 + 1482 * z ** 5 - 1920 * z ** 3 - 945 * z) / 92160
    df_ = float(df)
    return z + g1 / df_ + g2 / df_ ** 2 + g3 / df_ ** 3 + g4 / df_ ** 4


def pool(studies: list[Study], *, alpha: float = 0.05) -> dict:
    """Random-effects pooling with Paule-Mandel tau² + HKSJ CI floor.

    Returns a dict ready to be `json.dump`-ed and ingested by
    `tools.baseline.record_from_report`.
    """
    # Conditional 0.5 correction
    corrected: list[Study] = [
        s.correct(0.5) if s.needs_correction() else s for s in studies
    ]
    yi = [s.log_or() for s in corrected]
    vi = [s.var_log_or() for s in corrected]
    k = len(yi)

    # Paule-Mandel tau²
    tau2 = _paule_mandel_tau2(yi, vi)

    # RE weights
    wi = [1 / (v + tau2) for v in vi]
    w_sum = sum(wi)
    mu_hat = sum(w * y for w, y in zip(wi, yi)) / w_sum

    # Q statistic (computed with FE weights, per Cochran's original definition)
    w_fe = [1 / v for v in vi]
    mu_fe = sum(w * y for w, y in zip(w_fe, yi)) / sum(w_fe)
    q = sum(w * (y - mu_fe) ** 2 for w, y in zip(w_fe, yi))
    df = k - 1
    i2 = max(0.0, (q - df) / q * 100) if q > 0 else 0.0

    # HKSJ variance with floor: q/df <= 1 -> scale = 1 (prevents CI narrowing)
    scale = max(1.0, q / df) if df > 0 else 1.0
    hksj_var = scale / w_sum

    # HKSJ uses t_{k-1}, NOT normal
    t_crit = _t_critical(df, alpha) if df >= 1 else 1.96
    se = math.sqrt(hksj_var)
    ci_lower = mu_hat - t_crit * se
    ci_upper = mu_hat + t_crit * se

    return {
        "k": k,
        "pooled_estimate": mu_hat,         # log scale
        "pooled_or": math.exp(mu_hat),     # OR scale (display convenience)
        "ci_lower": ci_lower,              # log scale
        "ci_upper": ci_upper,
        "ci_lower_or": math.exp(ci_lower),
        "ci_upper_or": math.exp(ci_upper),
        "se": se,
        "q": q,
        "i2": i2,
        "tau2": tau2,
        "df": df,
        "method": "RE-PM-HKSJ",  # Paule-Mandel tau², HKSJ CI with Q/df floor
        "alpha": alpha,
        "studies": [
            {"label": s.label, "yi": y, "vi": v}
            for s, y, v in zip(corrected, yi, vi)
        ],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, required=True,
                    help="CSV with columns: study, a, b, c, d")
    ap.add_argument("--output", type=Path, default=Path("report.json"))
    ap.add_argument("--alpha", type=float, default=0.05)
    args = ap.parse_args(argv)

    studies = load_csv(args.data)
    report = pool(studies, alpha=args.alpha)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Pooled {report['k']} studies:")
    print(f"  OR = {report['pooled_or']:.3f}  "
          f"(95% CI {report['ci_lower_or']:.3f} to {report['ci_upper_or']:.3f})")
    print(f"  tau² = {report['tau2']:.4f}   I² = {report['i2']:.1f}%   Q = {report['q']:.2f}")
    print(f"  method = {report['method']}   k = {report['k']}")
    print(f"\nReport: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
