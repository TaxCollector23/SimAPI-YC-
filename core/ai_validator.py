"""
SimAPI — AI Validation Layer v2.3 [SIMAPI-DIAG-WIRED + MULTI-KEY FALLBACK-CHAIN]

Physics engine diagnosis is passed directly into the prompt.
The AI layer elaborates on confirmed findings — it does not generate its own.

A single free-tier model on OpenRouter can hit its daily quota (429) or return
blank content independent of anything wrong in this codebase. `MODEL_CHAIN`
routes around that by trying several independent (key, model) pairs across up
to two OpenRouter accounts before giving up, so a 429/expired-key/deprecated
model on one combination degrades to a slower answer instead of
"AI layer unavailable."
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

OPENROUTER_API_KEY   = os.environ.get("SIMAPI_OPENROUTER_API_KEY", "")
OPENROUTER_API_KEY_2 = os.environ.get("SIMAPI_OPENROUTER_API_KEY_2", "")
OPENROUTER_URL       = os.environ.get("SIMAPI_OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions")
QUICK_MODEL          = os.environ.get("SIMAPI_AI_QUICK_MODEL", "nvidia/nemotron-nano-9b-v2:free")
MODEL                = QUICK_MODEL
TIMEOUT_SECONDS      = int(os.environ.get("SIMAPI_AI_QUICK_TIMEOUT_SECONDS", "18"))
TOKENS_SHORT = 700
TOKENS_LONG  = 3000
AI_ENABLED = bool(OPENROUTER_API_KEY or OPENROUTER_API_KEY_2)

# Fallback chain of (key, model) pairs. Two independent OpenRouter keys, each
# tried against its own set of models — a bad/expired/rate-limited key on one
# combination falls through to the next key+model, not just the next model on
# the same key. Verified against GET https://openrouter.ai/api/v1/models —
# OpenRouter's free catalog changes over time and stale slugs 404 rather than
# falling through, so this list must be checked periodically, not assumed.
_KEY_MODEL_CHAIN: list[tuple[str, str]] = []
if OPENROUTER_API_KEY:
    _KEY_MODEL_CHAIN += [
        (OPENROUTER_API_KEY, QUICK_MODEL),
        (OPENROUTER_API_KEY, "google/gemma-4-31b-it:free"),
        (OPENROUTER_API_KEY, "nvidia/nemotron-3-nano-30b-a3b:free"),
    ]
if OPENROUTER_API_KEY_2:
    _KEY_MODEL_CHAIN += [
        (OPENROUTER_API_KEY_2, "openai/gpt-oss-20b:free"),
        (OPENROUTER_API_KEY_2, "google/gemma-4-26b-a4b-it:free"),
        (OPENROUTER_API_KEY_2, "nvidia/nemotron-3-super-120b-a12b:free"),
    ]
if not _KEY_MODEL_CHAIN and OPENROUTER_API_KEY:
    _KEY_MODEL_CHAIN = [(OPENROUTER_API_KEY, QUICK_MODEL)]
KEY_MODEL_CHAIN = list(dict.fromkeys(_KEY_MODEL_CHAIN))  # de-dup, preserve order
MODEL_CHAIN = list(dict.fromkeys(m for _, m in KEY_MODEL_CHAIN))  # for logging/back-compat

# Only these models accept/benefit from the `reasoning` param (hidden
# chain-of-thought token budget). Sending it to a non-reasoning model causes
# it to return blank content instead of an answer.
_REASONING_MODEL_PATTERNS = ("nemotron", "gpt-oss")


def _uses_reasoning_param(model: str) -> bool:
    m = model.lower()
    return any(p in m for p in _REASONING_MODEL_PATTERNS)


class _RetryableError(Exception):
    """Raised for 429/5xx/empty-content/unparseable responses — try the next model."""


# Version marker — confirms this file is the updated version
_VALIDATOR_VERSION = "2.3-domain-expert-prompts"


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


# Domain-specific expertise cues — steers the model toward the right causal
# vocabulary for each field instead of generic "the data looks off" answers.
_DOMAIN_EXPERTISE = {
    "aerodynamics": "CFD post-processing: unit slips (Pa/kPa, deg/rad), Mach/Reynolds "
        "consistency, stall-region CL behavior, mesh y+ sensitivity, solver residual convergence.",
    "fluid_dynamics": "CFD/FVM solvers: courant number instability, turbulence model mismatch, "
        "boundary-layer resolution, pressure-velocity coupling divergence.",
    "structural": "FEA: stress-strain consistency (Hooke's law), mesh refinement artifacts, "
        "boundary condition under-constraint, unit mismatches (MPa vs Pa), element locking.",
    "thermodynamics": "Heat transfer: energy balance violations, unit errors (K vs °C), "
        "material property lookup errors, steady-state vs transient solver settings.",
    "robotics": "Control/kinematics: joint-limit violations, actuator saturation, sensor noise vs "
        "drift, coordinate-frame mismatches, timestep-dependent integration error.",
    "combustion": "Reacting flow: species conservation, flame-speed unit errors, ignition-delay "
        "outliers, chemistry-mechanism solver stiffness.",
    "electromagnetics": "EM solvers: mesh discretization at skin depth, unit errors (permittivity/"
        "permeability), boundary condition (PML) reflection artifacts.",
}


def _quick_summary(data: pd.DataFrame, physics_issues: list[dict]) -> dict:
    nc = list(data.select_dtypes(include=[np.number]).columns)
    n = len(data)
    failed = [i for i in physics_issues if i.get("status") == "failed"]
    warned = [i for i in physics_issues if i.get("status") == "warning"]

    def _fmt(i: dict) -> str:
        name = i.get("name", "")
        detail = i.get("detail") or i.get("description") or ""
        val = i.get("value")
        cat = i.get("category", "")
        val_str = f", value={val}" if val is not None else ""
        return f"{name} [{cat}]: {detail}{val_str}"

    return {
        "trials": n,
        "columns": len(nc),
        "column_names": nc[:15],
        "failed_checks": [_fmt(i) for i in failed[:10]],
        "warning_checks": [_fmt(i) for i in warned[:6]],
    }


def _build_prompt(data: pd.DataFrame, sim_type: str, conditions: dict,
                  physics_issues: list[dict],
                  diagnosis_context: dict | None = None) -> str:
    """
    Build the AI prompt. When diagnosis_context is provided (the normal path),
    the prompt leads with the confirmed physics engine diagnosis and asks the
    AI to elaborate specifically — not to generate its own independent finding.

    Feeds the model actual check details and values (not just check names),
    plus domain-specific causal vocabulary, so the answer names concrete
    fields and mechanisms instead of generic "data looks anomalous" filler.
    """
    summary = _quick_summary(data, physics_issues)
    expertise = _DOMAIN_EXPERTISE.get(sim_type, "engineering simulation post-processing")

    if diagnosis_context and diagnosis_context.get("primary_finding"):
        dx = diagnosis_context
        causal = " → ".join((dx.get("causal_chain") or [])[:4])
        steps = (dx.get("investigation_steps") or ["No steps available"])[:2]
        pipeline = dx.get("pipeline_stage", "unknown").replace("_", " ")
        confidence = int((dx.get("confidence") or 0) * 100)

        return f"""You are a senior {sim_type} simulation engineer with deep expertise in: {expertise}

The deterministic physics engine has already validated {summary['trials']} trials across {summary['columns']} columns ({', '.join(summary['column_names']) or 'n/a'}) and produced a confirmed diagnosis below. Your job is to explain it precisely to another engineer — not invent a new diagnosis, and not restate generic statistics language.

CONFIRMED PHYSICS ENGINE DIAGNOSIS:
Finding: {dx['primary_finding']}
Pipeline stage: {pipeline}
Confidence: {confidence}%
Causal chain: {causal}
Investigation steps already identified: {'; '.join(steps)}

FAILED CHECKS (name, category, exact value):
{chr(10).join(summary['failed_checks']) or 'none'}

WARNING CHECKS:
{chr(10).join(summary['warning_checks']) or 'none'}

Write 3-4 sentences: (1) what specifically went wrong, naming the exact field/value from the checks above, (2) the most likely root-cause mechanism given your domain expertise (e.g. a specific unit conversion, a specific solver setting, a specific sensor failure mode — not "data quality issue"), (3) one concrete, specific first thing to check that isn't already in the investigation steps above.

Respond ONLY with this JSON, no other text:
{{"verdict": "not normal", "reason": "3-4 specific sentences per the instructions above", "anomaly_score": 0.8, "recommendation": "one concrete actionable step, naming a specific file/parameter/column to check"}}"""

    # Fallback: no diagnosis context available
    return f"""You are a senior {sim_type} simulation engineer with deep expertise in: {expertise}

You are sanity-checking a dataset of {summary['trials']} trials across {summary['columns']} columns ({', '.join(summary['column_names']) or 'n/a'}).

FAILED CHECKS (name, category, exact value):
{chr(10).join(summary['failed_checks']) or 'none'}

WARNING CHECKS:
{chr(10).join(summary['warning_checks']) or 'none'}

Conditions: {json.dumps(conditions)}

Is this dataset physically normal or not? If not, name the specific field and value that's wrong and the most likely root-cause mechanism from your domain expertise — not a generic "statistical anomaly" answer.

Respond ONLY with this JSON, no other text:
{{"verdict": "normal" | "not normal", "reason": "1-2 specific sentences naming the actual failed check, its value, and the likely mechanism", "anomaly_score": 0.0}}

anomaly_score: 0.0=clean, 1.0=seriously corrupted."""


def _call_api(prompt: str, max_tokens: int, model: str, key: str, timeout: int) -> tuple:
    body = {
        "model": model, "max_tokens": max_tokens, "temperature": 0.1,
        "messages": [{"role": "user", "content": prompt}],
    }
    if _uses_reasoning_param(model):
        body["reasoning"] = {"exclude": True, "max_tokens": min(250, max_tokens // 2)}
    payload = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(
        OPENROUTER_URL, data=payload,
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json",
                 "HTTP-Referer": "https://simapi.dev",
                 "X-Title": "SimAPI"},
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code in (401, 404, 429, 500, 502, 503, 504):
            # 401 = this specific key is invalid/revoked (try the other key);
            # 404 = model slug deprecated/renamed on OpenRouter's end (try the
            # next model) — neither is a request error on our side.
            raise _RetryableError(f"HTTP {e.code} from {model}") from e
        raise
    return raw, (time.time() - t0) * 1000


def _extract_json_object(text: str) -> dict | None:
    """Brace-match the first JSON object in text, for models that wrap it in prose."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _parse(raw: str) -> dict:
    data = json.loads(raw)
    content = data["choices"][0]["message"].get("content")
    if not content:
        raise _RetryableError("Model returned no content (token budget exhausted on hidden reasoning)")
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        end = -1 if lines[-1].strip() in ("```", "```json") else len(lines)
        content = "\n".join(lines[1:end])
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        parsed = _extract_json_object(content)
        if parsed is None:
            raise _RetryableError("Model returned unparseable content") from None
        return parsed


_FALLBACK_BUDGET_SECONDS = float(os.environ.get("SIMAPI_AI_FALLBACK_BUDGET_SECONDS", "40"))


def _call_with_fallback(prompt: str, max_tokens: int = TOKENS_SHORT,
                        timeout: int = TIMEOUT_SECONDS) -> tuple[dict, str]:
    """Try each (key, model) pair in KEY_MODEL_CHAIN, widening the token budget
    once per pair before moving on. Returns (parsed_json, model_used). Raises
    the last error if every pair fails, or if a shared wall-clock budget runs
    out — a hung model can't eat into every other pair's chance to answer."""
    last_err: Exception | None = None
    deadline = time.time() + _FALLBACK_BUDGET_SECONDS
    for max_tok in (max_tokens, max_tokens * 2):
        for key, model in KEY_MODEL_CHAIN:
            remaining = deadline - time.time()
            if remaining <= 0.5:
                raise last_err or RuntimeError("AI fallback chain: time budget exhausted")
            try:
                raw, _ = _call_api(prompt, max_tok, model, key, min(timeout, remaining))
                return _parse(raw), model
            except _RetryableError as e:
                last_err = e
                continue
            except (ValueError, KeyError) as e:
                last_err = e
                continue
    raise last_err or RuntimeError("AI fallback chain exhausted with no error recorded")


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
            parsed, used_model = _call_with_fallback(prompt)

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
                model=used_model,
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
    thread.join(timeout=_FALLBACK_BUDGET_SECONDS + 5)

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
