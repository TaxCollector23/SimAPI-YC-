/**
 * API client for the in-browser validation dashboard (ported from the desktop
 * app). Points at the same-origin serverless routes under /api, so it works for
 * everyone with no separate backend.
 */
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api";
export const DEMO_KEY = "sk_demo_a1b2c3d4e5f6";

export interface ValidationRequest {
  data: Record<string, unknown>[];
  simulation_type: string;
  conditions: Record<string, number>;
  run_ai: boolean;
  job_id?: string;
}

export interface Issue {
  name: string;
  human_name: string;
  status: "warning" | "failed";
  description: string;
  detail: string;
  value: number | null;
  category: string;
}

export interface Exclusion {
  trial_number: number;
  trial_index: number;
  reason: string;
  severity: string;
}

export interface Stat {
  mean: number; std: number; median: number;
  p5: number; p95: number; min: number; max: number;
  n: number; skewness: number; cv: number;
}

export interface AIFinding {
  severity: "critical" | "warning" | "info";
  category: string;
  title: string;
  detail: string;
  trials: number[];
  confidence: number;
  source: "ai_only" | "confirms_physics" | "physics_missed";
}

export interface AIResult {
  status: string;
  verdict?: string; // terse headline: "Normal" / "Not Normal" (quick check) or a deep-orchestrator verdict
  model: string;
  processing_ms: number;
  anomaly_score: number;
  dataset_summary: string;
  physics_agreement: string;
  physics_gaps: string;
  findings: AIFinding[];
  recommendations: string[];
  timed_out: boolean;
  error: string | null;
  // Present only when the full Python orchestrator ran (not the lite TS review).
  corruption_probability?: Record<string, number>;
  root_causes?: { name: string; confidence: number; evidence: string; affected_columns?: string[]; severity?: string }[];
  what_only_ai_sees?: string;
  what_physics_caught?: string;
  what_physics_missed?: string;
  phase_timings?: Record<string, number>;
  recommended_action?: string;
}

export interface ValidationResult {
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
  unique_checks?: number;
  passed: number;
  warnings: number;
  failed: number;
  issues: Issue[];
  exclusions: Exclusion[];
  statistics: Record<string, Stat>;
  checks_by_category: Record<string, { passed: number; warning: number; failed: number }>;
  columns_renamed: Record<string, string>;
  ai: AIResult | null;
  ai_status: string;
  ai_running?: boolean;
  ai_exclusions?: number[];
}

export interface GeneratedKey {
  api_key: string; label: string; tier: string;
  created_at: number; message: string;
}

export async function generateKey(label: string): Promise<GeneratedKey> {
  const r = await fetch(`${API_BASE}/v1/keys/generate`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ label, tier: "developer" }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function validate(req: ValidationRequest, apiKey: string): Promise<ValidationResult> {
  const r = await fetch(`${API_BASE}/v1/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-API-Key": apiKey },
    body: JSON.stringify(req),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ error: r.statusText }));
    throw new Error(err?.error?.message ?? err?.detail?.error ?? err?.error ?? r.statusText);
  }
  return r.json();
}

export async function runDemo(): Promise<ValidationResult> {
  const r = await fetch(`${API_BASE}/v1/demo`, { method: "POST" });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function pollAI(jobId: string): Promise<{
  ai_running: boolean; ai_status: string; ai: AIResult | null;
  ai_exclusions?: number[]; exclusions?: Exclusion[];
  trials_excluded?: number; trials_valid?: number; exclusion_rate?: number;
  status?: "passed" | "warning" | "failed"; training_ready?: boolean;
}> {
  const r = await fetch(`${API_BASE}/v1/job/${jobId}/ai`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function healthCheck(): Promise<boolean> {
  try {
    const r = await fetch(`${API_BASE}/v1/health`, { signal: AbortSignal.timeout(3000) });
    return r.ok;
  } catch { return false; }
}

// ── Pre-flight (mesh + setup) validation ────────────────────────────────────────
export interface SetupIssue {
  name: string; human_name: string; status: "warning" | "failed";
  description: string; detail: string; value: number | null; category: string;
}
export interface PredictedFailure { check: string; label: string; why: string; fix: string }
export interface SetupResult {
  status: "ready" | "warning" | "not_ready";
  all_checks: number; passed: number; warnings: number; failed: number;
  issues: SetupIssue[];
  predicted_error_types: string[];
  predicted_failures?: PredictedFailure[];
  estimated_corruption_risk: number;
  recommendations: string[];
  processing_ms: number;
}

export async function validateSetup(config: Record<string, unknown>, meshStats?: Record<string, unknown>, simulationType = "aerodynamics"): Promise<SetupResult> {
  const r = await fetch(`${API_BASE}/v1/validate/setup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ config, mesh_stats: meshStats, simulation_type: simulationType }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ error: r.statusText }));
    throw new Error(err?.error?.message ?? r.statusText);
  }
  return r.json();
}

export interface RepairChange { row: number; column: string; before: unknown; after: unknown }
export interface RepairProposal {
  kind: string; description: string; affected_row_count: number;
  changes: RepairChange[]; rows_dropped: number[]; reorder_preview: number[] | null;
}
export interface RepairResult {
  proposals: RepairProposal[];
  unrepairable: { column: string; reason: string; rows: number[] }[];
  total_changes: number;
  repaired_data?: Record<string, unknown>[];
}

/** Preview (or apply) automatic structural repairs. Requires PYTHON_API_URL on this deployment. */
export async function repair(data: Record<string, unknown>[], apply = false): Promise<RepairResult> {
  const r = await fetch(`${API_BASE}/v1/repair`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ data, apply }),
  });
  const json = await r.json();
  if (!r.ok) throw new Error(json?.error?.message ?? r.statusText);
  return json;
}
