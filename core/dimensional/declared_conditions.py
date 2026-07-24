"""
Layer 7 -- declared conditions as assertions.

The caller already supplies domain/conditions metadata (e.g. altitude,
declared free-stream velocity). Today that's decorative; here it's testable.
If the user declares 11000 m and the data implies 288 K, that's a finding no
self-consistency method between columns can ever produce -- and when the
dataset has NO temperature column at all, the ISA-derived value becomes the
anchor of last resort for Layer 3.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .pi_laws import LawFinding

R_AIR = 287.05
G0 = 9.80665
T0_ISA = 288.15   # K at sea level
P0_ISA = 101325.0
LAPSE_RATE = 0.0065  # K/m, up to 11 km


def isa_at_altitude(alt_m: float) -> tuple[float, float, float]:
    """Standard-atmosphere (troposphere, <=11km; simplified isothermal
    stratosphere beyond) temperature (K), pressure (Pa), density (kg/m^3)."""
    if alt_m <= 11000.0:
        t = T0_ISA - LAPSE_RATE * alt_m
        p = P0_ISA * (t / T0_ISA) ** (G0 / (LAPSE_RATE * R_AIR))
    else:
        t11 = T0_ISA - LAPSE_RATE * 11000.0
        p11 = P0_ISA * (t11 / T0_ISA) ** (G0 / (LAPSE_RATE * R_AIR))
        t = t11
        p = p11 * np.exp(-G0 * (alt_m - 11000.0) / (R_AIR * t11))
    rho = p / (R_AIR * t)
    return float(t), float(p), float(rho)


@dataclass
class ConditionAssertion:
    label: str
    declared: float
    implied: float
    rel_dev: float
    columns: tuple[str, ...]
    row_ids: list[int]


def check_declared_conditions(data: pd.DataFrame, conditions: dict) -> tuple[list[ConditionAssertion], list[LawFinding]]:
    """Returns (direct assertion violations, synthetic anchors for Layer 3
    to consume when the dataset lacks a column ISA could otherwise check)."""
    assertions: list[ConditionAssertion] = []
    synthetic_anchors: list[LawFinding] = []

    alt = conditions.get("altitude_m", conditions.get("altitude"))
    if alt is None:
        return assertions, synthetic_anchors

    t_isa, p_isa, rho_isa = isa_at_altitude(float(alt))

    temp_col = next((c for c in data.columns if "temp" in c.lower() and "delta" not in c.lower()), None)
    press_col = next((c for c in data.columns if c.lower() in ("p", "pressure", "p_static", "static_pressure")), None)
    dens_col = next((c for c in data.columns if "density" in c.lower() or c.lower() in ("rho", "rho_inf")), None)

    for col, expected, label in ((temp_col, t_isa, "ISA temperature"),
                                  (press_col, p_isa, "ISA pressure"),
                                  (dens_col, rho_isa, "ISA density")):
        if col is None:
            continue
        s = pd.to_numeric(data[col], errors="coerce").dropna()
        if len(s) == 0:
            continue
        median = float(s.median())
        rel_dev = abs(median - expected) / abs(expected)
        if rel_dev > 0.05:
            bad = s[np.abs(s - expected) / abs(expected) > 0.05]
            assertions.append(ConditionAssertion(
                label=f"{label} at {alt:g} m: declared implies {expected:.2f}, data median {median:.2f}",
                declared=expected, implied=median, rel_dev=rel_dev,
                columns=(col,), row_ids=[int(i) for i in bad.index],
            ))

    # Anchor of last resort: if there's no temperature column at all but
    # there IS pressure and density, inject T_ISA as a synthetic constant so
    # Layer 3's P/(rho*T) family of checks still has something to anchor on.
    if temp_col is None and press_col is not None and dens_col is not None:
        p = pd.to_numeric(data[press_col], errors="coerce")
        rho = pd.to_numeric(data[dens_col], errors="coerce")
        with np.errstate(all="ignore"):
            r_calc = p / (rho * t_isa)
        valid = r_calc.dropna()
        if len(valid) >= 5:
            rel = np.abs(valid - R_AIR) / R_AIR
            coverage = float((rel <= 0.02).mean())
            if coverage >= 0.10:
                violated = {int(i): float(valid.loc[i] / R_AIR) for i in valid.index[rel > 0.02]}
                synthetic_anchors.append(LawFinding(
                    kind="anchored_constant",
                    label=f"{press_col}/({dens_col}·T_ISA) = R_air (T_ISA={t_isa:.1f}K from declared altitude)",
                    columns=(press_col, dens_col),
                    expected_value=R_AIR,
                    observed_median=float(valid.median()),
                    scale=R_AIR * 0.02,
                    violated_rows=violated,
                    coverage=coverage,
                    weight=1.0,
                    note=f"declared altitude {alt:g}m used as anchor of last resort (no temperature column)",
                ))
    return assertions, synthetic_anchors
