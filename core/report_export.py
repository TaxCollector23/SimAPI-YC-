"""
SimAPI — Machine-readable validation-report export for CI gating.

A physics-validation report is only useful in a CI/CD pipeline if the pipeline
can *fail the build* on a bad result. The two formats CI systems already know
how to ingest are:

* **JUnit XML** — understood natively by GitHub Actions, GitLab CI, Jenkins,
  CircleCI, Azure Pipelines, Bitbucket. A non-zero ``failures`` count turns the
  step red and blocks the merge.
* **SARIF 2.1.0** — GitHub Code Scanning / advanced-security surface. Each
  physics finding becomes an annotation on the run.

Both converters are pure, deterministic functions over the public
``/v1/validate`` response dict: no network, no clock, no randomness, so the same
report always serializes to byte-identical output. That determinism is what
makes them safe to diff and safe to gate on.

Mapping rules (shared by both formats):
  * an issue with ``status == "failed"``   -> a failing check (error)
  * an issue with ``status == "warning"``  -> a warning; it fails the build only
                                              under ``strict_warnings``
  * every excluded (impossible/unsuitable) trial is summarised as one gating
    check so a physically-impossible dataset always trips the gate even when it
    produced no free-standing issue.
"""
from __future__ import annotations

import json
from typing import Any
from xml.sax.saxutils import escape, quoteattr

TOOL_NAME = "SimAPI"
TOOL_VERSION = "3.1.0"
INFORMATION_URI = "https://github.com/simapi"

# status -> SARIF level
_SARIF_LEVEL = {"failed": "error", "warning": "warning", "passed": "none"}


def _issues(result: dict[str, Any]) -> list[dict[str, Any]]:
    issues = result.get("issues")
    return issues if isinstance(issues, list) else []


def _is_gating_failure(status: str, strict_warnings: bool) -> bool:
    if status == "failed":
        return True
    if status == "warning" and strict_warnings:
        return True
    return False


def _gating_checks(result: dict[str, Any], strict_warnings: bool) -> list[dict[str, Any]]:
    """Flatten a validation report into a stable, ordered list of CI checks.

    Each check: ``{name, classname, category, status, message, detail, failed}``.
    The order is deterministic (issues in report order, then the synthetic
    dataset-level check) so exports are byte-stable across runs.
    """
    checks: list[dict[str, Any]] = []
    for i, issue in enumerate(_issues(result)):
        status = str(issue.get("status", "warning"))
        category = str(issue.get("category", "physics"))
        name = str(issue.get("human_name") or issue.get("name") or f"check_{i}")
        message = str(issue.get("description", name))
        detail = str(issue.get("detail", ""))
        checks.append({
            "name": name,
            "classname": f"{TOOL_NAME.lower()}.{category}",
            "category": category,
            "status": status,
            "message": message,
            "detail": detail,
            "failed": _is_gating_failure(status, strict_warnings),
            "ruleId": str(issue.get("name") or f"{category}.{i}"),
        })

    # Synthetic dataset-level gate: impossible/unsuitable trials are excluded
    # rather than surfaced as an issue, so without this a dataset that is 40%
    # physically impossible could still show zero failing testcases.
    trials_excluded = int(result.get("trials_excluded", 0) or 0)
    trials_submitted = int(result.get("trials_submitted", 0) or 0)
    training_ready = bool(result.get("training_ready", True))
    gate_failed = (not training_ready) or trials_excluded > 0
    checks.append({
        "name": "dataset.training_ready",
        "classname": f"{TOOL_NAME.lower()}.dataset",
        "category": "dataset",
        "status": "failed" if gate_failed else "passed",
        "message": "Dataset is physically valid and training-ready"
                   if not gate_failed else "Dataset has excluded / physically-invalid rows",
        "detail": f"{trials_excluded} of {trials_submitted} trial(s) excluded; "
                  f"training_ready={training_ready}.",
        "failed": gate_failed,
        "ruleId": "dataset.training_ready",
    })
    return checks


def to_junit_xml(
    result: dict[str, Any],
    *,
    strict_warnings: bool = False,
    suite_name: str = "SimAPI Physics Validation",
) -> str:
    """Render a ``/v1/validate`` result as a JUnit XML document.

    ``strict_warnings=True`` makes warning-level findings count as failures so a
    pipeline can gate on them too.
    """
    checks = _gating_checks(result, strict_warnings)
    total = len(checks)
    failures = sum(1 for c in checks if c["failed"])
    # processing_ms -> seconds; JUnit `time` is a float in seconds.
    time_s = round(float(result.get("processing_ms", 0.0) or 0.0) / 1000.0, 4)

    lines: list[str] = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append(
        f'<testsuites name={quoteattr(suite_name)} tests="{total}" '
        f'failures="{failures}" errors="0" time="{time_s}">'
    )
    lines.append(
        f'  <testsuite name={quoteattr(suite_name)} tests="{total}" '
        f'failures="{failures}" errors="0" skipped="0" time="{time_s}">'
    )
    for c in checks:
        lines.append(
            f'    <testcase name={quoteattr(c["name"])} '
            f'classname={quoteattr(c["classname"])} time="0">'
        )
        if c["failed"]:
            body = escape(c["detail"] or c["message"])
            lines.append(
                f'      <failure message={quoteattr(c["message"])} '
                f'type={quoteattr(c["category"])}>{body}</failure>'
            )
        elif c["status"] == "warning":
            # Non-gating warning: keep the testcase green but record the note so
            # it is still visible in CI logs.
            lines.append(f'      <system-out>{escape("WARNING: " + (c["detail"] or c["message"]))}</system-out>')
        lines.append("    </testcase>")
    lines.append("  </testsuite>")
    lines.append("</testsuites>")
    return "\n".join(lines) + "\n"


def to_sarif(result: dict[str, Any], *, strict_warnings: bool = False) -> dict[str, Any]:
    """Render a ``/v1/validate`` result as a SARIF 2.1.0 log (as a dict)."""
    checks = _gating_checks(result, strict_warnings)

    # De-duplicate rules by ruleId while preserving first-seen order.
    rules: list[dict[str, Any]] = []
    seen_rules: set[str] = set()
    sarif_results: list[dict[str, Any]] = []
    for c in checks:
        rule_id = c["ruleId"]
        if rule_id not in seen_rules:
            seen_rules.add(rule_id)
            rules.append({
                "id": rule_id,
                "name": c["category"],
                "shortDescription": {"text": c["name"]},
            })
        if c["status"] == "passed":
            continue  # SARIF results carry findings, not passes
        level = _SARIF_LEVEL.get(c["status"], "warning")
        if c["status"] == "warning" and strict_warnings:
            level = "error"
        sarif_results.append({
            "ruleId": rule_id,
            "level": level,
            "message": {"text": c["detail"] or c["message"]},
            "properties": {"category": c["category"], "status": c["status"]},
        })

    return {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [{
            "tool": {
                "driver": {
                    "name": TOOL_NAME,
                    "version": TOOL_VERSION,
                    "informationUri": INFORMATION_URI,
                    "rules": rules,
                }
            },
            "results": sarif_results,
        }],
    }


def to_sarif_json(result: dict[str, Any], *, strict_warnings: bool = False, indent: int | None = None) -> str:
    """Convenience: SARIF as a JSON string with stable key order."""
    return json.dumps(to_sarif(result, strict_warnings=strict_warnings), indent=indent, sort_keys=False)
