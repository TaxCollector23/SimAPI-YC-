import { NextResponse } from "next/server";
import { validate, type SimulationType, type CheckResult } from "@/lib/validation-engine";
import { aiReview } from "@/lib/ai-review";

/**
 * POST /api/v1/validate
 *
 * A free, public validation endpoint that runs the deterministic engine on the
 * server (same code the browser uses). Accepts the standard SimAPI request shape
 * so the Python/Node SDKs and CLI work against it directly — no separate backend
 * to host, no redirect.
 */
export const runtime = "nodejs";

interface ValidateBody {
  data?: Record<string, unknown>[];
  simulation_type?: SimulationType;
  conditions?: Record<string, number>;
  job_id?: string;
}

function errorBody(code: string, message: string, requestId: string) {
  return { error: { code, message, request_id: requestId } };
}

export async function POST(req: Request) {
  const requestId = crypto.randomUUID().replace(/-/g, "").slice(0, 12);
  const t0 = performance.now();

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

  // Validate each trial and aggregate.
  let allChecks = 0, passed = 0, warnings = 0, failed = 0, excluded = 0;
  const issueMap = new Map<string, CheckResult>();
  const exclusions: { trial_index: number; reason: string }[] = [];

  rows.forEach((trial, i) => {
    const r = validate(trial, simType);
    allChecks += r.checksRun;
    passed += r.passed;
    warnings += r.warnings;
    failed += r.failed;
    for (const c of r.checks) if (c.status !== "passed" && !issueMap.has(c.name)) issueMap.set(c.name, c);
    if (r.failed > 0) {
      excluded++;
      exclusions.push({ trial_index: i, reason: r.violations[0]?.reason ?? "Failed physics checks" });
    }
  });

  const trialsValid = rows.length - excluded;
  const status = failed > 0 ? "failed" : warnings > 0 ? "warning" : "passed";
  const issueChecks = [...issueMap.values()];
  const issues = issueChecks.map((c) => ({
    name: c.name, status: c.status, detail: c.detail, category: c.category,
  }));

  // Optional AI second-pass (runs only when OPENROUTER_API_KEY is configured).
  const ai = await aiReview(
    {
      status,
      score: status === "passed" ? 100 : status === "warning" ? 70 : 35,
      violations: issueChecks.filter((c) => c.status === "failed").map((c) => ({ field: c.name, value: "", reason: c.detail, severity: "critical" as const })),
      recommendations: [],
      simulationType: simType,
      checks: issueChecks,
    },
    body.conditions ?? {},
  );

  const response = {
    job_id: body.job_id ?? requestId.slice(0, 8),
    status,
    confidence: status === "passed" ? "high" : status === "warning" ? "medium" : "low",
    trials_submitted: rows.length,
    trials_valid: trialsValid,
    trials_excluded: excluded,
    exclusion_rate: rows.length ? excluded / rows.length : 0,
    training_ready: status !== "failed" && trialsValid >= 1,
    all_checks: allChecks,
    passed,
    warnings,
    failed,
    issues,
    exclusions,
    statistics: {},
    columns_renamed: {},
    processing_ms: Math.round((performance.now() - t0) * 100) / 100,
    ai_status: ai.enabled ? (ai.error ? "error" : "done") : "disabled",
    ai: ai.enabled ? ai : null,
    request_id: requestId,
  };

  return NextResponse.json(response, { headers: { "X-Request-ID": requestId } });
}
