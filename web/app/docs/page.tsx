import type { Metadata } from "next";
import Link from "next/link";
import { PageHero } from "@/components/ui/page-hero";
import { Reveal } from "@/components/ui/reveal";
import {
  Rocket, KeyRound, Braces, FileCode2, Boxes, Terminal, GitBranch, ShieldCheck, ArrowUpRight,
} from "lucide-react";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Documentation",
  description: "Guides, API reference, SDKs, and examples for the SimAPI simulation validation platform.",
};

// The full reference is a Mintlify site (see /docs-site). These cards deep-link
// into it; locally they resolve to the docs home.
const DOCS = "https://docs.simapi.dev";

const groups = [
  {
    title: "Get started",
    items: [
      { icon: Rocket, label: "Quickstart", href: `${DOCS}/quickstart`, sub: "First validation in 3 minutes" },
      { icon: KeyRound, label: "Authentication", href: `${DOCS}/authentication`, sub: "API keys & rate limits" },
      { icon: Terminal, label: "CLI", href: `${DOCS}/sdks/cli`, sub: "Validate from the terminal" },
    ],
  },
  {
    title: "API reference",
    items: [
      { icon: Braces, label: "Validation API", href: `${DOCS}/api-reference/validate`, sub: "POST /v1/validate" },
      { icon: FileCode2, label: "Jobs API", href: `${DOCS}/api-reference/jobs`, sub: "Poll async results" },
      { icon: GitBranch, label: "Error codes", href: `${DOCS}/error-codes`, sub: "Stable, documented codes" },
    ],
  },
  {
    title: "SDKs & integrations",
    items: [
      { icon: Boxes, label: "Python SDK", href: `${DOCS}/sdks/python`, sub: "pip install simapi" },
      { icon: GitBranch, label: "GitHub Actions", href: `${DOCS}/cicd/github-actions`, sub: "Gate on validation status" },
      { icon: ShieldCheck, label: "Security", href: `${site.github}/blob/main/SECURITY.md`, sub: "Deployment hardening" },
    ],
  },
];

export default function DocsPage() {
  return (
    <>
      <PageHero
        eyebrow="Documentation"
        title={<>Everything you need to build on SimAPI</>}
        lede="Guides, a complete API reference, SDKs, and copy-paste examples — engineered to feel like the best developer docs you've used."
      >
        <div className="mt-2 flex flex-wrap gap-3">
          <a href={`${DOCS}/quickstart`} className="btn-accent">Quickstart</a>
          <a href={site.github} className="btn-ghost">
            View source <ArrowUpRight className="h-4 w-4" />
          </a>
        </div>
      </PageHero>

      <section className="container-tight space-y-12 pb-24">
        {groups.map((g) => (
          <Reveal key={g.title}>
            <h2 className="mb-4 text-xs font-semibold uppercase tracking-wider text-white/40">
              {g.title}
            </h2>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {g.items.map((it) => (
                <a
                  key={it.label}
                  href={it.href}
                  className="group flex items-start gap-3 rounded-2xl border border-white/[0.07] bg-ink-900/50 p-5 transition-colors hover:border-white/15"
                >
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 bg-white/[0.03]">
                    <it.icon className="h-4.5 w-4.5 text-accent-cyan" />
                  </div>
                  <div className="min-w-0">
                    <p className="flex items-center gap-1 text-sm font-medium text-white">
                      {it.label}
                      <ArrowUpRight className="h-3.5 w-3.5 text-white/25 transition-colors group-hover:text-white" />
                    </p>
                    <p className="text-xs text-white/45">{it.sub}</p>
                  </div>
                </a>
              ))}
            </div>
          </Reveal>
        ))}
      </section>
    </>
  );
}
