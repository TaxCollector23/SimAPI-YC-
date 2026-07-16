"use client";

import { useEffect, useState } from "react";
import { CheckCircle, XCircle, AlertTriangle, ArrowRight, GitCompare } from "lucide-react";
import { cn } from "@/lib/utils";
import { listRuns, diffRuns, type RunRecord } from "@/lib/run-history";

const statusIcon: Record<string, React.ReactNode> = {
  passed: <CheckCircle className="h-3.5 w-3.5 text-pass" />,
  warning: <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />,
  failed: <XCircle className="h-3.5 w-3.5 text-red-400" />,
};

export function HistoryPanel() {
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [a, setA] = useState<string | null>(null); // older baseline
  const [b, setB] = useState<string | null>(null); // newer

  useEffect(() => {
    const r = listRuns();
    setRuns(r);
    if (r.length >= 2) { setB(r[0].id); setA(r[1].id); }
  }, []);

  const runA = runs.find((r) => r.id === a);
  const runB = runs.find((r) => r.id === b);
  const diff = runA && runB ? diffRuns(runA, runB) : null;

  if (runs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-2xl border border-white/[0.07] bg-ink-900/40 py-32 text-center">
        <GitCompare className="mb-3 h-7 w-7 text-white/20" />
        <p className="text-white/40">No runs yet</p>
        <p className="mt-1 text-xs text-white/25">Validate a dataset on the Output tab — your runs are saved here for comparison.</p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <RunPicker label="Baseline (older)" runs={runs} value={a} onChange={setA} />
        <RunPicker label="Compare (newer)" runs={runs} value={b} onChange={setB} />
      </div>

      {diff && runA && runB && (
        <div className="space-y-4">
          <div className="flex items-center justify-center gap-3 text-xs text-white/50">
            <RunChip r={runA} /> <ArrowRight className="h-4 w-4 text-white/30" /> <RunChip r={runB} />
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <DiffCard title="Resolved" count={diff.resolved.length} tone="pass" items={diff.resolved} empty="No issues resolved" />
            <DiffCard title="Introduced" count={diff.introduced.length} tone="fail" items={diff.introduced} empty="No new issues" />
            <DiffCard title="Still present" count={diff.persisting.length} tone="warn" items={diff.persisting} empty="None persisting" />
          </div>
          <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] px-4 py-3 text-xs text-white/55">
            Exclusions {diff.exclusionDelta === 0 ? "unchanged" : diff.exclusionDelta > 0
              ? <span className="text-amber-400">+{diff.exclusionDelta} more trials excluded</span>
              : <span className="text-pass">{diff.exclusionDelta} fewer trials excluded</span>}
            {" "}({runA.trials_excluded} → {runB.trials_excluded} of {runB.trials_submitted}).
          </div>
        </div>
      )}

      <div>
        <p className="mb-2 text-xs uppercase tracking-widest text-white/30">All runs ({runs.length})</p>
        <div className="overflow-hidden rounded-2xl border border-white/[0.07]">
          {runs.map((r) => (
            <div key={r.id} className="flex items-center justify-between border-b border-white/[0.05] px-4 py-2.5 text-xs last:border-0">
              <div className="flex items-center gap-2 text-white/60">
                {statusIcon[r.status]} <span className="font-mono text-white/40">{r.id}</span> {r.simulationType}
              </div>
              <div className="flex items-center gap-4 text-white/40">
                <span>{r.issues.length} issues</span>
                <span>{r.trials_excluded}/{r.trials_submitted} excl</span>
                <span>{new Date(r.ts).toLocaleString()}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function RunPicker({ label, runs, value, onChange }: { label: string; runs: RunRecord[]; value: string | null; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="mb-1 block text-[11px] text-white/45">{label}</label>
      <select value={value ?? ""} onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-white/[0.08] bg-black/30 px-3 py-2 text-sm text-white/75 outline-none focus:border-accent-blue/40">
        {runs.map((r) => (
          <option key={r.id} value={r.id}>{new Date(r.ts).toLocaleString()} · {r.status} · {r.issues.length} issues</option>
        ))}
      </select>
    </div>
  );
}

function RunChip({ r }: { r: RunRecord }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-black/20 px-2.5 py-1">
      {statusIcon[r.status]} <span className="font-mono text-white/40">{r.id}</span>
    </span>
  );
}

function DiffCard({ title, count, tone, items, empty }: { title: string; count: number; tone: "pass" | "fail" | "warn"; items: { name: string; human_name: string }[]; empty: string }) {
  const cls = tone === "pass" ? "border-pass/25 bg-pass/5" : tone === "fail" ? "border-red-400/25 bg-red-400/5" : "border-amber-400/20 bg-amber-400/5";
  const txt = tone === "pass" ? "text-pass" : tone === "fail" ? "text-red-400" : "text-amber-400";
  return (
    <div className={cn("rounded-2xl border p-4", cls)}>
      <p className={cn("text-sm font-semibold", txt)}>{title} · {count}</p>
      <div className="mt-2 space-y-1">
        {items.length === 0 ? <p className="text-xs text-white/30">{empty}</p>
          : items.slice(0, 8).map((i) => <p key={i.name} className="text-xs text-white/55">{i.human_name}</p>)}
        {items.length > 8 && <p className="text-xs text-white/30">+{items.length - 8} more</p>}
      </div>
    </div>
  );
}
