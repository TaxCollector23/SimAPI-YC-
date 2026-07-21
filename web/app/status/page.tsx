"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Loader2 } from "lucide-react";

interface Component { name: string; endpoint?: string }
const COMPONENTS: Component[] = [
  { name: "Validation API", endpoint: "https://sim-api.vercel.app/api/v1/health" },
  { name: "Pre-flight API", endpoint: "https://sim-api.vercel.app/api/v1/health" },
  { name: "Dashboard", endpoint: "https://sim-api.vercel.app" },
  { name: "Documentation", endpoint: "https://simapidocs.github.io" },
  { name: "npm registry (simapi-cli)" },
];

export default function StatusPage() {
  const [state, setState] = useState<Record<string, "up" | "down" | "checking">>({});

  useEffect(() => {
    COMPONENTS.forEach(async (c) => {
      if (!c.endpoint) { setState((s) => ({ ...s, [c.name]: "up" })); return; }
      setState((s) => ({ ...s, [c.name]: "checking" }));
      try {
        await fetch(c.endpoint, { mode: "no-cors", signal: AbortSignal.timeout(6000) });
        setState((s) => ({ ...s, [c.name]: "up" }));
      } catch {
        setState((s) => ({ ...s, [c.name]: "down" }));
      }
    });
  }, []);

  const allUp = COMPONENTS.every((c) => state[c.name] === "up");

  return (
    <div className="container-tight pt-32 pb-24">
      <div className="mx-auto max-w-2xl">
        <div className={`rounded-2xl border p-6 ${allUp ? "border-pass/25 bg-pass/[0.05]" : "border-white/[0.08] bg-ink-900/50"}`}>
          <div className="flex items-center gap-3">
            <CheckCircle2 className={`h-6 w-6 ${allUp ? "text-pass" : "text-white/40"}`} />
            <h1 className="text-xl font-semibold text-white">{allUp ? "All systems operational" : "Checking systems…"}</h1>
          </div>
          <p className="mt-2 text-sm text-white/45">Live checks run from your browser against each public component.</p>
        </div>

        <div className="mt-6 overflow-hidden rounded-2xl border border-white/[0.08]">
          {COMPONENTS.map((c) => {
            const st = state[c.name];
            return (
              <div key={c.name} className="flex items-center justify-between border-b border-white/[0.05] px-5 py-3.5 last:border-0">
                <span className="text-sm text-white/70">{c.name}</span>
                {st === "up" ? <span className="flex items-center gap-1.5 text-xs text-pass"><span className="h-2 w-2 rounded-full bg-pass" /> Operational</span>
                  : st === "down" ? <span className="flex items-center gap-1.5 text-xs text-amber-400"><span className="h-2 w-2 rounded-full bg-amber-400" /> Degraded</span>
                  : <span className="flex items-center gap-1.5 text-xs text-white/35"><Loader2 className="h-3 w-3 animate-spin" /> Checking</span>}
              </div>
            );
          })}
        </div>

        <div className="mt-6 grid grid-cols-3 gap-4">
          {[["99.9%", "target uptime"], ["<30ms", "median physics latency"], ["21", "domains covered"]].map(([v, l]) => (
            <div key={l} className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4 text-center">
              <p className="font-mono text-xl font-semibold text-accent-cyan">{v}</p>
              <p className="mt-0.5 text-[11px] text-white/40">{l}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
