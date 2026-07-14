import { cn } from "@/lib/utils";

/**
 * SimAPI brand mark — the hero validation motif condensed into a square emblem:
 * connected simulation nodes flowing into a validated (checked) result node.
 */
export function Logo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={cn(className)} fill="none" aria-hidden="true">
      <defs>
        <linearGradient id="simapi-mark" x1="0" y1="0" x2="40" y2="40">
          <stop offset="0" stopColor="#22d3ee" />
          <stop offset="0.5" stopColor="#3b82f6" />
          <stop offset="1" stopColor="#8b5cf6" />
        </linearGradient>
      </defs>
      <rect x="0.75" y="0.75" width="38.5" height="38.5" rx="9" stroke="url(#simapi-mark)" strokeWidth="1.5" strokeOpacity="0.5" />
      {/* pipeline edges */}
      <g stroke="url(#simapi-mark)" strokeWidth="1.6" strokeOpacity="0.55">
        <line x1="9" y1="24" x2="19" y2="13" />
        <line x1="19" y1="13" x2="28" y2="21" />
      </g>
      {/* simulation nodes */}
      <g fill="#0a0b10" stroke="url(#simapi-mark)" strokeWidth="1.8">
        <circle cx="9" cy="24" r="2.6" />
        <circle cx="19" cy="13" r="2.6" />
      </g>
      {/* validated result node */}
      <circle cx="28" cy="26" r="6.4" fill="url(#simapi-mark)" fillOpacity="0.16" stroke="url(#simapi-mark)" strokeWidth="1.8" />
      <path d="m25 26 2.2 2.2 4.2-4.6" stroke="url(#simapi-mark)" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
