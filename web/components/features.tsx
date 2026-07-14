"use client";

import { motion } from "framer-motion";
import {
  Cpu,
  Sparkles,
  GitCompare,
  Layers,
  GitBranch,
  History,
  Boxes,
  Puzzle,
  Plug,
  Code2,
  Lock,
} from "lucide-react";
import { SectionHeader } from "./ui/section";

const features = [
  { icon: Cpu, title: "Deterministic physics validation", desc: "287 rule-based checks across 21 domains: bounds, conservation laws, dimensional and cross-variable consistency." },
  { icon: Sparkles, title: "AI-assisted validation", desc: "A second-pass LLM reviews full distributions to catch what rules miss — magnitude realism, provenance artifacts, ML-readiness." },
  { icon: GitBranch, title: "Regression detection", desc: "Compare against a baseline and flag when a new run drifts outside expected envelopes." },
  { icon: GitCompare, title: "Simulation diffing", desc: "Field-level and statistical diffs between two runs, surfaced as a structured report." },
  { icon: Plug, title: "CI/CD integration", desc: "Gate merges and deploys on validation status. GitHub Actions, GitLab, and Jenkins ready." },
  { icon: History, title: "Historical analysis", desc: "Track validation trends across thousands of runs to spot slow degradation early." },
  { icon: Boxes, title: "Batch validation", desc: "Validate entire sweeps and datasets in parallel with per-trial exclusion accounting." },
  { icon: Puzzle, title: "Plugin system", desc: "Register custom validators and organization-specific rules in a typed rule engine." },
  { icon: Code2, title: "API-first architecture", desc: "Everything is an endpoint. Consistent schemas, stable error codes, request IDs." },
  { icon: Layers, title: "First-class SDKs", desc: "Python today; JavaScript and TypeScript in progress, generated from one OpenAPI spec." },
  { icon: Lock, title: "Enterprise security", desc: "API keys, rate limiting, audit logs, SSO, and private deployments for regulated teams." },
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

        <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f, i) => (
            <motion.div
              key={f.title}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ delay: (i % 3) * 0.06, duration: 0.5 }}
              className="group relative overflow-hidden rounded-2xl border border-white/[0.07] bg-ink-900/50 p-6 transition-colors hover:border-white/15"
            >
              <div className="pointer-events-none absolute -right-16 -top-16 h-32 w-32 rounded-full bg-accent-blue/10 opacity-0 blur-2xl transition-opacity group-hover:opacity-100" />
              <h3 className="text-[15px] font-semibold text-white">{f.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-white/50">{f.desc}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
