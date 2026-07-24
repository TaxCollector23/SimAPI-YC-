"""
Exact rational linear algebra over `fractions.Fraction`.

Deliberately NOT numpy/SVD. A full-matrix SVD null space returns an
arbitrary orthonormal basis that rotates physically meaningful dimensionless
groups into meaningless linear combinations of them -- this is documented as
the single bug that took detection from 12/15 to 1/15. Exact rational
elimination on small (<=4 column) subsets gives a null space aligned with
the actual integer/half-integer structure of physical laws, not an
arbitrary rotation of it.
"""
from __future__ import annotations

from fractions import Fraction

Matrix = list[list[Fraction]]
Vector = list[Fraction]


def _copy(m: Matrix) -> Matrix:
    return [row[:] for row in m]


def rref(matrix: Matrix) -> tuple[Matrix, list[int]]:
    """Row-reduced echelon form. Returns (rref_matrix, pivot_columns)."""
    m = _copy(matrix)
    if not m:
        return m, []
    n_rows, n_cols = len(m), len(m[0])
    pivot_row = 0
    pivots: list[int] = []
    for col in range(n_cols):
        # Find a nonzero pivot at or below pivot_row.
        sel = None
        for r in range(pivot_row, n_rows):
            if m[r][col] != 0:
                sel = r
                break
        if sel is None:
            continue
        m[pivot_row], m[sel] = m[sel], m[pivot_row]
        pv = m[pivot_row][col]
        m[pivot_row] = [x / pv for x in m[pivot_row]]
        for r in range(n_rows):
            if r == pivot_row:
                continue
            factor = m[r][col]
            if factor != 0:
                m[r] = [a - factor * b for a, b in zip(m[r], m[pivot_row], strict=True)]
        pivots.append(col)
        pivot_row += 1
        if pivot_row == n_rows:
            break
    return m, pivots


def null_space(D: Matrix) -> list[Vector]:
    """Basis for {e : D @ e = 0}, D is n_dims x n_cols. Exact rational."""
    if not D or not D[0]:
        return []
    n_cols = len(D[0])
    r, pivots = rref(D)
    pivot_set = set(pivots)
    free_cols = [c for c in range(n_cols) if c not in pivot_set]
    basis: list[Vector] = []
    for free in free_cols:
        vec = [Fraction(0)] * n_cols
        vec[free] = Fraction(1)
        for i, pc in enumerate(pivots):
            # r[i][free] is the coefficient tying pivot column pc to free column.
            vec[pc] = -r[i][free]
        basis.append(vec)
    return basis


def solve_particular(D: Matrix, target: Vector) -> Vector | None:
    """One solution to D @ e = target, or None if inconsistent."""
    if not D or not D[0]:
        return None
    n_rows, n_cols = len(D), len(D[0])
    aug = [D[i][:] + [target[i]] for i in range(n_rows)]
    r, pivots = rref(aug)
    # Inconsistent if any row is [0,...,0 | nonzero].
    for row in r:
        if all(x == 0 for x in row[:n_cols]) and row[n_cols] != 0:
            return None
    sol = [Fraction(0)] * n_cols
    for i, pc in enumerate(pivots):
        if pc < n_cols:
            sol[pc] = r[i][n_cols]
    return sol


def gcd_frac(vec: Vector) -> Fraction:
    """Largest Fraction g such that every entry is an integer multiple of g,
    used to normalize a null-space basis vector to its simplest form."""
    from math import gcd as _igcd
    nz = [x for x in vec if x != 0]
    if not nz:
        return Fraction(1)
    num_g = 0
    den_l = 1
    for x in nz:
        num_g = _igcd(num_g, abs(x.numerator))
        den_l = den_l * x.denominator // _igcd(den_l, x.denominator)
    if num_g == 0:
        return Fraction(1)
    return Fraction(num_g, den_l)


def normalize_vector(vec: Vector) -> Vector:
    g = gcd_frac(vec)
    if g == 0:
        return vec
    return [x / g for x in vec]
