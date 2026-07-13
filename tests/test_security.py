"""Unit tests for auth and the token-bucket rate limiter."""
import dataclasses

import pytest

from api.errors import RateLimitedError, UnauthorizedError
from api.security import RateLimiter, authenticate, enforce_rate_limit


class _FakeRequest:
    def __init__(self, headers=None):
        self.headers = headers or {}


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


def test_auth_disabled_returns_anonymous(monkeypatch):
    from api import security

    _with_settings(monkeypatch, security, require_auth=False, api_keys=[])
    assert authenticate(_FakeRequest()) == "anonymous"


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
