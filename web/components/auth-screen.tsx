"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { Logo } from "./logo";

export function AuthScreen() {
  const { signInEmail, signUpEmail } = useAuth();
  const [mode, setMode] = useState<"signin" | "signup">("signup");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "signup") await signUpEmail(email, password, name);
      else await signInEmail(email, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-md flex-col justify-center pt-24">
      <div className="mb-8 flex flex-col items-center text-center">
        <Logo className="h-11" />
        <h1 className="mt-4 text-2xl font-semibold text-white">
          {mode === "signup" ? "Create your SimAPI account" : "Welcome back"}
        </h1>
        <p className="mt-2 text-sm text-white/50">
          {mode === "signup"
            ? "Enter your information below to get started."
            : "Sign in to access your dashboard and API keys."}
        </p>
      </div>

      <div className="card p-6">
        <form onSubmit={submit} className="space-y-3">
          {mode === "signup" && (
            <Input label="Name" value={name} onChange={setName} placeholder="Ada Lovelace" />
          )}
          <Input label="Email" type="email" value={email} onChange={setEmail} placeholder="you@company.com" required />
          <Input label="Password" type="password" value={password} onChange={setPassword} placeholder="At least 8 characters" required />
          {error && <p className="text-xs text-fail">{error}</p>}
          <button type="submit" disabled={busy} className="btn-accent w-full">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {mode === "signup" ? "Create account" : "Sign in"}
          </button>
        </form>

        <p className="mt-4 text-center text-xs text-white/45">
          {mode === "signup" ? "Already have an account?" : "Don't have an account yet?"}{" "}
          <button
            onClick={() => {
              setMode(mode === "signup" ? "signin" : "signup");
              setError(null);
            }}
            className="text-accent-cyan hover:underline"
          >
            {mode === "signup" ? "Or, sign in" : "Create one — it's free"}
          </button>
        </p>
      </div>

      <p className="mt-4 text-center text-[11px] leading-relaxed text-white/30">
        Your account lives in this browser — a real password-hashed local session, no third-party auth provider.
      </p>
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
