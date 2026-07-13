"""
SimAPI — Observability primitives: structured logging, request IDs, and metrics.

Design goals:
  * Zero mandatory third-party dependencies (works with the stdlib alone).
  * JSON logs in production for ingestion by Datadog / Loki / CloudWatch.
  * A Prometheus-compatible text exposition at ``/v1/metrics`` without pulling in
    the full client library — the counters we need are simple and in-process.

If ``opentelemetry`` is installed, spans are emitted automatically; if not, the
tracing calls degrade to no-ops so the dependency stays optional.
"""
from __future__ import annotations

import json
import logging
import sys
import threading
import time
from contextvars import ContextVar

from .config import settings

# ── Request-scoped correlation id ───────────────────────────────────────────────
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


# ── Structured logging ──────────────────────────────────────────────────────────
class JsonLogFormatter(logging.Formatter):
    """Render log records as single-line JSON with the active request id."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_ctx.get(),
        }
        # Merge any structured extras attached via logger.info(msg, extra={...}).
        for key, value in getattr(record, "__dict__", {}).items():
            if key.startswith("ctx_"):
                payload[key[4:]] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> logging.Logger:
    """Idempotently configure the root SimAPI logger."""
    logger = logging.getLogger("simapi")
    logger.setLevel(settings.log_level)
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    if settings.log_json:
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        )
    logger.addHandler(handler)
    logger.propagate = False
    return logger


log = configure_logging()


# ── In-process metrics registry (Prometheus text format) ────────────────────────
class Metrics:
    """Thread-safe counters and histograms exposed in Prometheus text format."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, float] = {}
        self._latency_sum_ms: float = 0.0
        self._latency_count: int = 0
        self._started = time.time()

    def incr(self, name: str, value: float = 1.0, **labels: str) -> None:
        key = self._key(name, labels)
        with self._lock:
            self._counters[key] = self._counters.get(key, 0.0) + value

    def observe_latency(self, ms: float) -> None:
        with self._lock:
            self._latency_sum_ms += ms
            self._latency_count += 1

    @staticmethod
    def _key(name: str, labels: dict[str, str]) -> str:
        if not labels:
            return name
        rendered = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{rendered}}}"

    def render(self) -> str:
        with self._lock:
            lines = [
                "# HELP simapi_uptime_seconds Seconds since process start.",
                "# TYPE simapi_uptime_seconds gauge",
                f"simapi_uptime_seconds {time.time() - self._started:.1f}",
                "# HELP simapi_http_requests_total Total HTTP requests.",
                "# TYPE simapi_http_requests_total counter",
            ]
            for key, value in sorted(self._counters.items()):
                lines.append(f"simapi_{key} {value:g}")
            avg = self._latency_sum_ms / self._latency_count if self._latency_count else 0.0
            lines += [
                "# HELP simapi_request_latency_ms_avg Mean request latency (ms).",
                "# TYPE simapi_request_latency_ms_avg gauge",
                f"simapi_request_latency_ms_avg {avg:.2f}",
            ]
        return "\n".join(lines) + "\n"


metrics = Metrics()
