<div align="center">

# SimAPI

### The CI/CD layer for engineering simulations.

Automatically validate CFD, FEA, multiphysics, and robotics simulation output
against physical laws — before it reaches a design decision or an ML training set.

[![CI](https://img.shields.io/badge/CI-passing-brightgreen)](.github/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-black)](LICENSE)
[![Checks](https://img.shields.io/badge/physics%20checks-470%2B-orange)](core/physics_validator.py)
[![Domains](https://img.shields.io/badge/domains-21-purple)](core/physics_validator.py)

[Website](https://sim-api.vercel.app) · [Playground](https://simapiplayground.vercel.app) ·
[Docs](https://simapidocs.github.io) · [Status](https://simapistatus.vercel.app) ·
[Benchmarks](https://sim-api.vercel.app/benchmark)

</div>

---

## Table of contents

- [Mission](#mission)
- [Quick start](#quick-start)
- [Installation](#installation)
- [Architecture](#architecture)
- [The validation engine](#the-validation-engine)
- [Detection pipeline](#detection-pipeline)
- [Automatic repair](#automatic-repair)
- [The AI layer](#the-ai-layer)
- [CLI](#cli)
- [Configuration](#configuration)
- [API reference](#api-reference)
- [Benchmarks](#benchmarks)
- [Examples](#examples)
- [Project structure](#project-structure)
- [Testing](#testing)
- [Deployment](#deployment)
- [Design philosophy](#design-philosophy)
- [Security](#security)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## Mission

Engineering organizations run thousands of simulations a week. Today, a human
engineer eyeballs the output before anyone trusts it — checking that a CFD run
converged, that units weren't mixed up somewhere in the pipeline, that a
sensor didn't drift halfway through a sweep. That manual gate is slow,
subjective, and doesn't scale. Bad simulation data that slips through
silently poisons downstream design decisions and, increasingly, the training
sets for surrogate ML models.

**SimAPI is the automated validation gate.** Point it at simulation output —
in whatever format your tool produces it — and it returns a verdict backed by
470+ deterministic physics checks across 21 simulation domains, plus an
optional AI second pass that catches what rules structurally can't. Every
number this project publishes about itself (benchmark improvements, detection
recall, precision) is measured against a reproducible, randomized-corruption
benchmark harness anyone can re-run — see [Benchmarks](#benchmarks). If a
claim doesn't hold up, it gets corrected on the [changelog](https://sim-api.vercel.app/changelog),
not quietly dropped.

## Quick start

```bash
# 1. Install
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure (optional in dev — the AI layer is disabled without a key)
cp .env.example .env

# 3. Run the API
python launch.py            # http://localhost:8000, interactive docs at /docs

# 4. Try it
curl -X POST http://localhost:8000/v1/demo | python3 -m json.tool
```

Or with the CLI, against the hosted API (no local setup at all):

```bash
curl -fsSL https://sim-api.vercel.app/install.sh | sh
simapi login
simapi validate simulation.json
```

Or try it in the browser with zero installation: **[simapiplayground.vercel.app](https://simapiplayground.vercel.app)**.

## Installation

| Method | Command |
| ------ | ------- |
| Homebrew | `brew install TaxCollector23/tap/simapi` |
| npm (Node CLI) | `npm install -g simapi-cli` |
| curl (unix) | `curl -fsSL https://sim-api.vercel.app/install.sh \| sh` |
| PowerShell (Windows) | `irm https://sim-api.vercel.app/install.ps1 \| iex` |
| Docker | `docker run -p 8000:8000 --env-file .env simapi:latest` (build from this repo — no published image yet) |
| pip (Python SDK + CLI) | not yet published to PyPI — clone this repo and `pip install -e python-pkg/` for now |

All installers put the `simapi` command on your `PATH`. Run `simapi doctor`
after installing to confirm everything is wired up correctly (config
directory, credentials, API connectivity).

## Architecture

SimAPI is four connected systems, not one monolith. Each layer talks to the
others through a clean interface — the website has no business logic of its
own, and the CLI never re-implements backend logic:

```
                ┌──────────────────────────────────────────────┐
   client ───▶  │  FastAPI (api/server.py)                     │
   SDK / CLI    │   middleware: request-id · logging · metrics │
   curl / web   │   deps:       auth · rate limit               │
                │   handlers:   consistent error envelope       │
                └───────┬───────────────────────┬──────────────┘
                        │                        │
        ┌───────────────▼──────────┐   ┌─────────▼────────────────┐
        │ core/ingestion.py        │   │ core/physics_validator.py│
        │ 9 input formats +        │   │ 57 layers, 470+ checks   │
        │ 500+ column aliases      │   │ across 21 domains        │
        └───────────────┬──────────┘   └─────────┬────────────────┘
                        └── DataFrame ───────────▶│  synchronous verdict
                                                  │
                                        ┌─────────▼──────────────┐
                                        │ core/ai_validator.py   │
                                        │ fast quick-check (default,│
                                        │ ~2-18s) OR core/ai_orch-│
                                        │ estrator.py (5-phase   │
                                        │ deep analysis, opt-in) │
                                        │ polled via /job/{id}/ai│
                                        └────────────────────────┘
                                                  │
                                        ┌─────────▼──────────────┐
                                        │ core/repair.py         │
                                        │ deterministic, reversible│
                                        │ fixes with a preview   │
                                        └────────────────────────┘
```

- **`api/config.py`** — immutable, env-sourced settings (12-factor).
- **`api/security.py`** — API-key auth (constant-time comparison) + token-bucket rate limiter.
- **`api/observability.py`** — JSON logging, request-id context propagation, Prometheus metrics.
- **`api/errors.py`** — typed errors → one consistent JSON envelope with stable error codes.
- **`web/`** — Next.js 15 site. On Vercel by default it runs a ~20-check TypeScript
  port of the engine (`web/lib/validation-engine.ts`) for zero-cold-start serverless
  validation. Set `PYTHON_API_URL` to proxy to a real deployment of this Python
  API instead, and the site transparently upgrades to the full 470+ check engine
  — the dashboard shows a "Full engine" vs "Lite engine" badge so you always know
  which one you're getting. Nothing about this is hidden or faked.

The CLI (both the Python and Node implementations, kept behaviorally
identical) never duplicates validation logic — it's a thin client over the
same API everything else talks to.

## The validation engine

`core/physics_validator.py` runs data through 57 layers covering:

- **Universal checks** (all domains) — input quality, plausibility bounds,
  numerical stability, statistical distribution shape, outlier detection,
  near-duplicate rows, cross-variable relationships, conservation laws,
  dimensional consistency, temporal drift, monotonicity, symmetry, scaling
  laws, information entropy, autocorrelation, stationarity, multicollinearity,
  regression quality, signal quality, sensor fusion consistency, boundary
  conditions, convergence, energy balance, and more.
- **A universal conservation-law detector** (`core/universal_validator.py`) —
  RANSAC-discovered physical invariants (e.g. deriving the gas constant or a
  Reynolds-number relationship directly from your data, robust to up to ~40%
  corruption), a non-dimensional coupling matrix, and state-space observation.
  This is the layer responsible for most of the recall improvement described
  in [Benchmarks](#benchmarks).
- **21 domain-specific layers** — one per `SimulationType`: aerodynamics,
  fluid dynamics, structural/FEA, thermodynamics, robotics, combustion,
  acoustics, electromagnetics, geomechanics, biomechanics, nuclear, plasma,
  chemical, hydrodynamics, meteorology, astrophysics, materials, tribology,
  aeroelasticity, cryogenics, and multiphysics.

Every check returns a `PhysicsCheck` with a name, status (`passed` /
`warning` / `failed`), a human-readable description, the offending value, and
a category. The report's `all_checks_count` is the count of **unique check
names**, not total invocations — running 470 checks against 200 trials isn't
"94,000 checks ran," it's 470 distinct things that were tested. That
deduplication is enforced in both the Python engine and the TypeScript port.

## Detection pipeline

For a batch of trials, the pipeline is:

```
Input → Parser → Normalization → Validation → Consistency Analysis
      → Confidence Scoring → Repair Suggestions → Output
```

1. **Parser** (`core/ingestion.py`) auto-detects format (or takes an explicit
   hint) and converts everything into one internal DataFrame representation
   before any validation runs. See [supported formats](#examples) below.
2. **Normalization** applies 500+ column aliases (`cd`, `Cd`, `drag_coeff`,
   `coefficient_of_drag` → `drag_coefficient`) so checks fire regardless of
   which tool produced the data — ANSYS, OpenFOAM, STAR-CCM+, Fluent, COMSOL,
   SU2, Abaqus, and MATLAB naming conventions are all covered.
3. **Validation** runs all 57 layers (see above).
4. **Consistency analysis / confidence scoring** — the report includes an
   overall status, a confidence level (`high`/`medium`/`low`), a per-column
   statistical summary, and a checks-by-category breakdown.
5. **Repair suggestions** — optionally, `core/repair.py` proposes safe fixes
   (see [Automatic repair](#automatic-repair)).
6. **Output** — a single JSON report with `issues`, `exclusions`,
   `statistics`, and `training_ready` (whether the data, after exclusions, is
   fit to train an ML model on).

## Automatic repair

After validation, `core/repair.py` looks for **structural** problems it can
fix deterministically and reversibly — it never touches a physics violation
(an out-of-bounds value, a unit error) because that's a data-quality problem
for you to investigate, not something SimAPI silently rewrites:

| Repair | What it catches |
| ------ | ---------------- |
| `duplicate_rows` | Exact-duplicate rows (copy-paste artifacts) |
| `duplicate_or_missing_ids` | A trial-ID column with gaps or repeats |
| `timestamp_ordering` | Rows out of chronological order |
| `wrapped_angles` | Angle values outside [-180°, 180°] (convention mismatch) |
| `missing_value_interpolation` | Short (≤3-row) NaN gaps in numeric columns, linearly interpolated |

Every repair produces a preview (before/after per affected row) before
anything is applied:

```bash
simapi repair simulation.json           # preview only
simapi repair simulation.json --apply   # writes simulation.repaired.json
```

Or via the API: `POST /v1/repair` with `"apply": false` (default, preview) or
`"apply": true` (returns the repaired dataset).

## The AI layer

There are two AI paths, and the default one is intentionally fast — it's a
sanity check, not an investigation:

- **Quick check (default)** — `core/ai_validator.py`. A small, non-reasoning-
  heavy free model (`nvidia/nemotron-nano-9b-v2:free` by default) answers one
  question: is this dataset normal or not. Typically 2-18 seconds. Runs after
  every validation when an OpenRouter key is configured (`run_ai: true`,
  the default).
- **Deep orchestrator (opt-in via `deep_ai: true`)** — `core/ai_orchestrator.py`.
  A 5-phase pipeline using a larger model (`SIMAPI_AI_MODEL`, defaults to
  `nvidia/nemotron-3-ultra-550b-a55b:free`):
  1. **Phase 0 — Dataset profiling.** Reads raw distributions and correlations,
     produces a test plan (priority checks, checks to skip, expected ranges)
     that parameterizes the physics engine.
  2. **Phase 1 — Physics engine** runs with that test plan.
  3. **Phase 2 — Pattern recognition.** Collapses many individual check
     failures into root-cause diagnoses, flags likely false positives, and
     identifies checks that *should* have fired but didn't.
  4. **Phase 3 — Targeted follow-up probes** (`core/followup_probes.py`):
     `probe_gas_constant` (ideal-gas-law unit-error detection),
     `probe_joint_distribution_shift` (relationship changes between halves of
     the dataset), `probe_duplicate_cosine` (near-duplicate row detection),
     `probe_regime_change` (concatenated-dataset detection via windowed CV),
     `probe_physically_impossible_combinations` (domain-specific physics,
     e.g. thin-airfoil-theory consistency for aerodynamics).
  5. **Phase 4 — Final synthesis.** A confidence-weighted verdict, a
     corruption-probability distribution, and — the most useful field —
     `what_only_ai_can_see`: findings no rule-based check could produce.

Both paths degrade gracefully with no API key configured: physics validation
is completely unaffected, and `ai_status` reports `"disabled"` rather than
failing the request.

## CLI

Both implementations (Python: `python-pkg/simapi/cli.py`, Node:
`sdk-node/bin/simapi.js`) are zero-dependency and behaviorally identical:

```
simapi login                          Authenticate via the browser, save the API key
simapi logout                         Remove stored credentials
simapi whoami                         Show account, plan, and masked API key
simapi init                           Create a simapi.json config
simapi validate <file> [options]      Validate a file and print a report
  --type <domain>                       simulation domain
  --json                                raw JSON output
  --fail-on <warning|failed>            exit non-zero on that status
simapi watch <file>                   Re-validate automatically on file change
simapi repair <file> [--apply]        Preview or apply automatic repairs
simapi doctor [--fix]                 Diagnose config, credentials, connectivity,
                                       and project setup; --fix what's fixable
simapi explain                        Explain the last validation run in detail
simapi usage                          Requests today/month, quota, avg latency
simapi api-key <show|rotate|delete>   Manage your API key
simapi config [set <key> <value>]     Show or update CLI configuration
simapi version                        Print the installed CLI version
```

The CLI never dumps unreadable JSON unless you ask for it with `--json` — by
default you get colored status, a summary table, and the top issues in plain
English.

## Configuration

All configuration is environment-driven — see [`.env.example`](.env.example)
for the full list. Never hardcode credentials; every secret-shaped value here
is read from the environment with a safe default.

| Variable | Default | Purpose |
| -------- | ------- | ------- |
| `SIMAPI_REQUIRE_AUTH` | `false` | Enforce API-key auth |
| `SIMAPI_API_KEYS` | — | Comma-separated accepted keys |
| `SIMAPI_RATE_LIMIT_RPM` | `120` | Sustained requests/minute per caller |
| `SIMAPI_CORS_ORIGINS` | `*` | Allowed CORS origins |
| `SIMAPI_OPENROUTER_API_KEY` | — | Enables the AI layer when set |
| `SIMAPI_AI_QUICK_MODEL` | `nvidia/nemotron-nano-9b-v2:free` | Model for the default fast AI check |
| `SIMAPI_AI_QUICK_TIMEOUT_SECONDS` | `18` | Timeout for the quick check |
| `SIMAPI_AI_MODEL` | `nvidia/nemotron-3-ultra-550b-a55b:free` | Model for the deep orchestrator |
| `SIMAPI_AI_TIMEOUT_SECONDS` | `75` | Timeout for the deep orchestrator |

## API reference

Interactive docs are served at `/docs` (Swagger UI) and `/redoc`; the raw
OpenAPI 3.1 schema is at `/openapi.json`. Visiting the API root (`/`, e.g.
`http://localhost:8000/`) redirects to `/docs` — this server is the
validation API, not the website (that's a separate Next.js app in `web/`,
normally on `:3000`).

| Method | Path | Description |
| ------ | ---- | ----------- |
| `GET`  | `/v1/health` | Liveness + service facts (unauthenticated) |
| `GET`  | `/v1/metrics` | Prometheus metrics |
| `POST` | `/v1/validate` | Validate a JSON batch of trials |
| `POST` | `/v1/validate/upload` | Validate an uploaded file (any [supported format](#examples)) |
| `POST` | `/v1/validate/physics-only` | Physics checks only (skip AI) |
| `POST` | `/v1/validate/setup` | Pre-flight: validate a mesh/solver/BC setup *before* running the simulation |
| `POST` | `/v1/repair` | Preview or apply automatic structural repairs |
| `POST` | `/v1/demo` | Validate seeded synthetic data |
| `GET`  | `/v1/job/{id}` | Fetch a job's physics result |
| `GET`  | `/v1/job/{id}/ai` | Poll for the async AI result (includes any AI-added exclusions) |
| `GET`  | `/v1/jobs?limit=&offset=` | List recent jobs (paginated) |

**Consistent error contract.** Every error returns the same envelope with a
stable `code`, a message, and a `request_id` that correlates to server logs:

```json
{ "error": { "code": "rate_limited", "message": "Rate limit exceeded. Slow down and retry.", "request_id": "3f9c…" } }
```

**Optional context fields** on `/v1/validate` sharpen the AI layer's output
without being required: `geometry_description`, `what_are_you_measuring`,
`expected_output_ranges`, `reference_dataset_id`, `known_issues`,
`ml_model_type`, and `deep_ai` (opt into the 5-phase orchestrator instead of
the default quick check).

## Benchmarks

Every number below comes from `benchmark/run_benchmark.py` — a script you can
run yourself in about 12 seconds on a laptop CPU, no GPU required. It
generates a synthetic but physically-consistent aerodynamics dataset (1,400
training trials, 600 held-out test trials), injects ~30% corruption across 6
categories with randomized placement (not clustered — a harder, more
realistic test than fixed-position corruption), and trains a gradient-boosted
tree and a small MLP on four versions of the data: untouched-corrupted, a
naive IQR/z-score statistical baseline, SimAPI-validated, and a clean oracle
ceiling.

```bash
python -m benchmark.run_benchmark
```

**Current results** (mean over 5 seeds):

| Metric | Value |
| ------ | ----- |
| Exclusion precision | 99% |
| Exclusion recall | 95% |
| GBT MAPE improvement vs corrupted | +19.9% |
| MLP MAPE improvement vs corrupted | +67.0% |
| Per-category recall | solver divergence 100%, unit conversion 100%, sensor drift 99%, copy-paste 100%, cross-variable 100%, measurement noise 70% |

Live, always-current numbers: **[sim-api.vercel.app/benchmark](https://sim-api.vercel.app/benchmark)**.

This project has published two rounds of corrections to its own benchmark
numbers rather than let a stale claim stand — see the
[changelog](https://sim-api.vercel.app/changelog) versions 3.4 and 3.5.
Measurement noise (70% recall) remains the hardest category: low-magnitude
noise within physically plausible bounds is fundamentally difficult to
distinguish from real variance, and that's stated plainly rather than
smoothed over.

## Examples

**Supported input formats** — everything normalizes into one internal
representation before validation, so the engine never cares where the data
came from: JSON, CSV, YAML, TOML, TXT (key:value blocks), Markdown (pipe
tables), VTK, NumPy (`.npy`/`.npz`), and OpenFOAM `postProcessing` output.

```bash
# JSON
simapi validate simulation.json

# CSV — column headers are aliased automatically
simapi validate results.csv --type structural

# YAML
simapi validate scenario.yaml
```

```python
import simapi

result = simapi.validate(
    data="cfd_output.csv",
    simulation_type="aerodynamics",
    conditions={"velocity": 15.0, "altitude": 120.0},
)

print(result.summary())
print(result.status)             # "passed" | "warning" | "failed"
print(result.training_ready)     # True / False
print(result.drag_coefficient)   # StatResult(mean=0.312, std=0.018, n=196)
```

```bash
curl -X POST https://sim-api.vercel.app/api/v1/validate \
  -H "Content-Type: application/json" \
  -d '{
    "data": [{"cd": 0.31, "cl": 0.8, "re": 4.0e5, "ma": 0.04}],
    "simulation_type": "aerodynamics",
    "run_ai": true
  }'
```

## Project structure

| Path | What |
| ---- | ---- |
| `core/` | Validation engine: `physics_validator.py` (57 layers), `universal_validator.py` (conservation-law detector), `ingestion.py` (parser + aliasing), `repair.py`, `ai_validator.py` (quick check), `ai_orchestrator.py` (deep 5-phase pipeline), `followup_probes.py`, `mesh_validator.py` (pre-flight) |
| `api/` | FastAPI service: `server.py`, `config.py`, `security.py`, `observability.py`, `errors.py` |
| `benchmark/` | `run_benchmark.py` (5-seed harness), `results.json` (published, harness-generated) |
| `sdk/`, `python-pkg/` | Python SDK + CLI |
| `sdk-node/` | Node SDK + CLI (behaviorally identical to the Python CLI) |
| `tests/` | Pytest suite — API contract, ingestion, repair, physics, mesh, security |
| `web/` | Next.js 15 site: marketing pages, dashboard, playground, and the TypeScript lite engine used on serverless deployments |
| `docs-site/`, `docs-pages/` | Developer documentation sources |
| `Formula/` | Homebrew tap formula |

## Testing

```bash
make test       # full pytest suite
make cov        # coverage report
make lint       # ruff
make typecheck  # mypy
```

The suite covers API contracts (every endpoint, every error path), the
ingestion layer (every supported format), the repair layer (every repair
type plus edge cases like conflicting repairs on the same column), the mesh
pre-flight validator, and security (auth, rate limiting). CI runs the full
matrix (Python 3.10, 3.11, 3.12) on every push.

## Deployment

The image is a standard, non-root, health-checked container and runs
anywhere containers run:

```bash
docker build -t simapi:latest .
docker run -p 8000:8000 --env-file .env simapi:latest
```

- **Render** — `render.yaml` at the repo root defines the service; connect
  the repo via Render's Blueprint flow for one-click deploy.
- **Railway** — `railway.json` at the repo root; connect the repo for
  one-click deploy.
- **AWS / Azure / GCP** — push to a registry and run on ECS/Fargate, Cloud
  Run, or Container Apps; scrape `/v1/metrics`, health-check `/v1/health`.
- **Kubernetes** — use `/v1/health` for liveness/readiness probes and the
  Prometheus endpoint for HPA signals.
- **Vercel (website only)** — `web/` deploys as a standalone Next.js app.
  Without `PYTHON_API_URL` set, it runs the TypeScript lite engine; set it to
  a deployed instance of this API to upgrade to the full engine.

## Design philosophy

- **The engine is the product.** The website contains no business logic; the
  CLI never duplicates validation logic. Everything routes through the same
  core engine.
- **No fabricated numbers, ever.** Every benchmark claim is reproducible by
  running `benchmark/run_benchmark.py` yourself. When a number didn't hold up
  under a harder test, it was corrected publicly on the changelog rather than
  quietly replaced.
- **Precision over recall when they trade off.** A false positive — excluding
  a genuinely good trial — is worse than a missed corruption, because it
  erodes trust in the tool. Exclusion precision has held at 99% across every
  benchmark iteration; recall has been the metric under active improvement.
- **Repair, don't guess.** The automatic-repair layer only fixes structural
  problems (duplicate rows, timestamp order, wrapped angles) with a preview
  before anything is applied. It never rewrites a physics violation — that's
  a decision for the engineer, not the tool.
- **Deterministic first, AI second.** The physics engine's verdict never
  depends on an LLM being available or responding correctly. The AI layer is
  additive — it degrades to `"disabled"` cleanly, never blocks a validation.
- **No placeholder features.** If a feature isn't real — backed by an actual
  implementation, not a mockup — it doesn't ship. See the
  [roadmap](https://sim-api.vercel.app/roadmap) for an explicit list of
  what's deliberately not built yet, and why.

## Security

- API keys are hashed (SHA-256) before storage; the raw key is shown exactly
  once at creation.
- Constant-time comparison for key auth (`api/security.py`) to avoid timing
  side-channels.
- Token-bucket rate limiting per caller, with a `Retry-After` header on 429s.
- No secrets are ever hardcoded — every credential is read from the
  environment with a safe, non-secret default. `.env`, `.env.local`, and
  `.env.local.rtf`-style files are gitignored.
- See [SECURITY.md](SECURITY.md) for the vulnerability disclosure process.

## Troubleshooting

**`simapi doctor` is your first move for any CLI issue** — it checks config
directory permissions, saved credentials, live API connectivity (with
latency), and `simapi.json` validity, and reports exactly what's wrong.

| Symptom | Likely cause | Fix |
| ------- | ------------ | --- |
| `AI validation disabled: no API key configured` | `SIMAPI_OPENROUTER_API_KEY` not set | Set it in `.env`; physics validation still works without it |
| AI check returns an error / times out | Free-tier model rate-limited upstream, or a reasoning model exhausted its token budget on hidden chain-of-thought | The quick-check path retries once automatically; if it still fails, physics results are unaffected — the AI layer is additive, not blocking |
| `Full engine` badge shows `Lite engine` on the website | `PYTHON_API_URL` isn't set (or isn't reachable) on that deployment | Deploy this API and set `PYTHON_API_URL` in the Next.js project's env vars |
| `localhost:8000` shows a 404 | You hit the API root without a path | It now redirects to `/docs` — port 8000 is the Python API, not the website (that's `:3000`, a separate `npm run dev` process) |
| CLI command not found after install | `PATH` doesn't include the install directory | Re-run the installer (it appends to your shell profile) or open a new shell |

## FAQ

**Does this require an internet connection / API key to work at all?**
No. The physics engine (`core/physics_validator.py`) is fully local and
deterministic — no network calls, no API key required. Only the optional AI
second pass needs an OpenRouter key.

**Why does the dashboard show a different check count than I expect?**
The count is *unique check names*, not total invocations. 470 checks against
2,000 trials is still "470 checks" — the same check evaluated many times
isn't 470×2,000 distinct things.

**Why is GBT's improvement smaller than MLP's?**
Gradient-boosted trees are inherently robust to the outlier-style corruptions
in this benchmark; neural networks are far more sensitive to the distribution
shift that sensor drift causes. Both are reported, deliberately, instead of
leading with the more flattering number — see [Benchmarks](#benchmarks).

**Can I add a new simulation domain?**
Yes — see [CONTRIBUTING.md](CONTRIBUTING.md) for the checklist (bounds
table, domain-specific layer, column aliases, a test).

**Is the AI layer required?**
No. It's additive. Every response includes `ai_status` — `"disabled"` when
no key is configured, and physics validation is complete and correct on its
own either way.

## Roadmap

An honest accounting of what's shipped, in progress, and explicitly not
built yet lives at **[sim-api.vercel.app/roadmap](https://sim-api.vercel.app/roadmap)**
— including things like organizations/RBAC and billing that need a durable
backend data store this project doesn't have yet, stated plainly rather than
stubbed out with placeholder UI. See [CHANGELOG.md](CHANGELOG.md) for shipped
work.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow, coding
conventions, and how to add a new simulation domain or validation check.

```bash
make dev        # deps + pre-commit hooks
make test       # run the suite
make lint       # ruff
make typecheck  # mypy

# Marketing site / dashboard / playground
cd web && npm install && npm run dev        # http://localhost:3000
```

## License

MIT — see [LICENSE](LICENSE).
