"""
SimAPI — AI Orchestrator v1.0

Multi-phase AI validation that controls the validation pipeline like a senior
simulation engineer. Replaces the single-shot AI layer with a structured
reasoning pipeline:

  Phase 0: Dataset profiling (what kind of data is this?)
  Phase 2: Pattern recognition (collapse individual issues into root causes)
  Phase 3: Targeted follow-up probes (run specific additional tests)
  Phase 4: Final synthesis (produce a confidence-weighted verdict)

Phase 1 is the physics engine itself (orchestrated externally).
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from core.followup_probes import (
    probe_duplicate_cosine,
    probe_gas_constant,
    probe_joint_distribution_shift,
    probe_physically_impossible_combinations,
    probe_regime_change,
)

OPENROUTER_API_KEY = os.environ.get("SIMAPI_OPENROUTER_API_KEY", "")
OPENROUTER_URL = os.environ.get("SIMAPI_OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions")
MODEL = os.environ.get("SIMAPI_AI_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free")
TIMEOUT_SECONDS = int(os.environ.get("SIMAPI_AI_TIMEOUT_SECONDS", "75"))
AI_ENABLED = bool(OPENROUTER_API_KEY)


@dataclass
class OrchestratorResult:
    verdict: str
    overall_confidence: float
    corruption_probability: dict[str, float]
    root_causes: list[dict[str, Any]]
    false_positive_suspicions: list[dict[str, str]]
    what_physics_caught: str
    what_physics_missed: str
    what_only_ai_sees: str
    findings: list[dict[str, Any]]
    recommended_action: str
    training_ready_after_corrections: bool
    ai_exclusions: list[int]
    phase_timings: dict[str, float]
    model: str
    error: str | None = None


def _call_llm(prompt: str, max_tokens: int = 3000) -> dict:
    """Call OpenRouter and return parsed JSON from the model's response.

    The default free model is a reasoning model — hidden chain-of-thought
    tokens count against max_tokens, so a low budget can exhaust the whole
    response before any visible JSON is emitted. Exclude reasoning from the
    response and give enough headroom for both.
    """
    payload = json.dumps({
        "model": MODEL, "max_tokens": max_tokens, "temperature": 0.1,
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
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        raw = json.loads(resp.read().decode("utf-8"))

    content = raw["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        lines = content.split("\n")
        end = -1 if lines[-1].strip().startswith("```") else len(lines)
        content = "\n".join(lines[1:end])
    return json.loads(content)


def _distribution_summary(s: pd.Series) -> dict:
    s = s.dropna()
    if len(s) == 0:
        return {}
    return {
        "mean": round(float(s.mean()), 6),
        "std": round(float(s.std()), 6),
        "p1": round(float(s.quantile(0.01)), 6),
        "p25": round(float(s.quantile(0.25)), 6),
        "median": round(float(s.median()), 6),
        "p75": round(float(s.quantile(0.75)), 6),
        "p99": round(float(s.quantile(0.99)), 6),
        "min": round(float(s.min()), 6),
        "max": round(float(s.max()), 6),
        "skew": round(float(s.skew()), 3),
        "n": int(len(s)),
    }


def run_phase_0(data: pd.DataFrame, sim_type: str, conditions: dict,
                context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Phase 0: Dataset profiling — determine what kind of data this is."""
    t0 = time.time()

    nc = list(data.select_dtypes(include=[np.number]).columns)
    distributions = {col: _distribution_summary(data[col]) for col in nc[:20]}

    corr_pairs = []
    if len(nc) >= 2:
        cm = data[nc[:15]].corr()
        for i in range(len(cm.columns)):
            for j in range(i + 1, len(cm.columns)):
                r = float(cm.iloc[i, j])
                if not np.isnan(r) and abs(r) > 0.5:
                    corr_pairs.append(f"{cm.columns[i]}~{cm.columns[j]}: r={r:.3f}")

    first_rows = data.head(5).to_dict(orient="records")
    last_rows = data.tail(5).to_dict(orient="records")

    ctx_str = ""
    if context:
        if context.get("geometry_description"):
            ctx_str += f"\nGeometry: {context['geometry_description']}"
        if context.get("what_are_you_measuring"):
            ctx_str += f"\nObjective: {context['what_are_you_measuring']}"
        if context.get("known_issues"):
            ctx_str += f"\nKnown issues: {context['known_issues']}"

    prompt = f"""You are a senior simulation engineer profiling a dataset before validation.

Simulation type: {sim_type}
Trials: {len(data)}
Columns: {', '.join(nc[:20])}
Conditions: {json.dumps(conditions)}
{ctx_str}

Distributions:
{json.dumps(distributions, indent=1)}

Correlations: {'; '.join(corr_pairs[:10])}

First 5 rows: {json.dumps(first_rows[:3], default=str)}
Last 5 rows: {json.dumps(last_rows[:3], default=str)}

Produce a JSON test plan:
{{
  "actual_simulation_type": "string",
  "confidence_in_type": 0.0-1.0,
  "primary_target_variable": "string",
  "dominant_variance_sources": ["col1", "col2"],
  "suspected_issues": ["brief description"],
  "priority_checks": ["check_name"],
  "skip_checks": [],
  "expected_ranges": {{"column": [min, max]}},
  "regime": "description of flow/physics regime",
  "dataset_notes": "one sentence about what this dataset represents"
}}

Respond ONLY with valid JSON."""

    try:
        result = _call_llm(prompt, max_tokens=2500)
        result["_timing_ms"] = round((time.time() - t0) * 1000, 1)
        return result
    except Exception as e:
        return {
            "actual_simulation_type": sim_type,
            "confidence_in_type": 0.5,
            "suspected_issues": [],
            "priority_checks": [],
            "skip_checks": [],
            "expected_ranges": {},
            "dataset_notes": f"Phase 0 failed: {e}",
            "_timing_ms": round((time.time() - t0) * 1000, 1),
        }


def run_phase_2(data: pd.DataFrame, sim_type: str, physics_results: dict,
                test_plan: dict) -> dict[str, Any]:
    """Phase 2: Pattern recognition — collapse individual issues into root causes."""
    t0 = time.time()

    issues_summary = []
    for issue in physics_results.get("issues", [])[:30]:
        issues_summary.append({
            "name": issue.get("name", ""),
            "status": issue.get("status", ""),
            "detail": issue.get("detail", issue.get("description", "")),
            "category": issue.get("category", ""),
        })

    exclusions_summary = []
    for excl in physics_results.get("exclusions", [])[:20]:
        exclusions_summary.append({
            "trial": excl.get("trial_index", 0),
            "reason": excl.get("reason", ""),
        })

    prompt = f"""You are diagnosing a {sim_type} dataset. The physics engine found these issues:

Issues ({len(issues_summary)} shown):
{json.dumps(issues_summary[:20], indent=1)}

Exclusions ({len(exclusions_summary)} shown):
{json.dumps(exclusions_summary[:15], indent=1)}

Test plan from Phase 0:
{json.dumps({k: v for k, v in test_plan.items() if not k.startswith("_")}, indent=1)}

Checks by category: {json.dumps(physics_results.get("checks_by_category", {}), indent=1)}

Collapse individual failures into ROOT CAUSES. Many individual check failures often share one underlying cause.

Respond ONLY with valid JSON:
{{
  "root_causes": [
    {{
      "name": "string",
      "confidence": 0.0-1.0,
      "evidence": "specific explanation referencing check names and patterns",
      "affected_trials_range": [start, end],
      "affected_columns": ["col1"],
      "severity": "critical|warning|info"
    }}
  ],
  "false_positive_suspicions": [
    {{"check_name": "string", "reason": "why this might be a false positive"}}
  ],
  "checks_that_should_have_fired": [
    {{"check": "string", "reason": "why"}}
  ]
}}"""

    try:
        result = _call_llm(prompt, max_tokens=2800)
        result["_timing_ms"] = round((time.time() - t0) * 1000, 1)
        return result
    except Exception as e:
        return {
            "root_causes": [],
            "false_positive_suspicions": [],
            "checks_that_should_have_fired": [],
            "_timing_ms": round((time.time() - t0) * 1000, 1),
            "_error": str(e),
        }


def run_phase_3(data: pd.DataFrame, sim_type: str, diagnosis: dict) -> dict[str, Any]:
    """Phase 3: Run targeted follow-up probes based on Phase 2 diagnosis."""
    t0 = time.time()
    results = {}

    results["gas_constant"] = probe_gas_constant(data)

    nc = list(data.select_dtypes(include=[np.number]).columns)
    if len(nc) >= 2:
        results["joint_distribution"] = probe_joint_distribution_shift(
            data, nc[0], nc[1] if len(nc) > 1 else nc[0]
        )

    results["duplicates"] = probe_duplicate_cosine(data)

    for col in nc[:5]:
        key = f"regime_change_{col}"
        results[key] = probe_regime_change(data, col)

    results["physics_combinations"] = probe_physically_impossible_combinations(data, sim_type)

    results["_timing_ms"] = round((time.time() - t0) * 1000, 1)
    return results


def run_phase_4(data: pd.DataFrame, sim_type: str, test_plan: dict,
                physics_results: dict, diagnosis: dict,
                probe_results: dict, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Phase 4: Final synthesis — produce a confidence-weighted verdict."""
    t0 = time.time()

    root_causes = diagnosis.get("root_causes", [])
    n_excluded_physics = physics_results.get("trials_excluded", 0)
    n_total = physics_results.get("trials_submitted", len(data))

    probe_findings = []
    for key, val in probe_results.items():
        if key.startswith("_"):
            continue
        if isinstance(val, dict) and val.get("flagged"):
            probe_findings.append(f"{key}: {val.get('detail', 'flagged')}")

    prompt = f"""You are producing a final synthesis for a {sim_type} validation.

Phase 0 (profiling): {json.dumps({k: v for k, v in test_plan.items() if not k.startswith("_")}, indent=1)}

Phase 1 (physics): {n_excluded_physics}/{n_total} trials excluded, {physics_results.get("all_checks_count", 0)} checks run

Phase 2 (diagnosis): {len(root_causes)} root causes identified:
{json.dumps(root_causes[:5], indent=1)}

Phase 3 (probes): {json.dumps(probe_findings[:8])}

User context: {json.dumps(context or {}, default=str)}

Produce the FINAL verdict. Respond ONLY with valid JSON:
{{
  "verdict": "training_ready|not_training_ready|needs_correction",
  "overall_confidence": 0.0-1.0,
  "corruption_probability_distribution": {{"category": probability}},
  "what_physics_engine_caught": "one sentence",
  "what_physics_engine_missed": "one sentence (or 'nothing significant')",
  "what_only_ai_can_see": "one sentence about higher-order patterns",
  "recommended_action": "specific actionable recommendation",
  "training_ready_after_corrections": true/false,
  "additional_exclusions": []
}}"""

    try:
        result = _call_llm(prompt, max_tokens=2500)
        result["_timing_ms"] = round((time.time() - t0) * 1000, 1)
        return result
    except Exception as e:
        return {
            "verdict": "not_training_ready" if n_excluded_physics > n_total * 0.3 else "training_ready",
            "overall_confidence": 0.5,
            "corruption_probability_distribution": {},
            "what_physics_engine_caught": f"{n_excluded_physics} trials excluded by deterministic checks",
            "what_physics_engine_missed": "AI synthesis unavailable",
            "what_only_ai_can_see": "",
            "recommended_action": "Review physics engine results manually",
            "training_ready_after_corrections": n_excluded_physics < n_total * 0.5,
            "additional_exclusions": [],
            "_timing_ms": round((time.time() - t0) * 1000, 1),
            "_error": str(e),
        }


def orchestrate(data: pd.DataFrame, sim_type: str, conditions: dict,
                physics_results: dict, context: dict[str, Any] | None = None) -> OrchestratorResult:
    """Run the full 4-phase AI orchestration pipeline."""
    if not AI_ENABLED:
        return OrchestratorResult(
            verdict="physics_only",
            overall_confidence=0.0,
            corruption_probability={},
            root_causes=[],
            false_positive_suspicions=[],
            what_physics_caught=f"{physics_results.get('trials_excluded', 0)} trials excluded",
            what_physics_missed="AI disabled — no API key configured",
            what_only_ai_sees="",
            findings=[],
            recommended_action="Configure SIMAPI_OPENROUTER_API_KEY for AI-enhanced validation",
            training_ready_after_corrections=physics_results.get("training_ready", True),
            ai_exclusions=[],
            phase_timings={},
            model=MODEL,
            error="AI disabled",
        )

    timings = {}

    # Phase 0
    test_plan = run_phase_0(data, sim_type, conditions, context)
    timings["phase_0_profile_ms"] = test_plan.get("_timing_ms", 0)

    # Phase 2
    diagnosis = run_phase_2(data, sim_type, physics_results, test_plan)
    timings["phase_2_diagnosis_ms"] = diagnosis.get("_timing_ms", 0)

    # Phase 3
    probe_results = run_phase_3(data, sim_type, diagnosis)
    timings["phase_3_probes_ms"] = probe_results.get("_timing_ms", 0)

    # Phase 4
    synthesis = run_phase_4(data, sim_type, test_plan, physics_results, diagnosis, probe_results, context)
    timings["phase_4_synthesis_ms"] = synthesis.get("_timing_ms", 0)

    ai_exclusions = synthesis.get("additional_exclusions", [])
    corruption_prob = synthesis.get("corruption_probability_distribution", {})

    root_causes = diagnosis.get("root_causes", [])
    findings = []
    for rc in root_causes:
        findings.append({
            "severity": rc.get("severity", "warning"),
            "category": "ai_root_cause",
            "title": rc.get("name", "Unknown"),
            "detail": rc.get("evidence", ""),
            "confidence": rc.get("confidence", 0.5),
            "affected_columns": rc.get("affected_columns", []),
        })

    return OrchestratorResult(
        verdict=synthesis.get("verdict", "training_ready"),
        overall_confidence=float(synthesis.get("overall_confidence", 0.5)),
        corruption_probability=corruption_prob,
        root_causes=root_causes,
        false_positive_suspicions=diagnosis.get("false_positive_suspicions", []),
        what_physics_caught=synthesis.get("what_physics_engine_caught", ""),
        what_physics_missed=synthesis.get("what_physics_engine_missed", ""),
        what_only_ai_sees=synthesis.get("what_only_ai_can_see", ""),
        findings=findings,
        recommended_action=synthesis.get("recommended_action", ""),
        training_ready_after_corrections=synthesis.get("training_ready_after_corrections", True),
        ai_exclusions=[int(x) for x in ai_exclusions if isinstance(x, (int, float))],
        phase_timings=timings,
        model=MODEL,
    )


def result_to_dict(result: OrchestratorResult) -> dict:
    return {
        "verdict": result.verdict,
        "overall_confidence": result.overall_confidence,
        "corruption_probability": result.corruption_probability,
        "root_causes": result.root_causes,
        "false_positive_suspicions": result.false_positive_suspicions,
        "what_physics_caught": result.what_physics_caught,
        "what_physics_missed": result.what_physics_missed,
        "what_only_ai_sees": result.what_only_ai_sees,
        "findings": result.findings,
        "recommended_action": result.recommended_action,
        "training_ready_after_corrections": result.training_ready_after_corrections,
        "ai_exclusions": result.ai_exclusions,
        "phase_timings": result.phase_timings,
        "model": result.model,
        "error": result.error,
    }
