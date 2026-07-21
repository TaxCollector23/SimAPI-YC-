"""
SimAPI — AI Validation Layer v2

This is the DEFAULT AI check that runs after every physics validation: a fast
sanity pass ("is this normal or not"), not a deep investigation. It uses a
small, non-reasoning-heavy free model and a strict timeout so it never
becomes the bottleneck in a validation request — the physics engine is the
source of truth; the AI layer is a second opinion, not a blocker.

For deep multi-phase root-cause analysis (5-phase pipeline, larger model,
longer budget), see core/ai_orchestrator.py — opt-in via `deep_ai: true` on
the validate request, not the default path.

Token budgets are deliberately different by purpose:
- TOKENS_SHORT: quick verdicts (CLI output, playground headline) — a few
  hundred tokens is enough for "normal" / "not normal" + one reason.
- TOKENS_LONG: detailed explanations (sim explain, deep orchestrator phases)
  — up to ~3000 tokens so a real diagnosis isn't truncated mid-sentence.
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

# Secrets and tunables are read from the environment. Never hardcode credentials.
# See .env.example for the full list of supported variables.
OPENROUTER_API_KEY = os.environ.get("SIMAPI_OPENROUTER_API_KEY", "")
OPENROUTER_URL     = os.environ.get("SIMAPI_OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions")

# The quick model prioritizes latency (< 20s) over depth — it's answering a
# single yes/no question, not writing a diagnosis. The deep orchestrator
# (core/ai_orchestrator.py) uses a separate, larger model via SIMAPI_AI_MODEL.
QUICK_MODEL        = os.environ.get("SIMAPI_AI_QUICK_MODEL", "nvidia/nemotron-nano-9b-v2:free")
MODEL              = QUICK_MODEL  # backwards-compat alias used by report_to_dict/tests
TIMEOUT_SECONDS    = int(os.environ.get("SIMAPI_AI_QUICK_TIMEOUT_SECONDS", "18"))

TOKENS_SHORT = 400   # quick verdict: "normal"/"not normal" + one-sentence reason
TOKENS_LONG  = 3000  # detailed explanations (deep orchestrator phases)

# When no key is configured the AI layer is disabled and reports its status
# cleanly rather than failing a validation run. Physics validation is unaffected.
AI_ENABLED = bool(OPENROUTER_API_KEY)

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
    verdict:         str = ""  # terse 2-3 word headline: "Normal" / "Not Normal"


def _quick_summary(data: pd.DataFrame, physics_issues: list[dict]) -> dict:
    """Compact signal for the quick check — not a full distribution dump.

    The quick model only needs to answer "is this normal", so it gets counts
    and a handful of the most extreme values, not every percentile of every
    column. Keeping the input small is most of why this path is fast.
    """
    nc = list(data.select_dtypes(include=[np.number]).columns)
    n = len(data)
    failed = [i for i in physics_issues if i.get("status") == "failed"]
    warned = [i for i in physics_issues if i.get("status") == "warning"]

    # Highest coefficient-of-variation columns are the most likely to look "off".
    notable_cv = []
    for col in nc[:15]:
        s = data[col].dropna()
        if len(s) > 1 and s.mean() != 0:
            cv = abs(float(s.std() / s.mean()))
            if cv > 0.5:
                notable_cv.append(f"{col} (cv={cv:.2f})")

    return {
        "trials": n,
        "columns": len(nc),
        "failed_checks": [i.get("name", "") for i in failed[:8]],
        "warning_checks": [i.get("name", "") for i in warned[:8]],
        "high_variance_columns": notable_cv[:5],
    }


def _build_prompt(data: pd.DataFrame, sim_type: str, conditions: dict, physics_issues: list[dict]) -> str:
    """Minimal prompt for the fast default check: is this dataset normal or not."""
    summary = _quick_summary(data, physics_issues)
    return f"""You are sanity-checking a {sim_type} simulation dataset that a deterministic physics engine already validated with {summary['trials']} trials across {summary['columns']} columns.

Failed checks: {summary['failed_checks'] or 'none'}
Warning checks: {summary['warning_checks'] or 'none'}
High-variance columns (cv>0.5): {summary['high_variance_columns'] or 'none'}
Conditions: {json.dumps(conditions)}

Is this dataset normal (safe to use as-is) or not normal (has a real problem)? Be terse.

Respond ONLY with this JSON, no other text:
{{"verdict": "normal" | "not normal", "reason": "one short sentence", "anomaly_score": 0.0}}

anomaly_score: 0.0=clean, 1.0=seriously corrupted. "normal" implies anomaly_score < 0.4."""


def _call_api(prompt: str, max_tokens: int = TOKENS_SHORT, model: str = QUICK_MODEL, timeout: int = TIMEOUT_SECONDS) -> tuple:
    payload = json.dumps({
        "model": model, "max_tokens": max_tokens, "temperature": 0.1,
        # Cap hidden reasoning tokens explicitly — some free models reason
        # even with exclude=true, and an uncapped reasoning budget can eat
        # the whole response before any visible content is emitted.
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
    return raw, (time.time()-t0)*1000


def _parse(raw: str) -> dict:
    data = json.loads(raw)
    content = data["choices"][0]["message"].get("content")
    if not content:
        # Some free models still burn part of the reasoning budget on hidden
        # chain-of-thought even with reasoning.exclude=true, occasionally
        # leaving zero tokens for the visible answer. Fail with a clear,
        # specific error rather than an AttributeError on None.
        raise ValueError("Model returned no content (likely exhausted its token budget on hidden reasoning)")
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        end = -1 if lines[-1].strip() in ("```","```json") else len(lines)
        content = "\n".join(lines[1:end])
    return json.loads(content)


def validate_with_ai(data: pd.DataFrame, simulation_type: str,
                     conditions: dict, physics_issues: list[dict]) -> AIValidationReport:
    t0 = time.time()

    # Graceful degradation: if no API key is configured, skip the AI pass and
    # report a clear, non-error status so physics results are still returned.
    if not AI_ENABLED:
        return AIValidationReport(
            status="disabled", model=MODEL, processing_ms=0.0,
            findings=[], dataset_summary="AI validation disabled: no API key configured.",
            anomaly_score=0.0, recommendations=[], timed_out=False,
            error=None,
        )

    result = {"done": False, "report": None, "error": None}

    def _run():
        try:
            prompt = _build_prompt(data, simulation_type, conditions, physics_issues)
            try:
                raw, api_ms = _call_api(prompt)
                parsed = _parse(raw)
            except (ValueError, KeyError):
                # One retry with a larger token budget — free-tier reasoning
                # models occasionally burn their whole budget on hidden
                # chain-of-thought and leave nothing for the visible answer.
                raw, api_ms = _call_api(prompt, max_tokens=TOKENS_SHORT * 2)
                parsed = _parse(raw)
            is_normal = str(parsed.get("verdict", "")).strip().lower() == "normal"
            anomaly = float(parsed.get("anomaly_score", 0.1 if is_normal else 0.6))
            result["report"] = AIValidationReport(
                status="passed" if is_normal else ("failed" if anomaly > 0.7 else "warning"),
                verdict="Normal" if is_normal else "Not Normal",
                model=QUICK_MODEL,
                processing_ms=round((time.time()-t0)*1000, 1),
                findings=[] if is_normal else [AIFinding(
                    severity="warning", category="ai_quick_check", title="AI flagged this dataset",
                    detail=str(parsed.get("reason", "")), trials=[], confidence=1.0 - anomaly,
                )],
                dataset_summary=str(parsed.get("reason", "")),
                anomaly_score=anomaly,
                recommendations=[],
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
            processing_ms=round((time.time()-t0)*1000, 1),
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
        "findings": [{"severity":f.severity,"category":f.category,"title":f.title,
                      "detail":f.detail,"trials":f.trials,"confidence":f.confidence}
                     for f in report.findings],
        "recommendations": report.recommendations,
        "error": report.error,
    }
