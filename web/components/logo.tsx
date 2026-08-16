import { cn } from "@/lib/utils";

/**
 * SimAPI mark — a minimal validation glyph (a checked frame), drawn inline so it
 * inherits the current text color and scales crisply. No raster, no gradient.
 * Pass a height class (e.g. `h-9`); the mark is square.
 */
export function Logo({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      role="img"
      aria-label="SimAPI"
      className={cn("aspect-square h-6 w-auto", className)}
      fill="none"
    >
      <rect x="2.5" y="2.5" width="19" height="19" rx="4" stroke="currentColor" strokeOpacity="0.28" strokeWidth="1.5" />
      <path d="M7 12.2l3.2 3.3L17 8.5" stroke="#2563eb" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
