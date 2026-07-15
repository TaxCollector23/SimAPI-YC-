import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Reveal } from "./ui/reveal";

export function Cta() {
  return (
    <section className="relative py-20 sm:py-28">
      <div className="container-tight">
        <Reveal>
          <div className="relative overflow-hidden rounded-lg border border-white/[0.08] bg-ink-900/60 px-8 py-16 text-center">
            <div className="pointer-events-none absolute inset-0 grid-bg opacity-40" />
            <div className="pointer-events-none absolute inset-x-0 top-0 h-64 bg-radial-fade" />
            <div className="relative">
              <h2 className="mx-auto max-w-2xl text-balance text-3xl font-semibold tracking-tight text-white sm:text-4xl">
                Put a quality gate in front of every simulation run.
              </h2>
              <p className="mx-auto mt-4 max-w-xl text-white/55">
                Generate a key, validate a sample run in the browser, then move the same
                checks into your CLI, SDK, or CI pipeline.
              </p>
              <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
                <Link href="/dashboard" className="btn-accent">
                  Get API Key <ArrowRight className="h-4 w-4" />
                </Link>
                <Link href="/docs" className="btn-ghost">
                  Read docs
                </Link>
              </div>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
