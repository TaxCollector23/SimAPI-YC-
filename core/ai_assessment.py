"""
SimAPI — AI Assessment Module v2.0
Math-to-Text Contextual Translation Pipeline

Architecture:
  1. Compute-First Orchestration — deterministic engine runs first
  2. Hyper-lean prompt injection — only high-value error logs reach the LLM
  3. Expert Physics Debugger persona — eliminates statistical hallucinations

Public interface:
    result = generate_ai_assessment(validation_report)
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

OPENROUTER_API_KEY = os.environ.get("SIMAPI_OPENROUTER_API_KEY", "")
OPENROUTER_URL = os.environ.get(
    "SIMAPI_OPENROUTER_URL",
    "https://openrouter.ai/api/v1/chat/completions"
)
AI_MODEL = os.environ.get("SIMAPI_AI_MODEL", "nvidia/nemotron-nano-9b-v2:free")
TIMEOUT_SECONDS = int(os.environ.get("SIMAPI_AI_TIMEOUT_SECONDS", "30"))
AI_ENABLED = bool(OPENROUTER_API_KEY)

_SYSTEM_PROMPT = """You are an expert Metrology and Physics QA Engineer. \
You will be provided with a structured mathematical anomaly report generated \
by a deterministic conservation engine.

Your sole objective is to translate these mathematical violations into a clear, \
actionable enterprise-grade root-cause diagnosis for simulation developers.

CRITICAL RULES:
- Do NOT analyze statistical column variance. High variance is expected in \
multi-state simulations.
- Rely strictly on the explicit physical invariants provided in the context matrix.
- If the report shows an invariant violation (e.g., a delta change in Reynolds \
vs Velocity), explain the physical mechanism behind why that specific scaling \
paradox occurs (e.g., fluid media shift, unit conversion mismatch, or a frozen \
solver state).
- Keep your output concise, professional, and directly aimed at helping an \
engineer debug their simulation pipeline.
- Respond ONLY with valid JSON in the format specified. No markdown, no preamble."""


def _build_lean_prompt(validation_report: dict) -> str:
    """
    Build a hyper-lean prompt: strip raw data, inject only the high-value
    mathematical error logs. Keeps token count minimal for edge-model inference.
    """
    profile = validation_report.get("profile_assigned", "UNKNOWN")
    invariants = validation_report.get("discovered_invariants", {})
    anomalies = validation_report.get("anomalies_detected", [])
    n_excluded = len(validation_report.get("excluded_indices", set()))

    # Collapse anomalies into a compact error matrix (max 15 entries)
    critical = [a for a in anomalies if a.get("severity") == "critical"][:8]
    warnings_ = [a for a in anomalies if a.get("severity") == "warning"][:7]
    top_anomalies = critical + warnings_

    error_matrix = []
    for a in top_anomalies:
        error_matrix.append({
            "row": a.get("row_index"),
            "eq": a.get("invariant_equation"),
            "delta": a.get("divergence_delta"),
            "sev": a.get("severity"),
        })

    context = {
        "domain_profile": profile,
        "discovered_invariants": {k: round(float(v), 4) for k, v in invariants.items()
                                   if isinstance(v, (int, float))},
        "total_anomalies": len(anomalies),
        "rows_excluded": n_excluded,
        "error_matrix": error_matrix,
    }

    user_message = (
        f"Mathematical anomaly report:\n{json.dumps(context, indent=2)}\n\n"
        "Provide your expert diagnosis as JSON:\n"
        '{"expert_assessment": "<concise root-cause diagnosis>", '
        '"primary_failure_mode": "<one of: unit_error|sensor_drift|solver_divergence|'
        'copy_paste|cross_variable|measurement_noise|clean>", '
        '"engineer_action": "<specific corrective step>", '
        '"confidence": <0.0-1.0>}'
    )

    return _SYSTEM_PROMPT + "\n\n" + user_message


def _call_llm(prompt: str) -> dict | None:
    if not AI_ENABLED:
        return None

    payload = json.dumps({
        "model": AI_MODEL,
        "max_tokens": 600,
        "temperature": 0.05,
        "reasoning": {"exclude": True},
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        OPENROUTER_URL, data=payload,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://simapi.dev",
            "X-Title": "SimAPI",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        content = raw["choices"][0]["message"].get("content", "").strip()
        if content.startswith("```"):
            lines = content.split("\n")
            end = -1 if lines[-1].strip().startswith("```") else len(lines)
            content = "\n".join(lines[1:end])
        return json.loads(content)
    except Exception as e:
        return {"error": str(e), "expert_assessment": "AI assessment unavailable."}


def generate_ai_assessment(validation_report: dict) -> dict:
    """
    Compute-first AI assessment.

    1. If dataset is 100% valid → lean structural summary to LLM for final sanity.
    2. If anomalies exist → inject exact mathematical failure logs into prompt.

    Returns the input report dict augmented with 'ai_assessment' key.
    """
    t0 = time.time()
    report = dict(validation_report)

    if not AI_ENABLED:
        report["ai_assessment"] = {
            "status": "disabled",
            "reason": "No SIMAPI_OPENROUTER_API_KEY configured.",
            "expert_assessment": None,
        }
        return report

    anomalies = report.get("anomalies_detected", [])
    is_valid = report.get("is_valid", True)

    if is_valid and not anomalies:
        # Clean dataset: minimal confirmation prompt
        prompt = (
            _SYSTEM_PROMPT + "\n\n"
            "The deterministic conservation engine found NO anomalies in this "
            f"{report.get('profile_assigned', 'UNKNOWN')} simulation dataset. "
            f"Discovered invariants: {json.dumps(report.get('discovered_invariants', {}), default=str)}.\n\n"
            "Confirm dataset cleanliness or flag any structural concern:\n"
            '{"expert_assessment": "<brief confirmation>", '
            '"primary_failure_mode": "clean", '
            '"engineer_action": "None required.", '
            '"confidence": 0.95}'
        )
    else:
        prompt = _build_lean_prompt(report)

    llm_result = _call_llm(prompt)
    ms = round((time.time() - t0) * 1000, 1)

    if llm_result:
        report["ai_assessment"] = {
            "status": "completed",
            "model": AI_MODEL,
            "processing_ms": ms,
            "expert_assessment": llm_result.get(
                "expert_assessment", "Assessment not available."
            ),
            "primary_failure_mode": llm_result.get("primary_failure_mode", "unknown"),
            "engineer_action": llm_result.get("engineer_action", ""),
            "confidence": llm_result.get("confidence", 0.0),
            "error": llm_result.get("error"),
        }
    else:
        report["ai_assessment"] = {
            "status": "disabled",
            "processing_ms": ms,
            "expert_assessment": None,
        }

    return report
