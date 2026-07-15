# simapi (Node.js SDK + CLI)

Validate simulation results against physical laws from Node.js or the terminal.
Requires Node 18+.

## Install

```bash
npm install simapi-cli          # SDK
npm install -g simapi-cli       # CLI (`simapi` command)
```

## SDK

```ts
import { SimAPI } from "simapi-cli";

const client = new SimAPI(process.env.SIMAPI_API_KEY);

const result = await client.validate(rows, {
  simulationType: "aerodynamics",
  conditions: { velocity: 15.0 },
});

if (result.status === "failed") {
  throw new Error("Simulation rejected");
}

// Or validate a file directly:
const r2 = await client.validateFile("simulation.json", { simulationType: "structural" });
```

Configuration falls back to environment variables:

- `SIMAPI_API_KEY` — your key
- `SIMAPI_BASE_URL` — API base URL (default `https://api.simapi.dev`)

Errors throw `SimAPIError` with `code`, `status`, and `requestId`.

## CLI

```bash
simapi login                 # paste your key (saved to ~/.simapi/config.json)
simapi init                  # write a sample simulation.json
simapi validate simulation.json
simapi validate run.json --type structural --json
simapi validate run.csv --fail-on warning   # non-zero exit for CI
simapi whoami
simapi logout
simapi version
simapi help
```

`SIMAPI_API_KEY` overrides the saved key, which is convenient in CI.

## Build (for contributors)

```bash
npm install
npm run build     # compiles src/ → dist/
```

The CLI (`bin/simapi.js`) is plain Node ESM and runs without a build step.
