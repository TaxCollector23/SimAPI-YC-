"""
SimAPI v3 — REST API Server.

Validation flow:
  * Physics result is computed synchronously and returned immediately.
  * The AI reasoning layer runs asynchronously and is polled via
    ``GET /v1/job/{id}/ai``.
  * Column aliases are normalized during ingestion before any validation runs,
    and trial exclusions are de-duplicated before serialization.

Production concerns (auth, rate limiting, request correlation, structured
logging, metrics, a consistent error contract, and CORS) are layered on via
middleware and dependencies without altering the validation semantics, so the
public response schema remains backward compatible.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import uuid
from typing import Any

import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, File, Form, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from pydantic import BaseModel, Field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.config import settings
from api.errors import (
    ErrorCode,
    NotFoundError,
    PayloadTooLargeError,
    SimAPIError,
    error_body,
)
from api.observability import log, metrics, request_id_ctx
from api.security import authenticate, enforce_rate_limit
from core.ai_orchestrator import AI_ENABLED as ORCHESTRATOR_ENABLED
from core.ai_orchestrator import orchestrate as ai_orchestrate
from core.ai_orchestrator import result_to_dict as orchestrator_dict
from core.ai_validator import AI_ENABLED, validate_with_ai
from core.ai_validator import MODEL as AI_MODEL
from core.ai_validator import report_to_dict as ai_dict
from core.ingestion import DataIngester
from core.mesh_validator import MeshValidator, humanize_mesh_check_name, predict_corruption_risks
from core.physics_validator import PhysicsValidator, SimulationType
from core.repair import analyze as repair_analyze

API_VERSION = "3.1.0"

app = FastAPI(
    title="SimAPI",
    version=API_VERSION,
    description=(
        "The CI/CD layer for engineering simulations. Dual-layer validation: "
        "1300+ deterministic physics checks across 21 domains plus optional LLM "
        "reasoning."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

validator = PhysicsValidator()
mesh_validator = MeshValidator()
ingester = DataIngester()


@app.get("/", include_in_schema=False)
async def root():
    """
    This server (port 8000 by default) is the Python validation API, not the
    website. The dashboard / website frontend runs separately via `npm run
    dev` in web/ (http://localhost:3000) and talks to this API when
    PYTHON_API_URL is set. Redirect here to the interactive API docs instead
    of a bare 404, since that's the closest thing to a "frontend" this
    service has.
    """
    return RedirectResponse(url="/docs")

# Job store: {job_id: {physics: dict, ai_running: bool, ts: float}}
JOBS: dict[str, dict[str, Any]] = {}
_JOBS_LOCK = threading.Lock()


# ── Request / response models ───────────────────────────────────────────────────
class ValidateRequest(BaseModel):
    """Payload for JSON validation requests."""

    data: list[dict[str, Any]] = Field(..., description="Trials as a list of records.")
    simulation_type: SimulationType = Field(
        default=SimulationType.AERODYNAMICS, description="Physics domain to validate against."
    )
    conditions: dict[str, float] = Field(default_factory=dict, description="Input boundary conditions.")
    job_id: str | None = Field(default=None, description="Optional caller-supplied tracking id.")
    run_ai: bool = Field(default=True, description="Run the async AI reasoning layer.")
    deep_ai: bool = Field(
        default=False,
        description="Use the 5-phase AI orchestrator (root-cause analysis, ~10-90s) instead of "
        "the default quick sanity check (~2-18s, 'normal'/'not normal' verdict).",
    )
    geometry_description: str | None = Field(default=None, description="Free text geometry description.")
    what_are_you_measuring: str | None = Field(default=None, description="What the simulation is studying.")
    expected_output_ranges: dict[str, list[float]] | None = Field(default=None, description="Expected value ranges.")
    reference_dataset_id: str | None = Field(default=None, description="Previous clean validation job ID.")
    known_issues: str | None = Field(default=None, description="Known data issues to ignore.")
    ml_model_type: str | None = Field(default=None, description="tree|neural_network|linear|other")


class RepairRequest(BaseModel):
    """Payload for the automatic-repair endpoint."""

    data: list[dict[str, Any]] = Field(..., description="Trials as a list of records.")
    apply: bool = Field(default=False, description="If true, return the repaired dataset. If false (default), preview only.")


class SetupValidateRequest(BaseModel):
    """Payload for pre-simulation (mesh + setup) validation."""

    config: dict[str, Any] = Field(default_factory=dict, description="Simulation configuration dict.")
    mesh_stats: dict[str, Any] | None = Field(default=None, description="Mesh quality metrics, if available.")
    solver: str = Field(default="openfoam", description="openfoam | ansys | comsol | su2 | abaqus")
    physics: str = Field(default="fluid", description="fluid | structural | thermal | electromagnetic")
    simulation_type: str = Field(default="aerodynamics", description="Output physics domain.")


# ── Middleware: correlation id, timing, structured access log, metrics ──────────
@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex
    token = request_id_ctx.set(rid)
    start = time.perf_counter()
    try:
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000.0
        response.headers["X-Request-ID"] = rid
        response.headers["Server-Timing"] = f"app;dur={duration_ms:.1f}"
        route = request.scope.get("route")
        metrics.incr(
            "http_requests_total",
            method=request.method,
            path=route.path if route else request.url.path,
            status=str(response.status_code),
        )
        metrics.observe_latency(duration_ms)
        log.info(
            "request",
            extra={
                "ctx_method": request.method,
                "ctx_path": request.url.path,
                "ctx_status": response.status_code,
                "ctx_duration_ms": round(duration_ms, 1),
            },
        )
        return response
    finally:
        request_id_ctx.reset(token)


# ── Exception handlers: single, consistent error envelope everywhere ────────────
@app.exception_handler(SimAPIError)
async def _handle_simapi_error(request: Request, exc: SimAPIError):
    metrics.incr("errors_total", code=exc.code)
    body = error_body(exc.code, exc.message, request_id=request_id_ctx.get(), details=exc.details)
    headers = {}
    if exc.code == ErrorCode.RATE_LIMITED:
        headers["Retry-After"] = str(int(exc.details.get("retry_after_seconds", 1)) or 1)
    return JSONResponse(status_code=exc.status_code, content=body, headers=headers)


@app.exception_handler(RequestValidationError)
async def _handle_validation_error(request: Request, exc: RequestValidationError):
    metrics.incr("errors_total", code=ErrorCode.VALIDATION_FAILED)
    # ``exc.errors()`` may carry non-serializable objects (e.g. exception ctx);
    # keep only the JSON-safe fields clients actually need.
    errors = [
        {"loc": list(e.get("loc", [])), "msg": str(e.get("msg", "")), "type": e.get("type", "")}
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=error_body(
            ErrorCode.VALIDATION_FAILED,
            "Request failed schema validation.",
            request_id=request_id_ctx.get(),
            details={"errors": errors},
        ),
    )


@app.exception_handler(Exception)
async def _handle_unexpected(request: Request, exc: Exception):
    metrics.incr("errors_total", code=ErrorCode.INTERNAL)
    log.exception("unhandled_exception")
    message = str(exc) if not settings.is_production else "An internal error occurred."
    return JSONResponse(
        status_code=500,
        content=error_body(ErrorCode.INTERNAL, message, request_id=request_id_ctx.get()),
    )


# ── Auth + rate-limit dependency ────────────────────────────────────────────────
async def caller_identity(request: Request) -> str:
    """Authenticate the request and enforce the caller's rate-limit budget."""
    identity = authenticate(request)
    enforce_rate_limit(identity)
    return identity


# ── Serialization ───────────────────────────────────────────────────────────────
def _json_safe(value: Any) -> Any:
    """Recursively replace non-finite floats (NaN/inf) with None.

    Statistics such as the skewness of a constant column are legitimately NaN,
    but JSON has no representation for them and strict encoders reject them.
    """
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _serialize(report, df: pd.DataFrame) -> dict[str, Any]:
    """Serialize a physics report, de-duplicating exclusions by trial index."""
    seen: set = set()
    unique_excl: list[dict[str, Any]] = []
    for e in report.exclusions:
        key = (e.trial_index, e.reason[:40])
        if key not in seen:
            seen.add(key)
            unique_excl.append({"trial_index": e.trial_index, "reason": e.reason, "severity": e.severity})

    issues = [
        {
            "name": c.name,
            "status": c.status.value if hasattr(c.status, "value") else str(c.status),
            "description": c.description,
            "detail": c.detail,
            "value": c.value,
            "category": c.category,
        }
        for c in report.issues
    ]

    stats = {
        col: {
            "mean": s.mean, "std": s.std, "median": s.median,
            "p5": s.p5, "p95": s.p95, "min": s.min, "max": s.max,
            "n": s.n, "skewness": s.skewness, "cv": s.cv,
        }
        for col, s in report.statistics.items()
    }

    renamed = df.attrs.get("simapi_renamed", {})

    return _json_safe({
        "job_id": report.job_id,
        "status": report.overall_status.value,
        "confidence": report.confidence.value,
        "trials_submitted": report.trials_submitted,
        "trials_valid": report.trials_valid,
        "trials_excluded": report.trials_excluded,
        "exclusion_rate": report.exclusion_rate,
        "training_ready": report.training_ready,
        "processing_ms": report.processing_time_ms,
        "all_checks": report.all_checks_count,
        "passed": report.passed_count,
        "warnings": report.warning_count,
        "failed": report.failed_count,
        # ``issues`` is the canonical field; ``physics_checks`` is a stable alias
        # kept for SDK/back-compat. Both point at the same surfaced checks.
        "issues": issues,
        "physics_checks": issues,
        "exclusions": unique_excl,
        "statistics": stats,
        "checks_by_category": report.checks_by_category,
        "provenance": report.provenance,
        "columns_renamed": renamed,
        "ai": None,
        "ai_status": "pending",  # overwritten by the caller based on run_ai / AI availability
        "ai_exclusions": [],     # populated by the AI second-pass worker
    })


def _prune_jobs() -> None:
    """Evict expired or overflow jobs to bound memory (called under lock)."""
    now = time.time()
    expired = [jid for jid, s in JOBS.items() if now - s["ts"] > settings.job_ttl_seconds]
    for jid in expired:
        JOBS.pop(jid, None)
    if len(JOBS) > settings.max_jobs:
        for jid, _ in sorted(JOBS.items(), key=lambda x: x[1]["ts"])[: len(JOBS) - settings.max_jobs]:
            JOBS.pop(jid, None)


def _ai_exclusion_indices(df: pd.DataFrame, ai_findings: list[dict]) -> list[int]:
    """Second-pass exclusions: pull specific trial indices out of critical AI
    findings (converting 1-indexed display → 0-indexed data)."""
    idxs: set[int] = set()
    for finding in ai_findings or []:
        if finding.get("severity") == "critical" and finding.get("trials"):
            for trial_num in finding["trials"]:
                i = int(trial_num) - 1
                if 0 <= i < len(df):
                    idxs.add(i)
    return sorted(idxs)


def _run_ai_async(job_id: str, df: pd.DataFrame, sim_type: str,
                  conditions: dict, physics_issues: list[dict],
                  physics_result: dict | None = None,
                  context: dict | None = None,
                  deep_ai: bool = False) -> None:
    try:
        with _JOBS_LOCK:
            if job_id in JOBS:
                JOBS[job_id]["ai_running"] = True

        # Build diagnosis context from APIE causal diagnosis engine
        diagnosis_context = None
        with _JOBS_LOCK:
            apie_result = JOBS.get(job_id, {}).get("apie_result")
        if apie_result and hasattr(apie_result, "diagnosis") and apie_result.diagnosis:
            dx = apie_result.diagnosis
            diagnosis_context = {
                "primary_finding": dx.primary_diagnosis,
                "pipeline_stage": dx.pipeline_stage,
                "causal_chain": dx.causal_chain,
                "investigation_steps": dx.investigation_steps,
                "confidence": dx.confidence,
            }

        # ── Grounded AI pipeline (cluster -> verify -> narrate) ────────────
        # Replaces the single-shot "second opinion" call. Every root cause is
        # verified by a deterministic probe before it is reported, and the whole
        # pipeline degrades to a deterministic summary rather than to an error.
        from core.ai_pipeline import run_pipeline

        profile_summary = ""
        try:
            prov = (physics_result or {}).get("provenance") or {}
            dp = prov.get("dataset_profile") or {}
            if dp:
                profile_summary = (
                    f"{dp.get('design_type', 'unknown').replace('_', ' ')}, "
                    f"regime {dp.get('regime', 'unknown')}, "
                    f"swept: {', '.join((dp.get('swept_columns') or [])[:3]) or 'none'}"
                )
        except Exception:
            pass

        pipe = run_pipeline(
            df, sim_type, physics_result or {}, profile_summary, use_ai=True,
        )

        confirmed = [c for c in pipe.root_causes if c.status == "confirmed"]
        hypotheses = [c for c in pipe.root_causes if c.status == "hypothesis"]
        status = ("passed" if not pipe.root_causes
                  else "failed" if confirmed else "warning")

        ai_data = {
            "status": status,
            "verdict": "Normal" if not pipe.root_causes else "Not Normal",
            "pipeline_version": pipe.version,
            "model": pipe.model_narrate or "deterministic",
            "processing_ms": sum(pipe.phase_timings.values()),
            "phase_timings": pipe.phase_timings,
            "degraded": pipe.degraded,
            "narrative": pipe.narrative,
            "narrative_source": pipe.narrative_source,
            "dataset_summary": pipe.narrative,
            "anomaly_score": 0.0 if not pipe.root_causes else (0.85 if confirmed else 0.45),
            "n_findings_in": pipe.n_findings_in,
            "n_causes_out": pipe.n_causes_out,
            "root_causes": [c.to_dict() for c in pipe.root_causes],
            "findings": [{
                "severity": "critical" if c.status == "confirmed" else "warning",
                "category": c.mode_key,
                "title": c.label,
                "detail": (f"{c.stage} — affects trial(s) "
                           f"{', '.join(str(t + 1) for t in c.affected_trials[:8])}. {c.action}"),
                "trials": [t + 1 for t in c.affected_trials],
                "confidence": c.confidence,
                "status": c.status,
                "evidence": c.evidence[:4],
                "source": c.source,
            } for c in pipe.root_causes],
            "recommendations": [c.action for c in (confirmed + hypotheses)[:4]],
            "error": None,
        }

        # The AI layer never removes rows. Exclusions are the physics engine's
        # decision alone; the pipeline only explains them.
        ai_excl = []
        with _JOBS_LOCK:
            if job_id not in JOBS:
                return
            physics = JOBS[job_id]["physics"]
            physics["ai"] = ai_data
            physics["ai_status"] = ai_data["status"]
            physics["ai_exclusions"] = ai_excl
            listed = {e["trial_index"] for e in physics["exclusions"]}
            new_ai = [i for i in ai_excl if i not in listed]
            for i in new_ai:
                physics["exclusions"].append(
                    {"trial_index": i, "reason": "AI-flagged critical anomaly", "severity": "critical"}
                )
            if new_ai:
                physics["trials_excluded"] += len(new_ai)
                physics["trials_valid"] = max(0, physics["trials_valid"] - len(new_ai))
                sub = physics["trials_submitted"] or 1
                physics["exclusion_rate"] = round(physics["trials_excluded"] / sub, 4)
            ai_sev = {"passed": 0, "warning": 1, "failed": 2, "error": 0, "disabled": 0}.get(ai_data["status"], 0)
            ph_sev = {"passed": 0, "warning": 1, "failed": 2}.get(physics["status"], 0)
            if ai_sev > ph_sev:
                physics["status"] = ai_data["status"]
                if ai_data.get("anomaly_score", 0) > 0.5:
                    physics["training_ready"] = False
        metrics.incr("ai_validations_total", status=ai_data["status"])
    except Exception as e:
        log.exception("ai_worker_failed")
        with _JOBS_LOCK:
            if job_id in JOBS:
                JOBS[job_id]["physics"]["ai_status"] = "error"
                JOBS[job_id]["physics"]["ai"] = {
                    "error": str(e), "status": "error", "findings": [], "recommendations": [],
                }
    finally:
        with _JOBS_LOCK:
            if job_id in JOBS:
                JOBS[job_id]["ai_running"] = False

# APIE singleton — loaded once at startup
try:
    from core.apie import AdaptivePhysicsIntelligenceEngine as _APIE
    _apie_engine = _APIE()
    APIE_AVAILABLE = True
except Exception:
    _apie_engine = None
    APIE_AVAILABLE = False


async def _validate_core(req: ValidateRequest) -> dict[str, Any]:
    if len(req.data) > settings.max_rows:
        raise PayloadTooLargeError(
            f"Request exceeds the maximum of {settings.max_rows} rows.",
            details={"rows": len(req.data), "limit": settings.max_rows},
        )

    df, ingest_meta = ingester.ingest(req.data, format_hint="json")
    # ``df.attrs`` is the pandas-sanctioned slot for user metadata (no warning).
    df.attrs["simapi_renamed"] = ingest_meta.get("columns_renamed", {})

    jid = req.job_id or uuid.uuid4().hex[:8]
    physics = validator.validate(df, req.simulation_type, req.conditions, jid)
    result = _serialize(physics, df)

    # ── APIE v3.1: five-layer engine + causal diagnosis + cross-run memory ──
    if APIE_AVAILABLE and _apie_engine is not None:
        try:
            domain_str = (req.simulation_type.value
                          if hasattr(req.simulation_type, "value")
                          else str(req.simulation_type))
            conditions_dict = dict(req.conditions or {})

            apie_result = _apie_engine.validate(
                df, domain=domain_str, conditions=conditions_dict, risk_mode="precision",
            )

            # Cross-run history check
            cross_run = None
            config_key = req.job_id or domain_str
            try:
                from core.run_history import get_default_tracker
                tracker = get_default_tracker()
                cross_run = tracker.check_and_update(
                    fingerprint=apie_result.fingerprint,
                    config_key=config_key,
                    n_excluded=len(apie_result.excluded_indices),
                    n_flagged=len(apie_result.flagged_for_review),
                    corruption_types=list(apie_result.test_plan.suspected_corruption_types.keys()),
                )
            except Exception:
                pass

            # Merge exclusions
            physics_excl = set(result.get("excluded_indices", []))
            apie_excl = apie_result.excluded_indices
            merged_excl = sorted(physics_excl | apie_excl)
            result["excluded_indices"] = merged_excl

            # Build response
            dx = apie_result.diagnosis
            result["apie"] = {
                "version": "3.1",
                "domain_profile": apie_result.domain_profile,
                "discovered_invariants": apie_result.discovered_invariants,
                "ai_used": apie_result.ai_used,
                "processing_ms": apie_result.processing_ms,
                "checks_run": [c["check"] for c in apie_result.test_plan.checks],
                "suspected_corruption": {
                    k: round(v, 2)
                    for k, v in apie_result.test_plan.suspected_corruption_types.items()
                    if v > 0.2
                },
                "flagged_for_review": apie_result.flagged_for_review[:20],
                "total_exclusions": len(merged_excl),
                "n_flagged_review": len(apie_result.flagged_for_review),
                # Causal diagnosis
                "diagnosis": {
                    "primary_finding": dx.matched_failure_modes[0]["failure_mode"] if dx and dx.matched_failure_modes else "none",
                    "pipeline_stage": dx.pipeline_stage if dx else "unknown",
                    "causal_chain": dx.causal_chain[:3] if dx else [],
                    "investigation_steps": dx.investigation_steps[:3] if dx else [],
                    "confidence": dx.confidence if dx else 0,
                    "counterfactual_impact": (dx.counterfactual_impact[:300] if dx else ""),
                } if dx else None,
                # Cross-run context
                "cross_run": {
                    "n_historical_runs": cross_run.n_historical_runs,
                    "run_is_outlier": cross_run.run_is_outlier,
                    "config_match_score": cross_run.config_match_score,
                    "anomalies": [
                        {"kind": a.kind, "subject": a.subject,
                         "sigma": a.sigma, "severity": a.severity,
                         "interpretation": a.interpretation}
                        for a in cross_run.anomalies[:5]
                    ],
                } if cross_run else None,
            }
        except Exception as _apie_err:
            result["apie"] = {"error": str(_apie_err), "version": "3.1"}

    result["columns_renamed"] = ingest_meta.get("columns_renamed", {})
    result["ai_status"] = "pending" if (req.run_ai and AI_ENABLED) else "disabled"

    with _JOBS_LOCK:
        JOBS[jid] = {"physics": result, "ai_running": False, "ts": time.time()}
        if APIE_AVAILABLE and "apie_result" in dir():
            JOBS[jid]["apie_result"] = apie_result
        _prune_jobs()

    metrics.incr("physics_validations_total", status=result["status"])

    if req.run_ai and (AI_ENABLED or ORCHESTRATOR_ENABLED):
        context = {}
        if req.geometry_description:
            context["geometry_description"] = req.geometry_description
        if req.what_are_you_measuring:
            context["what_are_you_measuring"] = req.what_are_you_measuring
        if req.expected_output_ranges:
            context["expected_output_ranges"] = req.expected_output_ranges
        if req.known_issues:
            context["known_issues"] = req.known_issues
        if req.ml_model_type:
            context["ml_model_type"] = req.ml_model_type
        threading.Thread(
            target=_run_ai_async,
            args=(jid, df, req.simulation_type.value, req.conditions, result["issues"]),
            kwargs={"physics_result": result, "context": context or None, "deep_ai": req.deep_ai},
            daemon=True,
        ).start()

    return result


# ── Health / metrics ─────────────────────────────────────────────────────────────
@app.get("/v1/health", tags=["system"])
async def health() -> dict[str, Any]:
    """Liveness + basic service facts. Unauthenticated by design."""
    return {
        "status": "ok",
        "version": API_VERSION,
        "environment": settings.environment,
        "physics_checks": "1300+",
        "domains": 21,
        "ai_enabled": AI_ENABLED,
        "ai_model": AI_MODEL,
        "jobs_processed": validator.checks_run,
        "avg_physics_ms": round(validator.total_processing_ms / max(validator.checks_run, 1), 1),
    }


@app.get("/v1/metrics", response_class=PlainTextResponse, tags=["system"])
async def prometheus_metrics() -> str:
    """Prometheus text-format metrics for scraping."""
    return metrics.render()


# ── Validation endpoints ─────────────────────────────────────────────────────────
@app.post("/v1/validate", tags=["validation"])
async def validate(req: ValidateRequest, _: str = Depends(caller_identity)):
    return await _validate_core(req)


@app.post("/v1/validate/upload", tags=["validation"])
async def validate_upload(
    file: UploadFile = File(...),
    simulation_type: str = Form("aerodynamics"),
    conditions: str = Form("{}"),
    job_id: str = Form(""),
    run_ai: str = Form("true"),
    _: str = Depends(caller_identity),
):
    contents = await file.read()
    if len(contents) > settings.max_upload_bytes:
        raise PayloadTooLargeError(
            f"Upload exceeds the maximum of {settings.max_upload_bytes} bytes.",
            details={"bytes": len(contents), "limit": settings.max_upload_bytes},
        )
    try:
        conditions_parsed = json.loads(conditions or "{}")
    except json.JSONDecodeError as e:
        raise SimAPIError(f"`conditions` must be valid JSON: {e}", code=ErrorCode.BAD_REQUEST) from e
    try:
        sim = SimulationType(simulation_type)
    except ValueError as e:
        raise SimAPIError(
            f"Unknown simulation_type '{simulation_type}'.",
            code=ErrorCode.UNSUPPORTED_FORMAT,
            details={"allowed": [s.value for s in SimulationType]},
        ) from e
    df, _meta = ingester.ingest(contents, filename=file.filename)
    req = ValidateRequest(
        data=df.to_dict(orient="records"),
        simulation_type=sim,
        conditions=conditions_parsed,
        job_id=job_id or uuid.uuid4().hex[:8],
        run_ai=run_ai.lower() == "true",
    )
    return await _validate_core(req)


@app.post("/v1/validate/physics-only", tags=["validation"])
async def validate_physics_only(req: ValidateRequest, _: str = Depends(caller_identity)):
    req.run_ai = False
    return await _validate_core(req)


@app.post("/v1/validate/setup", tags=["validation"])
async def validate_setup(req: SetupValidateRequest, _: str = Depends(caller_identity)):
    """
    Pre-flight validation: judge a mesh + solver + physics setup BEFORE it runs
    and predict which output checks are likely to fail.

    Now powered by APIE: mesh quality metrics are analyzed alongside any
    historical run data to predict specific corruption types (solver divergence,
    sensor drift, measurement noise) with confidence scores.
    """
    report = mesh_validator.validate(
        config=req.config, mesh_stats=req.mesh_stats,
        solver=req.solver, physics=req.physics, simulation_type=req.simulation_type,
    )

    # APIE preflight corruption prediction
    apie_preflight = {}
    try:
        from core.mesh_validator import predict_output_corruption
        apie_preflight = predict_output_corruption(
            simulation_type=req.simulation_type.value if hasattr(req.simulation_type, "value")
                            else str(req.simulation_type),
            mesh_stats=dict(req.mesh_stats or {}),
            solver_settings=dict(req.solver or {}),
        )
    except Exception as e:
        apie_preflight = {"error": str(e)}
    # ── APIE pre-flight risk prediction ─────────────────────────────────────
    try:
        apie_preflight = predict_corruption_risks(
            simulation_type=req.simulation_type.value if hasattr(req.simulation_type, 'value') else str(req.simulation_type),
            mesh_stats=req.mesh_stats or {},
            solver=req.solver or {},
            physics=req.physics or {},
        )
    except Exception as _pf_err:
        apie_preflight = {"error": str(_pf_err)[:200]}

    issues = [
        {
            "name": c.name,
            "human_name": humanize_mesh_check_name(c.name),
            "status": c.status,
            "description": c.description,
            "detail": c.detail,
            "value": c.value,
            "category": c.category,
        }
        for c in report.issues
    ]
    metrics.incr("setup_validations_total", status=report.status)
    return _json_safe({
        "status": report.status,
        "all_checks": report.all_checks_count,
        "passed": report.passed_count,
        "warnings": report.warning_count,
        "failed": report.failed_count,
        "issues": issues,
        "predicted_error_types": report.predicted_error_types,
        "estimated_corruption_risk": report.estimated_corruption_risk,
        "apie_preflight": apie_preflight,
        "recommendations": report.recommendations,
        "processing_ms": report.processing_ms,
    })


@app.post("/v1/repair", tags=["validation"])
async def repair(req: RepairRequest, _: str = Depends(caller_identity)):
    """
    Automatic repair: deterministic, reversible fixes for structural data
    problems (duplicate rows, missing/duplicate IDs, out-of-order timestamps,
    wrapped angles, short NaN gaps). This never touches physics violations —
    those are the user's data quality problem to investigate, not something
    SimAPI silently rewrites.

    By default this only previews proposed changes (`apply=false`). Set
    `apply=true` to receive the repaired dataset in the response.
    """
    df, _meta = ingester.ingest(req.data, format_hint="json")
    report = repair_analyze(df)
    result = _json_safe(report.to_dict())
    metrics.incr("repairs_total", proposals=str(len(report.proposals)))
    if req.apply:
        result["repaired_data"] = report.apply(df).to_dict(orient="records")
    return result


@app.get("/v1/job/{job_id}", tags=["jobs"])
async def get_job(job_id: str, _: str = Depends(caller_identity)):
    with _JOBS_LOCK:
        if job_id not in JOBS:
            raise NotFoundError(f"Job {job_id} not found.")
        result = JOBS[job_id]["physics"].copy()
        result["ai_running"] = JOBS[job_id]["ai_running"]
    return result


@app.get("/v1/job/{job_id}/ai", tags=["jobs"])
async def get_job_ai(job_id: str, _: str = Depends(caller_identity)):
    """
    Poll for the AI result once it is ready.

    The AI worker (_run_ai_async) folds AI-flagged trials into the job's
    exclusion set and can escalate status/training_ready — return those
    fields too, or a client that only reads `ai` will silently miss any
    trial the physics engine passed but the AI orchestrator excluded.
    """
    with _JOBS_LOCK:
        if job_id not in JOBS:
            raise NotFoundError(f"Job {job_id} not found.")
        physics = JOBS[job_id]["physics"]
        return {
            "job_id": job_id,
            "ai_running": JOBS[job_id]["ai_running"],
            "ai_status": physics.get("ai_status", "pending"),
            "ai": physics.get("ai"),
            "ai_exclusions": physics.get("ai_exclusions", []),
            "exclusions": physics.get("exclusions", []),
            "trials_excluded": physics.get("trials_excluded"),
            "trials_valid": physics.get("trials_valid"),
            "exclusion_rate": physics.get("exclusion_rate"),
            "status": physics.get("status"),
            "training_ready": physics.get("training_ready"),
        }


@app.get("/v1/jobs", tags=["jobs"])
async def list_jobs(
    limit: int = Query(50, ge=1, le=500, description="Page size."),
    offset: int = Query(0, ge=0, description="Number of jobs to skip."),
    _: str = Depends(caller_identity),
):
    """List recent jobs, newest first, with cursor-free offset pagination."""
    with _JOBS_LOCK:
        ordered = sorted(JOBS.items(), key=lambda x: x[1]["ts"], reverse=True)
        total = len(ordered)
        page = ordered[offset : offset + limit]
        jobs = [
            {
                "job_id": jid,
                "ts": s["ts"],
                "status": s["physics"]["status"],
                "checks": s["physics"]["all_checks"],
                "ai_status": s["physics"].get("ai_status", "pending"),
                "ai_running": s["ai_running"],
            }
            for jid, s in page
        ]
    return {
        "jobs": jobs,
        "pagination": {"total": total, "limit": limit, "offset": offset, "returned": len(jobs)},
    }


@app.post("/v1/demo", tags=["validation"])
async def demo(_: str = Depends(caller_identity)):
    """Run a validation against pristine synthetic aerodynamics data (100% pass example)."""
    np.random.seed(42)
    n = 500
    v = 15.0
    rho = 1.225  # Air density at sea level
    L = 0.5  # Reference length
    mu = 1.81e-5  # Dynamic viscosity
    data = []
    # Generate perfectly valid aerodynamic dataset with exact physics relationships
    for _i in range(n):
        # Small variations on base values
        v_var = v + np.random.normal(0, 0.02)
        cd = 0.31 + np.random.normal(0, 0.007)
        cl = 0.85 + np.random.normal(0, 0.012)
        cd = np.clip(cd, 0.09, 0.42)
        cl = np.clip(cl, -1.0, 1.0)
        # Exact physics relationships
        mach = v_var / 343.0
        reynolds = (rho * v_var * L) / mu  # Exact Reynolds number
        data.append({
            "drag_coefficient": float(cd),
            "lift_coefficient": float(cl),
            "reynolds_number": float(reynolds),  # Exact relationship
            "pressure": float(101325 + np.random.normal(0, 150)),
            "velocity": float(v_var),
            "mach_number": float(mach),  # Exact relationship
            "angle_of_attack": float(4.0 + np.random.normal(0, 1.0)),
            "temperature": float(288.15 + np.random.normal(0, 2.0)),
            "density": float(rho + np.random.normal(0, 0.01)),
            "viscosity": float(mu + np.random.normal(0, 1e-7)),
            "skin_friction_coefficient": float(0.004 + np.random.normal(0, 0.0003)),
            "turbulence_intensity": float(0.03 + np.random.normal(0, 0.004)),
            "pitching_moment": float(-0.05 + np.random.normal(0, 0.005)),
            "side_force_coefficient": float(0.02 + np.random.normal(0, 0.003)),
        })
    return await _validate_core(ValidateRequest(
        data=data,
        simulation_type=SimulationType.AERODYNAMICS,
        conditions={"velocity": v, "altitude": 120.0},
        job_id=f"demo_{uuid.uuid4().hex[:6]}",
        run_ai=True,
    ))


@app.on_event("startup")
async def _on_startup() -> None:
    log.info(
        "startup",
        extra={
            "ctx_version": API_VERSION,
            "ctx_environment": settings.environment,
            "ctx_ai_enabled": AI_ENABLED,
            "ctx_auth_required": settings.require_auth or bool(settings.api_keys),
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host=settings.host, port=settings.port, reload=True)

