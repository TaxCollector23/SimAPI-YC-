import type { Metadata } from "next";
import Link from "next/link";
import { Database, GitBranch, FileCheck2, Bot } from "lucide-react";
import { PageHero } from "@/components/ui/page-hero";
import { Reveal } from "@/components/ui/reveal";
import { Cta } from "@/components/cta";

export const metadata: Metadata = {
  title: "Use Cases",
  description:
    "Four places SimAPI's validation layer belongs in a simulation pipeline: ML training-data QA, CI gates, regulatory pre-checks, and autonomy/robotics validation.",
};

interface UseCase {
  icon: typeof Database;
  domain: string;
  title: string;
  problem: string;
  approach: string;
  engine: string;
  endpoint: string;
}

const cases: UseCase[] = [
  {
    icon: Database,
    domain: "Surrogate & ML models",
    title: "Pre-training data QA",
    problem:
      "A surrogate model is only as trustworthy as the sweep it learns from. A single Pa-vs-kPa unit error or a block of solver-divergence spikes is enough to bias a drag-coefficient regressor — and nothing in the CSV looks obviously wrong.",
    approach:
      "Validate every dataset before it enters the training set. Impossible rows (a definitional bound broken, an anchored constant violated) are removed with a per-row reason; borderline rows are flagged for a human rather than silently dropped. The response carries a training_ready flag your data loader can branch on.",
    engine: "Dimensional-analysis cascade + physics rule engine",
    endpoint: "POST /v1/validate",
  },
  {
    icon: GitBranch,
    domain: "Simulation pipelines",
    title: "CI gates on every run",
    problem:
      "Solver upgrades, mesh regressions, and post-processing script changes introduce corruption that no unit test catches — because the pipeline still produces a well-formed CSV, just a physically wrong one.",
    approach:
      "Run the CLI in CI and gate the build on the verdict. The GitHub Action wraps simapi-cli with an exit-code contract: physics violations fail the build, review-tier findings surface as an annotated report, and a SARIF file feeds GitHub code scanning. Pin a stable config key to track drift across runs.",
    engine: "CLI exit codes (validate / dimensional --fail-on)",
    endpoint: "integrations/github-action",
  },
  {
    icon: FileCheck2,
    domain: "Regulated submissions",
    title: "Pre-submission checks",
    problem:
      "Data that feeds a certification package has to be defensible. 'It looked right' is not an audit trail, and discovering a dimensional inconsistency after submission is expensive.",
    approach:
      "Validate each dataset and attach the report to the design record. Every finding cites the exact check, value, and bound it crossed. The compliance layer emits a signed, timestamped report with a SHA-256 hash of both the data and the report, mapped to ISO 26262 (Part 6), DO-178C, FDA 21 CFR Part 11, and NHTSA AV guidance.",
    engine: "Physics engine + compliance report generator",
    endpoint: "core/compliance.py",
  },
  {
    icon: Bot,
    domain: "Autonomy & robotics",
    title: "Sim validation for control stacks",
    problem:
      "Robotics and autonomy teams train and test controllers against simulated dynamics. If the simulator emits states that violate kinematic or energy constraints, the policy learns to exploit a bug, not the physics.",
    approach:
      "Validate rollouts against the robotics domain's plausibility bounds, conservation relations, and cross-variable checks. Declared operating conditions (mass, velocity, actuator limits) become testable assertions the run must satisfy, so a physically impossible trajectory is caught before it shapes a policy.",
    engine: "Physics rule engine (robotics domain) + declared conditions",
    endpoint: "POST /v1/validate/dimensional",
  },
];

export default function UseCases() {
  return (
    <>
      <PageHero
        title={<>Four places validation earns its keep</>}
        lede="Not case studies with numbers we can't stand behind — the actual points in a simulation pipeline where teams put a physics check, and which part of the engine does the work at each one."
      />

      <section className="container-tight pb-16">
        <div className="border-t border-white/10">
          {cases.map((c, i) => (
            <Reveal key={c.title} delay={i * 0.04}>
              <div className="grid gap-6 border-b border-white/10 py-8 sm:grid-cols-[240px_1fr]">
                <div>
                  <div className="flex h-9 w-9 items-center justify-center border border-white/10">
                    <c.icon className="h-4 w-4 text-accent-blue" />
                  </div>
                  <div className="mt-3 text-xs uppercase tracking-[0.12em] text-white/40">
                    {c.domain}
                  </div>
                  <h2 className="mt-1 text-lg font-semibold text-white">{c.title}</h2>
                </div>
                <div className="space-y-4">
                  <div>
                    <div className="text-xs font-medium uppercase tracking-[0.08em] text-white/35">
                      The failure it catches
                    </div>
                    <p className="mt-1.5 text-sm leading-relaxed text-white/65">{c.problem}</p>
                  </div>
                  <div>
                    <div className="text-xs font-medium uppercase tracking-[0.08em] text-white/35">
                      How SimAPI fits
                    </div>
                    <p className="mt-1.5 text-sm leading-relaxed text-white/65">{c.approach}</p>
                  </div>
                  <div className="flex flex-wrap gap-x-8 gap-y-2 pt-1 text-xs">
                    <span className="text-white/40">
                      Engine:{" "}
                      <span className="text-white/70">{c.engine}</span>
                    </span>
                    <span className="text-white/40">
                      Entry point:{" "}
                      <code className="font-mono text-accent-blue">{c.endpoint}</code>
                    </span>
                  </div>
                </div>
              </div>
            </Reveal>
          ))}
        </div>

        <p className="mt-8 max-w-2xl text-sm leading-relaxed text-white/50">
          Every domain listed spans the same 21 simulation types — aerodynamics, fluid dynamics,
          structural, thermodynamics, robotics, combustion, electromagnetics, and the rest. See the{" "}
          <Link href="/platform" className="text-accent-blue underline underline-offset-2">
            platform
          </Link>{" "}
          for how the engines fit together, or the{" "}
          <Link href="/docs" className="text-accent-blue underline underline-offset-2">
            docs
          </Link>{" "}
          to wire one of these in.
        </p>
      </section>

      <Cta />
    </>
  );
}
