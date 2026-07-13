# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and the project adheres to
semantic versioning.

## [3.1.0] — 2026-07-12

Production-hardening release. **No breaking changes to the response schema.**

### Security
- **Removed a hardcoded OpenRouter API key** from `core/ai_validator.py`; all
  secrets now come from the environment. Rotate the leaked key immediately.
- Added API-key authentication (`X-API-Key` / bearer) with constant-time
  comparison, gated by `SIMAPI_REQUIRE_AUTH`.
- Added a per-caller token-bucket rate limiter.
- Added `gitleaks` secret scanning to CI and pre-commit, plus a
  `detect-private-key` hook and a `SECURITY.md` policy.

### Added
- Centralized 12-factor configuration (`api/config.py`).
- Structured JSON logging with request-id correlation (`api/observability.py`).
- Consistent error contract with stable machine-readable codes (`api/errors.py`).
- `GET /v1/metrics` Prometheus endpoint; `GET /v1/health` now reports
  environment and AI availability.
- Offset pagination on `GET /v1/jobs`; job-store TTL and size caps.
- Payload size limits (rows and upload bytes) returning `413`.
- Dockerfile (multi-stage, non-root, healthcheck), `docker-compose.yml`,
  `Makefile`, `.env.example`, GitHub Actions CI, pre-commit, `pyproject.toml`.
- Test suite (`tests/`) covering the API contract, auth, and rate limiting.

### Fixed
- SDK `ValidationResult` read a non-existent `physics_checks` field and treated a
  warning **count** as a list — it now reads the documented schema and degrades
  gracefully.
- Non-finite statistics (e.g. skewness of a constant column) no longer crash JSON
  serialization; they serialize as `null`.
- Removed dead/duplicate code and a `NameError`-prone module/local shadowing in
  the physics engine; silenced benign numerical warnings.
- The AI layer degrades cleanly to a `disabled` status when no key is configured.

## [3.0.0] — earlier

- Initial dual-layer validator: 280+ physics checks across 21 domains plus an
  async LLM reasoning layer, FastAPI server, Python SDK, and demo dashboard.
