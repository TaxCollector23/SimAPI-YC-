"""
SimAPI — Grounded AI Pipeline (Phases C / D / E)
=================================================

The AI layer's job is NOT to second-guess the physics. A language model
re-deriving a deterministic gas-law calculation adds nothing and can only
introduce error. Its job is the three things deterministic code cannot do:

  Phase C  CLUSTER   Collapse N findings into K root causes.
                     10 findings across 3 columns are usually 1 pipeline bug.
  Phase D  VERIFY    Every hypothesis is confirmed or refuted by *code*.
                     The model proposes; only a deterministic probe disposes.
  Phase E  NARRATE   Explain confirmed causes in engineer language.

Three invariants make this trustworthy:

  1. SELECT, NEVER INVENT. The model picks a failure mode from a fixed library
     and a probe from a fixed allowlist. It cannot name a file, a line number,
     or a value that is not already in its input. Free text is confined to the
     final narrative, and that narrative is validated against the input before
     it is shown.

  2. CONFIDENCE IS EARNED. A hypothesis is labelled `hypothesis` until a probe
     confirms it, then `confirmed`. An unverified guess is never rendered with
     a confidence number, because a fabricated 90% is worse than no number.

  3. FAIL DOWN, NEVER OUT. Every phase has a deterministic fallback. With no
     API key, no network, or a rate-limited model, the pipeline still emits
     clustered root causes — just without the narrative. The physics result is
     always complete and standalone.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from core.followup_probes import (
    probe_duplicate_cosine,
    probe_gas_constant,
    probe_joint_distribution_shift,
    probe_physically_impossible_combinations,
    probe_regime_change,
)

# ── Model configuration ───────────────────────────────────────────────────────
# Two tiers. Clustering is structured classification and runs fine on a small
# model; the narrative needs a stronger one. Both are overridable, and either
# failing degrades to the deterministic path rather than to an error.
API_KEY = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("SIMAPI_OPENROUTER_API_KEY", "")
API_URL = os.environ.get("SIMAPI_OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions")
MODEL_CLUSTER = os.environ.get("SIMAPI_AI_CLUSTER_MODEL", "nvidia/nemotron-3-nano-30b-a3b:free")
MODEL_NARRATE = os.environ.get("SIMAPI_AI_NARRATE_MODEL", "nvidia/nemotron-3-nano-30b-a3b:free")
TIMEOUT_CLUSTER = int(os.environ.get("SIMAPI_AI_CLUSTER_TIMEOUT", "25"))
TIMEOUT_NARRATE = int(os.environ.get("SIMAPI_AI_NARRATE_TIMEOUT", "30"))
AI_ENABLED = bool(API_KEY)
PIPELINE_VERSION = "4.0-grounded"


# ═══════════════════════════════════════════════════════════════════════════════
# Failure mode library — the model selects from this, it cannot invent entries
# ═══════════════════════════════════════════════════════════════════════════════

FAILURE_MODES: Dict[str, dict] = {
    "unit_scale_error": {
        "label": "Unit scale error",
        "signature": "values off by a clean power of ten (×1000, ×60, ÷1000)",
        "stage": "post-processing / export",
        "probe": "gas_constant",
        "action": "Find the unit conversion in the export step and check it is applied once, to every row.",
    },
    "unit_offset_error": {
        "label": "Unit offset error (Kelvin ↔ Celsius)",
        "signature": "temperatures offset by ~273.15, or a bimodal temperature distribution",
        "stage": "data ingestion / logging",
        "probe": "impossible_combinations",
        "action": "Confirm every temperature in the chain uses one scale; sensors often report °C while solvers use K.",
    },
    "solver_divergence": {
        "label": "Solver divergence",
        "signature": "isolated extreme values, orders of magnitude outside physical bounds",
        "stage": "solver iteration",
        "probe": "impossible_combinations",
        "action": "Check solver residuals and mesh quality at the affected trials; reduce timestep or add flux limiting.",
    },
    "derived_quantity_error": {
        "label": "Derived quantity formula error",
        "signature": "a computed column disagrees with its defining formula while its inputs are clean",
        "stage": "post-processing / derived quantities",
        "probe": "impossible_combinations",
        "action": "Recompute the derived column from its inputs and compare; check for a wrong constant or missing term.",
    },
    "frozen_output": {
        "label": "Frozen solver output / duplicated rows",
        "signature": "identical rows repeated",
        "stage": "solver output / data pipeline",
        "probe": "duplicate_cosine",
        "action": "Check whether the solver advanced between writes, or whether a caching layer returned a stale result.",
    },
    "sensor_drift": {
        "label": "Sensor or gauge drift",
        "signature": "progressive monotonic change in one channel while others stay stable",
        "stage": "measurement / gauge extraction",
        "probe": "regime_change",
        "action": "Plot the channel against run order; check calibration date and thermal compensation.",
    },
    "regime_change": {
        "label": "Operating regime change",
        "signature": "distribution shifts partway through the dataset",
        "stage": "test configuration",
        "probe": "regime_change",
        "action": "Confirm whether a configuration changed mid-campaign; if so, split the dataset before training.",
    },
    "measurement_noise": {
        "label": "Measurement noise beyond uncertainty band",
        "signature": "scattered isolated outliers with no structure",
        "stage": "measurement",
        "probe": "joint_shift",
        "action": "Compare scatter against instrument spec; check grounding, shielding and sample rate.",
    },
}

PROBE_REGISTRY: Dict[str, Callable] = {
    "gas_constant": lambda df, **k: probe_gas_constant(df),
    "duplicate_cosine": lambda df, **k: probe_duplicate_cosine(df),
    "regime_change": lambda df, col=None, **k: probe_regime_change(df, col) if col else {"skipped": "no column"},
    "impossible_combinations": lambda df, sim_type="", **k: probe_physically_impossible_combinations(df, sim_type),
    "joint_shift": lambda df, col_a=None, col_b=None, **k: (
        probe_joint_distribution_shift(df, col_a, col_b) if col_a and col_b else {"skipped": "needs two columns"}
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# Result types
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class RootCause:
    mode_key: str
    label: str
    affected_trials: List[int]
    evidence: List[str]                  # verbatim engine findings, never paraphrased
    stage: str
    status: str = "hypothesis"           # hypothesis | confirmed | refuted
    probe_name: Optional[str] = None
    probe_result: Optional[dict] = None
    confidence: Optional[float] = None   # None until a probe confirms
    action: str = ""
    source: str = "deterministic"        # deterministic | ai

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PipelineResult:
    version: str
    root_causes: List[RootCause]
    narrative: str
    narrative_source: str                # "ai" | "deterministic"
    n_findings_in: int
    n_causes_out: int
    phase_timings: Dict[str, float]
    degraded: List[str]                  # phases that fell back, and why
    model_cluster: Optional[str] = None
    model_narrate: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["root_causes"] = [c.to_dict() for c in self.root_causes]
        return d


# ═══════════════════════════════════════════════════════════════════════════════
# LLM transport
# ═══════════════════════════════════════════════════════════════════════════════

def _call_llm(prompt: str, model: str, timeout: int, max_tokens: int = 1200) -> dict:
    """One JSON-returning LLM call. Raises on any failure; callers degrade."""
    payload = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "temperature": 0.0,
        "reasoning": {"exclude": True, "max_tokens": min(400, max_tokens // 3)},
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        API_URL, data=payload, method="POST",
        headers={"Authorization": f"Bearer {API_KEY}",
                 "Content-Type": "application/json",
                 "HTTP-Referer": "https://sim-api.vercel.app",
                 "X-Title": "SimAPI"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.loads(r.read().decode())
    content = (body.get("choices") or [{}])[0].get("message", {}).get("content")
    if not content:
        raise ValueError("empty model response")
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?|```$", "", content, flags=re.M).strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        a, b = content.find("{"), content.rfind("}")
        if a != -1 and b > a:
            return json.loads(content[a:b + 1])
        raise


# ═══════════════════════════════════════════════════════════════════════════════
# Phase C — clustering
# ═══════════════════════════════════════════════════════════════════════════════

# Ordered most-specific first. A finding is assigned to the FIRST rule it
# matches, and a trial is reported under its single most specific cause — a
# solver blow-up is not also "measurement noise" just because it is an outlier.
_DET_RULES: List[Tuple[str, Tuple[str, ...]]] = [
    ("unit_scale_error",      ("gas constant", "p/(ρt)", "expected 287", "unit error",
                               "×1000", "/1000", "ideal gas")),
    ("unit_offset_error",     ("273.15", "celsius", "kelvin", "°c")),
    ("frozen_output",         ("duplicate", "identical rows", "near-duplicate")),
    ("solver_divergence",     ("nan", "inf", "non-finite", "divergence",
                               "outside", "bounds", "physically impossible")),
    ("derived_quantity_error",("inconsistent", "≠", "does not match", "recomputed",
                               "disagrees")),
    ("regime_change",         ("change-point", "changepoint", "regime", "segment",
                               "distribution shift")),
    ("sensor_drift",          ("mann-kendall", "drift", "creep", "monotonic trend")),
    ("measurement_noise",     ("outlier", "z-score", "tukey", "spike", "jump")),
]

# Same order = priority. Lower index wins when a trial matches several causes.
_RULE_PRIORITY = {k: i for i, (k, _) in enumerate(_DET_RULES)}


def cluster_deterministic(exclusions: List[dict]) -> List[RootCause]:
    """
    Vocabulary-based clustering. Runs with no network and is the floor the AI
    path must beat; if the model returns anything unusable we keep this.
    """
    buckets: Dict[str, Dict[str, Any]] = {}
    for ex in exclusions:
        reason = str(ex.get("reason", ""))
        low = reason.lower()
        key = next((k for k, words in _DET_RULES if any(w in low for w in words)), None)
        if key is None:
            continue
        b = buckets.setdefault(key, {"trials": set(), "evidence": []})
        idx = ex.get("trial_index")
        if isinstance(idx, int):
            b["trials"].add(idx)
        if reason not in b["evidence"] and len(b["evidence"]) < 6:
            b["evidence"].append(reason)

    # A trial can trip several checks; report it once, under the most specific
    # cause. Duplicating a trial across causes inflates the apparent number of
    # problems and makes the report read as noise.
    owner: Dict[int, str] = {}
    for key, b in buckets.items():
        for t in b["trials"]:
            cur = owner.get(t)
            if cur is None or _RULE_PRIORITY[key] < _RULE_PRIORITY[cur]:
                owner[t] = key

    out: List[RootCause] = []
    for key, b in buckets.items():
        trials = sorted(t for t in b["trials"] if owner.get(t) == key)
        if not trials:
            continue
        m = FAILURE_MODES[key]
        out.append(RootCause(
            mode_key=key, label=m["label"], affected_trials=trials,
            evidence=b["evidence"], stage=m["stage"],
            probe_name=m["probe"], action=m["action"],
            source="deterministic",
        ))
    out.sort(key=lambda c: (_RULE_PRIORITY[c.mode_key], -len(c.affected_trials)))
    return out


def cluster_ai(exclusions: List[dict], sim_type: str, profile_summary: str,
               fallback: List[RootCause]) -> Tuple[List[RootCause], Optional[str]]:
    """Ask the model to group findings. Returns (causes, degradation_reason)."""
    if not AI_ENABLED or not exclusions:
        return fallback, "no API key" if not AI_ENABLED else None

    findings = [{"trial": e.get("trial_index"), "reason": str(e.get("reason", ""))[:160]}
                for e in exclusions[:40]]
    catalog = {k: v["signature"] for k, v in FAILURE_MODES.items()}

    prompt = f"""You are a senior simulation engineer triaging validation findings for a {sim_type} dataset.

DATASET PROFILE: {profile_summary}

FINDINGS (produced by a deterministic physics engine — all are correct):
{json.dumps(findings, indent=1)}

FAILURE MODE CATALOG (you MUST choose mode_key values from this list only):
{json.dumps(catalog, indent=1)}

Group the findings into root causes. Rules:
- Findings with DIFFERENT physical origins must stay in SEPARATE causes. Do not
  invent a single story that links unrelated findings.
- Every trial number you output must appear in FINDINGS above.
- Every evidence string must be copied verbatim from a FINDINGS reason.
- Do not name files, paths, line numbers, or variables not shown above.
- If a finding matches no catalog entry, omit it.

Respond ONLY with JSON:
{{"root_causes":[{{"mode_key":"<from catalog>","affected_trials":[int],"evidence":["verbatim reason"],"reasoning":"one sentence"}}]}}"""

    try:
        parsed = _call_llm(prompt, MODEL_CLUSTER, TIMEOUT_CLUSTER, max_tokens=1400)
    except Exception as e:
        return fallback, f"clustering model unavailable ({type(e).__name__})"

    valid_trials = {e.get("trial_index") for e in exclusions}
    valid_reasons = {str(e.get("reason", "")) for e in exclusions}

    causes: List[RootCause] = []
    for rc in (parsed.get("root_causes") or [])[:8]:
        key = rc.get("mode_key")
        if key not in FAILURE_MODES:                       # invented mode -> drop
            continue
        trials = [t for t in (rc.get("affected_trials") or [])
                  if isinstance(t, int) and t in valid_trials]   # invented trial -> drop
        ev = [s for s in (rc.get("evidence") or [])
              if any(s[:60] in r or r[:60] in s for r in valid_reasons)]  # invented evidence -> drop
        if not trials:
            continue
        m = FAILURE_MODES[key]
        causes.append(RootCause(
            mode_key=key, label=m["label"], affected_trials=sorted(set(trials)),
            evidence=ev[:6] or [next(iter(valid_reasons), "")],
            stage=m["stage"], probe_name=m["probe"], action=m["action"], source="ai",
        ))

    if not causes:
        return fallback, "model output failed grounding checks"

    # The model must account for at least half the excluded trials, or we do not
    # trust its grouping over the deterministic one.
    covered = {t for c in causes for t in c.affected_trials}
    if len(covered) < 0.5 * len({e.get("trial_index") for e in exclusions}):
        return fallback, "model covered too few findings"
    return causes, None


# ═══════════════════════════════════════════════════════════════════════════════
# Phase D — verification
# ═══════════════════════════════════════════════════════════════════════════════

def verify(causes: List[RootCause], df: pd.DataFrame, sim_type: str) -> List[RootCause]:
    """
    Run each cause's probe. The probe is deterministic code — this is what turns
    a hypothesis into a finding, and it is the only place confidence is created.
    """
    for c in causes:
        fn = PROBE_REGISTRY.get(c.probe_name or "")
        if fn is None:
            continue
        try:
            kwargs: Dict[str, Any] = {"sim_type": sim_type}
            if c.probe_name == "regime_change":
                num = [x for x in df.columns if pd.api.types.is_numeric_dtype(df[x])]
                kwargs["col"] = num[0] if num else None
            elif c.probe_name == "joint_shift":
                num = [x for x in df.columns if pd.api.types.is_numeric_dtype(df[x])]
                kwargs["col_a"], kwargs["col_b"] = (num + [None, None])[:2]
            res = fn(df, **kwargs)
            c.probe_result = res if isinstance(res, dict) else {"result": str(res)}
            hit = _probe_supports(c.probe_result)
            if hit is True:
                c.status, c.confidence = "confirmed", 0.92
            elif hit is False:
                c.status, c.confidence = "refuted", 0.25
            else:
                c.status, c.confidence = "hypothesis", None
        except Exception as e:
            c.probe_result = {"error": str(e)}
            c.status, c.confidence = "hypothesis", None
    return causes


def _probe_supports(res: dict) -> Optional[bool]:
    """True = probe confirms, False = refutes, None = inconclusive."""
    if not isinstance(res, dict) or res.get("skipped") or res.get("error"):
        return None
    for k in ("violations", "n_violations", "n_duplicates", "n_flagged", "count"):
        v = res.get(k)
        if isinstance(v, (int, float)):
            return v > 0
    for k in ("detected", "shift_detected", "change_detected", "found"):
        if isinstance(res.get(k), bool):
            return res[k]
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# Phase E — narrative
# ═══════════════════════════════════════════════════════════════════════════════

_BANNED = re.compile(
    r"\b[\w/\\-]+\.(?:ya?ml|json|csv|py|txt|cfg|ini|xml|dat|log|inp)\b|line\s+\d+",
    re.I,
)


def narrate_deterministic(causes: List[RootCause], n_rows: int, n_excluded: int) -> str:
    if not causes:
        return (f"No root causes identified. {n_excluded} of {n_rows} trials were "
                "excluded by individual checks.")
    parts: List[str] = []
    for c in causes[:4]:
        marker = {"confirmed": "Confirmed", "refuted": "Refuted", "hypothesis": "Suspected"}[c.status]
        trials = ", ".join(str(t + 1) for t in c.affected_trials[:6])
        more = f" (+{len(c.affected_trials) - 6} more)" if len(c.affected_trials) > 6 else ""
        parts.append(f"{marker}: {c.label} affecting trial(s) {trials}{more}, "
                     f"originating at the {c.stage} stage. {c.action}")
    return " ".join(parts)


def narrate_ai(causes: List[RootCause], sim_type: str, n_rows: int,
               n_excluded: int, profile_summary: str) -> Tuple[str, str, Optional[str]]:
    """Returns (narrative, source, degradation_reason)."""
    det = narrate_deterministic(causes, n_rows, n_excluded)
    if not AI_ENABLED or not causes:
        return det, "deterministic", ("no API key" if not AI_ENABLED else None)

    payload = [{
        "cause": c.label, "status": c.status, "stage": c.stage,
        "trials_1based": [t + 1 for t in c.affected_trials[:10]],
        "evidence": c.evidence[:4],
        "probe_result": {k: v for k, v in (c.probe_result or {}).items()
                         if isinstance(v, (int, float, bool, str))},
    } for c in causes[:4]]

    prompt = f"""Write a short root-cause summary for a simulation engineer.

DATASET: {sim_type}, {n_rows} trials, {n_excluded} excluded. {profile_summary}

CONFIRMED AND SUSPECTED CAUSES:
{json.dumps(payload, indent=1)}

Rules — violating any of these makes the output unusable:
- Use ONLY the values, trial numbers and column names shown above.
- NEVER name a file, path, or line number. You do not know the file layout.
- Treat causes with status "confirmed" as fact; describe "hypothesis" as unconfirmed.
- Keep unrelated causes separate. Do not invent a link between them.
- 3-5 sentences. State what happened, where in the pipeline, and what to check first.

Respond ONLY with JSON: {{"summary":"..."}}"""

    try:
        parsed = _call_llm(prompt, MODEL_NARRATE, TIMEOUT_NARRATE, max_tokens=700)
        text = str(parsed.get("summary", "")).strip()
    except Exception as e:
        return det, "deterministic", f"narrative model unavailable ({type(e).__name__})"

    if len(text) < 40:
        return det, "deterministic", "narrative too short"
    if _BANNED.search(text):
        # The single most damaging hallucination: a plausible filename the
        # engineer will go looking for and never find.
        return det, "deterministic", "narrative referenced a file or line number"

    real = {str(t + 1) for c in causes for t in c.affected_trials}
    cited = set(re.findall(r"\btrial\s+(\d+)", text, re.I))
    if cited - real:
        return det, "deterministic", f"narrative cited trials not in findings: {sorted(cited - real)}"

    return text, "ai", None


# ═══════════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════════

def run_pipeline(df: pd.DataFrame, sim_type: str, physics_result: dict,
                 profile_summary: str = "", use_ai: bool = True) -> PipelineResult:
    """
    Cluster → verify → narrate. Never raises; degradations are reported, not thrown.
    """
    timings: Dict[str, float] = {}
    degraded: List[str] = []
    exclusions = physics_result.get("exclusions") or []
    n_rows = int(physics_result.get("trials_submitted") or len(df))
    n_excl = int(physics_result.get("trials_excluded") or len(
        {e.get("trial_index") for e in exclusions}))

    # Phase C
    t = time.time()
    det_causes = cluster_deterministic(exclusions)
    if use_ai and AI_ENABLED:
        causes, why = cluster_ai(exclusions, sim_type, profile_summary, det_causes)
        if why:
            degraded.append(f"clustering: {why}")
    else:
        causes, why = det_causes, None
        if use_ai and not AI_ENABLED:
            degraded.append("clustering: no API key")
    timings["cluster_ms"] = round((time.time() - t) * 1000, 1)

    # Phase D
    t = time.time()
    causes = verify(causes, df, sim_type)
    timings["verify_ms"] = round((time.time() - t) * 1000, 1)

    # Phase E
    t = time.time()
    if use_ai:
        narrative, src, why = narrate_ai(causes, sim_type, n_rows, n_excl, profile_summary)
        if why:
            degraded.append(f"narrative: {why}")
    else:
        narrative, src = narrate_deterministic(causes, n_rows, n_excl), "deterministic"
    timings["narrate_ms"] = round((time.time() - t) * 1000, 1)

    return PipelineResult(
        version=PIPELINE_VERSION,
        root_causes=causes,
        narrative=narrative,
        narrative_source=src,
        n_findings_in=len(exclusions),
        n_causes_out=len(causes),
        phase_timings=timings,
        degraded=degraded,
        model_cluster=MODEL_CLUSTER if AI_ENABLED else None,
        model_narrate=MODEL_NARRATE if AI_ENABLED else None,
    )
