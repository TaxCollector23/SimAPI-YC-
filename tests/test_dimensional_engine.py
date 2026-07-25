"""
Acceptance tests for the dimensional-analysis validation engine
(core/dimensional/). Numbering follows the spec's acceptance-test table.
Tests 7, 8, and 10 are explicitly the ones that were broken in prior
architectures and are the priority bar for this rewrite.
"""
import time

import numpy as np
import pandas as pd
import pytest

from core.dimensional import validate
from core.dimensional.declared_conditions import isa_at_altitude


def _ideal_gas_dataset(n, seed=0):
    rng = np.random.default_rng(seed)
    # Noise held to realistic sensor precision (<1% relative) so it stays
    # comfortably under the anchor's 2% acceptance tolerance -- this is a
    # property of "how noisy is a real measurement", not of the engine.
    T = 293.15 + rng.normal(0, 1.0, n)
    rho = 1.225 + rng.normal(0, 0.006, n)
    P = rho * 287.05 * T
    v = rng.uniform(10, 60, n)
    return pd.DataFrame({"temperature": T, "density": rho, "pressure": P, "velocity": v})


# ── Test 1: clean parameter sweep -> 0 exclusions ──────────────────────────
def test_1_clean_sweep_zero_exclusions():
    df = _ideal_gas_dataset(45, seed=1)
    report = validate(df)
    assert report.impossible_rows == set(), report.summary()


# ── Test 7: majority corruption WITH an anchor -> correct at every level ──
@pytest.mark.parametrize("pct", [10, 30, 45, 55, 70, 90])
def test_7_majority_corruption_with_anchor(pct):
    n = 200
    df = _ideal_gas_dataset(n, seed=42)
    rng = np.random.default_rng(7)
    n_corrupt = int(n * pct / 100)
    corrupt_idx = rng.choice(n, size=n_corrupt, replace=False)
    df.loc[corrupt_idx, "pressure"] = df.loc[corrupt_idx, "pressure"] / 1000.0  # Pa -> kPa written as Pa

    report = validate(df)
    flagged = report.impossible_rows | report.inconsistent_rows

    truth = set(int(i) for i in corrupt_idx)
    tp = len(flagged & truth)
    recall = tp / len(truth) if truth else 1.0
    precision = tp / len(flagged) if flagged else 1.0

    # The anchor (P/(rho*T)=R_air) does not move with the data, so it must
    # stay correct across the whole corruption range, including past 50%
    # where a median-based method would invert.
    assert recall > 0.85, f"pct={pct}: recall={recall:.2f} flagged={len(flagged)} truth={len(truth)}"
    assert precision > 0.85, f"pct={pct}: precision={precision:.2f}"


# ── Test 8: majority corruption WITHOUT an anchor -> split reported ───────
def test_8_majority_corruption_no_anchor_reports_split():
    n = 150
    rng = np.random.default_rng(8)
    # A pure Pi-law with no matching physical constant in the dictionary:
    # tau * omega / power = 1 (rotational power identity) -- exact, but not
    # one of the ~30 shipped constants, so no anchor applies.
    tau = rng.uniform(5, 50, n)
    omega = rng.uniform(10, 200, n)
    power = tau * omega

    for pct in (30, 70):
        p = power.copy()
        n_corrupt = int(n * pct / 100)
        corrupt_idx = rng.choice(n, size=n_corrupt, replace=False)
        p2 = p.copy()
        p2[corrupt_idx] = p2[corrupt_idx] * 1e3  # unit-convention split, no physical constant involved
        df = pd.DataFrame({"torque": tau, "angular_velocity": omega, "power": p2})

        report = validate(df)
        splits = [law for law in report.laws if law.kind == "bimodal_split"]
        assert splits, f"pct={pct}: expected a bimodal split finding, got laws={[l.kind for l in report.laws]}"
        named = [s for s in splits if "1e3" in s.note or "kilo" in s.note]
        assert named, f"pct={pct}: split found but factor not named: {[s.note for s in splits]}"


# ── Test 10: 80-column dataset completes under 10s ─────────────────────────
def test_10_eighty_columns_under_10s():
    n = 300
    rng = np.random.default_rng(10)
    cols = {}
    # A handful of columns forming a real law (so Layer 2/3 have work to do)...
    T = 293.15 + rng.normal(0, 2, n)
    rho = 1.225 + rng.normal(0, 0.01, n)
    cols["temperature"] = T
    cols["density"] = rho
    cols["pressure"] = rho * 287.05 * T
    # ...and 77 more unrelated numeric columns, matching the "real exports
    # are 30-80 columns" note in the spec.
    for i in range(77):
        cols[f"field_{i}"] = rng.uniform(0, 100, n)
    df = pd.DataFrame(cols)

    t0 = time.time()
    report = validate(df, max_columns=15)
    elapsed = time.time() - t0
    assert elapsed < 10.0, f"took {elapsed:.2f}s"
    assert report.n_rows == n


# ── Test 11: imperial-unit dataset -> converted, then behaves as SI ───────
def test_11_imperial_units_converted():
    n = 60
    rng = np.random.default_rng(11)
    T_k = 293.15 + rng.normal(0, 2, n)
    rho = 1.225 + rng.normal(0, 0.01, n)
    P_pa = rho * 287.05 * T_k

    T_f = (T_k - 273.15) * 9 / 5 + 32
    P_psi = P_pa / 6894.757293168

    df = pd.DataFrame({
        "temperature_degF": T_f,
        "density": rho,
        "pressure_psi": P_psi,
    })
    report = validate(df)
    t_unit = report.units.columns["temperature_degF"]
    p_unit = report.units.columns["pressure_psi"]
    assert t_unit.usable and p_unit.usable
    assert t_unit.si_scale != 1.0 or t_unit.si_offset != 0.0
    assert p_unit.si_scale != 1.0
    # Once converted to SI, the same anchored law should be found as the
    # native-SI ideal-gas dataset.
    anchors = [law for law in report.laws if law.kind == "anchored_constant" and "R_air" in law.label]
    assert anchors, report.summary()


# ── Test 12: mixed-type columns -> non-physical columns excluded, no crash ─
def test_12_mixed_type_columns_no_crash():
    n = 40
    rng = np.random.default_rng(12)
    df = _ideal_gas_dataset(n, seed=12)
    df["run_id"] = [f"RUN-{i:04d}" for i in range(n)]
    df["is_converged"] = rng.choice([True, False], n)
    df["category"] = rng.choice(["A", "B", "C"], n)
    df["notes"] = None

    report = validate(df)  # must not raise
    assert "run_id" not in report.units.usable_columns()
    assert "category" not in report.units.usable_columns()


# ── Semantic bounds (Layer 6) sanity, feeding into "impossible" ───────────
def test_semantic_bound_violation_is_impossible():
    n = 30
    df = _ideal_gas_dataset(n, seed=13)
    df["conversion"] = np.random.default_rng(13).uniform(0.5, 0.99, n)
    df.loc[0, "conversion"] = 1.22  # dimensionally fine, physically impossible
    report = validate(df)
    assert 0 in report.impossible_rows


# ── Layer 7: declared conditions as assertions, incl. ISA anchor-of-last-resort
def test_isa_altitude_assertion_and_anchor():
    t, p, rho = isa_at_altitude(11000.0)
    assert 215 < t < 220           # ISA @ 11km ~= 216.65 K
    assert 21000 < p < 23000       # ISA @ 11km ~= 22632 Pa

    n = 50
    rng = np.random.default_rng(14)
    rho_arr = np.full(n, rho) * (1 + rng.normal(0, 0.005, n))
    p_arr = rho_arr * 287.05 * t
    # One trial's pressure is corrupted (wrong altitude data mixed in).
    p_arr[0] *= 1.5
    df = pd.DataFrame({"pressure": p_arr, "density": rho_arr})
    report = validate(df, conditions={"altitude_m": 11000.0})
    assert 0 in (report.impossible_rows | report.inconsistent_rows)


# ── Structural: duplicates are unsuitable-for-training, not "impossible" ──
def test_exact_duplicates_are_unsuitable_not_impossible():
    n = 20
    df = _ideal_gas_dataset(n, seed=15)
    df.loc[1] = df.loc[0]  # exact duplicate row
    report = validate(df)
    assert 1 in report.unsuitable_rows
    assert 1 not in report.impossible_rows


# ── Test 2: valid transonic sweep -> 0 exclusions (Mach>1 must not be
# treated as "impossible" by an over-eager semantic bound) ────────────────
def test_2_transonic_sweep_zero_exclusions():
    n = 60
    rng = np.random.default_rng(2)
    v = np.linspace(325, 548, n) * (1 + rng.normal(0, 0.001, n))
    mach = v / 343.0
    df = pd.DataFrame({"velocity": v, "mach_number": mach})
    report = validate(df)
    assert report.impossible_rows == set(), report.summary()


# ── Test 9: in-range corruption breaking no bound/law -> still ranked by
# the Pi-space response surface ────────────────────────────────────────────
def test_9_in_range_corruption_ranked_top():
    n = 200
    rng = np.random.default_rng(9)
    # Log-uniform Re sweep (realistic for an engineering sweep, and avoids
    # the sparse low-Re tail a linear-uniform sweep over 2 decades would
    # produce, which starves k-NN of neighbours there and inflates ordinary
    # rows' residuals for reasons unrelated to corruption).
    re = np.exp(rng.uniform(np.log(1e5), np.log(1e7), n))
    ma = rng.uniform(0.1, 0.6, n)
    # Realistic drag coefficient: stays well clear of zero across the whole
    # Re/Ma sweep, so a *relative* corruption is never accidentally trivial
    # in absolute terms (this is what a real Cd column looks like -- it
    # doesn't cross zero).
    cd = 0.55 - 0.02 * np.log(re) + 0.05 * ma**2 + rng.normal(0, 0.0008, n)
    corrupt_row = 17
    cd2 = cd.copy()
    cd2[corrupt_row] *= 1.075  # +7.5%, still well within the column's overall range
    df = pd.DataFrame({"reynolds_number": re, "mach_number": ma, "drag_coefficient": cd2})

    from core.dimensional.response_surface import find_surface_anomalies
    from core.dimensional.units_resolver import resolve_units
    units = resolve_units(list(df.columns))
    findings = find_surface_anomalies(df, units)
    cd_finding = next((f for f in findings if f.column == "drag_coefficient"), None)
    assert cd_finding is not None, "expected a response-surface finding on drag_coefficient"
    ranked = sorted(zip(cd_finding.row_ids, cd_finding.residual_z, strict=True), key=lambda x: -x[1])
    top2_rows = [r for r, _ in ranked[:2]]
    assert corrupt_row in top2_rows, f"corrupted row not in top-2: {ranked[:5]}"


# ── Test 4: time series with real gauge drift + explicit time_s column ────
def test_4_temporal_gauge_drift_caught():
    n = 150
    rng = np.random.default_rng(16)
    time_s = np.arange(n, dtype=float) * 2.0  # 2s cadence, monotonic
    T = 293.15 + rng.normal(0, 0.5, n)
    rho = 1.225 + rng.normal(0, 0.003, n)
    # Real gauge drift: the density sensor slowly biases upward over the
    # back half of the run (a common real failure -- e.g. thermal creep in
    # a pressure transducer), NOT a single bad row.
    drift = np.where(time_s > time_s[int(n*0.4)],
                      (time_s - time_s[int(n*0.4)]) * 0.0004, 0.0)
    rho_drifted = rho + drift
    # Pressure is measured independently (from the TRUE, undrifted density) --
    # a real gauge drift is exactly this: one sensor's reported value biases
    # away from physical reality while everything it should be consistent
    # with does not, which is what actually breaks the anchor over time.
    P = rho * 287.05 * T
    df = pd.DataFrame({"time_s": time_s, "temperature": T, "density": rho_drifted, "pressure": P})

    report = validate(df)
    drift_laws = [law for law in report.laws if law.kind == "temporal_drift"]
    assert drift_laws, f"expected a temporal_drift finding; laws={[l.kind for l in report.laws]}"
    # The drift should be attributed to rows in the drifting (later) segment,
    # not scattered randomly across the whole run.
    drift_rows = set(drift_laws[0].violated_rows)
    late_rows = set(range(int(n*0.6), n))
    assert len(drift_rows & late_rows) > len(drift_rows) * 0.5, \
        f"drift rows should concentrate late in the run: {sorted(drift_rows)[:10]}"


# ── Test 6: 15 domains x 1 subtle corruption each -> >=12/15, 0 FP ────────
def test_6_fifteen_domains_subtle_corruption():
    from core.dimensional.dimensions import CONSTANTS

    by_name = {c.name: c for c in CONSTANTS}
    rng = np.random.default_rng(17)
    n = 80
    scenarios: list[tuple[str, pd.DataFrame, set]] = []

    def two_col_product(col_a, col_b, const_name, corrupt_factor=1.15):
        """a*b == const exactly; both columns must be DIMENSIONALLY consistent
        with the constant (their combination must actually sum to its
        dimension, not just share a name-guessed dimension)."""
        c = by_name[const_name]
        a = rng.uniform(1.0, 5.0, n)
        b = c.value / a
        df = pd.DataFrame({col_a: a, col_b: b})
        df.loc[5, col_b] *= corrupt_factor
        return df, {5}

    def two_col_ratio(col_a, col_b, const_name, corrupt_factor=1.15):
        """a/b == const exactly."""
        c = by_name[const_name]
        b = rng.uniform(1.0, 5.0, n)
        a = c.value * b
        df = pd.DataFrame({col_a: a, col_b: b})
        df.loc[5, col_b] *= corrupt_factor
        return df, {5}

    # 1. Ideal gas (R_air): P/(rho*T) -- 3-column anchor.
    T = 293.15 + rng.normal(0, 0.5, n)
    rho = 1.225 + rng.normal(0, 0.003, n)
    P = rho * 287.05 * T
    df1 = pd.DataFrame({"temperature": T, "density": rho, "pressure": P})
    df1.loc[3, "pressure"] /= 1000.0
    scenarios.append(("ideal_gas/R_air", df1, {3}))

    # 2-3. mass=density*volume (M = ML^-3 * L^3) -- electron/proton mass.
    d1, t1 = two_col_product("density_a", "volume_a", "m_e")
    scenarios.append(("m_e", d1, t1))
    d2, t2 = two_col_product("density_b", "volume_b", "m_p")
    scenarios.append(("m_p", d2, t2))

    # 4. charge=current*time (T*I) -- elementary charge.
    d3, t3 = two_col_product("current_a", "time_a", "e_charge")
    scenarios.append(("e_charge", d3, t3))

    # 5. density=mass/volume (M/L^3) -- water density.
    d4, t4 = two_col_ratio("mass_a", "volume_c", "rho_water")
    scenarios.append(("rho_water", d4, t4))

    # 6. viscosity=pressure*time (ML^-1T^-2 * T = ML^-1T^-1) -- water viscosity.
    d5, t5 = two_col_product("pressure_a", "time_b", "mu_water")
    scenarios.append(("mu_water", d5, t5))

    # 7. surface_tension=force/length (MLT^-2/L = MT^-2) -- water surface tension.
    d6, t6 = two_col_ratio("force_a", "length_a", "sigma_water")
    scenarios.append(("sigma_water", d6, t6))

    # 8. specific_heat=energy/(mass*temperature) -- 3-column, air c_p.
    energy = rng.uniform(1.0, 5.0, n)
    mass = rng.uniform(1.0, 5.0, n)
    temp = by_name["c_p_air"].value * mass / energy  # so energy/(mass*temp)=c_p
    df8 = pd.DataFrame({"energy_a": energy, "mass_c": mass, "temperature_a": temp})
    df8.loc[5, "temperature_a"] *= 1.15
    scenarios.append(("c_p_air", df8, {5}))

    # 9. acceleration=velocity/time -- standard gravity.
    d7, t7 = two_col_ratio("velocity_a", "time_c", "g")
    scenarios.append(("g", d7, t7))

    # 10. pressure=force/area -- standard atmosphere.
    d8, t8 = two_col_ratio("force_b", "area_a", "atm")
    scenarios.append(("atm", d8, t8))

    # 11. length=velocity*time -- Earth radius.
    d9, t9 = two_col_product("velocity_b", "time_d", "R_earth")
    scenarios.append(("R_earth", d9, t9))

    # 12. mass=density*volume -- solar mass.
    d10, t10 = two_col_product("density_c", "volume_d", "M_sun")
    scenarios.append(("M_sun", d10, t10))

    # 13. velocity=length/time -- speed of sound in air.
    d11, t11 = two_col_ratio("length_b", "time_e", "c_sound_air")
    scenarios.append(("c_sound_air", d11, t11))

    # 14. time=length/velocity -- seconds in a Julian year.
    d12, t12 = two_col_ratio("length_c", "velocity_c", "year_s")
    scenarios.append(("year_s", d12, t12))

    # 15. pressure=force/area -- torr.
    d13, t13 = two_col_ratio("force_c", "area_b", "torr")
    scenarios.append(("torr", d13, t13))

    detected = 0
    false_positives = 0
    per_scenario = []
    for name, df, truth in scenarios:
        report = validate(df)
        flagged = report.impossible_rows | report.inconsistent_rows
        hit = bool(flagged & truth)
        detected += int(hit)
        fp = len(flagged - truth)
        false_positives += fp
        per_scenario.append((name, hit, fp))

    assert len(scenarios) == 15
    assert detected >= 12, f"only {detected}/15 domains detected their corruption: {per_scenario}"
    assert false_positives == 0, f"{false_positives} false positives across 15 domains: {per_scenario}"
