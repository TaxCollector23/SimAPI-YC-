import type { Metadata } from "next";
import { ShieldCheck, KeyRound, Lock, Server, FileCheck, Eye } from "lucide-react";
import { PageHero } from "@/components/ui/page-hero";
import { Reveal } from "@/components/ui/reveal";
import { Cta } from "@/components/cta";

export const metadata: Metadata = {
  title: "Security",
  description: "How SimAPI handles your data, keys, and infrastructure — encryption, API-key hygiene, and deployment options for regulated teams.",
};

const practices = [
  { icon: KeyRound, title: "API keys, hashed at rest", body: "Keys are shown once at generation, then stored only as a SHA-256 hash. Send them via the X-API-Key header over TLS; rotate or revoke any key instantly." },
  { icon: Lock, title: "Encryption in transit", body: "All API traffic is HTTPS/TLS 1.2+. Validation is stateless — request payloads are processed and not persisted beyond the ephemeral job TTL." },
  { icon: Server, title: "Self-hosted & VPC options", body: "The engine is a container you can run in your own VPC or air-gapped network. On Enterprise, simulation data never leaves your infrastructure." },
  { icon: Eye, title: "Least data, by design", body: "The deterministic engine needs only numeric columns. Non-numeric fields are dropped on ingest; nothing is stored to train shared models." },
  { icon: FileCheck, title: "Auditable & reproducible", body: "Every verdict is deterministic and cites the exact check, value, and bound it violated — a defensible audit trail, not a black box." },
  { icon: ShieldCheck, title: "Access controls (Enterprise)", body: "SSO, role-based access, and audit logs for teams that need them. Security review and a DPA available on request." },
];

export default function SecurityPage() {
  return (
    <>
      <PageHero
        eyebrow="Security"
        title={<>Built for teams that can&apos;t leak data</>}
        lede="Simulation data is often sensitive IP. SimAPI is designed to touch as little of it as possible, keep keys safe, and run inside your own perimeter when you need it to."
      />
      <section className="container-tight pb-16">
        <div className="grid gap-4 sm:grid-cols-2">
          {practices.map((p, i) => (
            <Reveal key={p.title} delay={i * 0.04}>
              <div className="h-full rounded-2xl border border-white/[0.08] bg-ink-900/50 p-6">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.03]">
                  <p.icon className="h-5 w-5 text-accent-cyan" />
                </div>
                <h3 className="mt-4 text-[15px] font-semibold text-white">{p.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-white/50">{p.body}</p>
              </div>
            </Reveal>
          ))}
        </div>
        <div className="mt-8 rounded-2xl border border-white/[0.07] bg-white/[0.02] p-6 text-sm text-white/55">
          <p><strong className="text-white/80">Reporting a vulnerability.</strong> Email <a className="text-accent-cyan" href="mailto:security@sim-api.dev">security@sim-api.dev</a> or open a private advisory on the <a className="text-accent-cyan" href="https://github.com/TaxCollector23/SimAPI-YC-/security">GitHub repo</a>. We aim to acknowledge within one business day. SOC 2 Type II is on the roadmap for Enterprise.</p>
        </div>
      </section>
      <Cta />
    </>
  );
}
