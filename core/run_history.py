"""
SimAPI — Run History Tracker
==============================

The single most important architectural gap in the original system:
validation in isolation. A simulation dataset that looks clean on its own
can be deeply wrong relative to the 200 previous runs of the same configuration.

This module gives APIE temporal memory.

Architecture
------------
A RunHistoryTracker is keyed to a (simulation_config_hash, domain) pair.
It maintains a compact statistical summary of all historical runs —
their fingerprints, column distributions, and APIE validation results.

When a new dataset arrives:
  1. Compute its fingerprint (already done by APIE Layer 1)
  2. Compare against the historical envelope:
     - Column mean/std drift vs. historical mean-of-means / pooled std
     - Ratio invariant baselines vs. learned historical baseline
     - Copy-paste fraction vs. historical norm
     - Residual entropy vs. historical norm
  3. Return cross-run anomaly scores per column and per invariant
  4. Flag runs that are outliers in the historical sequence even when
     they pass all within-run checks

This catches:
  - "Silent drift" corruptions: each individual run looks fine,
    but column 3 has been slowly moving for 40 runs
  - Configuration change contamination: someone updated a mesh parameter
    and the solver quietly started producing different values
  - Batch labeling errors: run_047 was labeled as config_A but its
    fingerprint matches config_B's historical distribution

Storage
-------
Summaries are compact (~2KB per run). A 1000-run history fits in 2MB.
The tracker uses welford online statistics for O(1) updates.
Persistence: caller provides a dict (in-memory) or path (JSON file).
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

# ═══════════════════════════════════════════════════════════════════════════════
# Data structures
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ColumnSummary:
    """Welford running stats for one column across runs."""
    n: int = 0           # number of runs seen
    mean_of_means: float = 0.0
    m2_of_means: float = 0.0   # for variance of run-means (Welford)
    mean_of_stds: float = 0.0
    m2_of_stds: float = 0.0
    mean_of_medians: float = 0.0
    m2_of_medians: float = 0.0

    def update(self, run_mean: float, run_std: float, run_median: float):
        self.n += 1
        # Welford update for run-means
        delta = run_mean - self.mean_of_means
        self.mean_of_means += delta / self.n
        delta2 = run_mean - self.mean_of_means
        self.m2_of_means += delta * delta2
        # stds
        d = run_std - self.mean_of_stds
        self.mean_of_stds += d / self.n
        self.m2_of_stds += d * (run_std - self.mean_of_stds)
        # medians
        d = run_median - self.mean_of_medians
        self.mean_of_medians += d / self.n
        self.m2_of_medians += d * (run_median - self.mean_of_medians)

    @property
    def std_of_means(self) -> float:
        return np.sqrt(self.m2_of_means / max(self.n - 1, 1))

    @property
    def std_of_stds(self) -> float:
        return np.sqrt(self.m2_of_stds / max(self.n - 1, 1))


@dataclass
class RunRecord:
    """Compact record of one validation run."""
    run_id: str
    timestamp: float
    n_rows: int
    column_stats: dict[str, tuple[float, float, float]]  # col → (mean, std, median)
    ratio_baselines: dict[str, float]                     # "col_a/col_b" → ratio value
    copy_paste_fraction: float
    residual_entropy: float
    n_excluded: int
    n_flagged: int
    corruption_types_found: list[str]


@dataclass
class CrossRunAnomaly:
    """A column or invariant that deviates from historical norms."""
    kind: str           # 'column_mean_drift' | 'column_std_spike' | 'ratio_drift' | 'entropy_shift'
    subject: str        # column name or ratio pair
    current_value: float
    historical_mean: float
    historical_std: float
    sigma: float
    severity: str       # 'warning' | 'critical'
    interpretation: str


@dataclass
class CrossRunResult:
    """What the history tracker found for this run."""
    n_historical_runs: int
    anomalies: list[CrossRunAnomaly]
    run_is_outlier: bool       # True if this run is a statistical outlier in the history
    config_match_score: float  # 0-1: how similar is this to expected fingerprint
    new_baseline_learned: bool # True if this run was added to the history
    historical_envelope: dict[str, Any]  # summarised for display
    processing_ms: float


# ═══════════════════════════════════════════════════════════════════════════════
# Run History Tracker
# ═══════════════════════════════════════════════════════════════════════════════

class RunHistoryTracker:
    """
    Temporal memory for APIE.

    Keyed to a simulation configuration (you supply a config_key — typically
    a hash of your mesh + solver + physics parameters).  Every validated run
    is summarised and stored; future runs are compared against this history.

    Usage:
        tracker = RunHistoryTracker(storage_path="my_sim_history.json")
        cross_run = tracker.check_and_update(
            fingerprint=apie_result.fingerprint,
            n_excluded=len(apie_result.excluded_indices),
            n_flagged=len(apie_result.flagged_for_review),
            corruption_types=list(apie_result.test_plan.suspected_corruption_types),
            config_key="mesh_v3_SST_Re1e6",
        )
        if cross_run.run_is_outlier:
            print("This run looks different from historical baseline!")
    """

    def __init__(self, storage_path: str | None = None,
                 max_runs_per_config: int = 500):
        self.max_runs = max_runs_per_config
        self._storage_path = Path(storage_path) if storage_path else None
        self._data: dict[str, Any] = self._load()

    # ── Public API ─────────────────────────────────────────────────────────────

    def check_and_update(
        self,
        fingerprint,                    # CorruptionFingerprint from APIE Layer 1
        config_key: str,               # identifies the simulation configuration
        n_excluded: int = 0,
        n_flagged: int = 0,
        corruption_types: list[str] | None = None,
        run_id: str | None = None,
    ) -> CrossRunResult:
        """
        Compare this run's fingerprint against history, then record it.

        This is the main entry point. Call it after APIE validates a dataset.
        Returns a CrossRunResult with any cross-run anomalies found.
        """
        t0 = time.time()
        key = self._norm_key(config_key)
        history = self._data.setdefault(key, self._empty_history())

        run_id = run_id or f"run_{int(time.time()*1000)}"
        n_hist = len(history['runs'])

        # ── Compare against history ────────────────────────────────────────
        anomalies: list[CrossRunAnomaly] = []
        config_match = 1.0

        if n_hist >= 3:   # need at least 3 runs to establish a baseline
            anomalies, config_match = self._compare_to_history(
                fingerprint, history, n_hist
            )

        # ── Determine if this run is an outlier ────────────────────────────
        critical = [a for a in anomalies if a.severity == 'critical']
        is_outlier = (
            len(critical) >= 2 or
            config_match < 0.6 or
            any(a.sigma > 5 for a in anomalies)
        )

        # ── Update history ─────────────────────────────────────────────────
        self._record_run(history, fingerprint, run_id, n_excluded, n_flagged,
                         corruption_types or [])
        self._maybe_save()

        ms = (time.time() - t0) * 1000
        envelope = self._build_envelope(history) if n_hist >= 3 else {}

        return CrossRunResult(
            n_historical_runs=n_hist,
            anomalies=anomalies,
            run_is_outlier=is_outlier,
            config_match_score=round(config_match, 3),
            new_baseline_learned=True,
            historical_envelope=envelope,
            processing_ms=round(ms, 1),
        )

    def get_trend(self, config_key: str, column: str,
                  last_n: int = 20) -> dict[str, Any]:
        """
        Return the trend of a specific column's mean across the last N runs.
        Useful for plotting drift over time.
        """
        key = self._norm_key(config_key)
        history = self._data.get(key, self._empty_history())
        runs = history['runs'][-last_n:]
        return {
            'run_ids': [r['run_id'] for r in runs],
            'timestamps': [r['timestamp'] for r in runs],
            'means': [r['column_stats'].get(column, [None, None, None])[0] for r in runs],
            'stds': [r['column_stats'].get(column, [None, None, None])[1] for r in runs],
        }

    def n_runs(self, config_key: str) -> int:
        key = self._norm_key(config_key)
        return len(self._data.get(key, {}).get('runs', []))

    def clear(self, config_key: str):
        key = self._norm_key(config_key)
        if key in self._data:
            del self._data[key]
            self._maybe_save()

    # ── Internal ────────────────────────────────────────────────────────────────

    def _compare_to_history(
        self, fp, history: dict, n_hist: int
    ) -> tuple[list[CrossRunAnomaly], float]:
        """Core comparison logic."""
        anomalies = []
        col_summaries: dict[str, dict] = history.get('col_summaries', {})
        ratio_summaries: dict[str, dict] = history.get('ratio_summaries', {})
        meta: dict = history.get('meta', {})

        # ── Column mean drift ──────────────────────────────────────────────
        for col, stats in fp.col_stats.items():
            run_mean, run_std, _, _, _, _ = stats
            if col not in col_summaries:
                continue
            cs = col_summaries[col]
            hist_mean = cs['mean_of_means']
            hist_std  = cs['std_of_means']
            if hist_std < 1e-10:
                continue
            sigma_drift = abs(run_mean - hist_mean) / hist_std
            if sigma_drift > 2.5:
                sev = 'critical' if sigma_drift > 4.5 else 'warning'
                anomalies.append(CrossRunAnomaly(
                    kind='column_mean_drift',
                    subject=col,
                    current_value=run_mean,
                    historical_mean=hist_mean,
                    historical_std=hist_std,
                    sigma=round(sigma_drift, 2),
                    severity=sev,
                    interpretation=(
                        f"'{col}' mean has shifted {sigma_drift:.1f}σ from the "
                        f"historical baseline across {n_hist} runs. "
                        f"Current: {run_mean:.4g} | Historical: {hist_mean:.4g}±{hist_std:.4g}. "
                        f"{'Likely mesh/solver configuration change.' if sigma_drift > 4 else 'Possible gradual calibration drift or test condition change.'}"
                    )
                ))

            # Check std spike (variance increase = numerical instability onset)
            hist_std_of_stds = cs.get('std_of_stds', 0)
            hist_mean_of_stds = cs.get('mean_of_stds', run_std)
            if hist_std_of_stds > 1e-10:
                sigma_std = (run_std - hist_mean_of_stds) / hist_std_of_stds
                if sigma_std > 3.5:
                    anomalies.append(CrossRunAnomaly(
                        kind='column_std_spike',
                        subject=col,
                        current_value=run_std,
                        historical_mean=hist_mean_of_stds,
                        historical_std=hist_std_of_stds,
                        sigma=round(sigma_std, 2),
                        severity='warning',
                        interpretation=(
                            f"'{col}' within-run variance is {sigma_std:.1f}σ higher than usual. "
                            "Increased scatter suggests mesh instability, solver looseness, or "
                            "test condition variability not seen in prior runs."
                        )
                    ))

        # ── Ratio invariant drift ──────────────────────────────────────────
        for pair, (ratio, _mad, _tau, _p) in fp.ratio_signals.items():
            if pair not in ratio_summaries:
                continue
            rs = ratio_summaries[pair]
            hist_ratio = rs['mean']
            hist_std   = rs['std']
            if hist_std < 1e-10 or abs(hist_ratio) < 1e-10:
                continue
            sigma_ratio = abs(ratio - hist_ratio) / hist_std
            if sigma_ratio > 3.0:
                sev = 'critical' if sigma_ratio > 5.0 else 'warning'
                anomalies.append(CrossRunAnomaly(
                    kind='ratio_drift',
                    subject=pair,
                    current_value=ratio,
                    historical_mean=hist_ratio,
                    historical_std=hist_std,
                    sigma=round(sigma_ratio, 2),
                    severity=sev,
                    interpretation=(
                        f"Physical ratio {pair} = {ratio:.4g} deviates {sigma_ratio:.1f}σ "
                        f"from historical baseline {hist_ratio:.4g}±{hist_std:.4g}. "
                        "This ratio should be a physical constant — deviation indicates "
                        "a change in fluid properties, reference conditions, or data format."
                    )
                ))

        # ── Copy-paste fraction vs history ─────────────────────────────────
        hist_cp_mean = meta.get('mean_copy_paste', 0)
        hist_cp_std  = meta.get('std_copy_paste', 0.001)
        if hist_cp_std > 1e-6 and fp.copy_paste_fraction > hist_cp_mean + 4 * hist_cp_std:
            anomalies.append(CrossRunAnomaly(
                kind='copy_paste_spike',
                subject='copy_paste_fraction',
                current_value=fp.copy_paste_fraction,
                historical_mean=hist_cp_mean,
                historical_std=hist_cp_std,
                sigma=round((fp.copy_paste_fraction - hist_cp_mean) / hist_cp_std, 1),
                severity='critical',
                interpretation=(
                    f"Copy-paste fraction {fp.copy_paste_fraction:.5f} is unusually high vs. "
                    f"historical norm {hist_cp_mean:.5f}. Solver may have frozen or "
                    "post-processing script may have duplicated output rows."
                )
            ))

        # ── Residual entropy shift ─────────────────────────────────────────
        hist_ent_mean = meta.get('mean_entropy', 2.0)
        hist_ent_std  = meta.get('std_entropy', 0.3)
        if hist_ent_std > 1e-6:
            sigma_ent = abs(fp.residual_entropy - hist_ent_mean) / hist_ent_std
            if sigma_ent > 3.0:
                direction = "lower" if fp.residual_entropy < hist_ent_mean else "higher"
                anomalies.append(CrossRunAnomaly(
                    kind='entropy_shift',
                    subject='residual_entropy',
                    current_value=fp.residual_entropy,
                    historical_mean=hist_ent_mean,
                    historical_std=hist_ent_std,
                    sigma=round(sigma_ent, 2),
                    severity='warning',
                    interpretation=(
                        f"Residual entropy is {direction} than usual ({fp.residual_entropy:.3f} vs "
                        f"historical {hist_ent_mean:.3f}±{hist_ent_std:.3f}). "
                        f"{'Lower entropy = more deterministic/frozen output = possible solver stall.' if direction == 'lower' else 'Higher entropy = noisier than usual = possible mesh degradation.'}"
                    )
                ))

        # ── Config match score ──────────────────────────────────────────────
        # Based on fraction of columns and ratios within 2σ of historical
        total_checks = len(col_summaries) + len(ratio_summaries)
        if total_checks == 0:
            config_match = 1.0
        else:
            n_anomalies = len([a for a in anomalies
                               if a.kind in ('column_mean_drift', 'ratio_drift')])
            config_match = max(0.0, 1.0 - n_anomalies / max(total_checks, 1))

        return anomalies, config_match

    def _record_run(self, history: dict, fp, run_id: str,
                    n_excluded: int, n_flagged: int, corruption_types: list[str]):
        """Record this run into the history."""
        # Build run record
        col_stats_compact = {
            col: (round(v[0], 6), round(v[1], 6), round(v[4], 6))   # mean, std, mad
            for col, v in fp.col_stats.items()
        }
        record = {
            'run_id': run_id,
            'timestamp': time.time(),
            'n_rows': fp.n_rows,
            'column_stats': col_stats_compact,
            'ratio_baselines': {k: round(v, 8) for k, v in fp.discovered_invariants.items()},
            'copy_paste_fraction': fp.copy_paste_fraction,
            'residual_entropy': fp.residual_entropy,
            'n_excluded': n_excluded,
            'n_flagged': n_flagged,
            'corruption_types_found': corruption_types,
        }
        history['runs'].append(record)
        # Trim to max_runs
        if len(history['runs']) > self.max_runs:
            history['runs'] = history['runs'][-self.max_runs:]

        # Update Welford summaries
        for col, (mean, std, _med) in col_stats_compact.items():
            cs = history['col_summaries'].setdefault(col, {
                'n': 0, 'mean_of_means': 0.0, 'm2_of_means': 0.0,
                'mean_of_stds': 0.0, 'm2_of_stds': 0.0,
                'std_of_means': 0.0, 'std_of_stds': 0.0,
            })
            n = cs['n'] + 1; cs['n'] = n
            for val, mk, m2k in [(mean, 'mean_of_means', 'm2_of_means'),
                                  (std,  'mean_of_stds',  'm2_of_stds')]:
                delta = val - cs[mk]; cs[mk] += delta / n
                cs[m2k] += delta * (val - cs[mk])
            cs['std_of_means'] = np.sqrt(cs['m2_of_means'] / max(n-1, 1))
            cs['std_of_stds']  = np.sqrt(cs['m2_of_stds']  / max(n-1, 1))

        for pair, (ratio, _mad, _tau, _p) in fp.ratio_signals.items():
            rs = history['ratio_summaries'].setdefault(pair, {'n': 0, 'mean': 0.0, 'M2': 0.0, 'std': 0.0})
            rs['n'] += 1; n = rs['n']
            delta = ratio - rs['mean']; rs['mean'] += delta / n
            rs['M2'] += delta * (ratio - rs['mean'])
            rs['std'] = np.sqrt(rs['M2'] / max(n-1, 1))

        meta = history['meta']
        for val, mk, m2k in [
            (fp.copy_paste_fraction, 'mean_copy_paste', 'm2_copy_paste'),
            (fp.residual_entropy,    'mean_entropy',     'm2_entropy'),
        ]:
            n_meta = meta.setdefault(mk + '_n', 0) + 1
            meta[mk + '_n'] = n_meta
            delta = val - meta.get(mk, 0.0); meta[mk] = meta.get(mk, 0.0) + delta / n_meta
            meta[m2k] = meta.get(m2k, 0.0) + delta * (val - meta[mk])
        meta['std_copy_paste'] = np.sqrt(meta.get('m2_copy_paste', 0) / max(meta.get('mean_copy_paste_n',1)-1,1))
        meta['std_entropy']    = np.sqrt(meta.get('m2_entropy', 0)    / max(meta.get('mean_entropy_n',1)-1,1))

    def _build_envelope(self, history: dict) -> dict[str, Any]:
        """Summary of the historical envelope for display."""
        cs = history['col_summaries']
        return {
            'n_runs': len(history['runs']),
            'columns_tracked': list(cs.keys()),
            'column_means': {col: round(v['mean_of_means'], 4) for col, v in cs.items()},
            'column_stds':  {col: round(v['std_of_means'], 4)  for col, v in cs.items()},
        }

    @staticmethod
    def _empty_history() -> dict:
        return {'runs': [], 'col_summaries': {}, 'ratio_summaries': {}, 'meta': {}}

    @staticmethod
    def _norm_key(k: str) -> str:
        return hashlib.sha256(k.encode()).hexdigest()[:16]

    def _load(self) -> dict:
        if self._storage_path and self._storage_path.exists():
            try:
                return json.loads(self._storage_path.read_text())
            except Exception:
                return {}
        return {}

    def _maybe_save(self):
        if self._storage_path:
            try:
                self._storage_path.write_text(json.dumps(self._data))
            except Exception:
                pass


# Module-level default tracker (in-memory, per-process)
_default_tracker = RunHistoryTracker()

def get_default_tracker() -> RunHistoryTracker:
    return _default_tracker
