"use client";

/** Filterable, exportable log of every validation run in this browser. */
import { useEffect, useMemo, useState } from "react";
import { Download, Search, Trash2 } from "lucide-react";
import { listRuns, clearRuns, type RunRecord } from "@/lib/run-history";
import { cn } from "@/lib/utils";

function toCsv(runs: RunRecord[]): string {
  const header = ["id", "timestamp", "simulation_type", "status", "engine", "execution_ms", "trials_submitted", "trials_excluded", "unique_checks"];
  const rows = runs.map((r) => [
    r.id, new Date(r.ts).toISOString(), r.simulationType, r.status, r.engine,
    String(r.executionMs), String(r.trials_submitted), String(r.trials_excluded), String(r.unique_checks),
  ]);
  return [header, ...rows].map((row) => row.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(",")).join("\n");
}

function download(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

export function LogsPanel({ onInspect }: { onInspect: (id: string) => void }) {
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "passed" | "warning" | "failed">("all");

  useEffect(() => { setRuns(listRuns()); }, []);

  const filtered = useMemo(
    () =>
      runs.filter((r) => {
        if (statusFilter !== "all" && r.status !== statusFilter) return false;
        if (query && !`${r.simulationType} ${r.id}`.toLowerCase().includes(query.toLowerCase())) return false;
        return true;
      }),
    [runs, query, statusFilter],
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-white">Logs</h1>
          <p className="mt-1 text-sm text-white/50">Every validation request made from this browser.</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => download(`simapi-logs-${Date.now()}.csv`, toCsv(filtered), "text/csv")}
            disabled={filtered.length === 0}
            className="btn-ghost disabled:opacity-40"
          >
            <Download className="h-4 w-4" /> Export CSV
          </button>
          <button
            onClick={() => {
              if (confirm(`Clear all ${runs.length} log entries stored in this browser?`)) {
                clearRuns();
                setRuns([]);
              }
            }}
            disabled={runs.length === 0}
            className="btn-ghost disabled:opacity-40"
          >
            <Trash2 className="h-4 w-4" /> Clear
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/30" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by simulation type or run ID…"
            className="w-full rounded-lg border border-white/10 bg-black/30 py-2.5 pl-9 pr-3 text-sm text-white/80 outline-none placeholder:text-white/25 focus:border-accent-blue/50"
          />
        </div>
        <div className="flex gap-1 rounded-lg border border-white/10 bg-black/20 p-1">
          {(["all", "passed", "warning", "failed"] as const).map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={cn(
                "rounded-md px-3 py-1.5 text-xs capitalize transition-colors",
                statusFilter === s ? "bg-white/10 text-white" : "text-white/45 hover:text-white",
              )}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-white/10 py-16 text-center text-sm text-white/35">
          {runs.length === 0 ? "No validations yet. Run one from the Playground tab." : "No runs match this filter."}
        </div>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-white/[0.07]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/[0.07] bg-white/[0.02] text-left text-xs text-white/45">
                <th className="p-3 font-medium">Run ID</th>
                <th className="p-3 font-medium">Type</th>
                <th className="p-3 font-medium">Status</th>
                <th className="p-3 font-medium">Engine</th>
                <th className="p-3 font-medium">Trials</th>
                <th className="p-3 font-medium">Latency</th>
                <th className="p-3 font-medium">When</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr
                  key={r.id}
                  onClick={() => onInspect(r.id)}
                  className="cursor-pointer border-b border-white/[0.05] transition-colors last:border-0 hover:bg-white/[0.02]"
                >
                  <td className="p-3 font-mono text-xs text-white/50">{r.id}</td>
                  <td className="p-3 text-white/70">{r.simulationType}</td>
                  <td className="p-3">
                    <span className={cn(
                      "rounded-full px-2 py-0.5 text-xs",
                      r.status === "passed" ? "bg-pass/15 text-pass" : r.status === "warning" ? "bg-warn/15 text-warn" : "bg-fail/15 text-fail",
                    )}>
                      {r.status}
                    </span>
                  </td>
                  <td className="p-3 text-xs text-white/45">{r.engine.replace("-checks", "")}</td>
                  <td className="p-3 text-white/60">{r.trials_submitted - r.trials_excluded} / {r.trials_submitted}</td>
                  <td className="p-3 text-white/50">{r.executionMs ? `${r.executionMs}ms` : "—"}</td>
                  <td className="p-3 text-white/40">{new Date(r.ts).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
