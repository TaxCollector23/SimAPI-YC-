"""
SimAPI — Pre-Simulation Mesh & Setup Validation Layer.

Validates a simulation *configuration* (mesh quality metrics + boundary
conditions + solver settings + physics models) BEFORE the run, and predicts
which downstream SimAPI output checks are likely to fail. This is the input-side
mirror of ``PhysicsValidator``: same terse ``_c``/``_w``/``_r`` helper pattern,
``mesh_`` prefixed check names, issue-surfacing (only warnings + failures leave
the API), and a strict no-external-calls budget (<200ms).
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any


# ── Dataclasses ─────────────────────────────────────────────────────────────────
@dataclass
class MeshCheck:
    name: str
    status: str                       # "passed" | "warning" | "failed"
    description: str
    detail: str = ""
    value: float | None = None
    threshold: float | None = None
    category: str = "general"


@dataclass
class MeshValidationReport:
    status: str                       # "ready" | "warning" | "not_ready"
    checks: list[MeshCheck]
    issues: list[MeshCheck]           # warnings + failures only
    all_checks_count: int
    passed_count: int
    warning_count: int
    failed_count: int
    predicted_error_types: list[str]  # SimAPI output checks likely to fail
    estimated_corruption_risk: float  # 0-1
    recommendations: list[str]
    processing_ms: float


# ── Human-readable check names (mirrors humanize_check_name) ─────────────────────
_HUMAN: dict[str, str] = {
    "mesh_yplus_model_compat": "Near-wall resolution (y+) matches the turbulence model",
    "mesh_aspect_ratio": "Cell aspect ratio within numerically safe limits",
    "mesh_nonortho": "Mesh non-orthogonality within solver limits",
    "mesh_skewness": "Cell skewness below degeneracy threshold",
    "mesh_cell_count_adequacy": "Cell count sufficient to resolve the flow",
    "mesh_boundary_layer_present": "Structured inflation layer present at walls",
    "mesh_boundary_layer_growth": "Boundary-layer growth ratio ≤ 1.3",
    "mesh_volume_ratio": "Adjacent cell volume ratio within limits",
    "mesh_watertight": "Surface mesh is watertight (no open edges/self-intersections)",
    "mesh_min_cell_quality": "Minimum cell quality above the solver threshold",
    "mesh_bc_inlet_outlet_consistency": "Inlet/outlet boundary conditions are consistent",
    "mesh_bc_pressure_gradient": "Pressure inlet/outlet gradient drives flow correctly",
    "mesh_bc_reynolds_turbulence_match": "Turbulence model matches the Reynolds regime",
    "mesh_bc_symmetry_geometry": "Symmetry plane matches geometry symmetry",
    "mesh_bc_wall_coverage": "All solid surfaces have wall boundary conditions",
    "mesh_bc_periodic_match": "Periodic boundary faces match",
    "mesh_bc_reference_values": "Reference velocity/pressure/density are self-consistent",
    "mesh_cfl_explicit": "Timestep satisfies the CFL condition",
    "mesh_turbulence_model_appropriate": "Turbulence model is appropriate for the flow",
    "mesh_convergence_criterion": "Convergence residual targets are tight enough",
    "mesh_discretization_order": "Discretization order high enough for accuracy",
    "mesh_relaxation_factors": "Relaxation factors in the stable range",
    "mesh_max_iterations": "Iteration budget adequate for convergence",
    "mesh_output_interval": "Output interval balances I/O and monitoring",
    "mesh_compressibility": "Compressible/incompressible assumption matches Mach number",
    "mesh_heat_transfer_model": "Heat-transfer model enabled for thermal BCs",
    "mesh_radiation_model": "Radiation modeled at high temperature",
    "mesh_buoyancy_model": "Buoyancy modeled for large temperature differences",
    "mesh_multiphase_model": "Multiphase model enabled for two-fluid setups",
    "mesh_combustion_model": "Combustion model enabled for fuel/oxidizer inlets",
    "mesh_mhd_model": "MHD enabled when magnetic fields are present",
}


def humanize_mesh_check_name(name: str) -> str:
    """Plain-English label for a mesh check (falls back to the raw name)."""
    if name in _HUMAN:
        return _HUMAN[name]
    # window-suffixed or dynamic names → strip and prettify
    base = name.split("__")[0]
    return _HUMAN.get(base, name.replace("mesh_", "").replace("_", " ").capitalize())


# ── Validator ────────────────────────────────────────────────────────────────────
class MeshValidator:
    """Deterministic pre-flight validator. No external calls; <200ms."""

    def __init__(self) -> None:
        self.checks_run = 0
        self.total_processing_ms = 0.0

    # helper pattern mirrors PhysicsValidator
    def _c(self, n, ok, desc, det="", v=None, t=None, cat="general") -> MeshCheck:
        return MeshCheck(n, "passed" if ok else "failed", desc, det, v, t, cat)

    def _w(self, n, ok, desc, det="", v=None, t=None, cat="general") -> MeshCheck:
        return MeshCheck(n, "passed" if ok else "warning", desc, det, v, t, cat)

    def _r(self, C: list[MeshCheck]) -> list[MeshCheck]:
        return C

    def validate(
        self,
        config: dict[str, Any],
        mesh_stats: dict[str, Any] | None = None,
        solver: str = "openfoam",
        physics: str = "fluid",
        simulation_type: str = "aerodynamics",
    ) -> MeshValidationReport:
        t0 = time.time()
        config = config or {}
        geo = config.get("geometry", {}) or {}
        flow = config.get("flow_conditions", {}) or {}
        mesh = {**(config.get("mesh", {}) or {}), **(mesh_stats or {})}
        solv = config.get("solver_settings", {}) or {}
        bc = config.get("boundary_conditions", {}) or {}
        solver = (config.get("solver") or solver or "openfoam").lower()
        physics = (config.get("physics") or physics or "fluid").lower()

        ctx = _Ctx(config, geo, flow, mesh, solv, bc, solver, physics, simulation_type)

        checks: list[MeshCheck] = []
        for layer in (
            self._mesh_quality, self._boundary_conditions, self._solver_config,
            self._physics_models,
        ):
            try:
                checks.extend(layer(ctx))
            except Exception:  # a malformed sub-config must never 500 the layer
                continue

        passed = [c for c in checks if c.status == "passed"]
        warned = [c for c in checks if c.status == "warning"]
        failed = [c for c in checks if c.status == "failed"]
        issues = warned + failed

        if failed:
            status = "not_ready"
        elif warned:
            status = "warning"
        else:
            status = "ready"

        predicted = self._predict_output_errors(ctx, issues)
        risk = self._corruption_risk(len(passed), warned, failed)
        recs = self._recommendations(issues)

        ms = (time.time() - t0) * 1000
        self.checks_run += 1
        self.total_processing_ms += ms

        return MeshValidationReport(
            status=status, checks=checks, issues=issues,
            all_checks_count=len(checks), passed_count=len(passed),
            warning_count=len(warned), failed_count=len(failed),
            predicted_error_types=predicted, estimated_corruption_risk=round(risk, 3),
            recommendations=recs, processing_ms=round(ms, 2),
        )

    # ── Category 1: Mesh quality ──────────────────────────────────────────────────
    def _mesh_quality(self, c: _Ctx) -> list[MeshCheck]:
        C: list[MeshCheck] = []
        m, cat = c.mesh, "mesh_quality"
        model = str(c.solv.get("turbulence_model", "")).lower()

        # y+ compatibility with the turbulence model
        yp = _f(m.get("estimated_yplus"))
        if yp is not None and model:
            low_re = any(k in model for k in ("komega", "sst", "spalart", "sa"))
            if low_re:
                C.append(self._c("mesh_yplus_model_compat", yp <= 5,
                    "Low-Re model requires y+≈1",
                    f"y+={yp:.1f} with {model}: needs y+≲1 (≤5 acceptable); wall not resolved" if yp > 5
                    else f"y+={yp:.1f} resolves the wall for {model}", yp, 1.0, cat))
            else:  # wall-function models (k-epsilon)
                ok = 30 <= yp <= 300
                C.append(self._w("mesh_yplus_model_compat", ok,
                    "Wall functions require 30<y+<300",
                    f"y+={yp:.1f} outside the wall-function range 30–300 for {model}" if not ok
                    else f"y+={yp:.1f} valid for wall functions", yp, 300.0, cat))

        ar = _f(m.get("max_aspect_ratio"))
        if ar is not None:
            C.append(self._c("mesh_aspect_ratio", ar <= 1000,
                "Aspect ratio ≤ 1000",
                f"max AR={ar:.0f} exceeds 1000 — numerical diffusion + slow convergence" if ar > 1000
                else f"max AR={ar:.0f} within limits", ar, 1000.0, cat) if ar > 1000
                else self._w("mesh_aspect_ratio", ar <= 100,
                    "Aspect ratio ≤ 100 (ideal)",
                    f"max AR={ar:.0f} is high (>100) — watch convergence" if ar > 100 else "", ar, 100.0, cat))

        no = _f(m.get("max_non_orthogonality"))
        if no is not None:
            if no > 85:
                C.append(self._c("mesh_nonortho", False, "Non-orthogonality ≤ 85°",
                    f"max non-orthogonality {no:.0f}° is unacceptable (>85°) for most solvers", no, 85.0, cat))
            else:
                C.append(self._w("mesh_nonortho", no <= 70, "Non-orthogonality ≤ 70°",
                    f"max non-orthogonality {no:.0f}° degrades accuracy (>70°) — add non-ortho correctors" if no > 70 else "",
                    no, 70.0, cat))

        sk = _f(m.get("max_skewness"))
        if sk is not None:
            if sk > 0.95:
                C.append(self._c("mesh_skewness", False, "Skewness ≤ 0.95",
                    f"max skewness {sk:.2f} is degenerate (>0.95)", sk, 0.95, cat))
            else:
                C.append(self._w("mesh_skewness", sk <= 0.85, "Skewness ≤ 0.85",
                    f"max skewness {sk:.2f} exceeds 0.85 warning threshold" if sk > 0.85 else "", sk, 0.85, cat))

        # Cell-count adequacy vs Reynolds number
        cells = _f(m.get("total_cells"))
        re = _f(c.flow.get("reynolds_number"))
        if cells is not None and re is not None and re > 0:
            # RANS empirical guideline: ~Re^(9/4) is DNS; RANS needs far less but
            # scales with log(Re). Flag clearly under-resolved meshes.
            rec_min = max(50_000, 20_000 * math.log10(max(re, 10)))
            C.append(self._w("mesh_cell_count_adequacy", cells >= rec_min,
                "Cell count adequate for the Reynolds number",
                f"{int(cells):,} cells may under-resolve Re={re:.0f} (guideline ≳{int(rec_min):,})" if cells < rec_min
                else f"{int(cells):,} cells adequate for Re={re:.0f}", cells, rec_min, cat))

        # Boundary-layer inflation
        has_bl = m.get("has_boundary_layers")
        if has_bl is not None:
            walls = str(c.bc.get("walls", "")).lower()
            wall_bounded = c.physics == "fluid" and ("noslip" in walls or "wall" in walls or not walls)
            C.append(self._w("mesh_boundary_layer_present", bool(has_bl) or not wall_bounded,
                "Structured inflation layer at walls",
                "No boundary-layer mesh at walls — near-wall gradients will be under-resolved" if (not has_bl and wall_bounded) else "",
                cat=cat))
            gr = _f(m.get("boundary_layer_growth_ratio"))
            if has_bl and gr is not None:
                C.append(self._w("mesh_boundary_layer_growth", gr <= 1.3,
                    "Boundary-layer growth ratio ≤ 1.3",
                    f"growth ratio {gr:.2f} > 1.3 — abrupt near-wall cell size jumps" if gr > 1.3 else "", gr, 1.3, cat))

        vr = _f(m.get("max_volume_ratio"))
        if vr is not None:
            C.append(self._w("mesh_volume_ratio", vr <= 10,
                "Adjacent cell volume ratio ≤ 10:1",
                f"volume ratio {vr:.1f}:1 (>10:1) causes interpolation errors" if vr > 10 else "", vr, 10.0, cat))

        # Watertight (surface meshes)
        oe = _f(m.get("open_edges"))
        si = _f(m.get("self_intersections"))
        dup = _f(m.get("duplicate_faces"))
        if any(x is not None for x in (oe, si, dup)):
            bad = (oe or 0) + (si or 0) + (dup or 0)
            C.append(self._c("mesh_watertight", bad == 0, "Surface mesh watertight",
                f"non-watertight: {int(oe or 0)} open edges, {int(si or 0)} self-intersections, "
                f"{int(dup or 0)} duplicate faces" if bad else "watertight", bad, 0.0, cat))

        mq = _f(m.get("min_cell_quality"))
        if mq is not None:
            thr = 0.1 if c.solver in ("openfoam", "su2") else 0.05
            C.append(self._c("mesh_min_cell_quality", mq >= thr,
                f"Minimum cell quality ≥ {thr}",
                f"min cell quality {mq:.3f} below the {c.solver} threshold {thr}" if mq < thr else "", mq, thr, cat))
        return self._r(C)

    # ── Category 2: Boundary conditions ──────────────────────────────────────────
    def _boundary_conditions(self, c: _Ctx) -> list[MeshCheck]:
        C: list[MeshCheck] = []
        bc, flow, cat = c.bc, c.flow, "boundary_conditions"
        inlet = str(bc.get("inlet", "")).lower()
        outlet = str(bc.get("outlet", "")).lower()

        if inlet and outlet:
            both_vel = "velocity" in inlet and "velocity" in outlet
            C.append(self._c("mesh_bc_inlet_outlet_consistency", not both_vel,
                "Inlet/outlet not overdetermined",
                "velocity fixed at BOTH inlet and outlet — overdetermined, no pressure reference" if both_vel
                else f"{inlet} → {outlet} is a consistent pairing", cat=cat))
            if "pressure" in inlet and "pressure" in outlet:
                pin = _f(flow.get("inlet_pressure"))
                pout = _f(flow.get("outlet_pressure"))
                if pin is not None and pout is not None:
                    C.append(self._c("mesh_bc_pressure_gradient", pin > pout,
                        "Pressure drop drives flow inlet→outlet",
                        f"inlet P={pin:.0f} ≤ outlet P={pout:.0f}: flow would reverse or stall" if pin <= pout else "",
                        pin - pout, 0.0, cat))

        # Reynolds regime vs turbulence model
        re = _f(flow.get("reynolds_number"))
        model = str(c.solv.get("turbulence_model", "")).lower()
        if re is not None:
            laminar = re < 2300
            has_turb = bool(model) and model not in ("laminar", "none")
            if laminar and has_turb:
                C.append(self._w("mesh_bc_reynolds_turbulence_match", False,
                    "Turbulence model matches Re regime",
                    f"Re={re:.0f} is laminar (<2300) but a turbulence model ({model}) is active", re, 2300.0, cat))
            elif not laminar and re > 4000 and not has_turb:
                C.append(self._c("mesh_bc_reynolds_turbulence_match", False,
                    "Turbulence model matches Re regime",
                    f"Re={re:.0f} is turbulent (>4000) but no turbulence model is set", re, 4000.0, cat))

        # Symmetry plane vs geometry
        if any("symmetry" in str(v).lower() for v in bc.values()):
            geo = c.geo
            w, h = _f(geo.get("domain_width")), _f(geo.get("domain_height"))
            sym = geo.get("is_symmetric")
            if sym is False:
                C.append(self._c("mesh_bc_symmetry_geometry", False,
                    "Symmetry plane matches geometry",
                    "symmetry BC applied but geometry is flagged asymmetric", cat=cat))
            elif sym is None and w is not None and h is not None:
                # can't confirm; surface an informational warning only if clearly odd
                pass

        # Wall coverage
        n_surf = _f(c.mesh.get("surface_count"))
        n_assigned = _f(c.mesh.get("assigned_bc_count"))
        if n_surf is not None and n_assigned is not None:
            C.append(self._c("mesh_bc_wall_coverage", n_assigned >= n_surf,
                "All surfaces have boundary conditions",
                f"{int(n_surf - n_assigned)} of {int(n_surf)} surfaces have no BC assigned" if n_assigned < n_surf else "",
                n_surf - n_assigned, 0.0, cat))

        # Periodic face matching
        pf1 = _f(c.mesh.get("periodic_faces_a"))
        pf2 = _f(c.mesh.get("periodic_faces_b"))
        if pf1 is not None and pf2 is not None:
            C.append(self._c("mesh_bc_periodic_match", abs(pf1 - pf2) < 1,
                "Periodic boundary faces match",
                f"periodic face count mismatch: {int(pf1)} vs {int(pf2)}" if abs(pf1 - pf2) >= 1 else "", cat=cat))

        # Reference value consistency (ideal gas)
        p, rho, T = _f(flow.get("pressure")), _f(flow.get("density")), _f(flow.get("temperature"))
        if p and rho and T:
            R = p / (rho * T)
            C.append(self._w("mesh_bc_reference_values", 250 <= R <= 320,
                "Reference P/ρ/T self-consistent (ideal gas)",
                f"P/(ρT)={R:.1f} deviates from R_air=287 — likely a unit mismatch in reference values" if not (250 <= R <= 320) else "",
                R, 287.0, cat))
        return self._r(C)

    # ── Category 3: Solver configuration ─────────────────────────────────────────
    def _solver_config(self, c: _Ctx) -> list[MeshCheck]:
        C: list[MeshCheck] = []
        s, cat = c.solv, "solver_config"

        cfl = _f(s.get("max_cfl"))
        explicit = bool(s.get("explicit")) or str(s.get("time_scheme", "")).lower() == "explicit"
        if cfl is not None:
            limit = 1.0 if explicit else 50.0
            C.append(self._c("mesh_cfl_explicit", cfl <= limit,
                f"CFL ≤ {limit:.0f} ({'explicit' if explicit else 'implicit'})",
                f"max CFL={cfl:.2f} exceeds {limit:.0f} for an {'explicit' if explicit else 'implicit'} solver — divergence risk" if cfl > limit else "",
                cfl, limit, cat))

        model = str(s.get("turbulence_model", "")).lower()
        st = c.simulation_type.lower()
        if model:
            external = st in ("aerodynamics", "aeroelasticity")
            if external and "epsilon" in model:
                C.append(self._w("mesh_turbulence_model_appropriate", False,
                    "Turbulence model suits the flow",
                    "k-ε handles separation/adverse gradients poorly for external aero — prefer k-ω SST or Spalart-Allmaras", cat=cat))
            else:
                C.append(self._w("mesh_turbulence_model_appropriate", True,
                    "Turbulence model suits the flow", "", cat=cat))

        tol = _f(s.get("convergence_tolerance"))
        if tol is not None:
            C.append(self._w("mesh_convergence_criterion", tol <= 1e-4,
                "Residual target ≤ 1e-4",
                f"convergence tolerance {tol:.0e} is loose (>1e-4) — solver may stop before converging" if tol > 1e-4 else "",
                tol, 1e-4, cat))

        order = _f(s.get("discretization_order"))
        if order is not None:
            C.append(self._w("mesh_discretization_order", order >= 2,
                "Second-order+ discretization",
                "first-order discretization is diffusive — use second-order for production accuracy" if order < 2 else "",
                order, 2.0, cat))

        for key, label in (("relaxation_velocity", "velocity"), ("relaxation_pressure", "pressure")):
            rf = _f(s.get(key))
            if rf is not None:
                ok = 0.2 <= rf <= 0.9
                C.append(self._w(f"mesh_relaxation_factors__{label}", ok,
                    "Relaxation factor in stable range (0.2–0.9)",
                    f"{label} relaxation {rf:.2f} {'>0.9 risks divergence' if rf > 0.9 else '<0.2 stalls convergence'}" if not ok else "",
                    rf, 0.9, cat))

        it = _f(s.get("max_iterations"))
        if it is not None:
            steady_min = 300
            C.append(self._w("mesh_max_iterations", it >= steady_min,
                "Iteration budget adequate",
                f"max_iterations={int(it)} is low — convergence to the residual target is unlikely" if it < steady_min else "",
                it, steady_min, cat))

        oi = _f(s.get("output_interval"))
        if oi is not None and it:
            C.append(self._w("mesh_output_interval", 1 <= oi <= it,
                "Output interval balances I/O and monitoring",
                ("output every iteration will dominate I/O" if oi < 1 else
                 "output interval exceeds the run length — no convergence monitoring") if not (1 <= oi <= it) else "",
                oi, cat=cat))
        return self._r(C)

    # ── Category 4: Physics model consistency ────────────────────────────────────
    def _physics_models(self, c: _Ctx) -> list[MeshCheck]:
        C: list[MeshCheck] = []
        flow, models, cat = c.flow, _models(c.config), "physics_models"

        ma = _f(flow.get("mach_number"))
        if ma is None:
            v = _f(flow.get("inlet_velocity"))
            T = _f(flow.get("temperature"))
            if v and T:
                ma = v / math.sqrt(1.4 * 287.05 * T)
        if ma is not None:
            incompressible = c.config.get("compressible") is False or "incompressible" in str(c.solver).lower() or models.get("incompressible")
            if ma > 0.3 and incompressible:
                C.append(self._c("mesh_compressibility", False,
                    "Compressible model for Ma>0.3",
                    f"Ma={ma:.2f} > 0.3 but an incompressible solver is selected — density variation ignored", ma, 0.3, cat))
            else:
                C.append(self._w("mesh_compressibility", True, "Compressibility assumption matches Ma", "", ma, 0.3, cat))

        T = _f(flow.get("temperature"))
        wall_T = flow.get("wall_temperature") is not None or bool(c.bc.get("temperature"))
        if wall_T and not models.get("heat_transfer"):
            C.append(self._w("mesh_heat_transfer_model", False,
                "Heat-transfer model for thermal BCs",
                "temperature BCs are set but no heat-transfer/energy model is enabled", cat=cat))

        if T is not None and T > 800 and not models.get("radiation"):
            C.append(self._w("mesh_radiation_model", False,
                "Radiation modeled at high temperature",
                f"T={T:.0f}K > 800K but radiation is not modeled — heat flux will be underpredicted", T, 800.0, cat))

        dT = _f(flow.get("temperature_difference"))
        gravity = c.config.get("gravity") is not False
        if dT is not None and dT > 20 and gravity and not models.get("buoyancy"):
            C.append(self._w("mesh_buoyancy_model", False,
                "Buoyancy modeled for large ΔT",
                f"ΔT={dT:.0f}K > 20K in gravity but buoyancy (Boussinesq/full) is off", dT, 20.0, cat))

        if flow.get("second_fluid") and not models.get("multiphase"):
            C.append(self._c("mesh_multiphase_model", False,
                "Multiphase model for two fluids",
                "two fluids present but no multiphase model (VOF/mixture/Eulerian) is active", cat=cat))

        if (flow.get("fuel") or c.bc.get("fuel")) and not models.get("combustion"):
            C.append(self._c("mesh_combustion_model", False,
                "Combustion model for fuel/oxidizer",
                "fuel/oxidizer inlets are set but no combustion model is enabled", cat=cat))

        if flow.get("magnetic_field") and not models.get("mhd"):
            C.append(self._c("mesh_mhd_model", False,
                "MHD enabled for magnetic fields",
                "magnetic field specified but magnetohydrodynamics is not enabled", cat=cat))
        return self._r(C)

    # ── Category 5: Predicted output corruption ──────────────────────────────────
    def _predict_output_errors(self, c: _Ctx, issues: list[MeshCheck]) -> list[dict[str, str] | str]:
        names = {i.name for i in issues}
        predicted: list[dict[str, str]] = []
        seen: set[str] = set()

        def add(check_name: str) -> None:
            if check_name not in seen:
                seen.add(check_name)
                predicted.append(humanize_mesh_check(check_name, c.config))

        if {"mesh_yplus_model_compat", "mesh_boundary_layer_present"} & names:
            add("cx_yplus_wallth")
            add("turb_tke_pos")
        if "mesh_cfl_explicit" in names or "mesh_convergence_criterion" in names or "mesh_max_iterations" in names:
            add("ns_spike")
            add("conv_res_momentum_residual")
        if "mesh_aspect_ratio" in names or "mesh_skewness" in names or "mesh_nonortho" in names:
            add("ns_spike")
            add("outlier_velocity")
            add("conv_res_momentum_residual")
        if "mesh_bc_reynolds_turbulence_match" in names or "mesh_turbulence_model_appropriate" in names:
            add("turbulence_model_mismatch")
        if "mesh_bc_reference_values" in names or "mesh_compressibility" in names:
            add("compressibility_mismatch")
        if "mesh_cell_count_adequacy" in names:
            add("mesh_nonortho")
            add("conv_res_momentum_residual")
        if {"mesh_heat_transfer_model", "mesh_radiation_model", "mesh_buoyancy_model"} & names:
            add("heat_transfer_missing")
        return predicted

    def _corruption_risk(self, n_pass: int, warned: list, failed: list) -> float:
        # Failures weigh 3×, warnings 1×; squashed to 0-1 with diminishing returns.
        weighted = 3.0 * len(failed) + 1.0 * len(warned)
        if weighted == 0:
            return 0.0
        return min(1.0, 1.0 - math.exp(-weighted / 4.0))

    def _recommendations(self, issues: list[MeshCheck]) -> list[str]:
        recs: list[str] = []
        for i in issues:
            if i.name == "mesh_yplus_model_compat":
                recs.append("Refine (or coarsen) the near-wall mesh to hit the y+ target for your turbulence model.")
            elif i.name == "mesh_nonortho":
                recs.append("Reduce mesh non-orthogonality or add non-orthogonal correctors to the solver.")
            elif i.name in ("mesh_skewness", "mesh_min_cell_quality"):
                recs.append("Repair degenerate/low-quality cells before running — they will inject numerical noise.")
            elif i.name == "mesh_aspect_ratio":
                recs.append("Lower peak cell aspect ratio to curb numerical diffusion and speed convergence.")
            elif i.name == "mesh_cfl_explicit":
                recs.append("Reduce the timestep (or switch to an implicit scheme) to satisfy the CFL condition.")
            elif i.name == "mesh_convergence_criterion":
                recs.append("Tighten residual targets to ≤1e-4 (≤1e-6 for incompressible pressure).")
            elif i.name == "mesh_discretization_order":
                recs.append("Use second-order (or higher) discretization for production accuracy.")
            elif i.name.startswith("mesh_relaxation_factors"):
                recs.append("Move relaxation factors into the 0.2–0.9 band to avoid divergence or stalling.")
            elif i.name == "mesh_compressibility":
                recs.append("Switch to a compressible solver — Ma>0.3 makes the incompressible assumption invalid.")
            elif i.name == "mesh_bc_reference_values":
                recs.append("Check reference pressure/density/temperature units — P/(ρT) should equal ~287 J/kg·K.")
            elif i.name == "mesh_bc_inlet_outlet_consistency":
                recs.append("Set a pressure reference at the outlet — fixing velocity at both ends is overdetermined.")
            elif i.name in ("mesh_heat_transfer_model", "mesh_radiation_model", "mesh_buoyancy_model",
                            "mesh_multiphase_model", "mesh_combustion_model", "mesh_mhd_model"):
                recs.append(f"Enable the missing physics model: {humanize_mesh_check_name(i.name)}.")
        # de-dup, preserve order
        seen: set = set()
        out = []
        for r in recs:
            if r not in seen:
                seen.add(r)
                out.append(r)
        return out


def humanize_mesh_check(check_name: str, config: dict[str, Any]) -> dict[str, str]:
    """Return a humanized description of a predicted output failure."""
    flow = (config.get("flow_conditions") or {})
    mesh = (config.get("mesh") or {})
    solv = (config.get("solver_settings") or {})
    yplus = mesh.get("estimated_yplus", "unknown")
    velocity = flow.get("inlet_velocity", flow.get("velocity", "unknown"))
    turb_model = solv.get("turbulence_model", "unknown")

    CHECKS = {
        "cx_yplus_wallth": {
            "plain_english": "Near-wall mesh too coarse for heat transfer calculations",
            "why_it_will_fail": f"Your y+ estimate of {yplus} is in the wall-function range, but heat transfer coefficient calculations require y+ < 5 for accurate near-wall temperature gradients. The mesh cannot resolve the thermal boundary layer.",
            "proposed_fix": f"Refine the boundary layer mesh to achieve y+ ≈ 1. Add at least 10 inflation layers with a growth ratio of 1.2 and first cell height appropriate for your inlet velocity of {velocity} m/s.",
        },
        "turb_tke_pos": {
            "plain_english": "Turbulent kinetic energy may go negative (unphysical)",
            "why_it_will_fail": f"With {turb_model} on an under-resolved mesh, TKE can become negative near walls where the production/dissipation balance is poorly approximated. This causes NaN propagation.",
            "proposed_fix": "Ensure the near-wall mesh resolves the viscous sublayer (y+ ≈ 1) or switch to a realizability-constrained turbulence model that clips negative TKE.",
        },
        "ns_spike": {
            "plain_english": "Sudden spikes in output fields (numerical instability)",
            "why_it_will_fail": "Poor cell quality (high aspect ratio, skewness, or non-orthogonality) causes the discretization to produce oscillations that appear as spikes in velocity or pressure fields.",
            "proposed_fix": "Repair the worst cells — reduce max aspect ratio below 100, max skewness below 0.85, and max non-orthogonality below 70°. Add non-orthogonal correctors if using OpenFOAM.",
        },
        "outlier_velocity": {
            "plain_english": "Velocity field will contain unrealistic outlier values",
            "why_it_will_fail": "Degenerate cells (high skewness or aspect ratio) cause local numerical errors that manifest as velocity values far outside the expected range, polluting downstream statistics.",
            "proposed_fix": "Identify and fix the worst-quality cells. Use mesh quality tools (checkMesh in OpenFOAM) to locate specific cells, then re-mesh those regions with tighter quality constraints.",
        },
        "conv_res_momentum_residual": {
            "plain_english": "Momentum residuals will not converge to target tolerance",
            "why_it_will_fail": "The combination of mesh quality issues and solver settings makes it unlikely that momentum residuals will drop below your convergence target. The solver will exhaust its iteration budget.",
            "proposed_fix": "Fix the underlying mesh quality issues first. If the mesh is acceptable, increase max iterations to at least 500, ensure second-order discretization, and tighten under-relaxation factors to 0.5–0.7.",
        },
        "turbulence_model_mismatch": {
            "plain_english": "Turbulence model is inappropriate for this flow regime",
            "why_it_will_fail": f"The selected model ({turb_model}) does not match the flow's Reynolds number regime. This produces incorrect eddy viscosity, leading to wrong drag/lift predictions and possible divergence.",
            "proposed_fix": "For external aerodynamics use k-ω SST or Spalart-Allmaras. For internal flows with strong recirculation use k-ω SST. Only use k-ε for simple internal flows without separation.",
        },
        "compressibility_mismatch": {
            "plain_english": "Compressibility assumption does not match the flow speed",
            "why_it_will_fail": f"At the current velocity ({velocity} m/s), density variations are significant but the incompressible solver ignores them. Pressure and velocity fields will be wrong, and the gas constant check will flag inconsistencies.",
            "proposed_fix": "Switch to a compressible solver (rhoSimpleFoam, density-based solver) for Mach > 0.3. For Mach 0.3–0.8, a low-Mach preconditioning approach also works.",
        },
        "mesh_nonortho": {
            "plain_english": "High mesh non-orthogonality degrades solution accuracy",
            "why_it_will_fail": "Non-orthogonality above 70° introduces significant interpolation errors in face gradients. Without correction, pressure and velocity gradients are computed inaccurately.",
            "proposed_fix": "Re-mesh to reduce non-orthogonality below 70° (ideally below 50°). If unavoidable, add at least 2 non-orthogonal correctors and use limited gradient schemes.",
        },
        "mesh_skewness": {
            "plain_english": "High cell skewness will inject numerical noise",
            "why_it_will_fail": "Skewed cells cause the face center to deviate significantly from the cell-connecting line, making gradient interpolation inaccurate and creating local oscillations.",
            "proposed_fix": "Identify cells with skewness > 0.85 and re-mesh those regions. Use hex-dominant meshing near critical areas. Set decomposition method to preserve cell quality at processor boundaries.",
        },
        "mesh_aspect_ratio": {
            "plain_english": "Extreme cell aspect ratios will cause numerical diffusion",
            "why_it_will_fail": "Cells stretched beyond 100:1 cause the numerical scheme to behave as first-order in the stretched direction, smearing gradients and producing artificially smooth fields.",
            "proposed_fix": "Reduce aspect ratios in the flow direction to below 100:1. In boundary layers, high aspect ratio in the wall-parallel direction is acceptable, but wall-normal stretching should stay below 50:1.",
        },
        "bc_inlet_outlet": {
            "plain_english": "Inlet/outlet boundary conditions are overdetermined",
            "why_it_will_fail": "Fixing velocity at both inlet and outlet leaves no pressure reference. The system is mathematically overdetermined and the solver will either diverge or produce a non-physical pressure field.",
            "proposed_fix": "Set velocity at the inlet and pressure at the outlet (or vice versa). One boundary must float to absorb the pressure level.",
        },
        "solver_cfl": {
            "plain_english": "CFL condition violated — solver will diverge",
            "why_it_will_fail": "The explicit time-advancement scheme requires CFL ≤ 1 for stability. Exceeding this causes exponential error growth that destroys the solution within a few timesteps.",
            "proposed_fix": "Reduce the timestep to satisfy CFL ≤ 0.8 at all cells, or switch to an implicit time-advancement scheme (which is unconditionally stable for CFL > 1).",
        },
        "heat_transfer_missing": {
            "plain_english": "Thermal predictions will be missing or wrong",
            "why_it_will_fail": "Temperature boundary conditions are set but the energy equation is not solved. The temperature field will remain at its initialization value and heat transfer coefficients will be zero.",
            "proposed_fix": "Enable the energy equation in the solver configuration. For incompressible flow with small temperature differences, enable the Boussinesq approximation. For compressible flow, the energy equation is mandatory.",
        },
    }

    if check_name in CHECKS:
        return {"check_name": check_name, **CHECKS[check_name]}

    return {
        "check_name": check_name,
        "plain_english": check_name.replace("_", " ").capitalize(),
        "why_it_will_fail": "This check is predicted to fail based on the current configuration.",
        "proposed_fix": "Review the simulation setup for issues related to this check.",
    }


# ── Internal helpers ─────────────────────────────────────────────────────────────
@dataclass
class _Ctx:
    config: dict[str, Any]
    geo: dict[str, Any]
    flow: dict[str, Any]
    mesh: dict[str, Any]
    solv: dict[str, Any]
    bc: dict[str, Any]
    solver: str
    physics: str
    simulation_type: str


def _f(x: Any) -> float | None:
    """Coerce to float, returning None for missing/non-numeric values."""
    if x is None or isinstance(x, bool):
        return None
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _models(config: dict[str, Any]) -> dict[str, bool]:
    """Normalize the enabled-physics-models section from a few common shapes."""
    m = config.get("physics_models") or config.get("models") or {}
    if isinstance(m, list):
        return {str(k).lower(): True for k in m}
    if isinstance(m, dict):
        return {str(k).lower(): bool(v) for k, v in m.items()}
    return {}



def predict_corruption_risks(
    simulation_type: str,
    mesh_stats: dict,
    solver: dict,
    physics: dict,
) -> dict:
    """
    APIE-powered pre-flight corruption risk prediction.
    
    Based on the simulation domain, mesh quality, and solver settings,
    predicts which types of output corruption are most likely and which
    APIE checks will be most important for post-run validation.
    
    Returns:
        dict with corruption risk scores and recommended checks.
    """
    try:
        from core.apie import get_profile
        profile = get_profile(simulation_type)
    except Exception:
        profile = None

    risks = {}
    recommendations = []
    required_checks = []

    # ── Mesh quality → corruption risk mapping ────────────────────────────────
    cell_count = mesh_stats.get("cell_count", 0)
    max_skewness = mesh_stats.get("max_skewness", 0.0)
    mesh_stats.get("max_aspect_ratio", 1.0)
    nonortho_avg = mesh_stats.get("average_non_orthogonality", 0.0)

    # High skewness → solver divergence risk
    if max_skewness > 0.8:
        risks["solver_divergence"] = min(1.0, (max_skewness - 0.8) / 0.2)
        recommendations.append(
            f"High skewness ({max_skewness:.2f}) increases solver divergence risk. "
            "APIE will run joint_skew_outlier and ensemble_predictor with tight thresholds."
        )
        required_checks.append("joint_skew_outlier")

    # Coarse mesh → numerical diffusion → unit conversion errors undetected
    if cell_count < 50000 and "aerodynamics" in simulation_type.lower():
        risks["measurement_noise"] = 0.6
        recommendations.append(
            f"Cell count ({cell_count:,}) may be insufficient for boundary layer resolution. "
            "APIE will apply local neighborhood anomaly detection on wall-adjacent cells."
        )
        required_checks.append("target_neighbor_anomaly")

    # Non-orthogonality → pressure-velocity coupling errors
    if nonortho_avg > 40:
        risks["cross_variable"] = min(1.0, (nonortho_avg - 40) / 20)
        recommendations.append(
            "High non-orthogonality may cause pressure-velocity decoupling. "
            "APIE will check Re/v and P/(ρT) invariants."
        )
        required_checks.append("ratio_invariant")

    # ── Solver settings → unit conversion risk ────────────────────────────────
    solver_name = solver.get("name", "").lower()
    if any(s in solver_name for s in ["openfoam", "foam"]):
        risks["unit_conversion"] = 0.3
        recommendations.append(
            "OpenFOAM output commonly has Pa/kPa and m/mm unit inconsistencies. "
            "APIE will apply strict P/(ρT) = 287 check."
        )
        required_checks.append("ratio_invariant")

    # ── Domain-specific invariants ────────────────────────────────────────────
    if profile:
        invariant_names = [inv.law_name for inv in profile.invariants]
        recommendations.append(
            f"Domain '{profile.canonical_name}' has {len(profile.invariants)} known "
            f"physical invariants: {', '.join(invariant_names[:3])}. "
            "These will be checked automatically by APIE post-run."
        )
        required_checks.extend(
            inv.check for inv in profile.invariants
        )

    # ── Predicted error types for APIE focus ─────────────────────────────────
    risk_sorted = sorted(risks.items(), key=lambda x: -x[1])
    predicted_errors = [k for k, v in risk_sorted if v > 0.3]

    return {
        "corruption_risk_scores": risks,
        "predicted_error_types": predicted_errors,
        "recommended_apie_checks": list(set(required_checks)),
        "domain_invariants_count": len(profile.invariants) if profile else 0,
        "domain_canonical": profile.canonical_name if profile else "unknown",
        "recommendations": recommendations,
        "overall_corruption_risk": min(1.0, sum(risks.values()) / max(len(risks), 1)),
    }


# Module-level singleton (mirrors PhysicsValidator usage in the server).
mesh_validator = MeshValidator()


def predict_output_corruption(
    simulation_type: str,
    mesh_stats: dict,
    solver_settings: dict,
    historical_data=None,
) -> dict:
    """
    APIE-powered output corruption prediction for preflight validation.

    Analyzes mesh quality metrics and solver settings to predict which
    types of output corruption are most likely. When historical_data is
    provided (a DataFrame of previous runs), computes a full fingerprint
    and returns suspected corruption types with confidence scores.

    Returns a dict with:
      - suspected_corruption_types: {type: confidence}
      - risk_factors: [human-readable explanations]
      - recommended_checks: [check types to watch for in output]
      - fingerprint (if historical_data provided)
    """
    try:
        from core.apie import compute_fingerprint, get_profile
    except ImportError:
        return {"error": "APIE not available"}

    risk_factors = []
    suspected = {}
    recommended = []

    # ── Mesh-based risk factors ──────────────────────────────────────────────
    max_skew = mesh_stats.get("max_skewness", 0)
    max_ar = mesh_stats.get("max_aspect_ratio", 1)
    non_ortho = mesh_stats.get("max_non_orthogonality", 0)

    if max_skew > 0.85:
        suspected["solver_divergence"] = max(suspected.get("solver_divergence", 0),
                                              0.4 + (max_skew - 0.85) * 2)
        risk_factors.append(
            f"High mesh skewness ({max_skew:.2f} > 0.85) increases risk of "
            "numerical divergence in output fields."
        )
        recommended.append("joint_skew_outlier")

    if max_ar > 100:
        suspected["sensor_drift"] = max(suspected.get("sensor_drift", 0),
                                         min(0.8, (max_ar - 100) / 500))
        risk_factors.append(
            f"Extreme aspect ratio ({max_ar:.0f}) causes anisotropic error "
            "propagation — output may drift from physical values near high-AR cells."
        )
        recommended.append("pairwise_ratio_drift")

    if non_ortho > 70:
        suspected["measurement_noise"] = max(suspected.get("measurement_noise", 0), 0.5)
        risk_factors.append(
            f"High non-orthogonality ({non_ortho:.0f}° > 70°) introduces "
            "truncation error in gradient reconstruction — manifests as noise in "
            "derived quantities."
        )
        recommended.append("target_neighbor_anomaly")

    # ── Solver-based risk factors ────────────────────────────────────────────
    cfl = solver_settings.get("cfl_number", 0)
    if cfl > 0.8:
        suspected["solver_divergence"] = max(suspected.get("solver_divergence", 0),
                                              min(0.9, cfl))
        risk_factors.append(
            f"CFL = {cfl:.2f} > 0.8: explicit solver may produce Courant-unstable "
            "spikes in velocity/pressure output."
        )
        recommended.append("temporal_coherence")

    rel_tol = solver_settings.get("relative_tolerance", 1e-6)
    if rel_tol > 1e-3:
        suspected["measurement_noise"] = max(suspected.get("measurement_noise", 0), 0.6)
        risk_factors.append(
            f"Loose convergence tolerance ({rel_tol:.0e}) — output fields may not "
            "be fully converged, producing run-to-run measurement noise."
        )

    # ── Domain profile context ───────────────────────────────────────────────
    profile = get_profile(simulation_type)
    if profile:
        recommended.extend([
            inv.check for inv in profile.invariants
            if inv.check in ("ratio_invariant", "physical_bounds", "law_constraint")
        ])

    # ── Historical fingerprint (if data available) ───────────────────────────
    fingerprint_summary = None
    if historical_data is not None:
        try:
            import pandas as pd
            if isinstance(historical_data, list):
                historical_data = pd.DataFrame(historical_data)
            fp = compute_fingerprint(historical_data, simulation_type, {})
            # Merge fingerprint signals into suspected
            for _pair, (_, _, tau, p) in fp.ratio_signals.items():
                if abs(tau) > 0.08 and p < 0.05:
                    suspected["sensor_drift"] = max(
                        suspected.get("sensor_drift", 0), min(1.0, abs(tau) * 5)
                    )
            if fp.copy_paste_fraction > 0.001:
                suspected["copy_paste"] = min(1.0, fp.copy_paste_fraction * 200)
            fingerprint_summary = {
                "n_rows": fp.n_rows,
                "discovered_invariants": fp.discovered_invariants,
                "max_distribution_shift": fp.max_distribution_shift,
                "copy_paste_fraction": fp.copy_paste_fraction,
            }
        except Exception:
            pass

    return {
        "suspected_corruption_types": {
            k: round(min(v, 1.0), 2) for k, v in suspected.items() if v > 0.1
        },
        "risk_factors": risk_factors,
        "recommended_checks": list(dict.fromkeys(recommended)),  # deduplicated
        "domain_profile": profile.canonical_name if profile else None,
        "historical_fingerprint": fingerprint_summary,
    }

