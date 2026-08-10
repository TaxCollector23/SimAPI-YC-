import type { Config } from "tailwindcss";

/**
 * Black-and-blue theme experiment for SimAPI.
 *
 * Drop-in replacement for web/tailwind.config.ts. Only tokens change —
 * no component text, no button labels, no backend.
 *
 * Design rules (from TaxCollector23/unslopify + cyxzdev/Uncodixfy):
 *   - one accent color, not three (kill cyan+violet)
 *   - no gradient-heavy compositions (kill accent-gradient)
 *   - no oversized border-radius (buttons stay rounded but not pills)
 *   - no glass-morphism as a headline surface
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
      screens: { "2xl": "1200px" },
    },
    extend: {
      colors: {
        // True black canvas. No blue undertone in the neutrals — the blue
        // lives only in the accent, so it reads as a decision, not a wash.
        ink: {
          950: "#000000",
          900: "#050506",
          850: "#08090b",
          800: "#0d0e11",
          700: "#15171c",
          600: "#1f2229",
        },
        line: "rgba(255,255,255,0.08)",
        // One accent, not three. A cooler infrastructure blue than the
        // marketing-website #3b82f6 — closer to a terminal / IDE selection blue.
        accent: {
          blue: "#2563eb",
          blueHover: "#1d4ed8",
          blueSoft: "#3b82f6",
        },
        pass: "#22c55e",
        warn: "#eab308",
        fail: "#ef4444",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      // Radii tightened. rounded-2xl / 3xl are still available so nothing
      // breaks, but the values are pulled in so surfaces stop reading as
      // consumer-app cards.
      borderRadius: {
        "2xl": "0.5rem",
        "3xl": "0.75rem",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        // Kept for skeleton-loading contexts only.
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.6s cubic-bezier(0.22,1,0.36,1) both",
      },
      backgroundImage: {
        // Same name so components importing `bg-accent-gradient` still
        // resolve — but the "gradient" is now a single flat blue with a
        // barely-there vertical lift. No cyan. No violet. No shimmer.
        "accent-gradient":
          "linear-gradient(180deg,#2563eb 0%,#1d4ed8 100%)",
        "radial-fade":
          "radial-gradient(60% 50% at 50% 0%,rgba(37,99,235,0.10) 0%,transparent 70%)",
      },
    },
  },
  plugins: [],
};

export default config;
