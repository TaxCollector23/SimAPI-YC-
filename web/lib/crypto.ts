/**
 * Web Crypto helpers for API-key hashing.
 * All hashing uses the platform SubtleCrypto — no dependencies.
 */

function toHex(buf: ArrayBuffer): string {
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function randomHex(bytes: number): string {
  const arr = new Uint8Array(bytes);
  crypto.getRandomValues(arr);
  return Array.from(arr)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/** SHA-256 hex digest of a string (used to store API keys at rest). */
export async function sha256(text: string): Promise<string> {
  const data = new TextEncoder().encode(text);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return toHex(digest);
}

/** Generate a display-friendly API key: `sk_live_<32 hex>`. */
export function generateApiKey(): string {
  return `sk_live_${randomHex(20)}`;
}

export { randomHex };
