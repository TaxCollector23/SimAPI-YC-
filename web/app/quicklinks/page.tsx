import type { Metadata } from "next";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

export const metadata: Metadata = {
  title: "Quick Links",
  description: "Every SimAPI-related site, in one place.",
};

interface LinkEntry { label: string; href: string; desc: string; external?: boolean }

// Update this list every time a new SimAPI domain goes live. Deliberately
// excludes the admin console — that's not public-facing.
const LINKS: LinkEntry[] = [
  { label: "Website", href: "https://sim-api.vercel.app", desc: "Main site, dashboard, and playground.", external: true },
  { label: "Playground", href: "https://simapiplayground.vercel.app", desc: "Run validations in the browser, no account needed.", external: true },
  { label: "Documentation", href: "https://simapidocs.github.io", desc: "Quick start, API reference, CLI docs.", external: true },
  { label: "Status", href: "https://simapistatus.vercel.app", desc: "Live system status and latency.", external: true },
  { label: "API backend", href: "https://simapi-yc.onrender.com", desc: "Full Python engine — interactive docs, OpenAPI schema.", external: true },
  { label: "GitHub", href: "https://github.com/TaxCollector23/SimAPI-YC-", desc: "Source code, issues, and pull requests.", external: true },
];

export default function QuickLinksPage() {
  return (
    <div className="container-tight pt-32 pb-24">
      <div className="mx-auto max-w-2xl">
        <h1 className="text-3xl font-semibold text-white">Quick links</h1>
        <p className="mt-2 text-sm text-white/50">Every SimAPI site, in one place.</p>

        <div className="mt-8 overflow-hidden rounded-2xl border border-white/[0.08]">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              target={l.external ? "_blank" : undefined}
              rel={l.external ? "noreferrer" : undefined}
              className="flex items-center justify-between gap-4 border-b border-white/[0.05] px-5 py-4 transition-colors last:border-0 hover:bg-white/[0.03]"
            >
              <div>
                <span className="flex items-center gap-1.5 text-sm font-medium text-white">
                  {l.label}
                  <ArrowUpRight className="h-3.5 w-3.5 text-white/30" />
                </span>
                <span className="text-xs text-white/40">{l.desc}</span>
              </div>
              <span className="shrink-0 font-mono text-xs text-white/30">{l.href.replace(/^https?:\/\//, "")}</span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
