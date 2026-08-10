# Black-and-blue theme experiment

A drop-in visual override for the `web/` marketing site. Only colors,
radii, and a few decoration choices change. **No component text is
touched. No button labels change. No backend is touched.**

## What changes vs. the shipped theme

| Slop pattern (per unslopify + Uncodixfy) | Before | After |
|---|---|---|
| Three-color gradient (cyan → blue → violet) | `bg-accent-gradient` uses `#22d3ee → #3b82f6 → #8b5cf6` | Single flat blue `#2563eb → #1d4ed8` (barely a gradient) |
| Dual radial fades on the body | Blue radial + violet radial | Solid true black |
| Pill buttons (`rounded-full`) | `rounded-full` on every `.btn` | `rounded-md` |
| Big white primary CTA (SaaS-landing signature) | `bg-white text-ink-950` with soft shadow | `bg-accent-blue text-white` |
| Glass-morphism (`.glass`, backdrop-blur cards) | `bg-white/[0.03] backdrop-blur-xl` | Solid `bg-ink-900` with a hairline border |
| Decorative animations (`float`, `pulse-soft`, `grid-pan`) | On every hero background | Removed; only `fade-up` kept |
| Big blue drop-shadow "glow" behind panels | `shadow-glow` = 60px blue blur | Replaced by a 1px hairline |
| Neutrals with a blue undertone (implies "AI") | `ink-950 = #06070a` | True black `#000000`; blue lives only in the accent |

Everything the components import still resolves — same class names,
same tokens, same `text-gradient` / `btn-primary` / `.glass` / etc.
Only the values behind those names change.

## To apply

```bash
cp web-experiments/black-blue/tailwind.config.ts web/tailwind.config.ts
cp web-experiments/black-blue/globals.css       web/app/globals.css
cd web && npm run dev
```

## To roll back (exact restore of the shipped theme)

```bash
git checkout web/tailwind.config.ts web/app/globals.css
```

The experiment folder itself stays committed as a reference regardless
of whether the override is applied to `web/`. You can delete the entire
`web-experiments/` tree at any time without touching the shipped site.

## What is deliberately NOT changed

- Every string of visible text
- Every button, form, or link's label
- Every component's structure or props
- The API, the CLI, the SDK, or any Python code
- Any file outside `web/tailwind.config.ts` and `web/app/globals.css`
  when the override is applied

## Design lineage

- <https://github.com/TaxCollector23/unslopify> — anti-slop ruleset
- <https://github.com/cyxzdev/Uncodixfy> — "GPT is surprisingly bad at UI design"
  ruleset, blocks floating cards / oversized radii / gradient soup /
  glass-morphism
