import { NextResponse } from "next/server";
import { validateSetupConfig } from "@/lib/mesh-validate";

/**
 * POST /api/v1/validate/setup
 *
 * Pre-flight validation of a simulation setup (mesh + BCs + solver + physics).
 * Same issue-surfacing contract as /v1/validate — only warnings and failures.
 */
export const runtime = "nodejs";

interface Body {
  config?: Record<string, unknown>;
  mesh_stats?: Record<string, unknown>;
  solver?: string;
  physics?: string;
  simulation_type?: string;
}

export async function POST(req: Request) {
  const requestId = crypto.randomUUID().replace(/-/g, "").slice(0, 12);
  let body: Body;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: { code: "validation_failed", message: "Body is not valid JSON.", request_id: requestId } }, { status: 422 });
  }
  const config = (body.config ?? {}) as Record<string, unknown>;
  if (body.solver) (config as Record<string, unknown>).solver = body.solver;
  const report = validateSetupConfig(config, body.mesh_stats, body.simulation_type ?? "aerodynamics");
  return NextResponse.json({ ...report, request_id: requestId }, { headers: { "X-Request-ID": requestId } });
}
