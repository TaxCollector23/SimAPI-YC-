import { NextResponse } from "next/server";

/** POST /api/v1/keys/generate — issue a fresh demo API key for the playground. */
export const runtime = "nodejs";

function randomHex(bytes: number) {
  const arr = new Uint8Array(bytes);
  crypto.getRandomValues(arr);
  return Array.from(arr).map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function POST(req: Request) {
  let label = "My Key";
  try {
    const body = await req.json();
    if (body?.label) label = String(body.label);
  } catch {
    /* label optional */
  }
  return NextResponse.json({
    api_key: `sk_live_${randomHex(20)}`,
    label,
    tier: "developer",
    created_at: Date.now(),
    message: "Store this key securely — it is shown only once.",
  });
}
