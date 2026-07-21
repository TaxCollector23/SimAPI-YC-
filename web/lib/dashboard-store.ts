/**
 * Per-user dashboard state: API keys.
 *
 * API keys are shown once at creation and stored only as a SHA-256 hash plus a
 * short display prefix — the raw key is never persisted. Validation activity
 * lives in lib/run-history.ts (the source the actual /v1/validate calls write
 * to) — Overview/Analytics/Logs/Request Inspector all read from there.
 */
import { generateApiKey, sha256 } from "./crypto";

export interface ApiKeyRecord {
  id: string;
  name: string;
  prefix: string; // e.g. "sk_live_1a2b3c…"
  hash: string; // sha256 of the full key
  createdAt: number;
  lastUsed: number | null;
}

const keysKey = (uid: string) => `simapi.keys.${uid}`;

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

/** Mark the most recently created key as used — called after a real API request. */
export function touchKey(uid: string) {
  const keys = read<ApiKeyRecord>(keysKey(uid)).sort((a, b) => b.createdAt - a.createdAt);
  if (keys.length === 0) return;
  const all = read<ApiKeyRecord>(keysKey(uid));
  const idx = all.findIndex((k) => k.id === keys[0].id);
  if (idx >= 0) {
    all[idx].lastUsed = Date.now();
    write(keysKey(uid), all);
  }
}
