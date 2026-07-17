import { NextResponse } from "next/server";
import type { SimulationType } from "@/lib/validation-engine";
import { richValidate } from "@/lib/rich-validate";
import { aiReview, type AiReview } from "@/lib/ai-review";

/**
 * POST /api/v1/validate
 *
 * Free public validation endpoint. Runs the deterministic engine on the server
 * (same code the browser uses) and returns the full report shape the dashboard
 * and SDKs consume, plus an optional AI second pass (OPENROUTER_API_KEY).
 */
export const runtime = "nodejs";
export const maxDuration = 30;

interface ValidateBody {
  data?: Record<string, unknown>[];
  simulation_type?: SimulationType;
  conditions?: Record<string, number>;
  run_ai?: boolean;
  job_id?: string;
}

function errorBody(code: string, message: string, requestId: string) {
  return { error: { code, message, request_id: requestId } };
}

/** Map the compact AI review into the dashboard's richer AIResult shape. */
function mapAi(review: AiReview): Record<string, unknown> | null {
  if (!review.enabled) return null;
  if (review.error) {
    return { status: "error", model: review.model ?? "", processing_ms: 0, anomaly_score: 0, dataset_summary: "", physics_agreement: "", physics_gaps: "", findings: [], recommendations: [], timed_out: false, error: review.error };
  }
  const anomaly = review.status === "agree" ? 0.12 : review.status === "concern" ? 0.42 : 0.78;
  const concerns = review.concerns ?? [];
  return {
    status: "completed",
    verdict: review.verdict ?? "",
    model: review.model ?? "",
    processing_ms: 0,
    anomaly_score: anomaly,
    dataset_summary: review.assessment ?? "",
    physics_agreement: review.status === "agree" ? "Confirms the deterministic findings — no additional physical inconsistencies detected." : "",
    physics_gaps: review.status !== "agree" ? concerns.join(" ") : "",
    findings: concerns.map((cc) => ({
      severity: review.status === "disagree" ? "critical" : "warning",
      category: "ai_review",
      title: "AI-identified concern",
      detail: cc,
      trials: [],
      confidence: 0.7,
      source: "physics_missed",
    })),
    recommendations: concerns,
    timed_out: false,
    error: null,
  };
}

/** Strongest pairwise Pearson correlations among numeric columns (for the AI profile). */
function topCorrelations(rows: Record<string, unknown>[]): { pair: string; r: number }[] {
  if (rows.length < 5) return [];
  const cols: Record<string, number[]> = {};
  for (const row of rows) for (const [k, v] of Object.entries(row)) {
    if (typeof v === "number" && Number.isFinite(v)) (cols[k] ??= []).push(v);
  }
  const names = Object.keys(cols).filter((k) => cols[k].length === rows.length);
  const out: { pair: string; r: number }[] = [];
  for (let i = 0; i < names.length; i++)
    for (let j = i + 1; j < names.length; j++) {
      const r = pearson(cols[names[i]], cols[names[j]]);
      if (Number.isFinite(r) && Math.abs(r) > 0.3) out.push({ pair: `${names[i]}~${names[j]}`, r: Math.round(r * 100) / 100 });
    }
  return out.sort((a, b) => Math.abs(b.r) - Math.abs(a.r)).slice(0, 6);
}
function pearson(a: number[], b: number[]): number {
  const n = a.length, ma = a.reduce((x, y) => x + y, 0) / n, mb = b.reduce((x, y) => x + y, 0) / n;
  let num = 0, da = 0, db = 0;
  for (let i = 0; i < n; i++) { const x = a[i] - ma, y = b[i] - mb; num += x * y; da += x * x; db += y * y; }
  return da && db ? num / Math.sqrt(da * db) : NaN;
}

export async function POST(req: Request) {
  const requestId = crypto.randomUUID().replace(/-/g, "").slice(0, 12);

  let body: ValidateBody;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json(errorBody("validation_failed", "Request body is not valid JSON.", requestId), { status: 422 });
  }

  const simType = (body.simulation_type ?? "aerodynamics") as SimulationType;
  const rows = Array.isArray(body.data) ? body.data : [];
  if (rows.length === 0) {
    return NextResponse.json(errorBody("bad_request", "`data` must be a non-empty array of trial records.", requestId), { status: 400 });
  }
  if (rows.length > 10000) {
    return NextResponse.json(errorBody("payload_too_large", "Maximum 10,000 trials per request.", requestId), { status: 413 });
  }

  const PYTHON_API = process.env.PYTHON_API_URL;
  let result;
  let engineSource: "python" | "typescript" = "typescript";

  if (PYTHON_API) {
    try {
      const upstream = await fetch(`${PYTHON_API}/v1/validate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ data: rows, simulation_type: simType, conditions: body.conditions ?? {}, run_ai: false }),
        signal: AbortSignal.timeout(25_000),
      });
      if (upstream.ok) {
        const pyResult = await upstream.json();
        engineSource = "python";
        result = {
          job_id: requestId.slice(0, 8),
          status: pyResult.overall_status ?? pyResult.status ?? "passed",
          confidence: pyResult.confidence ?? "high",
          trials_submitted: pyResult.trials_submitted ?? rows.length,
          trials_valid: pyResult.trials_valid ?? rows.length,
          trials_excluded: pyResult.trials_excluded ?? 0,
          exclusion_rate: pyResult.exclusion_rate ?? 0,
          training_ready: pyResult.training_ready ?? true,
          processing_ms: pyResult.processing_time_ms ?? 0,
          all_checks: pyResult.all_checks_count ?? 0,
          unique_checks: pyResult.all_checks_count ?? 0,
          passed: pyResult.passed_count ?? 0,
          warnings: pyResult.warning_count ?? 0,
          failed: pyResult.failed_count ?? 0,
          issues: (pyResult.issues ?? []).map((i: Record<string, unknown>) => ({
            name: i.name, human_name: i.description, status: i.status,
            description: i.detail ?? i.description, detail: i.detail ?? "",
            value: i.value, category: i.category,
          })),
          exclusions: (pyResult.exclusions ?? []).map((e: Record<string, unknown>) => ({
            trial_number: (e.trial_index as number) + 1, trial_index: e.trial_index,
            reason: e.reason, severity: e.severity,
          })),
          statistics: pyResult.statistics ?? {},
          checks_by_category: pyResult.checks_by_category ?? {},
          columns_renamed: {},
        };
      } else {
        result = richValidate(rows, simType, requestId.slice(0, 8));
      }
    } catch {
      result = richValidate(rows, simType, requestId.slice(0, 8));
    }
  } else {
    result = richValidate(rows, simType, requestId.slice(0, 8));
  }

  const excludedIdx = new Set(result.exclusions.map((e: { trial_index: number }) => e.trial_index));
  const profile = {
    trials_submitted: result.trials_submitted,
    trials_excluded: result.trials_excluded,
    statistics: result.statistics,
    correlations: topCorrelations(rows),
    sample_rows: rows.slice(0, 4),
    violating_rows: rows.filter((_, i) => excludedIdx.has(i)).slice(0, 4),
  };

  // AI logic-check pass is opt-in, not default -- physics validation is
  // deterministic and complete on its own. Explicitly pass run_ai: true to enable.
  const review =
    body.run_ai !== true
      ? ({ enabled: false } as AiReview)
      : await aiReview(
          {
            status: result.status,
            score: result.status === "passed" ? 100 : result.status === "warning" ? 70 : 35,
            violations: result.issues.filter((i: { status: string }) => i.status === "failed").map((i: { name: string; detail: string }) => ({ field: i.name, value: "", reason: i.detail, severity: "critical" as const })),
            recommendations: [],
            simulationType: simType,
            checks: [],
          },
          body.conditions ?? {},
          profile,
        );

  return NextResponse.json(
    {
      ...result,
      engine: engineSource === "python" ? "python-470-checks" : "typescript-20-checks",
      python_backend: engineSource === "python",
      ai: mapAi(review),
      ai_status: review.enabled ? (review.error ? "error" : "completed") : "disabled",
      ai_running: false,
      request_id: requestId,
    },
    { headers: { "X-Request-ID": requestId } },
  );
}
