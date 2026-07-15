"""Pre-simulation (mesh + setup) validation tests."""
from core.mesh_validator import MeshValidator, humanize_mesh_check_name

_GOOD = {
    "geometry": {"characteristic_length": 1.0},
    "flow_conditions": {"inlet_velocity": 15.0, "reynolds_number": 1_000_000,
                        "mach_number": 0.044, "temperature": 293.15,
                        "pressure": 101325.0, "density": 1.225},
    "mesh": {"total_cells": 2_000_000, "min_cell_quality": 0.4,
             "max_non_orthogonality": 60.0, "max_skewness": 0.6,
             "max_aspect_ratio": 80.0, "has_boundary_layers": True,
             "boundary_layer_growth_ratio": 1.2, "estimated_yplus": 1.0},
    "solver_settings": {"turbulence_model": "kOmegaSST", "discretization_order": 2,
                        "max_iterations": 2000, "convergence_tolerance": 1e-5,
                        "max_cfl": 0.8, "relaxation_velocity": 0.7, "relaxation_pressure": 0.3},
    "boundary_conditions": {"inlet": "velocityInlet", "outlet": "pressureOutlet", "walls": "noSlip"},
}


def _bad():
    cfg = {k: dict(v) if isinstance(v, dict) else v for k, v in _GOOD.items()}
    cfg["mesh"] = {**_GOOD["mesh"], "estimated_yplus": 45.0, "max_non_orthogonality": 88.0, "max_aspect_ratio": 2000.0}
    cfg["solver_settings"] = {**_GOOD["solver_settings"], "discretization_order": 1, "convergence_tolerance": 1e-3}
    return cfg


def test_mesh_validator_good_config_ready():
    r = MeshValidator().validate(_GOOD)
    assert r.status in ("ready", "warning")
    assert r.all_checks_count > 10
    assert r.processing_ms < 200  # strict budget
    assert r.estimated_corruption_risk <= 0.2


def test_mesh_validator_bad_config_not_ready():
    r = MeshValidator().validate(_bad())
    assert r.status == "not_ready"
    names = {i.name for i in r.issues}
    assert "mesh_yplus_model_compat" in names   # y+=45 with k-omega SST
    assert "mesh_nonortho" in names              # 88° unacceptable
    assert r.estimated_corruption_risk > 0.3
    assert r.predicted_error_types               # non-empty predictions


def test_humanize_mesh_check_name():
    assert "y+" in humanize_mesh_check_name("mesh_yplus_model_compat")
    assert humanize_mesh_check_name("mesh_unknown_check")  # falls back, no crash


def test_setup_endpoint_contract(client):
    r = client.post("/v1/validate/setup", json={"config": _bad(), "solver": "openfoam",
                                                "physics": "fluid", "simulation_type": "aerodynamics"})
    assert r.status_code == 200
    b = r.json()
    assert b["status"] == "not_ready"
    assert isinstance(b["predicted_error_types"], list) and b["predicted_error_types"]
    assert isinstance(b["recommendations"], list)
    assert 0.0 <= b["estimated_corruption_risk"] <= 1.0
    # issue-surfacing: only warnings + failures, each with a human_name
    assert all(i["status"] in ("warning", "failed") for i in b["issues"])
    assert all(i.get("human_name") for i in b["issues"])


def test_setup_endpoint_compressibility(client):
    cfg = {**_GOOD, "compressible": False,
           "flow_conditions": {**_GOOD["flow_conditions"], "mach_number": 0.6}}
    b = client.post("/v1/validate/setup", json={"config": cfg}).json()
    assert any(i["name"] == "mesh_compressibility" for i in b["issues"])
