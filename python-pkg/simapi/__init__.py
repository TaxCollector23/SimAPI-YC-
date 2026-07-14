"""
SimAPI Python SDK.

A dependency-free client (stdlib ``urllib``) for the SimAPI validation service.

    from simapi import SimAPI
    client = SimAPI(api_key="sk_live_...")
    result = client.validate("simulation.json", simulation_type="aerodynamics")
    print(result["status"])
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

__version__ = "1.0.0"

DEFAULT_BASE = os.environ.get("SIMAPI_BASE_URL", "https://sim-api.vercel.app/api")


class SimAPIError(RuntimeError):
    def __init__(self, message: str, code: str = "error", status: int = 0, request_id: str | None = None):
        super().__init__(message)
        self.code = code
        self.status = status
        self.request_id = request_id


def _request(url: str, method: str = "GET", body: dict | None = None, api_key: str | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode())
            err = payload.get("error", {})
            raise SimAPIError(err.get("message", str(e)), err.get("code", "http_error"), e.code, err.get("request_id")) from None
        except (json.JSONDecodeError, AttributeError):
            raise SimAPIError(str(e), "http_error", e.code) from None
    except urllib.error.URLError as e:
        raise SimAPIError(f"Request failed: {e.reason}", "network_error") from None


class SimAPI:
    """Object-oriented client with a bound API key and base URL."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or os.environ.get("SIMAPI_API_KEY")
        self.base_url = (base_url or DEFAULT_BASE).rstrip("/")

    def validate(self, data, simulation_type: str = "aerodynamics", conditions: dict | None = None) -> dict:
        """Validate a JSON file path or a list of trial records."""
        if isinstance(data, str):
            with open(data, encoding="utf-8") as f:
                parsed = json.load(f)
            rows = parsed if isinstance(parsed, list) else parsed.get("data") or parsed.get("trials") or []
            if not conditions and isinstance(parsed, dict):
                conditions = parsed.get("conditions")
        else:
            rows = data
        body = {"data": rows, "simulation_type": simulation_type, "conditions": conditions or {}}
        return _request(f"{self.base_url}/v1/validate", "POST", body, self.api_key)

    def health(self) -> dict:
        return _request(f"{self.base_url}/v1/health")


def validate(data, simulation_type: str = "aerodynamics", conditions: dict | None = None, api_key: str | None = None) -> dict:
    """Module-level convenience wrapper."""
    return SimAPI(api_key=api_key).validate(data, simulation_type, conditions)
