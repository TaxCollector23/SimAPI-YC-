import { NextResponse } from "next/server";
import { aiReview } from "@/lib/ai-review";
import type { ValidationReport } from "@/lib/validation-engine";

/**
 * POST /api/v1/ai-review
 *
 * Second-pass AI check. The browser sends a deterministic validation report plus
 * the conditions; the server (which holds OPENROUTER_API_KEY) asks an LLM whether
 * the verdict is physically and logically correct. Returns `{ enabled: false }`
 * when no key is configured.
 */
export const runtime = "nodejs";
export const maxDuration = 60;

interface Body {
  report?: Pick<ValidationReport, "status" | "score" | "violations" | "recommendations" | "simulationType" | "checks">;
  conditions?: Record<string, unknown>;
}

export async function POST(req: Request) {
  let body: Body;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ enabled: false, error: "Invalid JSON" }, { status: 422 });
  }
  if (!body.report) {
    return NextResponse.json({ enabled: false, error: "Missing report" }, { status: 400 });
  }
  const review = await aiReview(body.report, body.conditions ?? {});
  return NextResponse.json(review);
}
