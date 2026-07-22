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
    assert body["all_checks"] > 100
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
    assert body["trials_submitted"] == 500
    assert body["trials_excluded"] <= 5


def test_unsupported_simulation_type_upload(client):
    r = client.post(
        "/v1/validate/upload",
        files={"file": ("d.csv", "cd,cl\n0.3,0.8\n0.31,0.82\n", "text/csv")},
        data={"simulation_type": "warp_drive"},
    )
    assert r.status_code == 400
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
