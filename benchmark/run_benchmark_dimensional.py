"""
SimAPI Dimensional-Analysis Engine Benchmark.

Measures core/dimensional/ -- the engine that now authoritatively drives
/v1/validate -- using the SAME dataset generator and corruption-injection
methodology as the legacy APIE benchmark (benchmark/run_benchmark.py), so
the two are directly, fairly comparable.

Two detection tiers are reported, matching the engine's own output classes:
  - "auto-excluded"     = impossible ∪ unsuitable_for_training rows
                           (the engine's most confident tier -- an anchored
                           physical constant violated, or a definitional
                           impossibility. This is what /v1/validate reports
                           as `trials_excluded` / `training_ready`.)
  - "detected (total)"  = auto-excluded ∪ inconsistent rows
                           (adds rows flagged for human review -- the engine
                           is NOT confident enough to auto-exclude these, by
                           design; they're a lower-precision, higher-recall tier.)

Reporting both, rather than collapsing to one number, is the honest way to
represent an engine that deliberately treats "this row is definitely wrong"
and "this row looks suspicious, a human should look" as different things.

Run:
    python -m benchmark.run_benchmark_dimensional
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.dimensional import validate as dimensional_validate

# Reuse the exact dataset generator, corruption injector, ML eval harness,
# and precision/recall scorer from the legacy benchmark -- same ground truth,
# same corruption categories, same ML-quality methodology. Only the engine
# under test changes.
from benchmark.run_benchmark import (
    CONDITIONS, N_TOTAL, TEST_FRAC, gen, inject_corruptions,
    naive_clean, train_eval, _prec_recall,
)
from sklearn.model_selection import train_test_split


def clean_with_dimensional(df: pd.DataFrame) -> tuple[pd.DataFrame, set, set, float]:
    """Run the dimensional engine. Returns (cleaned_df, auto_excluded, inconsistent, ms)."""
    df = df.reset_index(drop=True)
    t0 = time.time()
    report = dimensional_validate(df, conditions=CONDITIONS)
    ms = (time.time() - t0) * 1000
    auto_excluded = set(report.impossible_rows) | set(report.unsuitable_rows)
    inconsistent = set(report.inconsistent_rows)
    cleaned = df[~df.index.isin(auto_excluded)]
    return cleaned, auto_excluded, inconsistent, ms


def run_benchmark(seeds: tuple = (42, 123, 456, 789, 1337)) -> dict:
    print("\nSimAPI Dimensional-Analysis Engine Benchmark")
    print(f"Scale: n≈{int(N_TOTAL*(1-TEST_FRAC)):,} train / {int(N_TOTAL*TEST_FRAC):,} test")
    print("=" * 72)

    t0 = time.time()
    results: dict = {"gbt": [], "mlp": []}
    pr_runs_auto: list = []
    pr_runs_total: list = []
    val_times: list = []

    for seed in seeds:
        np.random.seed(seed)
        clean = gen(N_TOTAL)
        train_pool, test = train_test_split(clean, test_size=TEST_FRAC, random_state=seed)
        corrupted, log = inject_corruptions(train_pool.copy())

        cleaned, auto_excluded, inconsistent, val_ms = clean_with_dimensional(corrupted)
        naive_cleaned = naive_clean(corrupted)
        pr_auto = _prec_recall(auto_excluded, log)
        pr_total = _prec_recall(auto_excluded | inconsistent, log)
        pr_runs_auto.append(pr_auto)
        pr_runs_total.append(pr_total)
        val_times.append(val_ms)

        for model_type in ("gbt", "mlp"):
            r_clean = train_eval(train_pool, test, model_type)
            r_cor   = train_eval(corrupted, test, model_type)
            r_sim   = train_eval(cleaned, test, model_type)
            r_nav   = train_eval(naive_cleaned, test, model_type)
            results[model_type].append({
                "mape_clean": r_clean["mape"], "mape_corrupted": r_cor["mape"],
                "mape_simapi": r_sim["mape"], "mape_naive": r_nav["mape"],
                "mape_improvement": (r_cor["mape"] - r_sim["mape"]) / r_cor["mape"] * 100,
                "naive_improvement": (r_cor["mape"] - r_nav["mape"]) / r_cor["mape"] * 100,
                "simapi_vs_naive": (r_nav["mape"] - r_sim["mape"]) / r_nav["mape"] * 100,
            })

        cat_str = " | ".join(f"{k.replace('_',' ')[:4]} {v*100:.0f}%"
                             for k, v in pr_auto["per_category_recall"].items())
        print(f"  seed {seed}: auto-excl recall {pr_auto['recall']*100:.1f}% prec {pr_auto['precision']*100:.1f}%"
              f"  |  total-detected recall {pr_total['recall']*100:.1f}% prec {pr_total['precision']*100:.1f}%"
              f"  ({val_ms/1000:.2f}s)  [{cat_str}]")

    summary: dict = {
        "engine": "dimensional-analysis",
        "seeds": list(seeds),
        "n_train": int(N_TOTAL * (1 - TEST_FRAC)),
        "n_test": int(N_TOTAL * TEST_FRAC),
        "corruption_rate_pct": 30.2,
        "validation_ms_mean": round(float(np.mean(val_times)), 1),
        "validation_ms_std": round(float(np.std(val_times)), 1),
        "models": {},
    }

    print(f"\n── Results (mean ± std, {len(seeds)} seeds) ──")
    for mt, runs in results.items():
        mape_imp = [r["mape_improvement"] for r in runs]
        vs_naive = [r["simapi_vs_naive"] for r in runs]
        m = {
            "mape_improvement_mean": round(float(np.mean(mape_imp)), 2),
            "mape_improvement_std": round(float(np.std(mape_imp)), 2),
            "mape_corrupted_mean": round(float(np.mean([r["mape_corrupted"] for r in runs])), 4),
            "mape_simapi_mean": round(float(np.mean([r["mape_simapi"] for r in runs])), 4),
            "mape_naive_mean": round(float(np.mean([r["mape_naive"] for r in runs])), 4),
            "mape_clean_mean": round(float(np.mean([r["mape_clean"] for r in runs])), 4),
            "naive_improvement_mean": round(float(np.mean([r["naive_improvement"] for r in runs])), 2),
            "simapi_vs_naive_mean": round(float(np.mean(vs_naive)), 2),
        }
        summary["models"][mt] = m
        print(f"  {mt.upper()} MAPE: corrupted {m['mape_corrupted_mean']:.4f}% → "
              f"naive {m['mape_naive_mean']:.4f}% → dimensional {m['mape_simapi_mean']:.4f}% "
              f"(ceiling {m['mape_clean_mean']:.4f}%)")

    def _summarize(pr_runs, label):
        prec = float(np.mean([p["precision"] for p in pr_runs]))
        rec = float(np.mean([p["recall"] for p in pr_runs]))
        cat = {c: round(float(np.mean([p["per_category_recall"][c] for p in pr_runs])) * 100, 1)
               for c in pr_runs[0]["per_category_recall"]}
        print(f"\n  [{label}] Precision {prec*100:.2f}%  ·  Recall {rec*100:.2f}%")
        print("  Per-category: " + " · ".join(f"{c} {v:.1f}%" for c, v in cat.items()))
        return {"precision": round(prec, 4), "recall": round(rec, 4), "per_category_recall_pct": cat}

    summary["auto_excluded"] = _summarize(pr_runs_auto, "auto-excluded — high confidence, no human review needed")
    summary["total_detected"] = _summarize(pr_runs_total, "total detected — includes flagged-for-review rows")
    summary["elapsed_s"] = round(time.time() - t0, 1)

    print(f"\n  Validation latency: {np.mean(val_times)/1000:.2f}s ± {np.std(val_times)/1000:.2f}s")
    print(f"  Total benchmark: {summary['elapsed_s']}s")

    out = Path(__file__).resolve().parent / "results_dimensional.json"
    out.write_text(json.dumps(summary, indent=2))
    print(f"\n  Wrote {out}")
    return summary


if __name__ == "__main__":
    run_benchmark()
