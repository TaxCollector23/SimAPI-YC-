/**
 * Optional Firebase initialization.
 *
 * Firebase Auth activates only when the public config env vars are present, so
 * the app runs with a local session fallback out of the box and upgrades to real
 * Google / email-password auth once a Firebase project is configured. The SDK is
 * imported dynamically to keep it out of the main bundle when unused.
 */
export const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

export const isFirebaseConfigured = Boolean(firebaseConfig.apiKey && firebaseConfig.authDomain);

// Cached Firebase Auth instance (lazily initialized).
let authPromise: Promise<import("firebase/auth").Auth> | null = null;

export async function getFirebaseAuth() {
  if (!isFirebaseConfigured) throw new Error("Firebase is not configured");
  if (!authPromise) {
    authPromise = (async () => {
      const { initializeApp, getApps } = await import("firebase/app");
      const { getAuth } = await import("firebase/auth");
      const app = getApps().length ? getApps()[0] : initializeApp(firebaseConfig);
      return getAuth(app);
    })();
  }
  return authPromise;
}
