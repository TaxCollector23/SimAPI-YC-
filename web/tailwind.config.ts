import type { Config } from "tailwindcss";

/**
 * Black-and-blue theme experiment for SimAPI — v2 (anti-slop).
 *
 * v1 changed colours. v2 changes shape, rhythm, typography, and CTA
 * grammar so the site stops reading like a SaaS landing template.
 *
 * Drop-in replacement for web/tailwind.config.ts. No component text
 * is edited. No backend is touched.
 *
 * Design rules (from TaxCollector23/unslopify + cyxzdev/Uncodixfy):
 *   - one accent, not three
 *   - no gradient-heavy compositions
 *   - no oversized border-radius (v2: no radius at all outside 1px pills)
 *   - no glass-morphism
 *   - no floating cards
 *   - restraint over decoration
 *
 * To apply:  cp web-experiments/black-blue/tailwind.config.ts web/tailwind.config.ts
 * To rollback: git checkout web/tailwind.config.ts
 */
const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    container: {
      center: true,
      padding: "1.5rem",
      // Narrower: the shipped 1200px is a marketing width. Editorial
      // reading widths (~960) feel more like documentation and less
      // like a pitch deck.
      screens: { "2xl": "960px" },
    },
    // v2: kill EVERY border-radius. rounded-full still exists for
    // scrollbar/dot-indicator legit uses. rounded-md / lg / xl / 2xl /
    // 3xl all collapse to zero — every card, button, badge, and pill
    // becomes a rectangle.
    borderRadius: {
      none: "0",
      sm: "0",
      DEFAULT: "0",
      md: "0",
      lg: "0",
      xl: "0",
      "2xl": "0",
      "3xl": "0",
      full: "9999px",
    },
    extend: {
      colors: {
        // True black canvas. No blue undertone in the neutrals; blue
        // lives only in the accent so it reads as a decision.
        ink: {
          950: "#000000",
          900: "#050506",
          850: "#08090b",
          800: "#0d0e11",
          700: "#15171c",
          600: "#1f2229",
        },
        line: "rgba(255,255,255,0.10)",
        // One accent — infrastructure blue closer to terminal selection.
        accent: {
          blue: "#2563eb",
          blueHover: "#1d4ed8",
          blueSoft: "#3b82f6",
          // Kept so components importing `accent-cyan` / `accent-violet`
          // still compile — but both now map to the same blue. No
          // gradient will resolve as three colours.
          cyan: "#2563eb",
          violet: "#2563eb",
        },
        pass: "#22c55e",
        warn: "#eab308",
        fail: "#ef4444",
      },
      fontFamily: {
        // v2: a real editorial serif for display headings, system stack
        // for body, ui-monospace for code and buttons. No web-font fetch —
        // system fonts only, so no FOUT and no network dependency.
        sans: ["var(--font-sans)", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
        serif: ["ui-serif", "Georgia", "Cambria", "\"Times New Roman\"", "Times", "serif"],
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: { "100%": { transform: "translateX(100%)" } },
      },
      animation: {
        // Only fade-up survives. float / pulse-soft / grid-pan were
        // decoration; killed.
        "fade-up": "fade-up 0.6s cubic-bezier(0.22,1,0.36,1) both",
      },
      backgroundImage: {
        // Names kept so components importing these utilities still resolve,
        // but both are neutralized. `accent-gradient` is a flat blue fill
        // (no gradient); `radial-fade` is nothing at all — the glowy hero
        // and CTA blobs are removed everywhere, including pages this system
        // does not own.
        "accent-gradient": "none",
        "radial-fade": "none",
      },
    },
  },
  plugins: [],
};

export default config;
