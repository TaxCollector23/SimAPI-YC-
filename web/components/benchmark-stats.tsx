import results from "@/lib/benchmark-results-dimensional.json";

const gbt = results.models.gbt;
const mlp = results.models.mlp;
const auto = results.auto_excluded;
const total = results.total_detected;
const catAuto = auto.per_category_recall_pct;
const catTotal = total.per_category_recall_pct;
const n_train = results.n_train ?? 9333;

function pct(v: number, d = 1) { return `${v.toFixed(d)}%`; }

const CATEGORIES: { cat: string; a: number; t: number }[] = [
  { cat: "Unit conversion (Pa vs kPa)", a: catAuto.unit_conversion, t: catTotal.unit_conversion },
  { cat: "Cross-variable (Re ≠ ρvL/μ)", a: catAuto.cross_variable, t: catTotal.cross_variable },
  { cat: "Measurement noise", a: catAuto.measurement_noise, t: catTotal.measurement_noise },
  { cat: "Solver divergence", a: catAuto.solver_divergence, t: catTotal.solver_divergence },
  { cat: "Sensor drift", a: catAuto.sensor_drift, t: catTotal.sensor_drift },
  { cat: "Copy-paste (near-duplicate rows)", a: catAuto.copy_paste, t: catTotal.copy_paste },
];

export function BenchmarkStats() {
  return (
    <section className="relative py-20 sm:py-24">
      <div className="container-tight max-w-4xl">
        {/* Header — flat, left-aligned, no eyebrow */}
        <h2 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">The honest numbers</h2>
        <p className="mt-3 max-w-2xl text-sm leading-relaxed text-white/55">
          n={n_train.toLocaleString()} training trials, {results.corruption_rate_pct}% corrupted across 6 failure
          modes. Same dataset generator and corruption injector as the legacy engine&rsquo;s benchmark — only the
          engine under test changed. Mean across {results.seeds.length} seeds.
        </p>

        {/* Headline numbers — flat divided row, not glow cards */}
        <div className="mt-8 grid border border-white/10 sm:grid-cols-3 sm:divide-x sm:divide-white/10">
          {[
            { v: pct(results.corruption_rate_pct, 0), l: "of trials corrupted", h: "6 categories, incl. measurement noise below the local variance floor" },
            { v: pct(auto.recall * 100, 1), l: "auto-excluded, no review", h: `precision ${pct(auto.precision * 100, 1)} — zero false positives at this tier` },
            { v: pct(total.recall * 100, 1), l: "total detected", h: `incl. flagged-for-review · precision ${pct(total.precision * 100, 1)}` },
          ].map((s) => (
            <div key={s.l} className="border-b border-white/10 p-5 last:border-b-0 sm:border-b-0">
              <p className="font-mono text-3xl font-semibold text-white">{s.v}</p>
              <p className="mt-1 text-sm text-white/70">{s.l}</p>
              <p className="mt-1.5 text-[11px] leading-relaxed text-white/40">{s.h}</p>
            </div>
          ))}
        </div>

        <div className="mt-6 border-l-2 border-accent-blue/50 bg-white/[0.02] px-5 py-4 text-sm leading-relaxed text-white/60">
          <span className="font-medium text-white/85">Two tiers, on purpose. </span>
          &ldquo;Auto-excluded&rdquo; rows violate a mathematically verifiable physical law (an anchored constant, a
          definitional bound) — when this engine excludes a row, it isn&rsquo;t a guess. &ldquo;Flagged for review&rdquo; rows
          deviate from the learned response surface but don&rsquo;t break a provable law — the engine surfaces them for a
          human rather than silently deleting data it can&rsquo;t prove is wrong.
        </div>

        {/* Downstream model impact */}
        <h3 className="mt-12 text-sm font-semibold text-white">Downstream model error (MAPE)</h3>
        <div className="mt-3 overflow-x-auto border border-white/10">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="border-b border-white/10 text-left text-xs text-white/45">
                <th className="p-3 font-medium">Model</th>
                <th className="p-3 font-medium">Corrupted</th>
                <th className="p-3 font-medium">Naive (IQR+Z)</th>
                <th className="p-3 font-medium">Dimensional (auto-excl)</th>
                <th className="p-3 font-medium">Clean ceiling</th>
              </tr>
            </thead>
            <tbody className="font-mono text-white/70">
              <tr className="border-b border-white/[0.06]">
                <td className="p-3 font-sans">
                  <span className="text-white">Neural net (MLP)</span>
                  <span className="block text-xs text-white/35">distribution-sensitive</span>
                </td>
                <td className="p-3 text-fail">{pct(mlp.mape_corrupted_mean, 2)}</td>
                <td className="p-3 text-warn">{pct(mlp.mape_naive_mean, 2)}</td>
                <td className="p-3 text-white/70">{pct(mlp.mape_simapi_mean, 2)}</td>
                <td className="p-3 text-white/40">{pct(mlp.mape_clean_mean, 2)}</td>
              </tr>
              <tr>
                <td className="p-3 font-sans">
                  <span className="text-white">Gradient boosting</span>
                  <span className="block text-xs text-white/35">robust to outliers</span>
                </td>
                <td className="p-3 text-white/60">{pct(gbt.mape_corrupted_mean, 2)}</td>
                <td className="p-3 text-white/60">{pct(gbt.mape_naive_mean, 2)}</td>
                <td className="p-3 text-pass">{pct(gbt.mape_simapi_mean, 2)}</td>
                <td className="p-3 text-white/40">{pct(gbt.mape_clean_mean, 2)}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs leading-relaxed text-white/40">
          This table trains only with the <span className="text-white/70">auto-excluded</span> tier removed — the
          flagged-for-review rows are deliberately left in, since removing them without a human decision would defeat
          the point of a review tier. On MLP, naive statistical filtering currently beats the auto-excluded-only tier
          on this synthetic benchmark, because naive filtering catches large-magnitude outliers (like solver-divergence
          spikes) that don&rsquo;t violate any checkable physical law and so land in the review tier by design. We&rsquo;re not
          hiding that.
        </p>

        {/* Per-category recall */}
        <h3 className="mt-12 text-sm font-semibold text-white">Recall by failure category</h3>
        <div className="mt-3 overflow-x-auto border border-white/10">
          <table className="w-full min-w-[520px] text-sm">
            <thead>
              <tr className="border-b border-white/10 text-left text-xs text-white/45">
                <th className="p-3 font-medium">Category</th>
                <th className="p-3 text-right font-medium">Auto-excluded</th>
                <th className="p-3 text-right font-medium">Total detected</th>
              </tr>
            </thead>
            <tbody>
              {CATEGORIES.map((c) => (
                <tr key={c.cat} className="border-b border-white/[0.06] last:border-b-0">
                  <td className="p-3 text-white/70">{c.cat}</td>
                  <td className="p-3 text-right font-mono text-accent-blue">{c.a?.toFixed(1)}%</td>
                  <td className="p-3 text-right font-mono text-white/70">{c.t?.toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Strong / weak, flat panels */}
        <div className="mt-6 grid gap-px border border-white/10 bg-white/10 sm:grid-cols-2">
          <div className="bg-ink-900 p-5">
            <h4 className="mb-2 text-sm font-semibold text-white">Strongest: anchored constants</h4>
            <p className="text-sm leading-relaxed text-white/55">
              A Pa→kPa unit error produces individually plausible pressure values — only P/(ρT) ≈ 0.287 instead of
              287.05 J/(kg·K) reveals it. That&rsquo;s a physical constant, not a statistical pattern, so it doesn&rsquo;t
              degrade with dataset size or corruption fraction. Unit-conversion recall stays near{" "}
              {catTotal.unit_conversion?.toFixed(0)}% regardless of scale, auto-excluded with zero false positives.
            </p>
          </div>
          <div className="bg-ink-900 p-5">
            <h4 className="mb-2 text-sm font-semibold text-white">Honestly weak: measurement noise</h4>
            <p className="text-sm leading-relaxed text-white/55">
              {(100 - (catTotal.measurement_noise ?? 100)).toFixed(0)}% of measurement-noise rows are missed
              ({catTotal.measurement_noise?.toFixed(1)}% caught). These perturbations land within the natural scatter
              for that specific feature combination — there&rsquo;s no statistical signature to find, because the corrupted
              value is genuinely indistinguishable from a real one at that point in the design space. A physical
              detection limit, not a software gap.
            </p>
          </div>
        </div>

        <p className="mt-6 text-xs text-white/35">
          Reproduce:{" "}
          <code className="bg-white/[0.06] px-1.5 py-0.5 font-mono">python -m benchmark.run_benchmark_dimensional</code>{" "}
          — {results.seeds.length} seeds · n≈{n_train.toLocaleString()} train · {results.elapsed_s}s runtime · precision
          is stable across seeds; recall varies by category as shown.
        </p>
      </div>
    </section>
  );
}
