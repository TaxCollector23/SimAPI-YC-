/**
 * Local dashboard state: API keys.
 *
 * No account system -- this is just a per-browser convenience store. API
 * keys are shown once at creation and stored only as a SHA-256 hash plus a
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

const KEYS_KEY = "simapi.keys.local";

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
export function listKeys(): ApiKeyRecord[] {
  return read<ApiKeyRecord>(KEYS_KEY).sort((a, b) => b.createdAt - a.createdAt);
}

/** Create a key. Returns the RAW key exactly once; only its hash is stored. */
export async function createKey(name: string): Promise<{ raw: string; record: ApiKeyRecord }> {
  const raw = generateApiKey();
  const record: ApiKeyRecord = {
    id: crypto.randomUUID().slice(0, 8),
    name: name.trim() || "Default",
    prefix: `${raw.slice(0, 14)}…`,
    hash: await sha256(raw),
    createdAt: Date.now(),
    lastUsed: null,
  };
  const keys = read<ApiKeyRecord>(KEYS_KEY);
  write(KEYS_KEY, [...keys, record]);
  return { raw, record };
}

export function revokeKey(id: string) {
  write(KEYS_KEY, read<ApiKeyRecord>(KEYS_KEY).filter((k) => k.id !== id));
}

/** Mark the most recently created key as used — called after a real API request. */
export function touchKey() {
  const keys = read<ApiKeyRecord>(KEYS_KEY).sort((a, b) => b.createdAt - a.createdAt);
  if (keys.length === 0) return;
  const all = read<ApiKeyRecord>(KEYS_KEY);
  const idx = all.findIndex((k) => k.id === keys[0].id);
  if (idx >= 0) {
    all[idx].lastUsed = Date.now();
    write(KEYS_KEY, all);
  }
}
