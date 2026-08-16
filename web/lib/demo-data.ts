/**
 * Built-in demo datasets for the validation playground.
 *
 * These are NOT fixtures — each generator returns a plain array of trial
 * records that is fed through the real deterministic engine
 * (lib/rich-validate.ts) by POST /api/v1/demo. What the dashboard renders is
 * whatever that engine actually detects, so a visitor clicking a demo watches a
 * genuine physics/statistics violation get caught, with a real explanation.
 *
 * Every dataset is deterministic (seeded) so the demo is stable across reloads.
 */

export type SimulationType = "aerodynamics" | "fluid_dynamics";

export interface DemoCase {
  id: string;
  label: string;
  /** One-line description of what the visitor should expect to see. */
  blurb: string;
  simulationType: SimulationType;
  /** What the engine returns for this dataset — for UI labelling only. */
  expected: "passed" | "failed";
  /** The corruption the engine is expected to surface (empty for the clean case). */
  detects: string;
  trials: number;
  generate: () => Record<string, unknown>[];
}

/** Small, fast, deterministic PRNG (mulberry32) so demos never drift. */
function rng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s |= 0;
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const N = 200;

/**
 * A well-converged subsonic aerodynamics sweep. Every value sits inside its
 * physical envelope and the cross-variable relationships hold, so the engine
 * returns PASSED with zero exclusions.
 */
export function cleanAeroDataset(): Record<string, unknown>[] {
  const r = rng(12345);
  const rows: Record<string, unknown>[] = [];
  for (let i = 0; i < N; i++) {
    const v = 15 + (r() - 0.5) * 0.6;
    rows.push({
      drag_coefficient: round(0.31 + (r() - 0.5) * 0.02, 5),
      lift_coefficient: round(0.84 + (r() - 0.5) * 0.03, 5),
      reynolds_number: Math.round(415000 + (r() - 0.5) * 20000),
      mach_number: round(v / 343 + (r() - 0.5) * 0.001, 5), // stays consistent with velocity
      velocity: round(v, 3),
    });
  }
  return rows;
}

/**
 * A diverged CFD/aero run: the solver blew up on a handful of trials, producing
 * a saturated drag value, a NaN target, an impossible negative lift, and a
 * supersonic Mach number inside a subsonic sweep. The engine excludes each and
 * returns FAILED.
 */
export function divergedAeroDataset(): Record<string, unknown>[] {
  const rows = cleanAeroDataset();
  rows.forEach((row, i) => {
    if (i % 23 === 0) row.drag_coefficient = 999.0;          // saturated / out of bounds
    else if (i % 31 === 0) row.drag_coefficient = NaN;       // non-finite target
    else if (i % 37 === 0) row.lift_coefficient = -50.0;     // impossible lift
    else if (i % 41 === 0) row.mach_number = 1.42;           // supersonic in a subsonic sweep
  });
  return rows;
}

/**
 * The subtle one. A clean CFD dataset where ~12% of rows had their pressure
 * logged in kPa instead of Pa. Every individual pressure value is physically
 * plausible on its own — only the anchored gas constant P/(rho*T) reveals the
 * error: it reads ~0.287 instead of 287 J/(kg*K). The engine excludes exactly
 * those rows and returns FAILED, with a root-cause explanation.
 */
export function unitErrorDataset(): Record<string, unknown>[] {
  const r = rng(6789);
  const rows: Record<string, unknown>[] = [];
  for (let i = 0; i < N; i++) {
    const pressurePa = 101325 + (r() - 0.5) * 400;
    const density = round(1.225 + (r() - 0.5) * 0.01, 5);
    const temperature = round(288 + (r() - 0.5) * 2, 3);
    const unitError = i % 8 === 0; // ~12.5% of rows recorded in kPa
    rows.push({
      pressure: round(unitError ? pressurePa / 1000 : pressurePa, 3),
      density,
      temperature,
      velocity: round(30 + (r() - 0.5) * 1.2, 3),
      reynolds_number: Math.round(2.0e6 + (r() - 0.5) * 5e4),
    });
  }
  return rows;
}

export const DEMO_CASES: DemoCase[] = [
  {
    id: "clean",
    label: "Clean run",
    blurb: "A well-converged subsonic sweep — expect PASSED, no exclusions.",
    simulationType: "aerodynamics",
    expected: "passed",
    detects: "",
    trials: N,
    generate: cleanAeroDataset,
  },
  {
    id: "diverged",
    label: "Diverged solver",
    blurb: "Saturated drag (999), a NaN target, negative lift, a supersonic Mach — expect FAILED.",
    simulationType: "aerodynamics",
    expected: "failed",
    detects: "solver divergence · out-of-bounds · non-finite values",
    trials: N,
    generate: divergedAeroDataset,
  },
  {
    id: "unit_error",
    label: "Unit error (Pa vs kPa)",
    blurb: "Pressure logged in kPa on ~1 in 8 rows — caught by the anchored gas constant P/(ρT).",
    simulationType: "fluid_dynamics",
    expected: "failed",
    detects: "unit conversion error via P/(ρT) ≈ 287 J/(kg·K)",
    trials: N,
    generate: unitErrorDataset,
  },
];

/** Resolve a demo case id to its dataset. Defaults to the diverged case. */
export function demoData(caseId?: string): { data: Record<string, unknown>[]; case: DemoCase } {
  const c = DEMO_CASES.find((d) => d.id === caseId) ?? DEMO_CASES[1];
  return { data: c.generate(), case: c };
}

function round(v: number, digits: number): number {
  const f = 10 ** digits;
  return Math.round(v * f) / f;
}
