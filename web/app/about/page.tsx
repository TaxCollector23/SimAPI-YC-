import type { Metadata } from "next";
import { PageHero } from "@/components/ui/page-hero";
import { Reveal } from "@/components/ui/reveal";
import { Cta } from "@/components/cta";

export const metadata: Metadata = {
  title: "About",
  description:
    "Engineering teams trust software because software has automated testing. Engineering simulations have no equivalent. SimAPI is building it.",
};

const principles = [
  { title: "Deterministic first", body: "Where physics gives a clear answer, we use rules — auditable, reproducible, and fast. AI augments; it never replaces the ground truth." },
  { title: "API-first", body: "Every capability is an endpoint with a stable schema. If it can't be automated, it can't be trusted at scale." },
  { title: "Your data, your control", body: "Proprietary simulation data is some of the most sensitive IP a company has. Private and air-gapped deployment is a first-class path, not an afterthought." },
  { title: "No theater", body: "We don't fabricate logos, testimonials, or benchmarks. Claims map to code you can read." },
];

export default function AboutPage() {
  return (
    <>
      <PageHero
        eyebrow="About"
        title={<>Automated testing for the physical world.</>}
        lede="Software earns trust through continuous testing. Simulations — which increasingly drive design decisions and ML — have had no equivalent. We're building that layer."
      />

      <section className="container-tight py-12">
        <Reveal>
          <div className="prose-invert max-w-2xl space-y-5 text-white/60">
            <p>
              A modern engineering organization runs thousands of CFD, FEA, robotics, and
              multiphysics simulations. Today, a human engineer eyeballs the output before
              anyone trusts it. That gate is slow, subjective, and doesn&apos;t scale — and
              a single bad run can silently poison a design decision or an ML training set.
            </p>
            <p>
              SimAPI turns that manual gate into an API call. Deterministic physics rules,
              statistical analysis, and AI reasoning combine into a single verdict —
              <span className="text-white/80"> passed, warning, or failed</span> — in
              milliseconds. Think GitHub Actions for simulations, Stripe for simulation
              validation, Cloudflare for engineering trust.
            </p>
          </div>
        </Reveal>

        <div className="mt-14 grid gap-4 sm:grid-cols-2">
          {principles.map((p, i) => (
            <Reveal key={p.title} delay={i * 0.05}>
              <div className="rounded-2xl border border-white/[0.07] bg-ink-900/50 p-6">
                <h3 className="text-[15px] font-semibold text-white">{p.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-white/50">{p.body}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>
      <Cta />
    </>
  );
}
