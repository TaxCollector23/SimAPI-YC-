"""
Layer 1 -- Pi basis discovery.

Enumerates column subsets of size 2-4 and solves each subset's dimension
matrix null space independently and exactly (see linalg.py for why not a
full-matrix SVD). Accepted groups are integer/half-integer exponent
combinations with |exponent| <= 6, verified to produce finite numeric
values. Pairwise sums/differences of accepted groups are also tested, since
a law is often that two groups stand in a fixed ratio, not that either one
alone is constant.

Performance: subset enumeration is combinatorial, so columns are capped
(default 15) and prioritized by variance and dictionary/LLM confidence
before any subsets are built. Column-set signatures are cached within a run
to avoid recomputing a subset reached via more than one path.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from fractions import Fraction

import numpy as np
import pandas as pd

from .linalg import Matrix, gcd_frac, null_space
from .units_resolver import UnitsResolution

MAX_COLUMNS = 15
SUBSET_SIZES = (2, 3, 4)
MAX_ABS_EXPONENT = Fraction(6)
HALF_INTEGER_DENOMS = {1, 2}


@dataclass
class PiGroup:
    exponents: dict[str, Fraction]     # column -> exponent, zero entries omitted
    values: np.ndarray                 # computed group value per surviving row
    # Original data.index labels for each entry in `values`. When any
    # participating column has NaN, `_compute_values` drops those rows and
    # `values` becomes shorter than `data`. Downstream layers (2, 4) MUST
    # map positions through this index or they misattribute violations by
    # the number of dropped rows -- silently flagging clean rows and
    # missing corrupted ones. Regression: test_layer4_bimodal_split_row_ids_
    # survive_nan_column.
    index: pd.Index | None = None
    origin: str = "basis"              # "basis" | "sum" | "difference"
    source_columns: tuple[str, ...] = field(default_factory=tuple)

    @property
    def columns(self) -> tuple[str, ...]:
        return tuple(sorted(self.exponents))

    @property
    def signature(self) -> str:
        return "|".join(f"{c}^{self.exponents[c]}" for c in self.columns)

    def label(self) -> str:
        parts = []
        for c in self.columns:
            e = self.exponents[c]
            parts.append(c if e == 1 else f"{c}^{_fmt_exp(e)}")
        return "·".join(parts)


def _fmt_exp(e: Fraction) -> str:
    return str(e.numerator) if e.denominator == 1 else f"{e.numerator}/{e.denominator}"


def _is_half_integer(e: Fraction) -> bool:
    return e.denominator in HALF_INTEGER_DENOMS


def select_columns(data: pd.DataFrame, units: UnitsResolution, cap: int = MAX_COLUMNS) -> list[str]:
    usable = [c for c in units.usable_columns() if c in data.columns]
    scored = []
    for c in usable:
        s = pd.to_numeric(data[c], errors="coerce").dropna()
        if len(s) < 3:
            continue
        cv = float(s.std() / abs(s.mean())) if s.mean() != 0 else float(s.std())
        conf = units.columns[c].confidence
        scored.append((conf * (1.0 + min(cv, 5.0)), c))
    scored.sort(reverse=True)
    return [c for _, c in scored[:cap]]


def _compute_values(
    data: pd.DataFrame, exponents: dict[str, Fraction]
) -> tuple[np.ndarray, pd.Index] | None:
    """Return (values, surviving_index). Callers must use surviving_index
    to map positions back to data row ids; the values array is only as
    long as the rows that had non-NaN entries in every participating
    column."""
    cols = list(exponents)
    sub = data[cols].apply(pd.to_numeric, errors="coerce")
    if sub.isna().any().any():
        sub = sub.dropna()
        if len(sub) < 3:
            return None
    try:
        result = np.ones(len(sub), dtype=float)
        for c in cols:
            e = float(exponents[c])
            col_vals = sub[c].to_numpy(dtype=float)
            if e != int(e) and (col_vals < 0).any():
                return None  # fractional power of a negative number
            with np.errstate(all="ignore"):
                result = result * np.power(col_vals, e)
        if not np.all(np.isfinite(result)):
            return None
        return result, sub.index
    except Exception:
        return None


def find_pi_groups(
    data: pd.DataFrame,
    units: UnitsResolution,
    max_columns: int = MAX_COLUMNS,
    subset_sizes: tuple[int, ...] = SUBSET_SIZES,
) -> list[PiGroup]:
    columns = select_columns(data, units, cap=max_columns)
    cache: dict[str, list[list[Fraction]]] = {}
    groups: list[PiGroup] = []
    seen_signatures: set[str] = set()

    for size in subset_sizes:
        for subset in itertools.combinations(columns, size):
            sig = "|".join(subset)
            if sig in cache:
                basis = cache[sig]
            else:
                D: Matrix = [[units.columns[c].dimension[axis] for c in subset] for axis in range(7)]
                basis = null_space(D)
                cache[sig] = basis
            for vec in basis:
                normed = _normalize(vec)
                if normed is None:
                    continue
                exponents = {c: e for c, e in zip(subset, normed, strict=True) if e != 0}
                if len(exponents) < 2:
                    continue
                cv = _compute_values(data, exponents)
                if cv is None:
                    continue
                values, index = cv
                pg = PiGroup(exponents=exponents, values=values, index=index,
                             origin="basis", source_columns=subset)
                if pg.signature in seen_signatures:
                    continue
                seen_signatures.add(pg.signature)
                groups.append(pg)

    # Pairwise sums/differences: a fixed *ratio* between two groups (e.g.
    # Re / (rho*v*L/mu) == 1) is a law even when neither group alone is
    # constant. Cap the base-group count fed into this O(n^2) step.
    base = groups[:60]
    for g1, g2 in itertools.combinations(base, 2):
        for op, origin in ((1, "sum"), (-1, "difference")):
            combined = dict(g1.exponents)
            for c, e in g2.exponents.items():
                combined[c] = combined.get(c, Fraction(0)) + op * e
            combined = {c: e for c, e in combined.items() if e != 0}
            if len(combined) < 2 or any(abs(e) > MAX_ABS_EXPONENT for e in combined.values()):
                continue
            if not all(_is_half_integer(e) for e in combined.values()):
                continue
            cv = _compute_values(data, combined)
            if cv is None:
                continue
            values, index = cv
            pg = PiGroup(exponents=combined, values=values, index=index, origin=origin,
                         source_columns=tuple(sorted(set(g1.source_columns) | set(g2.source_columns))))
            if pg.signature in seen_signatures:
                continue
            seen_signatures.add(pg.signature)
            groups.append(pg)

    return groups


def _normalize(vec: list[Fraction]) -> list[Fraction] | None:
    g = gcd_frac(vec)
    if g == 0:
        return None
    normed = [x / g for x in vec]
    # Try halving if that still keeps everything on the half-integer grid
    # and produces a smaller-magnitude vector (prefer the simplest form).
    if all((x * 2).denominator == 1 for x in normed):
        halved = [x / 2 for x in normed]
        if all(_is_half_integer(x) for x in halved) and max(abs(x) for x in halved) >= Fraction(1, 2):
            if max(abs(x) for x in halved) < max(abs(x) for x in normed):
                normed = halved
    if any(abs(x) > MAX_ABS_EXPONENT for x in normed):
        return None
    if not all(_is_half_integer(x) for x in normed):
        return None
    if all(x == 0 for x in normed):
        return None
    return normed
