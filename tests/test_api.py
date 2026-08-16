"""End-to-end API contract tests."""


def test_health_ok(client):
    r = client.get("/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["domains"] == 21
    assert "ai_enabled" in body


def test_metrics_exposes_prometheus_text(client):
    client.get("/v1/health")  # generate at least one request
    r = client.get("/v1/metrics")
    assert r.status_code == 200
    assert "simapi_http_requests_total" in r.text
    assert "simapi_uptime_seconds" in r.text


def test_validate_physics_only(client, sample_payload):
    r = client.post("/v1/validate/physics-only", json=sample_payload)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("passed", "warning", "failed")
    assert body["all_checks"] > 0
    assert body["ai_status"] == "disabled"  # AI skipped for physics-only
    # Canonical field and back-compat alias must agree.
    assert body["issues"] == body["physics_checks"]


def test_request_id_header_is_returned(client, sample_payload):
    r = client.post("/v1/validate/physics-only", json=sample_payload)
    assert r.headers.get("X-Request-ID")


def test_request_id_is_echoed_when_supplied(client):
    r = client.get("/v1/health", headers={"X-Request-ID": "trace-123"})
    assert r.headers["X-Request-ID"] == "trace-123"


def test_error_envelope_on_not_found(client):
    r = client.get("/v1/job/does-not-exist")
    assert r.status_code == 404
    err = r.json()["error"]
    assert err["code"] == "not_found"
    assert "request_id" in err


def test_error_envelope_on_schema_violation(client):
    r = client.post("/v1/validate", json={"data": "not-a-list"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_failed"


def test_payload_too_large_is_rejected(client, monkeypatch):
    import dataclasses

    from api import server as srv

    monkeypatch.setattr(srv, "settings", dataclasses.replace(srv.settings, max_rows=5))
    payload = {"data": [{"cd": 0.3} for _ in range(10)], "simulation_type": "aerodynamics"}
    r = client.post("/v1/validate", json=payload)
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "payload_too_large"


def test_jobs_pagination(client, sample_payload):
    client.post("/v1/validate/physics-only", json=sample_payload)
    r = client.get("/v1/jobs?limit=1&offset=0")
    assert r.status_code == 200
    page = r.json()["pagination"]
    assert set(page) == {"total", "limit", "offset", "returned"}
    assert page["limit"] == 1


def test_job_ai_poll_exposes_exclusion_fields(client, sample_payload):
    """Regression test: the AI worker folds new exclusions into the job, but the
    poll endpoint used to only return `ai` — silently dropping any trial the AI
    orchestrator excluded that the physics engine had passed."""
    job_id = client.post("/v1/validate/physics-only", json=sample_payload).json()["job_id"]
    r = client.get(f"/v1/job/{job_id}/ai")
    assert r.status_code == 200
    body = r.json()
    for key in ("ai_exclusions", "exclusions", "trials_excluded", "trials_valid", "exclusion_rate", "status", "training_ready"):
        assert key in body


def test_demo_runs(client):
    r = client.post("/v1/demo")
    assert r.status_code == 200
    body = r.json()
    # The demo is pristine synthetic aerodynamics data — meant to show a
    # near-100% pass rate so first-time playground users get a positive result.
    # With more columns (each an independent chance at a rare >3.5-sigma
    # outlier in 500 samples), a handful of natural-noise exclusions is
    # expected and still a >98% pass rate.
    assert body["trials_submitted"] == 500
    assert body["trials_excluded"] <= 12


def test_unparseable_upload_returns_400_not_500(client):
    """A malformed file is the caller's mistake -> a clean 400 with the error
    envelope, never a 500 with a leaked internal message."""
    r = client.post(
        "/v1/validate/upload",
        files={"file": ("empty.txt", "", "text/plain")},
        data={"simulation_type": "aerodynamics"},
    )
    assert r.status_code == 400
    err = r.json()["error"]
    assert err["code"] == "bad_request"
    assert "request_id" in err
    # The catch-all 500 handler must not have been reached.
    assert err["code"] != "internal_error"


def test_unsupported_simulation_type_upload(client):
    r = client.post(
        "/v1/validate/upload",
        files={"file": ("d.csv", "cd,cl\n0.3,0.8\n0.31,0.82\n", "text/csv")},
        data={"simulation_type": "warp_drive"},
    )
    # 415 Unsupported Media Type is the correct HTTP contract for
    # unrecognised simulation_type; previously returned 400 (default)
    # which was contract drift for clients that branched on status.
    assert r.status_code == 415
    assert r.json()["error"]["code"] == "unsupported_format"


def test_repair_preview_finds_duplicate_ids(client):
    r = client.post(
        "/v1/repair",
        json={"data": [{"trial_id": 1, "velocity": 150}, {"trial_id": 1, "velocity": 151}], "apply": False},
    )
    assert r.status_code == 200
    body = r.json()
    kinds = [p["kind"] for p in body["proposals"]]
    assert "duplicate_or_missing_ids" in kinds
    assert "repaired_data" not in body  # preview mode must not include the repaired dataset


def test_repair_apply_returns_repaired_data(client):
    r = client.post(
        "/v1/repair",
        json={"data": [{"trial_id": 1, "velocity": 150}, {"trial_id": 1, "velocity": 151}], "apply": True},
    )
    assert r.status_code == 200
    body = r.json()
    repaired_ids = [row["trial_id"] for row in body["repaired_data"]]
    assert len(set(repaired_ids)) == len(repaired_ids)  # IDs are unique after repair


def test_repair_on_clean_data_has_no_proposals(client):
    r = client.post(
        "/v1/repair",
        json={"data": [{"velocity": 150}, {"velocity": 151}, {"velocity": 152}]},
    )
    assert r.status_code == 200
    assert r.json()["proposals"] == []


def test_repair_handles_empty_data_gracefully(client):
    r = client.post("/v1/repair", json={"data": []})
    assert r.status_code == 200
    assert r.json()["proposals"] == []


def test_validate_dimensional_endpoint(client, sample_payload):
    r = client.post("/v1/validate/dimensional", json=sample_payload)
    assert r.status_code == 200
    body = r.json()
    assert body["n_rows"] == 30
    assert "impossible" in body and "inconsistent" in body and "unsuitable_for_training" in body
    assert isinstance(body["laws_discovered"], list)
    assert isinstance(body["units_resolved"], dict)
    # Ingestion normalizes cd/cl/re/ma to their canonical names before the
    # dimensional engine sees them; all four should resolve as dimensionless.
    for col in ("drag_coefficient", "lift_coefficient", "reynolds_number", "mach_number"):
        assert body["units_resolved"][col]["usable"], body["units_resolved"]


def test_validate_dimensional_catches_unit_swap(client):
    import numpy as np
    rng = np.random.default_rng(0)
    n = 60
    T = 293.15 + rng.normal(0, 1, n)
    rho = 1.225 + rng.normal(0, 0.006, n)
    P = rho * 287.05 * T
    P[5] = P[5] / 1000.0  # Pa written as kPa
    data = [{"temperature": float(t), "density": float(r), "pressure": float(p)}
            for t, r, p in zip(T, rho, P, strict=True)]
    r = client.post("/v1/validate/dimensional", json={"data": data, "simulation_type": "aerodynamics"})
    assert r.status_code == 200
    body = r.json()
    assert 5 in body["impossible"]


# ── Physics-validator ns_inf regression ───────────────────────────────
# `.replace([inf,-inf], nan).fillna(0)` before `np.isinf` used to strip
# every Inf, so `total_inf` was always 0 and the ns_inf check always
# passed silently. Direct call (not HTTP) because Python's json rejects
# Inf and TestClient can't ship a NaN/Inf-bearing body.
def test_ns_inf_check_catches_infinity():
    import math
    import pandas as pd
    from core.physics_validator import PhysicsValidator, SimulationType
    v = PhysicsValidator()
    df = pd.DataFrame([
        {"velocity": 10.0, "pressure": 101325.0, "temperature": 293.15},
        {"velocity": 11.0, "pressure": 101325.0, "temperature": 293.15},
        {"velocity": math.inf, "pressure": 101325.0, "temperature": 293.15},
        {"velocity": 12.0, "pressure": 101325.0, "temperature": 293.15},
    ])
    report = v.validate(df, SimulationType.AERODYNAMICS, {})
    inf_check = next((c for c in report.issues if c.name == "ns_inf"), None)
    inf_row_excluded = any(
        (e.reason or "").lower().find("nan/inf") >= 0 or (e.reason or "").lower().find("divergence") >= 0
        for e in report.exclusions
    )
    # Either the ns_inf check now fails (total_inf > 0), or the Inf-bearing
    # row is excluded on numerical divergence. Both are correct signal.
    assert (inf_check is not None and inf_check.status.value != "passed") or inf_row_excluded, (
        f"Inf value slipped past ns_inf: ns_inf={inf_check.status if inf_check else None} "
        f"excluded={[e.reason for e in report.exclusions][:3]}"
    )


# ── Row-cap regression: /v1/validate/dimensional and /v1/repair must
# now reject over-large bodies before pandas parses them.
def test_dimensional_endpoint_enforces_row_cap(client):
    from api.config import settings
    if settings.max_rows > 200_000:
        import pytest
        pytest.skip("max_rows too high to exercise cheaply")
    oversize = [{"temperature": 293.15, "density": 1.225, "pressure": 101325.0}] * (settings.max_rows + 1)
    r = client.post("/v1/validate/dimensional", json={"data": oversize})
    assert r.status_code == 413
    assert r.json()["error"]["code"] in ("payload_too_large", "PAYLOAD_TOO_LARGE")


# ── SDK regression: reserved attributes not overwritten by columns ──
def test_sdk_reserved_attributes_not_clobbered_by_column_stats():
    from sdk.simapi import ValidationResult
    raw = {
        "job_id": "abc", "status": "passed", "confidence": "high",
        "trials_submitted": 10, "trials_valid": 10, "trials_excluded": 0,
        "exclusion_rate": 0.0, "training_ready": True, "processing_ms": 12.3,
        "statistics": {
            "status": {"mean": 0.5, "std": 0.1, "median": 0.5, "p5": 0.4,
                       "p95": 0.6, "min": 0.4, "max": 0.6, "n": 10},
            "drag_coefficient": {"mean": 0.312, "std": 0.02, "median": 0.31,
                                 "p5": 0.28, "p95": 0.34, "min": 0.27,
                                 "max": 0.35, "n": 10},
        },
    }
    result = ValidationResult(raw)
    # Reserved name must NOT be overwritten -- .status stays the pass/fail string.
    assert result.status == "passed"
    # Column collides w/ reserved name -> reachable via .statistics dict.
    assert "status" in result.statistics
    # Non-reserved column still bound as attribute.
    assert hasattr(result, "drag_coefficient")
    assert result.drag_coefficient.mean == 0.312
    # summary() still callable (would crash if setattr had clobbered it).
    assert isinstance(result.summary(), str)


# ── SDK NaN sanitization: a DataFrame with a blank cell used to break
# the JSON body because requests(json=payload) emits bare `NaN`.
def test_sdk_sanitizes_nan_before_posting():
    from sdk.simapi import _sanitize_for_json
    import math
    payload = {
        "data": [
            {"velocity": 10.0, "pressure": math.nan},
            {"velocity": 11.0, "pressure": 101300.0},
            {"velocity": math.inf, "pressure": 101310.0},
        ],
        "simulation_type": "aerodynamics",
    }
    out = _sanitize_for_json(payload)
    import json
    # Must produce strict JSON (no NaN token). If sanitization missed
    # a spot, `allow_nan=False` raises.
    _ = json.dumps(out, allow_nan=False)
    assert out["data"][0]["pressure"] is None
    assert out["data"][2]["velocity"] is None
