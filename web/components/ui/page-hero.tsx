import type { ReactNode } from "react";
import { Reveal } from "./reveal";

/** Consistent inner-page header with grid backdrop. */
export function PageHero({
  eyebrow,
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
    <section className="relative overflow-hidden pt-40 pb-16">
      <div className="pointer-events-none absolute inset-0 grid-bg opacity-40" />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-96 bg-radial-fade" />
      <div className="container-tight relative">
        <Reveal className="flex max-w-3xl flex-col gap-5">
          {eyebrow && <span className="eyebrow w-fit">{eyebrow}</span>}
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
