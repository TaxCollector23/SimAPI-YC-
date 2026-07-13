import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Reveal } from "./ui/reveal";

export function Cta() {
  return (
    <section className="relative py-24 sm:py-32">
      <div className="container-tight">
        <Reveal>
          <div className="relative overflow-hidden rounded-3xl border border-white/[0.08] bg-ink-900/60 px-8 py-16 text-center">
            <div className="pointer-events-none absolute inset-0 grid-bg opacity-40" />
            <div className="pointer-events-none absolute inset-x-0 top-0 h-64 bg-radial-fade" />
            <div className="relative">
              <h2 className="mx-auto max-w-2xl text-balance text-3xl font-semibold tracking-tight text-white sm:text-4xl">
                Give your simulations the testing they&apos;ve never had.
              </h2>
              <p className="mx-auto mt-4 max-w-xl text-white/55">
                Start validating in minutes. No simulation data leaves your control on
                enterprise plans.
              </p>
              <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
                <Link href="/contact" className="btn-accent">
                  Get API Key <ArrowRight className="h-4 w-4" />
                </Link>
                <Link href="/docs" className="btn-ghost">
                  Read the docs
                </Link>
              </div>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
