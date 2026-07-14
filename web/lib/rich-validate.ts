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
