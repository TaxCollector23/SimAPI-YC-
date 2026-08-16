import Link from "next/link";
import { Reveal } from "./ui/reveal";

export function Cta() {
  return (
    <section className="relative py-24 sm:py-32">
      <div className="container-tight">
        <Reveal className="flex flex-col items-start gap-6 border-t border-white/[0.06] pt-16">
          <h2 className="max-w-2xl text-balance text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            Put a quality gate in front of every simulation run.
          </h2>
          <p className="max-w-xl text-white/55">
            Generate a key, validate a sample run in the browser, then move the same
            checks into your CLI, SDK, or CI pipeline.
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-x-6 gap-y-3">
            <Link href="/dashboard" className="btn-accent">
              Get an API key
            </Link>
            <Link href="/docs" className="btn-primary">
              Read the docs
            </Link>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
