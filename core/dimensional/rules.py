"""
Layer 6 -- semantic bounds.
Layer 8 -- structural primitives.

Both are "Impossible" class by construction: true by definition, not by
domain assumption, so neither is ever suppressible and neither needs a
suppression-of-a-suppression escape hatch. `conversion = 1.22` is
dimensionally immaculate and physically impossible; no statistical method
catches it, but a [0,1] bound does, unconditionally.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

# (name-pattern, low, high, inclusive-low, inclusive-high, description)
SEMANTIC_BOUNDS: list[tuple[str, float, float, bool, bool, str]] = [
    (r"\b(conversion|efficiency|eta|fraction|utilization|void_fraction|"
     r"porosity|saturation|absorptivity|emissivity|transmissivity|"
     r"reflectivity|quality)\b", 0.0, 1.0, True, True, "must lie in [0,1]"),
    (r"\bprobability|likelihood|confidence\b", 0.0, 1.0, True, True, "must lie in [0,1]"),
    (r"\bcorrelation|corr_\w+\b", -1.0, 1.0, True, True, "|r| must be <=1"),
    (r"\bpoisson_ratio\b", -1.0, 0.5, False, True, "must lie in (-1, 0.5]"),
    (r"\bmach_?number|^ma$\b", 0.0, 60.0, True, True, "must be non-negative"),
    (r"\btemperature\b(?!.*delta)", 0.0, 1e6, True, True, "absolute temperature must be > 0 K"),
    (r"^t$", 0.0, 1e6, True, True, "absolute temperature must be > 0 K"),
    (r"\bmass\b", 0.0, float("inf"), False, True, "mass must be > 0"),
    (r"\bdensity\b", 0.0, float("inf"), False, True, "density must be > 0"),
    (r"\bhumidity|relative_humidity|rh\b", 0.0, 100.0, True, True, "RH must lie in [0,100]%"),
    (r"\bph\b", 0.0, 14.0, True, True, "pH must lie in [0,14]"),
    (r"\bwavelength|frequency\b", 0.0, float("inf"), False, True, "must be > 0"),
    (r"\byield_strength|ultimate_strength|hardness|viscosity\b", 0.0, float("inf"), False, True, "must be > 0"),
    (r"\bangle_of_attack|aoa\b", -90.0, 90.0, True, True, "must lie in [-90,90] deg"),
    (r"\bcloud_cover\b", 0.0, 100.0, True, True, "must lie in [0,100]%"),
    (r"\bmole_fraction|mass_fraction\b", 0.0, 1.0, True, True, "must lie in [0,1]"),
    (r"\bspring_constant|stiffness\b", 0.0, float("inf"), False, True, "must be > 0"),
]


@dataclass
class SemanticViolation:
    column: str
    row_ids: list[int]
    values: list[float]
    rule: str
    impossible: bool = True


def check_semantic_bounds(data: pd.DataFrame) -> list[SemanticViolation]:
    out: list[SemanticViolation] = []
    for col in data.columns:
        for pattern, lo, hi, inc_lo, inc_hi, desc in SEMANTIC_BOUNDS:
            if not re.search(pattern, col, re.IGNORECASE):
                continue
            s = pd.to_numeric(data[col], errors="coerce")
            valid = s.dropna()
            if len(valid) == 0:
                continue
            lo_bad = valid < lo if inc_lo else valid <= lo
            hi_bad = valid > hi if inc_hi else valid >= hi
            bad_mask = lo_bad | hi_bad
            if bad_mask.any():
                idx = valid.index[bad_mask]
                out.append(SemanticViolation(
                    column=col,
                    row_ids=[int(i) for i in idx],
                    values=[float(valid.loc[i]) for i in idx],
                    rule=f"{col} {desc}",
                ))
            break  # first matching pattern wins
    return out


@dataclass
class StructuralFinding:
    kind: str  # "non_finite" | "exact_duplicate"
    row_ids: list[int]
    detail: str


def check_structural(data: pd.DataFrame, rel_tol: float = 1e-9) -> list[StructuralFinding]:
    findings: list[StructuralFinding] = []
    numeric_cols = list(data.select_dtypes(include=[np.number]).columns)

    # Non-finite values.
    if numeric_cols:
        sub = data[numeric_cols].apply(pd.to_numeric, errors="coerce")
        non_finite_mask = ~np.isfinite(sub.to_numpy(dtype=float))
        bad_rows = np.where(non_finite_mask.any(axis=1))[0]
        if len(bad_rows):
            findings.append(StructuralFinding(
                kind="non_finite",
                row_ids=[int(data.index[p]) for p in bad_rows],
                detail=f"{len(bad_rows)} row(s) with NaN/Inf in {numeric_cols}",
            ))

    # Exact duplicates by PER-COLUMN RELATIVE equality -- never cosine
    # similarity. Cosine on raw vectors is dominated by the
    # largest-magnitude column (e.g. Reynolds ~1e5), so unrelated rows in a
    # smooth sweep score > 0.999 -- documented as 30/32 false exclusions.
    if numeric_cols and len(data) > 1:
        arr = data[numeric_cols].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
        n = len(arr)
        # Bucket by a coarse rounded key first so the exact O(k^2) relative-
        # equality check only ever runs within small candidate buckets, not
        # across the whole dataset -- keeps this tractable at real row counts.
        buckets: dict[tuple, list[int]] = {}
        for i in range(n):
            key = tuple(round(v, 6) if np.isfinite(v) else None for v in arr[i])
            buckets.setdefault(key, []).append(i)
        seen: set[int] = set()
        dup_rows: list[int] = []
        for idxs in buckets.values():
            if len(idxs) < 2:
                continue
            for a_pos in range(len(idxs)):
                i = idxs[a_pos]
                if i in seen:
                    continue
                for b_pos in range(a_pos + 1, len(idxs)):
                    j = idxs[b_pos]
                    if j in seen:
                        continue
                    a, b = arr[i], arr[j]
                    denom = np.maximum(np.abs(a), np.abs(b))
                    denom[denom == 0] = 1.0
                    rel_diff = np.abs(a - b) / denom
                    if np.all(rel_diff < rel_tol):
                        seen.add(j)
                        dup_rows.append(j)
        if dup_rows:
            findings.append(StructuralFinding(
                kind="exact_duplicate",
                row_ids=[int(data.index[p]) for p in dup_rows],
                detail=f"{len(dup_rows)} row(s) exactly duplicate an earlier row "
                       f"(per-column relative equality < {rel_tol:g})",
            ))
    return findings
