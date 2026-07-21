<div align="center">

# SimAPI

### The CI/CD layer for engineering simulations.

Automatically validate CFD, FEA, multiphysics, and robotics simulation output
against physical laws — before it reaches a design decision or an ML training set.

[![CI](https://img.shields.io/badge/CI-passing-brightgreen)](.github/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-black)](LICENSE)
[![Checks](https://img.shields.io/badge/physics%20checks-280%2B-orange)](core/physics_validator.py)
[![Domains](https://img.shields.io/badge/domains-21-purple)](core/physics_validator.py)

</div>

---

## Why SimAPI

Engineering organizations run thousands of simulations. Today a human engineer
eyeballs the output before anyone trusts it. That manual gate is slow, subjective,
and doesn't scale — and bad simulation data silently poisons downstream design
decisions and ML models.

**SimAPI is the automated validation gate.** Point it at simulation output and it
returns a trustworthy verdict in milliseconds:

- **Physics engine** — 280+ deterministic checks across 21 domains: plausibility
  bounds, conservation laws, dimensional consistency, cross-variable relationships,
  statistical distribution, outlier detection, and domain-specific rules.
- **AI reasoning layer** *(optional)* — a second-pass LLM review that catches what
  rules miss: magnitude realism, distribution-shape red flags, dataset-provenance
  artifacts, and ML-readiness concerns.

Think **GitHub Actions for simulations**, **Stripe for simulation validation**,
**Cloudflare for engineering trust**.

## Quickstart

```bash
# 1. Install
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure (optional in dev)
cp .env.example .env

# 3. Run the API + dashboard
python launch.py            # API on :8000, docs at /docs

# 4. Try it
curl -X POST http://localhost:8000/v1/demo | jq .status
```

### With Docker

```bash
docker compose up --build   # one command, production image
```

## Using the SDK

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

Set `SIMAPI_BASE_URL` and `SIMAPI_API_KEY` to point the SDK at a remote deployment.

## API

Interactive docs are served at `/docs` (Swagger UI) and `/redoc`; the raw schema
is at `/openapi.json`.

| Method | Path | Description |
| ------ | ---- | ----------- |
| `GET`  | `/v1/health` | Liveness + service facts (unauthenticated) |
| `GET`  | `/v1/metrics` | Prometheus metrics |
| `POST` | `/v1/validate` | Validate a JSON batch of trials |
| `POST` | `/v1/validate/upload` | Validate an uploaded CSV/JSON/VTK/NumPy/OpenFOAM file |
| `POST` | `/v1/validate/physics-only` | Physics checks only (skip AI) |
| `POST` | `/v1/demo` | Validate seeded synthetic data |
| `GET`  | `/v1/job/{id}` | Fetch a job's physics result |
| `GET`  | `/v1/job/{id}/ai` | Poll for the async AI result |
| `GET`  | `/v1/jobs?limit=&offset=` | List recent jobs (paginated) |

**Consistent error contract.** Every error returns the same envelope with a stable
`code`, a message, and a `request_id` that correlates to the server logs:

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
        │ format detect + 400      │   │ 53 layers, 280+ checks │
        │ column-alias normalize   │   │ 21 simulation domains  │
        └───────────────┬──────────┘   └─────────┬──────────────┘
                        └── DataFrame ───────────▶│  synchronous verdict
                                                  │
                                        ┌─────────▼──────────────┐
                                        │ core/ai_validator.py   │
                                        │ async LLM second pass  │
                                        │ (polled via /job/…/ai) │
                                        └────────────────────────┘
```

- **`api/config.py`** — immutable, env-sourced settings (12-factor).
- **`api/security.py`** — API-key auth (constant-time) + token-bucket rate limiter.
- **`api/observability.py`** — JSON logging, request-id context, metrics registry.
- **`api/errors.py`** — typed errors → one JSON envelope with stable codes.

## Configuration

All configuration is environment-driven; see [`.env.example`](.env.example) for the
full list. Highlights:

| Variable | Default | Purpose |
| -------- | ------- | ------- |
| `SIMAPI_REQUIRE_AUTH` | `false` | Enforce API-key auth |
| `SIMAPI_API_KEYS` | — | Comma-separated accepted keys |
| `SIMAPI_RATE_LIMIT_RPM` | `120` | Sustained requests/minute per caller |
| `SIMAPI_CORS_ORIGINS` | `*` | Allowed CORS origins |
| `SIMAPI_OPENROUTER_API_KEY` | — | Enables the AI layer when set |

## Deployment

The image is a standard, non-root, health-checked container and runs anywhere
containers run:

```bash
docker build -t simapi:latest .
docker run -p 8000:8000 --env-file .env simapi:latest
```

- **Render / Railway / Fly.io** — deploy the Dockerfile directly; set env vars in
  the dashboard.
- **AWS / Azure / GCP** — push to a registry and run on ECS/Fargate, Cloud Run, or
  Container Apps; scrape `/v1/metrics`, health-check `/v1/health`.
- **Kubernetes** — use `/v1/health` for liveness/readiness probes and the
  Prometheus endpoint for HPA signals.

## Repository layout

| Path | What |
| ---- | ---- |
| `api/` · `core/` · `sdk/` | Production FastAPI service, validation engine, Python SDK |
| `tests/` | Pytest suite (API contract + unit) |
| `web/` | Marketing site — Next.js 15 + Tailwind + Framer Motion (interactive demo & API playground) |
| `docs-site/` | Mintlify developer documentation |
| `dashboard/` | Static demo dashboard |

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

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow and how to add a new
simulation domain.

## Roadmap

Async job queue and durable storage · organizations / projects / RBAC · usage
dashboard and billing · webhooks · baseline & regression detection · custom
validation-rule plugins. See [CHANGELOG.md](CHANGELOG.md) for shipped work.

## License

MIT — see [LICENSE](LICENSE).
