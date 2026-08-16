"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { generateKey } from "@/lib/api";

/**
 * CLI + API setup landing. The CLI (`simapi login`) opens this at
 * /auth?cli=true; it also works as a plain "get an API key" page from the web.
 * The hosted API is open by default, so a key is optional — this page is
 * honest about that and never pretends a login is required.
 */
export default function AuthPage() {
  const [isCli, setIsCli] = useState(false);
  const [key, setKey] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    setIsCli(p.get("cli") === "true");
  }, []);

  async function generate() {
    setBusy(true);
    setErr(null);
    try {
      const res = await generateKey(isCli ? "CLI" : "Web");
      setKey(res.api_key);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not generate a key. Try again.");
    } finally {
      setBusy(false);
    }
  }

  function copy(text: string, id: string) {
    navigator.clipboard?.writeText(text).then(() => {
      setCopied(id);
      setTimeout(() => setCopied((c) => (c === id ? null : c)), 1500);
    });
  }

  const configCmd = key ? `simapi config set api_key ${key}` : "simapi config set api_key <key>";
  const envCmd = key ? `export SIMAPI_API_KEY=${key}` : "export SIMAPI_API_KEY=<key>";

  return (
    <section className="app-ui relative pt-40 pb-28">
      <div className="container-tight max-w-2xl">
        <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">
          {isCli ? "Connect the SimAPI CLI" : "Get an API key"}
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-white/55">
          The hosted API is <span className="text-white/80">open by default</span> — the{" "}
          <code className="bg-white/[0.06] px-1.5 py-0.5 font-mono text-[13px]">validate</code> engine
          works with no key at all. Generate a key only for higher rate limits, private/gated
          deployments, or the dimensional engine.
        </p>

        {/* Step 1 — install (CLI only) */}
        {isCli && (
          <div className="mt-10">
            <p className="text-xs font-medium uppercase tracking-wide text-white/40">Step 1 — install</p>
            <div className="mt-2 flex items-center justify-between border border-white/10 bg-black/30 px-4 py-3">
              <code className="font-mono text-sm text-white/85">npm install -g simapi-cli</code>
              <button
                onClick={() => copy("npm install -g simapi-cli", "install")}
                className="text-xs text-white/50 transition-colors hover:text-white"
              >
                {copied === "install" ? "Copied" : "Copy"}
              </button>
            </div>
          </div>
        )}

        {/* Step 2 — key */}
        <div className="mt-8">
          <p className="text-xs font-medium uppercase tracking-wide text-white/40">
            {isCli ? "Step 2 — generate a key" : "Generate a key"}
          </p>

          {!key ? (
            <button
              onClick={generate}
              disabled={busy}
              className="btn-accent mt-3 disabled:opacity-60"
            >
              {busy ? "Generating…" : "Generate API key"}
            </button>
          ) : (
            <div className="mt-3 flex items-center justify-between border border-accent-blue/30 bg-accent-blue/[0.05] px-4 py-3">
              <code className="truncate font-mono text-sm text-white">{key}</code>
              <button
                onClick={() => copy(key, "key")}
                className="ml-4 shrink-0 text-xs text-white/60 transition-colors hover:text-white"
              >
                {copied === "key" ? "Copied" : "Copy"}
              </button>
            </div>
          )}
          {err && <p className="mt-2 text-sm text-fail">{err}</p>}
          {key && (
            <p className="mt-2 text-xs text-white/40">
              Store it now — for security the full key isn&rsquo;t shown again. Manage keys from the{" "}
              <Link href="/dashboard" className="text-accent-blue hover:underline">dashboard</Link>.
            </p>
          )}
        </div>

        {/* Step 3 — use it */}
        <div className="mt-8">
          <p className="text-xs font-medium uppercase tracking-wide text-white/40">
            {isCli ? "Step 3 — connect" : "Use it"}
          </p>
          <p className="mt-2 text-sm text-white/55">
            {isCli ? "Save the key to the CLI config:" : "Send it as the X-API-Key header, or set it for the CLI:"}
          </p>
          <div className="mt-2 space-y-2">
            {[{ id: "cfg", cmd: configCmd }, { id: "env", cmd: envCmd }].map((row) => (
              <div key={row.id} className="flex items-center justify-between border border-white/10 bg-black/30 px-4 py-3">
                <code className="truncate font-mono text-sm text-white/85">{row.cmd}</code>
                <button
                  onClick={() => copy(row.cmd, row.id)}
                  className="ml-4 shrink-0 text-xs text-white/50 transition-colors hover:text-white"
                >
                  {copied === row.id ? "Copied" : "Copy"}
                </button>
              </div>
            ))}
          </div>
        </div>

        <p className="mt-10 border-t border-white/[0.06] pt-6 text-sm text-white/45">
          Prefer the browser?{" "}
          <Link href="/play" className="text-accent-blue hover:underline">Open the playground</Link>{" "}
          — no key required — or read the{" "}
          <Link href="/docs" className="text-accent-blue hover:underline">docs</Link>.
        </p>
      </div>
    </section>
  );
}
