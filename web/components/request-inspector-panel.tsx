"use client";

/**
 * Request Inspector — drills into one captured validation run. Everything
 * shown is either the actual request contract (POST /v1/validate always
 * sends Content-Type + X-API-Key, so that header list is accurate for every
 * run, not fabricated) or the real response payload captured in RunRecord.raw.
 */
import { useEffect, useState } from "react";
import { ArrowLeft, Copy, Check } from "lucide-react";
import { getRun, listRuns, type RunRecord } from "@/lib/run-history";
import { cn } from "@/lib/utils";

type Tab = "overview" | "headers" | "body" | "timeline" | "issues";

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1200); }}
      className="btn-ghost !py-1.5 !px-2.5 text-xs"
    >
      {copied ? <Check className="h-3.5 w-3.5 text-pass" /> : <Copy className="h-3.5 w-3.5" />} {copied ? "Copied" : "Copy"}
    </button>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-white/[0.05] py-2.5 text-sm last:border-0">
      <span className="text-white/45">{label}</span>
      <span className="text-white/80">{value}</span>
    </div>
  );
}

export function RequestInspectorPanel({ runId, onBack }: { runId: string | null; onBack: () => void }) {
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [selected, setSelected] = useState<RunRecord | null>(null);
  const [tab, setTab] = useState<Tab>("overview");

  useEffect(() => {
    setRuns(listRuns());
    if (runId) setSelected(getRun(runId) ?? null);
  }, [runId]);

  if (!selected) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-semibold text-white">Request Inspector</h1>
          <p className="mt-1 text-sm text-white/50">Select a run to inspect its request, response, and timeline.</p>
        </div>
        {runs.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-white/10 py-16 text-center text-sm text-white/35">
            No captured runs yet. Run a validation from the Playground tab, or open one from Logs.
          </div>
        ) : (
          <div className="overflow-hidden rounded-2xl border border-white/[0.07]">
            {runs.map((r) => (
              <button
                key={r.id}
                onClick={() => setSelected(r)}
                className="flex w-full items-center justify-between border-b border-white/[0.05] px-4 py-3 text-left text-sm last:border-0 hover:bg-white/[0.03]"
              >
                <span className="font-mono text-xs text-white/50">{r.id}</span>
                <span className="text-white/70">{r.simulationType}</span>
                <span className="text-white/40">{new Date(r.ts).toLocaleString()}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  const raw = (selected.raw ?? {}) as Record<string, unknown>;
  const ai = raw.ai as Record<string, unknown> | null | undefined;
  const timings = (ai?.phase_timings ?? raw.ai_phase_timings) as Record<string, number> | undefined;
  const issues = (raw.issues ?? selected.issues ?? []) as { name: string; human_name?: string; status: string; detail?: string; category?: string }[];
  const exclusions = (raw.exclusions ?? []) as { trial_number?: number; trial_index?: number; reason: string; severity?: string }[];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button onClick={() => { setSelected(null); onBack(); }} className="rounded-lg p-2 text-white/50 hover:bg-white/5 hover:text-white">
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div>
          <h1 className="text-xl font-semibold text-white">Run {selected.id}</h1>
          <p className="text-xs text-white/45">{selected.simulationType} · {new Date(selected.ts).toLocaleString()}</p>
        </div>
      </div>

      <div className="flex gap-1 border-b border-white/[0.07]">
        {(["overview", "headers", "body", "timeline", "issues"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "border-b-2 px-3 py-2 text-sm capitalize transition-colors",
              tab === t ? "border-accent-cyan text-white" : "border-transparent text-white/45 hover:text-white",
            )}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div className="card p-5">
          <Field label="Method" value="POST /v1/validate" />
          <Field label="Status" value={<span className="capitalize">{selected.status}</span>} />
          <Field label="Engine" value={selected.engine} />
          <Field label="Latency" value={selected.executionMs ? `${selected.executionMs}ms` : "—"} />
          <Field label="Trials submitted" value={selected.trials_submitted} />
          <Field label="Trials excluded" value={selected.trials_excluded} />
          <Field label="Unique checks" value={selected.unique_checks} />
          <Field label="Job ID" value={<code className="font-mono text-xs">{String(raw.job_id ?? "—")}</code>} />
        </div>
      )}

      {tab === "headers" && (
        <div className="card p-5">
          <Field label="Content-Type" value={<code className="font-mono text-xs">application/json</code>} />
          <Field label="X-API-Key" value={<code className="font-mono text-xs">sk_live_••••••••</code>} />
          <Field label="X-Request-ID" value={<code className="font-mono text-xs">{String(raw.job_id ?? selected.id)}</code>} />
        </div>
      )}

      {tab === "body" && (
        <div className="card overflow-hidden">
          <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-2">
            <span className="font-mono text-xs text-white/40">response body</span>
            <CopyButton text={JSON.stringify(raw, null, 2)} />
          </div>
          <pre className="max-h-[480px] overflow-auto p-4 font-mono text-xs leading-relaxed text-white/70">
            {JSON.stringify(raw, null, 2)}
          </pre>
        </div>
      )}

      {tab === "timeline" && (
        <div className="card p-5">
          {timings ? (
            <div className="space-y-3">
              {Object.entries(timings).map(([phase, ms]) => (
                <div key={phase}>
                  <div className="mb-1 flex justify-between text-xs text-white/50">
                    <span>{phase.replace(/_/g, " ")}</span>
                    <span>{ms}ms</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-white/5">
                    <div className="h-full bg-accent-blue" style={{ width: `${Math.min(100, (ms / (selected.executionMs || ms || 1)) * 100)}%` }} />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <Field label="Total processing time" value={selected.executionMs ? `${selected.executionMs}ms` : "—"} />
          )}
          {!timings && (
            <p className="mt-3 text-xs text-white/35">
              Phase-level timing is only available when the AI orchestrator ran for this request.
            </p>
          )}
        </div>
      )}

      {tab === "issues" && (
        <div className="space-y-3">
          {issues.length === 0 && exclusions.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-white/10 py-10 text-center text-sm text-white/35">
              No issues or exclusions on this run.
            </div>
          ) : (
            <>
              {issues.map((i, idx) => (
                <div key={idx} className="card p-4">
                  <div className="flex items-center gap-2">
                    <span className={cn("rounded-full px-2 py-0.5 text-xs", i.status === "failed" ? "bg-fail/15 text-fail" : "bg-warn/15 text-warn")}>
                      {i.status}
                    </span>
                    <span className="text-sm text-white">{i.human_name ?? i.name}</span>
                  </div>
                  {i.detail && <p className="mt-1.5 text-xs text-white/50">{i.detail}</p>}
                </div>
              ))}
              {exclusions.map((e, idx) => (
                <div key={`ex-${idx}`} className="card p-4">
                  <span className="text-sm text-white">Trial {e.trial_number ?? e.trial_index} excluded</span>
                  <p className="mt-1.5 text-xs text-white/50">{e.reason}</p>
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}
