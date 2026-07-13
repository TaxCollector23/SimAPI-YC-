"""
SimAPI — Centralized runtime configuration.

All configuration is sourced from environment variables so the same image can be
promoted across dev, staging, and production without code changes (12-factor).
Import the module-level ``settings`` singleton; never read ``os.environ`` directly
from request-handling code.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


def _load_dotenv() -> None:
    """Populate ``os.environ`` from a local ``.env`` file if present.

    Dependency-free and non-destructive: variables already set in the real
    environment always win, so container/orchestrator config is never overridden.
    """
    path = Path(__file__).resolve().parent.parent / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_list(name: str, default: list[str]) -> list[str]:
    raw = os.environ.get(name)
    if not raw:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    """Immutable, validated view of the process environment."""

    # ── Service ────────────────────────────────────────────────────────────────
    environment: str = os.environ.get("SIMAPI_ENV", "development")
    host: str = os.environ.get("SIMAPI_HOST", "0.0.0.0")
    port: int = _env_int("SIMAPI_PORT", 8000)
    log_level: str = os.environ.get("SIMAPI_LOG_LEVEL", "INFO").upper()
    log_json: bool = _env_bool("SIMAPI_LOG_JSON", True)

    # ── Auth ───────────────────────────────────────────────────────────────────
    # Comma-separated list of accepted API keys. When empty, auth is disabled
    # (development convenience). Production deployments MUST set this.
    api_keys: list[str] = field(default_factory=lambda: _env_list("SIMAPI_API_KEYS", []))
    require_auth: bool = _env_bool("SIMAPI_REQUIRE_AUTH", False)

    # ── Rate limiting (token bucket, per API key / client IP) ────────────────────
    rate_limit_enabled: bool = _env_bool("SIMAPI_RATE_LIMIT_ENABLED", True)
    rate_limit_rpm: int = _env_int("SIMAPI_RATE_LIMIT_RPM", 120)
    rate_limit_burst: int = _env_int("SIMAPI_RATE_LIMIT_BURST", 20)

    # ── CORS ─────────────────────────────────────────────────────────────────────
    cors_origins: list[str] = field(default_factory=lambda: _env_list("SIMAPI_CORS_ORIGINS", ["*"]))

    # ── Job store retention ──────────────────────────────────────────────────────
    job_ttl_seconds: int = _env_int("SIMAPI_JOB_TTL_SECONDS", 3600)
    max_jobs: int = _env_int("SIMAPI_MAX_JOBS", 10_000)

    # ── Payload limits ───────────────────────────────────────────────────────────
    max_rows: int = _env_int("SIMAPI_MAX_ROWS", 1_000_000)
    max_upload_bytes: int = _env_int("SIMAPI_MAX_UPLOAD_BYTES", 100 * 1024 * 1024)

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in ("prod", "production")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton (cached)."""
    return Settings()


settings = get_settings()
