import { NextResponse } from "next/server";

/**
 * POST /api/v1/parse
 *
 * Convert a free-form simulation description (simulations.txt, a log dump, a CSV
 * paste, etc.) into the SimAPI validation JSON schema, using an LLM via OpenRouter.
 * Returns { ok:false, enabled:false } when OPENROUTER_API_KEY isn't set, so the CLI
 * can fall back gracefully until the key is added.
 */
export const runtime = "nodejs";
export const maxDuration = 30;

const OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions";

export async function POST(req: Request) {
  let body: { text?: string; simulation_type?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ ok: false, error: "Invalid JSON body" }, { status: 422 });
  }
  const text = (body.text ?? "").slice(0, 60_000);
  if (!text.trim()) return NextResponse.json({ ok: false, error: "Empty input" }, { status: 400 });

  const key = process.env.OPENROUTER_API_KEY;
  if (!key) {
    return NextResponse.json({ ok: false, enabled: false, error: "AI text parsing needs OPENROUTER_API_KEY on the server." }, { status: 503 });
  }

  const model = process.env.OPENROUTER_MODEL || "anthropic/claude-3.5-haiku";
  const prompt = `Convert this simulation data/description into SimAPI's validation JSON. Extract every trial/row of numeric results into the "data" array; pull boundary conditions into "conditions". Use canonical column names where obvious (velocity, drag_coefficient, lift_coefficient, reynolds_number, mach_number, pressure, density, temperature, stress, etc.). Infer simulation_type if not given (${body.simulation_type ?? "aerodynamics"} by default).

Respond ONLY with JSON of the exact shape:
{ "simulation_type": "...", "conditions": { ... }, "data": [ { ... }, ... ] }

Input:
${text}`;

  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 25_000);
    const res = await fetch(OPENROUTER_URL, {
      method: "POST",
      headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json", "HTTP-Referer": "https://sim-api.vercel.app", "X-Title": "SimAPI" },
      body: JSON.stringify({ model, max_tokens: 4000, temperature: 0, messages: [{ role: "user", content: prompt }] }),
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (!res.ok) return NextResponse.json({ ok: false, error: `OpenRouter ${res.status}` }, { status: 502 });
    const data = await res.json();
    let content: string = data?.choices?.[0]?.message?.content ?? "";
    content = content.trim().replace(/^```(?:json)?/i, "").replace(/```$/, "").trim();
    const parsed = JSON.parse(content);
    if (!Array.isArray(parsed.data)) return NextResponse.json({ ok: false, error: "AI did not return a data array" }, { status: 502 });
    return NextResponse.json({ ok: true, ...parsed });
  } catch (e) {
    return NextResponse.json({ ok: false, error: e instanceof Error ? e.message : "parse failed" }, { status: 502 });
  }
}
