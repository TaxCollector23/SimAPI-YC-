import { SectionHeader } from "./ui/section";

// Sourced from benchmark/results.json (5 seeds). Shown with std — the honest range.
const MODELS = [
  { name: "Gradient Boosting", mape: "23%", std: "±14%", note: "robust baseline" },
  { name: "Neural Net (MLP)", mape: "53%", std: "±14%", note: "data-hungry model" },
];
const EXCLUSION = [
  { label: "Exclusion precision", value: "100%", hint: "of excluded trials were genuinely corrupted" },
  { label: "Exclusion recall", value: "55%", hint: "of corrupted trials caught (up from 38% baseline)" },
];

export function BenchmarkStats() {
  return (
    <section className="relative py-20 sm:py-24">
      <div className="container-tight">
        <SectionHeader
          eyebrow="Benchmark"
          title={<>Measured improvement, with error bars</>}
          lede="We inject known corruptions into training data, let SimAPI exclude what it flags, then train surrogate models on the cleaned set. Reported as mean ± std across 5 seeded configurations — not a single cherry-picked run."
        />
        <div className="mx-auto mt-10 grid max-w-4xl gap-4 sm:grid-cols-2">
          {MODELS.map((m) => (
            <div key={m.name} className="rounded-2xl border border-white/[0.08] bg-ink-900/50 p-6">
              <p className="text-sm text-white/50">{m.name} <span className="text-white/30">· {m.note}</span></p>
              <p className="mt-2 flex items-baseline gap-2">
                <span className="text-4xl font-semibold text-white">{m.mape}</span>
                <span className="font-mono text-lg text-white/40">{m.std}</span>
              </p>
              <p className="mt-1 text-xs text-white/40">MAPE improvement vs training on the raw corrupted data</p>
            </div>
          ))}
        </div>
        <div className="mx-auto mt-4 grid max-w-4xl gap-4 sm:grid-cols-2">
          {EXCLUSION.map((e) => (
            <div key={e.label} className="flex items-center justify-between rounded-2xl border border-white/[0.07] bg-white/[0.02] px-5 py-4">
              <div>
                <p className="text-xs uppercase tracking-wider text-white/40">{e.label}</p>
                <p className="text-xs text-white/35">{e.hint}</p>
              </div>
              <span className="font-mono text-2xl font-semibold text-accent-cyan">{e.value}</span>
            </div>
          ))}
        </div>
        <p className="mx-auto mt-6 max-w-4xl text-center text-xs text-white/30">
          Reproduce it yourself: <code className="rounded bg-white/[0.06] px-1.5 py-0.5 font-mono text-white/60">python -m benchmark.run_benchmark</code> — the exact numbers vary with corruption severity, which is why we show the spread.
        </p>
      </div>
    </section>
  );
}
