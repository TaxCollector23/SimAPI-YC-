"""
SimAPI — AI Validation Layer v2 (legacy shim over core/ai_orchestrator.py)

- Sends full distribution data, not just samples
- Configurable timeout (SIMAPI_AI_TIMEOUT_SECONDS) with graceful degradation
- Async-friendly: returns immediately, AI result polled separately
- Uses OpenRouter with the model set by SIMAPI_AI_MODEL (defaults to the
  strongest free-tier model available)
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
MODEL              = os.environ.get("SIMAPI_AI_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free")
TIMEOUT_SECONDS    = int(os.environ.get("SIMAPI_AI_TIMEOUT_SECONDS", "75"))

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


def _distribution_summary(s: pd.Series) -> dict:
    """Full distribution: percentiles, shape, tail behaviour."""
    if len(s) == 0:
        return {}
    s = s.dropna()
    return {
        "mean":   round(float(s.mean()), 8),
        "std":    round(float(s.std()), 8),
        "min":    round(float(s.min()), 8),
        "p1":     round(float(s.quantile(.01)), 8),
        "p5":     round(float(s.quantile(.05)), 8),
        "p10":    round(float(s.quantile(.10)), 8),
        "p25":    round(float(s.quantile(.25)), 8),
        "median": round(float(s.median()), 8),
        "p75":    round(float(s.quantile(.75)), 8),
        "p90":    round(float(s.quantile(.90)), 8),
        "p95":    round(float(s.quantile(.95)), 8),
        "p99":    round(float(s.quantile(.99)), 8),
        "max":    round(float(s.max()), 8),
        "skew":   round(float(s.skew()), 4),
        "kurt":   round(float(s.kurtosis()), 4),
        "cv":     round(float(s.std()/s.mean()), 4) if s.mean() != 0 else None,
        "n":      int(len(s)),
    }


def _build_prompt(data: pd.DataFrame, sim_type: str, conditions: dict, physics_issues: list[dict]) -> str:
    nc = list(data.select_dtypes(include=[np.number]).columns)
    n  = len(data)

    # Full distributions for every column
    distributions = {}
    for col in nc[:25]:
        distributions[col] = _distribution_summary(data[col])

    # Correlation matrix (key relationships)
    corr = {}
    if len(nc) >= 2:
        cm = data[nc[:15]].corr()
        for i in range(len(cm.columns)):
            for j in range(i+1, len(cm.columns)):
                r = float(cm.iloc[i,j])
                if not np.isnan(r) and abs(r) > 0.3:
                    corr[f"{cm.columns[i]} ↔ {cm.columns[j]}"] = round(r, 4)

    # Flagged trial rows (from physics exclusions)
    flagged = []
    for issue in physics_issues:
        if issue.get("status") == "failed":
            ti = issue.get("value")
            if ti is not None:
                try:
                    idx = int(ti)
                    if 0 <= idx < len(data):
                        row = {k: round(float(v), 6) if isinstance(v, float) and not np.isnan(v) else v
                               for k, v in data.iloc[idx].items() if k in nc[:20]}
                        flagged.append({"trial": idx, "data": row})
                except: pass

    # Also grab first 3 rows as anchors
    anchor_rows = []
    for i in range(min(3, n)):
        row = {k: round(float(v), 6) if isinstance(v, float) and not np.isnan(v) else v
               for k, v in data.iloc[i].items() if k in nc[:20]}
        anchor_rows.append({"trial": i, "data": row})

    # Physics issues summary (warnings + failures only)
    ph_summary = [{"check": i.get("name",""), "status": i.get("status",""),
                   "detail": i.get("detail",""), "cat": i.get("category","")}
                  for i in physics_issues[:40]]

    return f"""You are a world-class physics simulation data scientist performing expert second-pass validation. A deterministic rule engine has already run 280+ checks. Your job: find what it MISSED using domain expertise and holistic reasoning.

## Context
- Simulation type: **{sim_type}**
- Trials: **{n}**
- Columns: {', '.join(nc[:25])}
- Input conditions: {json.dumps(conditions)}

## Full Statistical Distributions
```json
{json.dumps(distributions, indent=2)}
```

## Notable Correlations (|r|>0.3)
```json
{json.dumps(corr, indent=2)}
```

## Anchor Rows (first 3 trials)
```json
{json.dumps(anchor_rows, indent=2)}
```

## Flagged Rows (physics engine exclusions)
```json
{json.dumps(flagged[:10], indent=2)}
```

## Physics Engine Already Found
```json
{json.dumps(ph_summary, indent=2)}
```

## Your Expert Analysis — Find What the Rules Missed

Think deeply about:

1. **Magnitude realism**: Are the absolute values physically achievable for {sim_type}? E.g. drag coefficients of 0.312 for what geometry? Is that consistent with the Reynolds number?

2. **Distribution shape**: Real CFD/FEA data has characteristic distributions. Perfectly Gaussian data with suspiciously low variance often indicates synthetic generation. High CV in quantities that should be nearly constant (e.g. material elastic modulus) suggests dataset mixing.

3. **Cross-variable physics not in the rule engine**: Beyond simple pairwise checks — does the combination of ALL these quantities tell a physically coherent story? Could a real simulation produce this joint distribution?

4. **Temporal/sequential patterns**: If this is convergence data, do residuals decrease monotonically? If this is parametric sweep data, are sweep variables clearly the dominant source of variance?

5. **ML training quality**: Will a model trained on this data generalize? Are there biases (only one flow regime, one material, narrow parameter space)? Is there enough variance in target variables?

6. **Dataset provenance signals**: Signs of copy-paste, scaling errors (unit conversion mistakes create suspicious round numbers or exact factors of 1000), truncation artifacts, sensor saturation.

7. **Domain expert intuition for {sim_type}**: Apply deep specialist knowledge that no rule engine can encode.

DO NOT repeat issues the physics engine already found. Find genuinely NEW insights.

Respond ONLY with valid JSON, no other text:

{{
  "overall_assessment": "2-3 sentence plain English summary of data quality and key concerns",
  "anomaly_score": 0.0,
  "status": "passed|warning|failed",
  "findings": [
    {{
      "severity": "critical|warning|info",
      "category": "magnitude_realism|distribution_shape|cross_variable_physics|temporal_pattern|ml_quality|dataset_provenance|domain_expert",
      "title": "Concise finding title",
      "detail": "Specific technical explanation with column names, values, and why it matters for {sim_type}",
      "trials": [],
      "confidence": 0.85
    }}
  ],
  "recommendations": [
    "Specific actionable recommendation"
  ]
}}

Rules:
- anomaly_score: 0.0=perfect, 1.0=invalid. passed<0.2, warning 0.2-0.5, failed>0.5
- 0 findings if data is genuinely clean (say so clearly in overall_assessment)
- Maximum 12 findings, ranked by severity
- Be specific: cite column names and numerical values
- Do NOT hallucinate issues that aren't supported by the data"""


def _call_api(prompt: str) -> tuple:
    payload = json.dumps({
        "model": MODEL, "max_tokens": 3000, "temperature": 0.1,
        "reasoning": {"exclude": True},
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
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        raw = resp.read().decode("utf-8")
    return raw, (time.time()-t0)*1000


def _parse(raw: str) -> dict:
    data = json.loads(raw)
    content = data["choices"][0]["message"]["content"].strip()
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
            raw, api_ms = _call_api(prompt)
            parsed = _parse(raw)
            findings = [AIFinding(
                severity=f.get("severity","warning"),
                category=f.get("category","general"),
                title=f.get("title",""),
                detail=f.get("detail",""),
                trials=f.get("trials",[]),
                confidence=float(f.get("confidence",0.7)),
            ) for f in parsed.get("findings",[])]
            result["report"] = AIValidationReport(
                status=parsed.get("status","warning"),
                model=MODEL,
                processing_ms=round((time.time()-t0)*1000, 1),
                findings=findings,
                dataset_summary=parsed.get("overall_assessment",""),
                anomaly_score=float(parsed.get("anomaly_score",0.5)),
                recommendations=parsed.get("recommendations",[]),
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
            status="error", model=MODEL,
            processing_ms=round((time.time()-t0)*1000, 1),
            findings=[], dataset_summary="",
            anomaly_score=0.0, recommendations=[],
            timed_out=timed, error=err,
        )
    return result["report"]


def report_to_dict(report: AIValidationReport) -> dict:
    return {
        "status":          report.status,
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
