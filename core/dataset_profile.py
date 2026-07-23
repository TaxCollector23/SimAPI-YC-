"""
SimAPI — Dataset Semantic Profiler (Phase A)
=============================================

The component that was missing. Everything downstream depends on one question
the physics engine cannot answer on its own:

    "Is row order MEANINGFUL, and if so, what does it mean?"

A simulation dataset is almost never a time series. It is usually a *designed
parameter sweep*: velocity stepped from 12 to 28 m/s, one row per step. In that
data, adjacent rows are supposed to be nearly identical, and columns are
supposed to be perfectly monotonic. Those are design properties, not defects.

An engine that assumes row-order == time will report:
  - "near-duplicate of trial 5 (sim=0.9999)"  -> it's a fine-grained sweep
  - "Mann-Kendall drift tau=1.000"            -> it's the swept variable
  - "discontinuous jump in velocity"          -> it's the step size

All three are false positives, and on a real customer sweep they can exceed 90%
of all findings. This module classifies the dataset first, then emits a
CheckMask telling the physics engine which checks are physically meaningless
for this data shape and which bounds must be widened for this regime.

Design principles
-----------------
1. DETERMINISTIC FIRST. Every conclusion here is reachable with statistics
   alone. The AI layer may only *refine* this profile, never replace it, and
   the system is fully functional with the AI disabled.
2. SUPPRESSION IS SCOPED AND EXPLAINED. A check is never disabled globally —
   it is disabled for named columns, with a stated reason that appears in the
   report. Silent suppression is how validators lose trust.
3. FAIL OPEN. If classification is uncertain, suppress nothing. A false
   positive is recoverable; a missed solver divergence is not.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# ═══════════════════════════════════════════════════════════════════════════════
# Canonical column names
# ═══════════════════════════════════════════════════════════════════════════════

CANONICAL_ALIASES: Dict[str, str] = {
    # Aerodynamics
    "cd": "drag_coefficient", "c_d": "drag_coefficient", "coef_drag": "drag_coefficient",
    "drag_coeff": "drag_coefficient", "cdrag": "drag_coefficient",
    "cl": "lift_coefficient", "c_l": "lift_coefficient", "coef_lift": "lift_coefficient",
    "lift_coeff": "lift_coefficient", "clift": "lift_coefficient",
    "cm": "pitching_moment", "c_m": "pitching_moment",
    "re": "reynolds_number", "rey": "reynolds_number", "reynolds": "reynolds_number",
    "ma": "mach_number", "mach": "mach_number", "m_inf": "mach_number",
    "u_inf": "velocity", "v_inf": "velocity", "uinf": "velocity", "vel": "velocity",
    "u": "velocity", "speed": "velocity", "freestream_velocity": "velocity",
    "aoa": "angle_of_attack", "alpha": "angle_of_attack",
    "p_ref": "pressure", "pref": "pressure", "p": "pressure", "pres": "pressure",
    "press": "pressure", "p_static": "pressure", "static_pressure": "pressure",
    "t_ref": "temperature", "tref": "temperature", "t": "temperature",
    "temp": "temperature", "t_static": "temperature",
    "rho": "density", "dens": "density", "rho_inf": "density",
    "mu": "dynamic_viscosity", "nu": "kinematic_viscosity",
    # Structural
    "e": "elastic_modulus", "youngs_modulus": "elastic_modulus",
    "sigma": "stress", "sigma_vm": "von_mises_stress", "vm_stress": "von_mises_stress",
    "sf": "safety_factor", "fos": "safety_factor",
    "eps": "strain", "epsilon": "strain", "nu_poisson": "poisson_ratio",
    # Thermal
    "t_wind": "winding_temperature", "t_winding": "winding_temperature",
    "t_case": "case_temperature", "t_amb": "ambient_temperature",
    "i_rms": "rms_current", "r_wind": "winding_resistance",
    "p_cu": "copper_loss", "p_fe": "iron_loss",
    # Robotics
    "tau": "joint_torque", "trq": "joint_torque", "omega": "joint_velocity",
    "q_dot": "joint_velocity", "q": "joint_position", "theta": "joint_position",
    "p_elec": "electrical_power", "p_mech": "mechanical_power",
    # Propeller / drone
    "ct": "thrust_coefficient", "cp": "power_coefficient",
    "eta": "propulsive_efficiency", "j": "advance_ratio",
    "n_rpm": "rpm", "rotational_speed": "rpm",
}

# Columns whose name implies row order really is time.
TIME_COLUMN_HINTS = {
    "time", "t_s", "timestamp", "step", "timestep", "iteration", "iter",
    "frame", "sample", "epoch", "cycle", "elapsed", "sim_time", "datetime",
}


def canonicalize_columns(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """
    Map non-standard column names onto canonical names.

    Only renames when unambiguous: the canonical target must not already exist
    and must not be claimed by another column in the same pass. Two columns
    competing for one canonical name means we understand neither, so we leave
    both alone rather than guess.
    """
    lowered = {c: c.lower().strip().replace(" ", "_") for c in df.columns}
    existing = set(df.columns)

    # Count how many source columns want each canonical target.
    demand: Dict[str, List[str]] = {}
    for col, low in lowered.items():
        target = CANONICAL_ALIASES.get(low)
        if target and target not in existing:
            demand.setdefault(target, []).append(col)

    rename: Dict[str, str] = {}
    for target, sources in demand.items():
        if len(sources) == 1:          # unambiguous
            rename[sources[0]] = target

    return (df.rename(columns=rename) if rename else df), rename


# ═══════════════════════════════════════════════════════════════════════════════
# Profile + mask
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Suppression:
    """One scoped, explained check suppression. Never silent."""
    check_family: str           # e.g. "near_duplicates"
    columns: List[str]          # [] means dataset-wide
    reason: str                 # shown verbatim in the report
    source: str = "deterministic"   # "deterministic" | "ai" | "user"


@dataclass
class BoundOverride:
    """A widened physical bound justified by the detected regime."""
    column: str
    lo: float
    hi: float
    reason: str
    source: str = "deterministic"


@dataclass
class CheckMask:
    """What the physics engine should skip or relax, and why."""
    suppressions: List[Suppression] = field(default_factory=list)
    bound_overrides: List[BoundOverride] = field(default_factory=list)

    def suppressed_families(self) -> Dict[str, Suppression]:
        return {s.check_family: s for s in self.suppressions}

    def is_suppressed(self, family: str, column: Optional[str] = None) -> bool:
        for s in self.suppressions:
            if s.check_family != family:
                continue
            if not s.columns:            # dataset-wide
                return True
            if column is not None and column in s.columns:
                return True
        return False

    def bounds_for(self, column: str) -> Optional[Tuple[float, float]]:
        for b in self.bound_overrides:
            if b.column == column:
                return (b.lo, b.hi)
        return None

    def to_dict(self) -> dict:
        return {
            "suppressions": [asdict(s) for s in self.suppressions],
            "bound_overrides": [asdict(b) for b in self.bound_overrides],
        }


@dataclass
class DatasetProfile:
    """Semantic understanding of the dataset, produced before validation."""
    design_type: str                  # parameter_sweep | time_series | monte_carlo | mixed | unknown
    design_confidence: float          # 0-1
    swept_columns: List[str]          # monotonic-by-design independent variables
    constant_columns: List[str]       # held fixed by design
    response_columns: List[str]       # everything else (dependent variables)
    regime: str                       # e.g. "subsonic", "transonic", "supersonic", "unknown"
    regime_evidence: str
    row_order_is_time: bool
    exact_duplicate_groups: List[List[int]]
    column_renames: Dict[str, str]
    n_rows: int
    n_numeric_cols: int
    notes: List[str]
    mask: CheckMask
    ai_refined: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        d["mask"] = self.mask.to_dict()
        return d

    def summary_line(self) -> str:
        bits = [f"{self.design_type.replace('_', ' ')} ({self.design_confidence:.0%} conf)"]
        if self.swept_columns:
            bits.append(f"swept: {', '.join(self.swept_columns[:3])}")
        if self.regime != "unknown":
            bits.append(f"regime: {self.regime}")
        return " · ".join(bits)


# ═══════════════════════════════════════════════════════════════════════════════
# Deterministic detectors
# ═══════════════════════════════════════════════════════════════════════════════

def _monotonic_score(v: np.ndarray) -> float:
    """
    Fraction of consecutive steps sharing the dominant sign.
    1.0 == perfectly monotonic. Robust to ties and to a few corrupted rows,
    which matters because a corrupted sweep is still a sweep.
    """
    if len(v) < 4:
        return 0.0
    d = np.diff(v)
    d = d[np.isfinite(d)]
    nz = d[np.abs(d) > 1e-12]
    if len(nz) < 3:
        return 0.0
    pos = float((nz > 0).sum())
    return max(pos, len(nz) - pos) / len(nz)


def _step_regularity(v: np.ndarray) -> float:
    """
    1.0 == perfectly even spacing (linspace). A designed sweep has near-constant
    step size; a physical time series generally does not.
    """
    if len(v) < 4:
        return 0.0
    d = np.diff(v)
    d = d[np.isfinite(d) & (np.abs(d) > 1e-12)]
    if len(d) < 3:
        return 0.0
    med = np.median(np.abs(d))
    if med < 1e-12:
        return 0.0
    return float(1.0 - min(1.0, np.median(np.abs(np.abs(d) - med)) / med))


def _exact_duplicate_groups(df: pd.DataFrame, cols: List[str]) -> List[List[int]]:
    """
    Groups of *genuinely identical* rows, compared per column on a relative
    scale. This is the correct replacement for cosine similarity: cosine on raw
    vectors is dominated by whichever column has the largest magnitude (usually
    Reynolds number ~1e5), so every row in a sweep looks parallel.
    """
    if not cols or len(df) < 2:
        return []
    X = df[cols].to_numpy(dtype=float, na_value=np.nan)
    scale = np.nanmax(np.abs(X), axis=0)
    scale[~np.isfinite(scale) | (scale == 0)] = 1.0
    Xn = X / scale

    seen: Dict[bytes, List[int]] = {}
    for i in range(len(Xn)):
        key = np.round(Xn[i], 9).tobytes()
        seen.setdefault(key, []).append(i)
    return [idx for idx in seen.values() if len(idx) > 1]


def _detect_regime(df: pd.DataFrame) -> Tuple[str, str]:
    """Classify the physical regime so bounds can be widened where justified."""
    if "mach_number" in df.columns:
        m = pd.to_numeric(df["mach_number"], errors="coerce").dropna()
        if len(m):
            mx = float(m.max())
            if mx > 5.0:
                return "hypersonic", f"max Mach {mx:.2f}"
            if mx > 1.2:
                return "supersonic", f"max Mach {mx:.2f}"
            if mx > 0.8:
                return "transonic", f"max Mach {mx:.2f}"
            if mx > 0.3:
                return "compressible_subsonic", f"max Mach {mx:.2f}"
            return "incompressible", f"max Mach {mx:.2f}"

    if "velocity" in df.columns:
        v = pd.to_numeric(df["velocity"], errors="coerce").dropna()
        if len(v):
            mx = float(v.max())
            a = 340.0
            if "temperature" in df.columns:
                t = pd.to_numeric(df["temperature"], errors="coerce").dropna()
                if len(t) and 100 < float(t.median()) < 4000:
                    a = float(np.sqrt(1.4 * 287.05 * t.median()))
            m_est = mx / a
            if m_est > 1.2:
                return "supersonic", f"max velocity {mx:.1f} m/s ≈ Mach {m_est:.2f}"
            if m_est > 0.8:
                return "transonic", f"max velocity {mx:.1f} m/s ≈ Mach {m_est:.2f}"
    return "unknown", "no Mach or velocity column"


# ═══════════════════════════════════════════════════════════════════════════════
# Profiler
# ═══════════════════════════════════════════════════════════════════════════════

# Check families that assume row order is time. Meaningless on a designed sweep.
TEMPORAL_FAMILIES = [
    "temporal_drift", "monotonicity", "autocorrelation",
    "stationarity", "temporal", "signal_quality",
]

# Regime-justified bound widening. Base bounds assume sea-level subsonic flight.
REGIME_BOUNDS: Dict[str, List[Tuple[str, float, float]]] = {
    "transonic":  [("velocity", 0.0, 500.0),  ("mach_number", 0.0, 1.3)],
    "supersonic": [("velocity", 0.0, 2000.0), ("mach_number", 0.0, 6.0)],
    "hypersonic": [("velocity", 0.0, 8000.0), ("mach_number", 0.0, 30.0)],
}


def profile_dataset(
    df: pd.DataFrame,
    simulation_type: str = "",
    conditions: Optional[dict] = None,
    canonicalize: bool = True,
) -> Tuple[pd.DataFrame, DatasetProfile]:
    """
    Classify a dataset and build its CheckMask. Pure statistics, no network.

    Returns (possibly_renamed_df, profile).
    """
    notes: List[str] = []
    renames: Dict[str, str] = {}

    if canonicalize:
        df, renames = canonicalize_columns(df)
        if renames:
            notes.append(
                f"Canonicalized {len(renames)} column name(s): "
                + ", ".join(f"{k}→{v}" for k, v in list(renames.items())[:6])
            )

    num_cols = [c for c in df.columns
                if pd.api.types.is_numeric_dtype(df[c])]
    n = len(df)

    # ── Constant / swept / response classification ──────────────────────────
    constant_cols: List[str] = []
    swept_cols: List[str] = []
    sweep_scores: Dict[str, float] = {}

    for c in num_cols:
        v = pd.to_numeric(df[c], errors="coerce").to_numpy(dtype=float)
        finite = v[np.isfinite(v)]
        if len(finite) < 2:
            continue
        spread = float(np.nanmax(finite) - np.nanmin(finite))
        denom = max(abs(float(np.nanmedian(finite))), 1e-12)
        if spread / denom < 1e-9:
            constant_cols.append(c)
            continue
        mono = _monotonic_score(v)
        reg = _step_regularity(v)
        sweep_scores[c] = mono * reg
        # Monotonic AND evenly stepped == swept by design, not drifting.
        if mono > 0.95 and reg > 0.80:
            swept_cols.append(c)

    response_cols = [c for c in num_cols
                     if c not in constant_cols and c not in swept_cols]

    # ── Is row order time? ──────────────────────────────────────────────────
    has_time_col = any(c.lower() in TIME_COLUMN_HINTS for c in df.columns)

    # ── Design classification ───────────────────────────────────────────────
    if has_time_col:
        design_type, design_conf = "time_series", 0.95
        notes.append("Explicit time/step column present — row order treated as temporal.")
    elif swept_cols:
        best = max(sweep_scores.get(c, 0.0) for c in swept_cols)
        design_type = "parameter_sweep"
        design_conf = float(min(0.99, 0.60 + 0.39 * best))
        notes.append(
            f"Monotonic, evenly-spaced column(s) detected ({', '.join(swept_cols[:3])}) "
            "— dataset is a designed parameter sweep, not a time series."
        )
    elif n >= 10 and num_cols:
        monos = [_monotonic_score(pd.to_numeric(df[c], errors="coerce").to_numpy(float))
                 for c in num_cols]
        if monos and max(monos) < 0.75:
            design_type, design_conf = "monte_carlo", 0.70
            notes.append("No monotonic structure — sampled/Monte-Carlo design assumed.")
        else:
            design_type, design_conf = "unknown", 0.40
    else:
        design_type, design_conf = "unknown", 0.30

    row_order_is_time = design_type == "time_series"

    # ── Regime ──────────────────────────────────────────────────────────────
    regime, regime_evidence = _detect_regime(df)

    # ── True duplicates ─────────────────────────────────────────────────────
    dup_groups = _exact_duplicate_groups(df, num_cols)
    if dup_groups:
        notes.append(
            f"{sum(len(g) - 1 for g in dup_groups)} exactly-duplicated row(s) "
            f"in {len(dup_groups)} group(s) — verified by per-column equality."
        )

    # ── Build the mask ──────────────────────────────────────────────────────
    mask = CheckMask()

    if design_type == "parameter_sweep":
        # Temporal checks on the swept variables are guaranteed false positives:
        # a swept column is monotonic by construction.
        for fam in TEMPORAL_FAMILIES:
            mask.suppressions.append(Suppression(
                check_family=fam,
                columns=[],   # dataset-wide: see reason
                reason=(
                    f"Designed sweep over '{', '.join(swept_cols[:3])}' (monotonic, "
                    "evenly spaced). Swept variables trend by construction, and every "
                    "response variable is a function of them, so it trends too. "
                    "Trend/drift/stationarity tests measure the sweep, not a defect."
                ),
            ))
        # Cosine near-duplicate detection cannot separate a fine-grained sweep
        # from a real duplicate; exact matching replaces it.
        mask.suppressions.append(Suppression(
            check_family="near_duplicates",
            columns=[],
            reason=(
                "Fine-grained parameter sweep: adjacent rows are similar by design. "
                "Cosine similarity cannot distinguish sweep spacing from duplication; "
                "exact per-column matching is used instead "
                f"({sum(len(g) - 1 for g in dup_groups)} true duplicate row(s) found)."
            ),
        ))

    # Applies to every design type, not just sweeps.
    if design_type != "parameter_sweep":
        mask.suppressions.append(Suppression(
            check_family="near_duplicates",
            columns=[],
            reason=(
                "Cosine similarity on raw feature vectors is dominated by the "
                "largest-magnitude column (e.g. Reynolds number ~1e5), so unrelated "
                "rows score >0.999. Replaced by exact per-column matching "
                f"({sum(len(g) - 1 for g in dup_groups)} true duplicate row(s) found)."
            ),
        ))

    if design_type == "monte_carlo":
        mask.suppressions.append(Suppression(
            check_family="autocorrelation",
            columns=[],
            reason="Randomly sampled design — sequential correlation is not meaningful.",
        ))

    for col, lo, hi in REGIME_BOUNDS.get(regime, []):
        if col in df.columns:
            mask.bound_overrides.append(BoundOverride(
                column=col, lo=lo, hi=hi,
                reason=f"{regime.replace('_', ' ')} regime detected ({regime_evidence}); "
                       f"default subsonic bound on '{col}' would reject valid data.",
            ))

    return df, DatasetProfile(
        design_type=design_type,
        design_confidence=round(design_conf, 3),
        swept_columns=swept_cols,
        constant_columns=constant_cols,
        response_columns=response_cols,
        regime=regime,
        regime_evidence=regime_evidence,
        row_order_is_time=row_order_is_time,
        exact_duplicate_groups=dup_groups,
        column_renames=renames,
        n_rows=n,
        n_numeric_cols=len(num_cols),
        notes=notes,
        mask=mask,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Mask application
# ═══════════════════════════════════════════════════════════════════════════════

def _columns_mentioned(text: str, known: List[str]) -> List[str]:
    """Which known column names appear in a check name or exclusion reason."""
    low = (text or "").lower()
    # Longest-first so 'joint_velocity' wins over 'velocity'.
    return [c for c in sorted(known, key=len, reverse=True) if c.lower() in low]


# Findings state their physics in prose ("Mann-Kendall drift in velocity"), not
# by family name, so family membership is resolved from vocabulary. Order
# matters: the first match wins.
FAMILY_KEYWORDS: List[Tuple[str, Tuple[str, ...]]] = [
    ("near_duplicates", ("near-duplicate", "near duplicate", "cosine", "sim=", "duplicate of trial")),
    ("temporal_drift",  ("mann-kendall", "mann kendall", "drift", "drifted", "trend",
                         "change-point", "changepoint", "segment", "creep",
                         "τ=", "tau=")),
    ("autocorrelation", ("autocorrel", "lag-", "lag correlation", "durbin")),
    ("stationarity",    ("stationar", "adf", "kpss", "unit root", "regime shift")),
    ("monotonicity",    ("monotonic",)),
    ("temporal",        ("spike in", "jump in", "discontinu", "flatline", "step change",
                         "sudden change", "abrupt")),
    ("signal_quality",  ("signal-to-noise", "snr", "smoothness", "roughness")),
]


def _resolve_family(text: str, category: str) -> List[str]:
    """All plausible family labels for a finding, from its category and prose."""
    fams: List[str] = []
    if category:
        fams.append(category)
    low = (text or "").lower()
    for fam, words in FAMILY_KEYWORDS:
        if any(w in low for w in words):
            fams.append(fam)
    return fams


# Findings that must never be suppressed, whatever the profile says. A NaN is a
# NaN whether the dataset is a sweep or a time series, and suppressing solver
# divergence to make a report look clean is the failure mode that ends trust.
NEVER_SUPPRESS = (
    "nan", "inf", "non-finite", "divergence", "outside", "bounds",
    "physically impossible", "negative", "conservation", "gas constant",
    "unit error", "exceeds", "violates",
)


def apply_mask(checks: list, exclusions: list, profile: DatasetProfile,
               known_columns: List[str]) -> Tuple[list, list, List[dict]]:
    """
    Drop checks and exclusions the profile has shown to be physically meaningless
    for this dataset shape.

    Returns (kept_checks, kept_exclusions, suppression_log). The log is surfaced
    in the report so every suppression is visible and attributable — a validator
    that hides what it chose not to run cannot be audited.
    """
    mask = profile.mask
    if not mask.suppressions:
        return checks, exclusions, []

    log: Dict[str, dict] = {}

    def _suppressed(text: str, category: str) -> Optional[Suppression]:
        low = (text or "").lower()
        if any(w in low for w in NEVER_SUPPRESS):
            return None
        fams = _resolve_family(text, category)
        if not fams:
            return None
        cols = _columns_mentioned(text, known_columns)
        for s in mask.suppressions:
            if s.check_family not in fams:
                continue
            if not s.columns:              # dataset-wide suppression
                return s
            if any(c in s.columns for c in cols):
                return s
        return None

    kept_checks = []
    for c in checks:
        name = getattr(c, "name", "") or ""
        cat = getattr(c, "category", "") or ""
        hit = _suppressed(f"{name} {getattr(c, 'detail', '')}", cat)
        # Only suppress findings. A passing check is harmless and keeps the
        # "checks run" count honest.
        if hit and getattr(getattr(c, "status", None), "value", "") != "passed":
            e = log.setdefault(hit.check_family, {
                "check_family": hit.check_family, "reason": hit.reason,
                "source": hit.source, "checks_suppressed": 0, "exclusions_suppressed": 0,
            })
            e["checks_suppressed"] += 1
            continue
        kept_checks.append(c)

    # True duplicates found by exact matching are re-inserted as exclusions so
    # suppressing cosine similarity never loses a real finding.
    true_dupe_rows = {i for g in profile.exact_duplicate_groups for i in g[1:]}

    kept_excl = []
    for x in exclusions:
        reason = getattr(x, "reason", "") or ""
        hit = _suppressed(reason, "")
        if hit and getattr(x, "trial_index", -1) not in true_dupe_rows:
            e = log.setdefault(hit.check_family, {
                "check_family": hit.check_family, "reason": hit.reason,
                "source": hit.source, "checks_suppressed": 0, "exclusions_suppressed": 0,
            })
            e["exclusions_suppressed"] += 1
            continue
        kept_excl.append(x)

    return kept_checks, kept_excl, list(log.values())
