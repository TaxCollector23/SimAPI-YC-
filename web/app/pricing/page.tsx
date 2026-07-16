import type { Metadata } from "next";
import Link from "next/link";
import { Check } from "lucide-react";
import { PageHero } from "@/components/ui/page-hero";
import { Reveal } from "@/components/ui/reveal";
import { Cta } from "@/components/cta";

export const metadata: Metadata = {
  title: "Pricing",
  description: "SimAPI pricing — a free tier for individuals, usage-based Developer plan, and Enterprise for regulated teams.",
};

const tiers = [
  {
    name: "Free",
    price: "$0",
    unit: "forever",
    blurb: "For individuals and evaluation.",
    cta: "Get an API key", href: "/dashboard",
    features: ["5,000 validations / month", "All 400+ deterministic checks", "In-browser validator + pre-flight", "CLI, Python & Node SDKs", "Community support"],
  },
  {
    name: "Developer",
    price: "$49",
    unit: "/ month",
    blurb: "For teams shipping to production.",
    highlight: true,
    cta: "Start free trial", href: "/dashboard",
    features: ["250,000 validations / month", "AI second-pass review", "Historical run diffs", "CI/CD gating + webhooks", "Priority email support", "99.9% uptime SLA target"],
  },
  {
    name: "Enterprise",
    price: "Custom",
    unit: "",
    blurb: "For regulated & large-scale teams.",
    cta: "Contact sales", href: "/security",
    features: ["Unlimited validations", "Self-hosted / VPC deployment", "SSO + audit logs + RBAC", "Custom rule packs per domain", "Dedicated support + onboarding", "Security review & DPA"],
  },
];

export default function PricingPage() {
  return (
    <>
      <PageHero
        eyebrow="Pricing"
        title={<>Priced per validation, not per seat</>}
        lede="Start free. Scale when your pipelines do. Every plan runs the full validation engine — higher tiers add AI review, CI gating, and enterprise controls."
      />
      <section className="container-tight pb-16">
        <div className="grid gap-5 lg:grid-cols-3">
          {tiers.map((t, i) => (
            <Reveal key={t.name} delay={i * 0.05}>
              <div className={`flex h-full flex-col rounded-2xl border p-7 ${t.highlight ? "border-accent-blue/40 bg-accent-blue/[0.06]" : "border-white/[0.08] bg-ink-900/50"}`}>
                {t.highlight && <span className="mb-3 w-fit rounded-full bg-accent-blue/20 px-2.5 py-0.5 text-[11px] font-medium text-accent-cyan">Most popular</span>}
                <h3 className="text-lg font-semibold text-white">{t.name}</h3>
                <p className="mt-1 text-sm text-white/45">{t.blurb}</p>
                <p className="mt-5 flex items-baseline gap-1.5">
                  <span className="text-4xl font-semibold text-white">{t.price}</span>
                  <span className="text-sm text-white/40">{t.unit}</span>
                </p>
                <Link href={t.href} className={`mt-6 ${t.highlight ? "btn-accent" : "btn-ghost"} w-full justify-center`}>{t.cta}</Link>
                <ul className="mt-6 space-y-2.5">
                  {t.features.map((f) => (
                    <li key={f} className="flex items-start gap-2.5 text-sm text-white/60">
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-pass" /> {f}
                    </li>
                  ))}
                </ul>
              </div>
            </Reveal>
          ))}
        </div>
        <p className="mt-8 text-center text-xs text-white/35">
          Prices are indicative for the launch. The public demo endpoint is free and unauthenticated for evaluation.
        </p>
      </section>
      <Cta />
    </>
  );
}
