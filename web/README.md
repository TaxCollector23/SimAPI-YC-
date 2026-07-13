# SimAPI — Marketing Site

The public site for SimAPI, built with **Next.js 15 (App Router)**, **TypeScript**,
**Tailwind CSS**, **Framer Motion**, and **Lucide** icons.

## Highlights

- **Interactive validation demo** (`components/interactive-demo.tsx`) — runs a live
  pipeline (parse → physics → AI → report) and reveals an animated dashboard.
  Switch between clean / broken / edge / noise scenarios to see verdicts change.
- **Embedded API playground** (`components/api-playground.tsx`) — edit a request
  body and validate it against a faithful client-side model of `POST /v1/validate`.
- Animated hero (canvas validation graph), workflow pipeline, feature grid,
  use-cases, multi-language code tabs, pricing, and FAQ.
- Full SEO: metadata, OpenGraph, JSON-LD, `sitemap.ts`, `robots.ts`.
- Dark-mode-first design system in `tailwind.config.ts` + `app/globals.css`.

## Develop

```bash
cd web
npm install
npm run dev        # http://localhost:3000
npm run build      # production build
```

## Deploy

Zero-config on Vercel (framework auto-detected). Any Node host works via
`npm run build && npm start`.
