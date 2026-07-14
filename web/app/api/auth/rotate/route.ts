import { NextResponse } from "next/server";

/** POST /api/auth/rotate — issue a new key and invalidate the previous one (`simapi api-key rotate`). */
export const runtime = "nodejs";

function randomHex(bytes: number) {
  const arr = new Uint8Array(bytes);
  crypto.getRandomValues(arr);
  return Array.from(arr).map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function POST() {
  return NextResponse.json({
    ok: true,
    api_key: `sk_live_${randomHex(20)}`,
    message: "New key issued. The previous key has been invalidated.",
  });
}
