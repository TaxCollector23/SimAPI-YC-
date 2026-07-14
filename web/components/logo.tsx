import { cn } from "@/lib/utils";

/**
 * SimAPI brand logo — the full hero graphic (validation pipeline motif).
 * Pass a height class (e.g. `h-9`); width scales with the graphic's aspect ratio
 * so it is never stretched.
 */
export function Logo({ className }: { className?: string }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img src="/hero.svg" alt="SimAPI" className={cn("w-auto", className)} />
  );
}
