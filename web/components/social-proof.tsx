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
          eyebrow="Fits your stack"
          title={<>Works with the tools you already run</>}
          lede="SimAPI is an HTTP API. Call it from a CI pipeline, a data job, or a notebook — validation slots in between your solver and everything downstream."
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
      </div>
    </section>
  );
}
