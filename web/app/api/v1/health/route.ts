import { NextResponse } from "next/server";

/** GET /api/v1/health — liveness for the public validation endpoint. */
export const runtime = "nodejs";

export async function GET() {
  const PYTHON_API = process.env.PYTHON_API_URL;
  let pythonBackend = false;

  if (PYTHON_API) {
    try {
      const res = await fetch(`${PYTHON_API}/v1/health`, { signal: AbortSignal.timeout(3000) });
      pythonBackend = res.ok;
    } catch {
      pythonBackend = false;
    }
  }

  return NextResponse.json({
    status: "ok",
    version: "3.1.0",
    engine: pythonBackend ? "python-1300-checks" : "typescript-20-checks",
    domains: pythonBackend ? 21 : 5,
    python_backend: pythonBackend,
    ai_enabled: !!process.env.OPENROUTER_API_KEY,
  });
}
