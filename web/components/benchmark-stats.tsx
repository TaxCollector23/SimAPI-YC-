import { SectionHeader } from "./ui/section";
import results from "@/lib/benchmark-results.json";

const gbt = results.models.gbt;
const mlp = results.models.mlp;
const recall = results.exclusion.per_category_recall_pct;

// Sourced from benchmark/results.json (5 seeds, randomized corruption). Full
// methodology and reproduction steps live on /benchmark — this component is
// numbers only.
export function BenchmarkStats() {
  return (
    <section className="relative py-20 sm:py-24">
      <div className="container-tight">
        <SectionHeader eyebrow="Benchmark" title={<>Benchmarks</>} />

        {/* Detection */}
        <div className="mx-auto mt-10 grid max-w-4xl gap-4 sm:grid-cols-3">
          {[
            { v: `${results.corruption_rate_pct.toFixed(0)}%`, l: "of trials corrupted", h: "6 categories: solver divergence, unit errors, sensor drift, cross-variable, copy-paste, measurement noise" },
            { v: `${Math.round(results.exclusion.recall * 100)}%`, l: "of corruptions caught", h: "exclusion recall across 5 seeded runs" },
            { v: `${(results.exclusion.precision * 100).toFixed(0)}%`, l: "exclusion precision", h: "when SimAPI flags a trial, it's genuinely corrupted" },
          ].map((s) => (
            <div key={s.l} className="rounded-2xl border border-white/[0.08] bg-ink-900/50 p-5 text-center">
              <p className="font-mono text-3xl font-semibold text-accent-cyan">{s.v}</p>
              <p className="mt-1 text-sm text-white/60">{s.l}</p>
              <p className="mt-1.5 text-[11px] leading-relaxed text-white/35">{s.h}</p>
            </div>
          ))}
        </div>

        {/* Model impact — four-way comparison */}
        <div className="mx-auto mt-4 max-w-4xl overflow-hidden rounded-2xl border border-white/[0.08]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/[0.08] bg-white/[0.02] text-left text-xs uppercase tracking-wider text-white/40">
                <th className="p-3.5 font-medium">Model</th>
                <th className="p-3.5 font-medium">Corrupted</th>
                <th className="p-3.5 font-medium">Naive (IQR+Z)</th>
                <th className="p-3.5 font-medium">SimAPI</th>
                <th className="p-3.5 font-medium">Clean ceiling</th>
              </tr>
            </thead>
            <tbody className="text-white/70">
              <tr className="border-b border-white/[0.05]">
                <td className="p-3.5"><span className="text-white">Neural net (MLP)</span></td>
                <td className="p-3.5 font-mono text-red-400">{mlp.mape_corrupted_mean}% MAPE</td>
                <td className="p-3.5 font-mono text-yellow-400">{mlp.mape_naive_mean}% MAPE</td>
                <td className="p-3.5 font-mono text-pass">{mlp.mape_simapi_mean}% MAPE</td>
                <td className="p-3.5 font-mono text-white/40">{mlp.mape_clean_mean}% MAPE</td>
              </tr>
              <tr>
                <td className="p-3.5"><span className="text-white">Gradient boosting</span></td>
                <td className="p-3.5 font-mono text-white/60">{gbt.mape_corrupted_mean}% MAPE</td>
                <td className="p-3.5 font-mono text-white/60">{gbt.mape_naive_mean}% MAPE</td>
                <td className="p-3.5 font-mono text-pass">{gbt.mape_simapi_mean}% MAPE</td>
                <td className="p-3.5 font-mono text-white/40">{gbt.mape_clean_mean}% MAPE</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Per-category recall */}
        <div className="mx-auto mt-4 max-w-4xl overflow-hidden rounded-2xl border border-white/[0.08]">
          <div className="bg-white/[0.02] p-3.5 text-xs uppercase tracking-wider text-white/40 border-b border-white/[0.08]">Per-category detection recall</div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-0">
            {Object.entries(recall).map(([cat, pct]) => (
              <div key={cat} className="border-b border-white/[0.05] p-3 text-sm">
                <span className="font-mono text-white/80">{pct.toFixed(0)}%</span>
                <span className="ml-2 text-white/40">{cat.replace(/_/g, " ")}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
