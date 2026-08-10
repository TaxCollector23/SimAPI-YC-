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
    # Column -> Fraction exponent for the group value this law tests. Populated
    # for anchored_constant and pi_constant so downstream layers (e.g. temporal
    # drift) can recompute the continuous per-row value without re-deriving
    # the group from scratch. None for bimodal_split (the split itself is the
    # finding; there is no single expected value to residualise against).
    exponents: dict[str, Fraction] | None = None
    # Per-row shared-factor cluster info, keyed by row id. Populated when >=3
    # violated rows all deviate from the law by the same factor (within
    # SHARED_FACTOR_REL_TOLERANCE) -- a strong signal that a subset was
    # recorded in the wrong unit rather than being scattered bad rows. Each
    # entry: {"cluster_size", "cluster_factor", "named" (str | None)}.
    row_clusters: dict[int, dict] = field(default_factory=dict)


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


SHARED_FACTOR_MIN_ROWS = 3         # need at least this many rows sharing a factor before naming it
SHARED_FACTOR_REL_TOLERANCE = 0.05 # rows within 5% of a common factor count as sharing it


def _shared_factor_clusters(violated_rows: dict[int, float]) -> dict[int, dict]:
    """Group violated rows by shared factor. When a subset was exported in
    the wrong unit (e.g. pressure in kPa written into a Pa column), every
    affected row deviates from the law by the same factor -- reporting each
    as an isolated violation buries the diagnostic. Where >=3 rows share a
    factor within tolerance, tag them with a cluster note and, if the factor
    matches one of the known SPLIT_FACTORS, name it. Returns a per-row dict
    with `cluster_size`, `cluster_factor`, and (when recognised) `named`."""
    from .dimensions import SPLIT_FACTORS

    if len(violated_rows) < SHARED_FACTOR_MIN_ROWS:
        return {}
    items = [(rid, float(f)) for rid, f in violated_rows.items()
             if np.isfinite(f) and f > 0]
    if len(items) < SHARED_FACTOR_MIN_ROWS:
        return {}
    # Cluster in log space so 1000x and 1/1000 collapse to the same |log|
    # magnitude when we then check both signs -- a corrupted subset can be
    # off either direction, and we still want to name the ratio.
    log_factors = np.array([np.log10(abs(f)) for _, f in items])
    order = np.argsort(log_factors)
    sorted_logs = log_factors[order]
    sorted_ids = [items[i][0] for i in order]
    sorted_raw = [items[i][1] for i in order]

    clusters: list[list[int]] = []  # list of position runs (into sorted_*)
    run = [0]
    tol_log = np.log10(1.0 + SHARED_FACTOR_REL_TOLERANCE)
    for i in range(1, len(sorted_logs)):
        if sorted_logs[i] - sorted_logs[i - 1] <= tol_log:
            run.append(i)
        else:
            clusters.append(run)
            run = [i]
    clusters.append(run)

    out: dict[int, dict] = {}
    for run in clusters:
        if len(run) < SHARED_FACTOR_MIN_ROWS:
            continue
        cluster_factors = [sorted_raw[i] for i in run]
        median_factor = float(np.median(cluster_factors))
        named = None
        for f, name in SPLIT_FACTORS.items():
            for candidate in (median_factor, 1.0 / median_factor):
                if abs(candidate / f - 1.0) < SHARED_FACTOR_REL_TOLERANCE:
                    named = name
                    break
            if named:
                break
        for i in run:
            out[sorted_ids[i]] = {
                "cluster_size": len(run),
                "cluster_factor": median_factor,
                "named": named,
            }
    return out


def _cluster_note_suffix(row_clusters: dict[int, dict]) -> str:
    """One-line diagnostic summary of shared-factor clusters, appended to a
    law's `note`. Reports each cluster once (not per-row) and names the unit
    factor when known -- "8 rows share factor 1e-3 (kilo/1)" tells the user
    "one subset was written in the wrong unit" in a way N isolated
    violations cannot."""
    if not row_clusters:
        return ""
    seen: list[tuple[float, str | None, int]] = []
    for info in row_clusters.values():
        f = round(float(info["cluster_factor"]), 6)
        matched = False
        for i, (ef, _, _) in enumerate(seen):
            if ef == f:
                seen[i] = (ef, seen[i][1], seen[i][2] + 1)
                matched = True
                break
        if not matched:
            seen.append((f, info.get("named"), 1))
    parts = []
    for factor, named, count in seen:
        label = named or f"{factor:.4g}x"
        parts.append(f"{count} rows share factor {label}")
    return "; " + "; ".join(parts)


SYSTEMATIC_DEVIATION_MAX_CV = 0.03  # how tight the data's own scatter must be to call it "uniform"
SYSTEMATIC_DEVIATION_MIN_DEV = 0.03  # how far from the true constant before it's worth a note
SYSTEMATIC_DEVIATION_MAX_DEV = 0.50  # beyond this it's not "a nearby but wrong value", just
                                     # coincidental dimensional overlap between unrelated quantities


def layer3_anchored_constants(
    data: pd.DataFrame, units: UnitsResolution, columns: list[str],
) -> list[LawFinding]:
    """For each physical constant, search column subsets whose dimensions
    match it, and accept if >=ANCHOR_MIN_COVERAGE of rows sit on the value
    -- the median is NOT trusted, because past ~50% corruption the median
    IS the corruption. A constant does not move with the data; where one
    applies, it defines truth regardless of what the majority looks like.

    Also returns 'systematic_anchor_deviation' findings for the case the
    coverage requirement structurally cannot catch: a uniform bias across
    effectively ALL rows leaves zero rows within tolerance of the true
    constant, so the >=10%-coverage requirement is never met and the anchor
    never activates at all (found via adversarial testing -- a 5% uniform
    pressure bias across 100% of rows produced zero findings without this).
    Computed from the SAME per-subset `vals` array as the coverage check,
    not a second combinatorial search -- this was originally a duplicate
    full pass and cost 2x the runtime for no reason.
    """
    findings: list[LawFinding] = []
    seen: set[str] = set()

    for size in (2, 3, 4):
        for subset in itertools.combinations(columns, size):
            D: Matrix = [[units.columns[c].dimension[axis] for c in subset] for axis in range(7)]
            best_deviation: LawFinding | None = None  # closest-matching constant for this subset,
                                                        # when no constant achieves real anchor coverage
            subset_has_real_anchor = False
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
                if finding.kind == "anchored_constant":
                    subset_has_real_anchor = True
                    key = finding.label + f"~{const.name}~{finding.kind}"
                    if key in seen:
                        continue
                    seen.add(key)
                    findings.append(finding)
                else:
                    if len(exponents) < 3:
                        continue  # 2-column ratios are too prone to spurious near-misses
                                  # against unrelated same-dimension constants (e.g. sqrt(P/rho)
                                  # sits close to the speed of sound purely because it's missing
                                  # a sqrt(gamma) factor -- a real physics detail, not corruption)
                    # Several constants can share the same dimension (e.g.
                    # R_air, c_p_air, c_v_air are all "specific heat"-shaped)
                    # -- only the single closest match is informative; the
                    # others are coincidental dimensional overlap, not a
                    # meaningful "your data implies X" statement.
                    rel = abs(finding.observed_median - finding.expected_value) / abs(finding.expected_value)
                    if best_deviation is None or rel < abs(
                        best_deviation.observed_median - best_deviation.expected_value
                    ) / abs(best_deviation.expected_value):
                        best_deviation = finding
            # If ANY constant genuinely anchored this subset, the subset IS
            # explained -- a different, dimensionally-coincidental constant
            # "also" not matching is noise, not a finding.
            if best_deviation is not None and not subset_has_real_anchor:
                key = best_deviation.label + f"~systematic_anchor_deviation~{tuple(sorted(subset))}"
                if key not in seen:
                    seen.add(key)
                    findings.append(best_deviation)
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

    label = "·".join(c if e == 1 else f"{c}^{e}" for c, e in exponents.items())
    rel_dev = np.abs(vals - const.value) / abs(const.value)
    on_anchor = rel_dev <= ANCHOR_RELATIVE_TOLERANCE
    coverage = float(on_anchor.mean())

    if coverage >= ANCHOR_MIN_COVERAGE:
        violated = {}
        positions = np.where(~on_anchor)[0]
        for p in positions:
            factor = float(vals[p] / const.value)
            violated[int(sub.index[p])] = factor
        row_clusters = _shared_factor_clusters(violated)
        note = f"{coverage*100:.0f}% of rows sit on {const.name}={const.value:g} {const.description}"
        if row_clusters:
            note += _cluster_note_suffix(row_clusters)
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
            note=note,
            exponents=dict(exponents),
            row_clusters=row_clusters,
        )

    # No row sits close enough to the true constant for the anchor to
    # activate -- but if the data is nonetheless TIGHTLY self-consistent
    # (not noisy) at a value meaningfully different from the constant, that
    # uniformity is itself worth surfacing. Lower confidence than a true
    # anchor violation: this could be a legitimate domain difference
    # (different gas/material/condition), not necessarily an error.
    median = float(np.median(vals))
    mad = float(np.median(np.abs(vals - median)))
    cv = (mad * 1.4826) / abs(median) if median != 0 else float("inf")
    if cv > SYSTEMATIC_DEVIATION_MAX_CV:
        return None  # not tightly self-consistent -- ordinary scatter/noise, nothing to say
    global_rel_dev = abs(median - const.value) / abs(const.value)
    if global_rel_dev < SYSTEMATIC_DEVIATION_MIN_DEV:
        return None  # within normal measurement tolerance of the true constant
    if global_rel_dev > SYSTEMATIC_DEVIATION_MAX_DEV:
        return None  # not "a nearby but wrong value" -- just coincidental dimensional overlap

    return LawFinding(
        kind="systematic_anchor_deviation",
        label=f"{label} = {const.name} ({const.value:g})",
        columns=tuple(cols),
        expected_value=const.value,
        observed_median=median,
        scale=abs(median) * SYSTEMATIC_DEVIATION_MAX_CV,
        violated_rows={int(i): float(v / const.value) for i, v in zip(sub.index, vals)},
        coverage=1.0,
        weight=0.4,  # lower confidence than a true anchor: could be a legitimate difference
        note=(f"~100% of rows are tightly self-consistent (CV={cv:.4f}) at "
              f"{median:.6g}, {global_rel_dev*100:.1f}% away from {const.name}={const.value:g} "
              f"{const.description}. No row sits close enough to the true constant for the anchor "
              f"to activate -- this may be a genuine domain difference (different gas/material/"
              f"condition) or a systematic calibration/unit error."),
        exponents=dict(exponents),
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

        row_clusters = _shared_factor_clusters(violated)
        note = "exact (zero scatter)" if mad == 0 else f"rel_mad={rel_mad:.2e}"
        if row_clusters:
            note += _cluster_note_suffix(row_clusters)
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
            note=note,
            exponents=dict(pg.exponents),
            row_clusters=row_clusters,
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


# ── Temporal drift (gauge drift on an established law, when a time column ──
# is present). Not a distinct spec layer number -- it's the same anchored/
# constant-law machinery from Layers 2-3, tested against time instead of
# just against the population median. A random outlier and a drifting gauge
# both violate the law, but only drift is *correlated with time*; that's
# the distinguishing signal a plain violation count can't see.
DRIFT_MIN_ROWS = 20
DRIFT_CORR_THRESHOLD = 0.5
# Materiality floor for a drift finding's end-of-run residual. Half the per-row
# violation threshold: with continuous per-row residuals reconstructed from a
# law's exponents, a sustained, time-correlated bias below the row-violation
# bar is still a real gauge fault (and one the row-level layers cannot see on
# their own). Below this floor the correlation may still be genuine but is
# indistinguishable from ambient noise, so stay silent.
DRIFT_TAIL_MATERIAL = ROW_VIOLATION_REL / 2


def find_time_column(data: pd.DataFrame) -> str | None:
    candidates = [c for c in data.columns if "time" in c.lower()]
    for c in candidates:
        s = pd.to_numeric(data[c], errors="coerce")
        if s.notna().sum() >= DRIFT_MIN_ROWS and s.is_monotonic_increasing:
            return c
    return candidates[0] if candidates else None


def detect_temporal_drift(data: pd.DataFrame, laws: list[LawFinding], time_col: str) -> list[LawFinding]:
    """For each established law (anchor or Pi-constant), test whether the
    residual (value vs expected) is correlated with time. A real gauge drift
    shows a strong, monotonic time-correlation; an isolated corrupted row or
    ordinary noise does not."""
    if time_col not in data.columns:
        return []
    t = pd.to_numeric(data[time_col], errors="coerce")
    if t.notna().sum() < DRIFT_MIN_ROWS:
        return []

    findings: list[LawFinding] = []
    for law in laws:
        if law.kind not in ("anchored_constant", "pi_constant") or law.expected_value is None:
            continue
        cols = [c for c in law.columns if c in data.columns]
        if not cols:
            continue
        sub = data[cols].apply(pd.to_numeric, errors="coerce")
        valid = sub.dropna().index.intersection(t.dropna().index)
        if len(valid) < DRIFT_MIN_ROWS:
            continue

        # Prefer a continuous per-row residual computed directly from the law's
        # stored exponents -- a slow drift that never crosses the row-violation
        # threshold produces zero violated_rows but a strong time-correlation in
        # the raw residual, and the earlier factor-from-violations reconstruction
        # was blind to it.
        residual: np.ndarray | None = None
        if law.exponents:
            vals = np.ones(len(valid), dtype=float)
            skip = False
            for c, e_frac in law.exponents.items():
                if c not in sub.columns:
                    skip = True
                    break
                e = float(e_frac)
                col_vals = sub.loc[valid, c].to_numpy(dtype=float)
                if e != int(e) and (col_vals < 0).any():
                    skip = True
                    break
                with np.errstate(all="ignore"):
                    vals = vals * np.power(col_vals, e)
            if not skip and np.all(np.isfinite(vals)) and law.expected_value != 0:
                residual = vals / law.expected_value - 1.0
        if residual is None:
            factor = pd.Series(1.0, index=valid)
            for rid, f in law.violated_rows.items():
                if rid in factor.index:
                    factor.loc[rid] = f
            residual = (factor - 1.0).to_numpy()

        tv = t.loc[valid].to_numpy()
        if np.std(residual) < 1e-12 or np.std(tv) < 1e-12:
            continue
        corr = float(np.corrcoef(tv, residual)[0, 1])
        if not np.isfinite(corr) or abs(corr) < DRIFT_CORR_THRESHOLD:
            continue
        # Require the drift to actually be material by the end of the run,
        # not just a statistically-detectable but tiny time-correlation.
        order = np.argsort(tv)
        tail = residual[order][-max(5, len(order)//10):]
        if np.median(np.abs(tail)) < DRIFT_TAIL_MATERIAL:
            continue

        # Attribute drift to rows whose continuous residual actually exceeds
        # the row-violation threshold, in addition to any hard-violated rows
        # from the base law -- with the continuous reconstruction this now
        # picks up rows the base law itself did not flag. When the drift
        # never crosses the per-row bar but the time-correlation and tail-
        # materiality guards did fire, fall back to the tail decile of the
        # time series (the rows that carry the drift's cumulative signature),
        # so the finding still attaches to concrete rows for arbitration.
        drift_rows: dict[int, float] = dict(law.violated_rows)
        idx_list = list(valid)
        for i, r in enumerate(residual):
            if abs(r) >= ROW_VIOLATION_REL:
                rid = int(idx_list[i])
                drift_rows.setdefault(rid, float(1.0 + r))
        if not drift_rows:
            tail_positions = order[-max(5, len(order)//10):]
            for i in tail_positions:
                rid = int(idx_list[i])
                drift_rows.setdefault(rid, float(1.0 + residual[i]))
        findings.append(LawFinding(
            kind="temporal_drift",
            label=f"{law.label} drifts with {time_col} (corr={corr:.2f})",
            columns=law.columns,
            expected_value=law.expected_value,
            observed_median=law.observed_median,
            scale=law.scale,
            violated_rows=drift_rows,
            coverage=law.coverage,
            weight=min(1.0, law.weight + 0.1),  # time-correlated is stronger evidence than isolated
            note=f"gauge/sensor drift: residual vs {time_col} correlation={corr:.2f} "
                 f"(law: {law.note})",
            exponents=dict(law.exponents) if law.exponents else None,
        ))
    return findings
