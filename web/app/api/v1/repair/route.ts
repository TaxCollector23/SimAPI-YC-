import { NextResponse } from "next/server";

/**
 * POST /api/v1/repair
 *
 * Automatic-repair preview/apply. This proxies straight to the Python backend
 * (core/repair.py) — repair logic is deterministic pandas work that has no
 * TypeScript port, unlike /v1/validate which has a lite TS fallback. Without
 * PYTHON_API_URL configured, this honestly reports that repair isn't
 * available rather than faking a result.
 */
export const runtime = "nodejs";
export const maxDuration = 30;

interface RepairBody {
  data?: Record<string, unknown>[];
  apply?: boolean;
}

export async function POST(req: Request) {
  const requestId = crypto.randomUUID().replace(/-/g, "").slice(0, 12);

  let body: RepairBody;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json(
      { error: { code: "validation_failed", message: "Request body is not valid JSON.", request_id: requestId } },
      { status: 422 },
    );
  }

  const rows = Array.isArray(body.data) ? body.data : [];
  if (rows.length === 0) {
    return NextResponse.json(
      { error: { code: "bad_request", message: "`data` must be a non-empty array of trial records.", request_id: requestId } },
      { status: 400 },
    );
  }

  const PYTHON_API = process.env.PYTHON_API_URL;
  if (!PYTHON_API) {
    return NextResponse.json(
      {
        error: {
          code: "not_available",
          message:
            "Automatic repair requires the Python backend (PYTHON_API_URL not configured on this deployment). " +
            "Run the API locally with `python launch.py`, or deploy it to Railway/Render — see /platform for the one-click configs.",
          request_id: requestId,
        },
      },
      { status: 501 },
    );
  }

  try {
    const upstream = await fetch(`${PYTHON_API}/v1/repair`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data: rows, apply: body.apply ?? false }),
      signal: AbortSignal.timeout(25_000),
    });
    const json = await upstream.json();
    return NextResponse.json(json, { status: upstream.status, headers: { "X-Request-ID": requestId } });
  } catch {
    return NextResponse.json(
      { error: { code: "upstream_unreachable", message: "Could not reach the Python backend.", request_id: requestId } },
      { status: 502 },
    );
  }
}
