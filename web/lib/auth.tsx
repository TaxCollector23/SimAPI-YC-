"use client";

/**
 * Authentication context.
 *
 * Uses Firebase Auth when configured (Google + email/password); otherwise falls
 * back to a real local session backed by PBKDF2-hashed accounts in localStorage,
 * so the dashboard is fully functional without external configuration.
 */
import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";
import { getFirebaseAuth, isFirebaseConfigured } from "./firebase";
import { hashPassword } from "./crypto";
import { upsertUserProfile, recordEvent } from "./telemetry";

export interface User {
  uid: string;
  email: string;
  name: string;
  provider: "google" | "password" | "local";
}

interface AuthState {
  user: User | null;
  loading: boolean;
  firebaseEnabled: boolean;
  signInGoogle: () => Promise<void>;
  signInEmail: (email: string, password: string) => Promise<void>;
  signUpEmail: (email: string, password: string, name: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

const USER_KEY = "simapi.user";
const ACCOUNTS_KEY = "simapi.accounts";

interface LocalAccount {
  uid: string;
  email: string;
  name: string;
  salt: string;
  hash: string;
}

function readAccounts(): LocalAccount[] {
  try {
    return JSON.parse(localStorage.getItem(ACCOUNTS_KEY) || "[]");
  } catch {
    return [];
  }
}
function writeAccounts(accts: LocalAccount[]) {
  localStorage.setItem(ACCOUNTS_KEY, JSON.stringify(accts));
}
function persistUser(user: User | null) {
  if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
  else localStorage.removeItem(USER_KEY);
}

/** Translate Firebase auth error codes into clear, actionable messages. */
function fbError(e: unknown): Error {
  const code = (e as { code?: string })?.code ?? "";
  const map: Record<string, string> = {
    "auth/unauthorized-domain": `This domain isn't authorized in Firebase yet. Add ${typeof location !== "undefined" ? location.hostname : "this domain"} under Firebase Console → Authentication → Settings → Authorized domains.`,
    "auth/popup-blocked": "Your browser blocked the sign-in popup — allow popups for this site and try again.",
    "auth/popup-closed-by-user": "Sign-in was cancelled.",
    "auth/operation-not-allowed": "This sign-in method isn't enabled in Firebase (Authentication → Sign-in method).",
    "auth/email-already-in-use": "An account with that email already exists. Sign in instead.",
    "auth/invalid-email": "That email address looks invalid.",
    "auth/weak-password": "Password is too weak — use at least 8 characters.",
    "auth/wrong-password": "Incorrect password.",
    "auth/invalid-credential": "Incorrect email or password.",
    "auth/user-not-found": "No account found for that email. Create one first.",
    "auth/too-many-requests": "Too many attempts — wait a moment and try again.",
    "auth/network-request-failed": "Network error reaching Firebase — check your connection.",
  };
  return new Error(map[code] || (e as Error)?.message || "Authentication failed.");
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isFirebaseConfigured) {
      // Local fallback: the browser-session copy in localStorage is the source of truth.
      try {
        const raw = localStorage.getItem(USER_KEY);
        if (raw) setUser(JSON.parse(raw));
      } catch {
        /* ignore */
      }
      setLoading(false);
      return;
    }

    // Firebase is configured: localStorage is only a paint-fast cache. The
    // Firebase SDK's own persisted session (IndexedDB) is the source of truth,
    // and onIdTokenChanged fires on sign-in/out, token refresh, and expiry —
    // without this listener the UI can drift out of sync with the real auth
    // state (e.g. showing "signed in" after Firebase invalidates the session).
    try {
      const raw = localStorage.getItem(USER_KEY);
      if (raw) setUser(JSON.parse(raw));
    } catch {
      /* ignore */
    }

    let unsubscribe = () => {};
    (async () => {
      const auth = await getFirebaseAuth();
      const { onIdTokenChanged } = await import("firebase/auth");
      unsubscribe = onIdTokenChanged(auth, (fbUser) => {
        if (fbUser) {
          const provider = fbUser.providerData[0]?.providerId === "google.com" ? "google" : "password";
          const u: User = {
            uid: fbUser.uid,
            email: fbUser.email ?? "",
            name: fbUser.displayName ?? fbUser.email ?? "User",
            provider,
          };
          persistUser(u);
          setUser(u);
          upsertUserProfile({ uid: u.uid, email: u.email, name: u.name, provider: u.provider });
          recordEvent(u.uid, "sign_in", { provider: u.provider });
        } else {
          persistUser(null);
          setUser(null);
        }
        setLoading(false);
      });
    })().catch(() => setLoading(false));

    return () => unsubscribe();
  }, []);

  const signInGoogle = useCallback(async () => {
    if (isFirebaseConfigured) {
      try {
        const auth = await getFirebaseAuth();
        const { GoogleAuthProvider, signInWithPopup } = await import("firebase/auth");
        const cred = await signInWithPopup(auth, new GoogleAuthProvider());
        const u: User = {
          uid: cred.user.uid,
          email: cred.user.email ?? "",
          name: cred.user.displayName ?? cred.user.email ?? "User",
          provider: "google",
        };
        persistUser(u);
        setUser(u);
      } catch (e) {
        throw fbError(e);
      }
      return;
    }
    // Local fallback: create a session tied to this browser.
    const u: User = {
      uid: `local_${crypto.randomUUID().slice(0, 8)}`,
      email: "you@local.session",
      name: "Local session",
      provider: "local",
    };
    persistUser(u);
    setUser(u);
  }, []);

  const signInEmail = useCallback(async (email: string, password: string) => {
    if (isFirebaseConfigured) {
      try {
        const auth = await getFirebaseAuth();
        const { signInWithEmailAndPassword } = await import("firebase/auth");
        const cred = await signInWithEmailAndPassword(auth, email, password);
        const u: User = { uid: cred.user.uid, email, name: cred.user.displayName ?? email, provider: "password" };
        persistUser(u);
        setUser(u);
      } catch (e) {
        throw fbError(e);
      }
      return;
    }
    const accts = readAccounts();
    const acct = accts.find((a) => a.email === email.toLowerCase());
    if (!acct) throw new Error("No account found for that email. Create one first.");
    const { hash } = await hashPassword(password, acct.salt);
    if (hash !== acct.hash) throw new Error("Incorrect password.");
    const u: User = { uid: acct.uid, email: acct.email, name: acct.name, provider: "password" };
    persistUser(u);
    setUser(u);
  }, []);

  const signUpEmail = useCallback(async (email: string, password: string, name: string) => {
    if (password.length < 8) throw new Error("Password must be at least 8 characters.");
    if (isFirebaseConfigured) {
      try {
        const auth = await getFirebaseAuth();
        const { createUserWithEmailAndPassword, updateProfile } = await import("firebase/auth");
        const cred = await createUserWithEmailAndPassword(auth, email, password);
        if (name) await updateProfile(cred.user, { displayName: name });
        const u: User = { uid: cred.user.uid, email, name: name || email, provider: "password" };
        persistUser(u);
        setUser(u);
      } catch (e) {
        throw fbError(e);
      }
      return;
    }
    const accts = readAccounts();
    if (accts.some((a) => a.email === email.toLowerCase())) {
      throw new Error("An account with that email already exists. Sign in instead.");
    }
    const { salt, hash } = await hashPassword(password);
    const acct: LocalAccount = { uid: `local_${crypto.randomUUID().slice(0, 8)}`, email: email.toLowerCase(), name: name || email, salt, hash };
    writeAccounts([...accts, acct]);
    const u: User = { uid: acct.uid, email: acct.email, name: acct.name, provider: "password" };
    persistUser(u);
    setUser(u);
  }, []);

  const signOut = useCallback(async () => {
    if (isFirebaseConfigured) {
      try {
        const auth = await getFirebaseAuth();
        const { signOut: fbSignOut } = await import("firebase/auth");
        await fbSignOut(auth);
      } catch {
        /* ignore */
      }
    }
    persistUser(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{ user, loading, firebaseEnabled: isFirebaseConfigured, signInGoogle, signInEmail, signUpEmail, signOut }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
