"""
Layer 2 -- constant Pi groups.
Layer 3 -- anchored constant groups (critical: the sole defence against
majority corruption inverting the engine's notion of "truth").
Layer 4 -- bimodal split detection (majority defence when no anchor applies).
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from fractions import Fraction

import numpy as np
import pandas as pd

from .dimensions import CONSTANTS, PhysicalConstant
from .linalg import Matrix, solve_particular
from .pi_basis import MAX_ABS_EXPONENT, PiGroup, _is_half_integer  # noqa: F401 (reuse)
from .units_resolver import UnitsResolution

# Relative deviation beyond which a row is flagged against an exact/near-exact
# law. Real corruption (unit swaps, scale bugs, sensor faults) produces
# deviations of tens of percent or more; genuine measurement/solver noise on
# a strong physical law is well under this.
ROW_VIOLATION_REL = 0.02
ROBUST_Z_THRESHOLD = 6.0

LAW_RELATIVE_TOLERANCE = 0.05      # Layer 2: max relative MAD to call a Pi group "constant"
ANCHOR_RELATIVE_TOLERANCE = 0.02   # Layer 3: max relative deviation to say a row "sits on" a constant
ANCHOR_MIN_COVERAGE = 0.10         # Layer 3: accept if >=10% of rows sit on the constant


@dataclass
class LawFinding:
    kind: str                       # "pi_constant" | "anchored_constant" | "bimodal_split"
    label: str
    columns: tuple[str, ...]
    expected_value: float | None
    observed_median: float
    scale: float                    # robust scatter used for row z-scores
    violated_rows: dict[int, float] = field(default_factory=dict)  # row -> factor (observed/expected)
    coverage: float = 1.0           # fraction of rows the law/anchor applies to
    weight: float = 1.0             # arbitration weight: tighter law -> higher
    note: str = ""


def _robust_scale(values: np.ndarray, median: float) -> float:
    mad = float(np.median(np.abs(values - median)))
    if mad > 0:
        return mad * 1.4826
    return max(abs(median), 1e-30) * 1e-9


def _weight_for(mad_over_median: float) -> float:
    # cv~1e-9 (an exact law) -> weight ~1.0; cv~0.05 (borderline) -> weight ~0.2.
    cv = max(mad_over_median, 1e-9)
    return float(np.clip(1.0 / (1.0 + 20.0 * cv), 0.05, 1.0))


def _row_index(data: pd.DataFrame, positions: np.ndarray) -> list[int]:
    return [int(data.index[p]) for p in positions]


def layer3_anchored_constants(
    data: pd.DataFrame, units: UnitsResolution, columns: list[str],
) -> list[LawFinding]:
    """For each physical constant, search column subsets whose dimensions
    match it, and accept if >=ANCHOR_MIN_COVERAGE of rows sit on the value
    -- the median is NOT trusted, because past ~50% corruption the median
    IS the corruption. A constant does not move with the data; where one
    applies, it defines truth regardless of what the majority looks like."""
    findings: list[LawFinding] = []
    seen: set[str] = set()

    for size in (2, 3, 4):
        for subset in itertools.combinations(columns, size):
            D: Matrix = [[units.columns[c].dimension[axis] for c in subset] for axis in range(7)]
            for const in CONSTANTS:
                target = list(const.dimension)
                sol = solve_particular(D, target)
                if sol is None:
                    continue
                if any(abs(e) > MAX_ABS_EXPONENT for e in sol):
                    continue
                if not all(_is_half_integer(e) for e in sol):
                    continue
                exponents = {c: e for c, e in zip(subset, sol, strict=True) if e != 0}
                # Require a genuine multi-column RELATIONSHIP, not a
                # single-column magnitude coincidence (e.g. a pressure
                # column that happens to sit near 1 atm isn't evidence of
                # anything -- P/(rho*T)=R_air is, because it encodes an
                # actual relationship between three independent columns).
                if len(exponents) < 2:
                    continue
                finding = _evaluate_anchor(data, exponents, const)
                if finding is None:
                    continue
                key = finding.label + f"~{const.name}"
                if key in seen:
                    continue
                seen.add(key)
                findings.append(finding)
    return findings


def _evaluate_anchor(data: pd.DataFrame, exponents: dict[str, Fraction],
                      const: PhysicalConstant) -> LawFinding | None:
    cols = list(exponents)
    sub = data[cols].apply(pd.to_numeric, errors="coerce").dropna()
    if len(sub) < 5:
        return None
    try:
        vals = np.ones(len(sub), dtype=float)
        for c in cols:
            e = float(exponents[c])
            col_vals = sub[c].to_numpy(dtype=float)
            if e != int(e) and (col_vals < 0).any():
                return None
            with np.errstate(all="ignore"):
                vals = vals * np.power(col_vals, e)
    except Exception:
        return None
    if not np.all(np.isfinite(vals)):
        return None

    rel_dev = np.abs(vals - const.value) / abs(const.value)
    on_anchor = rel_dev <= ANCHOR_RELATIVE_TOLERANCE
    coverage = float(on_anchor.mean())
    if coverage < ANCHOR_MIN_COVERAGE:
        return None

    label = "·".join(c if e == 1 else f"{c}^{e}" for c, e in exponents.items())
    violated = {}
    positions = np.where(~on_anchor)[0]
    for p in positions:
        factor = float(vals[p] / const.value)
        violated[int(sub.index[p])] = factor

    return LawFinding(
        kind="anchored_constant",
        label=f"{label} = {const.name} ({const.value:g})",
        columns=tuple(cols),
        expected_value=const.value,
        observed_median=float(np.median(vals)),
        scale=abs(const.value) * ANCHOR_RELATIVE_TOLERANCE,
        violated_rows=violated,
        coverage=coverage,
        weight=1.0,  # a physical constant anchor is maximal-confidence evidence
        note=f"{coverage*100:.0f}% of rows sit on {const.name}={const.value:g} {const.description}",
    )


def layer2_constant_pi_groups(
    data: pd.DataFrame, groups: list[PiGroup], vetoed_column_sets: list[set[str]],
) -> list[LawFinding]:
    """A Pi group whose value is constant across rows is a law. An
    exactly-satisfied law (zero MAD) is the STRONGEST evidence, not
    degenerate evidence -- do not discard it, and do not scale its
    tolerance to a scatter that doesn't exist."""
    findings: list[LawFinding] = []
    for pg in groups:
        cols = set(pg.columns)
        # Layer 3 anchors take precedence over overlapping Pi groups: an
        # anchor is truth-by-constant, a bare Pi-group median can itself be
        # the corruption under majority contamination.
        if any(len(cols & vc) >= 2 for vc in vetoed_column_sets):
            continue
        # Require at least one constituent column to actually vary in the
        # raw data -- a group built only from constant columns can't be
        # violated and carries no information.
        varies = False
        for c in pg.columns:
            s = pd.to_numeric(data[c], errors="coerce").dropna()
            if len(s) > 1 and float(s.std()) > 1e-12 * (abs(float(s.mean())) + 1e-12):
                varies = True
                break
        if not varies:
            continue

        values = pg.values
        if len(values) < 5 or not np.all(np.isfinite(values)):
            continue
        # A group that's secretly bimodal must NOT be accepted here as a
        # simple constant law: past 50% corruption the tight majority
        # cluster is the corrupted one, and a plain median/MAD check would
        # silently invert (flag the clean minority, pass the corrupted
        # majority) -- exactly the failure mode Layer 3 guards against for
        # anchors, unguarded here without this check. Defer to Layer 4.
        if detect_split(values) is not None:
            continue
        median = float(np.median(values))
        if median == 0:
            continue
        mad = float(np.median(np.abs(values - median)))
        rel_mad = mad / abs(median)
        if rel_mad > LAW_RELATIVE_TOLERANCE:
            continue  # not a law -- real scatter, not corruption evidence

        scale = _robust_scale(values, median)
        z = np.abs(values - median) / scale
        bad = z > ROBUST_Z_THRESHOLD
        violated = {}
        for p in np.where(bad)[0]:
            violated[int(data.index[p]) if p < len(data.index) else p] = float(values[p] / median)

        findings.append(LawFinding(
            kind="pi_constant",
            label=f"{pg.label()} = const",
            columns=pg.columns,
            expected_value=median,
            observed_median=median,
            scale=scale,
            violated_rows=violated,
            coverage=1.0,
            weight=_weight_for(rel_mad),
            note="exact (zero scatter)" if mad == 0 else f"rel_mad={rel_mad:.2e}",
        ))
    return findings


def detect_split(values: np.ndarray) -> dict | None:
    """Core bimodal-split test, shared by Layer 2 (which must NOT accept a
    secretly-bimodal group as a simple constant law -- doing so is the same
    majority-inversion failure Layer 3 guards against, just unguarded) and
    Layer 4 (which reports the split as a finding)."""
    if len(values) < 10 or not np.all(np.isfinite(values)) or np.any(values <= 0):
        return None
    logv = np.log(values)
    order = np.argsort(logv)
    sorted_log = logv[order]
    gaps = np.diff(sorted_log)
    if len(gaps) == 0:
        return None
    gap_idx = int(np.argmax(gaps))
    split_point = gap_idx + 1
    low_frac = split_point / len(values)
    # Both clusters must be substantial -- an isolated outlier is not a split.
    if low_frac < 0.05 or low_frac > 0.95:
        return None
    low_vals = np.exp(sorted_log[:split_point])
    high_vals = np.exp(sorted_log[split_point:])
    low_med, high_med = float(np.median(low_vals)), float(np.median(high_vals))
    low_mad = float(np.median(np.abs(low_vals - low_med))) / max(abs(low_med), 1e-30)
    high_mad = float(np.median(np.abs(high_vals - high_med))) / max(abs(high_med), 1e-30)
    if low_mad > 0.02 or high_mad > 0.02:
        return None  # a genuine spread, not a clean split -- stay silent
    return {
        "order": order, "logv": logv, "split_point": split_point, "low_frac": low_frac,
        "low_med": low_med, "high_med": high_med,
    }


def layer4_bimodal_split(data: pd.DataFrame, groups: list[PiGroup]) -> list[LawFinding]:
    """When no anchor applies, a law that should hold exactly but instead
    splits into two internally-tight clusters separated by a recognisable
    unit factor is decisive evidence of mixed conventions -- report the
    split and name the factor; don't guess which side is correct."""
    from .dimensions import SPLIT_FACTORS

    findings: list[LawFinding] = []
    for pg in groups:
        split = detect_split(pg.values)
        if split is None:
            continue
        order, logv = split["order"], split["logv"]
        split_point, low_frac = split["split_point"], split["low_frac"]
        low_med, high_med = split["low_med"], split["high_med"]

        ratio = high_med / low_med if low_med != 0 else float("inf")
        factor_name = None
        # The group itself may be a power/root form (e.g. sqrt(tau*omega/P)),
        # in which case the observed cluster ratio is that same power of the
        # true unit-conversion factor -- check ratio^2 and ratio^0.5 too, not
        # just the raw ratio, before giving up on naming it.
        for power, power_label in ((1, ""), (2, "^2"), (0.5, "^0.5")):
            test_ratio = ratio ** power
            for f, name in SPLIT_FACTORS.items():
                if abs(test_ratio / f - 1.0) < 0.02 or abs((1.0 / test_ratio) / f - 1.0) < 0.02:
                    factor_name = f"{name} (observed as (ratio){power_label})" if power != 1 else name
                    break
            if factor_name:
                break

        low_idx = order[:split_point]
        rows_in_minority = low_idx if low_frac <= 0.5 else order[split_point:]
        violated = {int(data.index[p]): float(np.exp(logv[p]) / (high_med if low_frac <= 0.5 else low_med))
                    for p in rows_in_minority}

        findings.append(LawFinding(
            kind="bimodal_split",
            label=f"{pg.label()} splits {low_frac*100:.0f}%/{(1-low_frac)*100:.0f}%",
            columns=pg.columns,
            expected_value=None,
            observed_median=float(np.median(pg.values)),
            scale=max(low_med, 1e-30) * 0.02,
            violated_rows=violated,
            coverage=1.0,
            weight=0.6,
            note=(f"factor {factor_name or f'{ratio:.4g}x (unrecognised)'}; "
                  f"clusters at {low_med:.4g} and {high_med:.4g}"),
        ))
    return findings
