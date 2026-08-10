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

import asyncio
import json
import os
import re
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
from core.ai_validator import AI_ENABLED
from core.ai_validator import MODEL as AI_MODEL
from core.dimensional import validate as dimensional_validate
from core.dimensional.dimensions import ALL_DIMENSION_KEYS, dimension_display_name
from core.dimensional.engine import KNOWN_IMPOSSIBLE, openrouter_llm_resolver
from core.dimensional.rules import SEMANTIC_BOUNDS
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
        "dimensional-analysis validation engine: units resolution, discovered "
        "physical laws, majority-corruption-proof anchored constants, and "
        "semantic/structural rules, plus optional LLM reasoning."
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
    unit_overrides: dict[str, str] | None = Field(
        default=None,
        description="Correct a wrong units mapping, e.g. {'v': 'volume'} if the engine guessed "
        "velocity. Re-run with this set after inspecting the units-resolved list in a prior response.",
    )


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


def _dimensional_stats(df: pd.DataFrame) -> dict[str, Any]:
    """Descriptive statistics per numeric column, in the same shape the
    legacy check-based engine's ``report.statistics`` produced."""
    stats: dict[str, Any] = {}
    for col in df.columns:
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(s) < 2:
            continue
        std = float(s.std())
        mean = float(s.mean())
        stats[col] = {
            "mean": mean, "std": std, "median": float(s.median()),
            "p5": float(s.quantile(0.05)), "p95": float(s.quantile(0.95)),
            "min": float(s.min()), "max": float(s.max()), "n": int(len(s)),
            "skewness": float(s.skew()) if len(s) > 2 else 0.0,
            "cv": float(std / mean) if mean else 0.0,
        }
    return stats


def _plain_language_summary(
    status: str, n_rows: int, trials_excluded: int, n_impossible: int, n_unsuitable: int,
    n_inconsistent: int, issues: list[dict], laws_confirmed: list[dict],
) -> str:
    """A 2-4 sentence, jargon-free explanation of what happened -- for
    someone who doesn't know what a Buckingham Pi group is. Built from the
    actual findings, not a generic template: names real column counts,
    real percentages, real confirmed laws."""
    parts: list[str] = []
    pct_excluded = round(100 * trials_excluded / n_rows, 1) if n_rows else 0.0

    if status == "passed":
        parts.append(f"All {n_rows:,} rows passed. No physical inconsistencies were found.")
        if laws_confirmed:
            best = laws_confirmed[0]
            parts.append(
                f"The data is consistent with real physics -- for example, the columns "
                f"{', '.join(best['columns'])} correctly satisfy a known physical relationship."
            )
        parts.append("This dataset looks safe to use for training or analysis.")
    else:
        if n_impossible:
            parts.append(
                f"{n_impossible} of {n_rows:,} rows ({round(100*n_impossible/n_rows,1)}%) contain values "
                f"that are mathematically impossible given the laws of physics -- not just unusual, "
                f"but definitively wrong (e.g. they contradict a known physical constant)."
            )
        if n_unsuitable:
            parts.append(
                f"{n_unsuitable} row(s) are physically valid but shouldn't be used for training "
                f"(duplicates or redundant data that would bias a model without adding information)."
            )
        if n_inconsistent:
            parts.append(
                f"{n_inconsistent} row(s) look statistically unusual compared to the rest of your data. "
                f"These aren't proven wrong, but are worth a human double-checking before you trust them."
            )
        if trials_excluded:
            parts.append(f"Recommended: exclude the {trials_excluded} flagged row(s) ({pct_excluded}% of the data) before training.")
        else:
            parts.append("Nothing needs to be auto-excluded, but review the warnings below before training.")
    return " ".join(parts)


def _concrete_fixes(issues: list[dict], n_rows: int) -> list[str]:
    """Specific, actionable next steps derived from the actual issues found
    -- not generic advice. Pulls the counterfactual-repair factor when one
    was computed (e.g. 'multiplying by 1000 would fix this'), which is
    proof, not a guess: the code actually re-checked the law after applying
    that factor."""
    fixes: list[str] = []
    seen_categories: set[str] = set()
    for issue in issues:
        cat = issue.get("category")
        detail = issue.get("detail", "")
        if cat in ("anchored_constant", "pi_constant", "systematic_anchor_deviation") and cat not in seen_categories:
            seen_categories.add(cat)
            fixes.append(
                f"Check the columns in \"{issue.get('description', '')}\" for a unit or scale error -- "
                f"{detail.split('(')[0].strip()}"
            )
        elif cat == "semantic_bounds" and "semantic_bounds" not in seen_categories:
            seen_categories.add("semantic_bounds")
            fixes.append(
                f"\"{issue.get('description', '')}\" violates a hard physical limit (e.g. a fraction "
                f"outside [0,1]) -- this is a data-entry or pipeline bug, not noise. Trace it to its source."
            )
        elif cat == "structural" and "structural" not in seen_categories:
            seen_categories.add("structural")
            fixes.append(f"Fix data hygiene: {detail}")
        elif cat == "declared_conditions" and "declared_conditions" not in seen_categories:
            seen_categories.add("declared_conditions")
            fixes.append(
                f"Your declared test conditions don't match what the data implies ({detail.split('(')[0].strip()}) "
                f"-- double-check the conditions you entered, or the data may be from a different run."
            )
        elif cat == "units" and "units" not in seen_categories:
            seen_categories.add("units")
            fixes.append(f"{detail} -- verify this column's units are what you think they are.")
    if not fixes:
        fixes.append("No specific fixes needed -- the dataset passed every check.")
    return fixes


def _stats_plain_language(stats: dict[str, Any]) -> list[str]:
    """One plain-English sentence per column -- range, average, and a
    variability note -- instead of raw mean/std/skew/cv numbers."""
    lines: list[str] = []
    for col, s in stats.items():
        cv = s.get("cv", 0)
        if cv < 0.02:
            variability = "barely varies across rows (nearly constant)"
        elif cv < 0.15:
            variability = "varies a normal amount"
        elif cv < 0.5:
            variability = "varies quite a bit"
        else:
            variability = "varies enormously (spans multiple orders of magnitude, or has outliers)"
        lines.append(
            f"{col}: ranges from {s['min']:.4g} to {s['max']:.4g}, averaging {s['mean']:.4g} "
            f"across {s['n']} rows -- {variability}."
        )
    return lines


def _serialize_dimensional(report, df: pd.DataFrame, job_id: str, processing_ms: float) -> dict[str, Any]:
    """Map a `core.dimensional.ValidationReport` onto the public response
    schema previously produced by the check-based `PhysicsValidator`
    (`_serialize`, above). This is what makes the dimensional-analysis
    engine a drop-in replacement: the CLI (sdk-node) and the web dashboard
    both consume this exact shape and neither needs to change.

    Class -> field mapping:
      * impossible              -> always excluded (never suppressible; "re-run these trials")
      * unsuitable_for_training -> excluded from the training-ready set (physically valid,
                                    harmful to learn from), but NOT a re-run recommendation
      * inconsistent            -> surfaced as an `issue` (human review), row stays included

    Training-suitability findings (design-space gaps, extrapolation risk, ...)
    are deliberately NOT folded into `issues`/`status`/`warnings`: the spec is
    explicit that these are dataset-level informational notes, not row or
    dataset defects -- "your data never covers the high-AoA regime" is worth
    reporting, but it should not make a physically clean dataset show up as
    `status: "warning"`. They're reported separately as `training_suitability`.

    Confirmed (non-violated) laws, semantic-bound checks, structural checks
    and condition assertions all count toward `passed` -- a validator that
    only ever reports what's wrong shows "0 passed" on a perfectly clean
    dataset, which reads as "did nothing" rather than "verified N things".
    """
    impossible = sorted(report.impossible_rows)
    inconsistent = sorted(report.inconsistent_rows)
    unsuitable = sorted(report.unsuitable_rows)
    excluded_rows = sorted(set(impossible) | set(unsuitable))

    findings_by_row = {f.row_id: f for f in report.row_findings}
    exclusions: list[dict[str, Any]] = []
    for rid in excluded_rows:
        f = findings_by_row.get(rid)
        severity = "critical" if rid in report.impossible_rows else "warning"
        exclusions.append({
            "trial_index": rid,
            "reason": f.reason if f else "excluded",
            "severity": severity,
        })

    issues: list[dict[str, Any]] = []
    laws_confirmed: list[dict[str, Any]] = []

    laws_passed = 0
    for law in report.laws:
        if not law.violated_rows:
            laws_passed += 1
            laws_confirmed.append({
                "kind": law.kind, "label": law.label, "columns": list(law.columns),
                "expected_value": law.expected_value, "coverage": round(law.coverage, 3),
            })
            continue
        status = "failed" if law.kind == "anchored_constant" else "warning"
        human_name_by_kind = {
            "anchored_constant": f"Violates a known physical constant ({law.label.split('=')[-1].strip()})",
            "pi_constant": "Breaks a physical law discovered in this dataset",
            "bimodal_split": "Data splits into two inconsistent unit conventions",
            "temporal_drift": "Value drifts progressively over time",
            "systematic_anchor_deviation": f"Entire dataset is offset from a known physical constant "
                                           f"({law.label.split('=')[-1].strip()})",
        }
        issues.append({
            "name": f"{law.kind}:{law.label}",
            "human_name": human_name_by_kind.get(law.kind, law.label),
            "status": status,
            "description": law.label,
            "detail": f"{law.note} ({len(law.violated_rows)} row(s) affected, "
                      f"coverage {law.coverage:.0%}).",
            "value": law.expected_value,
            "category": law.kind,
        })

    for sv in report.semantic_violations:
        issues.append({
            "name": f"semantic_bounds:{sv.column}",
            "human_name": f"\"{sv.column}\" is outside its physically valid range",
            "status": "failed",
            "description": f"{sv.column} {sv.rule}",
            "detail": f"{len(sv.row_ids)} row(s) violate a definitional bound on {sv.column}.",
            "value": sv.values[0] if sv.values else None,
            "category": "semantic_bounds",
        })
    # Every column matched against a semantic-bound pattern, whether or not
    # it was violated, so a clean run shows those checks as passed rather
    # than simply absent.
    semantic_violated_cols = {sv.column for sv in report.semantic_violations}
    semantic_checked_cols = set()
    for col in df.columns:
        for pattern, *_rest in SEMANTIC_BOUNDS:
            if re.search(pattern, str(col), re.IGNORECASE):
                semantic_checked_cols.add(col)
                break
    semantic_passed = len(semantic_checked_cols - semantic_violated_cols)

    structural_human_names = {
        "non_finite": "Contains NaN or infinite values",
        "exact_duplicate": "Contains exact duplicate rows",
        "near_duplicate": "Contains near-duplicate rows (disguised with tiny noise)",
    }
    for sf in report.structural_findings:
        issues.append({
            "name": f"structural:{sf.kind}",
            "human_name": structural_human_names.get(sf.kind, sf.kind.replace("_", " ").capitalize()),
            "status": "failed" if sf.kind == "non_finite" else "warning",
            "description": sf.kind.replace("_", " "),
            "detail": f"{sf.detail} ({len(sf.row_ids)} row(s)).",
            "value": None,
            "category": "structural",
        })
    # Structural is always exactly 2 dataset-wide checks (non-finite scan,
    # exact-duplicate scan); whichever didn't produce a finding passed.
    structural_kinds_found = {sf.kind for sf in report.structural_findings}
    structural_checked = 2
    structural_passed = structural_checked - len(structural_kinds_found & {"non_finite", "exact_duplicate"})

    for uc in report.units_conflicts:
        issues.append({
            "name": f"units_conflict:{uc.column}",
            "human_name": f"Units conflict on \"{uc.column}\"",
            "status": "warning",
            "description": f"Units conflict on {uc.column}",
            "detail": uc.note,
            "value": None,
            "category": "units",
        })

    condition_passed = 0
    for ca in report.condition_assertions:
        if ca.rel_dev > 0.02:  # meaningfully off, not just floating-point noise
            issues.append({
                "name": f"declared_conditions:{ca.label}",
                "human_name": f"Declared \"{ca.label}\" doesn't match what the data implies",
                "status": "warning" if ca.rel_dev < 0.10 else "failed",
                "description": f"Declared {ca.label} disagrees with what the data implies",
                "detail": f"declared={ca.declared:.4g}, implied={ca.implied:.4g} "
                          f"({ca.rel_dev:.1%} relative deviation).",
                "value": ca.implied,
                "category": "declared_conditions",
            })
        else:
            condition_passed += 1

    training_suitability = [
        {"kind": st.kind, "detail": st.detail, "columns": list(st.columns),
         "row_ids": st.row_ids, "severity": st.severity}
        for st in report.suitability
    ]

    failed_count = sum(1 for i in issues if i["status"] == "failed")
    warning_count = sum(1 for i in issues if i["status"] == "warning")
    passed_count = laws_passed + semantic_passed + structural_passed + condition_passed
    all_checks = passed_count + failed_count + warning_count
    all_checks = max(all_checks, 1)

    checks_by_category: dict[str, dict[str, int]] = {}
    for i in issues:
        c = checks_by_category.setdefault(i["category"], {"passed": 0, "warning": 0, "failed": 0})
        c[i["status"]] += 1
    if laws_passed:
        checks_by_category.setdefault("laws", {"passed": 0, "warning": 0, "failed": 0})["passed"] += laws_passed
    if semantic_passed:
        checks_by_category.setdefault("semantic_bounds", {"passed": 0, "warning": 0, "failed": 0})["passed"] += semantic_passed
    if structural_passed:
        checks_by_category.setdefault("structural", {"passed": 0, "warning": 0, "failed": 0})["passed"] += structural_passed
    if condition_passed:
        checks_by_category.setdefault("declared_conditions", {"passed": 0, "warning": 0, "failed": 0})["passed"] += condition_passed

    n_rows = report.n_rows
    trials_excluded = len(excluded_rows)
    trials_valid = n_rows - trials_excluded
    # Status is driven by real findings only -- impossible rows, inconsistent
    # rows, unsuitable-for-training rows, and issue-level failed/warning
    # counts. Training-suitability notes never move status: a hull-edge or
    # sparse-sampling note is true of nearly any finite dataset and is not a
    # correctness defect.
    if impossible or failed_count:
        status = "failed"
    elif inconsistent or unsuitable or warning_count:
        status = "warning"
    else:
        status = "passed"

    usable_cols = [u for u in report.units.columns.values() if u.usable]
    avg_conf = (sum(u.confidence for u in usable_cols) / len(usable_cols)) if usable_cols else 0.5
    confidence = "high" if avg_conf >= 0.75 else "medium" if avg_conf >= 0.5 else "low"

    renamed = df.attrs.get("simapi_renamed", {})
    plain_summary = _plain_language_summary(
        status, n_rows, trials_excluded, len(impossible), len(unsuitable), len(inconsistent),
        issues, laws_confirmed)
    concrete_fixes = _concrete_fixes(issues, n_rows)
    stats = _dimensional_stats(df)

    return _json_safe({
        "job_id": job_id,
        "status": status,
        "confidence": confidence,
        "plain_summary": plain_summary,
        "concrete_fixes": concrete_fixes,
        "trials_submitted": n_rows,
        "trials_valid": trials_valid,
        "trials_excluded": trials_excluded,
        "exclusion_rate": round(trials_excluded / n_rows, 4) if n_rows else 0.0,
        "training_ready": len(report.impossible_rows) == 0,
        "processing_ms": processing_ms,
        "all_checks": all_checks,
        "unique_checks": all_checks,
        "passed": passed_count,
        "warnings": warning_count,
        "failed": failed_count,
        "issues": issues,
        "physics_checks": issues,
        "exclusions": exclusions,
        "statistics": stats,
        "statistics_plain": _stats_plain_language(stats),
        "checks_by_category": checks_by_category,
        "laws_confirmed": laws_confirmed,
        "training_suitability": training_suitability,
        "provenance": {
            "engine": "dimensional-analysis",
            "engine_version": "1.0",
            "n_laws_discovered": len(report.laws),
            "n_laws_confirmed": laws_passed,
            "n_anchored_constants": sum(1 for law in report.laws if law.kind == "anchored_constant"),
            "n_pi_groups": len(report.pi_groups),
            "units_resolved": {c: {"confidence": round(u.confidence, 2), "source": u.source,
                                    "mapped_to": dimension_display_name(u.dimension)}
                               for c, u in report.units.columns.items()},
            "available_dimension_keys": ALL_DIMENSION_KEYS,
            "suppressions": list(report.suppressions),
            "inconsistent_rows": inconsistent,
            "unsuitable_for_training_rows": unsuitable,
            "known_impossible": KNOWN_IMPOSSIBLE,
        },
        "columns_renamed": renamed,
        "ai": None,
        "ai_status": "pending",
        "ai_exclusions": [],
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
        with _JOBS_LOCK:
            apie_result = JOBS.get(job_id, {}).get("apie_result")
        if apie_result and hasattr(apie_result, "diagnosis") and apie_result.diagnosis:
            pass

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

    # ── Primary engine: dimensional analysis (core/dimensional/) ───────────
    # Replaces the old hand-written-check engine (PhysicsValidator, ~470-885
    # per-column checks + suppression rules that never converged) as the
    # source of truth for status/exclusions/issues. Both the CLI (sdk-node)
    # and the web dashboard talk to this same /v1/validate response shape,
    # so routing this engine here is what makes it apply to both surfaces.
    #
    # Offloaded to a thread: this is CPU-bound (numpy/pandas), and running
    # it synchronously in the event loop blocks ALL request handling --
    # including unrelated /v1/health calls -- for the full duration of every
    # validate call, fully serializing concurrent traffic on a single
    # worker. numpy releases the GIL during most of its C-level work, so
    # this yields real concurrency even from one process, not just
    # non-blocking I/O interleaving.
    _t0 = time.perf_counter()
    dim_report = await asyncio.to_thread(
        dimensional_validate, df, conditions=req.conditions, llm_resolver=openrouter_llm_resolver,
        unit_overrides=req.unit_overrides)
    _dim_ms = round((time.perf_counter() - _t0) * 1000, 1)
    result = _serialize_dimensional(dim_report, df, jid, _dim_ms)

    # Legacy check-based engine kept available, non-authoritative: its
    # findings are exposed under `legacy_physics` for comparison/migration
    # only. It no longer drives status, exclusions, or training_ready.
    try:
        physics = await asyncio.to_thread(validator.validate, df, req.simulation_type, req.conditions, jid)
        legacy = _serialize(physics, df)
        result["legacy_physics"] = {
            "status": legacy["status"],
            "trials_excluded": legacy["trials_excluded"],
            "all_checks": legacy["all_checks"],
            "issues": legacy["issues"][:20],
        }
    except Exception:
        pass

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
        "engine": "dimensional-analysis",
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


@app.post("/v1/validate/dimensional", tags=["validation"])
async def validate_dimensional(req: ValidateRequest, _: str = Depends(caller_identity)):
    """
    Dimensional-analysis validation engine (core/dimensional/).

    Replaces hand-written per-column checks with column-name -> SI-dimension
    resolution, dimensionless (Pi) group discovery, ~30 shipped physical
    constants as majority-corruption-proof anchors, bimodal-split detection,
    a Pi-space response-surface residual layer, semantic bounds, and
    declared-conditions assertions. See core/dimensional/engine.py.

    This exposes the SAME dimensional-analysis engine that now powers
    /v1/validate, but returns the raw per-layer report (discovered laws,
    units resolution, condition assertions, training-suitability, etc.)
    instead of summarizing it into the CLI/SDK-compatible shape. Use this
    when you want the full detail; use /v1/validate for the standard,
    backward-compatible report.
    """
    df, ingest_meta = ingester.ingest(req.data, format_hint="json")
    conditions_dict = dict(req.conditions or {})
    report = await asyncio.to_thread(
        dimensional_validate, df, conditions=conditions_dict, llm_resolver=openrouter_llm_resolver,
        unit_overrides=req.unit_overrides)

    def _row_finding_dict(f):
        return {
            "row_index": f.row_id,
            "output_class": f.output_class,
            "reason": f.reason,
            "layer": f.layer,
            "weight": round(f.weight, 3),
            "factor": f.factor,
            "counterfactual_repair": f.counterfactual,
        }

    def _law_dict(law):
        return {
            "kind": law.kind,
            "label": law.label,
            "columns": list(law.columns),
            "expected_value": law.expected_value,
            "observed_median": law.observed_median,
            "coverage": round(law.coverage, 3),
            "weight": round(law.weight, 3),
            "n_violations": len(law.violated_rows),
            "note": law.note,
            # Per-row shared-factor cluster info -- when >=3 violated rows
            # share the same factor, this names the unit conversion instead
            # of leaving the caller to piece it together from N isolated rows.
            "row_clusters": getattr(law, "row_clusters", {}) or {},
        }

    return _json_safe({
        "job_id": req.job_id or uuid.uuid4().hex[:8],
        "n_rows": report.n_rows,
        "impossible": sorted(report.impossible_rows),
        "inconsistent": sorted(report.inconsistent_rows),
        "unsuitable_for_training": sorted(report.unsuitable_rows),
        "n_impossible": len(report.impossible_rows),
        "n_inconsistent": len(report.inconsistent_rows),
        "n_unsuitable_for_training": len(report.unsuitable_rows),
        "training_ready": len(report.impossible_rows) == 0,
        "laws_discovered": [_law_dict(law) for law in report.laws],
        "n_anchored_constants": sum(1 for law in report.laws if law.kind == "anchored_constant"),
        "row_findings": [_row_finding_dict(f) for f in report.row_findings],
        "units_resolved": {
            c: {
                "confidence": round(u.confidence, 2), "source": u.source,
                "usable": u.usable, "unit_label": u.unit_label,
                "mapped_to": dimension_display_name(u.dimension),
            }
            for c, u in report.units.columns.items()
        },
        "available_dimension_keys": ALL_DIMENSION_KEYS,
        "units_conflicts": [c.__dict__ for c in report.units_conflicts],
        "condition_assertions": [
            {"label": a.label, "declared": a.declared, "implied": a.implied,
             "rel_dev": round(a.rel_dev, 4), "columns": list(a.columns), "row_ids": a.row_ids}
            for a in report.condition_assertions
        ],
        # Dataset-level, deliberately NOT folded into the row lists above:
        # "your data never covers the high-AoA regime you deploy in" is not a
        # defect of any row, and reporting it as one would be misleading.
        "training_suitability": [
            {"kind": s.kind, "detail": s.detail, "columns": list(s.columns),
             "row_ids": s.row_ids, "severity": s.severity}
            for s in report.suitability
        ],
        # Every suppression carries its reason: a validator that hides what it
        # chose not to run cannot be audited.
        "suppressions": list(report.suppressions),
        "known_impossible": KNOWN_IMPOSSIBLE,
        "columns_renamed": ingest_meta.get("columns_renamed", {}),
    })


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
        temperature = float(288.15 + np.random.normal(0, 2.0))
        density = float(rho + np.random.normal(0, 0.01))
        # Pressure is DERIVED from the ideal-gas law (P = rho*R_air*T), not
        # generated as an independent noise source -- three independently
        # noisy quantities that "happen to look like" P=rhoRT is exactly
        # the self-inconsistency the dimensional engine's R_air anchor is
        # designed to (correctly) flag. A real sensor's P, rho and T are
        # physically coupled; this dataset should be too.
        pressure = float(density * 287.05 * temperature + np.random.normal(0, 15))
        data.append({
            "drag_coefficient": float(cd),
            "lift_coefficient": float(cl),
            "reynolds_number": float(reynolds),  # Exact relationship
            "pressure": pressure,
            "velocity": float(v_var),
            "mach_number": float(mach),  # Exact relationship
            "angle_of_attack": float(4.0 + np.random.normal(0, 1.0)),
            "temperature": temperature,
            "density": density,
            "viscosity": float(mu + np.random.normal(0, 1e-7)),
            "skin_friction_coefficient": float(0.004 + np.random.normal(0, 0.0003)),
            "turbulence_intensity": float(0.03 + np.random.normal(0, 0.004)),
            "pitching_moment": float(-0.05 + np.random.normal(0, 0.005)),
            "side_force_coefficient": float(0.02 + np.random.normal(0, 0.003)),
            "rolling_moment": float(0.01 + np.random.normal(0, 0.002)),
            "wall_shear_stress": float(0.8 + np.random.normal(0, 0.05)),
            "vibration_frequency": float(120.0 + np.random.normal(0, 3.0)),
            "boundary_layer_thickness": float(0.012 + np.random.normal(0, 0.0006)),
            "heat_transfer_coefficient": float(25.0 + np.random.normal(0, 1.5)),
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

