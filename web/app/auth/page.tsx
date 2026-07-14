"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Copy, Check, Loader2, Terminal, ArrowRight } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { createKey, listKeys } from "@/lib/dashboard-store";
import { AuthScreen } from "@/components/auth-screen";
import { Logo } from "@/components/logo";

export default function AuthPage() {
  const { user, loading } = useAuth();
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  // Once signed in, issue a fresh key for the terminal to paste.
  useEffect(() => {
    if (!user || apiKey) return;
    setBusy(true);
    createKey(user.uid, "CLI").then(({ raw }) => {
      setApiKey(raw);
      setBusy(false);
    });
  }, [user, apiKey]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-white/40" />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="container-tight pb-24">
        <AuthScreen />
      </div>
    );
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-lg flex-col justify-center px-6 py-24">
      <div className="mb-8 flex flex-col items-center text-center">
        <Logo className="h-11" />
        <div className="mt-4 flex items-center gap-2 text-sm text-white/50">
          <Terminal className="h-4 w-4" /> Connect the CLI
        </div>
        <h1 className="mt-3 text-2xl font-semibold text-white">You&apos;re almost ready.</h1>
      </div>

      <div className="card p-6">
        <ol className="space-y-2.5 text-sm text-white/60">
          <li className="flex gap-3"><Step n={1} /> Copy your API key.</li>
          <li className="flex gap-3"><Step n={2} /> Return to your terminal.</li>
          <li className="flex gap-3"><Step n={3} /> Paste it when prompted.</li>
        </ol>

        <div className="mt-5 flex items-center gap-2">
          <code className="flex-1 overflow-x-auto rounded-lg border border-white/10 bg-black/40 px-3 py-3 font-mono text-sm text-white/80">
            {busy || !apiKey ? "generating…" : apiKey}
          </code>
          <button
            onClick={() => {
              if (!apiKey) return;
              navigator.clipboard.writeText(apiKey);
              setCopied(true);
              setTimeout(() => setCopied(false), 1800);
            }}
            disabled={!apiKey}
            className="btn-accent shrink-0"
          >
            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            {copied ? "Copied" : "Copy API Key"}
          </button>
        </div>
        <p className="mt-3 text-xs text-white/35">
          This key is shown once. We store only a hash. Signed in as {user.email || user.name}.
        </p>
      </div>

      <Link href="/dashboard" className="mt-6 flex items-center justify-center gap-1.5 text-sm text-white/45 hover:text-white">
        Go to your dashboard <ArrowRight className="h-3.5 w-3.5" />
      </Link>

      {listKeys(user.uid).length > 1 && (
        <p className="mt-3 text-center text-[11px] text-white/25">
          Manage or revoke keys from the dashboard.
        </p>
      )}
    </div>
  );
}

function Step({ n }: { n: number }) {
  return (
    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-white/15 text-[11px] text-white/60">
      {n}
    </span>
  );
}
