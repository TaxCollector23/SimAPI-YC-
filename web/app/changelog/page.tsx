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
    version: "3.4", date: "July 2026", tag: "Honesty",
    items: [
      "Re-audited every benchmark claim end-to-end — see the new methodology page at /benchmark for the full write-up, including where SimAPI does NOT help (gradient-boosted trees) and where naive IQR/z-score filtering is competitive.",
      "Corrected the recall figure from the previous release: with randomized corruption placement and Mann-Kendall + sliding-window drift detection, recall is 71% (up from 55%), not the previously stated 89% — that number didn't hold up under a harder, randomized benchmark and we're not keeping it on the site.",
      "Exclusion precision holds at 99% — when SimAPI flags a trial, it's genuinely corrupted.",
      "Added a naive statistical baseline (IQR + z-score) to every benchmark run so the comparison isn't just \"vs. no filtering.\"",
      "New AI orchestrator: a 5-phase pipeline (dataset profiling → physics checks → pattern recognition → targeted follow-up probes → synthesis) replaces the single-pass AI reviewer.",
      "New automatic-repair layer (deterministic, reversible): duplicate rows, missing/duplicate IDs, out-of-order timestamps, wrapped angles, short NaN gaps — with a preview before anything is applied. `simapi repair <file> [--apply]` in both CLIs.",
      "Multi-format ingestion: YAML, TOML, TXT, and Markdown join CSV/JSON/VTK/NumPy/OpenFOAM.",
      "`simapi doctor [--fix]` and `simapi explain` added to both CLIs — real environment diagnostics and per-issue explanations, not stubs.",
      "Fixed a real bug where the deployed site's \"Full engine\" health check queried the wrong path and could never report a connected Python backend.",
      "Fixed Firebase session persistence: added the missing onIdTokenChanged listener so login state and token refresh track Firebase's actual session instead of a stale local cache.",
    ],
  },
  {
    version: "3.3", date: "July 2026", tag: "Detection",
    items: [
      "Relationship-drift detector: catches sensor drift that breaks a physical ratio (Re/v, Ma/v, P/ρ) even when the raw column looks stationary.",
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
