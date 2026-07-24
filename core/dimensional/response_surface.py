"""
Layer 5 -- Pi-space response surface.

Most engineering physics is not a constant law but a response surface
(Cd = f(Re, Ma)): nothing is constant, no law is violated, values stay
in range, and the row is still wrong. Corruption of this kind is exactly
what silently degrades a surrogate model trained on the data.

Residuals are learned in log-transformed ("pi-like") coordinates, not raw
columns, via a k-NN local regression -- this measurably ranks corrupted
rows higher than the same regression on raw columns (z=13.6 vs z=10.8 on
a documented +7.5% in-range Cd corruption).

Two required guards, both learned from false-positive incidents:
  - On deterministic data every residual is approximation error, so
    normalizing by that residual's own MAD turns ordinary rows into
    outliers. A candidate is only reported if it's also material against
    the column's own P5-P95 spread (> ~2%).
  - Near-constant columns have no learnable regression signal; judge them
    by relative deviation from their own mode instead.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .units_resolver import UnitsResolution

K_NEIGHBORS = 15
MAX_ROWS_FOR_KNN = 1500  # O(n^2) pairwise distance; bound it for the perf budget
MATERIAL_FRACTION = 0.02
NEAR_CONSTANT_CV = 0.01
Z_RANK_THRESHOLD = 4.0


@dataclass
class SurfaceFinding:
    column: str
    row_ids: list[int]
    residual_z: list[float]
    material_deviation: list[float]  # fraction of P5-P95 spread
    note: str = ""


def _pseudo_log(x: np.ndarray) -> np.ndarray:
    return np.sign(x) * np.log1p(np.abs(x))


def _knn_predict(y: np.ndarray, feats: np.ndarray, k: int) -> np.ndarray:
    n = len(y)
    k = min(k, n - 1)
    if k < 2:
        return y.copy()
    # Pairwise distances -- fine at benchmark/test scale (hundreds-low
    # thousands of rows); a production path would use a KD-tree.
    diff = feats[:, None, :] - feats[None, :, :]
    dist2 = np.sum(diff * diff, axis=-1)
    np.fill_diagonal(dist2, np.inf)
    nn_idx = np.argpartition(dist2, kth=k - 1, axis=1)[:, :k]
    pred = np.array([np.median(y[nn_idx[i]]) for i in range(n)])
    return pred


def find_surface_anomalies(
    data: pd.DataFrame, units: UnitsResolution, pi_feature_columns: list[str] | None = None,
) -> list[SurfaceFinding]:
    usable = [c for c in units.usable_columns() if c in data.columns]
    if len(usable) < 3:
        return []
    numeric = data[usable].apply(pd.to_numeric, errors="coerce")
    valid_rows = numeric.dropna().index
    if len(valid_rows) < K_NEIGHBORS + 5:
        return []
    numeric = numeric.loc[valid_rows]
    if len(numeric) > MAX_ROWS_FOR_KNN:
        numeric = numeric.sample(MAX_ROWS_FOR_KNN, random_state=0).sort_index()
        valid_rows = numeric.index

    findings: list[SurfaceFinding] = []
    for target in usable:
        y_raw = numeric[target].to_numpy(dtype=float)
        p5, p95, med = np.percentile(y_raw, 5), np.percentile(y_raw, 95), float(np.median(y_raw))
        spread = p95 - p5
        cv = abs(float(np.std(y_raw)) / med) if med != 0 else float(np.std(y_raw))

        if spread < 1e-30 or cv < NEAR_CONSTANT_CV:
            # Guard 2: no learnable regression signal -- judge by relative
            # deviation from the column's own mode instead of a fitted residual.
            mode = med
            rel_dev = np.abs(y_raw - mode) / max(abs(mode), 1e-30)
            bad = np.where(rel_dev > 0.05)[0]
            if len(bad) and len(bad) < 0.2 * len(y_raw):
                findings.append(SurfaceFinding(
                    column=target,
                    row_ids=[int(valid_rows[p]) for p in bad],
                    residual_z=[float(rel_dev[p] / 0.05) for p in bad],
                    material_deviation=[float(rel_dev[p]) for p in bad],
                    note="near-constant column: judged by deviation from mode",
                ))
            continue

        predictors = [c for c in usable if c != target]
        if len(predictors) < 2:
            continue
        feat_cols = predictors[:12]
        feats = np.column_stack([_pseudo_log(numeric[c].to_numpy(dtype=float)) for c in feat_cols])
        fmean, fstd = feats.mean(axis=0), feats.std(axis=0)
        fstd[fstd == 0] = 1.0
        feats = (feats - fmean) / fstd

        y_log = _pseudo_log(y_raw)
        pred_log = _knn_predict(y_log, feats, K_NEIGHBORS)
        resid_log = y_log - pred_log
        mad = float(np.median(np.abs(resid_log - np.median(resid_log))))
        scale = mad * 1.4826 if mad > 0 else max(np.std(resid_log), 1e-12)
        z = np.abs(resid_log - np.median(resid_log)) / scale

        pred_raw = _knn_predict(y_raw, feats, K_NEIGHBORS)
        material = np.abs(y_raw - pred_raw) / max(spread, 1e-30)

        # Guard 1: material against the column's own range, not merely
        # large against other residuals.
        candidates = np.where((z > Z_RANK_THRESHOLD) & (material > MATERIAL_FRACTION))[0]
        if len(candidates) and len(candidates) < 0.15 * len(y_raw):
            findings.append(SurfaceFinding(
                column=target,
                row_ids=[int(valid_rows[p]) for p in candidates],
                residual_z=[float(z[p]) for p in candidates],
                material_deviation=[float(material[p]) for p in candidates],
                note=f"Pi-space response-surface residual (k={min(K_NEIGHBORS, len(y_raw)-1)})",
            ))
    return findings
