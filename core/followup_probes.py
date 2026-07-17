"""
SimAPI — Follow-up Probes for AI Orchestrator Phase 3.

Targeted tests that the standard physics engine does not run. Each probe
returns a dict with 'flagged' (bool), 'detail' (str), and probe-specific data.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def probe_gas_constant(data: pd.DataFrame) -> dict:
    """Check P/(ρT) for every trial — catches unit errors that individually pass bounds."""
    cols = set(data.columns)
    if not {"pressure", "density", "temperature"}.issubset(cols):
        return {"flagged": False, "detail": "Missing required columns (pressure, density, temperature)"}

    R_expected = 287.05
    R_calc = data["pressure"] / (data["density"] * data["temperature"]).replace(0, np.nan)
    R_calc = R_calc.dropna()

    bad_mask = (R_calc < R_expected * 0.85) | (R_calc > R_expected * 1.15)
    bad_indices = list(R_calc[bad_mask].index.astype(int))

    if not bad_indices:
        return {"flagged": False, "detail": "All trials satisfy P/(ρT) ≈ 287 J/kg·K"}

    return {
        "flagged": True,
        "detail": f"{len(bad_indices)} trials where P/(ρT) deviates >15% from 287 J/kg·K — likely unit error in pressure, density, or temperature",
        "bad_indices": bad_indices[:50],
        "sample_values": [round(float(R_calc.iloc[i]), 2) for i in range(min(5, len(bad_indices)))],
    }


def probe_joint_distribution_shift(data: pd.DataFrame, col_a: str, col_b: str) -> dict:
    """Check if the correlation between two columns changes between first/second half."""
    if col_a not in data.columns or col_b not in data.columns:
        return {"flagged": False, "detail": f"Columns {col_a}/{col_b} not found"}

    a = data[col_a].dropna()
    b = data[col_b].dropna()
    idx = a.index.intersection(b.index)

    if len(idx) < 20:
        return {"flagged": False, "detail": "Insufficient data for joint distribution test"}

    mid = len(idx) // 2
    a_vals = a.loc[idx].values
    b_vals = b.loc[idx].values

    r_first = float(np.corrcoef(a_vals[:mid], b_vals[:mid])[0, 1]) if np.std(a_vals[:mid]) > 0 and np.std(b_vals[:mid]) > 0 else 0
    r_second = float(np.corrcoef(a_vals[mid:], b_vals[mid:])[0, 1]) if np.std(a_vals[mid:]) > 0 and np.std(b_vals[mid:]) > 0 else 0

    if np.isnan(r_first) or np.isnan(r_second):
        return {"flagged": False, "detail": "Could not compute correlations"}

    shift = abs(r_first - r_second)
    if shift > 0.3:
        return {
            "flagged": True,
            "detail": f"Correlation between {col_a} and {col_b} shifts by {shift:.3f} between first half (r={r_first:.3f}) and second half (r={r_second:.3f}) — possible condition change or data concatenation",
            "r_first_half": round(r_first, 4),
            "r_second_half": round(r_second, 4),
            "shift": round(shift, 4),
        }

    return {"flagged": False, "detail": f"Correlation between {col_a} and {col_b} is stable (shift={shift:.3f})"}


def probe_duplicate_cosine(data: pd.DataFrame) -> dict:
    """Find near-duplicate trial pairs using cosine similarity on numeric columns."""
    nc = list(data.select_dtypes(include=[np.number]).columns)
    if len(nc) < 2 or len(data) < 5:
        return {"flagged": False, "detail": "Insufficient data for duplicate detection"}

    X = data[nc].fillna(0).values
    means = X.mean(axis=0)
    stds = X.std(axis=0)
    stds[stds == 0] = 1
    Xn = (X - means) / stds

    norms = np.linalg.norm(Xn, axis=1, keepdims=True)
    norms[norms == 0] = 1
    Xn = Xn / norms

    duplicates = []
    window = 5
    for i in range(min(len(data) - 1, 2000)):
        for j in range(i + 1, min(i + window + 1, len(data))):
            sim = float(np.dot(Xn[i], Xn[j]))
            if sim > 0.9999:
                duplicates.append((i, j, round(sim, 6)))

    if not duplicates:
        return {"flagged": False, "detail": "No near-duplicate trial pairs found"}

    return {
        "flagged": True,
        "detail": f"{len(duplicates)} near-duplicate trial pairs found (cosine > 0.9999) — likely copy-paste contamination",
        "pairs": duplicates[:20],
    }


def probe_regime_change(data: pd.DataFrame, col: str, n_windows: int = 8) -> dict:
    """Detect if data comes from multiple distinct operating conditions."""
    if col not in data.columns:
        return {"flagged": False, "detail": f"Column {col} not found"}

    s = data[col].dropna()
    if len(s) < n_windows * 4:
        return {"flagged": False, "detail": "Insufficient data for regime change detection"}

    vals = s.values
    overall_cv = float(np.std(vals) / abs(np.mean(vals))) if np.mean(vals) != 0 else 0

    w_size = len(vals) // n_windows
    within_cvs = []
    for i in range(n_windows):
        chunk = vals[i * w_size:(i + 1) * w_size]
        if len(chunk) > 1 and np.mean(chunk) != 0:
            within_cvs.append(float(np.std(chunk) / abs(np.mean(chunk))))

    if not within_cvs:
        return {"flagged": False, "detail": "Could not compute within-window variation"}

    avg_within_cv = float(np.mean(within_cvs))

    if overall_cv > 0 and avg_within_cv > 0:
        ratio = overall_cv / avg_within_cv
        if ratio > 3.0:
            return {
                "flagged": True,
                "detail": f"{col}: overall CV ({overall_cv:.4f}) is {ratio:.1f}× the within-window CV ({avg_within_cv:.4f}) — data likely contains multiple operating conditions concatenated together",
                "overall_cv": round(overall_cv, 4),
                "within_cv": round(avg_within_cv, 4),
                "ratio": round(ratio, 2),
            }

    return {"flagged": False, "detail": f"{col}: CV ratio is normal ({overall_cv:.4f} overall vs {avg_within_cv:.4f} within windows)"}


def probe_physically_impossible_combinations(data: pd.DataFrame, sim_type: str) -> dict:
    """Check for physically impossible combinations specific to the simulation type."""
    cols = set(data.columns)
    findings = []

    if sim_type == "aerodynamics":
        if {"lift_coefficient", "angle_of_attack"}.issubset(cols):
            # Thin airfoil theory: Cl ≈ 2π sin(α)
            alpha = data["angle_of_attack"]
            cl = data["lift_coefficient"]
            # Convert degrees to radians if values suggest degrees
            alpha_rad = np.where(np.abs(alpha) > 1.0, np.radians(alpha), alpha)
            cl_theory = 2 * np.pi * np.sin(alpha_rad)
            deviation = np.abs(cl - cl_theory)
            bad = deviation > 2.0
            if bad.sum() > len(data) * 0.1:
                findings.append(f"Cl vs α: {int(bad.sum())} trials deviate significantly from thin airfoil theory")

        if {"drag_coefficient", "reynolds_number"}.issubset(cols):
            # Very low drag at low Reynolds is suspicious
            low_re = data["reynolds_number"] < 1e4
            low_drag = data["drag_coefficient"] < 0.01
            suspicious = (low_re & low_drag).sum()
            if suspicious > 0:
                findings.append(f"{suspicious} trials with Re<10k but Cd<0.01 — unrealistically low drag for transitional flow")

    if sim_type in ("fluid_dynamics", "aerodynamics"):
        if {"velocity", "mach_number"}.issubset(cols):
            # Check for supersonic velocities marked as subsonic
            supersonic_vel = data["velocity"] > 340
            subsonic_mach = data["mach_number"] < 1.0
            inconsistent = (supersonic_vel & subsonic_mach).sum()
            if inconsistent > 0:
                findings.append(f"{inconsistent} trials with velocity>340 m/s but Mach<1 — speed of sound inconsistency")

    if not findings:
        return {"flagged": False, "detail": "No physically impossible combinations detected"}

    return {
        "flagged": True,
        "detail": "; ".join(findings),
        "findings": findings,
    }
