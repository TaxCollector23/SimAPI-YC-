/**
 * Per-user dashboard state: API keys and validation activity.
 *
 * API keys are shown once at creation and stored only as a SHA-256 hash plus a
 * short display prefix — the raw key is never persisted. Usage stats are derived
 * from validations the user actually runs in the browser (no synthetic numbers).
 */
import { generateApiKey, sha256 } from "./crypto";
import type { ValidationReport } from "./validation-engine";

export interface ApiKeyRecord {
  id: string;
  name: string;
  prefix: string; // e.g. "sk_live_1a2b3c…"
  hash: string; // sha256 of the full key
  createdAt: number;
  lastUsed: number | null;
}

export interface ValidationRecord {
  id: string;
  ts: number;
  simulationType: string;
  status: "passed" | "warning" | "failed";
  score: number;
  executionMs: number;
  checksRun: number;
}

const keysKey = (uid: string) => `simapi.keys.${uid}`;
const runsKey = (uid: string) => `simapi.runs.${uid}`;

function read<T>(key: string): T[] {
  try {
    return JSON.parse(localStorage.getItem(key) || "[]");
  } catch {
    return [];
  }
}
function write<T>(key: string, value: T[]) {
  localStorage.setItem(key, JSON.stringify(value));
}

// ── API keys ────────────────────────────────────────────────────────────────
export function listKeys(uid: string): ApiKeyRecord[] {
  return read<ApiKeyRecord>(keysKey(uid)).sort((a, b) => b.createdAt - a.createdAt);
}

/** Create a key. Returns the RAW key exactly once; only its hash is stored. */
export async function createKey(uid: string, name: string): Promise<{ raw: string; record: ApiKeyRecord }> {
  const raw = generateApiKey();
  const record: ApiKeyRecord = {
    id: crypto.randomUUID().slice(0, 8),
    name: name.trim() || "Default",
    prefix: `${raw.slice(0, 14)}…`,
    hash: await sha256(raw),
    createdAt: Date.now(),
    lastUsed: null,
  };
  const keys = read<ApiKeyRecord>(keysKey(uid));
  write(keysKey(uid), [...keys, record]);
  return { raw, record };
}

export function revokeKey(uid: string, id: string) {
  write(keysKey(uid), read<ApiKeyRecord>(keysKey(uid)).filter((k) => k.id !== id));
}

export function touchKey(uid: string) {
  const keys = read<ApiKeyRecord>(keysKey(uid));
  if (keys.length === 0) return;
  keys[keys.length - 1].lastUsed = Date.now();
  write(keysKey(uid), keys);
}

// ── Validation activity ───────────────────────────────────────────────────────
export function recordRun(uid: string, report: ValidationReport) {
  const runs = read<ValidationRecord>(runsKey(uid));
  runs.push({
    id: crypto.randomUUID().slice(0, 8),
    ts: Date.now(),
    simulationType: report.simulationType,
    status: report.status,
    score: report.score,
    executionMs: report.executionMs,
    checksRun: report.checksRun,
  });
  write(runsKey(uid), runs.slice(-200)); // keep last 200
  touchKey(uid);
}

export function listRuns(uid: string): ValidationRecord[] {
  return read<ValidationRecord>(runsKey(uid)).sort((a, b) => b.ts - a.ts);
}

export interface UsageStats {
  requestsToday: number;
  totalValidations: number;
  successRate: number; // 0-100
  recent: ValidationRecord[];
}

export function usageStats(uid: string): UsageStats {
  const runs = listRuns(uid);
  const startOfDay = new Date();
  startOfDay.setHours(0, 0, 0, 0);
  const today = runs.filter((r) => r.ts >= startOfDay.getTime()).length;
  const succeeded = runs.filter((r) => r.status === "passed").length;
  return {
    requestsToday: today,
    totalValidations: runs.length,
    successRate: runs.length ? Math.round((succeeded / runs.length) * 100) : 0,
    recent: runs.slice(0, 8),
  };
}
