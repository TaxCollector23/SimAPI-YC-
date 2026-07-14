import { NextResponse } from "next/server";

/**
 * POST /api/auth/verify — used by `simapi login`.
 *
 * Verifies the pasted API key and returns the account context the CLI stores.
 * Keys are issued client-side in this deployment, so verification checks the key
 * format; the CLI persists the returned plan/masked key.
 */
export const runtime = "nodejs";

function mask(key: string) {
  return key.length <= 12 ? key : `${key.slice(0, 10)}${"•".repeat(6)}${key.slice(-4)}`;
}

export async function POST(req: Request) {
  let apiKey = "";
  try {
    const body = await req.json();
    apiKey = String(body?.api_key ?? "").trim();
  } catch {
    return NextResponse.json({ ok: false, error: "Invalid request body" }, { status: 422 });
  }
  if (!/^sk_(live|test|demo)_[a-z0-9]{8,}$/i.test(apiKey)) {
    return NextResponse.json({ ok: false, error: "Invalid API key format" }, { status: 401 });
  }
  return NextResponse.json({
    ok: true,
    plan: apiKey.startsWith("sk_test") ? "sandbox" : "developer",
    key_masked: mask(apiKey),
    email: null,
  });
}
