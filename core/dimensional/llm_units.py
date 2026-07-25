"""
Layer 0 LLM fallback -- classifies columns the dictionary resolver
couldn't (real solver output has effectively unlimited naming variety;
no static dictionary covers all of it).

Reuses the same multi-key OpenRouter fallback chain pattern already
proven elsewhere in this codebase (core/ai_validator.py): several
independent (key, model) pairs, since a single free-tier model/account can
hit its daily quota or return blank content for reasons unrelated to
whether the request itself was fine.

Graceful degradation is mandatory, not optional: if no key is configured,
if the network call fails, or if the model returns something unparseable,
this returns an empty dict and Layer 0 falls back to "unresolved" for
those columns -- which is a normal, handled state (they pass through to
Layer 5), not an error. "The LLM proposes, linear algebra disposes":
whatever this returns is still subject to the same |e|<=6 / half-integer
/ numeric-verification gate as a dictionary match before it can create an
accepted law, so a wrong guess here degrades to a units_conflict finding
at worst, never a corrupted validation result.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from .dimensions import BASE_DIMENSIONS

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
TIMEOUT_SECONDS = 8
# Hard ceiling on the WHOLE fallback chain, not per attempt. Without this the
# per-attempt timeout multiplies by the number of (key, model) pairs: measured
# 74s on a live request where every model failed on an unresolvable column,
# because 6 attempts x 12s each all ran to completion. Layer 0 is an optional
# enrichment -- unresolved columns are a normal, handled state -- so it must
# never dominate request latency. Whatever the chain has produced when the
# budget runs out is what gets used.
TOTAL_BUDGET_SECONDS = 20
_DIM_KEYS = sorted(BASE_DIMENSIONS.keys())

_SYSTEM_PROMPT = f"""You are classifying engineering-simulation column names by physical dimension.

For each column name given, identify:
1. Which physical quantity it represents, from EXACTLY this list of dimension keys: {", ".join(_DIM_KEYS)}
2. Your confidence (0.0-1.0) -- lower if the name is ambiguous or you're guessing.
3. If the name implies a NON-SI unit (e.g. a "_psi", "_degF", "_ft" suffix, or a
   name you recognize as conventionally imperial), name the unit using one of:
   psi, bar, atm, mmhg, torr, kpa, mpa, degf, degc, rankine, ft, inch, yard, mile,
   nmi, slug_ft3, lbm_ft3, lbf, lbm, slug, rpm, deg, gpm, hp, btu, cal, knot, mph.
   Otherwise omit unit (assume SI).

Real solver output uses terse/abbreviated names: Cd, p_static, U_mag, rho_inf, nut,
yPlus, tau_wall, Re_c -- these are typical, not exceptions.

Respond ONLY with JSON: {{"column_name": {{"dimension_key": "...", "confidence": 0.0-1.0, "unit": "..." or null}}, ...}}
If you cannot classify a column at all, omit it from the response entirely."""

_MODEL_CHAIN_TEMPLATE = [
    "nvidia/nemotron-nano-9b-v2:free",
    "openai/gpt-oss-20b:free",
    "google/gemma-4-31b-it:free",
]


def _build_key_model_chain() -> list[tuple[str, str]]:
    chain: list[tuple[str, str]] = []
    key1 = os.environ.get("SIMAPI_OPENROUTER_API_KEY", "")
    key2 = os.environ.get("SIMAPI_OPENROUTER_API_KEY_2", "")
    if key1:
        chain += [(key1, m) for m in _MODEL_CHAIN_TEMPLATE]
    if key2:
        chain += [(key2, m) for m in _MODEL_CHAIN_TEMPLATE]
    return chain


def _call_model(columns: list[str], model: str, key: str,
                 timeout: float = TIMEOUT_SECONDS) -> dict | None:
    body = json.dumps({
        "model": model,
        "max_tokens": min(2000, 60 * len(columns) + 200),
        "temperature": 0.0,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": "Columns: " + ", ".join(columns)},
        ],
    }).encode("utf-8")
    req = urllib.request.Request(
        OPENROUTER_URL, data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "HTTP-Referer": "https://simapi.dev", "X-Title": "SimAPI"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError):
        return None
    content = raw.get("choices", [{}])[0].get("message", {}).get("content")
    if not content:
        return None
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        end = -1 if lines[-1].strip() in ("```", "```json") else len(lines)
        content = "\n".join(lines[1:end])
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start, end = content.find("{"), content.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            return json.loads(content[start:end + 1])
        except json.JSONDecodeError:
            return None


def llm_resolve_columns(columns: list[str]) -> dict[str, dict]:
    """Classify `columns` via an LLM fallback chain. Returns {} (never
    raises) if no key is configured or every model in the chain fails --
    that's a normal, handled outcome, not an error."""
    if not columns:
        return {}
    chain = _build_key_model_chain()
    if not chain:
        return {}
    deadline = time.monotonic() + TOTAL_BUDGET_SECONDS
    for key, model in chain:
        remaining = deadline - time.monotonic()
        if remaining <= 1.0:
            break  # out of budget; unresolved columns fall through to Layer 5
        result = _call_model(columns, model, key, timeout=min(TIMEOUT_SECONDS, remaining))
        if result is None:
            continue
        # Only keep entries with a dimension key we actually know about.
        cleaned = {
            col: info for col, info in result.items()
            if isinstance(info, dict) and info.get("dimension_key") in BASE_DIMENSIONS
        }
        if cleaned:
            return cleaned
    return {}
