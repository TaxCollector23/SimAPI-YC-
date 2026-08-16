import { NextResponse } from "next/server";

/**
 * POST /api/v1/validate/report?format=junit|sarif&strict=true|false
 *
 * Proxies to the Python backend's deterministic CI-gating export
 * (core/report_export.py → POST /v1/validate/report). Returns JUnit XML
 * (application/xml) or SARIF 2.1.0 (application/json) so a pipeline can gate a
 * build on physics violations. The AI layer is forced off upstream, so output
 * is byte-stable and diff-safe.
 *
 * There is no TypeScript fallback: report export is a Python-engine capability
 * and requires PYTHON_API_URL.
 */
export const runtime = "nodejs";
export const maxDuration = 60;

interface ReportBody {
  data?: Record<string, unknown>[];
  simulation_type?: string;
  conditions?: Record<string, number>;
  job_id?: string;
}

function errorBody(code: string, message: string, requestId: string) {
  return { error: { code, message, request_id: requestId } };
}

export async function POST(req: Request) {
  const requestId = crypto.randomUUID().replace(/-/g, "").slice(0, 12);
  const url = new URL(req.url);
  const format = (url.searchParams.get("format") || "junit").toLowerCase();
  const strict = url.searchParams.get("strict") ?? "";
  if (format !== "junit" && format !== "sarif") {
    return NextResponse.json(errorBody("bad_request", "`format` must be `junit` or `sarif`.", requestId), { status: 400 });
  }

  let body: ReportBody;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json(errorBody("validation_failed", "Request body is not valid JSON.", requestId), { status: 422 });
  }

  const rows = Array.isArray(body.data) ? body.data : [];
  if (rows.length === 0) {
    return NextResponse.json(errorBody("bad_request", "`data` must be a non-empty array of trial records.", requestId), { status: 400 });
  }
  if (rows.length > 10000) {
    return NextResponse.json(errorBody("payload_too_large", "Maximum 10,000 trials per request.", requestId), { status: 413 });
  }

  const PYTHON_API = process.env.PYTHON_API_URL;
  if (!PYTHON_API) {
    return NextResponse.json(
      errorBody("backend_unavailable", "Report export (JUnit/SARIF) requires the Python backend (PYTHON_API_URL not configured on this deployment).", requestId),
      { status: 503 },
    );
  }

  const qs = new URLSearchParams({ format });
  if (strict) qs.set("strict", strict);

  try {
    const upstream = await fetch(`${PYTHON_API}/v1/validate/report?${qs.toString()}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        data: rows,
        simulation_type: body.simulation_type,
        conditions: body.conditions ?? {},
        job_id: body.job_id ?? requestId.slice(0, 8),
      }),
      signal: AbortSignal.timeout(35_000),
    });

    const text = await upstream.text();
    if (!upstream.ok) {
      let detail = "Backend returned an error.";
      try {
        const j = JSON.parse(text);
        detail = j?.detail ?? j?.error?.message ?? j?.error ?? detail;
      } catch {
        /* upstream error body was not JSON */
      }
      return NextResponse.json(errorBody("backend_error", detail, requestId), { status: upstream.status });
    }

    const contentType = upstream.headers.get("content-type") ?? (format === "sarif" ? "application/json" : "application/xml");
    return new NextResponse(text, {
      status: 200,
      headers: { "Content-Type": contentType, "X-Request-ID": requestId },
    });
  } catch (e) {
    return NextResponse.json(
      errorBody("backend_unavailable", e instanceof Error ? e.message : "The Python backend is unreachable.", requestId),
      { status: 503 },
    );
  }
}
