"""Unit tests for auth and the token-bucket rate limiter."""
import dataclasses

import pytest

from api.errors import RateLimitedError, UnauthorizedError
from api.security import RateLimiter, authenticate, enforce_rate_limit


class _FakeClient:
    def __init__(self, host: str = "1.2.3.4"):
        self.host = host


class _FakeRequest:
    def __init__(self, headers=None, client_host: str = "1.2.3.4"):
        self.headers = headers or {}
        self.client = _FakeClient(client_host)


def _with_settings(monkeypatch, module, **overrides):
    """Swap a module's frozen ``settings`` for a copy with overrides applied."""
    monkeypatch.setattr(module, "settings", dataclasses.replace(module.settings, **overrides))


def test_rate_limiter_allows_within_burst():
    limiter = RateLimiter(rpm=60, burst=3)
    assert all(limiter.check("a")[0] for _ in range(3))


def test_rate_limiter_blocks_when_exhausted():
    limiter = RateLimiter(rpm=60, burst=2)
    limiter.check("a")
    limiter.check("a")
    allowed, retry_after = limiter.check("a")
    assert allowed is False
    assert retry_after > 0


def test_rate_limiter_is_isolated_per_identity():
    limiter = RateLimiter(rpm=60, burst=1)
    assert limiter.check("a")[0] is True
    assert limiter.check("b")[0] is True  # different key, own bucket


def test_auth_disabled_keys_identity_by_client_ip(monkeypatch):
    """When auth is disabled, anonymous callers must get their OWN rate-limit
    bucket keyed by client IP. Previously every caller collapsed into the
    literal "anonymous", so any single client could exhaust the shared
    budget and 429 every other caller on the same worker."""
    from api import security

    _with_settings(monkeypatch, security, require_auth=False, api_keys=[])
    a = authenticate(_FakeRequest(client_host="10.0.0.1"))
    b = authenticate(_FakeRequest(client_host="10.0.0.2"))
    assert a.startswith("anon_") and b.startswith("anon_")
    assert a != b, "two IPs must not share a rate-limit bucket"


def test_auth_disabled_honours_x_forwarded_for(monkeypatch):
    """Instances behind a trusted proxy should still isolate per-client via
    XFF's first hop instead of collapsing everyone into the proxy's IP."""
    from api import security

    _with_settings(monkeypatch, security, require_auth=False, api_keys=[])
    ident = authenticate(_FakeRequest(
        headers={"x-forwarded-for": "203.0.113.7, 10.0.0.99"},
        client_host="10.0.0.99",
    ))
    assert ident == "anon_203.0.113.7"


def test_auth_rejects_missing_key(monkeypatch):
    from api import security

    _with_settings(monkeypatch, security, require_auth=True, api_keys=["secret-key"])
    with pytest.raises(UnauthorizedError):
        authenticate(_FakeRequest())


def test_auth_accepts_valid_key(monkeypatch):
    from api import security

    _with_settings(monkeypatch, security, require_auth=True, api_keys=["secret-key"])
    identity = authenticate(_FakeRequest({"x-api-key": "secret-key"}))
    assert identity.startswith("key_")


def test_enforce_rate_limit_can_raise(monkeypatch):
    from api import security

    _with_settings(monkeypatch, security, rate_limit_enabled=True)
    monkeypatch.setattr(security, "_limiter", RateLimiter(rpm=60, burst=1), raising=False)
    enforce_rate_limit("tester")
    with pytest.raises(RateLimitedError):
        enforce_rate_limit("tester")
