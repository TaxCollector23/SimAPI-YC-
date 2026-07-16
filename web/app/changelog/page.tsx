import type { Metadata } from "next";
import { PageHero } from "@/components/ui/page-hero";
import { Reveal } from "@/components/ui/reveal";

export const metadata: Metadata = {
  title: "Changelog",
  description: "What's new in SimAPI — releases, new checks, and platform improvements.",
};

interface Release { version: string; date: string; tag: string; items: string[] }

const releases: Release[] = [
  {
    version: "3.3", date: "July 2026", tag: "Detection",
    items: [
      "Relationship-drift detector: catches sensor drift that breaks a physical ratio (Re/v, Ma/v, P/ρ) even when the raw column looks stationary. Corruption recall 55% → 89%.",
      "CUSUM change-point layer for gradual drift in low-noise channels.",
      "Validation engine expanded past 400 deterministic checks across 21 domains.",
    ],
  },
  {
    version: "3.2", date: "July 2026", tag: "Platform",
    items: [
      "Pre-flight validation: judge a mesh + solver + physics setup before the run and predict which output checks will fail, with a why and a fix for each.",
      "Geometric mesh upload (STL) with real watertight / open-edge analysis.",
      "Historical run comparison — diff two runs for resolved / introduced / persisting issues.",
    ],
  },
  {
    version: "3.1", date: "July 2026", tag: "AI",
    items: [
      "AI second-pass reviewer is now data-aware — fed per-column statistics, correlations, and sample rows.",
      "Honest benchmark methodology: multi-seed with error bars and absolute before/after MAPE.",
    ],
  },
  {
    version: "3.0", date: "June 2026", tag: "Launch",
    items: [
      "Public validation API, in-browser dashboard, and CLI.",
      "Python & Node SDKs; Homebrew, curl, and PowerShell installers.",
      "287+ deterministic physics checks across 21 simulation domains.",
    ],
  },
];

export default function ChangelogPage() {
  return (
    <>
      <PageHero eyebrow="Changelog" title={<>What&apos;s new</>} lede="Every release, new check, and platform improvement — newest first." />
      <section className="container-tight pb-24">
        <div className="relative border-l border-white/[0.08] pl-8">
          {releases.map((r, i) => (
            <Reveal key={r.version} delay={i * 0.04}>
              <div className="relative mb-10">
                <span className="absolute -left-[38px] top-1 h-3 w-3 rounded-full border-2 border-accent-cyan bg-ink-950" />
                <div className="flex items-center gap-3">
                  <h2 className="text-xl font-semibold text-white">v{r.version}</h2>
                  <span className="rounded-full border border-white/10 px-2.5 py-0.5 text-[11px] text-white/50">{r.tag}</span>
                  <span className="text-xs text-white/35">{r.date}</span>
                </div>
                <ul className="mt-3 space-y-2">
                  {r.items.map((it, j) => (
                    <li key={j} className="flex items-start gap-2.5 text-sm leading-relaxed text-white/55">
                      <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-accent-cyan" /> {it}
                    </li>
                  ))}
                </ul>
              </div>
            </Reveal>
          ))}
        </div>
      </section>
    </>
  );
}
