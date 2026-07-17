"use client";

/**
 * Analytics — every number and chart here is computed from RunRecord[] in
 * lib/run-history.ts, i.e. validations the user actually ran against the live
 * API in this browser. No seeded or synthetic series. A fresh account shows
 * empty states, not fake charts.
 */
import { useEffect, useState } from "react";
import { listRuns, usageStats, type RunRecord, type UsageStats } from "@/lib/run-history";

function Empty({ label }: { label: string }) {
  return (
    <div className="flex h-40 items-center justify-center rounded-xl border border-dashed border-white/10 text-sm text-white/30">
      {label}
    </div>
  );
}

/** Simple SVG bar chart — no charting dependency needed for this. */
function BarChart({ data, formatValue }: { data: { label: string; value: number }[]; formatValue?: (v: number) => string }) {
  if (data.length === 0) return <Empty label="No data yet" />;
  const max = Math.max(...data.map((d) => d.value), 1);
  const w = 100 / data.length;
  return (
    <div className="flex h-40 items-end gap-1">
      {data.map((d, i) => (
        <div key={i} className="group relative flex-1" style={{ width: `${w}%` }}>
          <div
            className="mx-auto rounded-t bg-accent-cyan/60 transition-all group-hover:bg-accent-cyan"
            style={{ height: `${Math.max(4, (d.value / max) * 140)}px` }}
          />
          <div className="pointer-events-none absolute -top-7 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-black/80 px-1.5 py-0.5 text-[10px] text-white opacity-0 group-hover:opacity-100">
            {formatValue ? formatValue(d.value) : d.value}
          </div>
        </div>
      ))}
    </div>
  );
}

/** Simple SVG line chart for a latency/trend series. */
function LineChart({ points }: { points: number[] }) {
  if (points.length < 2) return <Empty label="Need at least 2 runs to show a trend" />;
  const max = Math.max(...points, 1);
  const min = Math.min(...points, 0);
  const range = max - min || 1;
  const w = 100, h = 100;
  const step = w / (points.length - 1);
  const path = points.map((p, i) => `${i === 0 ? "M" : "L"} ${i * step} ${h - ((p - min) / range) * h}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className="h-40 w-full">
      <path d={path} fill="none" stroke="currentColor" strokeWidth="2" className="text-accent-blue" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-white/[0.07] bg-ink-900/50 p-5">
      <h3 className="text-sm font-semibold text-white">{title}</h3>
      <div className="mt-4">{children}</div>
    </div>
  );
}

export function AnalyticsPanel() {
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [stats, setStats] = useState<UsageStats | null>(null);

  useEffect(() => {
    setRuns(listRuns());
    setStats(usageStats());
  }, []);

  if (!stats) return null;

  const chronological = [...runs].reverse();
  const passRateOverTime = chronological.map((r) => (r.status === "passed" ? 100 : r.status === "warning" ? 50 : 0));
  const latencyTrend = chronological.filter((r) => r.executionMs > 0).map((r) => r.executionMs);
  const exclusionByType = Object.values(
    runs.reduce<Record<string, { label: string; value: number; count: number }>>((acc, r) => {
      const key = r.simulationType;
      acc[key] ??= { label: key, value: 0, count: 0 };
      acc[key].value += r.trials_submitted ? (r.trials_excluded / r.trials_submitted) * 100 : 0;
      acc[key].count += 1;
      return acc;
    }, {}),
  ).map((d) => ({ label: d.label, value: Math.round(d.value / d.count) }));
  const statusBreakdown = ["passed", "warning", "failed"].map((s) => ({
    label: s,
    value: runs.filter((r) => r.status === s).length,
  }));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white">Analytics</h1>
        <p className="mt-1 text-sm text-white/50">
          Computed from {runs.length} validation{runs.length === 1 ? "" : "s"} you&apos;ve run in this browser.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-4">
        <Card title="Requests today">
          <p className="text-3xl font-semibold text-white">{stats.requestsToday}</p>
        </Card>
        <Card title="Pass rate">
          <p className="text-3xl font-semibold text-white">{runs.length ? `${stats.successRate}%` : "—"}</p>
        </Card>
        <Card title="Avg. latency">
          <p className="text-3xl font-semibold text-white">{stats.avgLatencyMs ? `${stats.avgLatencyMs}ms` : "—"}</p>
        </Card>
        <Card title="Avg. exclusion rate">
          <p className="text-3xl font-semibold text-white">{runs.length ? `${stats.avgExclusionRate}%` : "—"}</p>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Status breakdown">
          <BarChart data={statusBreakdown} />
          <div className="mt-3 flex justify-around text-xs text-white/40">
            {statusBreakdown.map((d) => <span key={d.label}>{d.label} ({d.value})</span>)}
          </div>
        </Card>
        <Card title="Corrupted-trial detection by simulation type">
          <BarChart data={exclusionByType} formatValue={(v) => `${v}% excluded`} />
          <div className="mt-3 flex flex-wrap justify-around gap-1 text-xs text-white/40">
            {exclusionByType.map((d) => <span key={d.label}>{d.label}</span>)}
          </div>
        </Card>
        <Card title="Pass rate over time (oldest → newest)">
          <LineChart points={passRateOverTime} />
        </Card>
        <Card title="Latency trend (ms, oldest → newest)">
          <LineChart points={latencyTrend} />
        </Card>
      </div>
    </div>
  );
}
