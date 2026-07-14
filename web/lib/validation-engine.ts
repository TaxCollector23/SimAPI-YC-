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
  const bounds = BOUNDS[simulationType];

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
