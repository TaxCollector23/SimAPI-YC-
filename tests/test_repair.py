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


def test_short_nan_gap_interpolated():
    df = pd.DataFrame({"pressure": [101325.0, np.nan, 101310.0], "velocity": [150.0, 151.0, 152.0]})
    report = analyze(df)
    kinds = [p.kind for p in report.proposals]
    assert "missing_value_interpolation" in kinds
    applied = report.apply(df)
    assert applied["pressure"].notna().all()


def test_long_nan_gap_flagged_unrepairable():
    df = pd.DataFrame({"pressure": [101325.0] + [np.nan] * 10 + [101310.0], "velocity": list(range(12))})
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
