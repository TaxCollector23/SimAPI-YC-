"""
The "unsuitable for training" output class -- data that is physically
VALID but harmful to learn from.

The spec calls this out as the class that barely exists in the old
engine, and as the one carrying the most value for the actual consumer:
"Your data never covers the high-AoA regime you intend to deploy in" is
worth more to an ML engineer than any row-level flag.

That framing drives a design decision here: most findings in this module
are DATASET-level, not row-level. A coverage gap is not a property of any
row -- flagging rows for it would be meaningless, since every individual
row is fine. Only duplicates (handled in rules.py) and extrapolation-risk
rows are genuinely per-row. So `SuitabilityFinding.row_ids` is
deliberately allowed to be empty, and the report surfaces these as
dataset-level warnings rather than forcing them into the row-exclusion
list where they would read as "throw these rows away".

Five sub-kinds, per the spec:
  duplicates            -- in rules.py (structural), listed here for completeness
  design_space_gap      -- unsampled voids in the factor space
  feature_target_leakage-- a "feature" that is an exact function of the target
  regime_imbalance      -- one regime dominates; the model will ignore the rest
  extrapolation_risk    -- rows at the extreme hull of the sampled space
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# A gap must be a real void, not just the low-density tail of a normal
# distribution -- required to be this many times the median inter-sample
# spacing before it counts.
GAP_RATIO_THRESHOLD = 6.0
MIN_ROWS_FOR_COVERAGE = 20
# Near-perfect correlation with the target. Deliberately very high: real
# physics has genuinely strong correlations (lift vs. AoA in the linear
# regime) that are legitimate features, not leakage. Only an essentially
# deterministic relationship indicates the target leaked into a feature.
LEAKAGE_R2 = 0.9995
IMBALANCE_DOMINANCE = 0.80   # one bin holding >80% of mass
EXTRAPOLATION_TAIL = 0.02    # rows beyond the 2%/98% hull edge


@dataclass
class SuitabilityFinding:
    kind: str                       # design_space_gap | feature_target_leakage | ...
    detail: str                     # plain-English, ML-engineer-facing
    columns: tuple[str, ...] = ()
    row_ids: list[int] = field(default_factory=list)   # often empty -- see module docstring
    severity: str = "warning"       # warning | info


def _numeric(data: pd.DataFrame, col: str) -> np.ndarray | None:
    s = pd.to_numeric(data[col], errors="coerce").dropna()
    if len(s) < MIN_ROWS_FOR_COVERAGE:
        return None
    return s.to_numpy(dtype=float)


def find_design_space_gaps(data: pd.DataFrame, columns: list[str]) -> list[SuitabilityFinding]:
    """A void in the sampled range of a factor. Detected as a gap between
    consecutive sorted samples that dwarfs the typical spacing -- scale-free,
    so it works equally on a 0-15 deg AoA sweep and a 1e5-1e7 Reynolds sweep."""
    out = []
    for col in columns:
        v = _numeric(data, col)
        if v is None:
            continue
        u = np.unique(v)
        if len(u) < MIN_ROWS_FOR_COVERAGE:
            continue  # a coarse factorial design is intentional, not a gap
        diffs = np.diff(u)
        med = float(np.median(diffs))
        if med <= 0:
            continue
        biggest = float(diffs.max())
        if biggest > GAP_RATIO_THRESHOLD * med:
            i = int(np.argmax(diffs))
            out.append(SuitabilityFinding(
                kind="design_space_gap",
                columns=(col,),
                detail=(f"{col} is never sampled between {u[i]:.4g} and {u[i+1]:.4g} "
                        f"(a {biggest/med:.0f}x gap vs. typical spacing). A model trained "
                        f"here will be interpolating blind across that band."),
            ))
    return out


def find_feature_target_leakage(data: pd.DataFrame, columns: list[str]) -> list[SuitabilityFinding]:
    """Two columns related by an essentially deterministic affine map. If one
    is the intended target, the other hands the model the answer, and offline
    metrics will look excellent while the model has learned nothing."""
    out = []
    cols = [c for c in columns if _numeric(data, c) is not None]
    for i, a in enumerate(cols):
        va = _numeric(data, a)
        for b in cols[i + 1:]:
            vb = _numeric(data, b)
            if va is None or vb is None or len(va) != len(vb):
                continue
            if np.std(va) == 0 or np.std(vb) == 0:
                continue
            r = float(np.corrcoef(va, vb)[0, 1])
            if not np.isfinite(r):
                continue
            if r * r >= LEAKAGE_R2:
                out.append(SuitabilityFinding(
                    kind="feature_target_leakage",
                    columns=(a, b),
                    detail=(f"{a} and {b} are related deterministically (R^2={r*r:.5f}). "
                            f"If either is the training target, the other leaks it -- "
                            f"validation scores will be optimistic and meaningless."),
                ))
    return out


def find_regime_imbalance(data: pd.DataFrame, columns: list[str]) -> list[SuitabilityFinding]:
    """One regime dominating the sample. A model fit on this minimises loss by
    ignoring the sparse regimes entirely -- which are often exactly the ones
    the deployment cares about (stall, transonic, high-AoA)."""
    out = []
    for col in columns:
        v = _numeric(data, col)
        if v is None:
            continue
        lo, hi = float(v.min()), float(v.max())
        if hi <= lo:
            continue
        counts, edges = np.histogram(v, bins=10, range=(lo, hi))
        frac = counts.max() / counts.sum()
        if frac > IMBALANCE_DOMINANCE:
            j = int(np.argmax(counts))
            out.append(SuitabilityFinding(
                kind="regime_imbalance",
                columns=(col,),
                detail=(f"{frac*100:.0f}% of rows fall in a single {col} band "
                        f"[{edges[j]:.4g}, {edges[j+1]:.4g}]. The remaining regimes are "
                        f"too sparse to learn; the model will effectively ignore them."),
            ))
    return out


def find_extrapolation_risk(data: pd.DataFrame, columns: list[str]) -> list[SuitabilityFinding]:
    """Rows sitting at the extreme edge of the sampled hull. These are valid
    data, but a model has almost no support there, so predictions near them
    are extrapolation dressed up as interpolation. Reported as info, not a
    defect -- the action is 'sample more here', never 'drop these rows'."""
    out = []
    for col in columns:
        v = _numeric(data, col)
        if v is None:
            continue
        s = pd.to_numeric(data[col], errors="coerce")
        lo_q = float(np.quantile(v, EXTRAPOLATION_TAIL))
        hi_q = float(np.quantile(v, 1 - EXTRAPOLATION_TAIL))
        edge = s[(s < lo_q) | (s > hi_q)]
        if 0 < len(edge) <= max(3, int(0.05 * len(v))):
            out.append(SuitabilityFinding(
                kind="extrapolation_risk",
                columns=(col,),
                row_ids=[int(i) for i in edge.index],
                detail=(f"{len(edge)} row(s) sit beyond the {col} hull edge "
                        f"[{lo_q:.4g}, {hi_q:.4g}]. Valid data, but the model has "
                        f"almost no support there -- treat predictions near them as "
                        f"extrapolation."),
                severity="info",
            ))
    return out


def assess_training_suitability(data: pd.DataFrame, columns: list[str]) -> list[SuitabilityFinding]:
    """Run all four dataset-level suitability analyses. (The fifth sub-kind,
    exact duplicates, is produced by rules.check_structural since it is a
    structural property, and is merged in by the engine.)"""
    if len(data) < MIN_ROWS_FOR_COVERAGE:
        return []
    cols = [c for c in columns if c in data.columns]
    return (find_design_space_gaps(data, cols)
            + find_feature_target_leakage(data, cols)
            + find_regime_imbalance(data, cols)
            + find_extrapolation_risk(data, cols))
