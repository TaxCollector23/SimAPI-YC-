"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

type Health = {
  status?: string;
  version?: string;
  engine?: string;
  domains?: number;
  python_backend?: boolean;
  ai_enabled?: boolean;
};

type Check = { name: string; state: "up" | "down" | "checking"; detail?: string };

export default function StatusPage() {
  const [checks, setChecks] = useState<Check[]>([
    { name: "Validation API", state: "checking" },
    { name: "Physics engine", state: "checking" },
    { name: "Website", state: "checking" },
    { name: "Documentation", state: "checking" },
  ]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const next: Check[] = [];

      // Validation API — a real same-origin JSON health check, not an opaque no-cors ping.
      let health: Health | null = null;
      try {
        const r = await fetch("/api/v1/health", { signal: AbortSignal.timeout(8000) });
        health = await r.json();
        next.push({ name: "Validation API", state: r.ok ? "up" : "down", detail: health?.version ? `v${health.version}` : undefined });
      } catch {
        next.push({ name: "Validation API", state: "down" });
      }

      next.push({
        name: "Physics engine",
        state: health?.python_backend ? "up" : health ? "up" : "down",
        detail: health?.engine === "python-dimensional" ? `${health.domains ?? 21} domains · dimensional` : health?.engine ? "TypeScript fallback" : undefined,
      });

      // Website + docs: reachability pings (opaque; a thrown fetch means unreachable).
      for (const [name, url] of [["Website", "/"], ["Documentation", "https://simapidocs.github.io"]] as const) {
        try {
          await fetch(url, { mode: url.startsWith("http") ? "no-cors" : "same-origin", signal: AbortSignal.timeout(8000) });
          next.push({ name, state: "up" });
        } catch {
          next.push({ name, state: "down" });
        }
      }

      if (!cancelled) setChecks(next);
    })();
    return () => { cancelled = true; };
  }, []);

  const settled = checks.every((c) => c.state !== "checking");
  const allUp = settled && checks.every((c) => c.state === "up");
  const heading = !settled ? "Checking systems…" : allUp ? "All systems operational" : "Some systems degraded";

  return (
    <div className="app-ui container-tight pt-32 pb-24">
      <div className="mx-auto max-w-2xl">
        <div className="flex items-center gap-3 border-l-2 border-pass/60 pl-4">
          {settled ? (
            <span className={`h-2.5 w-2.5 rounded-full ${allUp ? "bg-pass" : "bg-amber-400"}`} />
          ) : (
            <Loader2 className="h-4 w-4 animate-spin text-white/40" />
          )}
          <h1 className="text-xl font-semibold text-white">{heading}</h1>
        </div>
        <p className="mt-3 text-sm text-white/45">
          Checks run live from your browser against each public component every time this page loads.
        </p>

        <div className="mt-8 border border-white/10">
          {checks.map((c) => (
            <div key={c.name} className="flex items-center justify-between border-b border-white/[0.06] px-5 py-4 last:border-0">
              <div>
                <span className="text-sm text-white/80">{c.name}</span>
                {c.detail && <span className="ml-2 font-mono text-xs text-white/35">{c.detail}</span>}
              </div>
              {c.state === "up" ? (
                <span className="flex items-center gap-1.5 text-xs text-pass"><span className="h-2 w-2 rounded-full bg-pass" /> Operational</span>
              ) : c.state === "down" ? (
                <span className="flex items-center gap-1.5 text-xs text-amber-400"><span className="h-2 w-2 rounded-full bg-amber-400" /> Unreachable</span>
              ) : (
                <span className="flex items-center gap-1.5 text-xs text-white/35"><Loader2 className="h-3 w-3 animate-spin" /> Checking</span>
              )}
            </div>
          ))}
        </div>

        <div className="mt-6 grid grid-cols-3 border border-white/10 sm:divide-x sm:divide-white/10">
          {[["21", "simulation domains"], ["2", "deterministic engines"], ["MIT", "open source"]].map(([v, l]) => (
            <div key={l} className="border-b border-white/10 p-4 text-center last:border-b-0 sm:border-b-0">
              <p className="font-mono text-xl font-semibold text-white">{v}</p>
              <p className="mt-0.5 text-[11px] text-white/40">{l}</p>
            </div>
          ))}
        </div>

        <p className="mt-6 text-xs leading-relaxed text-white/35">
          SimAPI does not yet publish a formal uptime SLA — the hosted API is provided best-effort for
          evaluation, and production teams should run the self-hosted container. See the{" "}
          <a href="/roadmap" className="text-accent-blue underline underline-offset-2">roadmap</a> for what
          durable, production-grade operation still requires.
        </p>
      </div>
    </div>
  );
}
