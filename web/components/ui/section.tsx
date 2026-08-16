import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Reveal } from "./reveal";

/**
 * A titled page section: heading and lede.
 *
 * `eyebrow` is retained in the prop type for backward compatibility with
 * the many pages that still pass it, but it is intentionally NOT rendered
 * — the visual system has no uppercase mono kicker labels.
 */
export function SectionHeader({
  title,
  lede,
  align = "center",
}: {
  eyebrow?: string;
  title: ReactNode;
  lede?: ReactNode;
  align?: "center" | "left";
}) {
  return (
    <Reveal
      className={cn(
        "flex w-full flex-col gap-4",
        align === "center" ? "items-center text-center" : "items-start text-left",
      )}
    >
      <h2 className="w-full max-w-2xl text-balance text-3xl font-semibold tracking-tight text-white sm:text-4xl">
        {title}
      </h2>
      {lede && <p className="w-full max-w-2xl text-base leading-relaxed text-white/55">{lede}</p>}
    </Reveal>
  );
}

export function Section({
  id,
  className,
  children,
}: {
  id?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section id={id} className={cn("relative py-24 sm:py-32", className)}>
      <div className="container-tight">{children}</div>
    </section>
  );
}
