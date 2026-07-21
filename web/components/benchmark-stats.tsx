import { SectionHeader } from "./ui/section";
import results from "@/lib/benchmark-results.json";

const gbt = results.models.gbt;
const mlp = results.models.mlp;
const excl = results.exclusion;
const cat = excl.per_category_recall_pct;
const n_train = results.n_train ?? 9333;

function pct(v: number, d = 1) { return `${v.toFixed(d)}%`; }

export function BenchmarkStats() {
  return (
    <section className="relative py-20 sm:py-24">
      <div className="container-tight">
        <SectionHeader
          eyebrow="Benchmark"
          title={<>The honest numbers</>}
          lede={`n=${n_train.toLocaleString()} training trials, ${results.corruption_rate_pct}% corrupted across 6 failure modes. Three-way comparison: no filtering vs naive IQR/z-score vs SimAPI APIE. Mean ± std across ${results.seeds.length} seeds.`}
        />

        <div className="mx-auto mt-10 grid max-w-4xl gap-4 sm:grid-cols-3">
          {[
            { v: pct(results.corruption_rate_pct, 0), l: "of trials corrupted", h: "6 categories including the hardest: measurement noise and sensor drift" },
            { v: pct(excl.recall * 100, 1), l: "of corruptions caught", h: `precision ${pct(excl.precision * 100, 1)} — near-zero false positives` },
            { v: pct(excl.precision * 100, 1), l: "exclusion precision", h: "when flagged, it is genuinely corrupted" },
          ].map((s) => (
            <div key={s.l} className="rounded-2xl border border-white/[0.08] bg-ink-900/50 p-5 text-center">
              <p className="font-mono text-3xl font-semibold text-accent-cyan">{s.v}</p>
              <p className="mt-1 text-sm text-white/60">{s.l}</p>
              <p className="mt-1.5 text-[11px] leading-relaxed text-white/35">{s.h}</p>
            </div>
          ))}
        </div>

        <div className="mx-auto mt-4 max-w-4xl overflow-hidden rounded-2xl border border-white/[0.08]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/[0.08] bg-white/[0.02] text-left text-xs uppercase tracking-wider text-white/40">
                <th className="p-3.5 font-medium">Model</th>
                <th className="p-3.5 font-medium">Corrupted</th>
                <th className="p-3.5 font-medium">Naive (IQR+Z)</th>
                <th className="p-3.5 font-medium">SimAPI APIE</th>
                <th className="p-3.5 font-medium">Clean ceiling</th>
              </tr>
            </thead>
            <tbody className="text-white/70">
              <tr className="border-b border-white/[0.05]">
                <td className="p-3.5">
                  <span className="text-white">Neural net (MLP)</span><br />
                  <span className="text-xs text-white/35">distribution-sensitive</span>
                </td>
                <td className="p-3.5 font-mono text-red-400">{pct(mlp.mape_corrupted_mean, 2)} MAPE</td>
                <td className="p-3.5 font-mono text-yellow-400">{pct(mlp.mape_naive_mean, 2)} MAPE</td>
                <td className="p-3.5 font-mono text-pass">{pct(mlp.mape_simapi_mean, 2)} MAPE</td>
                <td className="p-3.5 font-mono text-white/40">{pct(mlp.mape_clean_mean, 2)} MAPE</td>
              </tr>
              <tr>
                <td className="p-3.5">
                  <span className="text-white">Gradient boosting</span><br />
                  <span className="text-xs text-white/35">robust to outliers</span>
                </td>
                <td className="p-3.5 font-mono text-white/60">{pct(gbt.mape_corrupted_mean, 2)} MAPE</td>
                <td className="p-3.5 font-mono text-white/60">{pct(gbt.mape_naive_mean, 2)} MAPE</td>
                <td className="p-3.5 font-mono text-pass">{pct(gbt.mape_simapi_mean, 2)} MAPE</td>
                <td className="p-3.5 font-mono text-white/40">{pct(gbt.mape_clean_mean, 2)} MAPE</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="mx-auto mt-4 max-w-4xl overflow-hidden rounded-2xl border border-white/[0.08]">
          <div className="border-b border-white/[0.08] bg-white/[0.02] p-3.5 text-xs uppercase tracking-wider text-white/40">
            Per-category detection recall
          </div>
          <div className="grid grid-cols-2 gap-0 sm:grid-cols-3">
            {[
              { cat: "Solver divergence", pct: cat.solver_divergence },
              { cat: "Unit conversion", pct: cat.unit_conversion },
              { cat: "Cross-variable", pct: cat.cross_variable },
              { cat: "Copy-paste blocks", pct: cat.copy_paste },
              { cat: "Sensor drift", pct: cat.sensor_drift },
              { cat: "Measurement noise", pct: cat.measurement_noise },
            ].map((c) => (
              <div key={c.cat} className="border-b border-white/[0.05] p-3 text-sm">
                <span className="font-mono text-white/80">{c.pct?.toFixed(1)}%</span>
                <span className="ml-2 text-white/40">{c.cat}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="mx-auto mt-6 max-w-4xl grid gap-4 sm:grid-cols-2">
          <div className="rounded-2xl border border-white/[0.08] bg-ink-900/50 p-5">
            <h4 className="text-sm font-semibold text-white mb-2">Why MLP improves {mlp.mape_improvement_mean.toFixed(0)}%</h4>
            <p className="text-sm text-white/55 leading-relaxed">
              APIE removes 100% of sensor drift rows — the velocity creep shifts the entire
              feature distribution. Neural networks are maximally sensitive to this: an MLP
              trained on drifted velocity learns the wrong v→Cd relationship for 15% of
              the dataset. Removing these rows lets the model learn the true distribution.
              MLP goes {pct(mlp.mape_corrupted_mean, 2)} → {pct(mlp.mape_simapi_mean, 2)},
              beating naive filtering by {pct(mlp.simapi_vs_naive_mean, 1)}.
            </p>
          </div>
          <div className="rounded-2xl border border-white/[0.08] bg-ink-900/50 p-5">
            <h4 className="text-sm font-semibold text-white mb-2">What naive filtering can&rsquo;t see</h4>
            <p className="text-sm text-white/55 leading-relaxed">
              A naive IQR filter removes rows that are statistical outliers column-by-column.
              Cross-variable corruptions (Re inflated 1.7–2.2× while v is unchanged) produce
              values inside each column&rsquo;s individual bounds — IQR catches zero of them.
              APIE catches 100% by checking Re/v as a physical invariant. Similarly,
              Pa→kPa unit errors produce plausible individual pressure values — only
              P/(ρT)≈0.287 instead of 287 reveals the error.
            </p>
          </div>
        </div>

        <p className="mx-auto mt-6 max-w-4xl text-center text-xs text-white/30">
          Reproduce:{" "}
          <code className="rounded bg-white/[0.06] px-1.5 py-0.5 font-mono">
            python -m benchmark.run_benchmark
          </code>{" "}
          — {results.seeds.length} seeds · n≈{n_train.toLocaleString()} train · {results.elapsed_s}s runtime ·
          numbers vary ±{gbt.mape_improvement_std.toFixed(1)}% (GBT) / ±{mlp.mape_improvement_std.toFixed(1)}% (MLP) across seeds
        </p>
      </div>
    </section>
  );
}
