import type { Metadata } from "next";
import { Fragment } from "react";
import Link from "next/link";
import { Check, Minus } from "lucide-react";
import { PageHero } from "@/components/ui/page-hero";
import { Reveal } from "@/components/ui/reveal";
import { Cta } from "@/components/cta";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "SimAPI pricing — a free open tier, a Team plan for CI gating and private deployment, and Enterprise for regulated, self-hosted teams.",
};

const tiers = [
  {
    name: "Open",
    price: "Free",
    unit: "",
    blurb: "The hosted API and the full engine, for individuals and evaluation.",
    cta: "Get an API key",
    href: "/dashboard",
    highlight: false,
    points: [
      "Hosted validation API — currently open, no card required",
      "Both deterministic engines, all 21 domains",
      "CLI, Python and Node SDKs",
      "Self-host the MIT-licensed engine with no limits",
      "Community support via GitHub",
    ],
  },
  {
    name: "Team",
    price: "Early access",
    unit: "",
    blurb: "For teams putting validation into a shared pipeline.",
    cta: "Request access",
    href: "mailto:balaji@balajin.net?subject=SimAPI%20Team%20plan",
    highlight: true,
    points: [
      "Private, dedicated deployment (your VPC or ours)",
      "CI gating via the GitHub Action and CLI exit codes",
      "Cross-run history and drift detection",
      "Higher rate limits, tuned per configuration",
      "Priority support and onboarding",
    ],
  },
  {
    name: "Enterprise",
    price: "Talk to us",
    unit: "",
    blurb: "For regulated and air-gapped environments.",
    cta: "Contact us",
    href: "mailto:balaji@balajin.net?subject=SimAPI%20Enterprise",
    highlight: false,
    points: [
      "Self-hosted, fully air-gapped container",
      "Signed, tamper-evident compliance reports",
      "Regulatory mapping: ISO 26262, DO-178C, 21 CFR Part 11",
      "Custom domain rules and units dictionaries",
      "Security review and DPA on request",
    ],
  },
];

type Cell = boolean | string;
interface Row {
  label: string;
  open: Cell;
  team: Cell;
  ent: Cell;
}

const groups: { heading: string; rows: Row[] }[] = [
  {
    heading: "Validation engine",
    rows: [
      { label: "Physics rule engine (21 domains)", open: true, team: true, ent: true },
      { label: "Dimensional-analysis cascade", open: true, team: true, ent: true },
      { label: "Pre-flight mesh & setup checks", open: true, team: true, ent: true },
      { label: "Structural repair (preview / apply)", open: true, team: true, ent: true },
      { label: "Multi-format ingestion (CSV, JSON, VTK, NumPy, OpenFOAM, …)", open: true, team: true, ent: true },
      { label: "AI reasoning layer (opt-in, bring your own key)", open: true, team: true, ent: true },
    ],
  },
  {
    heading: "Access & tooling",
    rows: [
      { label: "Hosted API", open: "Open, best-effort", team: "Dedicated", ent: "Self-hosted" },
      { label: "CLI, Python & Node SDKs", open: true, team: true, ent: true },
      { label: "Rate limits", open: "Shared", team: "Tuned per config", ent: "Unbounded (your infra)" },
      { label: "Cross-run history & drift detection", open: false, team: true, ent: true },
      { label: "CI gating (GitHub Action, exit codes)", open: "Self-serve", team: true, ent: true },
    ],
  },
  {
    heading: "Deployment & compliance",
    rows: [
      { label: "Self-hosted container (MIT)", open: true, team: true, ent: true },
      { label: "Private / VPC deployment", open: false, team: true, ent: true },
      { label: "Air-gapped deployment", open: false, team: false, ent: true },
      { label: "Signed compliance reports", open: false, team: "On request", ent: true },
      { label: "SSO, RBAC & audit logs", open: false, team: false, ent: "In development" },
      { label: "Security review & DPA", open: false, team: false, ent: true },
    ],
  },
  {
    heading: "Support",
    rows: [
      { label: "Community (GitHub issues)", open: true, team: true, ent: true },
      { label: "Priority support", open: false, team: true, ent: true },
      { label: "Onboarding & integration help", open: false, team: "Shared", ent: "Dedicated" },
    ],
  },
];

function cell(v: Cell) {
  if (v === true) return <Check className="mx-auto h-4 w-4 text-accent-blue" aria-label="Included" />;
  if (v === false) return <Minus className="mx-auto h-4 w-4 text-white/25" aria-label="Not included" />;
  return <span className="text-xs text-white/60">{v}</span>;
}

export default function PricingPage() {
  return (
    <>
      <PageHero
        title={<>Free to start. Self-host forever.</>}
        lede="The engine is MIT-licensed and the hosted API is currently open — you can validate real runs today without a contract. Paid plans add private deployment, CI gating, and the controls regulated teams need."
      />

      <section className="container-tight pb-16">
        <div className="grid gap-px overflow-hidden border border-white/10 bg-white/10 sm:grid-cols-3">
          {tiers.map((t, i) => (
            <Reveal key={t.name} delay={i * 0.05}>
              <div className={`flex h-full flex-col bg-ink-950 p-7 ${t.highlight ? "sm:relative sm:z-10" : ""}`}>
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-semibold text-white">{t.name}</h2>
                  {t.highlight && (
                    <span className="border border-accent-blue/40 px-1.5 py-0.5 text-[10px] font-medium tracking-wide text-accent-blue">
                      MOST TEAMS START HERE
                    </span>
                  )}
                </div>
                <p className="mt-4 text-2xl font-semibold text-white">
                  {t.price}
                  {t.unit && <span className="text-sm font-normal text-white/40"> {t.unit}</span>}
                </p>
                <p className="mt-2 text-sm leading-relaxed text-white/50">{t.blurb}</p>
                <Link
                  href={t.href}
                  className={`mt-6 w-full justify-center ${t.highlight ? "btn-accent" : "btn-ghost border border-white/15 px-4 py-2"}`}
                >
                  {t.cta}
                </Link>
                <ul className="mt-6 space-y-2.5 border-t border-white/10 pt-6">
                  {t.points.map((p) => (
                    <li key={p} className="flex items-start gap-2.5 text-sm text-white/65">
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-accent-blue" /> {p}
                    </li>
                  ))}
                </ul>
              </div>
            </Reveal>
          ))}
        </div>

        <p className="mt-4 text-sm leading-relaxed text-white/45">
          We haven&apos;t wired up automated billing yet — there is no card form and no metered
          invoice. The Open tier is genuinely free, and Team / Enterprise are handled by a
          conversation, not a checkout. When usage-based billing ships, it will be announced on the{" "}
          <Link href="/changelog" className="text-accent-blue underline underline-offset-2">
            changelog
          </Link>
          .
        </p>
      </section>

      <section className="container-tight pb-20">
        <h2 className="text-lg font-semibold text-white">Compare plans</h2>
        <div className="mt-6 overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-white/10 text-left">
                <th className="py-3 pr-4 font-medium text-white/40">Capability</th>
                <th className="px-4 py-3 text-center font-medium text-white">Open</th>
                <th className="px-4 py-3 text-center font-medium text-white">Team</th>
                <th className="px-4 py-3 text-center font-medium text-white">Enterprise</th>
              </tr>
            </thead>
            <tbody>
              {groups.map((g) => (
                <Fragment key={g.heading}>
                  <tr>
                    <td
                      colSpan={4}
                      className="border-b border-white/10 pt-6 pb-2 text-xs font-medium uppercase tracking-wider text-white/40"
                    >
                      {g.heading}
                    </td>
                  </tr>
                  {g.rows.map((r) => (
                    <tr key={r.label} className="border-b border-white/[0.06]">
                      <td className="py-3 pr-4 text-white/70">{r.label}</td>
                      <td className="px-4 py-3 text-center">{cell(r.open)}</td>
                      <td className="px-4 py-3 text-center">{cell(r.team)}</td>
                      <td className="px-4 py-3 text-center">{cell(r.ent)}</td>
                    </tr>
                  ))}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <Cta />
    </>
  );
}
