/**
 * Web Crypto helpers for local-session auth and API-key hashing.
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

/** Derive a PBKDF2 hash for a password with a per-account random salt. */
export async function hashPassword(password: string, salt?: string): Promise<{ salt: string; hash: string }> {
  const useSalt = salt ?? randomHex(16);
  const keyMaterial = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(password),
    "PBKDF2",
    false,
    ["deriveBits"],
  );
  const bits = await crypto.subtle.deriveBits(
    { name: "PBKDF2", salt: new TextEncoder().encode(useSalt), iterations: 100_000, hash: "SHA-256" },
    keyMaterial,
    256,
  );
  return { salt: useSalt, hash: toHex(bits) };
}

/** Generate a display-friendly API key: `sk_live_<32 hex>`. */
export function generateApiKey(): string {
  return `sk_live_${randomHex(20)}`;
}

export { randomHex };
