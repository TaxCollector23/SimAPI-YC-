"""
Persistent cache for LLM-resolved column units.

Without this, `llm_units.llm_resolve_columns` re-asks the LLM for the same
unusual column name every time it appears in a request -- across different
datasets, different users, forever. That's wasteful (network round-trip on
every request), slow (up to TOTAL_BUDGET_SECONDS added to latency), and it
means an unusual variable name is never actually *learned* -- just
repeatedly re-guessed from scratch.

This cache is what turns "call an LLM to classify an unknown column" into
"temporarily extend the units dictionary": the first time a column like
`tau_wall_shear` or `q_dyn` is seen, it costs an LLM call. Every time after
that, for that exact column name, it's a cache hit -- effectively behaving
like a locally-learned dictionary entry, without needing a code change or
a deploy to add it to the real static dictionary in units_resolver.py.

Design notes:
  - Keyed by the RAW column name, not a normalized form. Two datasets using
    "tau_wall" and "Tau_Wall" are different keys -- normalization happens
    on the dictionary-match path (units_resolver.py's own _normalize), not
    here, so a cache hit is always an exact, previously-seen name, never a
    fuzzy match that could silently misapply a mapping to a lookalike column
    from a different domain.
  - Never authoritative on its own: same as a fresh LLM answer, a cached
    entry still goes through Layer 2/3 verification (a units_conflict
    finding is raised if a discovered law contradicts it). Caching a wrong
    guess doesn't make it more trusted, just cheaper to repeat.
  - Graceful degradation is mandatory: any read/write/parse failure (no
    write permission, corrupt file, concurrent-write race) falls back to
    "no cache", never raises, and never blocks resolution.
  - File-based, single-process-friendly. For a multi-replica deployment,
    point SIMAPI_UNITS_CACHE_PATH at a shared/networked path, or swap this
    module's storage for a proper key-value store behind the same
    get/store interface -- the caller (engine.py) doesn't need to change.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

_DEFAULT_PATH = Path.home() / ".simapi" / "learned_units_cache.json"
_lock = threading.Lock()


def _cache_path() -> Path:
    override = os.environ.get("SIMAPI_UNITS_CACHE_PATH")
    return Path(override) if override else _DEFAULT_PATH


def _read_all() -> dict[str, dict]:
    path = _cache_path()
    try:
        if not path.exists():
            return {}
        return json.loads(path.read_text())
    except Exception:
        # Corrupt file, permission error, race with a concurrent writer --
        # any of these degrade to "cache is empty", not a crash.
        return {}


def _write_all(data: dict[str, dict]) -> None:
    path = _cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(path)  # atomic on POSIX; avoids a torn/corrupt file on crash
    except Exception:
        pass  # caching is a pure optimization; never let it break resolution


def get_cached(columns: list[str]) -> dict[str, dict]:
    """Return cached entries for whichever of `columns` have been seen
    before. Columns not in the cache are simply absent from the result --
    callers pass the remainder to the LLM as usual."""
    if not columns:
        return {}
    with _lock:
        all_entries = _read_all()
    return {c: all_entries[c]["info"] for c in columns if c in all_entries}


def store(resolved: dict[str, dict]) -> None:
    """Persist freshly LLM-resolved columns for reuse by future requests.
    `resolved` is the same {column: {dimension_key, confidence, unit}}
    shape llm_resolve_columns returns."""
    if not resolved:
        return
    with _lock:
        all_entries = _read_all()
        now = time.time()
        for col, info in resolved.items():
            existing = all_entries.get(col)
            times_seen = (existing.get("times_seen", 0) + 1) if existing else 1
            all_entries[col] = {
                "info": info,
                "first_seen": existing.get("first_seen", now) if existing else now,
                "last_seen": now,
                "times_seen": times_seen,
            }
        _write_all(all_entries)


def stats() -> dict:
    """Summary for introspection (e.g. `simapi doctor`, an admin endpoint):
    how many columns has this deployment learned, and which are used most."""
    with _lock:
        all_entries = _read_all()
    by_uses = sorted(all_entries.items(), key=lambda kv: -kv[1].get("times_seen", 0))
    return {
        "path": str(_cache_path()),
        "n_learned_columns": len(all_entries),
        "most_used": [{"column": c, "times_seen": v.get("times_seen", 0),
                       "dimension_key": v.get("info", {}).get("dimension_key")}
                      for c, v in by_uses[:20]],
    }
