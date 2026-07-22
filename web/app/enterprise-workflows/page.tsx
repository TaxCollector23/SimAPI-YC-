import type { Metadata } from "next";
import { ScanSearch, ShieldAlert, GitBranch, FileCheck2 } from "lucide-react";
import { PageHero } from "@/components/ui/page-hero";
import { Reveal } from "@/components/ui/reveal";
import { SectionHeader } from "@/components/ui/section";
import { Cta } from "@/components/cta";

export const metadata: Metadata = {
  title: "Enterprise Workflows",
  description: "Four production patterns for wiring SimAPI into a simulation pipeline — preflight, post-run QA, CI regression gates, and compliance reporting.",
};

const workflows = [
  {
    icon: ScanSearch,
    phase: "Before the solver runs",
    title: "Pre-flight mesh & setup validation",
    goal: "Catch geometry and boundary-condition errors before they burn solver time.",
    steps: [
      "Upload mesh (STL, STEP, CGNS) or setup config",
      "POST /v1/validate/setup — mesh quality, BC coverage, solver config checks",
      "Fix flagged issues, or proceed with a documented confidence score",
    ],
  },
  {
    icon: ShieldAlert,
    phase: "After the solver converges",
    title: "Post-run result validation",
    goal: "Flag anomalous or corrupted output before it reaches analysis or an ML pipeline.",
    steps: [
      "Export results (CSV, netCDF, JSON) from the solver",
      "POST /v1/validate — 1300+ physics checks plus AI review",
      "Route clean trials downstream; hold flagged ones for review",
    ],
  },
  {
    icon: GitBranch,
    phase: "On every commit",
    title: "CI regression gating",
    goal: "Detect unintended drift from solver upgrades, config changes, or mesh regressions.",
    steps: [
      "Wire the CLI into GitHub Actions, GitLab CI, or Jenkins",
      "Run the validation suite against a frozen reference config",
      "Block the merge if precision, recall, or exclusion rate regresses",
    ],
  },
  {
    icon: FileCheck2,
    phase: "For regulated domains",
    title: "Compliance & audit trail",
    goal: "Produce a defensible record of what was checked, and why a result was accepted or excluded.",
    steps: [
      "Validate every dataset that feeds a submission package",
      "Export the validation report (checks run, bounds, exclusions)",
      "Archive alongside the design record for audit and traceability",
    ],
  },
];

const patterns = [
  { title: "Synchronous", desc: "POST → validate → response in the same request. Best for interactive review UIs.", tech: "HTTP POST" },
  { title: "Asynchronous", desc: "Queue a job, poll for the result. Fits high-volume batch runs.", tech: "Job queue + polling" },
  { title: "Embedded", desc: "Import the engine directly into a pipeline script — no network hop.", tech: "Python / Node SDK" },
  { title: "Plugin", desc: "Post-processing hook inside the solver itself (OpenFOAM, ANSYS, COMSOL).", tech: "CLI / Docker sidecar" },
];

export default function EnterpriseWorkflows() {
  return (
    <>
      <PageHero
        eyebrow="Enterprise"
        title={<>Four patterns for putting SimAPI in the loop</>}
        lede="These are the integration points teams actually use — before the solver runs, after it finishes, on every commit, and when a result needs a paper trail."
      />

      <section className="container-tight pb-8">
        <div className="grid gap-4 sm:grid-cols-2">
          {workflows.map((w, i) => (
            <Reveal key={w.title} delay={i * 0.05}>
              <div className="h-full rounded-2xl border border-white/[0.08] bg-ink-900/50 p-6">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/[0.03]">
                    <w.icon className="h-5 w-5 text-accent-cyan" />
                  </div>
                  <span className="text-xs uppercase tracking-[0.1em] text-white/40">{w.phase}</span>
                </div>
                <h3 className="mt-4 text-[17px] font-semibold text-white">{w.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-white/50">{w.goal}</p>
                <ol className="mt-4 space-y-2 border-t border-white/[0.06] pt-4">
                  {w.steps.map((s, j) => (
                    <li key={j} className="flex gap-3 text-sm text-white/60">
                      <span className="shrink-0 text-white/30 tabular-nums">{j + 1}.</span>
                      {s}
                    </li>
                  ))}
                </ol>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      <section className="py-16 sm:py-20">
        <div className="container-tight">
          <SectionHeader
            eyebrow="Integration patterns"
            title={<>Wire it in however your stack works</>}
            lede="No single pattern fits every pipeline — pick the one that matches your latency and infrastructure constraints."
          />
          <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {patterns.map((p) => (
              <div key={p.title} className="rounded-2xl border border-white/[0.07] bg-white/[0.02] p-5">
                <h3 className="text-sm font-semibold text-white">{p.title}</h3>
                <p className="mt-2 text-xs leading-relaxed text-white/50">{p.desc}</p>
                <div className="mt-3 text-[11px] font-mono text-accent-cyan/80">{p.tech}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <Cta />
    </>
  );
}
