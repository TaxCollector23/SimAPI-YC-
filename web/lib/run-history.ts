/**
 * Browser-local history of validation runs, so engineers can compare two runs
 * of the same dataset and see which issues were resolved, introduced, or persist.
 */
export interface RunRecord {
  id: string;
  ts: number;
  label: string;
  simulationType: string;
  status: string;
  trials_submitted: number;
  trials_excluded: number;
  unique_checks: number;
  issues: { name: string; human_name: string; status: string }[];
}

const KEY = "simapi.runhistory";
const MAX = 25;

export function listRuns(): RunRecord[] {
  if (typeof localStorage === "undefined") return [];
  try {
    return (JSON.parse(localStorage.getItem(KEY) || "[]") as RunRecord[]).sort((a, b) => b.ts - a.ts);
  } catch {
    return [];
  }
}

export function recordRun(r: Omit<RunRecord, "id" | "ts" | "label">, label?: string): RunRecord {
  const rec: RunRecord = { ...r, id: crypto.randomUUID().slice(0, 8), ts: Date.now(), label: label || "" };
  const all = [rec, ...listRuns()].slice(0, MAX);
  try {
    localStorage.setItem(KEY, JSON.stringify(all));
  } catch {
    /* storage full / disabled — non-fatal */
  }
  return rec;
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
