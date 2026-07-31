import { SectionHeader } from "./ui/section";
import results from "@/lib/benchmark-results-dimensional.json";

const gbt = results.models.gbt;
const mlp = results.models.mlp;
const auto = results.auto_excluded;
const total = results.total_detected;
const catAuto = auto.per_category_recall_pct;
const catTotal = total.per_category_recall_pct;
const n_train = results.n_train ?? 9333;

function pct(v: number, d = 1) { return `${v.toFixed(d)}%`; }

export function BenchmarkStats() {
  return (
    <section className="relative py-20 sm:py-24">
      <div className="container-tight">
        <SectionHeader
          eyebrow="Benchmark"
          title={<>The honest numbers</>}
          lede={`n=${n_train.toLocaleString()} training trials, ${results.corruption_rate_pct}% corrupted across 6 failure modes. Same dataset generator and corruption injector as the legacy engine's benchmark -- only the engine under test changed. Mean across ${results.seeds.length} seeds.`}
        />

        <div className="mx-auto mt-10 grid max-w-4xl gap-4 sm:grid-cols-3">
          {[
            { v: pct(results.corruption_rate_pct, 0), l: "of trials corrupted", h: "6 categories including the hardest: measurement noise below the local variance floor" },
            { v: pct(auto.recall * 100, 1), l: "auto-excluded (no review needed)", h: `precision ${pct(auto.precision * 100, 1)} -- zero false positives at this tier` },
            { v: pct(total.recall * 100, 1), l: "total detected (incl. flagged for review)", h: `precision ${pct(total.precision * 100, 1)}` },
          ].map((s) => (
            <div key={s.l} className="rounded-2xl border border-white/[0.08] bg-ink-900/50 p-5 text-center">
              <p className="font-mono text-3xl font-semibold text-accent-cyan">{s.v}</p>
              <p className="mt-1 text-sm text-white/60">{s.l}</p>
              <p className="mt-1.5 text-[11px] leading-relaxed text-white/35">{s.h}</p>
            </div>
          ))}
        </div>

        <div className="mx-auto mt-4 max-w-4xl rounded-2xl border border-accent-blue/20 bg-accent-blue/[0.04] p-5 text-sm leading-relaxed text-white/60">
          <strong className="text-white/85">Two tiers, on purpose.</strong> "Auto-excluded" rows violate a
          mathematically verifiable physical law (an anchored constant, a definitional bound) --
          when this engine excludes a row, it isn&rsquo;t a guess. "Flagged for review" rows deviate from
          the learned response surface but don&rsquo;t break a provable law -- the engine surfaces them
          for a human to look at rather than silently deleting data it can&rsquo;t prove is wrong.
        </div>

        <div className="mx-auto mt-4 max-w-4xl overflow-hidden rounded-2xl border border-white/[0.08]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/[0.08] bg-white/[0.02] text-left text-xs uppercase tracking-wider text-white/40">
                <th className="p-3.5 font-medium">Model</th>
                <th className="p-3.5 font-medium">Corrupted</th>
                <th className="p-3.5 font-medium">Naive (IQR+Z)</th>
                <th className="p-3.5 font-medium">Dimensional (auto-excl only)</th>
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
                <td className="p-3.5 font-mono text-white/70">{pct(mlp.mape_simapi_mean, 2)} MAPE</td>
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
        <p className="mx-auto mt-2 max-w-4xl text-xs leading-relaxed text-white/35">
          This table trains only on the <strong>auto-excluded</strong> tier removed -- the flagged-for-review
          rows are deliberately left in, since removing them without a human decision would defeat the
          point of a review tier. On MLP, naive statistical filtering currently beats the auto-excluded-only
          tier on this synthetic benchmark, because naive filtering catches large-magnitude outliers
          (like the solver-divergence spikes) that don&rsquo;t violate any checkable physical law and so aren&rsquo;t
          auto-excluded by design -- they land in the review tier instead. We&rsquo;re not hiding that.
        </p>

        <div className="mx-auto mt-6 max-w-4xl overflow-hidden rounded-2xl border border-white/[0.08]">
          <div className="border-b border-white/[0.08] bg-white/[0.02] p-3.5 text-xs uppercase tracking-wider text-white/40">
            Per-category recall -- auto-excluded vs total detected
          </div>
          <div className="divide-y divide-white/[0.05]">
            {[
              { cat: "Unit conversion (Pa vs kPa)", a: catAuto.unit_conversion, t: catTotal.unit_conversion },
              { cat: "Cross-variable (Re ≠ ρvL/μ)", a: catAuto.cross_variable, t: catTotal.cross_variable },
              { cat: "Measurement noise", a: catAuto.measurement_noise, t: catTotal.measurement_noise },
              { cat: "Solver divergence", a: catAuto.solver_divergence, t: catTotal.solver_divergence },
              { cat: "Sensor drift", a: catAuto.sensor_drift, t: catTotal.sensor_drift },
              { cat: "Copy-paste (near-duplicate rows)", a: catAuto.copy_paste, t: catTotal.copy_paste },
            ].map((c) => (
              <div key={c.cat} className="flex items-center justify-between p-3 text-sm">
                <span className="text-white/70">{c.cat}</span>
                <span className="font-mono text-xs">
                  <span className="text-accent-cyan">{c.a?.toFixed(1)}%</span>
                  <span className="text-white/30"> auto · </span>
                  <span className="text-white/70">{c.t?.toFixed(1)}%</span>
                  <span className="text-white/30"> total</span>
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="mx-auto mt-6 max-w-4xl grid gap-4 sm:grid-cols-2">
          <div className="rounded-2xl border border-white/[0.08] bg-ink-900/50 p-5">
            <h4 className="text-sm font-semibold text-white mb-2">Where it's strongest: anchored constants</h4>
            <p className="text-sm text-white/55 leading-relaxed">
              A Pa→kPa unit error produces individually plausible pressure values -- only
              P/(ρT) ≈ 0.287 instead of 287.05 J/(kg·K) reveals it. This is a physical constant,
              not a statistical pattern, so it doesn&rsquo;t degrade with dataset size or corruption
              fraction. That&rsquo;s why unit-conversion recall stays near {catTotal.unit_conversion?.toFixed(0)}%
              regardless of scale, and is auto-excluded (no human review needed) with zero false positives.
            </p>
          </div>
          <div className="rounded-2xl border border-white/[0.08] bg-ink-900/50 p-5">
            <h4 className="text-sm font-semibold text-white mb-2">Where it's honestly weak: measurement noise</h4>
            <p className="text-sm text-white/55 leading-relaxed">
              {(100 - (catTotal.measurement_noise ?? 100)).toFixed(0)}% of measurement-noise rows are
              missed ({catTotal.measurement_noise?.toFixed(1)}% caught). These are perturbations that
              land within the natural scatter for that specific feature combination -- there's no
              statistical signature to find, because the corrupted value is genuinely indistinguishable
              from a real one at that point in the design space. This is a physical detection limit,
              not a software gap.
            </p>
          </div>
        </div>

        <p className="mx-auto mt-6 max-w-4xl text-center text-xs text-white/30">
          Reproduce:{" "}
          <code className="rounded bg-white/[0.06] px-1.5 py-0.5 font-mono">
            python -m benchmark.run_benchmark_dimensional
          </code>{" "}
          -- {results.seeds.length} seeds · n≈{n_train.toLocaleString()} train · {results.elapsed_s}s runtime ·
          precision does not vary meaningfully across seeds; recall varies by category as shown above
        </p>
      </div>
    </section>
  );
}
