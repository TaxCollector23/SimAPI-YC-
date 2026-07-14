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

  const result = richValidate(rows, simType, requestId.slice(0, 8));

  const review =
    body.run_ai === false
      ? ({ enabled: false } as AiReview)
      : await aiReview(
          {
            status: result.status,
            score: result.status === "passed" ? 100 : result.status === "warning" ? 70 : 35,
            violations: result.issues.filter((i) => i.status === "failed").map((i) => ({ field: i.name, value: "", reason: i.detail, severity: "critical" as const })),
            recommendations: [],
            simulationType: simType,
            checks: [],
          },
          body.conditions ?? {},
        );

  return NextResponse.json(
    {
      ...result,
      ai: mapAi(review),
      ai_status: review.enabled ? (review.error ? "error" : "completed") : "disabled",
      ai_running: false,
      request_id: requestId,
    },
    { headers: { "X-Request-ID": requestId } },
  );
}
