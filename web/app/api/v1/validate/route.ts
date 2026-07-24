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
export const maxDuration = 60;

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

  const concerns = review.concerns ?? [];
  const summary = review.assessment ?? "";
  const recs = review.recommendation ? [review.recommendation] : [];

  // Degraded path: the model failed, but we still surface the physics engine's
  // own finding (ai-review.ts populates `assessment` as a fallback) so the
  // panel is never empty and never blank-with-an-error.
  if (review.error) {
    return {
      status: summary ? "completed" : "error",
      verdict: review.verdict ?? "",
      model: review.model ?? "",
      processing_ms: 0,
      anomaly_score: summary ? 0.42 : 0,
      dataset_summary: summary,
      physics_agreement: "",
      physics_gaps: "",
      findings: summary
        ? [{
            severity: "warning",
            category: "physics_engine",
            title: "Physics engine finding",
            detail: summary,
            trials: [],
            confidence: 0.9,
            source: "physics_engine",
          }]
        : [],
      recommendations: recs,
      timed_out: false,
      error: review.error,
      review_version: review.reviewVersion ?? "",
    };
  }

  const anomaly = review.status === "agree" ? 0.12 : review.status === "concern" ? 0.42 : 0.78;

  return {
    status: "completed",
    verdict: review.verdict ?? "",
    model: review.model ?? "",
    processing_ms: 0,
    anomaly_score: anomaly,
    dataset_summary: summary,
    physics_agreement:
      review.status === "agree"
        ? "Confirms the deterministic findings — no additional physical inconsistencies detected."
        : "",
    // Intentionally NOT a copy of dataset_summary — leaving it empty prevents
    // the same sentence rendering four times in the panel.
    physics_gaps: "",
    findings:
      review.status === "agree"
        ? []
        : [{
            severity: "warning",
            category: "physics_engine",
            title: "Root-cause explanation",
            detail: summary,
            trials: [],
            confidence: 0.8,
            source: "physics_engine",
          }],
    recommendations: recs,
    timed_out: false,
    error: null,
    review_version: review.reviewVersion ?? "",
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
        body: JSON.stringify({ data: rows, simulation_type: simType, conditions: body.conditions ?? {}, run_ai: true }),
        signal: AbortSignal.timeout(35_000),
      });
      if (upstream.ok) {
        const pyResult = await upstream.json();
        engineSource = "python";
        result = {
          job_id: requestId.slice(0, 8),
          status: pyResult.status ?? "passed",
          confidence: pyResult.confidence ?? "high",
          trials_submitted: pyResult.trials_submitted ?? rows.length,
          trials_valid: pyResult.trials_valid ?? rows.length,
          trials_excluded: pyResult.trials_excluded ?? 0,
          exclusion_rate: pyResult.exclusion_rate ?? 0,
          training_ready: pyResult.training_ready ?? true,
          processing_ms: pyResult.processing_ms ?? 0,
          all_checks: pyResult.all_checks ?? 0,
          unique_checks: pyResult.all_checks ?? 0,
          passed: pyResult.passed ?? 0,
          warnings: pyResult.warnings ?? 0,
          failed: pyResult.failed ?? 0,
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

 const failedIssues = result.issues.filter((i: { status: string }) => i.status === "failed");

 const review =
    body.run_ai === false
      ? ({ enabled: false } as AiReview)
      : await aiReview(
          {
            status: result.status,
            score: result.status === "passed" ? 100 : result.status === "warning" ? 70 : 35,
            violations: failedIssues.map((i: { name: string; detail: string; value?: unknown }) => ({
              field: i.name,
              value: i.value != null ? String(i.value) : "",
              reason: i.detail || "",
              severity: "critical" as const,
            })),
            recommendations: result.exclusions
              .slice(0, 6)
              .map((e: { trial_number: number; reason: string }) => `Trial ${e.trial_number}: ${e.reason}`),
            simulationType: simType,
            checks: failedIssues.map((i: { name: string; detail: string; category?: string }) => ({
              name: i.name,
              category: i.category ?? "physics",
              status: "failed" as const,
              detail: i.detail || "",
            })),
          },
          body.conditions ?? {},
          profile,
        );

  return NextResponse.json(
    {
      ...result,
      engine: engineSource === "python" ? "python-1300-checks" : "typescript-20-checks",
      python_backend: engineSource === "python",
      ai: mapAi(review),
      ai_status: review.enabled ? (review.error ? "error" : "completed") : "disabled",
      ai_running: false,
      request_id: requestId,
    },
    { headers: { "X-Request-ID": requestId } },
  );
}
