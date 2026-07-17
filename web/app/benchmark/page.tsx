import type { Metadata } from "next";
import { SectionHeader } from "@/components/ui/section";
import { BenchmarkStats } from "@/components/benchmark-stats";
import results from "@/lib/benchmark-results.json";

export const metadata: Metadata = {
  title: "Benchmark Methodology",
  description:
    "How SimAPI's benchmark numbers are produced: dataset, corruption model, baselines, hardware, and what the results do and don't prove.",
};

const gbt = results.models.gbt;
const mlp = results.models.mlp;

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-white/[0.08] bg-ink-900/50 p-6">
      <h3 className="text-sm font-semibold text-white">{title}</h3>
      <div className="mt-3 text-sm leading-relaxed text-white/60">{children}</div>
    </div>
  );
}

export default function BenchmarkMethodologyPage() {
  return (
    <div className="pt-16">
      <section className="relative py-20 sm:py-24">
        <div className="container-tight">
          <SectionHeader
            eyebrow="Methodology"
            title={<>What we tested, and what we didn&rsquo;t</>}
            lede="Every number on this page comes from benchmark/run_benchmark.py, a script anyone can run locally. We publish the methodology so the numbers can be checked, not just trusted."
          />

          <div className="mx-auto mt-12 grid max-w-4xl gap-4 sm:grid-cols-2">
            <Card title="Dataset">
              A synthetic but physically-consistent aerodynamics dataset: {results.train_trials.toLocaleString()}{" "}
              training trials, {results.test_trials.toLocaleString()} held-out test trials. Generated from known
              physical relationships (lift/drag polars, Reynolds scaling, ideal gas law) so we have ground truth for
              which trials are corrupted and which are clean — something you can never get from real-world data.
            </Card>
            <Card title="Corruption model">
              {results.corruption_rate_pct}% of training trials are corrupted across 6 documented categories: solver
              divergence, unit conversion errors, sensor drift, copy-paste duplication, cross-variable
              inconsistency, and measurement noise. Corruption placement is randomized across the full dataset on
              every seed (not clustered in a fixed half) so detection can&rsquo;t rely on positional shortcuts.
            </Card>
            <Card title="Baseline">
              We compare against two baselines, not just &ldquo;no filtering&rdquo;: (1) the untouched corrupted
              training set, and (2) a naive statistical baseline (IQR outlier removal + z-score filtering at 4σ) —
              what a data scientist would do without SimAPI. SimAPI has to beat both to matter.
            </Card>
            <Card title="Models">
              Two model families with opposite sensitivity profiles: a gradient-boosted tree (
              <code className="rounded bg-white/[0.06] px-1 py-0.5 font-mono text-xs">
                GradientBoostingRegressor
              </code>
              , robust to outliers) and a small MLP (
              <code className="rounded bg-white/[0.06] px-1 py-0.5 font-mono text-xs">MLPRegressor</code>, sensitive
              to distribution shift). Reporting both instead of picking the flattering one is the point.
            </Card>
            <Card title="Runs &amp; variance">
              Every number is a mean ± standard deviation across {results.seeds.length} seeds ({results.seeds.join(
                ", ",
              )}
              ). A single-seed run is not a benchmark — it&rsquo;s an anecdote. Full run takes ~
              {results.elapsed_s.toFixed(1)}s on a laptop CPU, no GPU or special hardware required.
            </Card>
            <Card title="Reproducibility">
              Run it yourself:{" "}
              <code className="rounded bg-white/[0.06] px-1 py-0.5 font-mono text-xs">
                python -m benchmark.run_benchmark
              </code>
              . The script is ~230 lines, has no hidden data files, and writes its output to{" "}
              <code className="rounded bg-white/[0.06] px-1 py-0.5 font-mono text-xs">benchmark/results.json</code>{" "}
              — the same file this page reads from.
            </Card>
          </div>

          <div className="mx-auto mt-6 max-w-4xl rounded-2xl border border-amber-500/20 bg-amber-500/[0.04] p-6">
            <h3 className="text-sm font-semibold text-amber-300">Limitations — read this before citing these numbers</h3>
            <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-relaxed text-white/60">
              <li>
                <strong className="text-white/80">Synthetic data.</strong> The dataset is generated, not collected
                from a real wind tunnel or CFD run. Real datasets have correlated noise structures this benchmark
                can&rsquo;t capture. Treat these numbers as a controlled proof of mechanism, not a guarantee for
                your dataset.
              </li>
              <li>
                <strong className="text-white/80">GBT result is negative.</strong> SimAPI&rsquo;s exclusions
                reduced the GBT training set by more than the residual corruption cost it — MAPE moved from{" "}
                {gbt.mape_corrupted_mean}% to {gbt.mape_simapi_mean}% ({gbt.mape_improvement_mean}%). Tree models
                are already robust to the outlier-style corruptions in this benchmark, so removing data for them can
                cost more than it saves. We report this rather than hide it.
              </li>
              <li>
                <strong className="text-white/80">MLP result is a ceiling, not a typical case.</strong> {mlp.interpretation}
              </li>
              <li>
                <strong className="text-white/80">Naive filtering is competitive on MAPE.</strong> IQR/z-score
                filtering alone gets GBT to {gbt.mape_naive_mean}% and MLP to {mlp.mape_naive_mean}% — close to or
                better than SimAPI&rsquo;s {gbt.mape_simapi_mean}% and {mlp.mape_simapi_mean}%. SimAPI&rsquo;s
                advantage isn&rsquo;t raw MAPE here — it&rsquo;s {(results.exclusion.precision * 100).toFixed(1)}%
                exclusion precision (no false positives) and domain-specific detection (unit errors, physics
                violations) that a statistical filter structurally cannot see.
              </li>
              <li>
                <strong className="text-white/80">Recall is not uniform.</strong> Detection recall by category:{" "}
                {Object.entries(results.exclusion.per_category_recall_pct)
                  .map(([k, v]) => `${k.replace(/_/g, " ")} ${v}%`)
                  .join(", ")}
                . Measurement noise (14.6%) is the weakest category — low-magnitude noise within physically
                plausible bounds is fundamentally hard to distinguish from real variance.
              </li>
            </ul>
          </div>
        </div>
      </section>

      <BenchmarkStats />
    </div>
  );
}
