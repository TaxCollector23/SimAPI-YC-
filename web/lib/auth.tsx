"use client";

/**
 * Authentication context.
 *
 * A real local session backed by PBKDF2-hashed accounts in localStorage.
 * (Previously had an optional Firebase Auth path for Google/email — removed
 * for reliability; this local session is fully functional on its own.)
 */
import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";
import { hashPassword } from "./crypto";

export interface User {
  uid: string;
  email: string;
  name: string;
  provider: "password" | "local";
}

interface AuthState {
  user: User | null;
  loading: boolean;
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

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(USER_KEY);
      if (raw) setUser(JSON.parse(raw));
    } catch {
      /* ignore */
    }
    setLoading(false);
  }, []);

  const signInEmail = useCallback(async (email: string, password: string) => {
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
    persistUser(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, signInEmail, signUpEmail, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
