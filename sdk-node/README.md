# simapi-cli

Validate engineering simulation output against physical laws — from your terminal or from Node.js.

The `simapi` CLI checks a simulation dataset (JSON, CSV/TSV, or a text/log dump)
against dimensional analysis and domain physics, tells you whether the data is
trustworthy, and gates your CI when it isn't. The hosted API is open by
default — **no account, sign-in, or API key required.**

Requires **Node.js 18 or newer** (uses built-in `fetch`). Zero runtime dependencies.

## Install

```bash
npm install -g simapi-cli
```

This installs the global `simapi` command on **Windows, macOS, and Linux**.
Verify it:

```bash
simapi version
simapi doctor      # checks Node version + API connectivity
```

<details>
<summary>Platform notes</summary>

- **macOS / Linux** — if `npm i -g` needs `sudo`, prefer a Node version manager
  (nvm, fnm, volta) so global installs land in your home directory without root.
- **Windows** — works in PowerShell, `cmd`, and Git Bash. If `simapi` isn't found
  after install, open a new terminal so the updated `PATH` is picked up.
- No Node yet? Install it from <https://nodejs.org> (or `brew install node`,
  `winget install OpenJS.NodeJS`), then re-run the install command.

</details>

You can also run the one-line installers, which simply wrap `npm install -g simapi-cli`:

```bash
# macOS / Linux
curl -fsSL https://sim-api.vercel.app/install.sh | sh
```

```powershell
# Windows PowerShell
irm https://sim-api.vercel.app/install.ps1 | iex
```

## Quick start

```bash
simapi init                          # write a simapi.json config
simapi validate simulation.json      # validate and print a report
simapi validate simulation.csv       # CSV/TSV are parsed locally
simapi validate run.json --json      # raw JSON for scripting
```

## CLI commands

```bash
simapi validate <file>               # validate a .json/.csv/.txt file, print a report
simapi ci [file]                     # CI gate: non-zero exit when validation fails
simapi dimensional <file>            # raw dimensional-analysis report (laws, row findings)
simapi watch <file>                  # re-validate automatically on file change
simapi repair <file> [--apply]       # preview/apply automatic structural repairs
simapi explain                       # explain the issues from the last run
simapi domains                       # list supported simulation types
simapi usage                         # requests today/this month, avg time
simapi config [set <key> <value>]    # show or update CLI configuration
simapi doctor [--fix]                # diagnose config + connectivity
simapi version
simapi help                          # run `simapi <command> --help` for details
```

Common flags: `--type <domain>`, `--json`, `--no-ai`, `--fail-on <warning|failed>`.

### CI gate

`simapi ci` is built for pipelines. It validates the file (falling back to the
`files` entry in `simapi.json` when omitted), prints a compact verdict, and
**exits non-zero when the gate fails** so a bad simulation blocks the build:

```bash
simapi ci simulation.json                 # strict: warnings OR failures block
simapi ci run.csv --fail-on failed        # only hard failures block
simapi ci --json                          # machine-readable verdict for tooling
```

```jsonc
// simapi ci --json
{ "ok": false, "gate": "fail", "status": "failed", "failed": 1, "warnings": 0, "training_ready": false }
```

Example GitHub Actions step:

```yaml
- run: npx --yes simapi-cli ci simulation.json --fail-on warning
```

### API keys (optional)

The hosted API needs no key. A key is only relevant if you run your own
deployment with `SIMAPI_API_KEYS` set:

```bash
simapi api-key set <key>      # save a key to ~/.simapi/config.json (chmod 600)
simapi api-key show
simapi api-key delete
```

`SIMAPI_API_KEY` in the environment overrides the saved key — convenient in CI.

## Node.js SDK

The package also ships a typed SDK:

```ts
import { SimAPI } from "simapi-cli";

const client = new SimAPI(process.env.SIMAPI_API_KEY); // key is optional

const result = await client.validate(rows, {
  simulationType: "aerodynamics",
  conditions: { velocity: 15.0 },
});

if (result.status === "failed") {
  throw new Error("Simulation rejected");
}

// Or validate a JSON file directly:
const r2 = await client.validateFile("simulation.json", { simulationType: "structural" });
```

Configuration falls back to environment variables:

- `SIMAPI_API_KEY` — your key (optional for the hosted API)
- `SIMAPI_BASE_URL` — API base URL (default `https://sim-api.vercel.app/api`)

Errors throw `SimAPIError` with `code`, `status`, and `requestId`.

## Contributing / building

```bash
npm install
npm run build      # compiles src/ (TypeScript SDK) → dist/
```

The CLI (`bin/simapi.js`) is plain Node ESM and runs with no build step.

## License

MIT
