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
from .units_resolver import UnitsResolution, resolve_units

OUTPUT_CLASSES = ("impossible", "inconsistent", "unsuitable_for_training")


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
        }


def validate(
    data: pd.DataFrame,
    conditions: dict | None = None,
    llm_resolver: Callable[[list[str]], dict[str, dict]] | None = None,
    max_columns: int = 15,
) -> ValidationReport:
    conditions = conditions or {}
    data = data.reset_index(drop=True)
    n_rows = len(data)

    # ── Layer 0 ──────────────────────────────────────────────────────────
    numeric_cols = [c for c in data.columns if pd.api.types.is_numeric_dtype(data[c])
                     or pd.to_numeric(data[c], errors="coerce").notna().mean() > 0.8]
    units = resolve_units(numeric_cols, llm_resolver=llm_resolver)
    si_data = _apply_si_conversion(data, units)

    # ── Layer 1 ──────────────────────────────────────────────────────────
    groups = find_pi_groups(si_data, units, max_columns=max_columns)

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

    # ── Layer 5 ──────────────────────────────────────────────────────────
    surface_findings = find_surface_anomalies(si_data, units)

    # ── Layer 6 ──────────────────────────────────────────────────────────
    semantic_violations = check_semantic_bounds(data)

    # ── Layer 8 ──────────────────────────────────────────────────────────
    structural_findings = check_structural(si_data)

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
        elif sf.kind == "exact_duplicate":
            # Physically valid, harmful to learn from -- unsuitable for
            # training, not "impossible" (the row isn't physically wrong).
            for rid in sf.row_ids:
                findings.append(RowFinding(row_id=rid, output_class="unsuitable_for_training",
                                            reason=sf.detail, layer="structural", weight=1.0))

    for law in laws:
        out_class = "impossible" if law.kind == "anchored_constant" else "inconsistent"
        for rid, factor in law.violated_rows.items():
            cf = _counterfactual_repair(law.columns, rid, factor, si_data, law.kind)
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
