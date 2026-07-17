/**
 * Server-side (Firestore-backed) user telemetry — the real data source an
 * admin console needs. Everything before this file only lived in each
 * user's own browser localStorage, which no admin view can ever see across
 * users. This writes real, per-user records to Firestore so "how many API
 * keys does this user have," "what did they validate," and "when did they
 * last show up" have an actual answer.
 *
 * No-ops safely when Firebase isn't configured (isFirebaseConfigured is
 * false) or when Firestore writes fail (e.g. offline) — telemetry must
 * never block or break the feature it's instrumenting.
 */
import { isFirebaseConfigured, getFirestoreDb } from "./firebase";

export type EventType =
  | "sign_in"
  | "api_key_created"
  | "api_key_revoked"
  | "validation_run"
  | "settings_changed";

export interface UserProfile {
  uid: string;
  email: string;
  name: string;
  provider: string;
  createdAt: number;
  lastSeenAt: number;
  banned?: boolean;
}

export interface UserEvent {
  uid: string;
  type: EventType;
  detail: Record<string, unknown>;
  ts: number;
}

/** Create/update the user's profile document. Call on every sign-in. */
export async function upsertUserProfile(profile: Omit<UserProfile, "createdAt" | "lastSeenAt">): Promise<void> {
  if (!isFirebaseConfigured) return;
  try {
    const db = await getFirestoreDb();
    const { doc, getDoc, setDoc, serverTimestamp } = await import("firebase/firestore");
    const ref = doc(db, "users", profile.uid);
    const existing = await getDoc(ref);
    await setDoc(
      ref,
      {
        ...profile,
        lastSeenAt: serverTimestamp(),
        ...(existing.exists() ? {} : { createdAt: serverTimestamp() }),
      },
      { merge: true },
    );
  } catch {
    /* non-fatal — telemetry must never break the feature it's instrumenting */
  }
}

/** Record a discrete user action. Call on key creation/revocation, validation runs, etc. */
export async function recordEvent(uid: string, type: EventType, detail: Record<string, unknown> = {}): Promise<void> {
  if (!isFirebaseConfigured) return;
  try {
    const db = await getFirestoreDb();
    const { collection, addDoc, serverTimestamp } = await import("firebase/firestore");
    await addDoc(collection(db, "events"), { uid, type, detail, ts: serverTimestamp() });
  } catch {
    /* non-fatal */
  }
}
