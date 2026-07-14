"""
SimAPI Python SDK
Install: pip install simapi  (coming soon)
For now: from sdk.simapi import SimAPI

Usage:
    import simapi

    result = simapi.validate(
        data="my_cfd_output.csv",
        simulation_type="aerodynamics",
        conditions={"velocity": 15.0, "altitude": 120.0},
    )

    print(result.confidence)          # "high"
    print(result.drag_coefficient)    # StatResult(mean=0.312, std=0.018, ...)
    print(result.training_ready)      # True
    result.download_csv("clean.csv")
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import requests

API_BASE = os.environ.get("SIMAPI_BASE_URL", "https://sim-api.vercel.app/api")
API_KEY = os.environ.get("SIMAPI_API_KEY")


def _auth_headers(api_key: str | None) -> dict[str, str]:
    """Resolve the API key from the argument or the SIMAPI_API_KEY env var."""
    key = api_key or API_KEY
    return {"X-API-Key": key} if key else {}


# ── Result objects ─────────────────────────────────────────────────────────────

@dataclass
class StatResult:
    mean:     float
    std:      float
    median:   float
    p5:       float
    p95:      float
    min:      float
    max:      float
    n:        int
    skewness: float | None = None
    cv:       float | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "StatResult":
        """Build from a server ``statistics`` entry, ignoring unknown keys.

        Tolerating extra fields keeps the SDK forward compatible as the server
        adds new statistics.
        """
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})

    def __repr__(self):
        return f"StatResult(mean={self.mean:.4f}, std={self.std:.4f}, n={self.n})"


@dataclass
class PhysicsCheck:
    name:        str
    status:      str   # "passed" | "warning" | "failed"
    description: str
    detail:      str
    value:       float | None = None

    def __repr__(self):
        icon = "✓" if self.status == "passed" else "⚠" if self.status == "warning" else "✗"
        return f"{icon} {self.name}: {self.detail}"


class ValidationResult:
    """
    Returned by simapi.validate(). Contains full validation report
    with physics checks, statistics, and ML-ready data.
    """
    def __init__(self, raw: dict):
        self._raw = raw

        self.job_id           = raw["job_id"]
        self.status           = raw["status"]           # passed/warning/failed
        self.confidence       = raw["confidence"]       # high/medium/low
        self.trials_submitted = raw["trials_submitted"]
        self.trials_valid     = raw["trials_valid"]
        self.trials_excluded  = raw["trials_excluded"]
        self.exclusion_rate   = raw["exclusion_rate"]
        self.training_ready   = raw["training_ready"]
        self.processing_ms    = raw["processing_ms"]
        # ``warnings`` on the wire is a count; expose it as such and keep the
        # surfaced checks under ``physics_checks``.
        self.warning_count    = raw.get("warnings", 0)
        self.exclusions       = raw.get("exclusions", [])
        self.provenance       = raw.get("provenance", {})
        self.ai               = raw.get("ai")
        self.ai_status        = raw.get("ai_status", "pending")

        # Physics checks. The server exposes surfaced checks under both
        # ``physics_checks`` (alias) and ``issues`` (canonical); accept either.
        surfaced = raw.get("physics_checks", raw.get("issues", []))
        self.physics_checks = [
            PhysicsCheck(
                name        = c["name"],
                status      = c["status"],
                description = c.get("description", ""),
                detail      = c.get("detail", ""),
                value       = c.get("value"),
            )
            for c in surfaced
        ]

        # Statistics — accessible as result.drag_coefficient, result.pressure, etc.
        self._statistics = {}
        for col, stats in raw.get("statistics", {}).items():
            stat = StatResult.from_dict(stats)
            self._statistics[col] = stat
            setattr(self, col, stat)

    def passed_checks(self) -> list[PhysicsCheck]:
        return [c for c in self.physics_checks if c.status == "passed"]

    def failed_checks(self) -> list[PhysicsCheck]:
        return [c for c in self.physics_checks if c.status == "failed"]

    def warning_checks(self) -> list[PhysicsCheck]:
        return [c for c in self.physics_checks if c.status == "warning"]

    def summary(self) -> str:
        lines = [
            "SimAPI Validation Report",
            f"{'─' * 40}",
            f"Job ID:          {self.job_id}",
            f"Status:          {self.status.upper()}",
            f"Confidence:      {self.confidence.upper()}",
            f"Trials:          {self.trials_valid}/{self.trials_submitted} valid "
            f"({self.exclusion_rate*100:.1f}% excluded)",
            f"Training ready:  {'YES' if self.training_ready else 'NO'}",
            f"Processing time: {self.processing_ms:.1f}ms",
            "",
            f"Physics Checks ({len(self.physics_checks)}):",
        ]
        for check in self.physics_checks:
            icon = "✓" if check.status == "passed" else "⚠" if check.status == "warning" else "✗"
            lines.append(f"  {icon} {check.name}: {check.detail[:60]}")

        if self._statistics:
            lines += ["", "Statistics (valid trials):"]
            for col, stat in self._statistics.items():
                lines.append(f"  {col}: mean={stat.mean:.4f} ± {stat.std:.4f}  "
                             f"[{stat.p5:.4f}, {stat.p95:.4f}]")

        warning_checks = self.warning_checks()
        if warning_checks:
            lines += ["", "Warnings:"]
            for w in warning_checks:
                lines.append(f"  ⚠ {w.name}: {w.detail[:60]}")

        return "\n".join(lines)

    def to_dataframe(self) -> pd.DataFrame:
        """Return statistics as a DataFrame."""
        rows = []
        for col, stat in self._statistics.items():
            rows.append({
                "quantity": col, "mean": stat.mean, "std": stat.std,
                "median": stat.median, "p5": stat.p5, "p95": stat.p95,
                "min": stat.min, "max": stat.max, "n": stat.n,
            })
        return pd.DataFrame(rows)

    def download_csv(self, path: str):
        """Save statistics to CSV."""
        self.to_dataframe().to_csv(path, index=False)
        print(f"Saved to {path}")

    def __repr__(self):
        icon = "✓" if self.status == "passed" else "⚠" if self.status == "warning" else "✗"
        return (f"ValidationResult({icon} {self.status} | "
                f"confidence={self.confidence} | "
                f"{self.trials_valid}/{self.trials_submitted} trials valid | "
                f"training_ready={self.training_ready})")


# ── Main SDK functions ────────────────────────────────────────────────────────

def validate(
    data:            str | list | pd.DataFrame | np.ndarray,
    simulation_type: str = "aerodynamics",
    conditions:      dict = None,
    job_id:          str | None = None,
    api_key:         str | None = None,
) -> ValidationResult:
    """
    Validate simulation data against physical laws.

    Args:
        data:            File path (CSV/JSON/VTK), list of dicts, DataFrame, or numpy array
        simulation_type: "aerodynamics" | "fluid_dynamics" | "structural" |
                         "thermodynamics" | "robotics"
        conditions:      Input conditions e.g. {"velocity": 15.0, "altitude": 120.0}
        job_id:          Optional tracking ID
        api_key:         SimAPI API key (not required for local server)

    Returns:
        ValidationResult with physics checks, statistics, and ML-ready flag

    Example:
        result = simapi.validate(
            data="cfd_output.csv",
            simulation_type="aerodynamics",
            conditions={"velocity": 15.0},
        )
        print(result.summary())
        print(result.drag_coefficient.mean)
    """
    conditions = conditions or {}

    # Load data
    records = _load_data(data)

    payload = {
        "data":            records,
        "simulation_type": simulation_type,
        "conditions":      conditions,
    }
    if job_id:
        payload["job_id"] = job_id

    response = requests.post(
        f"{API_BASE}/v1/validate",
        json    = payload,
        headers = _auth_headers(api_key),
        timeout = 60,
    )

    if response.status_code != 200:
        raise RuntimeError(_format_error(response))

    return ValidationResult(response.json())


def demo() -> ValidationResult:
    """
    Run a demo validation with pre-generated aerodynamics data.
    No input required. Great for testing the installation.

    Example:
        import simapi
        result = simapi.demo()
        print(result.summary())
    """
    response = requests.post(f"{API_BASE}/v1/demo", timeout=60)
    if response.status_code != 200:
        raise RuntimeError(f"SimAPI error {response.status_code}: {response.text}")
    return ValidationResult(response.json())


def health() -> dict:
    """Check API server health."""
    return requests.get(f"{API_BASE}/v1/health", timeout=10).json()


def get_job(job_id: str) -> ValidationResult:
    """Retrieve a previous job result by ID."""
    response = requests.get(f"{API_BASE}/v1/job/{job_id}", timeout=10)
    if response.status_code == 404:
        raise ValueError(f"Job {job_id} not found")
    return ValidationResult(response.json())


# ── Client class ────────────────────────────────────────────────────────────────

class SimAPI:
    """
    Object-oriented client, equivalent to the module-level functions but with a
    bound API key and base URL. Mirrors the Node SDK.

    Example:
        from simapi import SimAPI
        client = SimAPI(api_key="sk_live_...")
        result = client.validate("simulation.json", simulation_type="aerodynamics")
        print(result.status)
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or API_KEY
        self.base_url = (base_url or API_BASE).rstrip("/")

    def validate(
        self,
        data: str | list | pd.DataFrame | np.ndarray,
        simulation_type: str = "aerodynamics",
        conditions: dict | None = None,
        job_id: str | None = None,
    ) -> ValidationResult:
        """Validate simulation data. Accepts a file path, list, DataFrame, or array."""
        records = _load_data(data)
        payload = {
            "data": records,
            "simulation_type": simulation_type,
            "conditions": conditions or {},
        }
        if job_id:
            payload["job_id"] = job_id
        response = requests.post(
            f"{self.base_url}/v1/validate",
            json=payload,
            headers=_auth_headers(self.api_key),
            timeout=60,
        )
        if response.status_code != 200:
            raise RuntimeError(_format_error(response))
        return ValidationResult(response.json())

    def demo(self) -> ValidationResult:
        """Validate seeded synthetic data."""
        response = requests.post(
            f"{self.base_url}/v1/demo", headers=_auth_headers(self.api_key), timeout=60
        )
        if response.status_code != 200:
            raise RuntimeError(_format_error(response))
        return ValidationResult(response.json())

    def get_job(self, job_id: str) -> ValidationResult:
        """Retrieve a previous job result by id."""
        response = requests.get(
            f"{self.base_url}/v1/job/{job_id}", headers=_auth_headers(self.api_key), timeout=10
        )
        if response.status_code == 404:
            raise ValueError(f"Job {job_id} not found")
        return ValidationResult(response.json())

    def health(self) -> dict:
        """Server health and facts."""
        return requests.get(f"{self.base_url}/v1/health", timeout=10).json()


# ── Error helper ───────────────────────────────────────────────────────────────

def _format_error(response) -> str:
    """Render a server error using the structured envelope when available."""
    try:
        body = response.json().get("error", {})
        code = body.get("code", "error")
        message = body.get("message", response.text)
        rid = body.get("request_id")
        suffix = f" (request_id={rid})" if rid else ""
        return f"SimAPI error {response.status_code} [{code}]: {message}{suffix}"
    except Exception:
        return f"SimAPI error {response.status_code}: {response.text}"


# ── Data loading helper ────────────────────────────────────────────────────────

def _load_data(data) -> list[dict]:
    """Convert any input type to list of dicts for the API."""
    if isinstance(data, list):
        return data

    if isinstance(data, pd.DataFrame):
        return data.to_dict(orient="records")

    if isinstance(data, np.ndarray):
        if data.ndim == 1:
            data = data.reshape(-1, 1)
        return pd.DataFrame(data).to_dict(orient="records")

    if isinstance(data, (str, Path)):
        path = Path(data)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {data}")

        ext = path.suffix.lower()
        if ext == ".csv":
            return pd.read_csv(path).to_dict(orient="records")
        elif ext == ".json":
            with open(path) as f:
                raw = json.load(f)
            if isinstance(raw, list):
                return raw
            if isinstance(raw, dict) and "trials" in raw:
                return raw["trials"]
            return [raw]
        elif ext in (".npy", ".npz"):
            arr = np.load(path)
            return pd.DataFrame(arr).to_dict(orient="records")
        else:
            # Try CSV as fallback
            return pd.read_csv(path).to_dict(orient="records")

    raise TypeError(f"Unsupported data type: {type(data)}")
