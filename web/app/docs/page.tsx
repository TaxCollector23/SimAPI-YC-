import type { Metadata } from "next";
import { PageHero } from "@/components/ui/page-hero";
import { ArrowUpRight } from "lucide-react";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Documentation",
  description: "Guides, API reference, SDKs, and examples for the SimAPI simulation validation platform.",
};

const DOCS = "https://simapidocs.github.io";

export default function DocsPage() {
  return (
    <PageHero
      eyebrow="Documentation"
      title={<>Everything you need to build on SimAPI</>}
      lede="Guides, a complete API reference, SDKs, and copy-paste examples."
    >
      <div className="mt-2 flex flex-wrap gap-3">
        <a href={DOCS} className="btn-accent">
          Quickstart <ArrowUpRight className="h-4 w-4" />
        </a>
        <a href={site.github} className="btn-ghost">
          View source <ArrowUpRight className="h-4 w-4" />
        </a>
      </div>
    </PageHero>
  );
}
