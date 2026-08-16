import type { ReactNode } from "react";
import { Reveal } from "./reveal";

/**
 * Consistent inner-page header. Flat black with a single hairline rule at
 * the bottom — no glow, no radial fade. `eyebrow` is kept in the prop type
 * for backward compatibility across the pages that pass it, but is not
 * rendered: the system has no kicker labels.
 */
export function PageHero({
  title,
  lede,
  children,
}: {
  eyebrow?: string;
  title: ReactNode;
  lede?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <section className="relative overflow-hidden border-b border-white/[0.06] pt-40 pb-16">
      <div className="container-tight relative">
        <Reveal className="flex max-w-3xl flex-col gap-5">
          <h1 className="text-balance text-4xl font-semibold tracking-tight text-white sm:text-5xl">
            {title}
          </h1>
          {lede && <p className="max-w-2xl text-lg leading-relaxed text-white/55">{lede}</p>}
          {children}
        </Reveal>
      </div>
    </section>
  );
}
