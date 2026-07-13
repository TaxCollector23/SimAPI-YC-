# Contributing to SimAPI

Thanks for your interest in improving SimAPI. This guide gets you productive fast.

## Development setup

```bash
python -m venv .venv && source .venv/bin/activate
make dev            # installs deps + pre-commit hooks
cp .env.example .env
make test           # should be green
make run            # starts API + dashboard
```

## Project layout

```
api/     FastAPI server, config, security, observability, error contract
core/    Validation engine: ingestion, physics rules, AI reasoning layer
sdk/     Python client SDK
tests/   Pytest suite (unit + API contract)
dashboard/  Static demo dashboard
```

## Ground rules

- **No secrets in code.** Configuration comes from the environment (`api/config.py`).
- **Keep the public response schema backward compatible.** If a break is truly
  necessary, document the rationale in the PR and `CHANGELOG.md`.
- **Every new physics check** goes in a layer method on `PhysicsValidator` and
  should emit a `PhysicsCheck` via the `_c`/`_w` helpers with a category.
- **Add tests** for new endpoints (contract test in `tests/test_api.py`) and new
  logic (unit test).

## Before opening a PR

```bash
make format lint typecheck test
```

CI must be green. PRs are squash-merged; write a clear, imperative title.

## Adding a new simulation domain

1. Add the enum value to `SimulationType`.
2. Add bounds to `BOUNDS` and a `_domain_<name>` layer method.
3. Register the method in the `layers` list in `PhysicsValidator.validate`.
4. Add column aliases to `COLUMN_ALIASES` in `core/ingestion.py`.
5. Add a contract test.
