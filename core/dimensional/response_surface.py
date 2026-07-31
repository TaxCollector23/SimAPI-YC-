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

A local k-NN fit has a structural blind spot: if corruption is clustered in
FEATURE space (not scattered), a corrupted row's nearest neighbours are
disproportionately other corrupted rows from the same cluster, so the local
fit ends up validating the cluster against itself -- measured catching only
1/39 rows in a clustered-corruption test (a whole velocity band corrupted
the same way). A robust GLOBAL regression (IRLS with Huber weights, fit
once against the reference sample) is complementary: a minority cluster
barely perturbs a fit over the whole reference set, so it stays sensitive
to exactly what the local check misses. Implemented in plain numpy rather
than pulling in sklearn as a hard dependency of the core validation path.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .units_resolver import UnitsResolution

K_NEIGHBORS = 15
MIN_ROWS_FOR_KNN = K_NEIGHBORS + 5
MAX_ROWS_FOR_KNN = 1500  # O(n^2) pairwise distance; bound it for the perf budget
# Below MIN_ROWS_FOR_KNN there aren't enough rows to fit a local response
# surface against covariates at all -- but that doesn't mean nothing can be
# said. A row whose value is a huge global outlier *within its own column*
# (999.0 among four values near 0.3) needs no covariates and no minimum
# neighbourhood, just a median and a spread -- the degenerate case of "does
# this row fit the response surface" when there's no surface to fit against.
# This is what makes small, hand-pasted playground datasets (5-20 rows)
# behave the same as the statistically-larger case instead of silently
# validating everything.
MIN_ROWS_FOR_GLOBAL_Z = 4
MIN_ROWS_FOR_GLOBAL_FIT = 150  # small-n IRLS fits are less stable; anchors (Layer 3) already
                               # reliably cover small, exact relationships, so this check can
                               # afford to wait for more data rather than risk a false flag.
GLOBAL_Z_THRESHOLD = 6.0  # deliberately more conservative than the local check's threshold --
                          # measured margin on the clustered-corruption case this targets is
                          # z~85-89, so this costs essentially no real sensitivity.
MATERIAL_FRACTION = 0.02
NEAR_CONSTANT_CV = 0.01
Z_RANK_THRESHOLD = 4.0
HUBER_DELTA = 1.35  # standard Huber tuning constant (~95% efficiency under Gaussian noise)
HUBER_IRLS_ITERS = 8

MAJORITY_FRACTION = 0.4
# Shared cap for every "how many rows can this layer flag before it stops
# trusting itself" decision below (previously four separate, undocumented
# guesses: 0.15, 0.15, 0.2, 0.4).
#
# This layer has no external ground truth of its own -- median, mode, k-NN,
# and Huber regression all infer "normal" purely from this dataset's own
# majority. For any column a Layer-3 anchor already covers, that's handled
# separately: `anchor_columns` (below) makes this layer defer entirely
# rather than risk contradicting a real physical constant with a fitted
# model that has no ground truth. This cap is for everything else -- where
# no anchor exists at all, and this layer's own statistics are genuinely
# the best available signal. There, 0.4 is grounded in the ~50% breakdown
# point of median/mode-based robust statistics (with a safety margin,
# empirically verified: raising it further re-broke the majority-corruption
# regression test once tried without the anchor-veto in place).
# Above this, a row's k-nearest neighbours lie essentially all to one side,
# so the local fit is extrapolating. 0.5 means the mean neighbour offset is
# half the mean neighbour distance -- a clearly lopsided neighbourhood,
# while an interior point on any reasonable sampling sits well below it.
ONE_SIDED_MAX = 0.5


@dataclass
class SurfaceFinding:
    column: str
    row_ids: list[int]
    residual_z: list[float]
    material_deviation: list[float]  # fraction of P5-P95 spread
    note: str = ""


def _pseudo_log(x: np.ndarray) -> np.ndarray:
    return np.sign(x) * np.log1p(np.abs(x))


def _knn_neighbors_against_ref(
    feats_ref: np.ndarray, feats_query: np.ndarray,
    ref_ids: np.ndarray, query_ids: np.ndarray, k: int,
) -> tuple[np.ndarray, np.ndarray]:
    """The expensive part of `_knn_predict_against_ref` -- the distance
    matrix and neighbour indices depend only on features, not on which
    target column is being predicted, so this is computed once per column
    and reused for both the log-space and raw-space predictions (which
    used to each recompute it from scratch -- 2x the cost for no reason).

    Returns (nn_idx, one_sidedness).
    """
    n_q, n_r = len(feats_query), len(feats_ref)
    k_eff = max(2, min(k, n_r - 1))
    # dist2(x, y) = ||x||^2 + ||y||^2 - 2 x.y -- a BLAS matmul for the
    # (n_q, n_r) distance matrix, instead of materializing an (n_q, n_r, d)
    # array via broadcasted subtraction (the previous approach, which
    # dominated runtime at thousands of query rows: ~13s of ~21s total on
    # a 9,333-row benchmark).
    q_sq = np.sum(feats_query * feats_query, axis=1)[:, None]
    r_sq = np.sum(feats_ref * feats_ref, axis=1)[None, :]
    dist2 = q_sq + r_sq - 2.0 * (feats_query @ feats_ref.T)
    np.maximum(dist2, 0, out=dist2)  # clip tiny floating-point negatives
    self_mask = ref_ids[None, :] == query_ids[:, None]
    dist2 = np.where(self_mask, np.inf, dist2)
    nn_idx = np.argpartition(dist2, kth=k_eff - 1, axis=1)[:, :k_eff]

    # One-sidedness needs actual offset vectors, but only for the k_eff
    # selected neighbours per row (n_q, k, d -- small), not the full grid.
    offsets = feats_ref[nn_idx] - feats_query[:, None, :]  # (n_q, k, d)
    mean_off = np.linalg.norm(offsets.mean(axis=1), axis=1)
    mean_dist = np.linalg.norm(offsets, axis=2).mean(axis=1)
    one_sided = np.divide(mean_off, mean_dist,
                          out=np.zeros(n_q), where=mean_dist > 0)
    return nn_idx, one_sided


def _huber_irls_fit(X_ref: np.ndarray, y_ref: np.ndarray) -> np.ndarray | None:
    """Iteratively-reweighted least squares with Huber weights: a linear
    fit that's barely perturbed by a minority of large-residual points --
    the property that makes it complementary to the local k-NN check,
    which a clustered minority of corrupted rows can fool (their nearest
    neighbours are mostly each other). Returns the fitted coefficients, or
    None if the design matrix is degenerate (e.g. collinear predictors)."""
    n, d = X_ref.shape
    w = np.ones(n)
    beta = None
    for _ in range(HUBER_IRLS_ITERS):
        Xw = X_ref * w[:, None]
        try:
            beta, *_ = np.linalg.lstsq(Xw.T @ X_ref, Xw.T @ y_ref, rcond=None)
        except np.linalg.LinAlgError:
            return None
        resid = y_ref - X_ref @ beta
        mad = float(np.median(np.abs(resid - np.median(resid))))
        s = max(mad * 1.4826, 1e-12)
        r = resid / s
        abs_r = np.abs(r)
        w = np.where(abs_r <= HUBER_DELTA, 1.0, HUBER_DELTA / np.maximum(abs_r, 1e-12))
    return beta


def _global_robust_residuals(
    feats_ref: np.ndarray, y_ref: np.ndarray, feats_all: np.ndarray, y_all: np.ndarray,
) -> tuple[np.ndarray, np.ndarray] | None:
    """Fit a robust global regression on the reference sample (degree-2:
    linear + squared terms per predictor, so it can track mild curvature
    without needing sklearn), then score every row's deviation from it.
    Returns (residuals, predictions) so the caller can compute its own
    material-deviation gate against this fit's prediction -- NOT the local
    k-NN's, which can itself be pulled toward a corrupted cluster."""
    n_ref, d = feats_ref.shape
    if n_ref < MIN_ROWS_FOR_GLOBAL_FIT:
        return None
    X_ref = np.column_stack([np.ones(n_ref), feats_ref, feats_ref ** 2])
    beta = _huber_irls_fit(X_ref, y_ref)
    if beta is None:
        return None
    X_all = np.column_stack([np.ones(len(feats_all)), feats_all, feats_all ** 2])
    pred_all = X_all @ beta
    return y_all - pred_all, pred_all


def _knn_predict(y: np.ndarray, feats: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    """Returns (prediction, one_sidedness) per row.

    `one_sidedness` measures whether a row's neighbourhood surrounds it or
    sits entirely to one side:

        ||mean(neighbour - x)|| / mean(||neighbour - x||)

    ~0 for an interior point (neighbours cancel out around it), ~1 for a
    point at the edge of the sampled design space (every neighbour lies
    inward). It is a ratio of distances, so it is scale-free and needs no
    tuning per dataset.

    This is the guard for the failure the spec names explicitly -- a
    2-factor design where the OLD engine excluded 60/60 valid trials. At a
    design corner k-NN has no neighbours beyond the corner, so the local
    fit EXTRAPOLATES, and on any curved response (a quadratic Cd(AoA) is
    the normal case, not a pathology) the residual it produces measures the
    curvature of the physics rather than anything wrong with the row. The
    corner is where curvature is largest, so the most extreme legitimate
    design points look the most anomalous -- exactly backwards.
    """
    n = len(y)
    k = min(k, n - 1)
    if k < 2:
        return y.copy(), np.zeros(n)
    # Pairwise distances -- fine at benchmark/test scale (hundreds-low
    # thousands of rows); a production path would use a KD-tree.
    diff = feats[:, None, :] - feats[None, :, :]
    dist2 = np.sum(diff * diff, axis=-1)
    np.fill_diagonal(dist2, np.inf)
    nn_idx = np.argpartition(dist2, kth=k - 1, axis=1)[:, :k]
    pred = np.array([np.median(y[nn_idx[i]]) for i in range(n)])

    offsets = feats[nn_idx] - feats[:, None, :]          # (n, k, d)
    mean_off = np.linalg.norm(offsets.mean(axis=1), axis=1)
    mean_dist = np.linalg.norm(offsets, axis=2).mean(axis=1)
    one_sided = np.divide(mean_off, mean_dist,
                          out=np.zeros(n), where=mean_dist > 0)
    return pred, one_sided


def _global_z_outliers(y_raw: np.ndarray, valid_rows: pd.Index, target: str) -> SurfaceFinding | None:
    """Degenerate response-surface check for datasets too small for k-NN:
    is this row a robust outlier within its own column, full stop. Same two
    required guards as the k-NN path (material-vs-spread, near-constant is
    handled by the caller before this is reached)."""
    y_log = _pseudo_log(y_raw)
    med = float(np.median(y_log))
    mad = float(np.median(np.abs(y_log - med)))
    scale = mad * 1.4826 if mad > 0 else max(np.std(y_log), 1e-12)
    z = np.abs(y_log - med) / scale

    p5, p95 = np.percentile(y_raw, 5), np.percentile(y_raw, 95)
    spread = p95 - p5
    raw_med = float(np.median(y_raw))
    material = np.abs(y_raw - raw_med) / max(spread, 1e-30)

    candidates = np.where((z > Z_RANK_THRESHOLD) & (material > MATERIAL_FRACTION))[0]
    # This is a median/MAD outlier check, not a fitted model -- it has a
    # natural ~50% breakdown point (the median doesn't move until outliers
    # are the majority), unlike the k-NN/global-regression checks below,
    # which really can be a poor fit and flag everything. So this cap can
    # safely be much more generous than theirs: up to 40% of rows, not 20%.
    # (Found via live testing: 2 rows sharing an identical extreme value in
    # a 5-row dataset -- 40% -- produced an unambiguous z~236, but the
    # tighter 20% cap silently discarded the finding entirely.)
    if len(candidates) and len(candidates) <= max(1, int(MAJORITY_FRACTION * len(y_raw))):
        return SurfaceFinding(
            column=target,
            row_ids=[int(valid_rows[p]) for p in candidates],
            residual_z=[float(z[p]) for p in candidates],
            material_deviation=[float(material[p]) for p in candidates],
            note="global outlier within column (too few rows to fit a local response surface)",
        )
    return None


def find_surface_anomalies(
    data: pd.DataFrame, units: UnitsResolution, pi_feature_columns: list[str] | None = None,
    anchor_columns: set[str] | None = None,
) -> list[SurfaceFinding]:
    """`anchor_columns`: columns already governed by a confirmed Layer-3
    anchor. This layer has no external ground truth -- it infers "normal"
    purely from this dataset's own majority, so once corruption exceeds
    ~50% it can mistake the corrupted majority for normal and flag the
    clean minority instead (verified directly: a genuinely clean row
    scored z=752.8 once >50% of its column was corrupted, because the
    fitted reference was built mostly from corrupted data). An anchor has
    no such weakness -- it compares against a real physical constant, not
    this dataset's own majority -- so for any column an anchor already
    covers, this layer defers entirely rather than risk contradicting it.
    """
    anchor_columns = anchor_columns or set()
    usable = [c for c in units.usable_columns() if c in data.columns]
    if len(usable) < 3:
        # With only 2 columns, any "outlier" in one is indistinguishable
        # from a genuine functional relationship to the other (e.g. an
        # anchor's a*b=const, where b is a smooth, deterministic function
        # of a) -- that's Layer 3's job, not a context-free univariate
        # check here. The global-z fallback below is for too few ROWS,
        # not too few columns to have real context.
        return []
    numeric = data[usable].apply(pd.to_numeric, errors="coerce")
    valid_rows = numeric.dropna().index
    if len(valid_rows) < MIN_ROWS_FOR_GLOBAL_Z:
        return []
    numeric = numeric.loc[valid_rows]
    ref_numeric = numeric
    if len(numeric) > MAX_ROWS_FOR_KNN:
        ref_numeric = numeric.sample(MAX_ROWS_FOR_KNN, random_state=0).sort_index()
    knn_available = len(ref_numeric) >= MIN_ROWS_FOR_KNN

    findings: list[SurfaceFinding] = []
    for target in usable:
        if target in anchor_columns:
            continue  # Layer 3 already has a ground-truthed verdict for this column; defer to it
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
            if len(bad) and len(bad) <= max(1, int(MAJORITY_FRACTION * len(y_raw))):
                findings.append(SurfaceFinding(
                    column=target,
                    row_ids=[int(valid_rows[p]) for p in bad],
                    residual_z=[float(rel_dev[p] / 0.05) for p in bad],
                    material_deviation=[float(rel_dev[p]) for p in bad],
                    note="near-constant column: judged by deviation from mode",
                ))
            continue

        predictors = [c for c in usable if c != target]
        if not knn_available or len(predictors) < 2:
            finding = _global_z_outliers(y_raw, valid_rows, target)
            if finding is not None:
                findings.append(finding)
            continue
        feat_cols = predictors[:12]
        # Query features: every valid row. Reference features: the (possibly
        # subsampled) reference set. Both standardized against the reference
        # set's own mean/std so a corrupted row doesn't skew its own scale.
        feats_all = np.column_stack([_pseudo_log(numeric[c].to_numpy(dtype=float)) for c in feat_cols])
        ref_mask = numeric.index.isin(ref_numeric.index)
        fmean, fstd = feats_all[ref_mask].mean(axis=0), feats_all[ref_mask].std(axis=0)
        fstd[fstd == 0] = 1.0
        feats_all = (feats_all - fmean) / fstd
        feats_ref = feats_all[ref_mask]

        y_log_all = _pseudo_log(y_raw)
        y_log_ref = y_log_all[ref_mask]
        y_raw_ref = y_raw[ref_mask]
        query_ids = numeric.index.to_numpy()
        ref_ids = ref_numeric.index.to_numpy()
        nn_idx, one_sided = _knn_neighbors_against_ref(
            feats_ref, feats_all, ref_ids, query_ids, K_NEIGHBORS)
        pred_log = np.array([np.median(y_log_ref[nn_idx[i]]) for i in range(len(feats_all))])
        pred_raw = np.array([np.median(y_raw_ref[nn_idx[i]]) for i in range(len(feats_all))])
        resid_log = y_log_all - pred_log
        mad = float(np.median(np.abs(resid_log - np.median(resid_log))))
        scale = mad * 1.4826 if mad > 0 else max(np.std(resid_log), 1e-12)
        z = np.abs(resid_log - np.median(resid_log)) / scale
        material = np.abs(y_raw - pred_raw) / max(spread, 1e-30)

        # Guard 1: material against the column's own range, not merely
        # large against other residuals.
        # Guard 3 (design-space boundary): a row whose neighbours all lie to
        # one side is being extrapolated to, not interpolated -- its residual
        # reflects the curvature of the response, not a defect. This is what
        # keeps the corners of a factorial design out of the findings.
        interior = one_sided < ONE_SIDED_MAX
        candidates = np.where((z > Z_RANK_THRESHOLD) & (material > MATERIAL_FRACTION) & interior)[0]
        if len(candidates) and len(candidates) <= max(1, int(MAJORITY_FRACTION * len(y_raw))):
            findings.append(SurfaceFinding(
                column=target,
                row_ids=[int(valid_rows[p]) for p in candidates],
                residual_z=[float(z[p]) for p in candidates],
                material_deviation=[float(material[p]) for p in candidates],
                note=f"Pi-space response-surface residual (k={min(K_NEIGHBORS, len(ref_numeric)-1)}, "
                     f"reference n={len(ref_numeric)}, scored n={len(y_raw)})",
            ))

        # Global robust-regression check -- catches corruption clustered in
        # feature space, which the local kNN check above can be fooled by
        # (a clustered row's own neighbours are mostly other corrupted rows).
        global_out = _global_robust_residuals(feats_ref, y_log_ref, feats_all, y_log_all)
        if global_out is not None:
            global_resid, _ = global_out
            g_mad = float(np.median(np.abs(global_resid - np.median(global_resid))))
            g_scale = g_mad * 1.4826 if g_mad > 0 else max(np.std(global_resid), 1e-12)
            g_z = np.abs(global_resid - np.median(global_resid)) / g_scale

            raw_out = _global_robust_residuals(feats_ref, y_raw_ref, feats_all, y_raw)
            g_pred_raw = raw_out[1] if raw_out is not None else pred_raw
            g_material = np.abs(y_raw - g_pred_raw) / max(spread, 1e-30)

            g_candidates = np.where((g_z > GLOBAL_Z_THRESHOLD) & (g_material > MATERIAL_FRACTION))[0]
            if len(g_candidates) and len(g_candidates) <= max(1, int(MAJORITY_FRACTION * len(y_raw))):
                findings.append(SurfaceFinding(
                    column=target,
                    row_ids=[int(valid_rows[p]) for p in g_candidates],
                    residual_z=[float(g_z[p]) for p in g_candidates],
                    material_deviation=[float(g_material[p]) for p in g_candidates],
                    note=f"Global robust-regression residual (Huber IRLS, reference n={len(ref_numeric)}, "
                         f"scored n={len(y_raw)}) -- catches corruption clustered in feature space "
                         f"that a local neighbourhood fit can be fooled by",
                ))
    return findings
