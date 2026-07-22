"""
SimAPI — Adversarial Red Team
================================

"If I were to ask an AI to construct data to fool this filter, would it have
an easy job doing so? Because if so, that's a problem."

Yes. It would. This module proves it — and then uses that knowledge.

The AdversarialRedTeam generates the HARDEST-TO-DETECT corruptions for a given
dataset and domain, then shows you exactly which ones APIE catches and which
ones slip through. This serves two purposes:

1. HONEST product positioning: we tell customers exactly where the blind spots are
   instead of hiding behind headline recall numbers on easy corruptions.

2. ACTIONABLE gap analysis: the blind spots in APIE's detection directly reveal
   which simulation pipeline controls need to be strengthened.

Attack taxonomy (ordered by difficulty to detect):
  EASY: Physical bounds violations, unit errors (ratio 1000× off)
  MEDIUM: Copy-paste blocks, isolated solver spikes
  HARD: Distribution-preserving corruptions (values in-distribution but wrong)
  HARD: Correlated multi-column perturbations (preserve all ratios while biasing target)
  VERY HARD: Temporal camouflage (ramp in/out over N rows)
  VERY HARD: Feature-space perturbations (shift in direction of maximum model uncertainty)

The module generates attacks at each tier, runs APIE against them, and reports
what survived detection. The output is a red team report that can be shown to
customers and used to prioritize detection improvements.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class AttackSpec:
    """One adversarial attack configuration."""
    name: str
    tier: str              # 'easy' | 'medium' | 'hard' | 'very_hard'
    description: str
    n_rows: int
    expected_detection: str  # 'definitely' | 'probably' | 'unlikely' | 'no'


@dataclass  
class AttackResult:
    """Result of one attack attempt."""
    attack_name: str
    tier: str
    n_injected: int
    n_detected_auto: int      # auto-removed by APIE
    n_detected_review: int    # flagged for review
    n_evaded: int             # completely missed
    detection_rate_auto: float
    detection_rate_combined: float
    fp_rate: float            # clean rows incorrectly flagged
    how_it_works: str
    why_hard: str
    mitigation: str


@dataclass
class RedTeamReport:
    """Full adversarial red team assessment."""
    domain: str
    n_rows: int
    attack_results: list[AttackResult]
    overall_detection_rate: float
    hard_evasion_rate: float     # fraction of HARD attacks that evaded detection
    apie_grade: str              # 'A' through 'F'
    blind_spots: list[str]
    recommendations: list[str]
    processing_ms: float


class AdversarialRedTeam:
    """
    Generates and evaluates adversarial attacks against APIE.

    This is the answer to "would an AI have an easy job fooling this?"
    The honest answer is shown in the report.
    """

    def __init__(self, apie_engine=None):
        self._apie = apie_engine

    def run_red_team(
        self,
        df_clean: pd.DataFrame,
        domain: str,
        conditions: dict | None = None,
        n_attack_rows: int = 50,
        seed: int = 42,
    ) -> RedTeamReport:
        """
        Run all attack tiers against APIE and produce a red team report.
        
        Args:
            df_clean: A clean baseline dataset (APIE should flag nothing)
            domain: The simulation domain
            n_attack_rows: Number of rows to corrupt per attack (default 50)
            seed: Random seed for reproducibility
        """
        t0 = time.time()
        rng = np.random.default_rng(seed)
        n = len(df_clean)
        conditions = conditions or {}

        if self._apie is None:
            from core.apie import AdaptivePhysicsIntelligenceEngine
            self._apie = AdaptivePhysicsIntelligenceEngine()

        # Verify baseline FP rate
        r_clean = self._apie.validate(df_clean.copy(), domain, conditions)
        baseline_fp = len(r_clean.excluded_indices)

        # Run attacks
        results: list[AttackResult] = []
        numeric_cols = df_clean.select_dtypes(include=[np.number]).columns.tolist()
        target_rows = sorted(rng.choice(n, size=min(n_attack_rows, n//4), replace=False).tolist())
        set(target_rows)

        # ── TIER 1 (EASY): Physical law violations ─────────────────────────
        res = self._attack_physical_bounds(df_clean, domain, conditions, target_rows,
                                           numeric_cols, rng, baseline_fp)
        results.append(res)

        # ── TIER 1 (EASY): Unit error (factor 1000) ────────────────────────
        res = self._attack_unit_error(df_clean, domain, conditions, target_rows,
                                      numeric_cols, rng, baseline_fp)
        results.append(res)

        # ── TIER 2 (MEDIUM): Isolated solver divergence ────────────────────
        res = self._attack_isolated_spikes(df_clean, domain, conditions, target_rows,
                                           numeric_cols, rng, baseline_fp)
        results.append(res)

        # ── TIER 2 (MEDIUM): Copy-paste block ──────────────────────────────
        res = self._attack_copypaste(df_clean, domain, conditions, target_rows, rng, baseline_fp)
        results.append(res)

        # ── TIER 3 (HARD): Distribution-preserving ─────────────────────────
        res = self._attack_distribution_preserving(df_clean, domain, conditions,
                                                    target_rows, numeric_cols, rng, baseline_fp)
        results.append(res)

        # ── TIER 3 (HARD): Correlated multi-column ────────────────────────
        res = self._attack_correlated_multicolumn(df_clean, domain, conditions,
                                                   target_rows, numeric_cols, rng, baseline_fp)
        results.append(res)

        # ── TIER 4 (VERY HARD): Temporal camouflage ───────────────────────
        res = self._attack_temporal_camouflage(df_clean, domain, conditions,
                                                target_rows, numeric_cols, rng, baseline_fp)
        results.append(res)

        # ── TIER 4 (VERY HARD): Feature-space boundary ────────────────────
        res = self._attack_boundary_perturbation(df_clean, domain, conditions,
                                                  target_rows, numeric_cols, rng, baseline_fp)
        results.append(res)

        # ── Build report ──────────────────────────────────────────────────
        ms = (time.time() - t0) * 1000
        return self._build_report(results, domain, n, ms)

    # ── Attack implementations ──────────────────────────────────────────────

    def _run_apie(self, df, domain, conditions, target_set, baseline_fp):
        """Run APIE and return (n_auto, n_review, n_evaded, fp_rate)."""
        r = self._apie.validate(df.copy(), domain, conditions)
        auto = r.excluded_indices
        review = {f['row_index'] for f in r.flagged_for_review}
        n = len(df)
        n_auto   = len(auto & target_set)
        n_review = len((review - auto) & target_set)
        n_evaded = len(target_set) - n_auto - n_review
        fp = max(0, len(auto - target_set) - baseline_fp) / max(n - len(target_set), 1)
        return n_auto, n_review, n_evaded, fp

    def _attack_physical_bounds(self, df, domain, conditions, rows, cols, rng, bfp):
        df2 = df.copy()
        # Prefer attacking the primary target column — most damaging and most detectable
        # Use last column as proxy for "derived" quantities (usually target-like)
        # Or use any column that has established physical bounds in the domain profile
        priority_cols = ['winding_temperature', 'thrust_coefficient', 'propulsive_efficiency',
                         'von_mises_stress', 'safety_factor', 'mechanical_power',
                         'drag_coefficient', 'pressure', 'temperature']
        col = next((c for c in priority_cols if c in df.columns), cols[0])
        stats = df[col].describe()
        for i in rows:
            df2.at[i, col] = stats['max'] * rng.uniform(5, 20)
        n_auto, n_rev, n_ev, fp = self._run_apie(df2, domain, conditions, set(rows), bfp)
        return AttackResult(
            attack_name="Physical Bounds Violation",
            tier="easy",
            n_injected=len(rows), n_detected_auto=n_auto, n_detected_review=n_rev, n_evaded=n_ev,
            detection_rate_auto=n_auto/len(rows), detection_rate_combined=(n_auto+n_rev)/len(rows),
            fp_rate=fp,
            how_it_works=f"Set {col} to 5-20× its maximum observed value. Values are obviously out of physical range.",
            why_hard="It isn't. Physical bounds violations are the easiest corruptions to detect.",
            mitigation="Already handled: physical_bounds check catches this with near-100% recall.",
        )

    def _attack_unit_error(self, df, domain, conditions, rows, cols, rng, bfp):
        df2 = df.copy()
        # Unit errors most impactful on quasi-constant columns (fixed parameters)
        # or columns with known physical constants as ratios
        priority_cols = ['ambient_temperature', 'pressure', 'rpm', 'winding_resistance',
                         'density', 'elastic_modulus', 'wall_thickness']
        col = next((c for c in priority_cols if c in df.columns), cols[0])
        for i in rows:
            df2.at[i, col] = df2.at[i, col] / 1000.0
        n_auto, n_rev, n_ev, fp = self._run_apie(df2, domain, conditions, set(rows), bfp)
        return AttackResult(
            attack_name="Unit Error (Factor 1000)",
            tier="easy",
            n_injected=len(rows), n_detected_auto=n_auto, n_detected_review=n_rev, n_evaded=n_ev,
            detection_rate_auto=n_auto/len(rows), detection_rate_combined=(n_auto+n_rev)/len(rows),
            fp_rate=fp,
            how_it_works=f"Divide {col} by 1000 (simulating Pa→kPa or m→mm type error).",
            why_hard="Not hard when it's a clean factor error — ratio invariant catches it.",
            mitigation="Already handled: ratio_invariant and quasi_constant_bounds check this.",
        )

    def _attack_isolated_spikes(self, df, domain, conditions, rows, cols, rng, bfp):
        df2 = df.copy()
        target_col = cols[rng.integers(0, len(cols))]
        spike_rows = rows[:len(rows)//3]  # only 1/3 of rows, more sparse
        for i in spike_rows:
            df2.at[i, target_col] = df[target_col].mean() + 12 * df[target_col].std()
        n_auto, n_rev, n_ev, fp = self._run_apie(df2, domain, conditions, set(spike_rows), bfp)
        return AttackResult(
            attack_name="Isolated Solver Spikes",
            tier="medium",
            n_injected=len(spike_rows), n_detected_auto=n_auto, n_detected_review=n_rev, n_evaded=n_ev,
            detection_rate_auto=n_auto/max(len(spike_rows),1), detection_rate_combined=(n_auto+n_rev)/max(len(spike_rows),1),
            fp_rate=fp,
            how_it_works=f"Insert 12σ spikes in {target_col} at sparse random rows (solver divergence pattern).",
            why_hard="Sparse isolation makes temporal coherence less effective; needs global outlier detection.",
            mitigation="ensemble_predictor and physical_bounds catch extreme spikes well.",
        )

    def _attack_copypaste(self, df, domain, conditions, rows, rng, bfp):
        df2 = df.copy()
        src = int(rng.integers(0, len(df)))
        paste_rows = rows[:len(rows)//2]
        for i in paste_rows:
            df2.iloc[i] = df2.iloc[src]
        n_auto, n_rev, n_ev, fp = self._run_apie(df2, domain, conditions, set(paste_rows), bfp)
        return AttackResult(
            attack_name="Copy-Paste Block",
            tier="medium",
            n_injected=len(paste_rows), n_detected_auto=n_auto, n_detected_review=n_rev, n_evaded=n_ev,
            detection_rate_auto=n_auto/max(len(paste_rows),1), detection_rate_combined=(n_auto+n_rev)/max(len(paste_rows),1),
            fp_rate=fp,
            how_it_works="Replace a block of rows with copies of a single source row (frozen solver output).",
            why_hard="Cosine similarity catches dense blocks; sparse copy-paste is harder.",
            mitigation="copy_paste_block check with bidirectional scan handles this.",
        )

    def _attack_distribution_preserving(self, df, domain, conditions, rows, cols, rng, bfp):
        """
        THE HARD ATTACK: sample replacement values FROM the empirical distribution.
        Values are statistically plausible globally but wrong for their context.
        """
        df2 = df.copy()
        len(df)
        target_col = cols[min(1, len(cols)-1)]  # second column
        # Sample from the empirical distribution of this column
        all_vals = df[target_col].values
        for i in rows:
            # Sample a value that is in the 90th-99th percentile (plausible, not extreme)
            # but assign it to a row where physics says it should be in the 10th-50th percentile
            replacement = rng.choice(all_vals[all_vals > np.percentile(all_vals, 90)])
            df2.at[i, target_col] = replacement
        n_auto, n_rev, n_ev, fp = self._run_apie(df2, domain, conditions, set(rows), bfp)
        return AttackResult(
            attack_name="Distribution-Preserving Corruption",
            tier="hard",
            n_injected=len(rows), n_detected_auto=n_auto, n_detected_review=n_rev, n_evaded=n_ev,
            detection_rate_auto=n_auto/len(rows), detection_rate_combined=(n_auto+n_rev)/len(rows),
            fp_rate=fp,
            how_it_works=(
                f"Replace {target_col} in {len(rows)} rows with values sampled from the "
                "90th-99th percentile of the same column. Values are statistically plausible "
                "globally but wrong for their feature context (wrong regime)."
            ),
            why_hard=(
                "Physical bounds checks pass — values are in-distribution. "
                "The ensemble predictor catches some via feature-target mismatch, "
                "but if the correlation is weak, many evade detection. "
                "An AI attacker would specifically choose columns where feature-target "
                "correlation is lowest."
            ),
            mitigation=(
                "The ensemble_predictor catches this when feature-target correlation is high. "
                "The RunHistoryTracker catches it when this column's mean deviates from historical. "
                "Fundamental mitigation: cross-run baseline monitoring."
            ),
        )

    def _attack_correlated_multicolumn(self, df, domain, conditions, rows, cols, rng, bfp):
        """
        HARD: Perturb multiple columns by the SAME factor.
        All pairwise ratios are preserved. Bounds are not violated.
        """
        df2 = df.copy()
        if len(cols) < 2:
            return self._attack_isolated_spikes(df, domain, conditions, rows, cols, rng, bfp)
        factor = rng.uniform(3.0, 6.0)  # large enough to hurt the model
        perturb_cols = cols[:min(3, len(cols))]
        for i in rows:
            for col in perturb_cols:
                df2.at[i, col] = df2.at[i, col] * factor
        n_auto, n_rev, n_ev, fp = self._run_apie(df2, domain, conditions, set(rows), bfp)
        return AttackResult(
            attack_name="Correlated Multi-Column (Ratio-Preserving)",
            tier="hard",
            n_injected=len(rows), n_detected_auto=n_auto, n_detected_review=n_rev, n_evaded=n_ev,
            detection_rate_auto=n_auto/len(rows), detection_rate_combined=(n_auto+n_rev)/len(rows),
            fp_rate=fp,
            how_it_works=(
                f"Multiply columns {perturb_cols} by {factor:.1f}× simultaneously. "
                "All pairwise ratios between these columns are preserved exactly. "
                "Ratio invariant checks find nothing. Physical bounds may or may not trigger."
            ),
            why_hard=(
                "This is the canonical attack against ratio-invariant validators. "
                "Cd×5 AND Cl×5 means Cd/Cl is unchanged. The ratio_invariant check passes. "
                "Only the physical_bounds check, joint_skew, or ensemble can catch this. "
                "An AI would specifically choose columns where physical bounds are not tight."
            ),
            mitigation=(
                "APIE's joint_skew_outlier catches correlated blow-up in 2D. "
                "Physical bounds on INDIVIDUAL columns provide the safety net. "
                "Tighter per-column bounds in domain profiles reduce the attack surface."
            ),
        )

    def _attack_temporal_camouflage(self, df, domain, conditions, rows, cols, rng, bfp):
        """
        VERY HARD: Ramp corruptions in and out over 20 rows.
        Creates smooth transitions that defeat temporal coherence checks.
        """
        df2 = df.copy()
        len(df)
        if len(rows) < 10:
            return self._attack_correlated_multicolumn(df, domain, conditions, rows, cols, rng, bfp)
        
        target_col = cols[rng.integers(0, min(3, len(cols)))]
        target_corrupt = rows[:len(rows)//2]
        
        if not target_corrupt:
            return self._attack_isolated_spikes(df, domain, conditions, rows, cols, rng, bfp)
            
        plateau_val = df[target_col].mean() + 6 * df[target_col].std()
        ramp_len = min(10, len(target_corrupt)//3)
        
        for idx, i in enumerate(target_corrupt):
            if idx < ramp_len:
                # Ramp in: gradually increase
                alpha = idx / ramp_len
                df2.at[i, target_col] = df[target_col].iloc[i] * (1 + alpha * 5)
            elif idx > len(target_corrupt) - ramp_len:
                # Ramp out: gradually decrease
                alpha = (len(target_corrupt) - idx) / ramp_len
                df2.at[i, target_col] = df[target_col].iloc[i] * (1 + alpha * 5)
            else:
                # Plateau: full corruption
                df2.at[i, target_col] = plateau_val

        n_auto, n_rev, n_ev, fp = self._run_apie(df2, domain, conditions, set(target_corrupt), bfp)
        return AttackResult(
            attack_name="Temporal Camouflage (Ramp In/Out)",
            tier="very_hard",
            n_injected=len(target_corrupt), n_detected_auto=n_auto, n_detected_review=n_rev, n_evaded=n_ev,
            detection_rate_auto=n_auto/max(len(target_corrupt),1), detection_rate_combined=(n_auto+n_rev)/max(len(target_corrupt),1),
            fp_rate=fp,
            how_it_works=(
                f"Ramp {target_col} up over {ramp_len} rows, hold at 6σ corruption plateau, "
                f"then ramp back down. The transition looks like a legitimate operating condition change."
            ),
            why_hard=(
                "The temporal_coherence check looks at inter-row jumps. "
                "The ramp-in/ramp-out creates SMOOTH transitions (each step is small), "
                "so no individual jump exceeds 7σ. The plateau rows have extreme values "
                "but the ensemble may miss them if the plateau is long enough that the "
                "inlier baseline shifts. This is a known attack against streaming anomaly detectors."
            ),
            mitigation=(
                "The APIE RunHistoryTracker catches this: the column mean shifts during the attack. "
                "Within-run: the ensemble predictor catches the plateau if it's long (>50 rows). "
                "Physical bounds provide a hard stop if the plateau exceeds physical limits. "
                "Temporal slope monitoring (not yet implemented) would catch the ramp."
            ),
        )

    def _attack_boundary_perturbation(self, df, domain, conditions, rows, cols, rng, bfp):
        """
        VERY HARD: Perturbation in the direction of maximum model uncertainty.
        Small changes in features that maximally affect the target prediction
        without moving the statistical signature.
        """
        df2 = df.copy()
        if len(cols) < 2:
            return self._attack_temporal_camouflage(df, domain, conditions, rows, cols, rng, bfp)
        
        # Perturb features by 1-2σ in a correlated direction
        # This shifts the feature space without creating statistical outliers
        sigma_scale = 1.5
        perturb_col = cols[rng.integers(0, min(2, len(cols)))]
        col_std = df[perturb_col].std()
        
        for i in rows:
            # Add sigma-scale perturbation — stays within 2σ globally, WRONG for context
            direction = rng.choice([-1, 1])
            df2.at[i, perturb_col] = df.at[i, perturb_col] + direction * sigma_scale * col_std

        n_auto, n_rev, n_ev, fp = self._run_apie(df2, domain, conditions, set(rows), bfp)
        return AttackResult(
            attack_name="Boundary Feature Perturbation (1-2σ)",
            tier="very_hard",
            n_injected=len(rows), n_detected_auto=n_auto, n_detected_review=n_rev, n_evaded=n_ev,
            detection_rate_auto=n_auto/len(rows), detection_rate_combined=(n_auto+n_rev)/len(rows),
            fp_rate=fp,
            how_it_works=(
                f"Perturb {perturb_col} by ±{sigma_scale}σ (within the observed range). "
                "Values remain statistically plausible. The feature shift biases model predictions "
                "systematically without creating detectable anomalies."
            ),
            why_hard=(
                "This is the fundamental limitation of statistical validation. "
                "A 1-2σ perturbation is WITHIN the natural variation of the training data. "
                "No statistical test can distinguish a legitimately high-velocity row "
                "from a row where velocity was correctly measured but position was corrupted. "
                "Physics-informed forward simulation is needed to catch this — "
                "checking not just 'is this value plausible' but 'is THIS value plausible "
                "given the other variables in this specific row.'"
            ),
            mitigation=(
                "This cannot be caught by statistical validation alone. "
                "Mitigation requires: (1) cross-row physical consistency checks using domain models, "
                "(2) sim-to-real gap monitoring to catch systematic bias post-deployment, "
                "(3) ensemble model uncertainty quantification to flag low-confidence predictions. "
                "This is the theoretical detection limit of output-only validation."
            ),
        )

    def _build_report(self, results: list[AttackResult], domain: str,
                      n_rows: int, ms: float) -> RedTeamReport:
        """Build the summary report."""
        # Compute aggregate metrics
        total_injected = sum(r.n_injected for r in results)
        total_detected_auto = sum(r.n_detected_auto for r in results)
        total_detected_combined = sum(r.n_detected_auto + r.n_detected_review for r in results)
        overall_auto = total_detected_auto / max(total_injected, 1)
        overall_combined = total_detected_combined / max(total_injected, 1)

        hard_results = [r for r in results if r.tier in ('hard', 'very_hard')]
        hard_evasion = np.mean([r.n_evaded / max(r.n_injected, 1) for r in hard_results]) if hard_results else 0.0

        # Grade
        if overall_auto > 0.85 and hard_evasion < 0.4:
            grade = 'A'
        elif overall_auto > 0.70 and hard_evasion < 0.6:
            grade = 'B'
        elif overall_auto > 0.55:
            grade = 'C'
        elif overall_auto > 0.35:
            grade = 'D'
        else:
            grade = 'F'

        blind_spots = [r.attack_name for r in results if r.detection_rate_auto < 0.3]
        recs = list(dict.fromkeys(
            r.mitigation for r in results if r.n_evaded > r.n_detected_auto
        ))

        return RedTeamReport(
            domain=domain,
            n_rows=n_rows,
            attack_results=results,
            overall_detection_rate=round(overall_combined, 3),
            hard_evasion_rate=round(hard_evasion, 3),
            apie_grade=grade,
            blind_spots=blind_spots,
            recommendations=recs[:4],
            processing_ms=round(ms, 1),
        )
