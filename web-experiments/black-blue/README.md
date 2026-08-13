# Black-and-blue theme experiment — v4 (arrow-CTA rework)

A drop-in visual override for the `web/` marketing site. **v1 changed
colours; v2 changes shape, rhythm, typography, and CTA grammar** so the
site stops reading like a SaaS landing template.

No component code is edited. Every visible string of text is preserved.
Every class name every component imports still resolves. Only the values
behind those class names change.

## What changes vs. the shipped theme

**Colour (from v1, retained):**

| Slop pattern | Before | After |
|---|---|---|
| Three-colour gradient (cyan → blue → violet) | `#22d3ee → #3b82f6 → #8b5cf6` | Single flat blue `#2563eb → #1d4ed8` |
| Dual radial fades on the body | blue + violet | true black |
| Neutrals with a blue undertone | `ink-950 = #06070a` | `#000000` |

**Shape and rhythm (new in v2):**

| Slop pattern (per unslopify + Uncodixfy) | Before | After |
|---|---|---|
| Center-aligned marketing hero | `text-center` + `items-center` | Left-aligned, editorial column |
| Sans-serif hero display type | `font-semibold text-6xl sans` | Editorial serif (system `ui-serif` / Georgia) at ~56px |
| Pill buttons (`rounded-full`) with icons carrying meaning | `rounded-full` with 4px icon | `rounded-0` monospace uppercase, icon shrunk to 12px so label carries |
| Big colored primary CTA | `bg-white text-ink-950` (SaaS-landing signature) | Bordered rectangle, transparent fill, inverts on hover |
| Accent CTA with 60px blue drop-shadow "glow" | `bg-accent-gradient shadow-[…blue-blur…]` | Solid blue rectangle, one accent surface on the page |
| Pill-shaped "eyebrow" tag | `rounded-full` bordered pill w/ pulsing dot | Bracket-tag `[ SIMULATION VALIDATION ]` in monospace, no border, no dot |
| Rounded feature cards (`rounded-2xl / 3xl`) | `1rem / 1.5rem` | 0. Every card, badge, and panel is a rectangle |
| Glass-morphism panels (`bg-white/[0.03] backdrop-blur-xl`) | translucent white wash + backdrop-blur | Solid `bg-ink-900` with a hairline border |
| Decorative animations (`float`, `pulse-soft`, `grid-pan`) | on every hero background | dropped; only `fade-up` kept for essential motion |
| Hero background canvas (dots / grid / animated svg) | full-viewport decoration | hidden via CSS |
| Container width | 1200px (pitch-deck) | 960px (editorial reading) |

**Typography and quiet (new in v3):**

| v2 pattern | v3 |
|---|---|
| System serif (`ui-serif` / Georgia) on h1/h2 | **Geist Sans** across the whole page — headings, body, buttons, nav |
| System monospace for code | **Geist Mono** for every code / mono surface |
| Bracket-tag eyebrow `[ SIMULATION VALIDATION ]` w/ monospace + brackets | Quiet Geist Mono tracked uppercase; no brackets, no border, no pulsing dot |
| Monospace uppercase buttons w/ 0.08em tracking | Geist Sans sentence-case medium weight — reads as a button, not a stylistic statement |
| Trust-badge pill row under CTAs (`CFD, FEA, robotics` / `CLI, SDK, REST API` / `CI fail gates`) | **Removed.** Every SaaS template has these; they say nothing the copy doesn't. |
| Any other bordered-pill badges in sections | Removed the same way — `section .rounded-full[class*="border"] { display: none }` |
| H1 at 56px | Pulled down to ~44px — documentation-hero scale, not marketing-hero scale |

Geist is loaded from Google Fonts via a single `@import` at the top of
`globals.css` — no `next/font` change, no `layout.tsx` edit, no addition
to `package.json`. Falls back to `ui-sans-serif` / `system-ui` if the
CDN is blocked.

**CTA rework (new in v4):**

| v3 | v4 |
|---|---|
| Two rectangle buttons in the hero (bordered ghost + solid blue) — still template-shaped ("primary + secondary" pair) | **One** solid blue rectangle (`.btn-accent`) as the single primary. Everything else is a **link with a sliding "→" arrow** on hover. |
| `.btn-primary` = bordered transparent rectangle | `.btn-primary` = white link + `→` arrow, underline on hover, arrow slides 4px right |
| `.btn-ghost` = bordered greyer rectangle | `.btn-ghost` = grey link + `→` arrow, same hover behaviour, brighter on hover |
| `.btn-accent` = solid blue rectangle | `.btn-accent` = solid blue rectangle (unchanged) — reserve for the single most important action on any page |

The pattern is what real product pages actually use (Stripe, Linear,
Vercel docs, Fly.io machines): **one** saturated call to action per
view, and every other navigation move is a quiet link. Nav's "Get API
Key" quietens to a link, hero's stays solid. Reads as a real product
page, not a template.

## Local dev

Once the override is applied, start the dev server on any free port:

```bash
PORT=4321 npm --prefix web run dev
```

Open <http://localhost:4321> (or whatever port you chose). The shipped
`.claude/launch.json` targets 3000; passing `PORT` overrides it.

**Reference lineage:**

- <https://github.com/TaxCollector23/unslopify>
- <https://github.com/cyxzdev/Uncodixfy> — *"GPT is surprisingly bad at UI design"*

Together these reject: floating cards, oversized radii, gradient-heavy
compositions, glass-morphism, decorative labeling. v2 implements those
rejections concretely.

## Files shipped in this folder

- **`tailwind.config.ts`** — collapses every `borderRadius` to 0 (except
  `full` for legit dots/scrollbars), narrows the container to 960px,
  removes cyan and violet from `accent`, adds a `serif` family stack,
  drops the `float` / `pulse-soft` / `grid-pan` animations.
- **`globals.css`** — retypes headings in system serif, force-lefts the
  hero, restyles buttons to monospace uppercase bordered rectangles,
  renders the eyebrow as a bracket-tag, hides the hero background canvas,
  strips pill radii from nav and trust-badges.
- **`README.md`** — this file.

## To apply

```bash
cp web-experiments/black-blue/tailwind.config.ts web/tailwind.config.ts
cp web-experiments/black-blue/globals.css       web/app/globals.css
cd web && npm run dev
```

Open <http://localhost:3000>.

## To roll back (exact restore of the shipped theme)

```bash
git checkout web/tailwind.config.ts web/app/globals.css
```

The experiment folder itself stays committed as a reference regardless
of whether the override is applied to `web/`. Deleting `web-experiments/`
never touches the shipped site.

## What is deliberately NOT changed

- Every string of visible text on the site
- Every button label
- Every component's props or structure
- The API, the CLI, the SDK, or any Python code
- Any file outside `web/tailwind.config.ts` and `web/app/globals.css`
  when the override is applied

## Verified before commit

Rendered the applied override locally, checked hero + benchmark
sections at both mobile (~800px) and desktop (1280px) viewports. No
console errors. No hydration warnings. All content sections render at
`opacity: 1`. Body computed background is `rgb(0, 0, 0)`. The
`text-gradient` utility now resolves to a flat blue, so the word
"wrong" in the hero renders solid, not tri-colour.
