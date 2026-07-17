"use client";

/**
 * Status page — every number here is measured live from your browser, not a
 * static SLA claim. "Uptime" is a rolling sample of checks made from this
 * browser across visits (stored locally), not a substitute for a real
 * monitoring service with server-side history — labeled as such.
 */
import { useEffect, useState } from "react";
import { CheckCircle2, Loader2 } from "lucide-react";

interface CheckResult {
  name: string;
  status: "up" | "down" | "checking";
  latencyMs: number | null;
}

const UPTIME_KEY = "simapi.status.history";
const MAX_HISTORY = 200;

function recordCheck(name: string, up: boolean) {
  try {
    const raw = localStorage.getItem(UPTIME_KEY);
    const all: Record<string, boolean[]> = raw ? JSON.parse(raw) : {};
    all[name] = [...(all[name] ?? []), up].slice(-MAX_HISTORY);
    localStorage.setItem(UPTIME_KEY, JSON.stringify(all));
  } catch {
    /* storage disabled — non-fatal */
  }
}

function uptimePct(name: string): number | null {
  try {
    const raw = localStorage.getItem(UPTIME_KEY);
    const all: Record<string, boolean[]> = raw ? JSON.parse(raw) : {};
    const hist = all[name];
    if (!hist || hist.length === 0) return null;
    return Math.round((hist.filter(Boolean).length / hist.length) * 1000) / 10;
  } catch {
    return null;
  }
}

async function timedFetch(url: string, opts?: RequestInit): Promise<{ up: boolean; ms: number }> {
  const t0 = performance.now();
  try {
    await fetch(url, { signal: AbortSignal.timeout(8000), ...opts });
    return { up: true, ms: Math.round(performance.now() - t0) };
  } catch {
    return { up: false, ms: Math.round(performance.now() - t0) };
  }
}

export default function StatusPage() {
  const [checks, setChecks] = useState<CheckResult[]>([
    { name: "Validation API", status: "checking", latencyMs: null },
    { name: "Auth service (Firebase)", status: "checking", latencyMs: null },
    { name: "AI provider (OpenRouter)", status: "checking", latencyMs: null },
  ]);
  const [checkedAt, setCheckedAt] = useState<Date | null>(null);

  useEffect(() => {
    (async () => {
      const results = await Promise.all([
        timedFetch("https://sim-api.vercel.app/api/v1/health"),
        timedFetch("https://identitytoolkit.googleapis.com/v1/projects", { mode: "no-cors" }),
        timedFetch("https://openrouter.ai/api/v1/models", { mode: "no-cors" }),
      ]);
      const names = ["Validation API", "Auth service (Firebase)", "AI provider (OpenRouter)"];
      names.forEach((n, i) => recordCheck(n, results[i].up));
      setChecks(names.map((name, i) => ({ name, status: results[i].up ? "up" : "down", latencyMs: results[i].ms })));
      setCheckedAt(new Date());
    })();
  }, []);

  const allUp = checks.every((c) => c.status === "up");
  const avgLatency = checks.filter((c) => c.latencyMs !== null).length
    ? Math.round(checks.reduce((sum, c) => sum + (c.latencyMs ?? 0), 0) / checks.length)
    : null;

  return (
    <div className="container-tight pt-32 pb-24">
      <div className="mx-auto max-w-2xl">
        <div className={`rounded-2xl border p-6 ${allUp ? "border-pass/25 bg-pass/[0.05]" : "border-white/[0.08] bg-ink-900/50"}`}>
          <div className="flex items-center gap-3">
            <CheckCircle2 className={`h-6 w-6 ${allUp ? "text-pass" : "text-white/40"}`} />
            <h1 className="text-xl font-semibold text-white">{allUp ? "All systems operational" : "Checking systems…"}</h1>
          </div>
          <p className="mt-2 text-sm text-white/45">
            Live checks run from your browser against each component.
            {checkedAt && ` Last checked ${checkedAt.toLocaleTimeString()}.`}
          </p>
        </div>

        <div className="mt-6 overflow-hidden rounded-2xl border border-white/[0.08]">
          {checks.map((c) => {
            const uptime = uptimePct(c.name);
            return (
              <div key={c.name} className="flex items-center justify-between border-b border-white/[0.05] px-5 py-3.5 last:border-0">
                <div>
                  <span className="text-sm text-white/70">{c.name}</span>
                  {uptime !== null && <span className="ml-2 text-[11px] text-white/30">{uptime}% of checks up (this browser)</span>}
                </div>
                <div className="flex items-center gap-3">
                  {c.latencyMs !== null && <span className="font-mono text-xs text-white/35">{c.latencyMs}ms</span>}
                  {c.status === "up" ? <span className="flex items-center gap-1.5 text-xs text-pass"><span className="h-2 w-2 rounded-full bg-pass" /> Operational</span>
                    : c.status === "down" ? <span className="flex items-center gap-1.5 text-xs text-amber-400"><span className="h-2 w-2 rounded-full bg-amber-400" /> Unreachable</span>
                    : <span className="flex items-center gap-1.5 text-xs text-white/35"><Loader2 className="h-3 w-3 animate-spin" /> Checking</span>}
                </div>
              </div>
            );
          })}
        </div>

        <div className="mt-6 grid grid-cols-2 gap-4">
          <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4 text-center">
            <p className="font-mono text-xl font-semibold text-accent-cyan">{avgLatency !== null ? `${avgLatency}ms` : "—"}</p>
            <p className="mt-0.5 text-[11px] text-white/40">avg. round-trip latency (this check)</p>
          </div>
          <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4 text-center">
            <p className="font-mono text-xl font-semibold text-accent-cyan">
              {checks.some((c) => uptimePct(c.name) !== null)
                ? `${Math.round((checks.reduce((s, c) => s + (uptimePct(c.name) ?? 100), 0) / checks.length) * 10) / 10}%`
                : "—"}
            </p>
            <p className="mt-0.5 text-[11px] text-white/40">uptime — local sample only, not a monitoring SLA</p>
          </div>
        </div>
      </div>
    </div>
  );
}
