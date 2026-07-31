<div align="center">

# SimAPI

### Automated physical-law validation for engineering simulation output.

SimAPI checks CFD, FEA, multiphysics, and robotics simulation results against
physical laws, dimensional consistency, conservation principles, and known
constants — before those results reach a design decision, a regulatory
submission, or a machine-learning training set.

[![CI](https://img.shields.io/badge/CI-passing-brightgreen)](.github/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-black)](LICENSE)
[![Checks](https://img.shields.io/badge/physics%20checks-280%2B-orange)](core/physics_validator.py)
[![Domains](https://img.shields.io/badge/domains-21-purple)](core/physics_validator.py)

</div>

---

## Table of contents

- [What SimAPI is](#what-simapi-is)
- [What it is not](#what-it-is-not)
- [Core capabilities](#core-capabilities)
- [The validation engines](#the-validation-engines)
- [Verdict model](#verdict-model)
- [Quickstart](#quickstart)
- [Using the SDK](#using-the-sdk)
- [Using the CLI](#using-the-cli)
- [API reference](#api-reference)
- [Error contract](#error-contract)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Repository layout](#repository-layout)
- [Development](#development)
- [Roadmap](#roadmap)
- [License](#license)

---

## What SimAPI is

A validation server. You give it simulation output — a CSV, JSON, or any of
several other formats; a declaration of the simulation type; and optionally the
known operating conditions of the run. It returns a structured verdict: which
rows are physically impossible, which are internally inconsistent, and which
are unsuitable for training a surrogate or ML model — with the reason for every
finding and, where applicable, a suggested fix.

The default path runs **entirely deterministic Python** (NumPy, SciPy, pandas).
Nothing leaves your machine. There is an optional AI layer, and it must be
enabled explicitly (see [The AI reasoning layer](#the-ai-reasoning-layer)).

There are two complementary validation engines, described below:

1. **The physics rule engine** (`core/physics_validator.py`) — thousands of
   hand-specified checks against per-domain plausibility bounds, conservation
   laws, cross-variable relations, and distribution statistics.
2. **The dimensional-analysis engine** (`core/dimensional/engine.py`) — an
   equation-discovery approach. It resolves column names to SI dimensions,
   discovers dimensionless (Pi) groups in the data itself, and tests the data
   against those groups, against physical constants, and against declared
   conditions. Adding a new domain requires no new code — only column-name
   patterns and optionally new constants, both of which are data, not logic.

The two engines run together in the default `/v1/validate` pipeline and each is
also exposed separately (`/v1/validate/physics-only` and
`/v1/validate/dimensional`).

## What it is not

An honest statement of the boundary, because it matters for how you should use
the output:

**Self-consistent-but-wrong data is undetectable from output alone.** A run that
used the wrong turbulence model produces output that is dimensionally perfect,
smooth, satisfies every Pi law and every semantic bound, and is simply
incorrect. Every layer of SimAPI tests the data against *itself* or against
physical constants that the wrong model also respects. Detecting that error
requires comparison against experiment or a trusted reference run — information
that is not in the dataset.

This boundary is stated in every report (the `known_impossible` field). A clean
report means *consistent with itself, with physical constants, and with the
declared conditions*. It does not mean *physically correct*.

SimAPI also never silently rewrites physics. The [repair layer](#repair-layer)
fixes structural problems (duplicate rows, out-of-order timestamps, wrapped
angles) and will not touch a physically implausible value.

---

## Core capabilities

### The physics rule engine

`core/physics_validator.py` — a deterministic engine covering **21 simulation
domains**:

`aerodynamics`, `fluid_dynamics`, `structural`, `thermodynamics`, `robotics`,
`combustion`, `acoustics`, `electromagnetics`, `geomechanics`, `biomechanics`,
`nuclear`, `plasma`, `chemical`, `hydrodynamics`, `meteorology`,
`astrophysics`, `materials`, `tribology`, `aeroelasticity`, `cryogenics`,
`multiphysics`.

Each domain has a table of per-column plausibility bounds (e.g. `Mach number`
must lie in `[0.0, 0.99]`, `void_fraction` in `[0, 1]`), backed by a set of
physical constants (`core/physics_validator.py:51`) such as sea-level air
density, the ideal-gas constant, and the Stefan-Boltzmann constant. The checks
span:

- **Plausibility bounds** — every numeric column is checked against its
  domain-specific operating envelope.
- **Conservation laws** — mass, momentum, and energy relations between columns
  are verified where the domain defines them.
- **Dimensional consistency** — relationships between columns must respect their
  units (see the dimensional engine, below).
- **Cross-variable relationships** — e.g. `Re = ρ·v·L/μ`, `Ma = v/c_sound`,
  `P = ρRT`.
- **Distribution statistics** — mean, standard deviation, median, percentiles,
  skewness, kurtosis, and coefficient of variation per column.
- **Outlier detection** — z-score based row exclusion with a documented
  threshold.
- **Domain-specific rules** — one-off checks that only apply inside a single
  domain.

Output is per-issue: name, status, description, the offending value, the
threshold it crossed, and a human-readable detail. Only warnings and failures
are surfaced; passing checks are counted, not dumped.

### The dimensional-analysis engine

`core/dimensional/engine.py` — the orchestrator for the dimensional-analysis
stack in `core/dimensional/`. Its design avoids the unbounded-suppression
problem of hand-written checks (every check encodes an assumption; real data
violates it legitimately; a suppression is added; the suppression needs its own
exceptions). Instead it ships **~25 hand-specified rules** and gets domain
coverage from a **units dictionary** — which is data, not logic.

The processing layers, in order:

| Layer | Module | What it does |
| ----- | ------ | ------------ |
| 0 | `units_resolver.py` | Maps each column name to an SI dimension with a confidence score, using a dictionary, unit-suffix detection, and unit conversion factors. An optional LLM fallback classifies names the dictionary misses; its results are cached persistently in `units_cache.py` so an unusual name is only ever asked once. |
| 1 | `pi_basis.py` | Discovers dimensionless (Pi) groups from the resolved units using an exact rational null-space computation. This is Buckingham-Pi theorem applied mechanically. |
| 2 | `pi_laws.py` | Pi groups that are constant across rows are reported as discovered physical laws. |
| 3 | `pi_laws.py` | Pi groups matching a **known physical constant** (g, c, ρ_air, R_air, …) are anchored. This is the defence against majority corruption: if most rows have been corrupted the same way, they define the "norm" — a known constant is the one reference point corruption cannot move. |
| 4 | `pi_laws.py` | Bimodal-split detection when no anchor applies: if a Pi group has two distinct stable values, that itself is a finding. |
| 5 | `response_surface.py` | For non-constant physics (`C_D = f(Re, Ma)`), residuals are learned against a Pi-space response surface using k-NN local regression plus a robust global IRLS/Huber fit. This catches in-range corruption that no bound or law would flag. |
| 6 | `rules.py` | ~30 quantity kinds with definitional semantic bounds (efficiency ∈ [0,1], `poisson_ratio` ∈ (−1, 0.5], absolute temperature > 0 K, `pH` ∈ [0,14], …). |
| 7 | `declared_conditions.py` | User-declared conditions (e.g. `velocity: 15.0`, `altitude: 120.0`) become testable assertions against the data. |
| 8 | `rules.py` | Structural checks: non-finite values, exact duplicates (with relative-equality tolerance). |

Layers 6 and 8 are *impossible by construction* — they express definitions, not
domain assumptions — so they are never suppressible.

**Arbitration.** Findings from all layers are combined by **weighted voting**,
not vote counting. Findings are clustered by root cause, and every finding can
carry a **counterfactual repair** — a statement like "×1000 closes the residual
from 99.9% to 0.00%", i.e. a unit-swap hypothesis that can be checked
mechanically.

**Output classes.** Instead of a single exclusion list, rows are classified
into three disjoint categories:

| Class | Meaning |
| ----- | ------- |
| `impossible` | Violates a definition or a hard physical bound — cannot be real as written (e.g. `conversion = 1.22`). |
| `inconsistent` | Contradicts the data's own discovered laws, an anchored physical constant, or a declared condition. |
| `unsuitable_for_training` | Dataset-level: structurally fine but unfit as training data (never covers the operating regime, has a near-duplicate-dominated structure, etc.). |

### Pre-flight mesh & setup validation

`core/mesh_validator.py` — validates a simulation **configuration before it
runs**: mesh quality metrics (aspect ratio, skewness, non-orthogonality, y+ vs
turbulence model, boundary-layer growth, volume ratio, watertightness, cell
count adequacy), boundary-condition consistency, solver settings, and physics
models. It produces a `ready / warning / not_ready` verdict, a list of
predictable downstream output-check failures, an estimated corruption risk
(0–1), and concrete recommendations. Exposed as `/v1/validate/setup` and the
CLI `preflight` command. Strictly no external calls — runs in well under 200ms.

### The AI reasoning layer

`core/ai_validator.py`, `core/ai_pipeline.py`, `core/ai_orchestrator.py` — an
**optional**, explicitly-enabled second pass. Its job is deliberately limited
to what deterministic code cannot do; it does not re-derive physics (an LLM
recomputing a gas law adds nothing and can only introduce error):

- **Phase C — cluster.** Collapse N findings into K root causes (10 findings
  across 3 columns are usually one pipeline bug).
- **Phase D — verify.** Every hypothesis the model proposes is confirmed or
  refuted by *deterministic code*. The model picks from a fixed library of
  failure modes and a fixed allowlist of probes; it cannot invent a file, a
  line, or a value that is not already in its input.
- **Phase E — narrate.** Confirmed causes are explained in engineer language.

Three invariants make this trustworthy: the model **selects, never invents**;
confidence is only assigned to **probe-confirmed** hypotheses; and every phase
**fails down, never out** — with no API key, no network, or a rate-limited
model, the pipeline still emits clustered root causes, just without the
narrative. The physics result is always complete and standalone.

A fallback chain (`MODEL_CHAIN`) tries several independent key/model pairs
before giving up, so a 429 or expired key on one combination degrades to a
slower answer rather than "AI layer unavailable."

To enable: set `SIMAPI_OPENROUTER_API_KEY` (and optionally `SIMAPI_AI_MODEL`)
and pass `run_ai=true`. Without a key the AI layer reports `disabled` and
physics validation is unaffected.

### Repair layer

`core/repair.py` — runs **after** validation, never instead of it. Every repair
is deterministic, reversible, and previewed before anything is applied
(`apply=false` by default). It fixes structural problems only:

- Duplicate rows
- Missing or duplicate IDs
- Out-of-order timestamps
- Wrapped angles (190° meant as −170°)
- Short NaN gaps (interpolation, up to a configurable gap length)

It will **not** rewrite a physically implausible value. A physics violation is a
data-quality problem for the user to investigate. Exposed as `/v1/repair`.

### Causal diagnosis

`core/causal_diagnosis.py` — the gap between *what* is wrong and *why* it is
wrong. Given a flagged row, it reasons in three layers:

1. **Signal pattern matching** — match the corruption fingerprint against a
   library of known failure modes (unit conversions, copy-paste blocks, sensor
   drift, solver divergence).
2. **Contextual analysis** — use neighboring rows and the report's provenance to
   localize *where* the error was introduced (solver, post-processing script,
   unit-conversion step).
3. **Recommendation** — name the specific step to inspect (e.g. "check the
   `pressure_extract.py` normalization step").

### Compliance reports

`core/compliance.py` — produces a signed, timestamped, tamper-evident report
suitable for attaching to a certification package:

- SHA-256 hash of the raw dataset (proves *which* data was validated)
- SHA-256 hash of the report itself (proves it was not modified post-hoc)
- The full validation result, causal diagnosis per corruption type, and chain
  of custody (who ran it, when, on what system)
- A regulatory mapping. Standards addressed: **ISO 26262** (automotive
  functional safety, Part 6 data quality), **DO-178C** (aerospace software),
  **FDA 21 CFR Part 11** (electronic records and signatures), and **NHTSA**
  AV testing guidelines.

### Adversarial red team

`core/adversarial.py` — generates the **hardest-to-detect corruptions** for a
given dataset and domain and shows exactly which ones the engine catches and
which slip through. The attack taxonomy is ordered by detection difficulty:

1. **Easy** — physical-bounds violations, unit errors (1000× off).
2. **Medium** — copy-paste blocks, isolated solver spikes.
3. **Hard** — distribution-preserving corruptions (values in-distribution but
   wrong).
4. **Hard** — correlated multi-column perturbations (preserve all ratios while
   biasing the target).
5. **Very hard** — temporal camouflage (a corruption that ramps in and out over
   N rows).

The point is honest positioning (the blind spots are stated explicitly, not
hidden behind recall numbers on easy corruptions) and actionable gap analysis
(each blind spot directly names the pipeline control that needs strengthening).

### Dataset profiling

`core/dataset_profile.py` — answers the question the rule engine cannot: *is
row order meaningful, and if so, what does it mean?* A simulation dataset is
usually a **designed parameter sweep** (velocity stepped 12→28 m/s, one row per
step), not a time series. In sweep data, adjacent rows are *supposed* to be
nearly identical and the swept column *supposed* to be perfectly monotonic.
Profiling the dataset first prevents the engine from reporting those design
properties as near-duplicates, drift, or discontinuous jumps — which on a real
sweep can account for 90%+ of findings.

### Run history

`core/run_history.py` — temporal memory. Validation in isolation misses the
most common real failure: a dataset that looks clean on its own but is deeply
wrong relative to the previous 200 runs of the same configuration. A
`RunHistoryTracker` keyed to `(simulation_config_hash, domain)` maintains
compact statistical summaries of historical runs — fingerprints, column
distributions, ratio-invariant baselines — and scores new runs against that
envelope, flagging cross-run drift even when nothing is wrong in isolation.

### Ingestion

`core/ingestion.py` — accepts **CSV, JSON, YAML, TOML, TXT/Markdown, VTK,
NumPy, and OpenFOAM** files. An aggressive column-alias map normalizes names
across tool conventions — ANSYS, OpenFOAM, STAR-CCM+, Fluent, COMSOL, SU2,
Abaqus, MATLAB — so physics checks fire regardless of naming convention. The
rename mapping is returned in the report (`columns_renamed`) so you can see
exactly what was normalized. Duplicate column names are de-duplicated
defensively so numeric operations cannot silently misbehave.

---

## Verdict model

Every validation returns a single top-level status plus per-row classification:

```
status           passed | warning | failed
confidence       high | medium | low
training_ready   bool  — false if any row is impossible (engine 1) or any row
                        is classified impossible (engine 2)
```

The report also includes: `trials_submitted / trials_valid / trials_excluded`,
an `exclusion_rate`, per-column `statistics` (mean, std, median, p5/p95,
min/max, skewness, kurtosis, CV), `exclusions` with reasons, and `provenance`
(which ingestion aliases were applied, which checks ran). Non-finite statistics
(negative variance, skewness of a constant column) serialize as `null` rather
than crashing.

## Quickstart

```bash
# 1. Install
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure (optional in development)
cp .env.example .env

# 3. Run the API + dashboard
python launch.py            # API on :8000, Swagger UI at /docs

# 4. Try it
curl -X POST http://localhost:8000/v1/demo | jq .status
```

With Docker:

```bash
docker compose up --build   # one command, production image
```

## Using the SDK

Python (`sdk/simapi.py`):

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

Node (`sdk-node/`):

```js
import { SimAPI } from "simapi";

const client = new SimAPI(process.env.SIMAPI_API_KEY);
const result = await client.validate(rows, { simulationType: "aerodynamics" });
console.log(result.status);
```

Set `SIMAPI_BASE_URL` and `SIMAPI_API_KEY` to point either SDK at a remote
deployment. The Python SDK also exposes `result.to_dataframe()` and
`result.download_csv("clean.csv")` for the excluded-clean dataset.

## Using the CLI

`python-pkg/simapi/cli.py` — a self-contained local CLI. The full engine runs
locally; data does not leave the machine unless you use `--upload`.

```bash
simapi validate output.csv                    # full forensic report
simapi validate output.csv --report report.md # Markdown report
simapi validate output.csv --sarif sarif.json # GitHub code-scanning SARIF
simapi watch output.csv                       # re-validate on change
simapi compare before.csv after.csv           # before/after a fix
simapi ci --domain aerodynamics output.csv    # CI mode, exit code by verdict
simapi preflight simapi.json                  # mesh/solver check before running
simapi report --history                       # cross-run trend analysis
simapi init                                   # create simapi.json for this project
```

CI exit codes:

```
0   Clean (or only review flags)
1   Critical corruptions auto-removed
2   Validation error (file not found, parse error)
3   Physical-law violations detected
```

## API reference

Interactive docs are served at `/docs` (Swagger UI) and `/redoc`; the raw
schema is at `/openapi.json`.

| Method | Path | Description |
| ------ | ---- | ----------- |
| `GET`  | `/v1/health` | Liveness + service facts (unauthenticated) |
| `GET`  | `/v1/metrics` | Prometheus metrics (plain text) |
| `POST` | `/v1/validate` | Validate a JSON batch of trials (both engines, optionally with AI) |
| `POST` | `/v1/validate/upload` | Validate an uploaded CSV/JSON/VTK/NumPy/OpenFOAM file |
| `POST` | `/v1/validate/physics-only` | Both engines, AI layer disabled (`run_ai=false`) |
| `POST` | `/v1/validate/dimensional` | Dimensional engine only — returns the raw per-layer report (discovered laws, units resolution, condition assertions, training-suitability) instead of the summarized shape |
| `POST` | `/v1/validate/setup` | Pre-flight mesh + solver + physics setup validation, with predicted output-corruption risk |
| `POST` | `/v1/repair` | Structural repair — previews proposals by default; `apply=true` returns the repaired dataset |
| `POST` | `/v1/demo` | Validate seeded, physically coupled synthetic aerodynamics data |
| `GET`  | `/v1/job/{id}` | Fetch a job's physics result |
| `GET`  | `/v1/job/{id}/ai` | Poll for the async AI result (includes AI-added exclusions and status changes) |
| `GET`  | `/v1/jobs?limit=&offset=` | List recent jobs, newest first (offset pagination) |

**Consistent error contract.** Every error returns the same envelope with a
stable `code`, a message, and a `request_id` that correlates to the server
logs:

```json
{ "error": { "code": "rate_limited", "message": "Rate limit exceeded. Slow down and retry.", "request_id": "3f9c…" } }
```

## Architecture

```
                ┌──────────────────────────────────────────────┐
   client ───▶  │  FastAPI (api/server.py)                     │
   SDK / curl   │   middleware: request-id · logging · metrics │
                │   deps:       auth · rate limit               │
                │   handlers:   consistent error envelope       │
                └───────┬───────────────────────┬──────────────┘
                        │                        │
        ┌───────────────▼──────────┐   ┌─────────▼──────────────┐
        │ core/ingestion.py        │   │ core/physics_validator │
        │ format detect + aliases  │   │ rule engine, 21 domains│
        └───────────────┬──────────┘   └─────────┬──────────────┘
                        │                        │
                        │      ┌─────────────────▼────────────────┐
                        └──────▶│ core/dimensional/engine.py      │
                               │  units → Pi groups → laws →      │
                               │  anchors → response surface →    │
                               │  semantic bounds → conditions    │
                               └────────────────┬─────────────────┘
                                                │  synchronous verdict
                                      ┌─────────▼──────────────┐
                                      │ core/ai_validator.py   │
                                      │ async LLM second pass  │
                                      │ (polled via /job/…/ai) │
                                      └────────────────────────┘
```

Supporting engines, all deterministic and pure-NumPy:

- **`api/config.py`** — immutable, environment-sourced settings (12-factor).
- **`api/security.py`** — API-key auth (constant-time compare) + token-bucket
  rate limiter.
- **`api/observability.py`** — JSON logging, request-id context, metrics
  registry.
- **`api/errors.py`** — typed errors → one JSON envelope with stable codes.
- **`core/mesh_validator.py`** — pre-run mesh/setup checks + corruption-risk
  prediction.
- **`core/repair.py`** — deterministic structural repair with previews.
- **`core/causal_diagnosis.py`** — root-cause attribution for findings.
- **`core/compliance.py`** — tamper-evident regulatory reports.
- **`core/adversarial.py`** — corruption-generation gap analysis.
- **`core/dataset_profile.py`** — sweep-vs-timeseries classification and
  check-masking.
- **`core/run_history.py`** — cross-run drift detection.
- **`core/physics_manifold.py`**, **`core/apie.py`**,
  **`core/universal_validator.py`** — manifold/adaptive engines used by the
  APIE pipeline and CLI.

## Configuration

All configuration is environment-driven; see [`.env.example`](.env.example) for
the full list. Highlights:

| Variable | Default | Purpose |
| -------- | ------- | ------- |
| `SIMAPI_ENV` | `development` | `development` \| `staging` \| `production` |
| `SIMAPI_HOST` / `SIMAPI_PORT` | `0.0.0.0` / `8000` | Bind address |
| `SIMAPI_REQUIRE_AUTH` | `false` | Enforce API-key auth |
| `SIMAPI_API_KEYS` | — | Comma-separated accepted keys |
| `SIMAPI_RATE_LIMIT_RPM` | `120` | Sustained requests/minute per caller |
| `SIMAPI_RATE_LIMIT_BURST` | `20` | Token-bucket burst allowance |
| `SIMAPI_CORS_ORIGINS` | `*` | Allowed CORS origins |
| `SIMAPI_MAX_ROWS` | `1000000` | Max rows per payload (returns `413`) |
| `SIMAPI_MAX_UPLOAD_BYTES` | `104857600` | Max upload bytes (returns `413`) |
| `SIMAPI_JOB_TTL_SECONDS` / `SIMAPI_MAX_JOBS` | `3600` / `10000` | Job-store retention |
| `SIMAPI_OPENROUTER_API_KEY` | — | Enables the AI layer when set |
| `SIMAPI_AI_MODEL` | `anthropic/claude-3.5-haiku` | First model in the fallback chain |
| `SIMAPI_LOG_JSON` | `true` | Structured JSON logs |

## Deployment

The image is a multi-stage, non-root, health-checked container and runs
anywhere containers run:

```bash
docker build -t simapi:latest .
docker run -p 8000:8000 --env-file .env simapi:latest
```

- **Render / Railway / Fly.io** — deploy the Dockerfile directly; set env vars
  in the platform dashboard.
- **AWS / Azure / GCP** — push to a registry and run on ECS/Fargate, Cloud Run,
  or Container Apps; scrape `/v1/metrics`, health-check `/v1/health`.
- **Kubernetes** — use `/v1/health` for liveness/readiness probes and the
  Prometheus endpoint for HPA signals.

The Python CLI (`python-pkg`) can be installed and run locally without a
deployment: `pip install ./python-pkg && simapi validate out.csv`.

## Repository layout

| Path | What |
| ---- | ---- |
| `api/` | FastAPI service: config, security, observability, errors, server |
| `core/` | Validation engines: physics rules, dimensional analysis, mesh, repair, causal diagnosis, compliance, adversarial, profiling, run history |
| `sdk/` | Lightweight Python SDK (`from sdk.simapi import SimAPI`) |
| `python-pkg/` | Installable Python package + local CLI (`simapi validate`, `simapi ci`, …) |
| `sdk-node/` | Node.js SDK + `simapi` CLI wrapper |
| `tests/` | Pytest suite (API contract, engine unit tests, ingestion formats, repair, security) |
| `web/` | Marketing site — Next.js 15 + Tailwind (interactive demo & API playground) |
| `docs-site/` | Mintlify developer documentation |
| `dashboard/` | Static demo dashboard |
| `docs/` | OpenAPI schema, Postman collection, examples |
| `.github/workflows/` | CI, web deploy, npm publish |
| `integrations/` | Docker, pre-commit hooks, GitHub Actions action |

## Development

```bash
make dev        # deps + pre-commit hooks
make test       # run the suite
make cov        # coverage report
make lint       # ruff
make typecheck  # mypy

# Marketing site
cd web && npm install && npm run dev        # http://localhost:3000

# Docs (Mintlify)
cd docs-site && mint dev                     # http://localhost:3000
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow and how to add a
new simulation domain.

## Roadmap

Async job queue and durable storage · organizations / projects / RBAC · usage
dashboard and billing · webhooks · baseline & regression detection · custom
validation-rule plugins. See [CHANGELOG.md](CHANGELOG.md) for shipped work.

## License

MIT — see [LICENSE](LICENSE).
