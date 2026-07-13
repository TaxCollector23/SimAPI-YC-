import type { Metadata } from "next";
import Link from "next/link";
import { PageHero } from "@/components/ui/page-hero";
import { Reveal } from "@/components/ui/reveal";
import { ArrowUpRight } from "lucide-react";

export const metadata: Metadata = {
  title: "Blog",
  description: "Engineering notes on simulation validation, physics rule engines, and building trust infrastructure.",
};

const posts = [
  {
    title: "Why simulations need a CI layer",
    excerpt: "Software earns trust through automated testing. Here's why simulations deserve the same — and what that gate looks like in practice.",
    date: "Coming soon",
    tag: "Vision",
  },
  {
    title: "Inside the physics engine: 287 checks across 21 domains",
    excerpt: "A tour of how deterministic validation layers compose — from plausibility bounds to conservation laws to cross-variable consistency.",
    date: "Coming soon",
    tag: "Engineering",
  },
  {
    title: "When to trust the AI layer (and when not to)",
    excerpt: "Deterministic rules give ground truth; the AI layer adds judgment. We break down where each belongs in a validation pipeline.",
    date: "Coming soon",
    tag: "Engineering",
  },
];

export default function BlogPage() {
  return (
    <>
      <PageHero
        eyebrow="Blog"
        title={<>Notes from the validation layer</>}
        lede="Deep dives on physics rule engines, simulation trust, and the infrastructure behind SimAPI."
      />
      <section className="container-tight space-y-4 pb-24">
        {posts.map((p, i) => (
          <Reveal key={p.title} delay={i * 0.05}>
            <Link
              href="#"
              className="group flex flex-col justify-between gap-4 rounded-2xl border border-white/[0.07] bg-ink-900/50 p-7 transition-colors hover:border-white/15 sm:flex-row sm:items-center"
            >
              <div className="max-w-2xl">
                <div className="flex items-center gap-3">
                  <span className="rounded-full border border-white/10 px-2.5 py-0.5 text-[11px] text-white/50">
                    {p.tag}
                  </span>
                  <span className="text-xs text-white/35">{p.date}</span>
                </div>
                <h2 className="mt-3 text-lg font-semibold text-white">{p.title}</h2>
                <p className="mt-2 text-sm leading-relaxed text-white/50">{p.excerpt}</p>
              </div>
              <ArrowUpRight className="h-5 w-5 shrink-0 text-white/30 transition-colors group-hover:text-white" />
            </Link>
          </Reveal>
        ))}
      </section>
    </>
  );
}
