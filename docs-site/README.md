# SimAPI Documentation

World-class developer docs for SimAPI, built with [Mintlify](https://mintlify.com).

## Preview locally

```bash
npm i -g mint
cd docs-site
mint dev            # http://localhost:3000
```

## Structure

- `docs.json` — navigation, theme, and tabs (Documentation · API Reference · SDKs).
- `*.mdx` — content pages using Mintlify components (Cards, Tabs, Steps,
  Accordions, ParamField/ResponseField, CodeGroup, callouts).
- `logo/`, `images/`, `favicon.svg` — brand assets.

## Deploy

Connect this folder to Mintlify (GitHub app) to publish at `docs.simapi.dev`.
Every push to `main` redeploys automatically.
