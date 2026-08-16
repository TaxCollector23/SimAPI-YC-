# SimAPI GitHub Action

Fail a build when a simulation output file contains physics violations.

The action installs [`simapi-cli`](https://www.npmjs.com/package/simapi-cli),
validates a file against SimAPI's deterministic engines (physical-law bounds,
dimensional consistency, conservation relations across 21 domains), and gates
the job on the verdict. Nothing about your data leaves the deterministic path
unless you explicitly opt into the AI layer.

## Quick start

```yaml
# .github/workflows/validate.yml
name: Validate simulation output
on: [push, pull_request]

jobs:
  physics-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: TaxCollector23/SimAPI-YC-/integrations/github-action@main
        with:
          file: data/cfd_output.csv
          simulation-type: aerodynamics
          fail-on: failed
```

If any row is physically impossible, the step exits non-zero and the build
fails. A JSON result is uploaded as a workflow artifact and a summary table is
written to the job summary.

## Inputs

| Input | Default | Description |
|---|---|---|
| `file` | — (required) | Path to the simulation output file (`.csv`, `.json`, `.txt`). |
| `engine` | `validate` | `validate` (both engines via the hosted API, works without a key) or `dimensional` (dimensional-analysis cascade only, needs `api-key`). |
| `simulation-type` | `""` | Declared domain, e.g. `aerodynamics`, `structural`, `robotics`. |
| `conditions` | `""` | Declared operating conditions for the dimensional engine, e.g. `velocity=15,altitude=120`. |
| `fail-on` | `failed` | `failed` → fail on impossible rows; `warning` → fail on any impossible **or** inconsistent row; `never` → collect only. |
| `api-key` | `""` | Sets `SIMAPI_API_KEY`. Not needed for the open hosted API with `validate`; required for `dimensional`. |
| `base-url` | `""` | Sets `SIMAPI_BASE_URL`. Point at your own deployment for private / air-gapped runs. |
| `cli-version` | `latest` | Version of `simapi-cli` to install. |
| `upload-report` | `true` | Upload the JSON result as an artifact. |
| `sarif` | `false` | Also generate a SARIF 2.1.0 report and upload it to GitHub code scanning. Requires `permissions: security-events: write` on the job and the Python backend on the target deployment. |

## Outputs

| Output | Description |
|---|---|
| `status` | Verdict: `passed`, `warning`, or `failed`. |
| `training-ready` | `true` if the dataset is safe for ML training. |
| `impossible` | Count of physically impossible rows. |
| `inconsistent` | Count of internally inconsistent rows. |
| `result-path` | Path to the raw JSON result. |

## How the gate works

The action runs the CLI with `--json` (which returns a machine-readable result)
and makes the pass/fail decision in [`run.sh`](./run.sh) so the policy is
explicit:

- `fail-on: failed` — non-zero exit when there is at least one **impossible**
  row (verdict `failed`).
- `fail-on: warning` — non-zero exit when there is any **impossible or
  inconsistent** row (verdict not `passed`).
- `fail-on: never` — always exit 0; use it to record results without blocking.

A failed request (network error, auth error) produces no JSON and fails the
step, so a misconfigured gate never silently passes.

## Private / self-hosted deployments

Point the action at your own deployment and, if it enforces auth, pass a key
from repository secrets:

```yaml
- uses: TaxCollector23/SimAPI-YC-/integrations/github-action@main
  with:
    file: data/rollout.csv
    engine: dimensional
    conditions: velocity=15,altitude=120
    base-url: https://simapi.internal.example.com/api
    api-key: ${{ secrets.SIMAPI_API_KEY }}
    fail-on: warning
```

## Using outputs downstream

```yaml
- id: simapi
  uses: TaxCollector23/SimAPI-YC-/integrations/github-action@main
  with:
    file: data/cfd_output.csv
    fail-on: never          # don't block; branch on the result instead
- if: steps.simapi.outputs.training-ready == 'false'
  run: echo "Dataset is not training-ready — skipping the retrain job."
```

## Notes

- Requires the runner to have network access to the SimAPI deployment.
- The hosted API is currently open for evaluation; for production CI, run against
  a deployment you control via `base-url`.
- The action pins `actions/setup-node`, `actions/upload-artifact` — Node 18+ is
  required by `simapi-cli`.
