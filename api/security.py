"""
SimAPI — Authentication and rate limiting.

* API-key auth via the ``X-API-Key`` header (or ``Authorization: Bearer <key>``).
  Keys are compared in constant time to avoid timing side channels.
* A per-client token-bucket rate limiter that smooths bursts while enforcing a
  sustained requests-per-minute ceiling. The limiter is in-process; for a
  multi-replica deployment swap the store for a Redis-backed implementation
  behind the same ``RateLimiter`` interface.
"""
from __future__ import annotations

import hmac
import threading
import time

from fastapi import Request

from .config import settings
from .errors import RateLimitedError, UnauthorizedError


# ── Authentication ──────────────────────────────────────────────────────────────
def extract_api_key(request: Request) -> str | None:
    """Pull the API key from ``X-API-Key`` or a bearer token."""
    key = request.headers.get("x-api-key")
    if key:
        return key.strip()
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def _key_is_valid(candidate: str) -> bool:
    """Constant-time comparison against the configured key set."""
    for known in settings.api_keys:
        if hmac.compare_digest(candidate, known):
            return True
    return False


def authenticate(request: Request) -> str:
    """
    FastAPI dependency. Returns the caller's identity (the API key, or
    ``"anonymous"`` when auth is disabled). Raises ``UnauthorizedError`` on a
    missing or invalid key when auth is required.
    """
    if not settings.require_auth and not settings.api_keys:
        return "anonymous"

    key = extract_api_key(request)
    if not key or not _key_is_valid(key):
        raise UnauthorizedError(
            "Missing or invalid API key. Provide it via the X-API-Key header.",
        )
    # Identify the caller by a short, non-reversible fingerprint for logs/metrics.
    return f"key_{key[:6]}"


# ── Rate limiting (token bucket) ────────────────────────────────────────────────
class _Bucket:
    __slots__ = ("tokens", "updated")

    def __init__(self, tokens: float, updated: float) -> None:
        self.tokens = tokens
        self.updated = updated


class RateLimiter:
    """
    Token-bucket limiter keyed by caller identity.

    ``rpm`` sets the sustained refill rate; ``burst`` is the bucket capacity,
    allowing short spikes above the average rate.
    """

    def __init__(self, rpm: int, burst: int) -> None:
        self.rate_per_sec = rpm / 60.0
        self.capacity = float(burst)
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def check(self, identity: str) -> tuple[bool, float]:
        """
        Consume one token for ``identity``.

        Returns ``(allowed, retry_after_seconds)``. ``retry_after_seconds`` is 0
        when the request is allowed.
        """
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.get(identity)
            if bucket is None:
                bucket = _Bucket(self.capacity, now)
                self._buckets[identity] = bucket
            # Refill proportional to elapsed time, capped at capacity.
            elapsed = now - bucket.updated
            bucket.tokens = min(self.capacity, bucket.tokens + elapsed * self.rate_per_sec)
            bucket.updated = now
            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                return True, 0.0
            deficit = 1.0 - bucket.tokens
            retry_after = deficit / self.rate_per_sec if self.rate_per_sec > 0 else 60.0
            return False, retry_after


_limiter = RateLimiter(settings.rate_limit_rpm, settings.rate_limit_burst)


def enforce_rate_limit(identity: str) -> None:
    """Raise ``RateLimitedError`` if ``identity`` has exhausted its budget."""
    if not settings.rate_limit_enabled:
        return
    allowed, retry_after = _limiter.check(identity)
    if not allowed:
        raise RateLimitedError(
            "Rate limit exceeded. Slow down and retry.",
            details={"retry_after_seconds": round(retry_after, 2)},
        )
