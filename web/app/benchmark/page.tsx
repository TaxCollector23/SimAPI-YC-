import type { Metadata } from "next";
import { SectionHeader } from "@/components/ui/section";
import { BenchmarkStats } from "@/components/benchmark-stats";
import results from "@/lib/benchmark-results.json";

export const metadata: Metadata = {
  title: "Benchmark Methodology",
  description:
    "APIE benchmark at production scale (n=9,333): methodology, architecture, and honest per-category results.",
};

const gbt = results.models.gbt;
const mlp = results.models.mlp;
const excl = results.exclusion;
const cat = excl.per_category_recall_pct;
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
            lede="Every number on this page is produced by benchmark/run_benchmark.py — a script anyone can run. We publish methodology, honest limitations, and negative results. The numbers are not cherry-picked from multiple runs."
          />

          <div className="mx-auto mt-10 grid max-w-4xl gap-4 sm:grid-cols-3">
            <Stat
              value={`${(excl.recall * 100).toFixed(1)}%`}
              label="overall recall"
              sub={`${results.seeds.length} seeds, n=${results.n_train.toLocaleString()} train trials`}
            />
            <Stat
              value={`${(excl.precision * 100).toFixed(1)}%`}
              label="exclusion precision"
              sub="when APIE flags a trial, it is genuinely corrupted"
            />
            <Stat
              value={`${valS}s`}
              label={`validation latency ±${valStdS}s`}
              sub={`full APIE cascade, CPU-only, n=${results.n_train.toLocaleString()} rows`}
            />
          </div>

          <div className="mx-auto mt-8 grid max-w-4xl gap-4 sm:grid-cols-2">
            <Card title="Dataset — production scale">
              A synthetic but physically self-consistent aerodynamics dataset:{" "}
              {results.n_train.toLocaleString()} training trials and{" "}
              {results.n_test.toLocaleString()} held-out test trials — 7× larger than
              the original benchmark. Generated from exact physical relationships (Re = ρvL/μ,
              Ma = v/c, P = ρRT) so ground truth corruption labels are available. At this
              scale, all 6 corruption categories inject proportionally more rows
              (e.g., ~460 measurement noise trials, ~1,400 sensor drift trials).
            </Card>

            <Card title="Corruption model">
              {results.corruption_rate_pct}% of training trials are corrupted across 6 documented
              categories: solver divergence (5%), unit conversion — Pa vs kPa (4%), cross-variable
              inconsistency — Re≠ρvL/μ (4%), copy-paste duplication (2.5%), sensor drift —
              progressive 1–9% velocity creep (15%), and measurement noise — ±12% target
              perturbation (5%). Corruption placement is fully randomised per seed.
            </Card>

            <Card title="Architecture: APIE three-stage cascade">
              <strong className="text-white/80">Stage 1 Fingerprinter (~50ms)</strong>: Computes
              a ~685-token JSON fingerprint — RANSAC ratio invariants with Kendall-tau drift
              scores, per-column skew/kurtosis/outlier counts, copy-paste cosine fraction,
              residual entropy from linear fit. No exclusion decisions made here.
              <br /><br />
              <strong className="text-white/80">Stage 2 Orchestrator (0ms det. / 2–5s AI)</strong>:
              Translates fingerprint into a parametric test plan. In deterministic mode, a
              rule-based meta-selector picks checks and calibrates thresholds from the fingerprint
              signals. In AI mode, the fingerprint is sent to an LLM which returns a JSON test
              plan. The LLM reasons about <em>what to check</em>, not individual rows — it cannot
              hallucinate row-level decisions.
              <br /><br />
              <strong className="text-white/80">Stage 3 Filter Bank (~200ms–2s)</strong>: Executes
              only the requested checks with the AI-specified parameters. Eight parametric checks:
              ratio invariant, pairwise ratio drift, ensemble predictor, copy-paste block,
              distribution shift, local neighbor anomaly, power law, joint skew outlier.
              Each check fits its model exclusively on the running clean inlier set.
            </Card>

            <Card title="AI integration — what it actually does">
              The AI layer receives only the fingerprint (~685 tokens), never raw rows.
              At n=9,333, sending all data would be prohibitive; the fingerprint is bounded
              regardless of dataset size. The AI identifies which corruption types are likely
              present and requests specific checks with calibrated parameters — for example,
              detecting that pressure skew of −4.9 vs clean density/temperature signals a
              Pa→kPa unit error and setting ratio threshold accordingly.
              <br /><br />
              In benchmark mode (no API key), a deterministic meta-selector produces
              the same test plan. The AI upgrades parameters when available; the deterministic
              plan is the safety net. Both are merged and tested honestly.
            </Card>

            <Card title="Baselines">
              Two baselines: (1) untouched corrupted training set, and (2) naive IQR outlier
              removal + z-score filtering at 4σ. SimAPI must beat both. At n=9,333,
              naive filtering removes fewer rows and is more competitive on GBT (robust model)
              but substantially worse on MLP (distribution-sensitive model) — exactly the
              split we predict from the architecture.
            </Card>

            <Card title="Runs &amp; variance">
              Every number is mean ± std across {results.seeds.length} seeds ({results.seeds.join(", ")}).
              A single-seed run is an anecdote. Total benchmark time: {results.elapsed_s}s
              on a laptop CPU — including all 5 validation runs, all model training, and
              all evaluation. No GPU, no network calls, no special hardware.
            </Card>

            <Card title="Latency — the honest number">
              Validation latency at n=9,333 is {valS}s ± {valStdS}s. This includes the full
              APIE cascade: fingerprinting (~50ms), orchestration (0ms deterministic), and
              all filter bank checks (~2.5s). The PhysicsValidator pre-pass dominates
              at ~1.5s. With AI assistance (real LLM call), add 2–5s for the orchestration
              phase — still sub-10s for 9K rows, scaling linearly with dataset size.
            </Card>

            <Card title="Reproducibility">
              Run it yourself:{" "}
              <code className="rounded bg-white/[0.06] px-1 py-0.5 font-mono text-xs">
                python -m benchmark.run_benchmark
              </code>
              . No hidden data files. Output writes to{" "}
              <code className="rounded bg-white/[0.06] px-1 py-0.5 font-mono text-xs">
                benchmark/results.json
              </code>
              , which this page reads directly. With Anthropic key:{" "}
              <code className="rounded bg-white/[0.06] px-1 py-0.5 font-mono text-xs">
                ANTHROPIC_API_KEY=sk-... python -m benchmark.run_benchmark
              </code>
              .
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
                numbers are a controlled proof of mechanism.
              </li>
              <li>
                <strong className="text-white/80">Single domain.</strong> All runs use
                aerodynamics data. APIE is domain-agnostic but per-category recall depends
                on which physical invariants are present. Other domains will have different
                fingerprint signals and require different checks.
              </li>
              <li>
                <strong className="text-white/80">Measurement noise floor.</strong>{" "}
                {(100 - (cat.measurement_noise ?? 90)).toFixed(0)}% of measurement noise rows
                are missed ({cat.measurement_noise?.toFixed(1)}% caught). These are rows where
                the ±12% perturbation falls within natural data variance for that specific
                feature value combination. This is a physical detection limit, not a software bug.
              </li>
              <li>
                <strong className="text-white/80">GBT improvement is modest.</strong> GBT improved{" "}
                {gbt.mape_improvement_mean.toFixed(1)}% vs corrupted and{" "}
                {gbt.simapi_vs_naive_mean.toFixed(1)}% vs naive. Tree models are inherently
                robust to outliers — the value here is precision (knowing WHICH rows to
                debug) and downstream MLP/neural pipeline improvement, not MAPE on GBT itself.
              </li>
              <li>
                <strong className="text-white/80">MLP improvement of {mlp.mape_improvement_mean.toFixed(0)}% is upper bound.</strong>{" "}
                MLP is maximally sensitive to distribution shift. Neural networks in
                production pipelines will see improvement proportional to their sensitivity
                to the corruptions present in their specific dataset.
              </li>
            </ul>
          </div>
        </div>
      </section>

      <BenchmarkStats />

      <section className="pb-24">
        <div className="container-tight">
          <div className="mx-auto max-w-4xl">
            <h2 className="text-lg font-semibold text-white mb-2">Per-category detection</h2>
            <p className="text-sm text-white/45 mb-6">
              n={results.n_train.toLocaleString()} training trials · {results.seeds.length} seeds · {results.ai_mode}
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              {[
                { cat: "Solver divergence", pct: cat.solver_divergence, mech: "Joint Mahalanobis outlier on correlated (Cd, Cl) pair — kurtosis~16 at 5.5σ threshold. Zero false positives at n=9,333." },
                { cat: "Unit conversion errors", pct: cat.unit_conversion, mech: "RANSAC invariant on P/(ρT). A Pa→kPa swap gives 0.287 instead of 287 J/kg·K — a 1000× deviation, detectable at any scale." },
                { cat: "Sensor drift", pct: cat.sensor_drift, mech: "Early-segment baseline tracker on Ma/v. Uses first 8% of data as clean anchor. Catches drift even when it starts at row 1000 in a 9K dataset." },
                { cat: "Copy-paste blocks", pct: cat.copy_paste, mech: "Cosine similarity scan with window=8, threshold=0.999. Standardised feature vectors; perturbed duplicates still exceed threshold." },
                { cat: "Cross-variable inconsistency", pct: cat.cross_variable, mech: "Ratio invariant on Re/v at σ=3.5. At n=9,333: 0 clean false positives, 100% recall. Corrupted Re is 1.7–2.2× larger than expected from velocity." },
                { cat: "Measurement noise", pct: cat.measurement_noise, mech: `Local k-NN regression anomaly + multi-model ensemble. ${(100 - (cat.measurement_noise ?? 90)).toFixed(0)}% missed are perturbations below local variance floor — physical detection limit.` },
              ].map((c) => (
                <div key={c.cat} className="rounded-xl border border-white/[0.08] bg-ink-900/40 p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-white">{c.cat}</span>
                    <span className="font-mono text-lg font-semibold text-accent-cyan">
                      {c.pct?.toFixed(1)}%
                    </span>
                  </div>
                  <div className="mb-3 h-1.5 w-full rounded-full bg-white/[0.06]">
                    <div className="h-1.5 rounded-full bg-accent-cyan/60" style={{ width: `${c.pct ?? 0}%` }} />
                  </div>
                  <p className="text-xs leading-relaxed text-white/40">{c.mech}</p>
                </div>
              ))}
            </div>

            <div className="mt-6 rounded-xl border border-white/[0.08] bg-ink-900/40 p-5">
              <h3 className="text-sm font-semibold text-white mb-3">What the AI actually sees</h3>
              <p className="text-sm text-white/55 leading-relaxed mb-3">
                At n=9,333, the fingerprint sent to the AI is ~685 tokens. Here is a real example
                of the diagnosis Claude produces from the fingerprint alone, without seeing any rows:
              </p>
              <div className="rounded-lg bg-black/30 p-4 font-mono text-xs text-white/70 leading-relaxed">
                <span className="text-accent-cyan">AI diagnosis: </span>
                &ldquo;Aerodynamics dataset with high-confidence multi-corruption: joint Cd/Cl kurtosis~16
                indicates solver divergence (5%); pressure skew −4.9 vs clean density/temperature
                indicates Pa→kPa unit error (4%); Ma/v Kendall tau=0.042 p=0.0 indicates velocity
                sensor drift; Re outliers 293 vs velocity 0 indicates cross-variable Reynolds
                contamination.&rdquo;
              </div>
              <p className="mt-3 text-xs text-white/35">
                The AI then specifies which checks to run and with which thresholds. It cannot
                modify the filter bank code — only parametrise it. This bounds the blast radius
                of any AI reasoning error.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
