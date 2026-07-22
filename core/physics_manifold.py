"""
SimAPI — Physics Manifold Validator (Layer 5)
===============================================

The architectural answer to "catch things it wasn't coded for."

Every simulation dataset, regardless of domain, lies on a low-dimensional
manifold determined by the governing physics equations. A compressible
aerodynamics solver sweeping Mach number and AoA produces data that lives
on a 2-3 dimensional manifold in the 8-column output space. A structural
FEA sweep lives on a manifold determined by the constitutive relations and
equilibrium equations.

Corrupted rows are OFF this manifold. A unit error in pressure takes the
pressure value off the manifold defined by P = rho * R * T. A solver
blowup creates a row that is off the manifold in multiple dimensions
simultaneously. A data pipeline error that swaps columns creates a row
where the multivariate structure is violated.

THIS WORKS WITHOUT KNOWING:
- What the columns are named
- What physics govern the simulation
- What type of corruption was injected
- What the physical bounds are

It works because the DATA ITSELF encodes the physics through the
correlations, ratios, and nonlinear relationships between columns.
PCA (and its kernel variants) extracts this structure.

Architecture
------------
Fit a PCA model on the inlier portion of the current data (cold start),
OR on the union of all prior clean runs (warm start via RunHistoryTracker).
Score each row by its reconstruction error: ||x - PCA(x)||^2.
Rows far from the manifold are corrupted.

The reconstruction IS the counterfactual: "this row should look like [values]."
The component loadings tell you which physical dimensions were violated.
The per-column reconstruction errors tell you which columns are anomalous.

Two-tier output (matching APIE philosophy):
- auto-remove: reconstruction error > 99.99th pct of clean baseline
- flag-for-review: reconstruction error > 99.0th pct of clean baseline

Limitations (documented honestly):
- Gradual sensor drift is ON the manifold if the drift is small relative
  to the natural variance. Drift detection requires RunHistoryTracker.
- Copy-paste corruptions: if the copied row is clean, it's ON the manifold.
  APIE's copy_paste_block check handles this.
- Configuration-level errors (wrong turbulence model): produces physically
  self-consistent but wrong results. No output validator catches this.
"""
from __future__ import annotations

import time
import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import RobustScaler

# ═══════════════════════════════════════════════════════════════════════════════
# Data structures
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ManifoldResult:
    """Result of physics manifold validation."""
    auto_remove: set[int]             # high-confidence off-manifold rows
    review_flags: list[dict]          # lower-confidence flags with reconstructions
    per_row_scores: np.ndarray        # reconstruction error per row
    threshold_auto: float             # threshold used for auto-remove
    threshold_review: float           # threshold used for review
    n_components: int                 # PCA components used (≈ physics DOF)
    explained_variance: float         # fraction of variance captured
    manifold_mode: str                # 'cold_start' | 'warm'
    column_names: list[str]           # columns included in manifold
    reconstructions: dict[int, dict[str, float]] | None  # row_idx → reconstructed values
    component_interpretation: list[str]  # what each component likely represents
    processing_ms: float


# ═══════════════════════════════════════════════════════════════════════════════
# Physics Manifold Validator
# ═══════════════════════════════════════════════════════════════════════════════

class PhysicsManifoldValidator:
    """
    Self-supervised physics manifold validator.

    Learns the structure of the simulation data and flags rows that violate it.
    Column-name agnostic. Domain agnostic. Catches unknown corruption types.

    Usage:
        pmv = PhysicsManifoldValidator()
        result = pmv.validate(df, prior_clean_X=prior_X, inlier_mask=apie_inliers)
        # result.auto_remove: remove these
        # result.review_flags: human should look at these
        # result.reconstructions[i]: what row i should look like
    """

    def __init__(
        self,
        max_components: int = 12,
        min_explained_variance: float = 0.95,
        auto_threshold_pct: float = 99.9,    # was 99.99, too conservative for cold_start
        review_threshold_pct: float = 98.0,  # was 99.0
    ):
        self.max_components = max_components
        self.min_ev = min_explained_variance
        self.auto_pct = auto_threshold_pct
        self.review_pct = review_threshold_pct

    def validate(
        self,
        df: pd.DataFrame,
        prior_clean_X: np.ndarray | None = None,
        inlier_mask: np.ndarray | None = None,
        provide_reconstructions: bool = True,
    ) -> ManifoldResult:
        """
        Validate a dataset against the physics manifold.

        Args:
            df: DataFrame to validate
            prior_clean_X: Optional array of prior clean run data (raw, unscaled).
                           When provided, calibration is much more accurate.
                           Shape: (n_prior_rows, n_cols) — same columns as df.
            inlier_mask: Optional boolean mask of rows believed to be clean.
                         Used for cold-start calibration when prior_clean_X is None.
                         Typically: ~apie_exclusions_mask from L1-L4.
            provide_reconstructions: Whether to compute per-row reconstructed values.
        """
        t0 = time.time()

        # Select numeric columns only
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if len(numeric_cols) < 2:
            return self._empty_result(len(df), time.time() - t0)

        X = df[numeric_cols].values.astype(float)
        n_rows, n_features = X.shape

        # Handle missing values
        col_medians = np.nanmedian(X, axis=0)
        for j in range(n_features):
            mask = ~np.isfinite(X[:, j])
            if mask.any():
                X[mask, j] = col_medians[j]

        # ── Determine calibration data ─────────────────────────────────────
        if prior_clean_X is not None and len(prior_clean_X) >= 100:
            # WARM MODE: calibrate on prior clean runs
            # Ensure prior has same number of columns (may need to align)
            if prior_clean_X.shape[1] == n_features:
                X_calib = prior_clean_X.astype(float)
                # Handle NaN in prior
                for j in range(n_features):
                    bad = ~np.isfinite(X_calib[:, j])
                    if bad.any():
                        X_calib[bad, j] = np.nanmedian(X_calib[:, j])
                mode = 'warm'
            else:
                X_calib = None; mode = 'cold_start'
        else:
            X_calib = None; mode = 'cold_start'

        if X_calib is None:
            # COLD START: use inlier subset of current data
            if inlier_mask is not None and inlier_mask.sum() >= 50:
                X_calib = X[inlier_mask]
            else:
                # Fallback: use rows with lowest Mahalanobis distance
                # (rough inlier detection without any prior)
                X_calib = self._rough_inliers(X)
            mode = 'cold_start'

        # ── Fit PCA on calibration data ────────────────────────────────────
        sc = RobustScaler()
        X_calib_s = sc.fit_transform(X_calib)

        # Choose number of components: minimum to explain min_ev of variance
        n_comp = min(self.max_components, X_calib_s.shape[1] - 1, X_calib_s.shape[0] - 1)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            pca = PCA(n_components=n_comp, random_state=42).fit(X_calib_s)

        # Find actual components needed to explain min_ev
        cum_ev = np.cumsum(pca.explained_variance_ratio_)
        n_needed = int(np.searchsorted(cum_ev, self.min_ev) + 1)
        n_needed = max(2, min(n_needed, n_comp))

        if n_needed < n_comp:
            pca = PCA(n_components=n_needed, random_state=42).fit(X_calib_s)

        # Calibration reconstruction errors
        X_calib_recon = pca.inverse_transform(pca.transform(X_calib_s))
        err_calib = np.sum((X_calib_s - X_calib_recon) ** 2, axis=1)

        # Thresholds from calibration distribution
        thr_auto   = float(np.percentile(err_calib, self.auto_pct))
        thr_review = float(np.percentile(err_calib, self.review_pct))

        # ── Score new data ─────────────────────────────────────────────────
        X_new_s = sc.transform(X)
        X_new_recon_s = pca.inverse_transform(pca.transform(X_new_s))
        err_new = np.sum((X_new_s - X_new_recon_s) ** 2, axis=1)

        # Per-column reconstruction errors (for diagnosis)
        col_err_s = (X_new_s - X_new_recon_s) ** 2  # (n, p)

        # ── Apply thresholds ───────────────────────────────────────────────
        auto_remove: set[int] = set()
        review_list: list[dict] = []

        for i in range(n_rows):
            score = float(err_new[i])
            if score <= thr_review:
                continue

            # Identify which columns are most violated
            col_scores = {numeric_cols[j]: float(col_err_s[i, j])
                          for j in range(n_features)}
            top_cols = sorted(col_scores, key=lambda c: -col_scores[c])[:3]

            # Reconstruction (what the row SHOULD look like)
            recon_vals = None
            if provide_reconstructions:
                recon_s = X_new_recon_s[i]
                recon_original = sc.inverse_transform(recon_s.reshape(1, -1))[0]
                recon_vals = {numeric_cols[j]: round(float(recon_original[j]), 6)
                              for j in range(n_features)}

            flag = {
                'row_index': i,
                'manifold_score': round(score, 4),
                'score_vs_auto_threshold': round(score / max(thr_auto, 1e-30), 2),
                'score_vs_review_threshold': round(score / max(thr_review, 1e-30), 2),
                'most_violated_columns': top_cols,
                'column_violation_scores': {c: round(col_scores[c], 4) for c in top_cols},
                'reconstructed_values': recon_vals,
                'diagnosis': self._diagnose_violation(top_cols, col_scores, X[i], recon_vals),
            }

            if score > thr_auto:
                auto_remove.add(i)
                flag['tier'] = 'auto_remove'
            else:
                flag['tier'] = 'review'
            review_list.append(flag)

        # Sort review_list by score descending
        review_list.sort(key=lambda x: -x['manifold_score'])

        # ── Component interpretation ───────────────────────────────────────
        comp_interp = self._interpret_components(pca, numeric_cols)

        ms = (time.time() - t0) * 1000
        return ManifoldResult(
            auto_remove=auto_remove,
            review_flags=review_list,
            per_row_scores=err_new,
            threshold_auto=round(thr_auto, 6),
            threshold_review=round(thr_review, 6),
            n_components=pca.n_components_,
            explained_variance=float(pca.explained_variance_ratio_.sum()),
            manifold_mode=mode,
            column_names=numeric_cols,
            reconstructions={f['row_index']: f['reconstructed_values']
                             for f in review_list if f.get('reconstructed_values')},
            component_interpretation=comp_interp,
            processing_ms=round(ms, 1),
        )

    # ── Internal methods ────────────────────────────────────────────────────────

    def _rough_inliers(self, X: np.ndarray, frac: float = 0.7) -> np.ndarray:
        """
        Rough inlier detection without any prior data.
        Uses columnwise median absolute deviation to identify the cleanest rows.
        Returns the `frac` fraction with lowest row-wise MAD scores.
        """
        col_meds = np.median(X, axis=0)
        col_mads = np.median(np.abs(X - col_meds), axis=0) + 1e-10
        scores = np.max(np.abs(X - col_meds) / col_mads, axis=1)
        k = max(50, int(len(X) * frac))
        inlier_idx = np.argsort(scores)[:k]
        return X[inlier_idx]

    def _diagnose_violation(
        self,
        top_cols: list[str],
        col_scores: dict[str, float],
        row_values: np.ndarray,
        recon_values: dict | None,
    ) -> str:
        """
        Generate a plain-English diagnosis of what the manifold violation means.
        This is the counterfactual: what should this row look like?
        """
        if not top_cols:
            return "Row deviates from the physics manifold in an uncharacterized way."

        primary = top_cols[0]
        parts = [f"The physics manifold is violated primarily in '{primary}'."]

        if recon_values and primary in recon_values:
            actual = row_values[0] if len(row_values) > 0 else None
            reconstructed = recon_values[primary]
            if actual is not None and abs(reconstructed) > 1e-10:
                ratio = actual / (reconstructed + 1e-30)
                if abs(ratio - 1000) < 200:
                    parts.append("The value is ~1000× the manifold expectation — likely Pa→kPa or m→mm unit error.")
                elif abs(ratio - 0.001) < 0.0005:
                    parts.append("The value is ~0.001× the manifold expectation — likely kPa→Pa or mm→m unit error.")
                elif ratio > 5:
                    parts.append(f"The value ({actual:.4g}) is {ratio:.1f}× the manifold prediction ({reconstructed:.4g}) — possible solver divergence or factor error.")
                elif ratio < 0.2:
                    parts.append(f"The value ({actual:.4g}) is {1/ratio:.1f}× below the manifold prediction ({reconstructed:.4g}) — possible sign error or unit division.")
                else:
                    parts.append(f"Manifold predicts {reconstructed:.4g}; actual is {actual:.4g} ({abs(ratio-1)*100:.0f}% deviation).")

        if len(top_cols) > 1:
            parts.append(f"Secondary violations in: {', '.join(top_cols[1:])}.")

        if len(top_cols) >= 2:
            parts.append(
                "Multi-column violation suggests the corruption propagated through "
                "the physics relationships (e.g., a unit error in an input that "
                "affects multiple derived outputs)."
            )

        return " ".join(parts)

    def _interpret_components(
        self, pca: PCA, col_names: list[str]
    ) -> list[str]:
        """
        Interpret PCA components in physical terms.
        High loadings on specific columns suggest what physical dimension
        the component represents.
        """
        interpretations = []
        components = pca.components_  # (n_components, n_features)

        for k, comp in enumerate(components):
            abs_loadings = np.abs(comp)
            top_idx = np.argsort(abs_loadings)[::-1][:3]
            top_cols = [col_names[j] for j in top_idx]
            top_vals = abs_loadings[top_idx]

            # Heuristic interpretation
            col_str = ", ".join(f"{c}({v:.2f})" for c, v in zip(top_cols, top_vals, strict=False))
            ev = pca.explained_variance_ratio_[k] * 100

            interp = f"PC{k+1} ({ev:.1f}% var): dominant in {col_str}"
            # Add physical interpretation hints
            if any('pressure' in c or 'velocity' in c for c in top_cols):
                interp += " → likely flow regime / Bernoulli axis"
            elif any('temperature' in c or 'thermal' in c or 'heat' in c for c in top_cols):
                interp += " → likely thermal state axis"
            elif any('torque' in c or 'force' in c or 'stress' in c for c in top_cols):
                interp += " → likely mechanical loading axis"
            elif any('current' in c or 'voltage' in c or 'power' in c for c in top_cols):
                interp += " → likely electrical state axis"

            interpretations.append(interp)

        return interpretations

    @staticmethod
    def _empty_result(n: int, elapsed: float) -> ManifoldResult:
        return ManifoldResult(
            auto_remove=set(), review_flags=[], per_row_scores=np.zeros(n),
            threshold_auto=0.0, threshold_review=0.0, n_components=0,
            explained_variance=0.0, manifold_mode='cold_start', column_names=[],
            reconstructions={}, component_interpretation=[],
            processing_ms=round(elapsed * 1000, 1),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Column name resolver — bridges arbitrary naming to known physics
# ═══════════════════════════════════════════════════════════════════════════════

# Mapping from common aliases to canonical names used in APIE domain profiles
# This allows domain profiles to fire even when columns have non-standard names
COLUMN_ALIAS_MAP: dict[str, str] = {
    # Aerodynamics
    'cd': 'drag_coefficient', 'coef_drag': 'drag_coefficient', 'drag_coeff': 'drag_coefficient',
    'cl': 'lift_coefficient', 'coef_lift': 'lift_coefficient', 'lift_coeff': 'lift_coefficient',
    're': 'reynolds_number', 'reynolds': 'reynolds_number', 'rey': 'reynolds_number',
    'ma': 'mach_number', 'mach': 'mach_number', 'm': 'mach_number',
    'u_inf': 'velocity', 'v_inf': 'velocity', 'u': 'velocity', 'vel': 'velocity',
    'v': 'velocity', 'spd': 'velocity', 'speed': 'velocity',
    'p_ref': 'pressure', 'p': 'pressure', 'pres': 'pressure', 'press': 'pressure',
    't_ref': 'temperature', 't': 'temperature', 'temp': 'temperature',
    'rho': 'density', 'dens': 'density',
    # Structural
    'e': 'elastic_modulus', 'youngs_modulus': 'elastic_modulus', 'e_modulus': 'elastic_modulus',
    'sigma': 'stress', 'sigma_vm': 'von_mises_stress', 'sf': 'safety_factor',
    'eps': 'strain', 'epsilon': 'strain',
    # Thermal
    't_wind': 'winding_temperature', 't_winding': 'winding_temperature',
    't_case': 'case_temperature', 't_amb': 'ambient_temperature',
    'r_th': 'thermal_resistance_wc', 'p_loss': 'total_loss',
    'i_rms': 'rms_current', 'r_wind': 'winding_resistance',
    # Robotics
    'tau': 'joint_torque', 'trq': 'joint_torque', 'omega': 'joint_velocity',
    'q_dot': 'joint_velocity', 'q': 'joint_position', 'theta': 'joint_position',
    'p_elec': 'electrical_power', 'p_mech': 'mechanical_power',
    # Drone
    'ct': 'thrust_coefficient', 'cp': 'power_coefficient',
    'eta': 'propulsive_efficiency', 'j': 'advance_ratio',
    'n': 'rpm', 'n_rpm': 'rpm', 'rotational_speed': 'rpm',
    # Electromagnetics
    'e_field': 'electric_field', 'h_field': 'magnetic_field',
    'f': 'frequency', 'freq': 'frequency', 'wl': 'wavelength', 'lam': 'wavelength',
}

def normalize_column_names(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    """
    Attempt to map non-standard column names to canonical APIE names.
    Returns (renamed_df, mapping_dict).
    Only renames when there's an unambiguous match.
    """
    rename_map: dict[str, str] = {}
    existing_canonical = set(df.columns)

    for col in df.columns:
        lower = col.lower().strip()
        if lower in COLUMN_ALIAS_MAP:
            canonical = COLUMN_ALIAS_MAP[lower]
            # Only rename if canonical name is not already taken
            if canonical not in existing_canonical and canonical not in rename_map.values():
                rename_map[col] = canonical

    if rename_map:
        df = df.rename(columns=rename_map)

    return df, rename_map


# Module-level singleton
_manifold_validator = PhysicsManifoldValidator()

def validate_manifold(
    df: pd.DataFrame,
    prior_clean_X: np.ndarray | None = None,
    inlier_mask: np.ndarray | None = None,
) -> ManifoldResult:
    """Validate a dataset against its physics manifold. Module-level convenience function."""
    return _manifold_validator.validate(df, prior_clean_X=prior_clean_X, inlier_mask=inlier_mask)
