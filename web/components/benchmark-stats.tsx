import { SectionHeader } from "./ui/section";

// Sourced from benchmark/results.json (5 seeds). Shown with the full context —
// corruption rate + absolute before/after MAPE — so it isn't a vanity metric.
export function BenchmarkStats() {
  return (
    <section className="relative py-20 sm:py-24">
      <div className="container-tight">
        <SectionHeader
          eyebrow="Benchmark"
          title={<>The honest numbers</>}
          lede="We corrupt ~32% of a 1,400-trial training set with six documented failure modes, let SimAPI exclude what it flags, then train models on the cleaned data. Reported as mean ± std across 5 seeded runs — with the raw before/after values, not just a headline percentage."
        />

        {/* Detection */}
        <div className="mx-auto mt-10 grid max-w-4xl gap-4 sm:grid-cols-3">
          {[
            { v: "32%", l: "of trials corrupted", h: "6 categories: solver divergence, unit errors, sensor drift, cross-variable, copy-paste, measurement noise" },
            { v: "89%", l: "of corruptions caught", h: "recall — the undetectable ~11% is pure in-bounds measurement noise" },
            { v: "99%", l: "exclusion precision", h: "of trials SimAPI excluded were genuinely corrupted" },
          ].map((s) => (
            <div key={s.l} className="rounded-2xl border border-white/[0.08] bg-ink-900/50 p-5 text-center">
              <p className="font-mono text-3xl font-semibold text-accent-cyan">{s.v}</p>
              <p className="mt-1 text-sm text-white/60">{s.l}</p>
              <p className="mt-1.5 text-[11px] leading-relaxed text-white/35">{s.h}</p>
            </div>
          ))}
        </div>

        {/* Model impact — absolute MAPE */}
        <div className="mx-auto mt-4 max-w-4xl overflow-hidden rounded-2xl border border-white/[0.08]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/[0.08] bg-white/[0.02] text-left text-xs uppercase tracking-wider text-white/40">
                <th className="p-3.5 font-medium">Model</th>
                <th className="p-3.5 font-medium">Trained on corrupted</th>
                <th className="p-3.5 font-medium">Trained on SimAPI-cleaned</th>
                <th className="p-3.5 font-medium">Clean-data ceiling</th>
              </tr>
            </thead>
            <tbody className="text-white/70">
              <tr className="border-b border-white/[0.05]">
                <td className="p-3.5"><span className="text-white">Neural net (MLP)</span><br /><span className="text-xs text-white/35">data-hungry, sensitive</span></td>
                <td className="p-3.5 font-mono text-red-400">7.31% MAPE</td>
                <td className="p-3.5 font-mono text-pass">2.70% MAPE</td>
                <td className="p-3.5 font-mono text-white/40">2.12% MAPE</td>
              </tr>
              <tr>
                <td className="p-3.5"><span className="text-white">Gradient boosting</span><br /><span className="text-xs text-white/35">robust baseline</span></td>
                <td className="p-3.5 font-mono text-white/60">0.58% MAPE</td>
                <td className="p-3.5 font-mono text-white/60">0.58% MAPE</td>
                <td className="p-3.5 font-mono text-white/40">0.42% MAPE</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="mx-auto mt-5 max-w-4xl rounded-2xl border border-white/[0.07] bg-white/[0.02] p-5 text-sm leading-relaxed text-white/55">
          <p><strong className="text-white/80">What the numbers mean.</strong> A sensitive model (MLP) trained on the corrupted set lands at 7.31% error; trained on the SimAPI-cleaned set it recovers to <strong className="text-pass">2.70%</strong> — most of the way to the 2.12% you'd get on perfectly clean data. That's a 58% ± 11% relative improvement, but the reason it's large is that the corrupted baseline was <em>bad</em>: a handful of out-of-bounds target rows wreck an unregularized net.</p>
          <p className="mt-3"><strong className="text-white/80">The honest caveat.</strong> A robust model (gradient boosting) barely moves — 0.58% → 0.58%. It already tolerates the corruption, so cleaning doesn't help it. <strong className="text-white/75">SimAPI's value scales with how sensitive your model is to training-data quality.</strong> If your model is robust, you gain little; if it's data-hungry, you gain a lot.</p>
        </div>

        <p className="mx-auto mt-5 max-w-4xl text-center text-xs text-white/30">
          Reproduce it: <code className="rounded bg-white/[0.06] px-1.5 py-0.5 font-mono text-white/60">python -m benchmark.run_benchmark</code> — exact numbers vary with corruption severity, which is why we publish the spread and the raw MAPE.
        </p>
      </div>
    </section>
  );
}
