"""
SimAPI — AI Validation Layer v2.1 [SIMAPI-DIAG-WIRED]

Physics engine diagnosis is passed directly into the prompt.
The AI layer elaborates on confirmed findings — it does not generate its own.
"""

import json
import os
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

OPENROUTER_API_KEY = os.environ.get("SIMAPI_OPENROUTER_API_KEY", "")
OPENROUTER_URL     = os.environ.get("SIMAPI_OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions")
QUICK_MODEL        = os.environ.get("SIMAPI_AI_QUICK_MODEL", "nvidia/nemotron-nano-9b-v2:free")
MODEL              = QUICK_MODEL
TIMEOUT_SECONDS    = int(os.environ.get("SIMAPI_AI_QUICK_TIMEOUT_SECONDS", "18"))
TOKENS_SHORT = 500
TOKENS_LONG  = 3000
AI_ENABLED = bool(OPENROUTER_API_KEY)

# Version marker — confirms this file is the updated version
_VALIDATOR_VERSION = "2.1-diag-wired"


@dataclass
class AIFinding:
    severity:   str
    category:   str
    title:      str
    detail:     str
    trials:     list[int] = field(default_factory=list)
    confidence: float = 0.7


@dataclass
class AIValidationReport:
    status:          str
    model:           str
    processing_ms:   float
    findings:        list[AIFinding]
    dataset_summary: str
    anomaly_score:   float
    recommendations: list[str]
    timed_out:       bool = False
    error:           str | None = None
    verdict:         str = ""


def _quick_summary(data: pd.DataFrame, physics_issues: list[dict]) -> dict:
    nc = list(data.select_dtypes(include=[np.number]).columns)
    n = len(data)
    failed = [i for i in physics_issues if i.get("status") == "failed"]
    warned = [i for i in physics_issues if i.get("status") == "warning"]
    return {
        "trials": n,
        "columns": len(nc),
        "failed_checks": [i.get("name", "") for i in failed[:8]],
        "warning_checks": [i.get("name", "") for i in warned[:8]],
    }


def _build_prompt(data: pd.DataFrame, sim_type: str, conditions: dict,
                  physics_issues: list[dict],
                  diagnosis_context: dict | None = None) -> str:
    """
    Build the AI prompt. When diagnosis_context is provided (the normal path),
    the prompt leads with the confirmed physics engine diagnosis and asks the
    AI to elaborate specifically — not to generate its own independent finding.
    """
    summary = _quick_summary(data, physics_issues)

    if diagnosis_context and diagnosis_context.get("primary_finding"):
        dx = diagnosis_context
        causal = " → ".join((dx.get("causal_chain") or [])[:3])
        step1 = (dx.get("investigation_steps") or ["No steps available"])[0]
        pipeline = dx.get("pipeline_stage", "unknown").replace("_", " ")
        confidence = int((dx.get("confidence") or 0) * 100)

        return f"""You are an expert simulation pipeline engineer reviewing a {sim_type} dataset.

The deterministic physics engine has already validated {summary['trials']} trials and produced a confirmed diagnosis. Your job is to translate this into a clear, specific explanation for the engineer — not to generate a new diagnosis.

CONFIRMED PHYSICS ENGINE DIAGNOSIS:
Finding: {dx['primary_finding']}
Pipeline stage: {pipeline}
Confidence: {confidence}%
Causal chain: {causal}
First investigation step: {step1}
Failed physics checks: {summary['failed_checks'] or 'none'}

Write a 2-3 sentence explanation of what went wrong, why it happened, and what the engineer should check first. Be specific — reference the actual finding, not generic advice.

Respond ONLY with this JSON, no other text:
{{"verdict": "not normal", "reason": "2-3 sentence specific explanation referencing the actual finding", "anomaly_score": 0.8, "recommendation": "one specific actionable step"}}"""

    # Fallback: no diagnosis context available
    return f"""You are sanity-checking a {sim_type} simulation dataset validated with {summary['trials']} trials.

Failed checks: {summary['failed_checks'] or 'none'}
Warning checks: {summary['warning_checks'] or 'none'}
Conditions: {json.dumps(conditions)}

Is this dataset normal or not? Be specific about what failed.

Respond ONLY with this JSON, no other text:
{{"verdict": "normal" | "not normal", "reason": "one specific sentence referencing the actual failed check", "anomaly_score": 0.0}}

anomaly_score: 0.0=clean, 1.0=seriously corrupted."""


def _call_api(prompt: str, max_tokens: int = TOKENS_SHORT,
              model: str = QUICK_MODEL, timeout: int = TIMEOUT_SECONDS) -> tuple:
    payload = json.dumps({
        "model": model, "max_tokens": max_tokens, "temperature": 0.1,
        "reasoning": {"exclude": True, "max_tokens": min(250, max_tokens // 2)},
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        OPENROUTER_URL, data=payload,
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}",
                 "Content-Type": "application/json",
                 "HTTP-Referer": "https://simapi.dev",
                 "X-Title": "SimAPI"},
        method="POST",
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    return raw, (time.time() - t0) * 1000


def _parse(raw: str) -> dict:
    data = json.loads(raw)
    content = data["choices"][0]["message"].get("content")
    if not content:
        raise ValueError("Model returned no content (token budget exhausted on hidden reasoning)")
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        end = -1 if lines[-1].strip() in ("```", "```json") else len(lines)
        content = "\n".join(lines[1:end])
    return json.loads(content)


def validate_with_ai(data: pd.DataFrame, simulation_type: str,
                     conditions: dict, physics_issues: list[dict],
                     diagnosis_context: dict | None = None) -> AIValidationReport:
    t0 = time.time()

    if not AI_ENABLED:
        return AIValidationReport(
            status="disabled", model=MODEL, processing_ms=0.0,
            findings=[], dataset_summary="AI validation disabled: no API key configured.",
            anomaly_score=0.0, recommendations=[], timed_out=False, error=None,
        )

    result = {"done": False, "report": None, "error": None}

    def _run():
        try:
            prompt = _build_prompt(data, simulation_type, conditions,
                                   physics_issues, diagnosis_context)
            try:
                raw, api_ms = _call_api(prompt)
                parsed = _parse(raw)
            except (ValueError, KeyError):
                raw, api_ms = _call_api(prompt, max_tokens=TOKENS_SHORT * 2)
                parsed = _parse(raw)

            is_normal = str(parsed.get("verdict", "")).strip().lower() == "normal"
            anomaly = float(parsed.get("anomaly_score", 0.1 if is_normal else 0.7))
            reason = str(parsed.get("reason", ""))
            recommendation = str(parsed.get("recommendation", ""))

            # If we had diagnosis context, use the physics engine finding as the title
            if diagnosis_context and diagnosis_context.get("primary_finding"):
                finding_title = diagnosis_context["primary_finding"]
            else:
                finding_title = "AI flagged this dataset"

            result["report"] = AIValidationReport(
                status="passed" if is_normal else ("failed" if anomaly > 0.6 else "warning"),
                verdict="Normal" if is_normal else "Not Normal",
                model=QUICK_MODEL,
                processing_ms=round((time.time() - t0) * 1000, 1),
                findings=[] if is_normal else [AIFinding(
                    severity="warning" if anomaly < 0.7 else "critical",
                    category="physics_diagnosis",
                    title=finding_title,
                    detail=reason,
                    trials=[],
                    confidence=round(1.0 - anomaly + 0.2, 2),
                )],
                dataset_summary=reason,
                anomaly_score=anomaly,
                recommendations=[recommendation] if recommendation else [],
                timed_out=False,
                error=None,
            )
        except Exception as e:
            result["error"] = str(e)
        finally:
            result["done"] = True

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    thread.join(timeout=TIMEOUT_SECONDS + 5)

    if not result["done"] or result["report"] is None:
        err = result.get("error") or "Request timed out"
        timed = not result["done"]
        return AIValidationReport(
            status="error", verdict="Unavailable", model=QUICK_MODEL,
            processing_ms=round((time.time() - t0) * 1000, 1),
            findings=[], dataset_summary="",
            anomaly_score=0.0, recommendations=[],
            timed_out=timed, error=err,
        )
    return result["report"]


def report_to_dict(report: AIValidationReport) -> dict:
    return {
        "status":          report.status,
        "verdict":         report.verdict,
        "model":           report.model,
        "processing_ms":   report.processing_ms,
        "anomaly_score":   report.anomaly_score,
        "dataset_summary": report.dataset_summary,
        "timed_out":       report.timed_out,
        "validator_version": _VALIDATOR_VERSION,  # marker: confirms updated version is live
        "findings": [{"severity": f.severity, "category": f.category, "title": f.title,
                      "detail": f.detail, "trials": f.trials, "confidence": f.confidence}
                     for f in report.findings],
        "recommendations": report.recommendations,
        "error": report.error,
    }
