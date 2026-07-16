/**
 * Aggregates the deterministic engine over a batch of trials into the rich
 * response shape the validation dashboard (ported from the desktop app) expects:
 * issues, exclusions, per-column statistics, checks-by-category, and renames.
 */
import { validate, canonical, type SimulationType, type CheckResult } from "./validation-engine";

export interface RichIssue {
  name: string;
  human_name: string;
  status: "warning" | "failed";
  description: string;
  detail: string;
  value: number | null;
  category: string;
}

export interface RichStat {
  mean: number; std: number; median: number;
  p5: number; p95: number; min: number; max: number;
  n: number; skewness: number; cv: number;
}

export interface RichResult {
  job_id: string;
  status: "passed" | "warning" | "failed";
  confidence: "high" | "medium" | "low";
  trials_submitted: number;
  trials_valid: number;
  trials_excluded: number;
  exclusion_rate: number;
  training_ready: boolean;
  processing_ms: number;
  all_checks: number;
  unique_checks: number;
  passed: number;
  warnings: number;
  failed: number;
  issues: RichIssue[];
  exclusions: { trial_number: number; trial_index: number; reason: string; severity: string }[];
  statistics: Record<string, RichStat>;
  checks_by_category: Record<string, { passed: number; warning: number; failed: number }>;
  columns_renamed: Record<string, string>;
}

function humanize(check: CheckResult): string {
  const cat = check.category.replace(/_/g, " ");
  if (check.category === "plausibility") return `Value outside its physical range — ${check.detail}`;
  if (check.category === "cross_variable") return `Cross-variable inconsistency — ${check.detail}`;
  if (check.category === "conservation") return `Conservation law violated — ${check.detail}`;
  if (check.category === "input_quality") return `Data quality issue — ${check.detail}`;
  return `${cat}: ${check.detail}`;
}

function stats(values: number[]): RichStat {
  const v = values.filter((x) => Number.isFinite(x)).sort((a, b) => a - b);
  const n = v.length;
  if (n === 0) return { mean: 0, std: 0, median: 0, p5: 0, p95: 0, min: 0, max: 0, n: 0, skewness: 0, cv: 0 };
  const mean = v.reduce((a, x) => a + x, 0) / n;
  const variance = v.reduce((a, x) => a + (x - mean) ** 2, 0) / n;
  const std = Math.sqrt(variance);
  const q = (p: number) => v[Math.min(n - 1, Math.max(0, Math.floor(p * (n - 1))))];
  const skew = std > 0 ? v.reduce((a, x) => a + ((x - mean) / std) ** 3, 0) / n : 0;
  return {
    mean, std, median: q(0.5), p5: q(0.05), p95: q(0.95),
    min: v[0], max: v[n - 1], n, skewness: skew, cv: mean !== 0 ? std / Math.abs(mean) : 0,
  };
}

export function richValidate(rows: Record<string, unknown>[], simType: SimulationType, jobId: string): RichResult {
  const t0 = performance.now();
  let passed = 0, warnings = 0, failed = 0, allChecks = 0, excluded = 0;
  const issueMap = new Map<string, RichIssue>();
  const exclusions: RichResult["exclusions"] = [];
  const byCat: Record<string, { passed: number; warning: number; failed: number }> = {};
  const columnsRenamed: Record<string, string> = {};
  const columnValues: Record<string, number[]> = {};
  const uniqueCheckNames = new Set<string>();

  rows.forEach((trial, i) => {
    // Track renames + collect numeric columns for statistics.
    for (const [rawKey, raw] of Object.entries(trial)) {
      const canon = canonical(rawKey);
      if (canon !== rawKey.trim().toLowerCase().replace(/[\s.-]+/g, "_")) columnsRenamed[rawKey] = canon;
      const num = typeof raw === "number" ? raw : Array.isArray(raw) ? Math.hypot(...(raw as number[])) : NaN;
      if (Number.isFinite(num)) (columnValues[canon] ??= []).push(num);
    }

    const r = validate(trial, simType);
    allChecks += r.checksRun;
    passed += r.passed;
    warnings += r.warnings;
    failed += r.failed;
    for (const c of r.checks) {
      uniqueCheckNames.add(c.name);
      const b = (byCat[c.category] ??= { passed: 0, warning: 0, failed: 0 });
      b[c.status] += 1;
      if (c.status !== "passed" && !issueMap.has(c.name)) {
        issueMap.set(c.name, {
          name: c.name,
          human_name: humanize(c),
          status: c.status as "warning" | "failed",
          description: c.detail,
          detail: c.detail,
          value: null,
          category: c.category,
        });
      }
    }
    if (r.failed > 0) {
      excluded++;
      exclusions.push({ trial_number: i + 1, trial_index: i, reason: r.violations[0]?.reason ?? "Failed physics checks", severity: "critical" });
    }
  });

  // ── Dataset-level detections (parity with the Python engine + benchmark):
  // monotonic drift, distribution shift, unit errors, near-duplicates. ──
  const excludedIdx = new Set<number>(exclusions.map((e) => e.trial_index));
  const exclude = (idx: number, reason: string, severity = "warning") => {
    if (!excludedIdx.has(idx)) { excludedIdx.add(idx); exclusions.push({ trial_number: idx + 1, trial_index: idx, reason, severity }); }
  };
  const addCheck = (name: string, human: string, detail: string, cat: string, sev: "warning" | "failed") => {
    uniqueCheckNames.add(name); allChecks += 1;
    (byCat[cat] ??= { passed: 0, warning: 0, failed: 0 })[sev] += 1;
    if (sev === "failed") failed += 1; else warnings += 1;
    if (!issueMap.has(name)) issueMap.set(name, { name, human_name: human, status: sev, description: detail, detail, value: null, category: cat });
  };

  const series: Record<string, { idx: number; v: number }[]> = {};
  const rowNum: Record<number, Record<string, number>> = {};
  rows.forEach((trial, i) => {
    for (const [rawKey, raw] of Object.entries(trial)) {
      const key = canonical(rawKey);
      const n = typeof raw === "number" ? raw : Array.isArray(raw) ? Math.hypot(...(raw as number[])) : NaN;
      if (Number.isFinite(n)) { (series[key] ??= []).push({ idx: i, v: n as number }); (rowNum[i] ??= {})[key] = n as number; }
    }
  });

  // 1. Monotonic drift (Pearson of value vs trial order — catches sub-R=0.7 creep).
  for (const [col, s] of Object.entries(series)) {
    if (s.length < 20) continue;
    const r = pearsonR(s.map((_, k) => k), s.map((p) => p.v));
    if (Number.isFinite(r) && Math.abs(r) > 0.35)
      addCheck(`temp_drift_${col}`, `Monotonic drift in ${col}`, `${col} trends monotonically over the run (r=${r.toFixed(2)}) — possible sensor drift`, "temporal_drift", "warning");
  }
  // 2. Distribution shift (10 windows; window mean >2.5σ from dataset mean → exclude).
  for (const [col, s] of Object.entries(series)) {
    if (s.length < 50) continue;
    const vals = s.map((p) => p.v), mu = mean(vals), sd = std(vals, mu);
    if (sd === 0) continue;
    const w = Math.floor(s.length / 10);
    for (let win = 0; win < 10; win++) {
      const chunk = s.slice(win * w, (win + 1) * w);
      if (!chunk.length) continue;
      const z = Math.abs(mean(chunk.map((p) => p.v)) - mu) / sd;
      if (z > 2.5) {
        addCheck(`temp_shift_${col}_w${win}`, `Distribution shift in ${col}`, `Window ${win + 1} mean deviates ${z.toFixed(1)}σ — condition change`, "distribution_shift", "warning");
        for (const p of chunk) exclude(p.idx, `Distribution shift in ${col} (${z.toFixed(1)}σ)`, "warning");
      }
    }
  }
  // 3. Gas-constant unit consistency: P/(ρT) must be ~287 J/kg·K.
  for (let i = 0; i < rows.length; i++) {
    const rn = rowNum[i];
    if (!rn) continue;
    const P = rn.pressure, rho = rn.density, T = rn.temperature;
    if (P && rho && T) {
      const R = P / (rho * T);
      if (R < 250 || R > 320) {
        addCheck("cx_gas_constant_check", "Gas-constant unit consistency", "P/(ρT) deviates from 287 J/kg·K — likely a Pa/kPa unit error", "cross_variable", "failed");
        exclude(i, `Gas constant P/(ρT)=${R.toFixed(1)} (expected 287) — unit error?`, "critical");
      }
    }
  }
  // 4. Near-duplicate blocks (standardized cosine similarity, sliding window).
  nearDuplicates(rowNum, rows.length, exclude, addCheck);

  // 5. Relationship drift: sensor drift buried in a wide marginal distribution but
  // breaking a near-constant physical ratio (Re/v, Ma/v, P/ρ, …). Excludes trials
  // whose ratio deviates from the clean baseline once a trend is confirmed.
  const RATIO_PAIRS: [string, string][] = [
    ["reynolds_number", "velocity"], ["mach_number", "velocity"], ["dynamic_pressure", "velocity"],
    ["pressure", "density"], ["stress", "strain"], ["heat_flux", "temperature"],
  ];
  for (const [a, b] of RATIO_PAIRS) {
    const ser: { idx: number; v: number }[] = [];
    for (let i = 0; i < rows.length; i++) {
      const rn = rowNum[i];
      if (rn && rn[a] !== undefined && rn[b] !== undefined && rn[b] !== 0) ser.push({ idx: i, v: rn[a] / rn[b] });
    }
    if (ser.length < 40) continue;
    const order = ser.map((_, k) => k), vals = ser.map((p) => p.v);
    if (Math.abs(pearsonR(order, vals)) < 0.2) continue; // require a real trend
    const k = Math.max(10, Math.floor(ser.length / 5));
    const baseArr = vals.slice(0, k).sort((x, y) => x - y);
    const base = baseArr[Math.floor(baseArr.length / 2)];
    const mad = median(baseArr.map((v) => Math.abs(v - base)));
    const scale = (mad > 0 ? mad * 1.4826 : std(vals.slice(0, k), mean(vals.slice(0, k)))) || 1e-9;
    let flagged = 0;
    for (const p of ser) if (Math.abs(p.v - base) / scale > 5) { exclude(p.idx, `Relationship drift: ${a}/${b} off clean baseline`, "warning"); flagged++; }
    if (flagged) addCheck(`reldrift_${a}:${b}`, `Sensor drift in ${a}/${b}`, `${flagged} trials where ${a}/${b} deviates >5σ from the clean baseline — progressive sensor drift`, "temporal_drift", "warning");
  }

  excluded = excludedIdx.size;
  const trialsValid = rows.length - excluded;
  const status = failed > 0 ? "failed" : warnings > 0 ? "warning" : "passed";
  const statistics: Record<string, RichStat> = {};
  for (const [col, vals] of Object.entries(columnValues)) if (vals.length >= 2) statistics[col] = stats(vals);

  return {
    job_id: jobId,
    status,
    confidence: status === "passed" ? "high" : status === "warning" ? "medium" : "low",
    trials_submitted: rows.length,
    trials_valid: trialsValid,
    trials_excluded: excluded,
    exclusion_rate: rows.length ? excluded / rows.length : 0,
    training_ready: status !== "failed" && trialsValid >= 1,
    processing_ms: Math.round((performance.now() - t0) * 100) / 100,
    all_checks: allChecks,
    unique_checks: uniqueCheckNames.size,
    passed,
    warnings,
    failed,
    issues: [...issueMap.values()],
    exclusions,
    statistics,
    checks_by_category: byCat,
    columns_renamed: columnsRenamed,
  };
}

// ── dataset-level helpers ──
function mean(a: number[]): number { return a.reduce((x, y) => x + y, 0) / a.length; }
function median(a: number[]): number { const s = [...a].sort((x, y) => x - y); return s.length ? s[Math.floor(s.length / 2)] : 0; }
function std(a: number[], mu: number): number { return Math.sqrt(a.reduce((x, y) => x + (y - mu) ** 2, 0) / a.length); }
function pearsonR(a: number[], b: number[]): number {
  const n = a.length, ma = mean(a), mb = mean(b);
  let num = 0, da = 0, db = 0;
  for (let i = 0; i < n; i++) { const x = a[i] - ma, y = b[i] - mb; num += x * y; da += x * x; db += y * y; }
  return da && db ? num / Math.sqrt(da * db) : NaN;
}
function nearDuplicates(
  rowNum: Record<number, Record<string, number>>, n: number,
  exclude: (idx: number, reason: string, sev?: string) => void,
  addCheck: (name: string, human: string, detail: string, cat: string, sev: "warning" | "failed") => void,
) {
  const counts: Record<string, number> = {};
  for (let i = 0; i < n; i++) { const rn = rowNum[i]; if (!rn) continue; for (const k of Object.keys(rn)) counts[k] = (counts[k] || 0) + 1; }
  const cols = Object.keys(counts).filter((k) => counts[k] === n);
  if (cols.length < 2 || n < 10) return;
  const X: number[][] = [];
  for (let i = 0; i < n; i++) X.push(cols.map((c) => rowNum[i][c]));
  const means = cols.map((_, j) => mean(X.map((r) => r[j])));
  const sds = cols.map((_, j) => std(X.map((r) => r[j]), means[j]) || 1);
  const Xn = X.map((r) => { const z = r.map((v, j) => (v - means[j]) / sds[j]); const nrm = Math.hypot(...z) || 1; return z.map((v) => v / nrm); });
  const window = 5;
  for (let i = 0; i < n - window; i++) {
    for (let j = i + 1; j <= i + window && j < n; j++) {
      const sim = Xn[i].reduce((s, v, k) => s + v * Xn[j][k], 0);
      if (sim > 0.999) {
        addCheck(`nd_block_${i}`, "Near-duplicate trial", `Trial ${i + 1} is nearly identical to trial ${j + 1} (cosine ${sim.toFixed(4)}) — likely copy-paste`, "near_duplicates", "warning");
        exclude(i, `Near-duplicate of trial ${j + 1} (sim ${sim.toFixed(4)})`, "warning");
        break;
      }
    }
  }
}

/** Deterministic demo dataset: 200 aerodynamics trials with several corruptions. */
export function demoDataset(): Record<string, unknown>[] {
  const rows: Record<string, unknown>[] = [];
  let seed = 12345;
  const rnd = () => ((seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);
  for (let i = 0; i < 200; i++) {
    const row: Record<string, number> = {
      cd: 0.31 + (rnd() - 0.5) * 0.02,
      cl: 0.84 + (rnd() - 0.5) * 0.03,
      re: 415000 + (rnd() - 0.5) * 20000,
      ma: 0.044 + (rnd() - 0.5) * 0.003,
      p: 101325 + (rnd() - 0.5) * 800,
      v: 15 + (rnd() - 0.5) * 0.6,
    };
    // Inject corruptions (~10%).
    if (i % 23 === 0) row.cd = 999.0;              // out of bounds
    else if (i % 31 === 0) row.cd = NaN;           // non-finite
    else if (i % 37 === 0) row.cl = -50.0;         // implausible lift
    else if (i % 41 === 0) row.ma = 1.42;          // supersonic in subsonic sweep
    rows.push(row);
  }
  return rows;
}
