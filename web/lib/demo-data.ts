/**
 * Demo scenarios for the interactive validation experience.
 *
 * Each scenario mirrors the real SimAPI response shape (status / scores /
 * anomalies / AI summary) plus lightweight chart series so the dashboard can
 * render pressure, velocity, and residual-timeline visuals entirely client-side.
 */

export type Verdict = "pass" | "warning" | "fail";

export interface Anomaly {
  trial: number;
  field: string;
  value: string;
  reason: string;
  severity: "critical" | "warning";
}

export interface Scenario {
  id: string;
  label: string;
  blurb: string;
  verdict: Verdict;
  physicsScore: number; // 0-100
  statisticalScore: number; // 0-100
  aiConfidence: number; // 0-100
  trials: number;
  excluded: number;
  checksRun: number;
  processingMs: number;
  anomalies: Anomaly[];
  warnings: string[];
  fixes: string[];
  aiSummary: string;
  // Chart series
  pressure: number[]; // pressure coefficient along chord
  velocity: number[]; // boundary-layer velocity profile
  residuals: number[]; // solver convergence (log residual per iteration)
  heatmap: number[][]; // small field grid, 0..1
}

function grid(seed: number, hot: boolean): number[][] {
  const rows = 8;
  const cols = 14;
  const out: number[][] = [];
  for (let r = 0; r < rows; r++) {
    const row: number[] = [];
    for (let c = 0; c < cols; c++) {
      const base =
        Math.sin((c / cols) * Math.PI * 1.4 + seed) * 0.5 +
        0.5 -
        Math.abs(r - rows / 2) / rows;
      const spike = hot && r === 3 && c === 10 ? 0.9 : 0;
      row.push(Math.max(0, Math.min(1, base * 0.8 + 0.15 + spike)));
    }
    out.push(row);
  }
  return out;
}

const chord = Array.from({ length: 40 }, (_, i) => i / 39);

export const scenarios: Scenario[] = [
  {
    id: "good",
    label: "Clean run",
    blurb: "A well-converged aerodynamics sweep.",
    verdict: "pass",
    physicsScore: 98,
    statisticalScore: 96,
    aiConfidence: 94,
    trials: 200,
    excluded: 0,
    checksRun: 287,
    processingMs: 23,
    anomalies: [],
    warnings: [],
    fixes: [],
    aiSummary:
      "Distributions are physically coherent for the stated Reynolds number. Drag and lift coefficients fall within realistic envelopes, residuals converge monotonically, and there is no evidence of synthetic artifacts. Dataset is training-ready.",
    pressure: chord.map((x) => -3.1 * Math.exp(-14 * x) + 0.9 * x - 0.15),
    velocity: chord.map((y) => 1 - Math.exp(-6.2 * y)),
    residuals: Array.from({ length: 24 }, (_, i) => -1 - i * 0.28 + Math.random() * 0.08),
    heatmap: grid(0.4, false),
  },
  {
    id: "broken",
    label: "Broken run",
    blurb: "Diverged solver with unphysical outputs.",
    verdict: "fail",
    physicsScore: 34,
    statisticalScore: 41,
    aiConfidence: 88,
    trials: 200,
    excluded: 37,
    checksRun: 287,
    processingMs: 29,
    anomalies: [
      { trial: 15, field: "drag_coefficient", value: "999.0", reason: "Exceeds physical bound (0.0005–3.5)", severity: "critical" },
      { trial: 42, field: "drag_coefficient", value: "NaN", reason: "Non-finite value in target column", severity: "critical" },
      { trial: 87, field: "lift_coefficient", value: "-50.0", reason: "Outside plausible lift envelope", severity: "critical" },
      { trial: 133, field: "mach_number", value: "1.42", reason: "Supersonic value in subsonic sweep", severity: "warning" },
    ],
    warnings: [
      "Residuals plateau above 1e-2 — solver did not converge.",
      "18.5% of trials excluded — dataset not training-ready.",
    ],
    fixes: [
      "Re-run trials 15, 42, 87 with a tighter CFL number.",
      "Add a convergence gate before export (residual < 1e-4).",
      "Clamp or reject non-finite target values at the source.",
    ],
    aiSummary:
      "This run shows clear signs of solver divergence: a saturated drag value (999), a NaN target, and a negative lift far outside any realistic envelope. The residual trace never drops below 1e-2. Do not use for design decisions or ML training until re-run.",
    pressure: chord.map((x) => -3.1 * Math.exp(-14 * x) + 0.9 * x - 0.15 + (x > 0.5 ? Math.sin(x * 60) * 0.6 : 0)),
    velocity: chord.map((y) => 1 - Math.exp(-6.2 * y) + Math.sin(y * 40) * 0.12),
    residuals: Array.from({ length: 24 }, (_, i) => -1 - Math.min(i, 6) * 0.18 + Math.random() * 0.2),
    heatmap: grid(1.1, true),
  },
  {
    id: "edge",
    label: "Edge case",
    blurb: "Valid but near physical limits.",
    verdict: "warning",
    physicsScore: 82,
    statisticalScore: 79,
    aiConfidence: 76,
    trials: 200,
    excluded: 4,
    checksRun: 287,
    processingMs: 25,
    anomalies: [
      { trial: 55, field: "velocity", value: "14.2", reason: "Velocity/Mach mismatch vs. stated conditions", severity: "warning" },
      { trial: 178, field: "angle_of_attack", value: "34.8°", reason: "Approaching stall boundary", severity: "warning" },
    ],
    warnings: [
      "Narrow parameter coverage — single flow regime.",
      "Two trials sit within 5% of a hard physical bound.",
    ],
    fixes: [
      "Broaden the angle-of-attack sweep to improve generalization.",
      "Verify the conditions block matches trial 55's velocity.",
    ],
    aiSummary:
      "The data is physically valid but operates close to the stall boundary and covers a narrow regime. Usable for validation, but an ML model trained here may not generalize beyond this envelope. Consider expanding the sweep.",
    pressure: chord.map((x) => -2.6 * Math.exp(-12 * x) + 1.1 * x - 0.2),
    velocity: chord.map((y) => 1 - Math.exp(-5.4 * y)),
    residuals: Array.from({ length: 24 }, (_, i) => -1 - i * 0.22 + Math.random() * 0.1),
    heatmap: grid(0.8, false),
  },
  {
    id: "noise",
    label: "Noise corrupted",
    blurb: "Sensor noise and quantization artifacts.",
    verdict: "warning",
    physicsScore: 71,
    statisticalScore: 58,
    aiConfidence: 83,
    trials: 200,
    excluded: 9,
    checksRun: 287,
    processingMs: 27,
    anomalies: [
      { trial: 12, field: "pressure", value: "±quantized", reason: "Suspicious round-number clustering (sensor quantization)", severity: "warning" },
      { trial: 96, field: "drag_coefficient", value: "high CV", reason: "Coefficient of variation 3× expected", severity: "warning" },
    ],
    warnings: [
      "High-frequency noise detected in pressure channel.",
      "Distribution kurtosis suggests measurement artifacts.",
    ],
    fixes: [
      "Apply a low-pass filter to the pressure channel before export.",
      "Increase sensor resolution or averaging window.",
    ],
    aiSummary:
      "Statistical fingerprints point to sensor noise and quantization rather than a modeling error — the underlying physics is plausible but the signal is corrupted. Filtering the pressure channel should recover a clean, training-ready dataset.",
    pressure: chord.map((x) => -3.0 * Math.exp(-14 * x) + 0.9 * x - 0.15 + (Math.random() - 0.5) * 0.5),
    velocity: chord.map((y) => 1 - Math.exp(-6.2 * y) + (Math.random() - 0.5) * 0.18),
    residuals: Array.from({ length: 24 }, (_, i) => -1 - i * 0.24 + (Math.random() - 0.5) * 0.3),
    heatmap: grid(1.6, false),
  },
];

export const verdictMeta: Record<Verdict, { label: string; color: string; ring: string }> = {
  pass: { label: "PASS", color: "text-pass", ring: "ring-pass/30 bg-pass/10" },
  warning: { label: "WARNING", color: "text-warn", ring: "ring-warn/30 bg-warn/10" },
  fail: { label: "FAIL", color: "text-fail", ring: "ring-fail/30 bg-fail/10" },
};

export const pipelineStages = [
  { key: "parse", label: "Parsing dataset", detail: "Detecting format · normalizing 24 column aliases" },
  { key: "physics", label: "Running deterministic validation", detail: "287 physics checks across 21 domains" },
  { key: "ai", label: "Running AI analysis", detail: "Second-pass reasoning over full distributions" },
  { key: "report", label: "Generating report", detail: "Scoring · anomalies · recommendations" },
] as const;
