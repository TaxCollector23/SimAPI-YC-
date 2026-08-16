"""Tests for JUnit / SARIF validation-report export (CI gating)."""
from xml.etree import ElementTree as ET

from core.report_export import to_junit_xml, to_sarif, to_sarif_json


def _failing_result():
    return {
        "status": "failed",
        "trials_submitted": 100,
        "trials_excluded": 7,
        "training_ready": False,
        "processing_ms": 1234.5,
        "issues": [
            {"name": "anchored_constant:R_air", "human_name": "Violates a known physical constant",
             "status": "failed", "description": "P/(rho*T) = 287.05",
             "detail": "6 row(s) affected, coverage 94%.", "category": "anchored_constant"},
            {"name": "structural:near_duplicate", "human_name": "Contains near-duplicate rows",
             "status": "warning", "description": "near duplicate",
             "detail": "3 row(s).", "category": "structural"},
        ],
    }


def _clean_result():
    return {
        "status": "passed",
        "trials_submitted": 50,
        "trials_excluded": 0,
        "training_ready": True,
        "processing_ms": 12.0,
        "issues": [],
    }


# ── JUnit ────────────────────────────────────────────────────────────────────
def test_junit_is_wellformed_xml():
    xml = to_junit_xml(_failing_result())
    root = ET.fromstring(xml)  # raises on malformed XML
    assert root.tag == "testsuites"


def test_junit_counts_failures_and_gates_on_failed():
    xml = to_junit_xml(_failing_result())
    root = ET.fromstring(xml)
    suite = root.find("testsuite")
    # 2 issues + 1 synthetic dataset gate = 3 testcases.
    assert suite.get("tests") == "3"
    # failed issue + failing dataset gate = 2 failures; warning is NOT gated.
    assert suite.get("failures") == "2"
    failures = root.findall(".//failure")
    assert len(failures) == 2


def test_junit_strict_gates_on_warnings():
    xml = to_junit_xml(_failing_result(), strict_warnings=True)
    root = ET.fromstring(xml)
    # Now the warning testcase also fails: 3 failures total.
    assert root.find("testsuite").get("failures") == "3"


def test_junit_clean_dataset_has_zero_failures():
    xml = to_junit_xml(_clean_result())
    root = ET.fromstring(xml)
    suite = root.find("testsuite")
    assert suite.get("failures") == "0"
    # The lone testcase is the passing dataset gate.
    assert suite.get("tests") == "1"
    assert root.findall(".//failure") == []


def test_junit_escapes_special_characters():
    result = _clean_result()
    result["issues"] = [{
        "name": "x", "human_name": 'bad & <name> "q"', "status": "failed",
        "description": "a < b & c", "detail": "1 < 2 & 3 > 0", "category": "structural",
    }]
    result["status"] = "failed"
    xml = to_junit_xml(result)
    root = ET.fromstring(xml)  # would raise if escaping were wrong
    assert root is not None


def test_junit_is_deterministic():
    r = _failing_result()
    assert to_junit_xml(r) == to_junit_xml(r)


# ── SARIF ────────────────────────────────────────────────────────────────────
def test_sarif_structure_and_levels():
    sarif = to_sarif(_failing_result())
    assert sarif["version"] == "2.1.0"
    run = sarif["runs"][0]
    assert run["tool"]["driver"]["name"] == "SimAPI"
    results = run["results"]
    # failed issue + failing dataset gate surface as results; the warning does too
    # (as level "warning"). Passing results are omitted.
    levels = sorted(r["level"] for r in results)
    assert "error" in levels
    assert "warning" in levels


def test_sarif_clean_dataset_has_no_results():
    sarif = to_sarif(_clean_result())
    assert sarif["runs"][0]["results"] == []


def test_sarif_json_is_valid_and_deterministic():
    import json
    s1 = to_sarif_json(_failing_result())
    s2 = to_sarif_json(_failing_result())
    assert s1 == s2
    json.loads(s1)  # valid JSON


# ── Endpoint wiring ──────────────────────────────────────────────────────────
def test_report_endpoint_junit(client, sample_payload):
    r = client.post("/v1/validate/report", json=sample_payload)
    assert r.status_code == 200
    assert "application/xml" in r.headers["content-type"]
    root = ET.fromstring(r.text)
    assert root.tag == "testsuites"


def test_report_endpoint_sarif(client, sample_payload):
    r = client.post("/v1/validate/report?format=sarif", json=sample_payload)
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "2.1.0"
    assert "runs" in body


def test_report_endpoint_rejects_unknown_format(client, sample_payload):
    r = client.post("/v1/validate/report?format=toml", json=sample_payload)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "bad_request"
