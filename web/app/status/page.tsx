import type { Metadata } from "next";
import { PageHero } from "@/components/ui/page-hero";
import { CheckCircle2 } from "lucide-react";

export const metadata: Metadata = {
  title: "Status",
  description: "Real-time operational status for the SimAPI platform.",
};

const services = [
  { name: "Validation API", uptime: "99.98%" },
  { name: "AI reasoning layer", uptime: "99.95%" },
  { name: "Dashboard & reports", uptime: "99.99%" },
  { name: "Webhooks", uptime: "99.97%" },
  { name: "Documentation", uptime: "100.0%" },
];

// Deterministic 90-day history (all operational for the demo).
const days = Array.from({ length: 90 });

export default function StatusPage() {
  return (
    <>
      <PageHero
        eyebrow="Status"
        title={<>All systems operational</>}
        lede="Live operational status across the SimAPI platform, updated continuously."
      >
        <div className="mt-2 flex items-center gap-2 text-sm text-pass">
          <span className="h-2.5 w-2.5 rounded-full bg-pass animate-pulse-soft" />
          Operational · 99.98% uptime over 90 days
        </div>
      </PageHero>

      <section className="container-tight space-y-3 pb-24">
        {services.map((s) => (
          <div key={s.name} className="rounded-2xl border border-white/[0.07] bg-ink-900/50 p-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-pass" />
                <span className="text-sm font-medium text-white">{s.name}</span>
              </div>
              <span className="text-xs text-white/45">{s.uptime} uptime</span>
            </div>
            <div className="mt-4 flex gap-[3px]">
              {days.map((_, i) => (
                <div
                  key={i}
                  className="h-7 flex-1 rounded-[2px] bg-pass/70"
                  title="Operational"
                />
              ))}
            </div>
            <div className="mt-2 flex justify-between text-[10px] text-white/30">
              <span>90 days ago</span>
              <span>Today</span>
            </div>
          </div>
        ))}
      </section>
    </>
  );
}
