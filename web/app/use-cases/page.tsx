import type { Metadata } from "next";
import { Plane, Battery, Cpu, Building2, FlaskConical } from "lucide-react";
import { PageHero } from "@/components/ui/page-hero";
import { Reveal } from "@/components/ui/reveal";
import { Cta } from "@/components/cta";

export const metadata: Metadata = {
  title: "Use Cases",
  description: "How teams use SimAPI's validation layer across aerospace, automotive, semiconductor, structural, and research simulation pipelines.",
};

const cases = [
  {
    icon: Plane,
    domain: "Aerospace & defense",
    workflow: "Pre-flight mesh validation",
    problem: "Mesh generation bugs produce invalid CFD results, and manual mesh inspection is slow.",
    approach: "Run preflight checks — watertightness, BC coverage, solver config — before the solver starts.",
    benefits: [
      "30+ automated mesh quality checks",
      "Solver restarts avoided when mesh is validated first",
      "Confidence score carried into the design record",
    ],
  },
  {
    icon: Battery,
    domain: "Automotive & energy",
    workflow: "Thermal & electrochemical QA",
    problem: "Batch simulation jobs occasionally produce NaN, divergence, or unit-error results that need manual triage.",
    approach: "Validate every trial post-solver; the engine flags and explains what it excluded.",
    benefits: [
      "11+ corruption types detected automatically",
      "99% precision on flagged exclusions",
      "Plain-language explanation for every flag",
    ],
  },
  {
    icon: Cpu,
    domain: "Semiconductors & photonics",
    workflow: "Design-iteration regression testing",
    problem: "Optical and EM simulations have no automated QA — a bad result can reach a tape-out decision.",
    approach: "Validate on every design iteration inside CI, and diff against the last known-good run.",
    benefits: [
      "Catches corrupted datasets that pass visual inspection",
      "Regression testing across solver/library upgrades",
      "Validation history attached to each design review",
    ],
  },
  {
    icon: Building2,
    domain: "Civil & structural",
    workflow: "Cross-team validation standard",
    problem: "Independent teams run FEA with drifting assumptions, producing inconsistent results across a firm.",
    approach: "Set one validation policy — no model ships to a client without a passing SimAPI run.",
    benefits: [
      "Catches unit mismatches and BC inconsistencies early",
      "One shared standard across disciplines",
      "Audit trail attached to every client deliverable",
    ],
  },
  {
    icon: FlaskConical,
    domain: "Research & academia",
    workflow: "Publication-ready validation",
    problem: "MD and computational chemistry runs have high outlier rates — hard to tell a bug from a rare event.",
    approach: "The AI layer classifies anomalies (divergence vs. plausible rare physics) and the log ships with the paper.",
    benefits: [
      "Automated detection of clear simulation failures",
      "Interpretable reasoning, not just a flag",
      "Reproducible validation methodology for peer review",
    ],
  },
];

export default function UseCases() {
  return (
    <>
      <PageHero
        eyebrow="Use cases"
        title={<>Where the validation layer earns its keep</>}
        lede="Five workflows, drawn from where teams actually place SimAPI in a simulation pipeline — not hypothetical, not case studies with numbers we can't stand behind."
      />

      <section className="container-tight pb-16">
        <div className="grid gap-4">
          {cases.map((c, i) => (
            <Reveal key={c.workflow} delay={i * 0.04}>
              <div className="grid gap-6 rounded-2xl border border-white/[0.08] bg-ink-900/50 p-6 sm:grid-cols-[220px_1fr] sm:p-8">
                <div>
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.03]">
                    <c.icon className="h-5 w-5 text-accent-cyan" />
                  </div>
                  <div className="mt-3 text-xs uppercase tracking-[0.1em] text-white/40">{c.domain}</div>
                  <h3 className="mt-1 text-[17px] font-semibold text-white">{c.workflow}</h3>
                </div>
                <div className="grid gap-4 border-t border-white/[0.06] pt-5 sm:border-l sm:border-t-0 sm:pl-6 sm:pt-0">
                  <div>
                    <div className="text-xs font-medium uppercase tracking-[0.08em] text-white/35">Challenge</div>
                    <p className="mt-1.5 text-sm leading-relaxed text-white/60">{c.problem}</p>
                  </div>
                  <div>
                    <div className="text-xs font-medium uppercase tracking-[0.08em] text-white/35">Approach</div>
                    <p className="mt-1.5 text-sm leading-relaxed text-white/60">{c.approach}</p>
                  </div>
                  <div>
                    <div className="text-xs font-medium uppercase tracking-[0.08em] text-white/35">Benefits</div>
                    <ul className="mt-1.5 space-y-1.5">
                      {c.benefits.map((b, j) => (
                        <li key={j} className="flex gap-2 text-sm text-white/60">
                          <span className="text-accent-cyan/70">—</span>
                          {b}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      <Cta />
    </>
  );
}
