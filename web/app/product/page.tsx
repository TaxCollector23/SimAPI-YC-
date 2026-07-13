import type { Metadata } from "next";
import { PageHero } from "@/components/ui/page-hero";
import { Features } from "@/components/features";
import { Workflow } from "@/components/workflow";
import { CodeSection } from "@/components/code-section";
import { Cta } from "@/components/cta";

export const metadata: Metadata = {
  title: "Product",
  description:
    "The dual-layer validation engine behind SimAPI: 287 deterministic physics checks across 21 domains plus an AI reasoning layer.",
};

const layers = [
  {
    title: "Deterministic physics engine",
    body: "53 validation layers run 287 checks in under 30ms — plausibility bounds, conservation laws, dimensional analysis, cross-variable relationships, outlier and distribution statistics — tuned per domain across aerodynamics, structural, thermal, robotics, and 17 more.",
    stat: "287 checks · 21 domains",
  },
  {
    title: "AI reasoning layer",
    body: "A second pass reasons over full statistical distributions to surface what rules can't encode: magnitude realism, distribution-shape red flags, dataset-provenance artifacts, and ML-readiness — with a confidence score and concrete recommendations.",
    stat: "Async · non-blocking",
  },
  {
    title: "Production API",
    body: "Auth, rate limiting, request-ID correlation, structured logs, Prometheus metrics, a consistent error contract, and pagination — everything you expect from infrastructure you'd put in a critical path.",
    stat: "Backward-compatible · versioned",
  },
];

export default function ProductPage() {
  return (
    <>
      <PageHero
        eyebrow="Product"
        title={<>Two layers of validation. One verdict you can trust.</>}
        lede="Deterministic where physics is known. Intelligent where judgment is required. Fast enough to sit in your CI."
      />

      <section className="container-tight py-8">
        <div className="grid gap-4 lg:grid-cols-3">
          {layers.map((l) => (
            <div key={l.title} className="rounded-2xl border border-white/[0.07] bg-ink-900/50 p-7">
              <p className="font-mono text-xs text-accent-cyan">{l.stat}</p>
              <h3 className="mt-3 text-lg font-semibold text-white">{l.title}</h3>
              <p className="mt-3 text-sm leading-relaxed text-white/55">{l.body}</p>
            </div>
          ))}
        </div>
      </section>

      <Workflow />
      <Features />
      <CodeSection />
      <Cta />
    </>
  );
}
