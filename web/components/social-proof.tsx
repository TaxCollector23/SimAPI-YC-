"use client";

import { SectionHeader } from "./ui/section";
import { Reveal } from "./ui/reveal";

const integrations = [
  "GitHub", "GitLab", "Jenkins", "Docker", "AWS", "Azure",
  "Google Cloud", "Kubernetes", "Airflow", "MLflow",
];

export function SocialProof() {
  return (
    <section className="relative py-24 sm:py-32">
      <div className="container-tight">
        <SectionHeader
          eyebrow="Ecosystem"
          title={<>Built for modern engineering teams</>}
          lede="Designed for CFD, FEA, robotics, and scientific-computing workflows — and ready for enterprise deployment. It plugs into the tools you already run."
        />

        {/* Integrations */}
        <Reveal className="mt-12">
          <div className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-white/[0.07] bg-white/[0.04] sm:grid-cols-3 lg:grid-cols-5">
            {integrations.map((name) => (
              <div
                key={name}
                className="flex items-center justify-center bg-ink-950 px-4 py-8 text-sm font-medium text-white/45 transition-colors hover:text-white"
              >
                {name}
              </div>
            ))}
          </div>
        </Reveal>

        {/* Design partner placeholders — clearly marked */}
        <div className="mt-14">
          <p className="mb-4 text-center text-xs uppercase tracking-[0.18em] text-white/35">
            Design partner program · onboarding now
          </p>
          <div className="grid gap-4 sm:grid-cols-3">
            {[1, 2, 3].map((n) => (
              <Reveal key={n} delay={n * 0.05}>
                <div className="flex h-32 flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-white/12 bg-ink-900/40">
                  <div className="h-8 w-8 rounded-lg bg-white/[0.05]" />
                  <span className="text-xs text-white/30">Your team here</span>
                  <span className="text-[10px] uppercase tracking-wider text-white/20">
                    Placeholder
                  </span>
                </div>
              </Reveal>
            ))}
          </div>
          <p className="mt-4 text-center text-xs text-white/30">
            We don&apos;t fake logos or testimonials. These slots fill in as real design
            partners come on board.
          </p>
        </div>
      </div>
    </section>
  );
}
