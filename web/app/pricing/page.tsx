import type { Metadata } from "next";
import { PageHero } from "@/components/ui/page-hero";
import { PricingCards } from "@/components/pricing-cards";
import { Faq } from "@/components/faq";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "Simple, usage-based pricing for simulation validation. Free for developers, scalable for teams, private deployments for enterprise.",
};

const compare = [
  ["Validations / month", "5,000", "250,000", "Unlimited"],
  ["Physics engine (287 checks)", "✓", "✓", "✓"],
  ["AI reasoning layer", "—", "✓", "✓"],
  ["Regression & baselines", "—", "✓", "✓"],
  ["CI/CD integrations", "—", "✓", "✓"],
  ["Private / air-gapped deploy", "—", "—", "✓"],
  ["SSO + audit logs", "—", "—", "✓"],
  ["Support", "Community", "Priority", "Dedicated + SLA"],
];

export default function PricingPage() {
  return (
    <>
      <PageHero
        eyebrow="Pricing"
        title={<>Pricing that scales with your pipeline</>}
        lede="Start free. Pay as your validation volume grows. Bring it fully in-house when you need to."
      />
      <section className="container-tight pb-8">
        <PricingCards />
      </section>

      <section className="container-tight py-16">
        <div className="overflow-hidden rounded-2xl border border-white/[0.07]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/[0.07] bg-white/[0.02] text-left text-white/50">
                <th className="p-4 font-medium">Feature</th>
                <th className="p-4 font-medium">Developer</th>
                <th className="p-4 font-medium">Startup</th>
                <th className="p-4 font-medium">Enterprise</th>
              </tr>
            </thead>
            <tbody>
              {compare.map((row) => (
                <tr key={row[0]} className="border-b border-white/[0.05] last:border-0">
                  <td className="p-4 text-white/70">{row[0]}</td>
                  {row.slice(1).map((cell, i) => (
                    <td key={i} className="p-4 text-white/50">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <Faq />
    </>
  );
}
