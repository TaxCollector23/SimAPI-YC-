import { NextResponse } from "next/server";
import { richValidate, demoDataset } from "@/lib/rich-validate";

/** POST /api/v1/demo — validate a seeded 200-trial dataset with injected corruptions. */
export const runtime = "nodejs";

export async function POST() {
  const requestId = crypto.randomUUID().replace(/-/g, "").slice(0, 12);
  const result = richValidate(demoDataset(), "aerodynamics", requestId.slice(0, 8));
  return NextResponse.json({ ...result, ai: null, ai_status: "disabled", ai_running: false, request_id: requestId });
}
