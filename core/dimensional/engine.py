"""
Dimensional-analysis validation engine -- orchestrator.

Replaces a hand-written-check architecture (that does not converge: every
check encodes an assumption, real data violates it legitimately, a
suppression gets added, the suppression needs its own exceptions) with
~25 hand-specified rules and domain coverage coming from a units
dictionary. Adding a 16th domain requires zero new code: it only needs
column-name patterns and, optionally, new physical constants -- both data,
not logic.

Layers:
  0 units_resolver   -- column name -> SI dimension, confidence, unit conversion
  1 pi_basis         -- dimensionless group discovery (exact rational null space)
  2 pi_laws (const)  -- Pi groups constant across rows are laws
  3 pi_laws (anchor) -- Pi groups matching a KNOWN constant; majority-corruption defence
  4 pi_laws (split)  -- bimodal split detection when no anchor applies
  5 response_surface -- Pi-space k-NN residuals for non-constant physics
  6 rules (semantic) -- ~30 quantity kinds with definitional bounds
  7 declared_conditions -- user-declared domain/conditions as testable assertions
  8 rules (structural) -- non-finite values, exact duplicates (relative equality)

Arbitration is weighted voting (not vote counting), with root-cause
clustering and counterfactual repair. Output is three classes -- impossible,
inconsistent, unsuitable-for-training -- not one exclusion list.

KNOWN-IMPOSSIBLE (documented deliberately; not attempted)
---------------------------------------------------------
Self-consistent-but-wrong data is outside what this or any output-only
validator can detect.

A simulation run with the wrong turbulence model produces output that is
dimensionally perfect, smooth, satisfies every anchor and every discovered
Pi law, sits inside every semantic bound, and is simply incorrect. Every
layer above tests the data against ITSELF (or against physical constants
that the wrong model also respects), so there is no signal in the output
to find. Detecting it requires comparison against experiment or a trusted
reference run -- i.e. information that is not in the dataset -- and is
addressed by the roadmap in which the platform runs the simulation itself.

This boundary is stated in the report (see `KNOWN_IMPOSSIBLE`, surfaced by
`ValidationReport.summary()`) rather than left implicit, because a
validator that quietly implies it caught everything is not credible about
what it did catch. A clean report from this engine means "consistent with
itself, with physical constants, and with declared conditions" -- it does
not mean "physically correct".
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import pi_laws
from .declared_conditions import check_declared_conditions
from .pi_basis import PiGroup, find_pi_groups, select_columns
from .response_surface import SurfaceFinding, find_surface_anomalies
from .rules import SemanticViolation, StructuralFinding, check_semantic_bounds, check_structural
from .training_suitability import SuitabilityFinding, assess_training_suitability
from .units_resolver import UnitsResolution, resolve_units

OUTPUT_CLASSES = ("impossible", "inconsistent", "unsuitable_for_training")

# Shipped in every report. See the module docstring: stating the boundary
# explicitly is what makes the rest of the reporting credible.
KNOWN_IMPOSSIBLE = (
    "Self-consistent-but-wrong data is not detectable from output alone. A run "
    "with (for example) the wrong turbulence model yields dimensionally perfect, "
    "smooth, anchor-satisfying output that is simply incorrect. A clean report "
    "here means the data is consistent with itself, with physical constants, and "
    "with the declared conditions -- it does not mean the physics is right. "
    "Establishing that requires comparison against experiment or a trusted "
    "reference run."
)


@dataclass
class RowFinding:
    row_id: int
    output_class: str
    reason: str
    layer: str
    weight: float
    factor: float | None = None          # observed/expected, if applicable
    counterfactual: str | None = None     # e.g. "x1000 closes the residual from 99.9% to 0.00%"
    root_cause_group: int | None = None


@dataclass
class UnitsConflict:
    column: str
    llm_dimension: str
    discovered_dimension: str
    note: str


@dataclass
class ValidationReport:
    n_rows: int
    units: UnitsResolution
    pi_groups: list[PiGroup]
    laws: list[pi_laws.LawFinding]
    surface_findings: list[SurfaceFinding]
    semantic_violations: list[SemanticViolation]
    structural_findings: list[StructuralFinding]
    condition_assertions: list
    units_conflicts: list[UnitsConflict]
    row_findings: list[RowFinding]
    suitability: list[SuitabilityFinding] = field(default_factory=list)
    suppressions: list[str] = field(default_factory=list)

    @property
    def impossible_rows(self) -> set[int]:
        return {f.row_id for f in self.row_findings if f.output_class == "impossible"}

    @property
    def inconsistent_rows(self) -> set[int]:
        return {f.row_id for f in self.row_findings if f.output_class == "inconsistent"}

    @property
    def unsuitable_rows(self) -> set[int]:
        return {f.row_id for f in self.row_findings if f.output_class == "unsuitable_for_training"}

    def summary(self) -> dict:
        return {
            "n_rows": self.n_rows,
            "n_laws_discovered": len(self.laws),
            "n_anchored_constants": sum(1 for law in self.laws if law.kind == "anchored_constant"),
            "impossible": sorted(self.impossible_rows),
            "inconsistent": sorted(self.inconsistent_rows),
            "unsuitable_for_training": sorted(self.unsuitable_rows),
            "units_conflicts": [c.__dict__ for c in self.units_conflicts],
            # Dataset-level, deliberately separate from the row lists above:
            # "your data never covers the high-AoA regime" is not a row defect.
            "training_suitability": [s.__dict__ for s in self.suitability],
            "suppressions": list(self.suppressions),
            "known_impossible": KNOWN_IMPOSSIBLE,
        }


def openrouter_llm_resolver(columns: list[str]) -> dict[str, dict]:
    """The real OpenRouter-backed Layer 0 fallback (core/dimensional/
    llm_units.py) for columns the dictionary can't classify. Not the
    default on `validate()` -- network calls should be opt-in, not
    automatic just because a key happens to be configured in the
    environment. Pass this explicitly:
    `validate(df, llm_resolver=openrouter_llm_resolver)`.
    Callers who want it are api/server.py's /v1/validate/dimensional
    endpoint; the test suite deliberately does not, so it stays fast and
    network-independent (none of its columns need an LLM anyway)."""
    from .llm_units import llm_resolve_columns
    return llm_resolve_columns(columns)


def validate(
    data: pd.DataFrame,
    conditions: dict | None = None,
    llm_resolver: Callable[[list[str]], dict[str, dict]] | None = None,
    max_columns: int = 15,
    unit_overrides: dict[str, str] | None = None,
) -> ValidationReport:
    """`llm_resolver`, if provided, classifies columns the dictionary
    resolver couldn't (see core.dimensional.engine.openrouter_llm_resolver
    for the real OpenRouter-backed implementation). Defaults to None --
    dictionary-only, deterministic, no network dependency.

    `unit_overrides`, if provided, is ``{col: dimension_key}`` -- lets a
    caller correct a wrong dictionary/LLM mapping (e.g. "v" resolved as
    velocity but is actually volume) and re-run with the fix applied."""
    conditions = conditions or {}
    data = data.reset_index(drop=True)
    if data.columns.duplicated().any():
        # Defensive, not just ingestion's job: a DataFrame with duplicate
        # column names crashes pandas numeric operations throughout this
        # engine (`data[col]` returns a DataFrame, not a Series, for a
        # duplicated label). core.ingestion.DataIngester already avoids
        # creating these, but this engine is called directly too (tests,
        # notebooks, future integrations), so it protects itself rather
        # than trusting every caller to have deduplicated first.
        seen: dict[str, int] = {}
        new_cols = []
        for c in data.columns:
            if c in seen:
                seen[c] += 1
                new_cols.append(f"{c}_dup{seen[c]}")
            else:
                seen[c] = 0
                new_cols.append(c)
        data = data.copy()
        data.columns = new_cols
    n_rows = len(data)
    # Audit trail. The spec is explicit: "Every suppression must carry its
    # reason into the report. A validator that hides what it chose not to
    # run cannot be audited." Anything this engine declines to analyse --
    # a column dropped for unresolvable units, a layer skipped for want of
    # rows -- records WHY here, so a reader can tell "clean" apart from
    # "never actually looked at".
    suppressions: list[str] = []

    # ── Layer 0 ──────────────────────────────────────────────────────────
    numeric_cols = [c for c in data.columns if pd.api.types.is_numeric_dtype(data[c])
                     or pd.to_numeric(data[c], errors="coerce").notna().mean() > 0.8]
    non_numeric = [c for c in data.columns if c not in numeric_cols]
    if non_numeric:
        suppressions.append(
            f"Layer 1-3/5 skipped for {len(non_numeric)} non-numeric column(s) "
            f"({', '.join(map(str, non_numeric[:6]))}"
            f"{', ...' if len(non_numeric) > 6 else ''}): IDs, flags and categoricals "
            f"carry no dimensions. Structural checks still apply.")
    units = resolve_units(numeric_cols, llm_resolver=llm_resolver, unit_overrides=unit_overrides)
    unresolved = [c for c in numeric_cols if not units.columns[c].usable]
    if unresolved:
        suppressions.append(
            f"Layer 1-3 skipped for {len(unresolved)} column(s) with unresolved or "
            f"low-confidence units ({', '.join(unresolved[:6])}"
            f"{', ...' if len(unresolved) > 6 else ''}): dimensional analysis needs a "
            f"trusted dimension. These are still judged by Layer 5 (response surface).")
    si_data = _apply_si_conversion(data, units)

    # ── Layer 1 ──────────────────────────────────────────────────────────
    groups = find_pi_groups(si_data, units, max_columns=max_columns)
    usable_n = len(units.usable_columns())
    if usable_n > max_columns:
        suppressions.append(
            f"Layer 1 considered the {max_columns} highest-value of {usable_n} usable "
            f"columns (ranked by variance x units confidence): subset enumeration is "
            f"combinatorial and the spec caps it to hold the <10s budget at 80 columns.")

    # ── Layer 7 (assertions + synthetic anchor of last resort) ─────────────
    condition_assertions, synthetic_anchors = check_declared_conditions(si_data, conditions)

    # ── Layer 3 (must run before Layer 2 and veto it on overlap) ───────────
    # Uses the SAME prioritized/capped column selection as Layer 1, not the
    # columns that happened to end up in a *dimensionless* Layer-1 group --
    # a column like temperature can never appear in a dimensionless group by
    # itself (nothing else to cancel its Theta exponent against) but is
    # essential to an anchor like P/(rho*T)=R_air, whose target dimension is
    # NOT zero.
    all_candidate_columns = select_columns(si_data, units, cap=max_columns)
    anchors = pi_laws.layer3_anchored_constants(si_data, units, all_candidate_columns)
    anchors = anchors + synthetic_anchors
    vetoed_column_sets = [set(a.columns) for a in anchors]

    # ── Layer 2 (internally defers to Layer 4's split test before ─────────
    # accepting any group as a simple constant law) ────────────────────────
    const_laws = pi_laws.layer2_constant_pi_groups(si_data, groups, vetoed_column_sets)

    # ── Layer 4 (runs over all groups; Layer 2 already skipped anything
    # it detected as bimodal, so there's no double-reporting) ──────────────
    splits = pi_laws.layer4_bimodal_split(si_data, groups)

    laws: list[pi_laws.LawFinding] = anchors + const_laws + splits

    # ── Temporal drift: when a time column exists, real gauge/sensor drift
    # is distinguished from an isolated corrupted row by being CORRELATED
    # with time, not just present. Reuses the same anchored/constant laws
    # above rather than being a separate detection family.
    time_col = pi_laws.find_time_column(si_data)
    if time_col:
        drift_findings = pi_laws.detect_temporal_drift(si_data, laws, time_col)
        laws = laws + drift_findings

    # ── Layer 5 ──────────────────────────────────────────────────────────
    anchor_columns = {c for a in anchors for c in a.columns}
    surface_findings = find_surface_anomalies(si_data, units, anchor_columns=anchor_columns)

    # ── Layer 6 ──────────────────────────────────────────────────────────
    semantic_violations = check_semantic_bounds(data)

    # ── Layer 8 ──────────────────────────────────────────────────────────
    structural_findings = check_structural(si_data)

    # ── Training suitability: physically valid, harmful to learn from ─────
    # Mostly DATASET-level, not row-level -- a coverage gap is not a property
    # of any single row, so these do not become row exclusions.
    suitability = assess_training_suitability(si_data, list(units.usable_columns()))
    if len(si_data) < 20:
        suppressions.append(
            "Training-suitability analysis skipped: coverage, imbalance and "
            "leakage statistics are not meaningful below 20 rows.")

    # ── Units-conflict verification: "the LLM proposes, linear algebra
    # disposes". If an accepted anchor/law implies a dimension the resolver
    # didn't assign (or assigned with low confidence), record the conflict
    # rather than silently trusting either side. ─────────────────────────
    units_conflicts = _find_units_conflicts(units, anchors)

    row_findings = _arbitrate(
        n_rows=n_rows, laws=laws, surface_findings=surface_findings,
        semantic_violations=semantic_violations, structural_findings=structural_findings,
        si_data=si_data,
    )

    return ValidationReport(
        n_rows=n_rows, units=units, pi_groups=groups, laws=laws,
        surface_findings=surface_findings, semantic_violations=semantic_violations,
        structural_findings=structural_findings, condition_assertions=condition_assertions,
        units_conflicts=units_conflicts, row_findings=row_findings,
        suitability=suitability, suppressions=suppressions,
    )


def _apply_si_conversion(data: pd.DataFrame, units: UnitsResolution) -> pd.DataFrame:
    out = data.copy()
    for col, u in units.columns.items():
        if col not in out.columns or not u.usable:
            continue
        if u.si_scale == 1.0 and u.si_offset == 0.0:
            continue
        s = pd.to_numeric(out[col], errors="coerce")
        out[col] = s * u.si_scale + u.si_offset
    return out


def _find_units_conflicts(units: UnitsResolution, anchors: list[pi_laws.LawFinding]) -> list[UnitsConflict]:
    from .dimensions import dim_repr
    conflicts = []
    for a in anchors:
        for col in a.columns:
            u = units.columns.get(col)
            if u is None or not u.usable:
                continue
            if u.confidence < 0.65:
                conflicts.append(UnitsConflict(
                    column=col,
                    llm_dimension=dim_repr(u.dimension) if u.dimension else "unresolved",
                    discovered_dimension="(participates in a verified anchored law)",
                    note=f"low-confidence label ({u.confidence:.2f}) but column participates "
                         f"in a numerically verified law: {a.label}",
                ))
    return conflicts


def _counterfactual_repair(finding_columns: tuple[str, ...], row_id: int, factor: float,
                            si_data: pd.DataFrame, kind: str) -> str | None:
    """Given a suspect factor between observed and expected, identify which
    column is the likely culprit by checking which one is anomalous relative
    to the OTHER (unaffected) rows -- P=rhoRT can be balanced by scaling any
    of its three terms, so residual closure alone can't identify the culprit."""
    if abs(factor) < 1e-12:
        return None
    candidates = [factor, 1.0 / factor]
    best = None
    for col in finding_columns:
        if col not in si_data.columns or row_id not in si_data.index:
            continue
        series = pd.to_numeric(si_data[col], errors="coerce")
        others = series.drop(index=row_id, errors="ignore").dropna()
        this_val = series.get(row_id)
        if others.empty or this_val is None or not np.isfinite(this_val):
            continue
        med_others = float(others.median())
        mad_others = float(np.median(np.abs(others - med_others))) or abs(med_others) * 1e-6 or 1e-12
        for cand in candidates:
            corrected = this_val / cand
            z_before = abs(this_val - med_others) / mad_others
            z_after = abs(corrected - med_others) / mad_others
            if z_before > 3 and z_after < 1.0:
                closure = 1.0 - min(1.0, z_after / max(z_before, 1e-9))
                msg = f"scaling {col} by {1/cand:.4g} closes the {kind} residual (z {z_before:.1f}->{z_after:.1f})"
                if best is None or closure > best[0]:
                    best = (closure, msg)
    return best[1] if best else None


def _arbitrate(
    n_rows: int, laws: list[pi_laws.LawFinding], surface_findings: list[SurfaceFinding],
    semantic_violations: list[SemanticViolation], structural_findings: list[StructuralFinding],
    si_data: pd.DataFrame,
) -> list[RowFinding]:
    findings: list[RowFinding] = []

    # Impossible: never suppressible.
    for sv in semantic_violations:
        for rid in sv.row_ids:
            findings.append(RowFinding(row_id=rid, output_class="impossible",
                                        reason=sv.rule, layer="semantic_bounds", weight=1.0))
    for sf in structural_findings:
        if sf.kind == "non_finite":
            for rid in sf.row_ids:
                findings.append(RowFinding(row_id=rid, output_class="impossible",
                                            reason=sf.detail, layer="structural", weight=1.0))
        elif sf.kind in ("exact_duplicate", "near_duplicate"):
            # Physically valid, harmful to learn from -- unsuitable for
            # training, not "impossible" (the row isn't physically wrong).
            for rid in sf.row_ids:
                findings.append(RowFinding(row_id=rid, output_class="unsuitable_for_training",
                                            reason=sf.detail, layer="structural", weight=1.0))

    for law in laws:
        out_class = "impossible" if law.kind == "anchored_constant" else "inconsistent"
        # A systematic deviation applies to ~every row by construction
        # (coverage=1.0) -- counterfactual repair is a per-row "what
        # surgical fix explains this outlier" analysis, which is both
        # wasteful and the wrong question when the answer is "the whole
        # dataset needs the same rescaling", not a per-row diagnosis.
        skip_counterfactual = law.kind == "systematic_anchor_deviation"
        for rid, factor in law.violated_rows.items():
            cf = None if skip_counterfactual else _counterfactual_repair(
                law.columns, rid, factor, si_data, law.kind)
            findings.append(RowFinding(
                row_id=rid, output_class=out_class,
                reason=f"{law.label} violated ({factor:.4g}x expected); {law.note}",
                layer=law.kind, weight=law.weight, factor=factor, counterfactual=cf,
            ))

    for sf in surface_findings:
        for rid, z, md in zip(sf.row_ids, sf.residual_z, sf.material_deviation, strict=True):
            weight = float(np.clip(z / 20.0, 0.1, 0.6))  # response-surface evidence is weaker than an exact law
            findings.append(RowFinding(
                row_id=rid, output_class="inconsistent",
                reason=f"{sf.column} deviates from Pi-space response surface "
                       f"(z={z:.1f}, {md*100:.1f}% of P5-P95 range); {sf.note}",
                layer="response_surface", weight=weight,
            ))

    # Weighted voting merge: a row can accumulate multiple findings across
    # layers. Requiring agreement between detectors is explicitly wrong here
    # (it dropped recall 12/12 -> 8/12 in testing) -- each layer's own finding
    # already passed that layer's threshold, so arbitration's job is to
    # (a) keep the single strongest finding driving the row's output class
    # and (b) cluster consequences of one root cause under it, not to gate
    # membership on multi-layer agreement.
    by_row: dict[int, list[RowFinding]] = {}
    for f in findings:
        by_row.setdefault(f.row_id, []).append(f)

    merged: list[RowFinding] = []
    class_priority = {"impossible": 0, "inconsistent": 1, "unsuitable_for_training": 2}
    for _rid, fs in by_row.items():
        fs.sort(key=lambda f: (class_priority[f.output_class], -f.weight))
        primary = fs[0]
        if len(fs) > 1:
            others = "; ".join(f"{f.layer}:{f.reason}" for f in fs[1:])
            primary.reason = f"{primary.reason} [root cause of {len(fs)-1} more: {others}]"
        merged.append(primary)

    return merged
