"""Regression tests for numerical robustness on degenerate (constant /
near-constant / zero-variance) columns.

Feeding a constant column into scipy's skew/kurtosis or numpy's correlation
used to emit RuntimeWarnings ("Precision loss ... catastrophic cancellation"
and "invalid value encountered in divide") and return unreliable NaNs. These
tests pin the guarded behaviour: no warning, and a finite, defined result.
"""
import warnings

import numpy as np
import pandas as pd
import pytest

from core.apie import (
    AdaptivePhysicsIntelligenceEngine,
    compute_fingerprint,
    safe_corrcoef,
    safe_kurtosis,
    safe_skew,
)


# ── Unit-level guards ────────────────────────────────────────────────────────
def test_safe_skew_on_constant_is_zero_and_silent():
    s = np.full(100, 3.14159)
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        val = safe_skew(s)
    assert val == 0.0


def test_safe_kurtosis_on_near_constant_is_zero_and_silent():
    rng = np.random.default_rng(0)
    s = np.full(100, 5.0) + rng.normal(0, 1e-15, 100)  # near-constant
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        val = safe_kurtosis(s)
    assert val == 0.0


def test_safe_skew_matches_scipy_on_well_conditioned_data():
    rng = np.random.default_rng(1)
    s = rng.exponential(1.0, 5000)  # genuinely skewed
    from scipy import stats
    assert safe_skew(s) == pytest.approx(float(stats.skew(s)), abs=1e-9)
    assert safe_skew(s) > 0.5  # exponential is right-skewed


def test_safe_corrcoef_on_constant_column_is_zero_and_silent():
    a = np.ones(50)          # zero variance
    b = np.arange(50.0)
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        val = safe_corrcoef(a, b)
    assert val == 0.0


def test_safe_corrcoef_matches_numpy_on_correlated_data():
    rng = np.random.default_rng(2)
    a = rng.normal(0, 1, 500)
    b = 2.0 * a + rng.normal(0, 0.1, 500)
    assert safe_corrcoef(a, b) == pytest.approx(float(np.corrcoef(a, b)[0, 1]), abs=1e-9)


def test_safe_corrcoef_handles_nan_and_length_mismatch():
    a = np.array([1.0, 2.0, np.nan, 4.0])
    b = np.array([2.0, 4.0, 6.0, 8.0])
    assert np.isfinite(safe_corrcoef(a, b))       # pairwise-complete only
    assert safe_corrcoef(np.ones(3), np.ones(5)) == 0.0  # mismatch -> 0.0


# ── Engine-level: no warnings on a fully constant / zero-variance dataset ─────
def _constant_frame(n=60):
    return pd.DataFrame({
        "drag_coefficient": np.full(n, 0.31),
        "lift_coefficient": np.full(n, 0.85),
        "velocity": np.full(n, 15.0),
        "pressure": np.full(n, 101325.0),
        "temperature": np.full(n, 288.15),
        "density": np.full(n, 1.225),
    })


def test_compute_fingerprint_constant_columns_no_warning():
    df = _constant_frame()
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        fp = compute_fingerprint(df, domain="aerodynamics")
    for _col, stats_tuple in fp.col_stats.items():
        skew, kurt = stats_tuple[2], stats_tuple[3]
        assert np.isfinite(skew) and np.isfinite(kurt)


def test_apie_engine_on_constant_columns_no_warning():
    df = _constant_frame()
    engine = AdaptivePhysicsIntelligenceEngine()
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        result = engine.validate(df, domain="aerodynamics")
    # A perfectly constant dataset is physically clean -> nothing impossible.
    assert isinstance(result.excluded_indices, set)


def test_apie_engine_near_constant_columns_no_warning():
    rng = np.random.default_rng(7)
    n = 80
    df = pd.DataFrame({
        "drag_coefficient": np.full(n, 0.31) + rng.normal(0, 1e-14, n),
        "lift_coefficient": np.full(n, 0.85) + rng.normal(0, 1e-14, n),
        "velocity": np.full(n, 15.0),
        "reynolds_number": np.full(n, 4.0e5),
    })
    engine = AdaptivePhysicsIntelligenceEngine()
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        engine.validate(df, domain="aerodynamics")
