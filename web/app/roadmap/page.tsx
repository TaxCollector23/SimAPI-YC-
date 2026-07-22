import type { Metadata } from "next";
import { PageHero } from "@/components/ui/page-hero";
import { Reveal } from "@/components/ui/reveal";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Roadmap",
  description: "What's shipped, in progress, and planned for SimAPI — an honest accounting, not a marketing wishlist.",
};

type Status = "shipped" | "in-progress" | "planned";

interface Item { title: string; detail: string; status: Status }

const items: Item[] = [
  { status: "shipped", title: "1300+ deterministic physics checks across 21 domains", detail: "core/physics_validator.py — the full engine, live on the deployed site via the self-hosted Python backend." },
  { status: "shipped", title: "Honest, reproducible benchmarks", detail: "5-seed, randomized-corruption benchmark with a naive-baseline comparison and a published methodology page — see /benchmark." },
  { status: "shipped", title: "Mann-Kendall + sliding-window sensor drift detection", detail: "Pushed corruption recall from 55% to 71% on the harder, randomized benchmark." },
  { status: "shipped", title: "Multi-phase AI orchestrator", detail: "Dataset profiling → physics checks → pattern recognition → targeted follow-up probes → synthesis, via OpenRouter." },
  { status: "shipped", title: "Automatic repair layer", detail: "Deterministic, reversible fixes (duplicate rows, IDs, timestamp ordering, wrapped angles, short NaN gaps) with a preview before anything is applied." },
  { status: "shipped", title: "Multi-format ingestion", detail: "CSV, JSON, YAML, TOML, TXT, Markdown, VTK, NumPy, and OpenFOAM all normalize into one internal schema." },
  { status: "shipped", title: "Pre-flight mesh/setup validation", detail: "Predicts likely output-check failures before a simulation runs, with plain-English explanations and config-specific fixes." },
  { status: "shipped", title: "CLI parity across Python and Node", detail: "login, validate, watch, doctor, explain, repair, api-key, config, usage — identical behavior in both implementations." },
  { status: "shipped", title: "Dashboard: Analytics, Logs, Request Inspector", detail: "All backed by real captured validation runs from this browser — no seeded or synthetic data." },
  { status: "shipped", title: "Hybrid TypeScript/Python engine on the deployed site", detail: "PYTHON_API_URL points the deployed site at the self-hosted Render backend, so the playground and API run the full 1300+ check engine. Falls back to a ~20-check TypeScript engine only if that backend is unreachable. The engine badge in the dashboard tells you which one you're getting." },
  { status: "in-progress", title: "One-click Python backend deployment", detail: "railway.json and render.yaml exist; still validating the one-click flow end-to-end on both platforms." },
  { status: "planned", title: "Durable job storage", detail: "Validation jobs are currently in-memory on the API server. A real queue + persistent store is needed before this can run as a production service with restart safety." },
  { status: "planned", title: "Organizations, projects, and RBAC", detail: "Today's auth model is single-user (a real, password-hashed local browser session). Multi-user orgs need a real backend data model — not on the roadmap until there's a durable store to build it on." },
  { status: "planned", title: "Billing", detail: "No payment provider is integrated. We won't add a fake pricing/billing UI before there's a real Stripe integration behind it." },
  { status: "planned", title: "Webhooks", detail: "Event delivery for validation completion, once job storage is durable enough to guarantee at-least-once delivery." },
  { status: "planned", title: "Plugin rule system", detail: "Let users register custom physics checks without forking core/physics_validator.py." },
];

const statusMeta: Record<Status, { label: string; className: string }> = {
  shipped: { label: "Shipped", className: "bg-pass/15 text-pass" },
  "in-progress": { label: "In progress", className: "bg-warn/15 text-warn" },
  planned: { label: "Planned", className: "bg-white/10 text-white/60" },
};

export default function RoadmapPage() {
  const groups: Status[] = ["shipped", "in-progress", "planned"];
  return (
    <>
      <PageHero
        eyebrow="Roadmap"
        title={<>What&apos;s shipped, what&apos;s next</>}
        lede="An honest accounting of the platform's state — including the things we explicitly haven't built yet, and why."
      />
      <section className="container-tight pb-24">
        <div className="mx-auto max-w-3xl space-y-12">
          {groups.map((status) => (
            <div key={status}>
              <h2 className="mb-4 text-lg font-semibold text-white">{statusMeta[status].label}</h2>
              <div className="space-y-3">
                {items.filter((i) => i.status === status).map((item, i) => (
                  <Reveal key={item.title} delay={i * 0.02}>
                    <div className="rounded-2xl border border-white/[0.07] bg-ink-900/40 p-5">
                      <div className="flex items-start justify-between gap-3">
                        <h3 className="text-sm font-medium text-white">{item.title}</h3>
                        <span className={cn("shrink-0 rounded-full px-2.5 py-0.5 text-[11px]", statusMeta[status].className)}>
                          {statusMeta[status].label}
                        </span>
                      </div>
                      <p className="mt-1.5 text-sm leading-relaxed text-white/50">{item.detail}</p>
                    </div>
                  </Reveal>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
