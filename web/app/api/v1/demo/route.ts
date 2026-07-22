import { NextResponse } from "next/server";
import { richValidate, demoDataset } from "@/lib/rich-validate";
import { aiReview, type AiReview } from "@/lib/ai-review";

/**
 * POST /api/v1/demo
 *
 * Runs the playground's one-click demo. When PYTHON_API_URL is configured,
 * proxies straight to the self-hosted backend's /v1/demo (the full 1300+
 * check engine, pristine 500-trial dataset designed to pass cleanly), then
 * runs the AI review locally with Vercel's own OpenRouter keys — same as
 * /api/v1/validate — rather than relying on the Python backend's own AI
 * status, which depends on keys being configured separately on Render.
 * Falls back to the local TypeScript lite engine only if that backend is
 * unreachable, so the demo always returns something.
 */
export const runtime = "nodejs";
export const maxDuration = 60;

function mapAi(review: AiReview): Record<string, unknown> | null {
  if (!review.enabled) return null;
  const summary = review.assessment ?? "";
  return {
    status: "completed",
    verdict: review.verdict ?? "",
    model: review.model ?? "",
    processing_ms: 0,
    anomaly_score: review.status === "agree" ? 0.12 : review.status === "concern" ? 0.42 : 0.78,
    dataset_summary: summary,
    physics_agreement: review.status === "agree"
      ? "Confirms the deterministic findings — no additional physical inconsistencies detected."
      : "",
    physics_gaps: "",
    findings: review.status === "agree" ? [] : (summary ? [{
      severity: "warning", category: "physics_engine", title: "Root-cause explanation",
      detail: summary, trials: [], confidence: 0.8, source: "physics_engine",
    }] : []),
    recommendations: review.recommendation ? [review.recommendation] : [],
    timed_out: false,
    error: review.error ?? null,
    review_version: review.reviewVersion ?? "",
  };
}

export async function POST() {
  const requestId = crypto.randomUUID().replace(/-/g, "").slice(0, 12);
  const PYTHON_API = process.env.PYTHON_API_URL;
  let result;
  let engineSource: "python" | "typescript" = "typescript";

  if (PYTHON_API) {
    try {
      const upstream = await fetch(`${PYTHON_API}/v1/demo`, {
        method: "POST",
        signal: AbortSignal.timeout(35_000),
      });
      if (upstream.ok) {
        const pyResult = await upstream.json();
        engineSource = "python";
        result = {
          job_id: requestId.slice(0, 8),
          status: pyResult.status ?? "passed",
          confidence: pyResult.confidence ?? "high",
          trials_submitted: pyResult.trials_submitted ?? 0,
          trials_valid: pyResult.trials_valid ?? 0,
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
      }
    } catch {
      // fall through to local engine below
    }
  }

  if (!result) {
    result = richValidate(demoDataset(), "aerodynamics", requestId.slice(0, 8));
  }

  const failedIssues = result.issues.filter((i: { status: string }) => i.status === "failed");
  const review = await aiReview(
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
      simulationType: "aerodynamics",
      checks: failedIssues.map((i: { name: string; detail: string; category?: string }) => ({
        name: i.name,
        category: i.category ?? "physics",
        status: "failed" as const,
        detail: i.detail || "",
      })),
    },
    { velocity: 15.0, altitude: 120.0 },
    {
      trials_submitted: result.trials_submitted,
      trials_excluded: result.trials_excluded,
      statistics: result.statistics,
    },
  );

  return NextResponse.json({
    ...result,
    engine: engineSource === "python" ? "python-1300-checks" : "typescript-20-checks",
    python_backend: engineSource === "python",
    ai: mapAi(review),
    ai_status: review.enabled ? (review.error ? "error" : "completed") : "disabled",
    ai_running: false,
    request_id: requestId,
  });
}
