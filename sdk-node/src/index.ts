/**
 * SimAPI Node.js SDK.
 *
 * A thin, typed wrapper over the SimAPI REST API that mirrors the Python SDK.
 * Requires Node 18+ (uses the global `fetch`).
 *
 * @example
 * import { SimAPI } from "simapi";
 * const client = new SimAPI(process.env.SIMAPI_API_KEY);
 * const result = await client.validate(rows, { simulationType: "aerodynamics" });
 * console.log(result.status);
 */
import { readFile } from "node:fs/promises";

export type SimulationType =
  | "aerodynamics"
  | "fluid_dynamics"
  | "structural"
  | "thermodynamics"
  | "robotics"
  | string;

export interface ValidateOptions {
  simulationType?: SimulationType;
  conditions?: Record<string, number>;
  jobId?: string;
  runAi?: boolean;
}

export interface ValidationIssue {
  name: string;
  status: string;
  detail: string;
  category?: string;
}

export interface ValidationResult {
  job_id: string;
  status: "passed" | "warning" | "failed";
  confidence: "high" | "medium" | "low";
  trials_submitted: number;
  trials_valid: number;
  trials_excluded: number;
  training_ready: boolean;
  all_checks: number;
  passed: number;
  warnings: number;
  failed: number;
  issues: ValidationIssue[];
  processing_ms: number;
  ai_status: string;
  [key: string]: unknown;
}

export class SimAPIError extends Error {
  code: string;
  status: number;
  requestId?: string;
  constructor(message: string, code: string, status: number, requestId?: string) {
    super(message);
    this.name = "SimAPIError";
    this.code = code;
    this.status = status;
    this.requestId = requestId;
  }
}

export interface SimAPIConfig {
  apiKey?: string;
  baseUrl?: string;
  timeoutMs?: number;
}

export class SimAPI {
  private apiKey?: string;
  private baseUrl: string;
  private timeoutMs: number;

  constructor(apiKeyOrConfig?: string | SimAPIConfig) {
    const cfg: SimAPIConfig =
      typeof apiKeyOrConfig === "string" ? { apiKey: apiKeyOrConfig } : apiKeyOrConfig ?? {};
    this.apiKey = cfg.apiKey ?? process.env.SIMAPI_API_KEY;
    this.baseUrl = (cfg.baseUrl ?? process.env.SIMAPI_BASE_URL ?? "https://sim-api.vercel.app/api").replace(/\/$/, "");
    this.timeoutMs = cfg.timeoutMs ?? 60_000;
  }

  /** Validate an array of trial records. */
  async validate(
    data: Record<string, unknown>[],
    options: ValidateOptions = {},
  ): Promise<ValidationResult> {
    return this.request<ValidationResult>("/v1/validate", {
      data,
      simulation_type: options.simulationType ?? "aerodynamics",
      conditions: options.conditions ?? {},
      ...(options.jobId ? { job_id: options.jobId } : {}),
      run_ai: options.runAi ?? true,
    });
  }

  /** Validate a JSON file of trial records on disk. */
  async validateFile(path: string, options: ValidateOptions = {}): Promise<ValidationResult> {
    const raw = await readFile(path, "utf8");
    const parsed = JSON.parse(raw);
    const data: Record<string, unknown>[] = Array.isArray(parsed)
      ? parsed
      : (parsed.trials ?? parsed.data ?? parsed.results ?? [parsed]);
    return this.validate(data, options);
  }

  /** Fetch a previously computed job by id. */
  async getJob(jobId: string): Promise<ValidationResult> {
    return this.request<ValidationResult>(`/v1/job/${jobId}`, undefined, "GET");
  }

  /** Server health and facts. */
  async health(): Promise<Record<string, unknown>> {
    return this.request("/v1/health", undefined, "GET");
  }

  private async request<T>(path: string, body?: unknown, method: "GET" | "POST" = "POST"): Promise<T> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const res = await fetch(`${this.baseUrl}${path}`, {
        method,
        headers: {
          "Content-Type": "application/json",
          ...(this.apiKey ? { "X-API-Key": this.apiKey } : {}),
        },
        body: body !== undefined ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });
      const text = await res.text();
      const json = text ? JSON.parse(text) : {};
      if (!res.ok) {
        const err = json.error ?? {};
        throw new SimAPIError(
          err.message ?? `Request failed with ${res.status}`,
          err.code ?? "http_error",
          res.status,
          err.request_id,
        );
      }
      return json as T;
    } finally {
      clearTimeout(timer);
    }
  }
}

export default SimAPI;
