import { NextResponse } from "next/server";

/**
 * GET /api/v1/job/{id}/ai — AI poll endpoint.
 *
 * The serverless validate endpoint returns the AI result inline, so there is no
 * async job to poll. This responds terminally (ai_running: false) so any poller
 * stops cleanly.
 */
export const runtime = "nodejs";

export async function GET() {
  return NextResponse.json({ ai_running: false, ai_status: "completed", ai: null });
}
