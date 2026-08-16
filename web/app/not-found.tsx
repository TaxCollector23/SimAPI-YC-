import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Page not found",
  robots: { index: false, follow: false },
};

const LINKS: { label: string; href: string; desc: string }[] = [
  { label: "Home", href: "/", desc: "What SimAPI is and the install command." },
  { label: "Playground", href: "/play", desc: "Run a validation in the browser, no login." },
  { label: "Documentation", href: "/docs", desc: "Quickstart, API reference, error contract." },
  { label: "Dashboard", href: "/dashboard", desc: "API keys, usage, and validation runs." },
  { label: "Benchmarks", href: "/benchmark", desc: "Methodology and the honest numbers." },
  { label: "Pricing", href: "/pricing", desc: "Open, Team, and Enterprise plans." },
];

export default function NotFound() {
  return (
    <section className="relative pt-40 pb-28">
      <div className="container-tight max-w-3xl">
        <p className="font-mono text-xs tracking-tight text-white/40">HTTP 404</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
          That page doesn&rsquo;t exist.
        </h1>
        <p className="mt-3 max-w-xl text-sm leading-relaxed text-white/55">
          The link may be out of date, or the URL was mistyped. Here&rsquo;s where to go instead.
        </p>

        <ul className="mt-10 divide-y divide-white/[0.06] border-y border-white/[0.06]">
          {LINKS.map((l) => (
            <li key={l.href}>
              <Link
                href={l.href}
                className="group grid grid-cols-[8rem_1fr] items-baseline gap-4 py-4 transition-colors hover:bg-white/[0.02]"
              >
                <span className="text-[15px] font-medium text-white group-hover:text-accent-blue">
                  {l.label}
                </span>
                <span className="text-sm text-white/50">{l.desc}</span>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
