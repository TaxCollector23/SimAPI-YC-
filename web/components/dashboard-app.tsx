"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  LayoutDashboard, KeyRound, Activity, FlaskConical, BookOpen, Settings as SettingsIcon,
  Copy, Check, Trash2, Plus, LogOut, ExternalLink, Loader2, BarChart3, ScrollText, Radar,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import {
  listKeys, createKey, revokeKey,
  type ApiKeyRecord,
} from "@/lib/dashboard-store";
import {
  usageStats, listRuns as listRunHistory,
  type UsageStats, type RunRecord,
} from "@/lib/run-history";
import { AuthScreen } from "./auth-screen";
import { ValidationDashboard } from "./validation-dashboard";
import { AnalyticsPanel } from "./analytics-panel";
import { LogsPanel } from "./logs-panel";
import { RequestInspectorPanel } from "./request-inspector-panel";
import { cn } from "@/lib/utils";
import { site } from "@/lib/site";

type Section = "overview" | "keys" | "usage" | "analytics" | "logs" | "inspector" | "run" | "settings";

const NAV: { id: Section; label: string; icon: typeof LayoutDashboard }[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "analytics", label: "Analytics", icon: BarChart3 },
  { id: "logs", label: "Logs", icon: ScrollText },
  { id: "inspector", label: "Request Inspector", icon: Radar },
  { id: "usage", label: "Usage", icon: Activity },
  { id: "keys", label: "API Keys", icon: KeyRound },
  { id: "run", label: "Playground", icon: FlaskConical },
  { id: "settings", label: "Settings", icon: SettingsIcon },
];

export function DashboardApp() {
  const { user, loading } = useAuth();
  const [section, setSection] = useState<Section>("overview");
  const [inspectRunId, setInspectRunId] = useState<string | null>(null);

  function goInspect(id: string) {
    setInspectRunId(id);
    setSection("inspector");
  }

  if (loading) {
    return (
      <div className="flex min-h-[70vh] items-center justify-center pt-24">
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
    <div className="container-tight pt-28 pb-24">
      <div className="grid gap-8 lg:grid-cols-[220px_1fr]">
        {/* Sidebar */}
        <aside className="lg:sticky lg:top-24 lg:self-start">
          <p className="px-3 text-xs font-semibold uppercase tracking-wider text-white/35">Dashboard</p>
          <nav className="mt-3 space-y-0.5">
            {NAV.map((item) => (
              <button
                key={item.id}
                onClick={() => setSection(item.id)}
                className={cn(
                  "flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors",
                  section === item.id ? "bg-white/[0.06] text-white" : "text-white/55 hover:bg-white/[0.03] hover:text-white",
                )}
              >
                <item.icon className="h-4 w-4" /> {item.label}
              </button>
            ))}
            <a
              href="/docs"
              className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-white/55 transition-colors hover:bg-white/[0.03] hover:text-white"
            >
              <BookOpen className="h-4 w-4" /> Documentation
            </a>
          </nav>
        </aside>

        {/* Content */}
        <div>
          {section === "overview" && <Overview onNavigate={setSection} />}
          {section === "analytics" && <AnalyticsPanel />}
          {section === "logs" && <LogsPanel onInspect={goInspect} />}
          {section === "inspector" && (
            <RequestInspectorPanel runId={inspectRunId} onBack={() => setInspectRunId(null)} />
          )}
          {section === "keys" && <ApiKeys />}
          {section === "usage" && <Usage />}
          {section === "run" && <RunSimulation />}
          {section === "settings" && <SettingsPanel />}
        </div>
      </div>
    </div>
  );
}

// ── Overview ──────────────────────────────────────────────────────────────────
function Overview({ onNavigate }: { onNavigate: (s: Section) => void }) {
  const { user } = useAuth();
  const [stats, setStats] = useState<UsageStats | null>(null);
  const [hasKey, setHasKey] = useState(false);

  useEffect(() => {
    if (!user) return;
    setStats(usageStats());
    setHasKey(listKeys(user.uid).length > 0);
  }, [user]);

  if (!stats || !user) return null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white">Welcome back, {user.name.split(" ")[0]}</h1>
        <p className="mt-1 text-sm text-white/50">Here&apos;s your validation activity.</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Requests today" value={String(stats.requestsToday)} />
        <Stat label="Total validations" value={String(stats.totalValidations)} />
        <Stat label="Pass rate" value={stats.totalValidations ? `${stats.successRate}%` : "—"} />
      </div>

      {!hasKey && (
        <div className="flex flex-col items-start gap-3 rounded-2xl border border-accent-blue/30 bg-accent-blue/[0.05] p-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-medium text-white">Generate your first API key</p>
            <p className="text-xs text-white/50">You&apos;ll need a key to call the API from the SDK or CLI.</p>
          </div>
          <button onClick={() => onNavigate("keys")} className="btn-accent shrink-0">
            <Plus className="h-4 w-4" /> Create API key
          </button>
        </div>
      )}

      <div>
        <h2 className="text-base font-semibold text-white">Quickstart — Run the simulations in your browser</h2>
        <p className="mt-1 text-sm text-white/50">
          No install needed. Configure conditions and validate right here.
        </p>
        <button onClick={() => onNavigate("run")} className="btn-accent mt-4">
          <FlaskConical className="h-4 w-4" /> Run simulation in browser
        </button>

        <p className="mb-3 mt-8 text-sm text-white/50">or, use the CLI</p>
        <div className="card overflow-hidden">
          <div className="border-b border-white/[0.06] px-4 py-2 font-mono text-xs text-white/40">python</div>
          <pre className="overflow-x-auto p-4 font-mono text-[13px] leading-relaxed text-white/70">
{`from simapi import SimAPI

client = SimAPI(api_key="sk_live_...")
result = client.validate("simulation.json", simulation_type="aerodynamics")

print(result.status)          # "passed" | "warning" | "failed"
print(result.violations)`}
          </pre>
        </div>
      </div>

      <RecentRuns runs={stats.recent} onRun={() => onNavigate("run")} />
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/[0.07] bg-ink-900/50 p-5">
      <p className="text-xs text-white/45">{label}</p>
      <p className="mt-2 text-3xl font-semibold text-white">{value}</p>
    </div>
  );
}

function RecentRuns({ runs, onRun }: { runs: RunRecord[]; onRun: () => void }) {
  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-white">Recent validations</h2>
        <button onClick={onRun} className="text-xs text-accent-cyan hover:text-white">Run a validation →</button>
      </div>
      {runs.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-white/10 py-10 text-center text-sm text-white/35">
          No validations yet. Run one from the Playground tab.
        </div>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-white/[0.07]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/[0.07] bg-white/[0.02] text-left text-xs text-white/45">
                <th className="p-3 font-medium">Type</th>
                <th className="p-3 font-medium">Status</th>
                <th className="p-3 font-medium">Trials</th>
                <th className="p-3 font-medium">Time</th>
                <th className="p-3 font-medium">When</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id} className="border-b border-white/[0.05] last:border-0">
                  <td className="p-3 text-white/70">{r.simulationType}</td>
                  <td className="p-3"><StatusPill status={r.status} /></td>
                  <td className="p-3 text-white/60">{r.trials_submitted - r.trials_excluded} / {r.trials_submitted}</td>
                  <td className="p-3 text-white/50">{r.executionMs ? `${r.executionMs}ms` : "—"}</td>
                  <td className="p-3 text-white/40">{timeAgo(r.ts)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const map: Record<string, string> = {
    passed: "bg-pass/15 text-pass",
    warning: "bg-warn/15 text-warn",
    failed: "bg-fail/15 text-fail",
  };
  return <span className={cn("rounded-full px-2 py-0.5 text-xs", map[status])}>{status}</span>;
}

// ── API Keys ──────────────────────────────────────────────────────────────────
function ApiKeys() {
  const { user } = useAuth();
  const [keys, setKeys] = useState<ApiKeyRecord[]>([]);
  const [newName, setNewName] = useState("");
  const [revealed, setRevealed] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [creating, setCreating] = useState(false);

  const refresh = useCallback(() => {
    if (user) setKeys(listKeys(user.uid));
  }, [user]);
  useEffect(refresh, [refresh]);

  async function create() {
    if (!user) return;
    setCreating(true);
    const { raw } = await createKey(user.uid, newName);
    setRevealed(raw);
    setNewName("");
    setCreating(false);
    refresh();
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white">API Keys</h1>
        <p className="mt-1 text-sm text-white/50">Keys authenticate your API, SDK, and CLI requests.</p>
      </div>

      {revealed && (
        <div className="rounded-2xl border border-pass/30 bg-pass/[0.05] p-5">
          <p className="text-sm font-medium text-white">Copy your API key now</p>
          <p className="text-xs text-white/50">This is the only time it will be shown. We store only a hash.</p>
          <div className="mt-3 flex items-center gap-2">
            <code className="flex-1 overflow-x-auto rounded-lg border border-white/10 bg-black/40 px-3 py-2.5 font-mono text-sm text-white/80">
              {revealed}
            </code>
            <button
              onClick={() => {
                navigator.clipboard.writeText(revealed);
                setCopied(true);
                setTimeout(() => setCopied(false), 1500);
              }}
              className="btn-ghost shrink-0"
            >
              {copied ? <Check className="h-4 w-4 text-pass" /> : <Copy className="h-4 w-4" />} {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <button onClick={() => setRevealed(null)} className="mt-3 text-xs text-white/45 hover:text-white">
            I&apos;ve saved it — dismiss
          </button>
        </div>
      )}

      <div className="card p-5">
        <label className="mb-1.5 block text-xs font-medium text-white/55">Create a new key</label>
        <div className="flex gap-2">
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Key name (e.g. production, ci)"
            className="flex-1 rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-sm text-white/80 outline-none placeholder:text-white/25 focus:border-accent-blue/50"
          />
          <button onClick={create} disabled={creating} className="btn-accent shrink-0">
            {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />} Create
          </button>
        </div>
      </div>

      <div className="overflow-hidden rounded-2xl border border-white/[0.07]">
        {keys.length === 0 ? (
          <p className="py-10 text-center text-sm text-white/35">No keys yet. Create one above.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/[0.07] bg-white/[0.02] text-left text-xs text-white/45">
                <th className="p-3 font-medium">Name</th>
                <th className="p-3 font-medium">Key</th>
                <th className="p-3 font-medium">Created</th>
                <th className="p-3 font-medium">Last used</th>
                <th className="p-3" />
              </tr>
            </thead>
            <tbody>
              {keys.map((k) => (
                <tr key={k.id} className="border-b border-white/[0.05] last:border-0">
                  <td className="p-3 text-white/70">{k.name}</td>
                  <td className="p-3 font-mono text-xs text-white/50">{k.prefix}</td>
                  <td className="p-3 text-white/40">{new Date(k.createdAt).toLocaleDateString()}</td>
                  <td className="p-3 text-white/40">{k.lastUsed ? timeAgo(k.lastUsed) : "never"}</td>
                  <td className="p-3 text-right">
                    <button
                      onClick={() => {
                        if (user) { revokeKey(user.uid, k.id); refresh(); }
                      }}
                      className="rounded-lg p-2 text-white/30 hover:bg-white/5 hover:text-fail"
                      aria-label="Revoke key"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// ── Usage ─────────────────────────────────────────────────────────────────────
function Usage() {
  const { user } = useAuth();
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [stats, setStats] = useState<UsageStats | null>(null);

  useEffect(() => {
    if (!user) return;
    setRuns(listRunHistory());
    setStats(usageStats());
  }, [user]);

  if (!stats) return null;
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white">Usage</h1>
        <p className="mt-1 text-sm text-white/50">Derived from validations you&apos;ve run in this browser.</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-4">
        <Stat label="Requests today" value={String(stats.requestsToday)} />
        <Stat label="Total validations" value={String(stats.totalValidations)} />
        <Stat label="Pass rate" value={stats.totalValidations ? `${stats.successRate}%` : "—"} />
        <Stat label="Avg. exclusion rate" value={stats.totalValidations ? `${stats.avgExclusionRate}%` : "—"} />
      </div>
      <RecentRuns runs={runs.slice(0, 20)} onRun={() => { /* stays on usage */ }} />
    </div>
  );
}

// ── Run Simulation ────────────────────────────────────────────────────────────
function RunSimulation() {
  return <ValidationDashboard />;
}

// ── Settings ──────────────────────────────────────────────────────────────────
function SettingsPanel() {
  const { user, signOut } = useAuth();
  if (!user) return null;
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white">Settings</h1>
        <p className="mt-1 text-sm text-white/50">Manage your account and session.</p>
      </div>

      <div className="card p-5">
        <h2 className="mb-4 text-sm font-semibold text-white">Account</h2>
        <dl className="space-y-3 text-sm">
          <Row label="Name" value={user.name} />
          <Row label="Email" value={user.email} />
          <Row label="User ID" value={<code className="font-mono text-xs text-white/50">{user.uid}</code>} />
          <Row label="Auth backend" value="Local (browser)" />
        </dl>
      </div>

      <div className="card p-5">
        <h2 className="mb-1 text-sm font-semibold text-white">Danger zone</h2>
        <p className="mb-4 text-xs text-white/45">Clears keys and validation history stored in this browser.</p>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => {
              if (confirm("Clear all local API keys and validation history?")) {
                localStorage.removeItem(`simapi.keys.${user.uid}`);
                localStorage.removeItem(`simapi.runs.${user.uid}`);
                location.reload();
              }
            }}
            className="btn-ghost"
          >
            <Trash2 className="h-4 w-4" /> Clear local data
          </button>
          <button onClick={() => signOut()} className="btn-ghost">
            <LogOut className="h-4 w-4" /> Sign out
          </button>
        </div>
      </div>

      <Link href={site.github} className="inline-flex items-center gap-1.5 text-sm text-white/45 hover:text-white">
        View the source on GitHub <ExternalLink className="h-3.5 w-3.5" />
      </Link>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-white/[0.05] pb-3 last:border-0 last:pb-0">
      <dt className="text-white/45">{label}</dt>
      <dd className="text-white/75">{value}</dd>
    </div>
  );
}

function timeAgo(ts: number): string {
  const s = Math.floor((Date.now() - ts) / 1000);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}
