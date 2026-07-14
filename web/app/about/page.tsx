import type { Metadata } from "next";
import { PageHero } from "@/components/ui/page-hero";
import { Reveal } from "@/components/ui/reveal";
import { Cta } from "@/components/cta";

export const metadata: Metadata = {
  title: "About",
  description:
    "What SimAPI is, the problem it solves, how the validation engine works, and where it's headed.",
};

const domains = [
  "Aerodynamics", "Fluid dynamics", "Structural", "Thermodynamics", "Robotics",
  "Combustion", "Acoustics", "Electromagnetics", "Geomechanics", "Biomechanics",
  "Nuclear", "Plasma", "Chemical", "Hydrodynamics", "Meteorology", "Astrophysics",
  "Materials", "Tribology", "Aeroelasticity", "Cryogenics", "Multiphysics",
];

const pipeline = [
  { step: "Ingest", body: "Detect the format (JSON, CSV, VTK, NumPy, OpenFOAM) and normalize column aliases to canonical names." },
  { step: "Validate", body: "Run 53 layers — plausibility bounds, conservation laws, dimensional and cross-variable checks, and statistics — producing per-check results." },
  { step: "Aggregate", body: "Exclude trials that violate hard bounds, then reduce all checks to a single verdict: passed, warning, or failed." },
  { step: "Return", body: "Emit a structured report — score, violations, statistics, recommendations — plus an optional async reasoning pass." },
];

export default function AboutPage() {
  return (
    <>
      <PageHero
        eyebrow="About"
        title={<>Automated checks for simulation output.</>}
        lede="Software is trusted because it has automated tests. Simulations, which increasingly drive design decisions and ML datasets, have had no equivalent. SimAPI is that check."
      />

      <section className="container-tight space-y-16 py-12">
        {/* The problem */}
        <Reveal>
          <div className="max-w-2xl space-y-5 text-white/60">
            <h2 className="text-xl font-semibold text-white">The problem</h2>
            <p>
              An engineering team runs thousands of CFD, FEA, robotics, and multiphysics
              simulations. Before anyone trusts a result, an engineer inspects it by hand.
              That review is slow and inconsistent, and a single bad run — a diverged
              solver, a unit-conversion error, a saturated sensor — can quietly corrupt a
              design decision or an ML training set.
            </p>
            <p>
              The failure modes are usually not subtle. Impossible values, violated
              conservation laws, and inconsistent quantities are detectable by rule. What
              was missing was a fast, deterministic way to check every run automatically.
            </p>
          </div>
        </Reveal>

        {/* How the API works */}
        <Reveal>
          <div className="max-w-3xl">
            <h2 className="text-xl font-semibold text-white">How the API works</h2>
            <p className="mt-3 max-w-2xl text-white/60">
              A single request to <code className="rounded bg-white/[0.06] px-1.5 py-0.5 font-mono text-sm text-white/80">POST /v1/validate</code>{" "}
              runs the deterministic engine synchronously and returns a report in
              milliseconds.
            </p>
            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              {pipeline.map((p, i) => (
                <div key={p.step} className="rounded-2xl border border-white/[0.07] bg-ink-900/50 p-5">
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 items-center justify-center rounded-md border border-white/10 font-mono text-xs text-accent-cyan">
                      {i + 1}
                    </span>
                    <h3 className="text-sm font-semibold text-white">{p.step}</h3>
                  </div>
                  <p className="mt-3 text-sm leading-relaxed text-white/50">{p.body}</p>
                </div>
              ))}
            </div>
          </div>
        </Reveal>

        {/* Deterministic philosophy */}
        <Reveal>
          <div className="max-w-2xl space-y-5 text-white/60">
            <h2 className="text-xl font-semibold text-white">Deterministic first</h2>
            <p>
              Where physics gives a clear answer, SimAPI uses rules: auditable,
              reproducible, and fast. The same input always produces the same verdict, and
              every failure cites the check, the value, and the bound it violated — so a
              result is never a black box.
            </p>
            <p>
              An optional reasoning layer runs afterward for the questions rules can&apos;t
              encode — distribution shape, dataset provenance, ML-readiness. It augments the
              verdict; it never overrides the deterministic ground truth, and it can be
              turned off entirely.
            </p>
          </div>
        </Reveal>

        {/* Domains */}
        <Reveal>
          <div>
            <h2 className="text-xl font-semibold text-white">Supported domains</h2>
            <p className="mt-3 max-w-2xl text-white/60">
              287 checks are organized into per-domain rule sets. Each domain contributes
              plausibility bounds and cross-variable relationships specific to its physics.
            </p>
            <div className="mt-6 flex flex-wrap gap-2">
              {domains.map((d) => (
                <span key={d} className="rounded-full border border-white/[0.08] bg-ink-900/50 px-3 py-1.5 text-sm text-white/60">
                  {d}
                </span>
              ))}
            </div>
          </div>
        </Reveal>

        {/* Roadmap */}
        <Reveal>
          <div className="max-w-2xl space-y-5 text-white/60">
            <h2 className="text-xl font-semibold text-white">Where it&apos;s headed</h2>
            <p>
              Next on the roadmap: a durable job queue and persistent storage, baseline and
              regression detection, organizations and role-based access, webhooks, and
              first-party JavaScript and TypeScript SDKs generated from one OpenAPI spec.
              We build in the open — the source and full changelog are on GitHub.
            </p>
          </div>
        </Reveal>
      </section>
      <Cta />
    </>
  );
}
