/**
 * Pre-simulation (mesh + setup) validator — TypeScript port of core/mesh_validator.py
 * so the Pre-flight tab works against the same-origin serverless API with no backend.
 * Deterministic, no external calls.
 */
export interface MeshIssue {
  name: string;
  human_name: string;
  status: "warning" | "failed";
  description: string;
  detail: string;
  value: number | null;
  category: string;
}

export interface PredictedFailure {
  check: string;      // raw output-check id (e.g. "cx_yplus_wall")
  label: string;      // human-readable name
  why: string;        // why it will fail given the current setup
  fix: string;        // concrete, actionable change
}

export interface SetupReport {
  status: "ready" | "warning" | "not_ready";
  all_checks: number;
  passed: number;
  warnings: number;
  failed: number;
  issues: MeshIssue[];
  predicted_error_types: string[];      // raw ids (back-compat)
  predicted_failures: PredictedFailure[];
  estimated_corruption_risk: number;
  recommendations: string[];
  processing_ms: number;
}

// Output-check id → human name + why-it-fires + how-to-fix.
const PREDICTED: Record<string, { label: string; why: string; fix: string }> = {
  cx_yplus_wall: { label: "Wall y+ resolution", why: "The near-wall mesh does not match the turbulence model's y+ requirement, so wall shear and heat transfer will be computed on an unresolved boundary layer.", fix: "Re-mesh the near-wall region to hit y+≈1 for low-Re models (k-ω SST, Spalart-Allmaras) or 30<y+<300 for wall functions (k-ε)." },
  th_heat_transfer_coeff: { label: "Heat-transfer coefficient", why: "Unresolved near-wall cells make the temperature gradient at the wall inaccurate, so the reported heat-transfer coefficient will be off.", fix: "Refine the boundary-layer mesh and confirm y+ is in range for your model." },
  turb_tke_pos: { label: "Turbulent kinetic energy positivity", why: "Poor near-wall resolution or a Re/turbulence-model mismatch produces negative or spurious turbulent kinetic energy in the output.", fix: "Fix the y+ / turbulence-model pairing and ensure the inlet turbulence intensity is physical." },
  ns_nan: { label: "NaN in the solution field", why: "The timestep violates the CFL condition or the residual target is too loose, so the solver diverges and writes NaN.", fix: "Lower the timestep to satisfy CFL, or tighten the convergence tolerance to ≤1e-4." },
  ns_inf: { label: "Infinite value in the solution field", why: "Aggressive relaxation or CFL violation causes the solution to blow up to Inf before it converges.", fix: "Reduce relaxation factors into 0.2–0.9 and cut the timestep." },
  ns_spike: { label: "Velocity spike outlier", why: "High-aspect-ratio, skewed, or non-orthogonal cells inject spurious velocity spikes into the field.", fix: "Repair the offending cells — lower aspect ratio, skewness, and non-orthogonality." },
  outlier_velocity: { label: "Velocity outlier detection", why: "Degenerate cells produce a handful of trials whose velocity sits far outside the physical distribution.", fix: "Improve mesh quality near the flagged regions before running." },
  conv_res_momentum_residual: { label: "Momentum residual convergence", why: "Mesh quality issues stall the momentum residual, so it never reaches the target and the run is under-converged.", fix: "Improve cell quality and add non-orthogonal correctors, then re-check residuals." },
  conv_res_continuity_residual: { label: "Continuity residual convergence", why: "Loose tolerances, too few iterations, or an under-resolved mesh leave the continuity residual above target.", fix: "Tighten the residual target, raise max iterations, and refine the mesh where needed." },
  input_forward_fill: { label: "Forward-filled (stalled) output", why: "When the solver diverges or stops early, monitors forward-fill the last value — a tell-tale corruption pattern.", fix: "Ensure the run actually converges (CFL, tolerance, iterations) so no values are held constant." },
  cx_re_velocity: { label: "Reynolds ↔ velocity consistency", why: "The turbulence model doesn't match the Reynolds regime, so the reported Re is inconsistent with the velocity field.", fix: "Pick a turbulence model appropriate for the Re regime (laminar vs RANS model)." },
  aero_drag_coefficient: { label: "Drag coefficient plausibility", why: "An inappropriate turbulence model for external aero mispredicts separation, corrupting the drag coefficient.", fix: "Use k-ω SST or Spalart-Allmaras for external aerodynamics instead of k-ε." },
  cx_gas_constant_check: { label: "Gas-constant unit consistency", why: "Reference pressure/density/temperature don't satisfy P/(ρT)=287 J/kg·K — usually a Pa vs kPa unit slip that propagates through the output.", fix: "Correct the reference-value units so P/(ρT) equals ~287." },
  cx_mach_vel: { label: "Mach ↔ velocity consistency", why: "A compressibility or reference mismatch makes the reported Mach number inconsistent with velocity.", fix: "Use a compressible solver above Ma 0.3 and verify reference speed of sound." },
  dim_pressure_units: { label: "Pressure dimensional check", why: "The pressure reference is off by an order of magnitude, so pressure-derived quantities carry a unit error.", fix: "Fix the pressure units in the reference values (Pa, not kPa)." },
  stat_high_variance: { label: "High output variance", why: "An under-resolved mesh leaves the run under-converged, so outputs show variance unrelated to the physics.", fix: "Refine the mesh for the Reynolds number and confirm convergence." },
  th_energy_balance: { label: "Energy balance", why: "A missing heat-transfer / radiation / buoyancy model breaks the energy balance in the output.", fix: "Enable the appropriate thermal model for your boundary conditions and temperature range." },
  th_heat_flux_sign: { label: "Heat-flux sign", why: "Without the right thermal model, the heat-flux direction can come out physically wrong.", fix: "Enable radiation/buoyancy/heat-transfer as required by the setup." },
};

const HUMAN: Record<string, string> = {
  mesh_yplus_model_compat: "Near-wall resolution (y+) matches the turbulence model",
  mesh_aspect_ratio: "Cell aspect ratio within numerically safe limits",
  mesh_nonortho: "Mesh non-orthogonality within solver limits",
  mesh_skewness: "Cell skewness below degeneracy threshold",
  mesh_cell_count_adequacy: "Cell count sufficient to resolve the flow",
  mesh_boundary_layer_present: "Structured inflation layer present at walls",
  mesh_boundary_layer_growth: "Boundary-layer growth ratio ≤ 1.3",
  mesh_volume_ratio: "Adjacent cell volume ratio within limits",
  mesh_watertight: "Surface mesh is watertight",
  mesh_min_cell_quality: "Minimum cell quality above the solver threshold",
  mesh_bc_inlet_outlet_consistency: "Inlet/outlet boundary conditions are consistent",
  mesh_bc_pressure_gradient: "Pressure inlet/outlet gradient drives flow correctly",
  mesh_bc_reynolds_turbulence_match: "Turbulence model matches the Reynolds regime",
  mesh_bc_reference_values: "Reference velocity/pressure/density are self-consistent",
  mesh_cfl_explicit: "Timestep satisfies the CFL condition",
  mesh_turbulence_model_appropriate: "Turbulence model is appropriate for the flow",
  mesh_convergence_criterion: "Convergence residual targets are tight enough",
  mesh_discretization_order: "Discretization order high enough for accuracy",
  mesh_relaxation_factors: "Relaxation factors in the stable range",
  mesh_max_iterations: "Iteration budget adequate for convergence",
  mesh_compressibility: "Compressible/incompressible assumption matches Mach number",
  mesh_heat_transfer_model: "Heat-transfer model enabled for thermal BCs",
  mesh_radiation_model: "Radiation modeled at high temperature",
  mesh_buoyancy_model: "Buoyancy modeled for large temperature differences",
};

export function humanizeMeshCheck(name: string): string {
  return HUMAN[name.split("__")[0]] ?? name.replace(/^mesh_/, "").replace(/_/g, " ");
}

type Status = "passed" | "warning" | "failed";
interface Check { name: string; status: Status; description: string; detail: string; value: number | null; category: string }

function num(x: unknown): number | null {
  if (x === null || x === undefined || typeof x === "boolean") return null;
  const v = Number(x);
  return Number.isFinite(v) ? v : null;
}

export function validateSetupConfig(config: Record<string, any>, meshStats?: Record<string, any>, simulationType = "aerodynamics"): SetupReport {
  const t0 = performance.now();
  const geo = config.geometry ?? {};
  const flow = config.flow_conditions ?? {};
  const mesh = { ...(config.mesh ?? {}), ...(meshStats ?? {}) };
  const s = config.solver_settings ?? {};
  const bc = config.boundary_conditions ?? {};
  const solver = String(config.solver ?? "openfoam").toLowerCase();
  const models: Record<string, boolean> = {};
  const rawModels = config.physics_models ?? config.models ?? {};
  if (Array.isArray(rawModels)) for (const k of rawModels) models[String(k).toLowerCase()] = true;
  else for (const [k, v] of Object.entries(rawModels)) models[k.toLowerCase()] = Boolean(v);

  const C: Check[] = [];
  const w = (name: string, ok: boolean, desc: string, detail = "", value: number | null = null, cat = "general") =>
    C.push({ name, status: ok ? "passed" : "warning", description: desc, detail, value, category: cat });
  const f = (name: string, ok: boolean, desc: string, detail = "", value: number | null = null, cat = "general") =>
    C.push({ name, status: ok ? "passed" : "failed", description: desc, detail, value, category: cat });

  // ── Mesh quality ──
  const model = String(s.turbulence_model ?? "").toLowerCase();
  const yp = num(mesh.estimated_yplus);
  if (yp !== null && model) {
    const lowRe = ["komega", "sst", "spalart", "sa"].some((k) => model.includes(k));
    if (lowRe) f("mesh_yplus_model_compat", yp <= 5, "Low-Re model requires y+≈1",
      yp > 5 ? `y+=${yp.toFixed(1)} with ${model}: needs y+≲1 — wall not resolved` : "", yp, "mesh_quality");
    else w("mesh_yplus_model_compat", yp >= 30 && yp <= 300, "Wall functions require 30<y+<300",
      (yp < 30 || yp > 300) ? `y+=${yp.toFixed(1)} outside wall-function range 30–300` : "", yp, "mesh_quality");
  }
  const ar = num(mesh.max_aspect_ratio);
  if (ar !== null) {
    if (ar > 1000) f("mesh_aspect_ratio", false, "Aspect ratio ≤ 1000", `max AR=${ar.toFixed(0)} → numerical diffusion + slow convergence`, ar, "mesh_quality");
    else w("mesh_aspect_ratio", ar <= 100, "Aspect ratio ≤ 100 (ideal)", ar > 100 ? `max AR=${ar.toFixed(0)} is high (>100)` : "", ar, "mesh_quality");
  }
  const no = num(mesh.max_non_orthogonality);
  if (no !== null) {
    if (no > 85) f("mesh_nonortho", false, "Non-orthogonality ≤ 85°", `max ${no.toFixed(0)}° unacceptable (>85°)`, no, "mesh_quality");
    else w("mesh_nonortho", no <= 70, "Non-orthogonality ≤ 70°", no > 70 ? `max ${no.toFixed(0)}° degrades accuracy (>70°)` : "", no, "mesh_quality");
  }
  const sk = num(mesh.max_skewness);
  if (sk !== null) {
    if (sk > 0.95) f("mesh_skewness", false, "Skewness ≤ 0.95", `max skewness ${sk.toFixed(2)} degenerate (>0.95)`, sk, "mesh_quality");
    else w("mesh_skewness", sk <= 0.85, "Skewness ≤ 0.85", sk > 0.85 ? `max skewness ${sk.toFixed(2)} exceeds 0.85` : "", sk, "mesh_quality");
  }
  const cells = num(mesh.total_cells), re = num(flow.reynolds_number);
  if (cells !== null && re !== null && re > 0) {
    const recMin = Math.max(50000, 20000 * Math.log10(Math.max(re, 10)));
    w("mesh_cell_count_adequacy", cells >= recMin, "Cell count adequate for Reynolds number",
      cells < recMin ? `${cells.toLocaleString()} cells may under-resolve Re=${re.toFixed(0)} (≳${Math.round(recMin).toLocaleString()})` : "", cells, "mesh_quality");
  }
  const hasBL = mesh.has_boundary_layers;
  if (hasBL !== undefined) {
    const walls = String(bc.walls ?? "").toLowerCase();
    const wallBounded = walls.includes("noslip") || walls.includes("wall") || !walls;
    w("mesh_boundary_layer_present", Boolean(hasBL) || !wallBounded, "Structured inflation layer at walls",
      !hasBL && wallBounded ? "No boundary-layer mesh at walls — near-wall gradients under-resolved" : "", null, "mesh_quality");
    const gr = num(mesh.boundary_layer_growth_ratio);
    if (hasBL && gr !== null) w("mesh_boundary_layer_growth", gr <= 1.3, "Growth ratio ≤ 1.3", gr > 1.3 ? `growth ratio ${gr.toFixed(2)} > 1.3` : "", gr, "mesh_quality");
  }
  const mq = num(mesh.min_cell_quality);
  if (mq !== null) {
    const thr = solver === "openfoam" || solver === "su2" ? 0.1 : 0.05;
    f("mesh_min_cell_quality", mq >= thr, `Minimum cell quality ≥ ${thr}`, mq < thr ? `min quality ${mq.toFixed(3)} below ${solver} threshold ${thr}` : "", mq, "mesh_quality");
  }
  // Watertight (surface meshes / uploaded geometry).
  const oe = num(mesh.open_edges), du = num(mesh.duplicate_faces), si = num(mesh.self_intersections);
  if (oe !== null || du !== null || si !== null) {
    const bad = (oe ?? 0) + (du ?? 0) + (si ?? 0);
    f("mesh_watertight", bad === 0, "Surface mesh watertight",
      bad ? `non-watertight geometry: ${oe ?? 0} open edges, ${si ?? 0} self-intersections, ${du ?? 0} duplicate faces — meshing will fail or leak` : "", bad, "mesh_quality");
  }

  // ── Boundary conditions ──
  const inlet = String(bc.inlet ?? "").toLowerCase(), outlet = String(bc.outlet ?? "").toLowerCase();
  if (inlet && outlet) {
    const bothVel = inlet.includes("velocity") && outlet.includes("velocity");
    f("mesh_bc_inlet_outlet_consistency", !bothVel, "Inlet/outlet not overdetermined",
      bothVel ? "velocity fixed at BOTH inlet and outlet — overdetermined, no pressure reference" : "", null, "boundary_conditions");
  }
  if (re !== null) {
    const laminar = re < 2300, hasTurb = Boolean(model) && model !== "laminar" && model !== "none";
    if (laminar && hasTurb) w("mesh_bc_reynolds_turbulence_match", false, "Turbulence model matches Re regime", `Re=${re.toFixed(0)} laminar (<2300) but ${model} active`, re, "boundary_conditions");
    else if (re > 4000 && !hasTurb) f("mesh_bc_reynolds_turbulence_match", false, "Turbulence model matches Re regime", `Re=${re.toFixed(0)} turbulent but no turbulence model set`, re, "boundary_conditions");
  }
  const p = num(flow.pressure), rho = num(flow.density), T = num(flow.temperature);
  if (p && rho && T) {
    const R = p / (rho * T);
    w("mesh_bc_reference_values", R >= 250 && R <= 320, "Reference P/ρ/T self-consistent",
      !(R >= 250 && R <= 320) ? `P/(ρT)=${R.toFixed(1)} deviates from R_air=287 — likely a unit mismatch` : "", R, "boundary_conditions");
  }

  // ── Solver config ──
  const cfl = num(s.max_cfl);
  const explicit = Boolean(s.explicit) || String(s.time_scheme ?? "").toLowerCase() === "explicit";
  if (cfl !== null) {
    const limit = explicit ? 1 : 50;
    f("mesh_cfl_explicit", cfl <= limit, `CFL ≤ ${limit}`, cfl > limit ? `max CFL=${cfl.toFixed(2)} exceeds ${limit} for ${explicit ? "explicit" : "implicit"} — divergence risk` : "", cfl, "solver_config");
  }
  const st = simulationType.toLowerCase();
  if (model && (st === "aerodynamics" || st === "aeroelasticity") && model.includes("epsilon"))
    w("mesh_turbulence_model_appropriate", false, "Turbulence model suits the flow", "k-ε handles separation poorly for external aero — prefer k-ω SST or Spalart-Allmaras", null, "solver_config");
  const tol = num(s.convergence_tolerance);
  if (tol !== null) w("mesh_convergence_criterion", tol <= 1e-4, "Residual target ≤ 1e-4", tol > 1e-4 ? `tolerance ${tol.toExponential(0)} is loose (>1e-4)` : "", tol, "solver_config");
  const order = num(s.discretization_order);
  if (order !== null) w("mesh_discretization_order", order >= 2, "Second-order+ discretization", order < 2 ? "first-order is diffusive — use second-order for production" : "", order, "solver_config");
  for (const [key, label] of [["relaxation_velocity", "velocity"], ["relaxation_pressure", "pressure"]] as const) {
    const rf = num(s[key]);
    if (rf !== null) w(`mesh_relaxation_factors__${label}`, rf >= 0.2 && rf <= 0.9, "Relaxation factor in 0.2–0.9",
      !(rf >= 0.2 && rf <= 0.9) ? `${label} relaxation ${rf.toFixed(2)} ${rf > 0.9 ? ">0.9 risks divergence" : "<0.2 stalls"}` : "", rf, "solver_config");
  }
  const it = num(s.max_iterations);
  if (it !== null) w("mesh_max_iterations", it >= 300, "Iteration budget adequate", it < 300 ? `max_iterations=${it} is low — convergence unlikely` : "", it, "solver_config");

  // ── Physics models ──
  let ma = num(flow.mach_number);
  if (ma === null) { const v = num(flow.inlet_velocity); if (v && T) ma = v / Math.sqrt(1.4 * 287.05 * T); }
  if (ma !== null) {
    const incompressible = config.compressible === false || solver.includes("incompressible") || models.incompressible;
    if (ma > 0.3 && incompressible) f("mesh_compressibility", false, "Compressible model for Ma>0.3", `Ma=${ma.toFixed(2)} > 0.3 but incompressible solver selected`, ma, "physics_models");
  }
  if (T !== null && T > 800 && !models.radiation) w("mesh_radiation_model", false, "Radiation modeled at high T", `T=${T.toFixed(0)}K > 800K but radiation off`, T, "physics_models");
  const wallT = flow.wall_temperature !== undefined || Boolean(bc.temperature);
  if (wallT && !models.heat_transfer) w("mesh_heat_transfer_model", false, "Heat-transfer model for thermal BCs", "temperature BCs set but no energy model enabled", null, "physics_models");

  // ── Aggregate ──
  const passed = C.filter((c) => c.status === "passed");
  const warned = C.filter((c) => c.status === "warning");
  const failed = C.filter((c) => c.status === "failed");
  const issues = [...warned, ...failed];
  const status: SetupReport["status"] = failed.length ? "not_ready" : warned.length ? "warning" : "ready";
  const names = new Set(issues.map((i) => i.name));

  const predicted: string[] = [];
  const add = (...cs: string[]) => cs.forEach((c) => !predicted.includes(c) && predicted.push(c));
  if (names.has("mesh_yplus_model_compat") || names.has("mesh_boundary_layer_present")) add("cx_yplus_wall", "th_heat_transfer_coeff", "turb_tke_pos");
  if (names.has("mesh_cfl_explicit") || names.has("mesh_convergence_criterion") || names.has("mesh_max_iterations")) add("ns_nan", "ns_inf", "conv_res_continuity_residual", "input_forward_fill");
  if (names.has("mesh_aspect_ratio") || names.has("mesh_skewness") || names.has("mesh_nonortho")) add("ns_spike", "outlier_velocity", "conv_res_momentum_residual");
  if (names.has("mesh_bc_reynolds_turbulence_match") || names.has("mesh_turbulence_model_appropriate")) add("cx_re_velocity", "turb_tke_pos", "aero_drag_coefficient");
  if (names.has("mesh_bc_reference_values") || names.has("mesh_compressibility")) add("cx_gas_constant_check", "cx_mach_vel", "dim_pressure_units");
  if (names.has("mesh_cell_count_adequacy")) add("stat_high_variance", "conv_res_continuity_residual");

  const weighted = 3 * failed.length + warned.length;
  const risk = weighted === 0 ? 0 : Math.min(1, 1 - Math.exp(-weighted / 4));

  const RECS: Record<string, string> = {
    mesh_yplus_model_compat: "Refine (or coarsen) the near-wall mesh to hit the y+ target for your turbulence model.",
    mesh_nonortho: "Reduce mesh non-orthogonality or add non-orthogonal correctors.",
    mesh_skewness: "Repair degenerate cells before running — they inject numerical noise.",
    mesh_min_cell_quality: "Repair low-quality cells before running.",
    mesh_watertight: "Close the surface mesh — seal open edges and remove duplicate/intersecting faces before meshing the volume.",
    mesh_aspect_ratio: "Lower peak cell aspect ratio to curb numerical diffusion.",
    mesh_cfl_explicit: "Reduce the timestep (or switch to implicit) to satisfy the CFL condition.",
    mesh_convergence_criterion: "Tighten residual targets to ≤1e-4 (≤1e-6 for incompressible pressure).",
    mesh_discretization_order: "Use second-order (or higher) discretization for production accuracy.",
    mesh_compressibility: "Switch to a compressible solver — Ma>0.3 invalidates the incompressible assumption.",
    mesh_bc_reference_values: "Check reference P/ρ/T units — P/(ρT) should equal ~287 J/kg·K.",
    mesh_bc_inlet_outlet_consistency: "Set a pressure reference at the outlet — fixing velocity at both ends is overdetermined.",
  };
  const recSeen = new Set<string>();
  const recommendations: string[] = [];
  for (const i of issues) {
    const r = i.name.startsWith("mesh_relaxation_factors")
      ? "Move relaxation factors into the 0.2–0.9 band."
      : RECS[i.name];
    if (r && !recSeen.has(r)) { recSeen.add(r); recommendations.push(r); }
  }

  return {
    status,
    all_checks: C.length,
    passed: passed.length,
    warnings: warned.length,
    failed: failed.length,
    issues: issues.map((i) => ({ ...i, human_name: humanizeMeshCheck(i.name) })) as MeshIssue[],
    predicted_error_types: predicted,
    predicted_failures: predicted.map((c) => {
      const d = PREDICTED[c];
      return { check: c, label: d?.label ?? c, why: d?.why ?? "", fix: d?.fix ?? "" };
    }),
    estimated_corruption_risk: Math.round(risk * 1000) / 1000,
    recommendations,
    processing_ms: Math.round((performance.now() - t0) * 100) / 100,
  };
}
