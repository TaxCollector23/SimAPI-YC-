import type { Metadata } from "next";
import { PageHero } from "@/components/ui/page-hero";
import { ContactForm } from "@/components/contact-form";
import { Mail, Github, ShieldCheck } from "lucide-react";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Contact",
  description: "Request an API key, join the design partner program, or talk to us about enterprise deployment.",
};

export default function ContactPage() {
  return (
    <>
      <PageHero
        eyebrow="Contact"
        title={<>Let&apos;s get your simulations validated</>}
        lede="Request an API key, join the design partner program, or ask about private deployment. We read every message."
      />
      <section className="container-tight grid gap-10 pb-24 lg:grid-cols-[1.2fr_1fr]">
        <ContactForm />
        <div className="space-y-4">
          {[
            { icon: Mail, title: "Email", body: "hello@simapi.dev", sub: "General & sales" },
            { icon: Github, title: "GitHub", body: "TaxCollector23/SimAPI-", sub: "Source & issues", href: site.github },
            { icon: ShieldCheck, title: "Security", body: "security@simapi.dev", sub: "Responsible disclosure" },
          ].map((c) => (
            <a
              key={c.title}
              href={c.href}
              className="flex items-start gap-3 rounded-2xl border border-white/[0.07] bg-ink-900/50 p-5 transition-colors hover:border-white/15"
            >
              <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 bg-white/[0.03]">
                <c.icon className="h-4.5 w-4.5 text-accent-cyan" />
              </div>
              <div>
                <p className="text-sm font-medium text-white">{c.title}</p>
                <p className="text-sm text-white/60">{c.body}</p>
                <p className="text-xs text-white/35">{c.sub}</p>
              </div>
            </a>
          ))}
        </div>
      </section>
    </>
  );
}
