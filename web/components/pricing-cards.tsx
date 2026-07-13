"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

const tiers = [
  {
    name: "Developer",
    price: "Free",
    cadence: "",
    blurb: "For individuals and early prototypes.",
    cta: "Get API Key",
    href: "/contact",
    featured: false,
    features: [
      "5,000 validations / month",
      "All 21 simulation domains",
      "Deterministic physics engine",
      "Python SDK + REST API",
      "Community support",
    ],
  },
  {
    name: "Startup",
    price: "$299",
    cadence: "/mo",
    blurb: "For teams shipping simulations to production.",
    cta: "Start free trial",
    href: "/contact",
    featured: true,
    features: [
      "250,000 validations / month",
      "AI reasoning layer",
      "Regression + baseline detection",
      "CI/CD integrations",
      "Validation history & trends",
      "Priority email support",
    ],
  },
  {
    name: "Enterprise",
    price: "Custom",
    cadence: "",
    blurb: "For regulated and large-scale engineering orgs.",
    cta: "Contact sales",
    href: "/contact",
    featured: false,
    features: [
      "Unlimited validations",
      "Private / air-gapped deployment",
      "SSO (SAML / OIDC)",
      "Audit logs",
      "Custom validators & rule engine",
      "Dedicated support + SLA",
    ],
  },
];

export function PricingCards() {
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      {tiers.map((t, i) => (
        <motion.div
          key={t.name}
          initial={{ opacity: 0, y: 18 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: i * 0.08, duration: 0.5 }}
          className={cn(
            "relative flex flex-col rounded-3xl border p-7",
            t.featured
              ? "border-accent-blue/40 bg-ink-900/70 shadow-glow"
              : "border-white/[0.08] bg-ink-900/40",
          )}
        >
          {t.featured && (
            <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-accent-gradient px-3 py-1 text-[11px] font-semibold text-white">
              Most popular
            </span>
          )}
          <h3 className="text-sm font-semibold uppercase tracking-wide text-white/60">{t.name}</h3>
          <div className="mt-4 flex items-end gap-1">
            <span className="text-4xl font-semibold text-white">{t.price}</span>
            {t.cadence && <span className="pb-1 text-sm text-white/40">{t.cadence}</span>}
          </div>
          <p className="mt-2 text-sm text-white/50">{t.blurb}</p>
          <Link
            href={t.href}
            className={cn("mt-6", t.featured ? "btn-accent" : "btn-ghost", "w-full")}
          >
            {t.cta}
          </Link>
          <ul className="mt-7 space-y-3">
            {t.features.map((f) => (
              <li key={f} className="flex items-start gap-2.5 text-sm text-white/60">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-pass" />
                {f}
              </li>
            ))}
          </ul>
        </motion.div>
      ))}
    </div>
  );
}
