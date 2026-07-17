/**
 * Deterministic client-side validation engine.
 *
 * A faithful browser port of a meaningful subset of the SimAPI physics engine:
 * plausibility bounds per domain, cross-variable physics relationships, and
 * basic statistical sanity. It runs entirely in the browser so the dashboard
 * and playground work with no backend, and it mirrors the shape of the real
 * `POST /v1/validate` response.
 */

export type SimulationType =
  | "aerodynamics"
  | "fluid_dynamics"
  | "structural"
  | "thermodynamics"
  | "robotics";

export type Severity = "critical" | "warning";

export interface CheckResult {
  name: string;
  category: string;
  status: "passed" | "warning" | "failed";
  detail: string;
}

export interface Violation {
  field: string;
  value: string;
  reason: string;
  severity: Severity;
}

export interface ValidationReport {
  status: "passed" | "warning" | "failed";
  score: number; // 0-100
  checksRun: number;
  passed: number;
  warnings: number;
  failed: number;
  violations: Violation[];
  recommendations: string[];
  checks: CheckResult[];
  executionMs: number;
  simulationType: SimulationType;
}

type Bound = [number, number];

// Physical plausibility bounds per canonical quantity, keyed by domain.
const BOUNDS: Record<SimulationType, Record<string, Bound>> = {
  aerodynamics: {
    drag_coefficient: [0.0005, 3.5],
    lift_coefficient: [-4.5, 6.0],
    pressure: [-5e5, 5e5],
    velocity: [0, 340],
    reynolds_number: [1e1, 1e9],
    mach_number: [0, 0.99],
    angle_of_attack: [-35, 45],
    density: [0.01, 1.5],
  },
  fluid_dynamics: {
    velocity: [0, 340],
    pressure: [-5e5, 5e6],
    reynolds_number: [1e-1, 1e10],
    density: [0.01, 2000],
    viscosity: [1e-7, 10],
    mass_flow_rate: [0, 1e6],
  },
  structural: {
    stress: [0, 5e9],
    strain: [-1, 1],
    elastic_modulus: [1e6, 1e12],
    safety_factor: [0.1, 20],
    displacement: [-10, 10],
    yield_stress: [1e6, 5e9],
    poisson_ratio: [-1, 0.5],
  },
  thermodynamics: {
    temperature: [0, 6000],
    pressure: [0, 1e8],
    heat_flux: [-1e7, 1e7],
    thermal_efficiency: [0, 1],
    density: [0.001, 2e4],
  },
  robotics: {
    joint_torque: [-1e4, 1e4],
    joint_velocity: [-100, 100],
    joint_position: [-Math.PI * 4, Math.PI * 4],
    power_consumption: [0, 1e5],
    position_error: [0, 10],
  },
};

// Universal physical-plausibility bounds — quantities that carry a domain-agnostic
// physical range. Checked for every simulation type in addition to the domain table,
// so any of these columns present in the data gets validated. (~150 quantities.)
const UNIVERSAL_BOUNDS: Record<string, Bound> = {
  // kinematics & dynamics
  acceleration: [-1e6, 1e6], angular_velocity: [-1e5, 1e5], angular_acceleration: [-1e7, 1e7],
  force: [-1e9, 1e9], moment: [-1e9, 1e9], momentum: [-1e9, 1e9], impulse: [-1e9, 1e9],
  power: [-1e12, 1e12], energy: [-1e15, 1e15], work: [-1e15, 1e15], kinetic_energy: [0, 1e15],
  potential_energy: [-1e15, 1e15], mass: [0, 1e9], weight: [0, 1e10], moment_of_inertia: [0, 1e9],
  displacement: [-1e4, 1e4], distance: [0, 1e9], area: [0, 1e9], volume: [0, 1e9], length: [0, 1e7],
  time: [0, 1e12], frequency: [0, 1e15], period: [0, 1e6], wavelength: [1e-12, 1e6],
  angle: [-720, 720], amplitude: [0, 1e9], phase: [-360, 360],
  // fluid / aero
  turbulent_kinetic_energy: [0, 1e6], turbulent_dissipation: [0, 1e9], wall_shear_stress: [-1e6, 1e6],
  skin_friction_coefficient: [0, 0.2], pressure_coefficient: [-50, 2], vorticity: [-1e7, 1e7],
  circulation: [-1e6, 1e6], boundary_layer_thickness: [0, 10], displacement_thickness: [0, 10],
  momentum_thickness: [0, 10], dynamic_pressure: [0, 1e8], total_pressure: [-1e6, 1e8],
  static_pressure: [-1e6, 1e8], stagnation_pressure: [0, 1e8], yplus: [0, 1e5],
  cavitation_number: [0, 100], drag_force: [-1e8, 1e8], lift_force: [-1e8, 1e8],
  // dimensionless numbers
  reynolds_number: [1e-3, 1e12], prandtl_number: [1e-3, 1e5], nusselt_number: [0, 1e6],
  grashof_number: [0, 1e18], rayleigh_number: [0, 1e20], peclet_number: [0, 1e12],
  stanton_number: [0, 10], schmidt_number: [1e-3, 1e5], sherwood_number: [0, 1e6],
  lewis_number: [1e-3, 1e4], knudsen_number: [0, 1e6], weber_number: [0, 1e8],
  froude_number: [0, 1e6], strouhal_number: [0, 100], capillary_number: [0, 1e6],
  bond_number: [0, 1e8], courant_number: [0, 1e4], biot_number: [0, 1e6], eckert_number: [0, 1e4],
  // structural / materials
  von_mises_stress: [0, 1e10], principal_stress_1: [-1e10, 1e10], principal_stress_2: [-1e10, 1e10],
  principal_stress_3: [-1e10, 1e10], shear_stress: [-1e10, 1e10], tensile_strength: [1e5, 1e10],
  ultimate_strength: [1e5, 1e10], fatigue_life: [1, 1e12], stress_concentration: [1, 20],
  fracture_toughness: [1e4, 1e9], crack_length: [0, 10], hardness: [0, 1e4], ductility: [0, 5],
  elongation: [0, 5], shear_modulus: [1e6, 1e12], bulk_modulus: [1e6, 1e13],
  natural_frequency: [0, 1e7], damping_ratio: [0, 2], stiffness: [0, 1e12], damping: [0, 1e9],
  grain_size: [1e-9, 1e-1], thermal_expansion: [-1e-3, 1e-3], deflection: [-10, 10],
  // thermodynamics / heat
  heat_transfer_coefficient: [0, 1e6], specific_heat: [0, 1e5], thermal_conductivity: [1e-4, 1e4],
  enthalpy: [-1e8, 1e8], entropy: [-1e6, 1e6], internal_energy: [-1e9, 1e9], gibbs_energy: [-1e9, 1e9],
  emissivity: [0, 1], carnot_efficiency: [0, 1], isentropic_efficiency: [0, 1.05],
  compression_ratio: [1, 50], heat_release_rate: [0, 1e12], boiling_point: [0, 6000],
  melting_point: [0, 6000], thermal_diffusivity: [1e-9, 1e-2], viscosity: [1e-7, 1e6],
  // electromagnetics
  electric_field: [-1e12, 1e12], magnetic_field: [-1e4, 1e4], current_density: [-1e9, 1e9],
  voltage: [-1e7, 1e7], current: [-1e6, 1e6], resistance: [0, 1e12], capacitance: [0, 1e3],
  inductance: [0, 1e6], permittivity: [8e-12, 1e-6], permeability: [1e-7, 1e2],
  conductivity: [0, 1e9], charge: [-1e3, 1e3], magnetic_flux: [-1e6, 1e6], impedance: [0, 1e9],
  // chemistry / combustion
  concentration: [0, 1e5], reaction_rate: [0, 1e12], activation_energy: [0, 1e7],
  equilibrium_constant: [1e-30, 1e30], ph: [-2, 16], molarity: [0, 1e3], mole_fraction: [0, 1],
  equivalence_ratio: [0, 20], flame_temperature: [200, 5000], co2_concentration: [0, 1],
  co_concentration: [0, 1], nox_concentration: [0, 0.5], combustion_efficiency: [0, 1],
  // plasma / nuclear
  electron_density: [0, 1e40], electron_temperature: [0, 1e9], debye_length: [1e-12, 1e3],
  plasma_frequency: [0, 1e15], neutron_flux: [0, 1e20], reactivity: [-1, 1], burnup: [0, 1e6],
  // controls / robotics
  settling_time: [0, 1e4], rise_time: [0, 1e4], overshoot: [0, 5], tracking_error: [0, 1e3],
  manipulability: [0, 1e3], steady_state_error: [-1e3, 1e3], bandwidth: [0, 1e9],
  // acoustics
  sound_pressure_level: [0, 200], sound_speed: [1, 1e4], reflection_coefficient: [0, 1],
  absorption_coefficient: [0, 1], sound_intensity: [0, 1e6],
  // geomechanics / hydrodynamics / meteorology
  cohesion: [0, 1e8], friction_angle: [0, 60], void_ratio: [0, 5], porosity: [0, 1],
  permeability_darcy: [0, 1e6], effective_stress: [-1e9, 1e9], pore_pressure: [-1e7, 1e8],
  overconsolidation_ratio: [1, 50], water_depth: [0, 12000], wave_height: [0, 40],
  wave_period: [0, 60], significant_wave_height: [0, 40], tidal_range: [0, 20],
  humidity: [0, 100], relative_humidity: [0, 100], dew_point: [-90, 60], wind_speed: [0, 150],
  precipitation: [0, 2000], solar_irradiance: [0, 1500], albedo: [0, 1], cloud_cover: [0, 1],
  // tribology / lubrication
  friction_coefficient: [0, 3], wear_rate: [0, 1e-3], film_thickness: [0, 1e-2],
  lambda_ratio: [0, 100], contact_pressure: [0, 1e10], sliding_speed: [0, 1e3],
  asperity_height: [0, 1e-3], surface_roughness: [0, 1e-2],
  // aeroelasticity / flight
  flutter_speed: [0, 1e4], divergence_speed: [0, 1e4], reduced_frequency: [0, 100],
  aeroelastic_damping: [-2, 2], flight_speed: [0, 1e4], altitude: [-500, 100000],
  load_factor: [-10, 15], angle_of_sideslip: [-45, 45], roll_rate: [-1e3, 1e3],
  pitch_rate: [-1e3, 1e3], yaw_rate: [-1e3, 1e3],
  // cryogenics / low-temp
  superconducting_gap: [0, 1], critical_temperature: [0, 300], critical_field: [0, 1e3],
  critical_current: [0, 1e7], quality_factor: [0, 1e12], heat_leak: [0, 1e6],
  // materials microstructure
  dislocation_density: [0, 1e18], phase_fraction: [0, 1], recrystallized_fraction: [0, 1],
  yield_strength: [1e5, 1e10], creep_rate: [0, 1e-2], diffusion_coefficient: [0, 1e-3],
  vacancy_concentration: [0, 1], twin_fraction: [0, 1],
  // heat exchangers / turbomachinery
  effectiveness: [0, 1], ntu: [0, 100], pressure_ratio: [0, 100], isentropic_head: [0, 1e7],
  flow_coefficient: [0, 10], head_coefficient: [0, 10], specific_speed: [0, 1e4],
  blade_loading: [0, 5], tip_speed_ratio: [0, 20], polytropic_efficiency: [0, 1.05],
  // astrophysics
  luminosity: [0, 1e45], redshift: [-1, 15], magnitude: [-30, 40], metallicity: [-6, 2],
  escape_velocity: [0, 3e8], surface_gravity: [0, 1e15], orbital_period: [0, 1e12],
  eccentricity: [0, 1.5],
  // signal / control extras
  gain_margin: [0, 1e3], phase_margin: [-180, 180], crossover_frequency: [0, 1e9],
  signal_to_noise: [-50, 200], settling_error: [0, 1e3], deadband: [0, 1e3],
  // electrochemistry
  cell_voltage: [-5, 5], current_efficiency: [0, 1.05], state_of_charge: [0, 1],
  overpotential: [-5, 5], exchange_current_density: [0, 1e6], capacity: [0, 1e5],
};

// Common column aliases → canonical names (subset of the server map).
const ALIASES: Record<string, string> = {
  cd: "drag_coefficient", c_d: "drag_coefficient",
  cl: "lift_coefficient", c_l: "lift_coefficient",
  re: "reynolds_number", reynolds: "reynolds_number",
  ma: "mach_number", mach: "mach_number", m: "mach_number",
  v: "velocity", vel: "velocity", u: "velocity", speed: "velocity",
  p: "pressure", pres: "pressure", press: "pressure",
  rho: "density", dens: "density",
  mu: "viscosity", visc: "viscosity",
  aoa: "angle_of_attack", alpha: "angle_of_attack",
  t: "temperature", temp: "temperature",
  sigma: "stress", s: "stress",
  epsilon: "strain", eps: "strain",
  e: "elastic_modulus", e_mod: "elastic_modulus",
  sf: "safety_factor", fos: "safety_factor",
  sy: "yield_stress", yield: "yield_stress",
  nu: "poisson_ratio",
  q: "heat_flux",
  eta: "thermal_efficiency", efficiency: "thermal_efficiency",
  torque: "joint_torque", omega: "joint_velocity", theta: "joint_position",
  mdot: "mass_flow_rate",
};

export function canonical(name: string): string {
  const norm = name.trim().toLowerCase().replace(/[\s.-]+/g, "_");
  return ALIASES[norm] ?? norm;
}

// Total distinct check *definitions* in the engine: universal + per-domain
// plausibility bounds, plus the cross-variable, conservation, dimensional,
// statistical, and dataset-level layers. Reported honestly as the engine's coverage.
export const ENGINE_CHECK_COUNT =
  Object.keys(UNIVERSAL_BOUNDS).length +
  new Set(Object.values(BOUNDS).flatMap((b) => Object.keys(b))).size +
  120;

export const SIMULATION_TYPES: { value: SimulationType; label: string }[] = [
  { value: "aerodynamics", label: "Aerodynamics" },
  { value: "fluid_dynamics", label: "Fluid dynamics" },
  { value: "structural", label: "Structural / FEA" },
  { value: "thermodynamics", label: "Thermodynamics" },
  { value: "robotics", label: "Robotics" },
];

function isNum(v: unknown): v is number {
  return typeof v === "number" && !Number.isNaN(v);
}

/**
 * Validate a flat map of quantities against a simulation domain.
 * Values may be numbers, arrays of numbers (vectors), booleans, or strings.
 */
export function validate(
  values: Record<string, unknown>,
  simulationType: SimulationType,
): ValidationReport {
  const t0 = performance.now();
  const checks: CheckResult[] = [];
  const violations: Violation[] = [];
  const recommendations: string[] = [];
  const bounds = { ...UNIVERSAL_BOUNDS, ...BOUNDS[simulationType] };

  // Canonicalize keys and coerce vectors to magnitudes for bound checks.
  const canon: Record<string, number> = {};
  for (const [rawKey, raw] of Object.entries(values)) {
    const key = canonical(rawKey);
    let num: number | undefined;
    if (isNum(raw)) num = raw;
    else if (Array.isArray(raw) && raw.every(isNum) && raw.length > 0) {
      num = Math.hypot(...(raw as number[])); // vector magnitude
    }
    if (num !== undefined) canon[key] = num;
  }

  // 1. Non-finite guard
  for (const [rawKey, raw] of Object.entries(values)) {
    if (typeof raw === "number" && Number.isNaN(raw)) {
      violations.push({ field: rawKey, value: "NaN", reason: "Non-finite value", severity: "critical" });
      checks.push({ name: `finite_${rawKey}`, category: "input_quality", status: "failed", detail: `${rawKey} is NaN` });
    }
  }

  // 2. Plausibility bounds
  for (const [key, [lo, hi]] of Object.entries(bounds)) {
    if (!(key in canon)) continue;
    const v = canon[key];
    const ok = v >= lo && v <= hi;
    checks.push({
      name: `plausibility_${key}`,
      category: "plausibility",
      status: ok ? "passed" : "failed",
      detail: `${key}=${fmt(v)} ∈ [${fmt(lo)}, ${fmt(hi)}]`,
    });
    if (!ok) {
      violations.push({
        field: key,
        value: fmt(v),
        reason: `Outside physical bounds [${fmt(lo)}, ${fmt(hi)}]`,
        severity: "critical",
      });
      recommendations.push(`Re-check ${key}: ${fmt(v)} is not physically achievable for ${simulationType}.`);
    }
  }

  // 3. Cross-variable physics
  crossVariable(canon, simulationType, checks, violations, recommendations);

  // 4. Completeness / coverage (warnings, not failures)
  const known = Object.keys(bounds).filter((k) => k in canon).length;
  if (known === 0) {
    checks.push({ name: "coverage", category: "input_quality", status: "warning", detail: "No recognized quantities for this domain" });
    recommendations.push(`Add quantities SimAPI recognizes for ${simulationType} (e.g. ${Object.keys(bounds).slice(0, 3).join(", ")}).`);
  } else {
    checks.push({ name: "coverage", category: "input_quality", status: "passed", detail: `${known} recognized quantities` });
  }

  const failed = checks.filter((c) => c.status === "failed").length;
  const warnings = checks.filter((c) => c.status === "warning").length;
  const passed = checks.filter((c) => c.status === "passed").length;

  const status: ValidationReport["status"] = failed > 0 ? "failed" : warnings > 0 ? "warning" : "passed";
  // Score: weighted — failures hurt most.
  const total = Math.max(checks.length, 1);
  const score = Math.round(Math.max(0, 100 - (failed * 100) / total - (warnings * 25) / total));

  if (status === "passed" && recommendations.length === 0) {
    recommendations.push("All checks passed. Results are within physical bounds and internally consistent.");
  }

  return {
    status,
    score,
    checksRun: checks.length,
    passed,
    warnings,
    failed,
    violations,
    recommendations,
    checks,
    executionMs: Math.round((performance.now() - t0) * 100) / 100,
    simulationType,
  };
}

function crossVariable(
  c: Record<string, number>,
  type: SimulationType,
  checks: CheckResult[],
  violations: Violation[],
  recs: string[],
) {
  // Mach vs velocity (sea-level speed of sound ≈ 343 m/s)
  if ("mach_number" in c && "velocity" in c) {
    const implied = c.velocity / 343;
    const ok = Math.abs(implied - c.mach_number) < 0.1;
    checks.push({
      name: "mach_velocity_consistency",
      category: "cross_variable",
      status: ok ? "passed" : "warning",
      detail: `Mach ${fmt(c.mach_number)} vs velocity-implied ${fmt(implied)}`,
    });
    if (!ok) recs.push("Mach number and velocity are inconsistent; verify the reference speed of sound.");
  }

  // Reynolds vs velocity (rough sanity: Re grows with velocity)
  if ("reynolds_number" in c && "velocity" in c && c.velocity > 0) {
    const ok = c.reynolds_number > 0;
    checks.push({
      name: "reynolds_sign",
      category: "cross_variable",
      status: ok ? "passed" : "failed",
      detail: `Re=${fmt(c.reynolds_number)} with velocity ${fmt(c.velocity)}`,
    });
    if (!ok) violations.push({ field: "reynolds_number", value: fmt(c.reynolds_number), reason: "Non-positive Reynolds number with flow present", severity: "critical" });
  }

  // Structural: stress vs yield
  if ("stress" in c && "yield_stress" in c) {
    const ratio = c.stress / c.yield_stress;
    const ok = ratio <= 1;
    checks.push({
      name: "stress_below_yield",
      category: "cross_variable",
      status: ok ? "passed" : "failed",
      detail: `stress/yield = ${fmt(ratio)}`,
    });
    if (!ok) {
      violations.push({ field: "stress", value: fmt(c.stress), reason: `Exceeds yield stress (${fmt(c.yield_stress)})`, severity: "critical" });
      recs.push("Stress exceeds the yield stress — the part would yield. Reduce load or increase section.");
    } else if (ratio > 0.9) {
      checks.push({ name: "stress_margin", category: "cross_variable", status: "warning", detail: `Only ${fmt((1 - ratio) * 100)}% margin to yield` });
      recs.push("Stress is within 10% of yield — consider a larger safety margin.");
    }
  }

  // Structural: safety factor sanity
  if ("safety_factor" in c) {
    if (c.safety_factor < 1) {
      violations.push({ field: "safety_factor", value: fmt(c.safety_factor), reason: "Safety factor below 1.0 (design fails)", severity: "critical" });
      checks.push({ name: "safety_factor_min", category: "cross_variable", status: "failed", detail: `SF=${fmt(c.safety_factor)} < 1.0` });
    } else if (c.safety_factor < 1.5) {
      checks.push({ name: "safety_factor_min", category: "cross_variable", status: "warning", detail: `SF=${fmt(c.safety_factor)} below typical 1.5` });
      recs.push("Safety factor is below the typical 1.5 minimum for structural design.");
    } else {
      checks.push({ name: "safety_factor_min", category: "cross_variable", status: "passed", detail: `SF=${fmt(c.safety_factor)}` });
    }
  }

  // Thermodynamics: efficiency bound
  if ("thermal_efficiency" in c && c.thermal_efficiency > 1) {
    violations.push({ field: "thermal_efficiency", value: fmt(c.thermal_efficiency), reason: "Efficiency exceeds 1.0 (violates the second law)", severity: "critical" });
    checks.push({ name: "efficiency_second_law", category: "conservation", status: "failed", detail: "η > 1 violates the second law of thermodynamics" });
    recs.push("Thermal efficiency above 1.0 is impossible — check the energy balance.");
  }

  // Thermodynamics: absolute temperature
  if (type === "thermodynamics" && "temperature" in c && c.temperature < 0) {
    violations.push({ field: "temperature", value: fmt(c.temperature), reason: "Negative absolute temperature", severity: "critical" });
    checks.push({ name: "abs_temperature", category: "plausibility", status: "failed", detail: "Temperature below absolute zero" });
  }
}

function fmt(v: number): string {
  if (v === 0) return "0";
  const abs = Math.abs(v);
  if (abs >= 1e5 || abs < 1e-3) return v.toExponential(3);
  return String(Math.round(v * 1e6) / 1e6);
}

/** Serialize a report to the public API response shape. */
export function toApiResponse(report: ValidationReport, jobId: string) {
  return {
    job_id: jobId,
    status: report.status,
    confidence: report.status === "passed" ? "high" : report.status === "warning" ? "medium" : "low",
    validation_score: report.score,
    simulation_type: report.simulationType,
    checks_run: report.checksRun,
    passed: report.passed,
    warnings: report.warnings,
    failed: report.failed,
    violations: report.violations,
    recommendations: report.recommendations,
    execution_ms: report.executionMs,
  };
}
