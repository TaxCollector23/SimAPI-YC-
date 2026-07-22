import { NextResponse } from "next/server";
import { richValidate, demoDataset } from "@/lib/rich-validate";

/**
 * POST /api/v1/demo
 *
 * Runs the playground's one-click demo. When PYTHON_API_URL is configured,
 * proxies straight to the self-hosted backend's /v1/demo (the full 1300+
 * check engine, pristine 500-trial dataset designed to pass cleanly).
 * Falls back to the local TypeScript lite engine only if that backend is
 * unreachable, so the demo always returns something.
 */
export const runtime = "nodejs";
export const maxDuration = 60;

export async function POST() {
  const requestId = crypto.randomUUID().replace(/-/g, "").slice(0, 12);
  const PYTHON_API = process.env.PYTHON_API_URL;

  if (PYTHON_API) {
    try {
      const upstream = await fetch(`${PYTHON_API}/v1/demo`, {
        method: "POST",
        signal: AbortSignal.timeout(25_000),
      });
      if (upstream.ok) {
        const pyResult = await upstream.json();
        return NextResponse.json({
          job_id: requestId.slice(0, 8),
          status: pyResult.overall_status ?? pyResult.status ?? "passed",
          confidence: pyResult.confidence ?? "high",
          trials_submitted: pyResult.trials_submitted ?? 0,
          trials_valid: pyResult.trials_valid ?? 0,
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
          engine: "python-1300-checks",
          python_backend: true,
          ai: pyResult.ai ?? null,
          ai_status: pyResult.ai_status ?? "disabled",
          ai_running: false,
          request_id: requestId,
        });
      }
    } catch {
      // fall through to local engine below
    }
  }

  const result = richValidate(demoDataset(), "aerodynamics", requestId.slice(0, 8));
  return NextResponse.json({
    ...result,
    engine: "typescript-20-checks",
    python_backend: false,
    ai: null,
    ai_status: "disabled",
    ai_running: false,
    request_id: requestId,
  });
}
