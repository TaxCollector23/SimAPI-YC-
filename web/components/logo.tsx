import { cn } from "@/lib/utils";

/** Abstract validation-node mark: a checked hexagonal simulation cell. */
export function Logo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn(className)} fill="none" aria-hidden="true">
      <defs>
        <linearGradient id="simapi-logo" x1="0" y1="0" x2="32" y2="32">
          <stop offset="0" stopColor="#22d3ee" />
          <stop offset="0.5" stopColor="#3b82f6" />
          <stop offset="1" stopColor="#8b5cf6" />
        </linearGradient>
      </defs>
      <path
        d="M16 2.5 27.7 9v14L16 29.5 4.3 23V9L16 2.5Z"
        stroke="url(#simapi-logo)"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path
        d="m11 16 3.4 3.4L21.5 12"
        stroke="url(#simapi-logo)"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
