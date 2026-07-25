import { NextResponse } from "next/server";

/**
 * POST /api/v1/validate/dimensional
 *
 * Proxies to the Python backend's dimensional-analysis validation engine
 * (core/dimensional/) — units resolution, Pi-group discovery, anchored
 * physical constants, bimodal-split detection, and a Pi-space response
 * surface, in place of the older hand-written check list. There is no
 * TypeScript fallback for this engine (unlike /api/v1/validate): it only
 * runs where PYTHON_API_URL is configured.
 */
export const runtime = "nodejs";
export const maxDuration = 60;

interface DimensionalBody {
  data?: Record<string, unknown>[];
  conditions?: Record<string, number>;
  job_id?: string;
}

function errorBody(code: string, message: string, requestId: string) {
  return { error: { code, message, request_id: requestId } };
}

export async function POST(req: Request) {
  const requestId = crypto.randomUUID().replace(/-/g, "").slice(0, 12);

  let body: DimensionalBody;
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
      errorBody("backend_unavailable", "The dimensional-analysis engine requires the Python backend (PYTHON_API_URL not configured on this deployment).", requestId),
      { status: 503 },
    );
  }

  try {
    const upstream = await fetch(`${PYTHON_API}/v1/validate/dimensional`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data: rows, conditions: body.conditions ?? {}, job_id: body.job_id ?? requestId.slice(0, 8) }),
      signal: AbortSignal.timeout(35_000),
    });
    const json = await upstream.json();
    if (!upstream.ok) {
      return NextResponse.json(errorBody("backend_error", json?.detail ?? json?.error ?? "Backend returned an error.", requestId), { status: upstream.status });
    }
    return NextResponse.json({ ...json, request_id: requestId }, { headers: { "X-Request-ID": requestId } });
  } catch (e) {
    return NextResponse.json(
      errorBody("backend_unavailable", e instanceof Error ? e.message : "The Python backend is unreachable.", requestId),
      { status: 503 },
    );
  }
}
