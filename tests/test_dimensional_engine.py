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


def test_7b_response_surface_defers_to_anchor_on_shared_columns():
    """Regression test for a real bug found via live testing: before the
    anchor-veto was added, response-surface (which has no external ground
    truth) could get fooled by a majority-corrupted column into flagging
    the CLEAN minority as anomalous -- directly contradicting the anchor's
    own, correct verdict for the same column. Verified live: a clean row
    scored z=752.8 (extremely confident, completely wrong) once >50% of
    the pressure column was corrupted."""
    n = 200
    df = _ideal_gas_dataset(n, seed=42)
    rng = np.random.default_rng(7)
    n_corrupt = int(n * 0.55)
    corrupt_idx = rng.choice(n, size=n_corrupt, replace=False)
    df.loc[corrupt_idx, "pressure"] = df.loc[corrupt_idx, "pressure"] / 1000.0

    report = validate(df)
    flagged = report.impossible_rows | report.inconsistent_rows
    truth = set(int(i) for i in corrupt_idx)
    false_positives = flagged - truth
    assert len(false_positives) == 0, (
        f"response_surface contradicted the anchor's verdict on {len(false_positives)} "
        f"clean row(s): {sorted(false_positives)[:5]}"
    )


def test_7c_tiny_dataset_near_majority_outlier_no_anchor_still_caught():
    """A second, opposite regression: a naive fix for the test above (just
    tightening the response-surface candidate-count cap) broke this case --
    a tiny dataset (n=5) with an obvious, extreme outlier affecting 40% of
    rows and NO anchor available at all (no known physical constant covers
    an arbitrary 'cd' drag-coefficient column here) must still be caught.
    The real fix is the anchor-veto above, not a blanket tighter cap."""
    df = pd.DataFrame([
        {"cd": 0.312, "cl": 0.847, "re": 415000, "ma": 0.044, "p": 101325, "v": 15},
        {"cd": 0.315, "cl": 0.851, "re": 418000, "ma": 0.044, "p": 101800, "v": 15},
        {"cd": 999, "cl": 0.848, "re": 410000, "ma": 0.044, "p": 101200, "v": 15},
        {"cd": 0.308, "cl": 0.839, "re": 421000, "ma": 0.044, "p": 100900, "v": 15},
        {"cd": 999, "cl": 0.855, "re": 409000, "ma": 0.043, "p": 101500, "v": 14.2},
    ])
    report = validate(df)
    flagged = report.impossible_rows | report.unsuitable_rows | report.inconsistent_rows
    assert {2, 4} <= flagged, f"expected rows 2 and 4 (cd=999) flagged, got {flagged}"


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


def test_near_duplicate_with_relative_noise_is_caught():
    """A row copy-pasted with tiny relative noise on every column
    simultaneously (the realistic 'copy-paste block with noise to disguise
    it' corruption pattern) must be caught even when a column is large-
    magnitude -- this is exactly the case the old absolute-decimal
    duplicate bucketing missed (a Reynolds ~1e5 column perturbed by 1e-5
    relative noise moves ~1.0 in absolute terms, well past 6-decimal
    rounding)."""
    n = 30
    df = _ideal_gas_dataset(n, seed=21)
    rng = np.random.default_rng(21)
    # Near-duplicate row: same as row 0, but with a tiny relative
    # perturbation on every column -- disguised, not identical.
    df.loc[1] = df.loc[0] * (1 + rng.normal(0, 1e-5, df.shape[1]))
    report = validate(df)
    assert 1 in report.unsuitable_rows, report.summary()
    assert 1 not in report.impossible_rows


def test_near_duplicate_does_not_fire_on_genuinely_different_rows():
    """A dense, fine-grained sweep must not be mistaken for near-duplicates
    -- false positives here would silently remove legitimate design points."""
    n = 60
    aoa = np.linspace(0, 10, n)
    df = pd.DataFrame({
        "angle_of_attack": aoa,
        "drag_coefficient": 0.02 + 0.001 * aoa + 0.0002 * aoa**2,
        "lift_coefficient": 0.1 * aoa,
        "velocity": np.full(n, 15.0),
    })
    report = validate(df)
    assert report.unsuitable_rows == set(), report.summary()


def test_units_cache_persists_llm_resolution(tmp_path, monkeypatch):
    """A column resolved once via the LLM fallback should be served from
    cache on a second call, without needing another 'network' call --
    this is what makes the LLM fallback function as a real (if informal)
    dictionary extension rather than a repeated re-guess."""
    monkeypatch.setenv("SIMAPI_UNITS_CACHE_PATH", str(tmp_path / "units_cache.json"))
    from core.dimensional.units_cache import get_cached, store, stats

    assert get_cached(["q_dyn"]) == {}
    store({"q_dyn": {"dimension_key": "pressure", "confidence": 0.85, "unit": None}})
    assert get_cached(["q_dyn", "unseen_col"]) == {
        "q_dyn": {"dimension_key": "pressure", "confidence": 0.85, "unit": None}
    }
    s = stats()
    assert s["n_learned_columns"] == 1
    assert s["most_used"][0]["column"] == "q_dyn"


def test_units_cache_avoids_llm_call_for_cached_columns(tmp_path, monkeypatch):
    """llm_resolve_columns must not call the model chain at all for columns
    already in the cache."""
    monkeypatch.setenv("SIMAPI_UNITS_CACHE_PATH", str(tmp_path / "units_cache.json"))
    monkeypatch.setenv("SIMAPI_OPENROUTER_API_KEY", "fake-key-should-never-be-used")
    from core.dimensional import llm_units
    from core.dimensional.units_cache import store

    store({"q_dyn": {"dimension_key": "pressure", "confidence": 0.85, "unit": None}})

    def _boom(*a, **kw):
        raise AssertionError("must not call the model chain for a fully-cached column set")
    monkeypatch.setattr(llm_units, "_call_model", _boom)

    result = llm_units.llm_resolve_columns(["q_dyn"])
    assert result == {"q_dyn": {"dimension_key": "pressure", "confidence": 0.85, "unit": None}}


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


# ── Test 4b: sub-threshold gauge drift is caught by continuous residual ───
# The base law only flags rows with >=2% deviation as violations; a slow ramp
# that never crosses that bar would previously produce zero residual variation
# in the drift detector (residual = 1.0 everywhere) and go undetected. The
# continuous per-row reconstruction from stored exponents should catch it.
def test_4b_subthreshold_temporal_drift_caught():
    n = 200
    rng = np.random.default_rng(23)
    time_s = np.arange(n, dtype=float)
    T = 293.15 + rng.normal(0, 0.3, n)
    rho = 1.225 + rng.normal(0, 0.002, n)
    # Linear drift capped so no single row exceeds ~1.8% deviation on the anchor.
    drift = np.linspace(0.0, 0.015, n) * rho
    rho_drifted = rho + drift
    P = rho * 287.05 * T
    df = pd.DataFrame({"time_s": time_s, "temperature": T,
                       "density": rho_drifted, "pressure": P})

    report = validate(df)
    drift_laws = [law for law in report.laws if law.kind == "temporal_drift"]
    assert drift_laws, (
        f"expected a temporal_drift finding on sub-threshold drift; "
        f"laws={[l.kind for l in report.laws]}"
    )


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


# ── Test 3: 2-factor design, quadratic Cd(AoA) -> corners NOT flagged ─────
def test_3_two_factor_design_corners_not_flagged():
    """The documented failure of the OLD engine: a 2-factor design where it
    excluded 60/60 valid trials. The corners of a factorial design are the
    extreme (but entirely intentional) combinations -- they must survive."""
    rng = np.random.default_rng(3)
    aoa_levels = np.linspace(0.0, 12.0, 6)
    mach_levels = np.linspace(0.3, 0.8, 5)
    aoa, mach, cd = [], [], []
    for a in aoa_levels:
        for m in mach_levels:
            for _rep in range(2):  # 6 x 5 x 2 = 60 trials
                aoa.append(a)
                mach.append(m)
                # Genuine quadratic response in AoA plus mild Mach dependence.
                cd.append(0.021 + 0.00042 * a**2 + 0.019 * m**2
                          + rng.normal(0, 2e-4))
    df = pd.DataFrame({"angle_of_attack": aoa, "mach": mach, "drag_coefficient": cd})
    assert len(df) == 60

    report = validate(df)
    flagged = report.impossible_rows | report.inconsistent_rows
    assert flagged == set(), (
        f"{len(flagged)} of 60 valid 2-factor trials flagged "
        f"(the old engine's 60/60 failure): {sorted(flagged)[:10]}")

    # Specifically the design corners -- max/min of both factors.
    corners = set(df.index[((df.angle_of_attack == aoa_levels[0]) | (df.angle_of_attack == aoa_levels[-1]))
                           & ((df.mach == mach_levels[0]) | (df.mach == mach_levels[-1]))])
    assert corners, "test setup: expected to identify corner trials"
    assert not (corners & flagged), f"design corners flagged: {sorted(corners & flagged)}"


# ── Test 5: cruise altitude, NO temperature column -> ISA-derived, 1 only ─
def test_5_cruise_altitude_no_temperature_column():
    """Declared conditions are the anchor of last resort: with no temperature
    column there is no P/(rho*T) anchor available from the data itself, so
    the ISA model for the declared altitude has to supply it."""
    n = 80
    rng = np.random.default_rng(5)
    alt = 10668.0  # FL350, a real cruise altitude
    t_isa, p_isa, rho_isa = isa_at_altitude(alt)

    rho = rho_isa * (1 + rng.normal(0, 0.004, n))
    p = rho * 287.05 * t_isa          # consistent with ISA temperature
    v = rng.uniform(230, 250, n)      # cruise TAS, varies freely
    df = pd.DataFrame({"pressure": p, "density": rho, "velocity": v})
    assert not any("temp" in c for c in df.columns), "test setup: no temperature column"

    # Exactly one genuinely corrupted trial.
    df.loc[7, "pressure"] *= 1.6

    report = validate(df, conditions={"altitude_m": alt})
    flagged = report.impossible_rows | report.inconsistent_rows
    assert 7 in flagged, f"the one true corruption was missed; flagged={sorted(flagged)}"
    assert flagged == {7}, f"expected exactly 1 finding, got {sorted(flagged)}"


# ── "Unsuitable for training": the class the spec says barely exists ──────
def test_design_space_gap_reported_as_dataset_level_not_row_exclusions():
    n = 120
    rng = np.random.default_rng(20)
    # A deliberate void: AoA is swept 0-4 deg and 12-16 deg, never between.
    low = rng.uniform(0.0, 4.0, n // 2)
    high = rng.uniform(12.0, 16.0, n // 2)
    aoa = np.concatenate([low, high])
    df = pd.DataFrame({
        "angle_of_attack": aoa,
        "drag_coefficient": 0.021 + 0.00042 * aoa**2 + rng.normal(0, 1e-4, n),
    })
    report = validate(df)
    gaps = [s for s in report.suitability if s.kind == "design_space_gap"]
    assert gaps, f"expected a coverage gap; got {[s.kind for s in report.suitability]}"
    assert any("angle_of_attack" in s.columns for s in gaps)
    # Crucially: a coverage gap must NOT translate into row exclusions.
    assert report.impossible_rows == set()
    assert report.inconsistent_rows == set()


def test_feature_target_leakage_detected():
    n = 60
    rng = np.random.default_rng(21)
    lift = rng.uniform(100, 900, n)
    df = pd.DataFrame({
        "lift_force": lift,
        "lift_force_kn": lift / 1000.0,  # the target, rescaled = pure leakage
        "velocity": rng.uniform(10, 60, n),
    })
    report = validate(df)
    leaks = [s for s in report.suitability if s.kind == "feature_target_leakage"]
    assert leaks, f"expected leakage finding; got {[s.kind for s in report.suitability]}"
    assert {"lift_force", "lift_force_kn"} == set(leaks[0].columns)


def test_regime_imbalance_detected():
    n = 200
    rng = np.random.default_rng(22)
    # 95% of the campaign sits at low AoA; the stall regime is barely sampled.
    aoa = np.concatenate([rng.uniform(0, 2, 190), rng.uniform(14, 18, 10)])
    df = pd.DataFrame({
        "angle_of_attack": aoa,
        "drag_coefficient": 0.021 + 0.00042 * aoa**2 + rng.normal(0, 1e-4, n),
    })
    report = validate(df)
    imbalance = [s for s in report.suitability if s.kind == "regime_imbalance"]
    assert imbalance, f"expected imbalance; got {[s.kind for s in report.suitability]}"


def test_suppressions_are_reported_with_reasons():
    """A validator that hides what it chose not to run cannot be audited."""
    n = 40
    df = _ideal_gas_dataset(n, seed=23)
    df["run_id"] = [f"RUN-{i:04d}" for i in range(n)]
    df["mystery_quantity_xyz"] = np.random.default_rng(23).uniform(1, 5, n)

    report = validate(df)
    assert report.suppressions, "no suppressions recorded"
    joined = " ".join(report.suppressions)
    assert "run_id" in joined, f"non-numeric column not accounted for: {report.suppressions}"
    assert "mystery_quantity_xyz" in joined, f"unresolved column not accounted for: {report.suppressions}"
    # Each entry must say WHY, not just what.
    for s in report.suppressions:
        assert len(s) > 40 and ":" in s, f"suppression lacks a reason: {s!r}"


# ── The design-space boundary guard must not become a blind spot ──────────
def test_boundary_guard_still_catches_interior_corruption():
    """The guard added for Test 3 suppresses Layer 5 where k-NN extrapolates
    (the edge of the sampled design space). Verify it did not simply switch
    Layer 5 off: on a well-sampled sweep an INTERIOR corruption is still
    caught, so what the guard removed is the boundary rows, not the detector."""
    n = 400
    rng = np.random.default_rng(24)
    re = np.exp(rng.uniform(np.log(1e4), np.log(1e6), n))
    mach = rng.uniform(0.2, 0.8, n)
    cd = 0.05 + 0.02 * np.log10(re) / 6.0 + 0.03 * mach**2 + rng.normal(0, 2e-4, n)
    df = pd.DataFrame({"reynolds_number": re, "mach": mach, "drag_coefficient": cd})

    # An interior row: mid-range in BOTH factors, so its neighbourhood
    # genuinely surrounds it and the guard does not apply.
    interior = df.index[
        (df.reynolds_number > np.quantile(re, 0.4)) & (df.reynolds_number < np.quantile(re, 0.6))
        & (df.mach > np.quantile(mach, 0.4)) & (df.mach < np.quantile(mach, 0.6))
    ]
    assert len(interior) > 0, "test setup: expected interior rows"
    victim = int(interior[0])
    df.loc[victim, "drag_coefficient"] *= 1.075  # the spec's +7.5%, in-range

    report = validate(df)
    flagged = report.impossible_rows | report.inconsistent_rows
    assert victim in flagged, (
        f"interior corruption missed -- the boundary guard has over-suppressed "
        f"Layer 5; flagged={sorted(flagged)}")


def test_layer5_sensitivity_limit_on_coarse_replicated_grid_is_documented():
    """Honest boundary, measured rather than assumed.

    On a COARSE REPLICATED factorial grid (few discrete levels, several reps
    per cell) Layer 5 is materially less sensitive than on a well-sampled
    sweep: the k nearest neighbours span whole cells, so the local median
    carries the response's curvature as approximation error, which inflates
    the MAD used to normalise and depresses the z-score of a real anomaly.
    Measured here: a genuine +30% Cd corruption reaches only z=2.7, under the
    z>4 threshold, so it is not reported.

    This is the same deterministic-data effect the spec flags as a source of
    false positives, appearing here as a false negative. It is pinned as a
    test so the limit stays visible and tracked instead of being discovered
    in the field. On designs like this, detection rests on Layers 2/3/4
    (exact laws and anchors), which do not depend on sampling density.

    A local linear fit was tried as a fix -- it cancels the gradient and does
    lift sensitivity -- but it regressed acceptance Test 3 (design corners
    became false positives again), so it was reverted rather than tuned.
    """
    rng = np.random.default_rng(24)
    aoa_levels = np.linspace(0.0, 12.0, 6)
    mach_levels = np.linspace(0.3, 0.8, 5)
    aoa, mach, cd = [], [], []
    for a in aoa_levels:
        for m in mach_levels:
            for _rep in range(4):
                aoa.append(a)
                mach.append(m)
                cd.append(0.021 + 0.00042 * a**2 + 0.019 * m**2 + rng.normal(0, 2e-4))
    df = pd.DataFrame({"angle_of_attack": aoa, "mach": mach, "drag_coefficient": cd})
    interior = df.index[(df.angle_of_attack == aoa_levels[2]) & (df.mach == mach_levels[2])]
    victim = int(interior[0])
    df.loc[victim, "drag_coefficient"] *= 1.30

    report = validate(df)
    flagged = report.impossible_rows | report.inconsistent_rows
    # Documenting the limit: the corruption is missed. What must NOT happen is
    # the engine inventing findings on the valid rows in its place.
    assert victim not in flagged, (
        "Layer 5 sensitivity on coarse replicated grids has IMPROVED -- this test "
        "pins a known limit; tighten or remove it now that it holds.")
    assert len(flagged) <= 1, f"valid grid rows falsely flagged: {sorted(flagged)}"


def test_report_states_the_known_impossible_boundary():
    """Stating this boundary explicitly is what makes the rest credible."""
    from core.dimensional.engine import KNOWN_IMPOSSIBLE
    report = validate(_ideal_gas_dataset(30, seed=25))
    text = report.summary()["known_impossible"]
    assert text == KNOWN_IMPOSSIBLE
    assert "turbulence model" in text
    assert "does not mean the physics is right" in text


# ── Regression: tiny hand-pasted playground datasets must not go silent ────
def test_small_playground_dataset_catches_obvious_outlier():
    """A 5-row dataset with one wildly-wrong drag coefficient (999.0 among
    values near 0.31) is exactly what a first-time user pastes into the
    playground. Response-surface k-NN needs >= 20 rows and silently no-ops
    below that -- this pins the small-n fallback (a global robust-z check
    within the column, no covariates needed) that catches it anyway."""
    df = pd.DataFrame({
        "cd": [0.312, 0.315, 999.0, 0.308, 0.320],
        "cl": [0.847, 0.851, 0.848, 0.839, 0.855],
        "re": [415000, 418000, 410000, 421000, 409000],
        "ma": [0.044, 0.044, 0.044, 0.044, 0.043],
        "p":  [101325, 101800, 101200, 100900, 101500],
        "v":  [15.0, 15.0, 15.0, 15.0, 14.2],
    })
    report = validate(df)
    flagged = report.impossible_rows | report.inconsistent_rows
    assert 2 in flagged, f"the 999.0 cd row was not caught; report={report.summary()}"
    assert len(flagged) == 1, f"clean rows were falsely flagged: {sorted(flagged)}"


def test_small_dataset_no_false_positives_on_clean_rows():
    """Same shape as above with the corrupted row removed -- must report
    nothing. A small-n fallback that catches real outliers but also flags
    ordinary rows would be worse than the silence it replaces."""
    df = pd.DataFrame({
        "cd": [0.312, 0.315, 0.308, 0.320],
        "cl": [0.847, 0.851, 0.839, 0.855],
        "re": [415000, 418000, 421000, 409000],
        "ma": [0.044, 0.044, 0.044, 0.043],
        "p":  [101325, 101800, 100900, 101500],
        "v":  [15.0, 15.0, 15.0, 14.2],
    })
    report = validate(df)
    assert report.impossible_rows == set()
    assert report.inconsistent_rows == set()


def test_sparse_optional_column_does_not_flag_every_row():
    """A column present in a minority of rows (an optional per-trial field)
    must not make every OTHER row look like it has a missing/corrupted
    value. Regression for a real bug: one row with an extra optional field
    caused all 5 rows to be flagged impossible for 'NaN' in that column."""
    rows = [
        {"stress": 245e6, "strain": 0.00196, "elastic_modulus": 125e9, "damping_ratio": 0.043},
        {"stress": 251e6, "strain": 0.00201, "elastic_modulus": 125e9, "damping_ratio": 0.044},
        {"stress": 248e6, "strain": 0.00198, "elastic_modulus": 125e9, "damping_ratio": 0.043},
        {"stress": 244e6, "strain": 0.00250, "elastic_modulus": 125e9, "damping_ratio": 0.043},
        {"stress": 248e6, "strain": 0.00198, "elastic_modulus": 125e9, "stress_concentration": 0.85},
    ]
    df = pd.DataFrame(rows)
    report = validate(df)
    # Row 4 is missing damping_ratio, which IS populated in 4/5 rows (a
    # real, dense field) -- that's a legitimate finding.
    assert report.impossible_rows == {4}
    # The other four rows must not be flagged just because they lack the
    # sparse, 1-row-only stress_concentration field.
    assert not ({0, 1, 2, 3} & report.impossible_rows)


def test_definitional_nonnegative_quantity_bound():
    """Turbulent kinetic energy is a variance-derived quantity -- negative
    is impossible by definition, same category as mass/density already in
    SEMANTIC_BOUNDS. No statistical method or anchor is needed for this."""
    df = pd.DataFrame({
        "velocity": [10.2, 9.8, 10.5],
        "turbulent_kinetic_energy": [0.12, 0.11, -0.05],
    })
    report = validate(df)
    assert 2 in report.impossible_rows
