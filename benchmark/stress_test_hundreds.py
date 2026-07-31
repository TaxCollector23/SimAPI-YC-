"""
Large-scale multi-domain adversarial stress test.

Hundreds of individual trials across 5 independent physics domains (not just
aerodynamics -- the domain every other test in this repo already leans on),
5 corruption types, and a graded severity sweep from blatant to deliberately
subtle. Reports honest detection rate as a function of severity per domain
per corruption type -- the actual answer to "how subtle can corruption be
before this stops catching it," not a single pass/fail number.

Run: python -m benchmark.stress_test_hundreds
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.dimensional import validate


def flagged(report) -> set:
    return report.impossible_rows | report.unsuitable_rows | report.inconsistent_rows


# ── Domain generators: each returns a DataFrame of N clean, physically ──────
# consistent rows, built from a REAL formula (not just "plausible-looking"
# random numbers) so corruption has a genuine ground truth to violate.

def dom_ideal_gas(n, rng):
    T = 293.15 + rng.normal(0, 3.0, n)
    rho = 1.225 + rng.normal(0, 0.02, n)
    P = rho * 287.05 * T
    v = rng.uniform(10, 60, n)
    return pd.DataFrame({"temperature": T, "density": rho, "pressure": P, "velocity": v})


def dom_beam_bending(n, rng):
    E = 200e9
    I = 8.33e-6
    L = 2.0
    F = rng.uniform(1000, 5000, n)
    stress = (F * L) * 0.05 / I
    strain = stress / E
    displacement = F * L**3 / (3 * E * I)
    return pd.DataFrame({"force_n": F, "stress_pa": stress, "strain": strain, "displacement_m": displacement})


def dom_orbital(n, rng):
    G = 6.674e-11
    M_earth = 5.972e24
    r = rng.uniform(6.6e6, 4.2e7, n)  # LEO to GEO-ish, meters
    v_orbit = np.sqrt(G * M_earth / r)
    period = 2 * np.pi * np.sqrt(r**3 / (G * M_earth))
    return pd.DataFrame({"orbital_radius_m": r, "orbital_velocity": v_orbit, "period_s": period})


def dom_electrical(n, rng):
    R = rng.uniform(10, 1000, n)
    I = rng.uniform(0.01, 2.0, n)
    V = I * R
    P = I**2 * R
    return pd.DataFrame({"resistance_ohm": R, "current_a": I, "voltage_v": V, "power_w": P})


def dom_projectile(n, rng):
    g = 9.80665
    v0 = rng.uniform(10, 100, n)
    angle = rng.uniform(0.1, 1.4, n)  # radians
    t_flight = 2 * v0 * np.sin(angle) / g
    range_m = v0**2 * np.sin(2 * angle) / g
    max_height = (v0 * np.sin(angle))**2 / (2 * g)
    return pd.DataFrame({"launch_velocity": v0, "launch_angle_rad": angle,
                         "flight_time_s": t_flight, "range_m": range_m, "max_height_m": max_height})


def dom_acoustics(n, rng):
    c = 343.0
    freq = rng.uniform(200, 5000, n)
    wavelength = c / freq
    sound_pressure = rng.uniform(1.0, 3.0, n)
    intensity_level = rng.uniform(85, 100, n)
    return pd.DataFrame({"frequency": freq, "wavelength": wavelength, "sound_speed": np.full(n, c),
                         "sound_pressure": sound_pressure, "intensity_level": intensity_level})


def dom_electromagnetics(n, rng):
    c = 2.998e8
    freq = rng.uniform(1e8, 1e10, n)
    wavelength = c / freq
    e_field = rng.uniform(5, 20, n)
    b_field = e_field / c
    power = rng.uniform(1, 10, n)
    return pd.DataFrame({"frequency": freq, "wavelength": wavelength, "electric_field": e_field,
                         "magnetic_field": b_field, "power": power})


def dom_geomechanics(n, rng):
    g = 9.80665
    depth = rng.uniform(10, 300, n)
    density = np.full(n, 2500.0)
    vertical_stress = density * g * depth
    pore_pressure = 998 * g * depth * 0.4
    friction_angle = rng.uniform(28, 36, n)
    return pd.DataFrame({"depth": depth, "density": density, "vertical_stress": vertical_stress,
                         "pore_pressure": pore_pressure, "friction_angle": friction_angle})


def dom_biomechanics(n, rng):
    g = 9.80665
    mass = rng.uniform(50, 100, n)
    grf = mass * g
    joint_velocity = rng.uniform(1.0, 3.0, n)
    joint_angle = rng.uniform(0.2, 0.8, n)
    muscle_force = 0.85 * grf + rng.normal(0, 5, n)  # peak muscle force scales with body weight
    return pd.DataFrame({"body_mass": mass, "ground_reaction_force": grf, "joint_velocity": joint_velocity,
                         "joint_angle": joint_angle, "muscle_force": muscle_force})


def dom_plasma(n, rng):
    k_B = 1.380649e-23
    mu_0 = 4 * np.pi * 1e-7
    n_e = rng.uniform(0.8e20, 1.2e20, n)
    T = np.full(n, 1e7)
    pressure = n_e * k_B * T
    b_field = np.full(n, 5.0)
    magnetic_pressure = b_field**2 / (2 * mu_0)
    beta = pressure / magnetic_pressure  # plasma beta = thermal pressure / magnetic pressure
    return pd.DataFrame({"electron_density": n_e, "temperature": T, "plasma_pressure": pressure,
                         "magnetic_field": b_field, "beta": beta})


def dom_chemical_reactor(n, rng):
    R_molar = 8.3145
    T = rng.uniform(330, 370, n)
    conc = np.full(n, 10.0)
    pressure = conc * R_molar * T
    reaction_rate = rng.uniform(0.03, 0.06, n)
    conversion = rng.uniform(0.75, 0.9, n)
    return pd.DataFrame({"temperature": T, "concentration": conc, "pressure": pressure,
                         "reaction_rate": reaction_rate, "conversion": conversion})


def dom_hydrodynamics(n, rng):
    g = 9.80665
    depth = rng.uniform(10, 100, n)
    density = np.full(n, 998.0)
    pressure = density * g * depth
    flow_velocity = rng.uniform(0.5, 3.0, n)
    froude = flow_velocity / np.sqrt(g * depth)
    return pd.DataFrame({"water_depth": depth, "density": density, "pressure": pressure,
                         "flow_velocity": flow_velocity, "froude_number": froude})


def dom_meteorology(n, rng):
    altitude = rng.uniform(0, 3000, n)
    temperature = 288.15 - 0.0065 * altitude + rng.normal(0, 0.3, n)
    pressure = 101325 * (temperature / 288.15) ** 5.2559 + rng.normal(0, 50, n)
    humidity = rng.uniform(0.4, 0.7, n)
    wind_speed = rng.uniform(2, 15, n)
    return pd.DataFrame({"altitude": altitude, "temperature": temperature, "pressure": pressure,
                         "humidity": humidity, "wind_speed": wind_speed})


def dom_tribology(n, rng):
    load = rng.uniform(50, 200, n)
    sliding_speed = rng.uniform(0.5, 2.0, n)
    mu = np.full(n, 0.3)
    friction_force = mu * load
    wear_rate = rng.uniform(0.8e-6, 1.6e-6, n)
    return pd.DataFrame({"load": load, "sliding_speed": sliding_speed, "friction_coefficient": mu,
                         "friction_force": friction_force, "wear_rate": wear_rate})


def dom_aeroelasticity(n, rng):
    rho = 1.225
    velocity = rng.uniform(50, 150, n)
    dynamic_pressure = 0.5 * rho * velocity**2
    wing_deflection = rng.uniform(0.03, 0.15, n)
    natural_frequency = rng.uniform(11, 14, n)
    return pd.DataFrame({"velocity": velocity, "density": np.full(n, rho), "dynamic_pressure": dynamic_pressure,
                         "wing_deflection": wing_deflection, "natural_frequency": natural_frequency})


def dom_cryogenics(n, rng):
    L_vap = 199000.0  # J/kg, latent heat of vaporization for liquid nitrogen
    temperature = rng.uniform(70, 85, n)
    pressure = rng.uniform(95000, 110000, n)
    heat_load = rng.uniform(40, 60, n)
    boil_off_rate = heat_load / L_vap + rng.normal(0, 1e-6, n)
    return pd.DataFrame({"temperature": temperature, "pressure": pressure, "heat_load": heat_load,
                         "boil_off_rate": boil_off_rate})


def dom_thermodynamics(n, rng):
    T = 400 + rng.normal(0, 5, n)
    P = rng.uniform(2e5, 5e5, n)
    rho = P / (287.05 * T)
    enthalpy = 1005 * T
    return pd.DataFrame({"temperature": T, "pressure": P, "density": rho, "enthalpy": enthalpy})


def dom_robotics(n, rng):
    torque = rng.uniform(5, 50, n)
    angular_velocity = rng.uniform(0.5, 5.0, n)
    power = torque * angular_velocity
    joint_angle = rng.uniform(-1.5, 1.5, n)
    return pd.DataFrame({"joint_torque": torque, "angular_velocity": angular_velocity,
                         "power": power, "joint_angle": joint_angle})


def dom_materials(n, rng):
    E = np.full(n, 200e9)
    yield_strength = rng.uniform(400e6, 450e6, n)
    tensile_strength = yield_strength * 1.3
    poisson_ratio = np.full(n, 0.30)
    return pd.DataFrame({"elastic_modulus": E, "yield_strength": yield_strength,
                         "tensile_strength": tensile_strength, "poisson_ratio": poisson_ratio})


DOMAINS = {
    "ideal_gas": dom_ideal_gas,
    "beam_bending": dom_beam_bending,
    "orbital_mechanics": dom_orbital,
    "electrical_circuit": dom_electrical,
    "projectile_motion": dom_projectile,
    "acoustics": dom_acoustics,
    "electromagnetics": dom_electromagnetics,
    "geomechanics": dom_geomechanics,
    "biomechanics": dom_biomechanics,
    "plasma_physics": dom_plasma,
    "chemical_reactor": dom_chemical_reactor,
    "hydrodynamics": dom_hydrodynamics,
    "meteorology": dom_meteorology,
    "tribology": dom_tribology,
    "aeroelasticity": dom_aeroelasticity,
    "cryogenics": dom_cryogenics,
    "thermodynamics": dom_thermodynamics,
    "robotics": dom_robotics,
    "materials_science": dom_materials,
}

# ── Corruption types, parameterized by severity in [0, 1] ───────────────────
# severity=1.0 is blatant (the kind of thing any check should catch),
# severity near 0 is deliberately subtle (the honest edge of detectability).

def corrupt_scale_error(df, col, severity, rng):
    """A unit/scale error: factor ranges from a mild 1.05x (subtle) to a
    gross 1000x (blatant, e.g. a full unit-prefix mistake)."""
    factor = 1.0 + severity * 999.0 if rng.random() > 0.5 else 1.0 / (1.0 + severity * 999.0)
    idx = rng.integers(0, len(df))
    df = df.copy()
    df.loc[idx, col] *= factor
    return df, {idx}


def corrupt_single_spike(df, col, severity, rng):
    """A single hallucinated value: from a subtle ~10% bump to a wild 50x spike."""
    idx = rng.integers(0, len(df))
    df = df.copy()
    orig = df.loc[idx, col]
    mult = 1.0 + severity * 49.0
    df.loc[idx, col] = orig * mult if orig != 0 else mult
    return df, {idx}


def corrupt_systematic_drift(df, col, severity, rng):
    """A subtle SYSTEMATIC bias across every row -- from 0.5% (likely
    invisible) to 15% (should be caught) -- simulating a flawed model
    constant, not a one-off error."""
    factor = 1.0 + (0.005 + severity * 0.145)
    df = df.copy()
    df[col] = df[col] * factor
    return df, set(range(len(df)))


def corrupt_cross_variable_swap(df, cols, severity, rng):
    """Internal inconsistency: partially decouple two columns that should
    move together, by blending in independent noise (severity controls how
    much of the real relationship survives vs. how much is replaced by
    unrelated noise)."""
    if len(cols) < 2:
        return df, set()
    df = df.copy()
    idx = rng.integers(0, len(df))
    col = cols[rng.integers(0, len(cols))]
    real = df.loc[idx, col]
    noise_val = real * rng.uniform(0.5, 1.5)
    blended = real * (1 - severity) + noise_val * severity
    df.loc[idx, col] = blended
    return df, {idx}


def corrupt_near_duplicate(df, severity, rng):
    """Copy a row with noise scaled by severity -- from a near-exact
    duplicate (1e-4 relative noise, very subtle) to loosely similar (5%)."""
    if len(df) < 2:
        return df, set()
    df = df.copy()
    src = rng.integers(0, len(df) - 1)
    dst = src + 1
    noise_scale = 1e-4 + severity * 0.05
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    noise = 1 + rng.normal(0, noise_scale, len(numeric_cols))
    df.loc[dst, numeric_cols] = df.loc[src, numeric_cols].to_numpy() * noise
    return df, {dst}


CORRUPTIONS = ["scale_error", "single_spike", "systematic_drift", "cross_variable", "near_duplicate"]


def run_trial(domain_name, gen_fn, corruption_type, severity, seed, n_rows=80):
    rng = np.random.default_rng(seed)
    df = gen_fn(n_rows, rng)
    cols = list(df.columns)
    target_col = cols[rng.integers(0, len(cols))]

    if corruption_type == "scale_error":
        cdf, truth = corrupt_scale_error(df, target_col, severity, rng)
    elif corruption_type == "single_spike":
        cdf, truth = corrupt_single_spike(df, target_col, severity, rng)
    elif corruption_type == "systematic_drift":
        cdf, truth = corrupt_systematic_drift(df, target_col, severity, rng)
    elif corruption_type == "cross_variable":
        cdf, truth = corrupt_cross_variable_swap(df, cols, severity, rng)
    elif corruption_type == "near_duplicate":
        cdf, truth = corrupt_near_duplicate(df, severity, rng)
    else:
        raise ValueError(corruption_type)

    if not truth:
        return None
    report = validate(cdf)
    caught = flagged(report)
    hit = len(truth & caught) > 0
    return hit


def main():
    severities = [0.02, 0.10, 0.25, 0.50, 0.80, 1.0]
    seeds_per_cell = 3  # trials per (domain, corruption, severity) combination

    total_trials = 0
    results: dict = {}

    print("Running multi-domain adversarial stress test...")
    print(f"Domains: {list(DOMAINS.keys())}")
    print(f"Corruption types: {CORRUPTIONS}")
    print(f"Severities: {severities}")
    print(f"Seeds per cell: {seeds_per_cell}")
    print()

    for domain_name, gen_fn in DOMAINS.items():
        for corruption_type in CORRUPTIONS:
            for severity in severities:
                hits = 0
                n = 0
                for s in range(seeds_per_cell):
                    seed = hash((domain_name, corruption_type, severity, s)) % (2**31)
                    r = run_trial(domain_name, gen_fn, corruption_type, severity, seed)
                    if r is None:
                        continue
                    n += 1
                    total_trials += 1
                    if r:
                        hits += 1
                key = (domain_name, corruption_type, severity)
                results[key] = (hits, n)

    print(f"Total trials run: {total_trials}\n")

    # ── Per corruption-type x severity summary (aggregated across domains) ──
    print("=" * 78)
    print("DETECTION RATE BY CORRUPTION TYPE x SEVERITY (aggregated across all 5 domains)")
    print("=" * 78)
    header = f"{'corruption type':<20}" + "".join(f"{s:>10.2f}" for s in severities)
    print(header)
    for corruption_type in CORRUPTIONS:
        row = f"{corruption_type:<20}"
        for severity in severities:
            hits = sum(results[(d, corruption_type, severity)][0] for d in DOMAINS)
            n = sum(results[(d, corruption_type, severity)][1] for d in DOMAINS)
            pct = 100 * hits / n if n else float("nan")
            row += f"{pct:>9.0f}%"
        print(row)

    print()
    print("=" * 78)
    print("PER-DOMAIN OVERALL DETECTION RATE (all corruption types, all severities)")
    print("=" * 78)
    for domain_name in DOMAINS:
        hits = sum(h for (d, c, sv), (h, n) in results.items() if d == domain_name)
        n = sum(n for (d, c, sv), (h, n) in results.items() if d == domain_name)
        print(f"  {domain_name:<20} {hits}/{n}  ({100*hits/n:.1f}%)")

    print()
    print("=" * 78)
    print("SEVERITY THRESHOLD: lowest severity level with >=50% aggregate detection,")
    print("per corruption type (the honest 'how subtle can it be and still get caught')")
    print("=" * 78)
    for corruption_type in CORRUPTIONS:
        threshold = None
        for severity in severities:
            hits = sum(results[(d, corruption_type, severity)][0] for d in DOMAINS)
            n = sum(results[(d, corruption_type, severity)][1] for d in DOMAINS)
            if n and hits / n >= 0.5:
                threshold = severity
                break
        print(f"  {corruption_type:<20} {'severity >= ' + str(threshold) if threshold is not None else 'NEVER reaches 50% in this sweep'}")

    return results


if __name__ == "__main__":
    main()
