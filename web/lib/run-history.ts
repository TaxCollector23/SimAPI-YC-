/**
 * Browser-local history of validation runs — the single source of truth for
 * the dashboard's Overview, Analytics, Logs, and Request Inspector pages.
 *
 * Every number shown in those pages is derived from runs the user actually
 * executed against the live API in this browser. There is no synthetic or
 * seeded data — a fresh account shows zeros and empty charts until the user
 * runs a validation.
 */
export interface RunRecord {
  id: string;
  ts: number;
  label: string;
  simulationType: string;
  status: string;
  engine: string; // "python-1300-checks" | "typescript-20-checks" | "unknown"
  executionMs: number;
  trials_submitted: number;
  trials_excluded: number;
  unique_checks: number;
  issues: { name: string; human_name: string; status: string }[];
  /** Full response payload, for the Request Inspector. Omitted from older records. */
  raw?: unknown;
}

const KEY = "simapi.runhistory";
const MAX = 40;

export function listRuns(): RunRecord[] {
  if (typeof localStorage === "undefined") return [];
  try {
    return (JSON.parse(localStorage.getItem(KEY) || "[]") as RunRecord[]).sort((a, b) => b.ts - a.ts);
  } catch {
    return [];
  }
}

export function getRun(id: string): RunRecord | undefined {
  return listRuns().find((r) => r.id === id);
}

export function recordRun(r: Omit<RunRecord, "id" | "ts" | "label">, label?: string): RunRecord {
  const rec: RunRecord = { ...r, id: crypto.randomUUID().slice(0, 8), ts: Date.now(), label: label || "" };
  const all = [rec, ...listRuns()].slice(0, MAX);
  try {
    localStorage.setItem(KEY, JSON.stringify(all));
  } catch {
    // Storage full or disabled — drop the raw payload and retry once, since
    // that's almost always what pushes a run over the quota.
    try {
      const trimmed = all.map((run) => (run.id === rec.id ? { ...run, raw: undefined } : run));
      localStorage.setItem(KEY, JSON.stringify(trimmed));
    } catch {
      /* non-fatal — history just won't persist this run */
    }
  }
  return rec;
}

export function clearRuns() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}

export interface RunDiff {
  resolved: { name: string; human_name: string }[];   // in older, gone in newer
  introduced: { name: string; human_name: string }[]; // new in newer
  persisting: { name: string; human_name: string }[]; // in both
  exclusionDelta: number;                              // newer − older excluded
}

/** Diff two runs (a = older baseline, b = newer). */
export function diffRuns(a: RunRecord, b: RunRecord): RunDiff {
  const setA = new Map(a.issues.map((i) => [i.name, i]));
  const setB = new Map(b.issues.map((i) => [i.name, i]));
  const resolved = a.issues.filter((i) => !setB.has(i.name)).map((i) => ({ name: i.name, human_name: i.human_name }));
  const introduced = b.issues.filter((i) => !setA.has(i.name)).map((i) => ({ name: i.name, human_name: i.human_name }));
  const persisting = b.issues.filter((i) => setA.has(i.name)).map((i) => ({ name: i.name, human_name: i.human_name }));
  return { resolved, introduced, persisting, exclusionDelta: b.trials_excluded - a.trials_excluded };
}

// ── Aggregate stats (Overview / Usage / Analytics) ──────────────────────────────
export interface UsageStats {
  requestsToday: number;
  totalValidations: number;
  successRate: number; // 0-100
  avgLatencyMs: number;
  avgExclusionRate: number; // 0-100, mean trials_excluded / trials_submitted
  recent: RunRecord[];
}

export function usageStats(): UsageStats {
  const runs = listRuns();
  const startOfDay = new Date();
  startOfDay.setHours(0, 0, 0, 0);
  const today = runs.filter((r) => r.ts >= startOfDay.getTime()).length;
  const succeeded = runs.filter((r) => r.status === "passed").length;
  const withLatency = runs.filter((r) => r.executionMs > 0);
  const exclusionRates = runs
    .filter((r) => r.trials_submitted > 0)
    .map((r) => r.trials_excluded / r.trials_submitted);
  return {
    requestsToday: today,
    totalValidations: runs.length,
    successRate: runs.length ? Math.round((succeeded / runs.length) * 100) : 0,
    avgLatencyMs: withLatency.length
      ? Math.round(withLatency.reduce((a, r) => a + r.executionMs, 0) / withLatency.length)
      : 0,
    avgExclusionRate: exclusionRates.length
      ? Math.round((exclusionRates.reduce((a, v) => a + v, 0) / exclusionRates.length) * 1000) / 10
      : 0,
    recent: runs.slice(0, 8),
  };
}
