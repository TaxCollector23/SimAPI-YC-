"""
SimAPI training-data-quality benchmark.

Measures how much SimAPI's exclusions improve a downstream surrogate model when
the training data is corrupted. Multi-seed methodology with error bars, two model
families (robust GBT + data-hungry MLP), and exclusion precision/recall vs the
known corruption ground truth.

    python -m benchmark.run_benchmark

Physics constants are kept consistent with PhysicsValidator's defaults so that
CLEAN data passes the cross-variable checks and only injected corruptions fire.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.physics_validator import PhysicsValidator, SimulationType  # noqa: E402

# Physics constants (must match PhysicsValidator defaults so clean data is consistent).
RHO, MU, L, C_SOUND, R_AIR = 1.225, 1.8e-5, 0.5, 343.0, 287.05
CONDITIONS = {"density": RHO, "viscosity": MU, "length_scale": L}

FEATURES = ["velocity", "reynolds_number", "mach_number", "lift_coefficient",
            "pressure", "temperature", "density"]
TARGET = "drag_coefficient"


# ── Synthetic data ───────────────────────────────────────────────────────────────
def gen(n: int) -> pd.DataFrame:
    """Physically self-consistent aerodynamics trials with a learnable cd target."""
    v = np.random.uniform(12.0, 18.0, n)
    temperature = 293.15 + np.random.normal(0, 0.8, n)
    density = RHO + np.random.normal(0, 0.004, n)
    reynolds = density * v * L / MU                      # Re = ρvL/μ  (consistent)
    mach = v / C_SOUND                                   # Ma = v/c    (consistent)
    lift = 0.84 + 0.012 * (v - 15) + np.random.normal(0, 0.004, n)
    pressure = density * R_AIR * temperature             # P = ρRT     (gas law holds)
    drag = (0.31 + 0.007 * (v - 15) + 2.2e-8 * (reynolds - reynolds.mean())
            + 0.04 * (lift - 0.84) + np.random.normal(0, 0.0015, n))
    return pd.DataFrame({
        "velocity": v, "reynolds_number": reynolds, "mach_number": mach,
        "lift_coefficient": lift, "pressure": pressure, "temperature": temperature,
        "density": density, "drag_coefficient": drag,
    })


def inject_corruptions(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, set]]:
    """Inject the five corruption categories; return (corrupted, ground-truth map)."""
    df = df.reset_index(drop=True)
    n = len(df)
    half = n // 2
    log: dict[str, set] = {k: set() for k in
                           ("solver_divergence", "unit_conversion", "sensor_drift",
                            "copy_paste", "cross_variable")}
    first = np.arange(0, half)
    rng = np.random.default_rng(np.random.randint(0, 1_000_000))

    def pick(frac):
        k = max(1, int(n * frac))
        return rng.choice(first, size=min(k, len(first)), replace=False)

    # Solver divergence: drag jumps out of its physical envelope (finite, so it
    # pollutes training) but not so extreme that a tree trivially isolates it.
    for i in pick(0.05):
        df.at[i, "drag_coefficient"] = rng.uniform(3.6, 4.8)   # just past the plausibility bound
        df.at[i, "lift_coefficient"] = rng.uniform(4.0, 6.0)
        log["solver_divergence"].add(int(i))
    # Unit conversion: pressure logged in kPa instead of Pa.
    for i in pick(0.04):
        if i in log["solver_divergence"]:
            continue
        df.at[i, "pressure"] = df.at[i, "pressure"] / 1000.0
        log["unit_conversion"].add(int(i))
    # Cross-variable: Reynolds inconsistent with velocity.
    for i in pick(0.04):
        if any(i in log[c] for c in ("solver_divergence", "unit_conversion")):
            continue
        df.at[i, "reynolds_number"] = df.at[i, "reynolds_number"] * rng.uniform(1.7, 2.2)
        log["cross_variable"].add(int(i))
    # Copy-paste block: a contiguous run duplicated from its first row (perturbed).
    blk = max(5, int(n * 0.025))
    start = int(rng.integers(5, max(6, half - blk)))
    for j in range(start + 1, start + blk):
        df.iloc[j] = df.iloc[start] * (1 + np.random.normal(0, 1e-5, df.shape[1]))
        log["copy_paste"].add(int(j))
    # Sensor drift: monotonic +8% creep on velocity over the second half.
    drift = np.linspace(0.0, 0.08, n - half)
    df.loc[half:, "velocity"] = df.loc[half:, "velocity"].values * (1 + drift)
    for i in range(half, n):
        log["sensor_drift"].add(int(i))
    return df, log


def clean_with_simapi(df: pd.DataFrame):
    """Run the physics validator; return (cleaned_df, excluded_index_set)."""
    report = PhysicsValidator().validate(
        df.reset_index(drop=True), SimulationType.AERODYNAMICS, CONDITIONS,
        max_exclusions=10 * len(df),
    )
    excluded = {int(e.trial_index) for e in report.exclusions}
    cleaned = df.reset_index(drop=True)
    cleaned = cleaned[~cleaned.index.isin(excluded)]
    return cleaned, excluded


# ── Model training ───────────────────────────────────────────────────────────────
def train_eval(train_df: pd.DataFrame, test_df: pd.DataFrame, model_type: str) -> dict:
    Xtr = train_df[FEATURES].replace([np.inf, -np.inf], np.nan)
    ytr = train_df[TARGET].replace([np.inf, -np.inf], np.nan)
    keep = ytr.notna()                                   # can't train on NaN targets
    Xtr, ytr = Xtr[keep], ytr[keep]
    Xtr = Xtr.fillna(Xtr.median())
    Xte = test_df[FEATURES].fillna(Xtr.median())
    yte = test_df[TARGET].values

    if model_type == "mlp":
        sc = StandardScaler().fit(Xtr)
        Xtr, Xte = sc.transform(Xtr), sc.transform(Xte)
        model = MLPRegressor(hidden_layer_sizes=(64, 32), max_iter=600,
                             early_stopping=True, random_state=0)
    else:
        model = GradientBoostingRegressor(n_estimators=150, max_depth=3, random_state=0)
    model.fit(Xtr, ytr.values)
    pred = model.predict(Xte)
    mae = mean_absolute_error(yte, pred)
    mape = float(np.mean(np.abs((yte - pred) / yte)) * 100)
    return {"mae": mae, "mape": mape}


def _prec_recall(excluded: set, log: dict[str, set]) -> dict:
    corrupted = set().union(*log.values())
    tp = len(excluded & corrupted)
    precision = tp / len(excluded) if excluded else 0.0
    recall = tp / len(corrupted) if corrupted else 0.0
    per_cat = {c: (len(excluded & idx) / len(idx) if idx else 0.0) for c, idx in log.items()}
    return {"precision": precision, "recall": recall, "n_corrupted": len(corrupted),
            "n_excluded": len(excluded), "per_category_recall": per_cat}


# ── Benchmark ────────────────────────────────────────────────────────────────────
def run_benchmark(seeds=(42, 123, 456, 789, 1337)) -> dict:
    t0 = time.time()
    results = {"gbt": [], "mlp": []}
    pr_runs = []
    for seed in seeds:
        np.random.seed(seed)
        clean = gen(2000)
        train_pool, test = train_test_split(clean, test_size=0.30, random_state=seed)
        corrupted, log = inject_corruptions(train_pool.copy())
        cleaned, excluded = clean_with_simapi(corrupted)
        pr_runs.append(_prec_recall(excluded, log))

        for model_type in ("gbt", "mlp"):
            r_corrupted = train_eval(corrupted, test, model_type)
            r_simapi = train_eval(cleaned, test, model_type)
            results[model_type].append({
                "mae_improvement": (r_corrupted["mae"] - r_simapi["mae"]) / r_corrupted["mae"] * 100,
                "mape_improvement": (r_corrupted["mape"] - r_simapi["mape"]) / r_corrupted["mape"] * 100,
            })
        print(f"  seed {seed}: excluded {pr_runs[-1]['n_excluded']}/{pr_runs[-1]['n_corrupted']} corrupted "
              f"(recall {pr_runs[-1]['recall']*100:.0f}%, precision {pr_runs[-1]['precision']*100:.0f}%)")

    summary = {"seeds": list(seeds), "models": {}}
    print(f"\n── Results (mean ± std over {len(seeds)} seeds) ──")
    for model_type, runs in results.items():
        mape = [r["mape_improvement"] for r in runs]
        mae = [r["mae_improvement"] for r in runs]
        summary["models"][model_type] = {
            "mape_improvement_mean": round(float(np.mean(mape)), 2),
            "mape_improvement_std": round(float(np.std(mape)), 2),
            "mae_improvement_mean": round(float(np.mean(mae)), 2),
            "mae_improvement_std": round(float(np.std(mae)), 2),
        }
        print(f"  {model_type.upper()} MAPE improvement: {np.mean(mape):5.1f}% ± {np.std(mape):.1f}%  |  "
              f"MAE: {np.mean(mae):5.1f}% ± {np.std(mae):.1f}%")

    prec = float(np.mean([p["precision"] for p in pr_runs]))
    rec = float(np.mean([p["recall"] for p in pr_runs]))
    cat = {c: round(float(np.mean([p["per_category_recall"][c] for p in pr_runs])) * 100, 1)
           for c in pr_runs[0]["per_category_recall"]}
    summary["exclusion"] = {"precision": round(prec, 3), "recall": round(rec, 3),
                            "per_category_recall_pct": cat}
    summary["elapsed_s"] = round(time.time() - t0, 1)
    print(f"\n  Exclusion precision {prec*100:.0f}% · recall {rec*100:.0f}%")
    print("  Per-category recall: " + " · ".join(f"{c} {v:.0f}%" for c, v in cat.items()))

    out = Path(__file__).resolve().parent / "results.json"
    out.write_text(json.dumps(summary, indent=2))
    print(f"\n  wrote {out}")
    return summary


if __name__ == "__main__":
    run_benchmark()
