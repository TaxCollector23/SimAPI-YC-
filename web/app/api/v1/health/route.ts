import { NextResponse } from "next/server";

/** GET /api/v1/health — liveness for the public validation endpoint. */
export const runtime = "nodejs";

export async function GET() {
  return NextResponse.json({
    status: "ok",
    version: "3.1.0",
    engine: "deterministic",
    domains: 5,
    checks: "client-parity",
    ai_enabled: false,
  });
}
