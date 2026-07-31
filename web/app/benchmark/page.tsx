import type { Metadata } from "next";
import { SectionHeader } from "@/components/ui/section";
import { BenchmarkStats } from "@/components/benchmark-stats";
import results from "@/lib/benchmark-results-dimensional.json";

export const metadata: Metadata = {
  title: "Benchmark Methodology",
  description:
    "Dimensional-analysis engine benchmark (n=9,333): methodology, architecture, and honest per-category results.",
};

const gbt = results.models.gbt;
const mlp = results.models.mlp;
const auto = results.auto_excluded;
const total = results.total_detected;
const catTotal = total.per_category_recall_pct;
const valS = (results.validation_ms_mean / 1000).toFixed(1);
const valStdS = (results.validation_ms_std / 1000).toFixed(1);

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-white/[0.08] bg-ink-900/50 p-6">
      <h3 className="text-sm font-semibold text-white">{title}</h3>
      <div className="mt-3 text-sm leading-relaxed text-white/60">{children}</div>
    </div>
  );
}

function Stat({ value, label, sub }: { value: string; label: string; sub?: string }) {
  return (
    <div className="rounded-2xl border border-white/[0.08] bg-ink-900/50 p-5 text-center">
      <p className="font-mono text-3xl font-semibold text-accent-cyan">{value}</p>
      <p className="mt-1 text-sm text-white/60">{label}</p>
      {sub && <p className="mt-1.5 text-[11px] leading-relaxed text-white/35">{sub}</p>}
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
            lede="Every number on this page is produced by benchmark/run_benchmark_dimensional.py — a script anyone can run. We publish methodology, honest limitations, and negative results. The numbers are not cherry-picked from multiple runs."
          />

          <div className="mx-auto mt-10 grid max-w-4xl gap-4 sm:grid-cols-3">
            <Stat
              value={`${(total.recall * 100).toFixed(1)}%`}
              label="total detection recall"
              sub={`${results.seeds.length} seeds, n=${results.n_train.toLocaleString()} train trials`}
            />
            <Stat
              value={`${(auto.precision * 100).toFixed(1)}%`}
              label="auto-exclusion precision"
              sub="when the engine auto-excludes a trial, it is genuinely corrupted"
            />
            <Stat
              value={`${valS}s`}
              label={`validation latency ±${valStdS}s`}
              sub={`full dimensional-analysis cascade, CPU-only, n=${results.n_train.toLocaleString()} rows`}
            />
          </div>

          <div className="mx-auto mt-8 grid max-w-4xl gap-4 sm:grid-cols-2">
            <Card title="Dataset — production scale">
              A synthetic but physically self-consistent aerodynamics dataset:{" "}
              {results.n_train.toLocaleString()} training trials and{" "}
              {results.n_test.toLocaleString()} held-out test trials. Generated from exact
              physical relationships (Re = ρvL/μ, Ma = v/c, P = ρRT) so ground truth corruption
              labels are available and the ideal-gas anchor has something real to verify against.
            </Card>

            <Card title="Corruption model">
              {results.corruption_rate_pct}% of training trials are corrupted across 6 documented
              categories: solver divergence (drag/lift coefficient spikes, 5%), unit conversion —
              Pa vs kPa (4%), cross-variable inconsistency — Re scaled 1.7–2.2× (4%), copy-paste
              near-duplication (2.5%), sensor drift — progressive 1–9% velocity creep (15%), and
              measurement noise — ±12% target perturbation (5%). Corruption placement is fully
              randomised per seed. Identical dataset generator and corruption injector as the
              retired engine&rsquo;s benchmark, for a fair comparison.
            </Card>

            <Card title="Architecture: 9-layer dimensional cascade">
              <strong className="text-white/80">Layer 0 — Units resolution</strong>: maps every
              column to SI base-dimension exponents via a dictionary (LLM fallback for unresolved
              columns), converts non-SI units, and emits per-column confidence.
              <br /><br />
              <strong className="text-white/80">Layers 1–4 — Discovered laws</strong>: enumerates
              dimensionless Pi-groups, finds ones that are constant across rows (exact laws) or
              match a known physical constant (anchored constants — the layer that stays correct
              even past 50% corruption, since a constant doesn&rsquo;t move with the data), and
              detects bimodal unit-convention splits.
              <br /><br />
              <strong className="text-white/80">Layer 5 — Pi-space response surface</strong>:
              <em> local</em> — a k-NN regression in log-transformed coordinates catches
              corruption that breaks no law and stays in-range but doesn&rsquo;t fit the learned
              Cd = f(Re, Ma)-style relationship. <em>Global</em> — a robust regression (IRLS with
              Huber weights, numpy-only, no new dependency) fit against the same reference sample,
              run alongside the local check. This closes a real gap: corruption clustered in
              feature space (e.g. a whole velocity band from one bad solver run) makes a corrupted
              row&rsquo;s nearest neighbours mostly other corrupted rows, so the local fit can
              validate the cluster against itself — measured catching only 1 of 39 rows in a
              clustered-corruption test before the global check was added. A global fit is barely
              perturbed by a minority cluster, so it stays sensitive to exactly what the local
              check misses. Both feed the review tier below.
              <br /><br />
              <strong className="text-white/80">Layers 6–8</strong>: semantic bounds (definitional
              impossibilities — a fraction outside [0,1]), declared-condition assertions, and
              structural checks (NaN/Inf, exact duplicates, and near-duplicates via
              magnitude-aware significant-figure bucketing — catches a copy-pasted block disguised
              with ~1e-5 relative noise even on large-magnitude columns like Reynolds number,
              which decimal-place bucketing alone misses).
            </Card>

            <Card title="Two output classes, not one exclusion list">
              <strong className="text-white/80">Auto-excluded</strong> ({(auto.recall * 100).toFixed(1)}% recall,{" "}
              {(auto.precision * 100).toFixed(1)}% precision): impossible or unsuitable-for-training
              rows — an anchored constant is violated, or a definitional bound is broken. No
              human review needed; this tier is never wrong on this benchmark.
              <br /><br />
              <strong className="text-white/80">Flagged for review</strong> (brings total recall to{" "}
              {(total.recall * 100).toFixed(1)}%): rows that deviate from the response surface but
              don&rsquo;t break a provable law. The engine is not confident enough to auto-remove
              these — it surfaces them for a human decision instead.
            </Card>

            <Card title="Baselines">
              Two baselines: (1) untouched corrupted training set, and (2) naive IQR outlier
              removal + z-score filtering at 4σ. On this benchmark, naive filtering is
              competitive with — and on MLP, currently beats — the auto-excluded-only tier,
              because it catches large-magnitude statistical outliers (like the solver-divergence
              spikes) that don&rsquo;t violate any checkable physical law. See the limitations
              section below; we are not hiding this.
            </Card>

            <Card title="Runs &amp; variance">
              Every number is mean across {results.seeds.length} seeds ({results.seeds.join(", ")}).
              A single-seed run is an anecdote. Total benchmark time: {results.elapsed_s}s
              on a CPU-only container — including all 5 validation runs, all model training, and
              all evaluation. No GPU, no network calls, no special hardware.
            </Card>

            <Card title="Latency — the honest number">
              Validation latency at n≈9,333 rows is {valS}s ± {valStdS}s. Most of this is the
              response-surface layer's k-NN search (fit against a bounded 1,500-row reference
              sample for tractable distance-matrix cost, but every row is scored against it — an
              earlier version of this layer silently skipped ~84% of rows above 1,500 total, which
              is exactly the kind of gap this benchmark exists to catch).
            </Card>

            <Card title="Reproducibility">
              Run it yourself:{" "}
              <code className="rounded bg-white/[0.06] px-1 py-0.5 font-mono text-xs">
                python -m benchmark.run_benchmark_dimensional
              </code>
              . No hidden data files. Output writes to{" "}
              <code className="rounded bg-white/[0.06] px-1 py-0.5 font-mono text-xs">
                benchmark/results_dimensional.json
              </code>
              , which this page reads directly.
            </Card>
          </div>

          <div className="mx-auto mt-6 max-w-4xl rounded-2xl border border-amber-500/20 bg-amber-500/[0.04] p-6">
            <h3 className="text-sm font-semibold text-amber-300">
              Limitations — read before citing
            </h3>
            <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-relaxed text-white/60">
              <li>
                <strong className="text-white/80">Synthetic data.</strong> Generated from known
                physical relationships. Real datasets have correlated noise, multi-physics
                coupling, and instrument-specific failure modes not captured here. These
                numbers are a controlled proof of mechanism, not a production SLA.
              </li>
              <li>
                <strong className="text-white/80">Single domain, single feature set.</strong> All
                runs use an 8-column aerodynamics dataset. Recall depends heavily on which
                anchored constants and declared conditions apply to the columns actually present
                — a dataset with more physically-coupled columns (e.g. one where reference length
                is itself a column) will see materially higher recall than this benchmark shows.
              </li>
              <li>
                <strong className="text-white/80">Auto-exclusion recall is low by design, not by accident.</strong>{" "}
                Only {(auto.recall * 100).toFixed(1)}% of corrupted rows are auto-excluded. This is
                intentional: the engine only auto-removes what it can mathematically prove is
                wrong. Most of the detection work on this benchmark ({(total.recall * 100).toFixed(1)}% total)
                lands in the review tier, which requires a human decision by design.
              </li>
              <li>
                <strong className="text-white/80">Measurement noise is the honest weak point.</strong>{" "}
                Only {catTotal.measurement_noise?.toFixed(1)}% of measurement-noise corruption is
                caught. These are perturbations that land within the natural scatter for that
                specific feature combination — a genuine physical detection limit (there's no
                statistical signature to find), not a software gap. By contrast, near-duplicate
                rows — the previous weak point — are now caught at{" "}
                {catTotal.copy_paste?.toFixed(0)}%, after fixing a bucketing bug that missed
                large-magnitude columns.
              </li>
              <li>
                <strong className="text-white/80">On this benchmark, MLP training quality using only the
                auto-excluded tier does not clearly beat naive filtering.</strong> MAPE went from{" "}
                {mlp.mape_corrupted_mean.toFixed(2)}% (corrupted) to {mlp.mape_simapi_mean.toFixed(2)}%
                (dimensional, auto-excluded tier only) vs {mlp.mape_naive_mean.toFixed(2)}% (naive
                IQR/z-score). GBT improved modestly ({gbt.mape_corrupted_mean.toFixed(2)}% →{" "}
                {gbt.mape_simapi_mean.toFixed(2)}%). The auto-excluded tier optimizes for
                zero-false-positive precision, not for maximum rows removed — pairing it with a
                human decision on the review tier is expected to close most of this gap, but we
                haven&rsquo;t measured that yet.
              </li>
            </ul>
          </div>
        </div>
      </section>

      <BenchmarkStats />
    </div>
  );
}
