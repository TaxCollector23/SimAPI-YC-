"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { Logo } from "./logo";

export function AuthScreen() {
  const { signInGoogle, signInEmail, signUpEmail, firebaseEnabled } = useAuth();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<null | "google" | "email">(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy("email");
    try {
      if (mode === "signup") await signUpEmail(email, password, name);
      else await signInEmail(email, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(null);
    }
  }

  async function google() {
    setError(null);
    setBusy("google");
    try {
      await signInGoogle();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Google sign-in failed.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-md flex-col justify-center pt-24">
      <div className="mb-8 flex flex-col items-center text-center">
        <Logo className="h-12 w-12" />
        <h1 className="mt-4 text-2xl font-semibold text-white">
          {mode === "signup" ? "Create your account" : "Sign in to SimAPI"}
        </h1>
        <p className="mt-2 text-sm text-white/50">
          {mode === "signup"
            ? "Get an API key and start validating in the browser."
            : "Access your dashboard, API keys, and validations."}
        </p>
      </div>

      <div className="card p-6">
        <button onClick={google} disabled={busy !== null} className="btn-ghost w-full">
          {busy === "google" ? <Loader2 className="h-4 w-4 animate-spin" /> : <GoogleGlyph />}
          Continue with Google
        </button>

        <div className="my-5 flex items-center gap-3 text-xs text-white/30">
          <span className="h-px flex-1 bg-white/10" /> or <span className="h-px flex-1 bg-white/10" />
        </div>

        <form onSubmit={submit} className="space-y-3">
          {mode === "signup" && (
            <Input label="Name" value={name} onChange={setName} placeholder="Ada Lovelace" />
          )}
          <Input label="Email" type="email" value={email} onChange={setEmail} placeholder="you@company.com" required />
          <Input label="Password" type="password" value={password} onChange={setPassword} placeholder="At least 8 characters" required />
          {error && <p className="text-xs text-fail">{error}</p>}
          <button type="submit" disabled={busy !== null} className="btn-accent w-full">
            {busy === "email" ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {mode === "signup" ? "Create account" : "Sign in"}
          </button>
        </form>

        <p className="mt-4 text-center text-xs text-white/45">
          {mode === "signup" ? "Already have an account?" : "New to SimAPI?"}{" "}
          <button
            onClick={() => {
              setMode(mode === "signup" ? "signin" : "signup");
              setError(null);
            }}
            className="text-accent-cyan hover:underline"
          >
            {mode === "signup" ? "Sign in" : "Create one"}
          </button>
        </p>
      </div>

      {!firebaseEnabled && (
        <p className="mt-4 text-center text-[11px] leading-relaxed text-white/30">
          Running with a local browser session. Set <code className="text-white/50">NEXT_PUBLIC_FIREBASE_*</code>{" "}
          to enable Firebase Google &amp; email auth.
        </p>
      )}
    </div>
  );
}

function Input({
  label,
  type = "text",
  value,
  onChange,
  placeholder,
  required,
}: {
  label: string;
  type?: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  required?: boolean;
}) {
  return (
    <div>
      <label className="mb-1.5 block text-xs font-medium text-white/55">{label}</label>
      <input
        type={type}
        value={value}
        required={required}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-sm text-white/80 outline-none placeholder:text-white/25 focus:border-accent-blue/50"
      />
    </div>
  );
}

function GoogleGlyph() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4">
      <path fill="#EA4335" d="M12 10.2v3.9h5.5c-.24 1.4-1.65 4.1-5.5 4.1-3.3 0-6-2.7-6-6.1s2.7-6.1 6-6.1c1.9 0 3.1.8 3.8 1.5l2.6-2.5C16.7 3.4 14.6 2.5 12 2.5 6.9 2.5 2.8 6.6 2.8 11.7S6.9 21 12 21c5.2 0 8.6-3.6 8.6-8.7 0-.6-.06-1-.15-1.5H12z" />
    </svg>
  );
}
