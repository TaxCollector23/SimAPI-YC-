"""
SimAPI — Automatic repair layer.

Runs AFTER validation, never instead of it. Every repair here is deterministic,
reversible, and safe: no repair here can turn bad data into data that looks
better than it is — they fix structural problems (duplicate rows, missing IDs,
out-of-order timestamps, wrapped angles, short NaN gaps), not physics
violations. A physics violation (out-of-bounds value, unit error, sensor
drift) is a data quality problem the user must investigate — SimAPI will
never silently rewrite a physically implausible value to make it pass.

Every repair produces a preview (before/after per affected row) before
anything is applied. Nothing is written unless the caller explicitly applies
the repair.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

# Column names that plausibly represent a wrapped angle, where values are
# expected in a canonical range and "wraps" (e.g. 190 degrees meant as -170)
# are a common copy/paste or unit-convention bug rather than corruption.
ANGLE_COLUMNS = {"angle_of_attack", "yaw_angle", "pitch_angle", "roll_angle", "phase_angle"}
TIME_COLUMNS = {"time", "timestamp", "t", "time_s", "elapsed_time", "step_time"}
ID_COLUMNS = {"id", "trial_id", "run_id", "case_id", "sample_id"}


@dataclass
class RepairChange:
    row: int
    column: str
    before: Any
    after: Any


@dataclass
class RepairProposal:
    kind: str
    description: str
    changes: list[RepairChange] = field(default_factory=list)
    rows_dropped: list[int] = field(default_factory=list)
    reorder_index: list[int] | None = None  # new row order, expressed in original index values

    @property
    def affected_row_count(self) -> int:
        if self.reorder_index is not None:
            return sum(1 for i, orig in enumerate(self.reorder_index) if i != orig)
        return len({c.row for c in self.changes}) + len(self.rows_dropped)

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "description": self.description,
            "affected_row_count": self.affected_row_count,
            "changes": [
                {"row": c.row, "column": c.column, "before": _jsonable(c.before), "after": _jsonable(c.after)}
                for c in self.changes[:20]
            ],
            "rows_dropped": self.rows_dropped[:20],
            "reorder_preview": self.reorder_index[:20] if self.reorder_index else None,
            "changes_truncated": len(self.changes) > 20,
            "rows_dropped_truncated": len(self.rows_dropped) > 20,
        }


def _jsonable(v):
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    if pd.isna(v):
        return None
    return v


@dataclass
class RepairReport:
    proposals: list[RepairProposal]
    unrepairable: list[dict]

    def to_dict(self) -> dict:
        return {
            "proposals": [p.to_dict() for p in self.proposals],
            "unrepairable": self.unrepairable,
            "total_changes": sum(p.affected_row_count for p in self.proposals),
        }

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply every proposal in this report to a copy of df and return it."""
        out = df.copy()
        drop_indices: set[int] = set()
        for p in self.proposals:
            if p.reorder_index is not None:
                valid = [i for i in p.reorder_index if i in out.index]
                out = out.loc[valid]
                continue
            for change in p.changes:
                if change.row in out.index:
                    out.at[change.row, change.column] = change.after
            drop_indices.update(p.rows_dropped)
        if drop_indices:
            out = out.drop(index=[i for i in drop_indices if i in out.index])
        return out.reset_index(drop=True)


def _find_column(df: pd.DataFrame, candidates: set[str]) -> str | None:
    lower = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand in lower:
            return lower[cand]
    return None


def repair_duplicate_rows(df: pd.DataFrame) -> RepairProposal | None:
    """Exact-duplicate rows are almost always a copy-paste artifact, not real data."""
    dup_mask = df.duplicated(keep="first")
    if not dup_mask.any():
        return None
    dropped = df.index[dup_mask].tolist()
    return RepairProposal(
        kind="duplicate_rows",
        description=f"{len(dropped)} row(s) are exact duplicates of an earlier row — removing the repeats.",
        rows_dropped=dropped,
    )


def repair_id_column(df: pd.DataFrame) -> RepairProposal | None:
    """Ensure a stable, unique trial identifier: add one if missing, de-duplicate if present."""
    id_col = _find_column(df, ID_COLUMNS)
    if id_col is None:
        return None  # No ID column present — nothing to repair (this is not "missing IDs", it's "no ID scheme").
    series = df[id_col]
    dup_mask = series.duplicated(keep="first")
    if not dup_mask.any() and series.notna().all():
        return None
    changes = []
    seen = set(series.dropna().tolist())
    next_id = (max((v for v in seen if isinstance(v, (int, float))), default=-1)) + 1
    dup_rows = set(df.index[dup_mask].tolist())
    for idx in df.index:
        val = series.loc[idx]
        needs_fix = pd.isna(val) or idx in dup_rows
        if needs_fix:
            while next_id in seen:
                next_id += 1
            changes.append(RepairChange(row=idx, column=id_col, before=val, after=next_id))
            seen.add(next_id)
            next_id += 1
    if not changes:
        return None
    return RepairProposal(
        kind="duplicate_or_missing_ids",
        description=f"{len(changes)} row(s) had a missing or duplicate '{id_col}' — assigning a new unique value.",
        changes=changes,
    )


def repair_timestamp_ordering(df: pd.DataFrame) -> RepairProposal | None:
    """If a time-like column exists and isn't monotonic, the rows are out of chronological order."""
    time_col = _find_column(df, TIME_COLUMNS)
    if time_col is None or not pd.api.types.is_numeric_dtype(df[time_col]):
        return None
    series = df[time_col]
    if series.is_monotonic_increasing:
        return None
    sorted_idx = series.sort_values(kind="stable").index.tolist()
    if sorted_idx == list(df.index):
        return None
    moved = sum(1 for i, orig in enumerate(sorted_idx) if i != orig)
    if moved == 0:
        return None
    return RepairProposal(
        kind="timestamp_ordering",
        description=f"Rows are not sorted by '{time_col}' — {moved} row(s) are out of chronological order.",
        reorder_index=sorted_idx,
    )


def repair_wrapped_angles(df: pd.DataFrame) -> RepairProposal | None:
    """Angle columns outside [-180, 180] are usually a wrap-around convention mismatch, not corruption."""
    changes = []
    for col in df.columns:
        if col.lower() not in ANGLE_COLUMNS or not pd.api.types.is_numeric_dtype(df[col]):
            continue
        for idx, val in df[col].items():
            if pd.isna(val) or -180.0 <= val <= 180.0:
                continue
            wrapped = ((val + 180.0) % 360.0) - 180.0
            changes.append(RepairChange(row=idx, column=col, before=val, after=round(wrapped, 6)))
    if not changes:
        return None
    return RepairProposal(
        kind="wrapped_angles",
        description=f"{len(changes)} angle value(s) fall outside [-180°, 180°] — normalizing to the canonical range.",
        changes=changes,
    )


def repair_short_nan_gaps(df: pd.DataFrame, max_gap: int = 3) -> tuple[RepairProposal | None, list[dict]]:
    """Interpolate isolated short runs of missing numeric values; flag long gaps as unrepairable."""
    changes = []
    unrepairable = []
    id_cols = {c.lower() for c in df.columns if c.lower() in ID_COLUMNS}
    numeric_cols = [c for c in df.select_dtypes(include=[np.number]).columns if c.lower() not in id_cols]
    for col in numeric_cols:
        series = df[col]
        is_na = series.isna()
        if not is_na.any():
            continue
        interpolated = series.interpolate(method="linear", limit=max_gap, limit_area="inside")
        for idx in df.index[is_na]:
            new_val = interpolated.loc[idx]
            if pd.notna(new_val):
                changes.append(RepairChange(row=idx, column=col, before=np.nan, after=round(float(new_val), 6)))
        still_na = interpolated.isna() & is_na
        if still_na.any():
            unrepairable.append({
                "column": col,
                "reason": f"{int(still_na.sum())} missing value(s) in '{col}' are in gaps longer than "
                          f"{max_gap} consecutive rows, or at the start/end where interpolation is unsafe. "
                          "These rows should be reviewed manually.",
                "rows": df.index[still_na].tolist()[:20],
            })
    if not changes:
        return None, unrepairable
    return (
        RepairProposal(
            kind="missing_value_interpolation",
            description=f"{len(changes)} missing numeric value(s) are in short gaps (<= {max_gap} rows) — "
                        "filling by linear interpolation between adjacent trials.",
            changes=changes,
        ),
        unrepairable,
    )


def analyze(df: pd.DataFrame) -> RepairReport:
    """Run every repair check and return a preview report. Nothing is modified."""
    proposals: list[RepairProposal] = []
    unrepairable: list[dict] = []

    for fn in (repair_duplicate_rows, repair_id_column, repair_timestamp_ordering, repair_wrapped_angles):
        result = fn(df)
        if result is not None:
            proposals.append(result)

    nan_proposal, nan_unrepairable = repair_short_nan_gaps(df)
    if nan_proposal is not None:
        proposals.append(nan_proposal)
    unrepairable.extend(nan_unrepairable)

    return RepairReport(proposals=proposals, unrepairable=unrepairable)
