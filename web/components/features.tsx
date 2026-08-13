import { SectionHeader } from "./ui/section";

/*
 * Editorial features index. No cards, no icons, no hover-glow orbs, no
 * "AI-assisted validation" bullet — those are the tells the theme
 * experiment is trying to erase. This is a numbered two-column list,
 * with hairline dividers and a monospace ordinal on the left. Reads
 * like a documentation index or a table of contents.
 */

const items: Array<{ title: string; desc: string }> = [
  {
    title: "Deterministic physics validation",
    desc: "287 rule-based checks across 21 domains: bounds, conservation laws, dimensional and cross-variable consistency.",
  },
  {
    title: "Dimensional-analysis engine",
    desc: "Discovers Buckingham-π groups and anchors them to physical constants; catches wrong-unit subsets by shared-factor clustering.",
  },
  {
    title: "Regression detection",
    desc: "Compare against a baseline and flag when a new run drifts outside expected envelopes.",
  },
  {
    title: "Simulation diffing",
    desc: "Field-level and statistical diffs between two runs, surfaced as a structured report.",
  },
  {
    title: "CI/CD integration",
    desc: "Gate merges and deploys on validation status. GitHub Actions ships today; GitLab and Jenkins compatible.",
  },
  {
    title: "Historical analysis",
    desc: "Track validation trends across thousands of runs to spot slow degradation early.",
  },
  {
    title: "Batch validation",
    desc: "Validate entire sweeps and datasets in parallel with per-trial exclusion accounting.",
  },
  {
    title: "Plugin system",
    desc: "Register custom validators and organization-specific rules in a typed rule engine.",
  },
  {
    title: "API-first architecture",
    desc: "Everything is an endpoint. Consistent schemas, stable error codes, request IDs.",
  },
  {
    title: "First-class SDKs",
    desc: "Python and Node today, generated from one OpenAPI spec.",
  },
  {
    title: "Enterprise security",
    desc: "API keys, rate limiting, audit logs, SSO, and private deployments for regulated teams.",
  },
];

export function Features() {
  return (
    <section id="features" className="relative py-24 sm:py-32">
      <div className="container-tight">
        <SectionHeader
          eyebrow="Platform"
          title={<>Everything you need to trust a simulation</>}
          lede="A complete validation layer — deterministic where it can be, intelligent where it must be."
        />

        <ul className="mt-14 divide-y divide-white/[0.06] border-y border-white/[0.06]">
          {items.map((f, i) => (
            <li
              key={f.title}
              className="grid grid-cols-[3rem_1fr] gap-x-6 gap-y-2 py-5 sm:grid-cols-[3.5rem_18rem_1fr] sm:py-6"
            >
              <span className="font-mono text-xs tabular-nums text-white/35">
                {String(i + 1).padStart(2, "0")}
              </span>
              <h3 className="text-[15px] font-medium text-white">{f.title}</h3>
              <p className="col-span-2 text-sm leading-relaxed text-white/55 sm:col-span-1">
                {f.desc}
              </p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
