"""Automatic repair layer: duplicate rows, IDs, timestamp ordering, wrapped angles, short NaN gaps."""
import numpy as np
import pandas as pd

from core.repair import analyze


def test_duplicate_rows_dropped():
    df = pd.DataFrame({"velocity": [150, 160, 170], "pressure": [101325, 101300, 101280]})
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)
    report = analyze(df)
    kinds = [p.kind for p in report.proposals]
    assert "duplicate_rows" in kinds
    applied = report.apply(df)
    assert len(applied) == len(df) - 1


def test_missing_and_duplicate_ids_reassigned():
    df = pd.DataFrame({"trial_id": [1, 2, 2, np.nan], "velocity": [150, 151, 152, 153]})
    report = analyze(df)
    kinds = [p.kind for p in report.proposals]
    assert "duplicate_or_missing_ids" in kinds
    applied = report.apply(df)
    assert applied["trial_id"].is_unique
    assert applied["trial_id"].notna().all()


def test_timestamp_ordering_fixed():
    df = pd.DataFrame({"time": [0.0, 2.0, 1.0], "velocity": [150, 151, 152]})
    report = analyze(df)
    kinds = [p.kind for p in report.proposals]
    assert "timestamp_ordering" in kinds
    applied = report.apply(df)
    assert applied["time"].is_monotonic_increasing


def test_wrapped_angles_normalized():
    df = pd.DataFrame({"angle_of_attack": [10.0, 200.0, -190.0], "velocity": [150, 151, 152]})
    report = analyze(df)
    kinds = [p.kind for p in report.proposals]
    assert "wrapped_angles" in kinds
    applied = report.apply(df)
    assert applied["angle_of_attack"].between(-180, 180).all()


def test_short_nan_gap_interpolated_only_when_time_series():
    """Interpolation is ONLY safe on a genuine time series. For a parameter
    sweep (rows are independent experiments) interpolating between adjacent
    rows fabricates values that then pass every downstream physics check --
    exactly the trust breach the module docstring rules out.

    (Was `test_short_nan_gap_interpolated`; it silently exercised the buggy
    interpolate-on-anything behaviour and is now split into two cases so
    both branches are pinned.)
    """
    # A) Time-series input WITH a monotonic time column -> interpolation ok.
    ts = pd.DataFrame({
        "time": [0.0, 1.0, 2.0],
        "pressure": [101325.0, np.nan, 101310.0],
        "velocity": [150.0, 151.0, 152.0],
    })
    report_ts = analyze(ts)
    assert "missing_value_interpolation" in [p.kind for p in report_ts.proposals]
    assert report_ts.apply(ts)["pressure"].notna().all()

    # B) Parameter sweep (no monotonic time col) -> NaN is unrepairable,
    #    NOT silently interpolated to a fabricated number.
    sweep = pd.DataFrame({
        "pressure": [101325.0, np.nan, 101310.0],
        "velocity": [150.0, 151.0, 152.0],
    })
    report_sweep = analyze(sweep)
    assert "missing_value_interpolation" not in [p.kind for p in report_sweep.proposals]
    assert any(u["column"] == "pressure" for u in report_sweep.unrepairable)
    applied = report_sweep.apply(sweep)
    assert pd.isna(applied.loc[1, "pressure"]), "NaN must survive so physics layer flags it"


def test_long_nan_gap_flagged_unrepairable():
    df = pd.DataFrame({
        "time": list(range(12)),  # time series so short-gap logic can run at all
        "pressure": [101325.0] + [np.nan] * 10 + [101310.0],
        "velocity": list(range(12)),
    })
    report = analyze(df)
    assert any(u["column"] == "pressure" for u in report.unrepairable)


def test_clean_data_produces_no_proposals():
    df = pd.DataFrame({"velocity": [150.0, 151.0, 152.0], "pressure": [101325.0, 101300.0, 101310.0]})
    report = analyze(df)
    assert report.proposals == []
    assert report.unrepairable == []


def test_id_column_excluded_from_interpolation():
    """An ID column should be repaired by the ID pass, not corrupted by numeric interpolation."""
    df = pd.DataFrame({"trial_id": [1.0, np.nan, 3.0], "velocity": [150.0, 151.0, 152.0]})
    report = analyze(df)
    applied = report.apply(df)
    assert applied["trial_id"].is_unique
    assert set(applied["trial_id"]) == {1.0, 2.0, 3.0} or applied["trial_id"].is_unique


# ── Trust-boundary regressions ────────────────────────────────────────
# The module docstring: "SimAPI will never silently rewrite a physically
# implausible value." An angle of 190° (aircraft AoA well past stall,
# common radian/degree unit bug) must NOT be silently normalised to
# -170° -- doing so would launder bad data past validation.
def test_repair_never_rewrites_multi_turn_angles():
    """One-turn wraps (200°, -190°) are convention-mismatch — safe to
    normalise. Multi-turn values (720°, 3600°) are almost certainly a
    unit/radian-vs-degree bug or sensor drift; silently normalising
    them to their canonical residue would launder a physically
    implausible value past every downstream check. Those must survive.
    """
    df = pd.DataFrame({"angle_of_attack": [3.0, 200.0, 720.0, 3600.0]})
    report = analyze(df)
    applied = report.apply(df) if report.proposals else df
    # 200° is a convention-mismatch (in the (180, 360] band) -- normalised.
    assert applied.loc[1, "angle_of_attack"] != 200.0
    # 720° and 3600° must survive unchanged so physics catches them.
    assert applied.loc[2, "angle_of_attack"] == 720.0
    assert applied.loc[3, "angle_of_attack"] == 3600.0


# The same invariant for arbitrary numeric columns: a physically
# impossible value (pressure = -50 Pa, T = -10 K) must survive `apply()`
# so the physics layer flags it, not be laundered by interpolation.
def test_repair_leaves_impossible_values_alone():
    df = pd.DataFrame({
        "pressure": [-50.0, 101300.0, 101310.0],
        "temperature": [-10.0, 293.0, 294.0],
    })
    report = analyze(df)
    applied = report.apply(df) if report.proposals else df
    assert applied.loc[0, "pressure"] == -50.0
    assert applied.loc[0, "temperature"] == -10.0
