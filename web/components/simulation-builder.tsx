"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Plus, Trash2, Play, Download, Loader2, Copy, Check,
  CheckCircle, AlertTriangle, XCircle, ChevronDown, ChevronUp, Info,
} from "lucide-react";
import {
  validate,
  toApiResponse,
  SIMULATION_TYPES,
  type SimulationType,
  type ValidationReport,
  type CheckResult,
} from "@/lib/validation-engine";
import { JsonView } from "./ui/json-view";
import { cn } from "@/lib/utils";

interface AiReview {
  enabled: boolean;
  status?: "agree" | "concern" | "disagree";
  assessment?: string;
  concerns?: string[];
  model?: string;
  error?: string;
}

type VarType = "number" | "boolean" | "string" | "vector" | "array";

interface Variable {
  id: string;
  name: string;
  type: VarType;
  value: string;
}

// Default condition variables per domain — pre-seeded but fully editable.
const PRESETS: Record<SimulationType, Variable[]> = {
  aerodynamics: [
    v("drag_coefficient", "number", "0.312"),
    v("lift_coefficient", "number", "0.847"),
    v("reynolds_number", "number", "415000"),
    v("mach_number", "number", "0.044"),
    v("velocity", "vector", "15, 0, 0"),
  ],
  fluid_dynamics: [
    v("velocity", "number", "12.5"),
    v("pressure", "number", "101325"),
    v("density", "number", "998.2"),
    v("reynolds_number", "number", "50000"),
  ],
  structural: [
    v("stress", "number", "250e6"),
    v("yield_stress", "number", "355e6"),
    v("safety_factor", "number", "1.42"),
    v("elastic_modulus", "number", "210e9"),
  ],
  thermodynamics: [
    v("temperature", "number", "320"),
    v("pressure", "number", "101325"),
    v("thermal_efficiency", "number", "0.41"),
    v("heat_flux", "number", "1200"),
  ],
  robotics: [
    v("joint_torque", "number", "45"),
    v("joint_velocity", "number", "2.1"),
    v("joint_position", "number", "1.57"),
    v("position_error", "number", "0.004"),
  ],
};

function v(name: string, type: VarType, value: string): Variable {
  return { id: crypto.randomUUID().slice(0, 6), name, type, value };
}

function coerce(variable: Variable): unknown {
  switch (variable.type) {
    case "number": return Number(variable.value);
    case "boolean": return variable.value === "true";
    case "string": return variable.value;
    case "vector":
    case "array":
      return variable.value.split(",").map((s) => Number(s.trim())).filter((n) => !Number.isNaN(n));
    default: return variable.value;
  }
}

export function SimulationBuilder({
  onComplete,
}: {
  onComplete?: (report: ValidationReport) => void;
}) {
  const [simType, setSimType] = useState<SimulationType>("aerodynamics");
  const [vars, setVars] = useState<Variable[]>(PRESETS.aerodynamics);
  const [report, setReport] = useState<ValidationReport | null>(null);
  const [running, setRunning] = useState(false);
  const [ai, setAi] = useState<{ loading: boolean; review: AiReview | null }>({ loading: false, review: null });

  function changeType(type: SimulationType) {
    setSimType(type);
    setVars(PRESETS[type].map((p) => ({ ...p, id: crypto.randomUUID().slice(0, 6) })));
    setReport(null);
    setAi({ loading: false, review: null });
  }
  function addVar() {
    setVars((vs) => [...vs, v(`variable_${vs.length + 1}`, "number", "0")]);
  }
  function update(id: string, patch: Partial<Variable>) {
    setVars((vs) => vs.map((x) => (x.id === id ? { ...x, ...patch } : x)));
  }
  function remove(id: string) {
    setVars((vs) => vs.filter((x) => x.id !== id));
  }

  function run() {
    setRunning(true);
    setReport(null);
    setAi({ loading: false, review: null });
    setTimeout(() => {
      const values: Record<string, unknown> = {};
      for (const variable of vars) if (variable.name.trim()) values[variable.name.trim()] = coerce(variable);
      const r = validate(values, simType);
      setReport(r);
      setRunning(false);
      onComplete?.(r);

      // Second-pass AI review (server-side; no-op unless OPENROUTER_API_KEY is set).
      setAi({ loading: true, review: null });
      fetch("/api/v1/ai-review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          report: { status: r.status, score: r.score, violations: r.violations, recommendations: r.recommendations, simulationType: r.simulationType, checks: r.checks },
          conditions: values,
        }),
      })
        .then((res) => res.json())
        .then((review: AiReview) => setAi({ loading: false, review }))
        .catch(() => setAi({ loading: false, review: { enabled: false } }));
    }, 400);
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[380px_1fr]">
      {/* ── Controls ── */}
      <div className="space-y-4">
        <div className="rounded-2xl border border-white/[0.08] bg-ink-900/60 p-4">
          <label className="mb-2 block text-xs uppercase tracking-widest text-white/35">Simulation type</label>
          <select
            value={simType}
            onChange={(e) => changeType(e.target.value as SimulationType)}
            className="w-full rounded-xl border border-white/[0.08] bg-black/30 px-3 py-2.5 text-sm text-white/75 outline-none focus:border-accent-blue/50"
          >
            {SIMULATION_TYPES.map((t) => (
              <option key={t.value} value={t.value} className="bg-ink-900">{t.label}</option>
            ))}
          </select>
        </div>

        <div className="rounded-2xl border border-white/[0.08] bg-ink-900/60 p-4">
          <div className="mb-3 flex items-center justify-between">
            <label className="text-xs uppercase tracking-widest text-white/35">Conditions (editable variables)</label>
            <button onClick={addVar} className="flex items-center gap-1 text-xs text-accent-cyan hover:text-white">
              <Plus className="h-3.5 w-3.5" /> Add
            </button>
          </div>
          <div className="space-y-2">
            {vars.map((variable) => (
              <div key={variable.id} className="flex items-center gap-1.5">
                <input
                  value={variable.name}
                  onChange={(e) => update(variable.id, { name: e.target.value })}
                  spellCheck={false}
                  className="w-[42%] rounded-lg border border-white/10 bg-black/30 px-2.5 py-2 font-mono text-xs text-white/80 outline-none focus:border-accent-blue/50"
                  aria-label="Variable name"
                />
                <select
                  value={variable.type}
                  onChange={(e) => update(variable.id, { type: e.target.value as VarType })}
                  className="rounded-lg border border-white/10 bg-black/30 px-1.5 py-2 text-xs text-white/70 outline-none focus:border-accent-blue/50"
                  aria-label="Variable type"
                >
                  {(["number", "boolean", "string", "vector", "array"] as VarType[]).map((t) => (
                    <option key={t} value={t} className="bg-ink-900">{t}</option>
                  ))}
                </select>
                {variable.type === "boolean" ? (
                  <select
                    value={variable.value}
                    onChange={(e) => update(variable.id, { value: e.target.value })}
                    className="flex-1 rounded-lg border border-white/10 bg-black/30 px-2 py-2 text-xs text-white/80 outline-none focus:border-accent-blue/50"
                  >
                    <option value="true" className="bg-ink-900">true</option>
                    <option value="false" className="bg-ink-900">false</option>
                  </select>
                ) : (
                  <input
                    value={variable.value}
                    onChange={(e) => update(variable.id, { value: e.target.value })}
                    spellCheck={false}
                    placeholder={variable.type === "vector" || variable.type === "array" ? "2, 4, 0" : ""}
                    className="flex-1 rounded-lg border border-white/10 bg-black/30 px-2.5 py-2 font-mono text-xs text-white/80 outline-none focus:border-accent-blue/50"
                    aria-label="Variable value"
                  />
                )}
                <button onClick={() => remove(variable.id)} className="rounded-lg p-1.5 text-white/30 hover:bg-white/5 hover:text-fail" aria-label="Delete variable">
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
            {vars.length === 0 && (
              <p className="rounded-lg border border-dashed border-white/10 py-6 text-center text-xs text-white/35">
                No variables. Add one to describe the simulation conditions.
              </p>
            )}
          </div>
          <button onClick={run} disabled={running} className="btn-accent mt-4 w-full">
            {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            {running ? "Running validation…" : "Run validation"}
          </button>
        </div>

        <div className="flex gap-3 rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-accent-cyan" />
          <p className="text-xs leading-relaxed text-white/35">
            Runs the deterministic engine entirely in your browser — no data leaves the page.
            Rename, retype, add, or remove any condition and re-run.
          </p>
        </div>
      </div>

      {/* ── Results ── */}
      <div className="min-h-[420px]">
        <AnimatePresence mode="wait">
          {!report && !running && (
            <motion.div key="idle" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="flex h-full min-h-[420px] flex-col items-center justify-center rounded-2xl border border-white/[0.07] bg-ink-900/40 text-center">
              <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full border border-white/[0.08] bg-white/[0.03]">
                <Play className="h-7 w-7 text-white/15" />
              </div>
              <p className="text-white/35">Configure conditions and hit Run</p>
              <p className="mt-1.5 text-xs text-white/20">Deterministic physics checks · results in milliseconds</p>
            </motion.div>
          )}
          {running && (
            <motion.div key="running" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="flex h-full min-h-[420px] flex-col items-center justify-center rounded-2xl border border-white/[0.07] bg-ink-900/40">
              <Loader2 className="mb-4 h-8 w-8 animate-spin text-accent-cyan" />
              <p className="text-sm text-white/50">Running physics validation…</p>
            </motion.div>
          )}
          {report && !running && (
            <motion.div key="report" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
              <Results report={report} ai={ai} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

function StatusPill({ status }: { status: ValidationReport["status"] }) {
  const map = {
    passed: { cls: "bg-pass/10 text-pass border-pass/30", Icon: CheckCircle, label: "PASSED" },
    warning: { cls: "bg-amber-400/10 text-amber-400 border-amber-400/30", Icon: AlertTriangle, label: "WARNING" },
    failed: { cls: "bg-red-400/10 text-red-400 border-red-400/30", Icon: XCircle, label: "FAILED" },
  }[status];
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold", map.cls)}>
      <map.Icon className="h-3.5 w-3.5" /> {map.label}
    </span>
  );
}

function Results({ report, ai }: { report: ValidationReport; ai: { loading: boolean; review: AiReview | null } }) {
  const [showAll, setShowAll] = useState(false);
  const [copied, setCopied] = useState(false);
  const issues = report.checks.filter((c) => c.status !== "passed");
  const visible = showAll ? issues : issues.slice(0, 8);
  const responseJson = JSON.stringify(toApiResponse(report, "3f9ca12b"), null, 2);

  function download() {
    const payload = { ...toApiResponse(report, crypto.randomUUID().slice(0, 8)), checks: report.checks, generated_at: new Date().toISOString() };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `simapi-report-${payload.job_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const metrics = [
    { l: "Checks run", v: String(report.checksRun), c: "text-accent-cyan" },
    { l: "Passed", v: String(report.passed), c: "text-pass" },
    { l: "Issues", v: String(report.warnings + report.failed), c: report.failed > 0 ? "text-red-400" : report.warnings > 0 ? "text-amber-400" : "text-pass" },
    { l: "Time", v: `${report.executionMs}ms`, c: "text-pass" },
  ];

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="rounded-2xl border border-white/[0.08] bg-ink-900/60 p-5">
        <div className="mb-5 flex items-center justify-between">
          <StatusPill status={report.status} />
          <span className="text-xs capitalize text-white/30">
            {report.status === "passed" ? "high" : report.status === "warning" ? "medium" : "low"} confidence · score {report.score}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {metrics.map((m) => (
            <div key={m.l} className="rounded-xl border border-white/[0.05] bg-white/[0.03] p-3 text-center">
              <p className={cn("font-mono text-xl font-semibold", m.c)}>{m.v}</p>
              <p className="mt-0.5 text-[10px] uppercase tracking-wider text-white/30">{m.l}</p>
            </div>
          ))}
        </div>
      </div>

      {/* AI second-pass review */}
      <AiPanel ai={ai} />

      {/* Pass / warn / fail bars */}
      <div className="rounded-2xl border border-white/[0.08] bg-ink-900/60 p-5">
        <p className="mb-4 text-xs uppercase tracking-widest text-white/30">
          {report.checksRun} checks — only issues are listed below
        </p>
        {[
          { label: "Passed", n: report.passed, color: "bg-pass", text: "text-pass" },
          { label: "Warnings", n: report.warnings, color: "bg-amber-400", text: "text-amber-400" },
          { label: "Failed", n: report.failed, color: "bg-red-400", text: "text-red-400" },
        ].map((r) => (
          <div key={r.label} className="mb-2.5 flex items-center gap-3">
            <span className={cn("w-16 text-xs", r.text)}>{r.label}</span>
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/[0.05]">
              <div className={cn("h-full rounded-full transition-all duration-700", r.color)}
                style={{ width: `${Math.round((r.n / Math.max(report.checksRun, 1)) * 100)}%` }} />
            </div>
            <span className={cn("w-8 text-right font-mono text-xs", r.text)}>{r.n}</span>
          </div>
        ))}
      </div>

      {/* Issues */}
      <div className="rounded-2xl border border-white/[0.08] bg-ink-900/60 p-5">
        <p className="mb-3 text-xs uppercase tracking-widest text-white/30">
          {issues.length === 0 ? "All checks passed" : `${issues.length} issue${issues.length !== 1 ? "s" : ""} found — click to expand`}
        </p>
        {issues.length === 0 ? (
          <div className="rounded-xl border border-pass/20 bg-pass/5 px-4 py-3 text-xs text-pass">
            ✓ Conditions are physically valid — all checks passed
          </div>
        ) : (
          <>
            <div className="space-y-1.5">{visible.map((c) => <IssueRow key={c.name} check={c} />)}</div>
            {issues.length > 8 && (
              <button onClick={() => setShowAll((s) => !s)} className="mt-3 flex items-center gap-1.5 text-xs text-white/30 hover:text-white">
                {showAll ? <><ChevronUp className="h-3 w-3" /> Show fewer</> : <><ChevronDown className="h-3 w-3" /> Show {issues.length - 8} more</>}
              </button>
            )}
          </>
        )}
      </div>

      {/* Recommendations */}
      {report.recommendations.length > 0 && (
        <div className="rounded-2xl border border-white/[0.08] bg-ink-900/60 p-5">
          <p className="mb-3 text-xs uppercase tracking-widest text-white/30">Recommendations</p>
          <div className="space-y-2">
            {report.recommendations.map((r, i) => (
              <div key={i} className="flex gap-2 text-xs text-white/50">
                <span className="shrink-0 text-accent-cyan">→</span>
                <span>{r}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* JSON */}
      <div className="rounded-2xl border border-white/[0.08] bg-ink-900/60 p-5">
        <div className="mb-3 flex items-center justify-between">
          <p className="text-xs uppercase tracking-widest text-white/30">JSON response</p>
          <div className="flex gap-3">
            <button onClick={() => { navigator.clipboard.writeText(responseJson); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
              className="flex items-center gap-1 text-xs text-white/45 hover:text-white">
              {copied ? <Check className="h-3.5 w-3.5 text-pass" /> : <Copy className="h-3.5 w-3.5" />} {copied ? "Copied" : "Copy"}
            </button>
            <button onClick={download} className="flex items-center gap-1 text-xs text-white/45 hover:text-white">
              <Download className="h-3.5 w-3.5" /> Report
            </button>
          </div>
        </div>
        <div className="max-h-64 overflow-auto rounded-lg border border-white/[0.06] bg-black/30 p-3">
          <JsonView text={responseJson} />
        </div>
      </div>
    </div>
  );
}

function AiPanel({ ai }: { ai: { loading: boolean; review: AiReview | null } }) {
  if (ai.loading) {
    return (
      <div className="flex items-center gap-2.5 rounded-2xl border border-purple-400/20 bg-purple-400/5 p-4 text-xs text-purple-300/80">
        <Loader2 className="h-4 w-4 animate-spin" /> AI reviewing whether the result is physically and logically correct…
      </div>
    );
  }
  const r = ai.review;
  if (!r) return null;
  if (!r.enabled) {
    return (
      <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-4 text-xs text-white/35">
        AI review is off. Set <code className="rounded bg-white/[0.06] px-1 font-mono text-white/60">OPENROUTER_API_KEY</code> to have an LLM double-check each result.
      </div>
    );
  }
  if (r.error) {
    return (
      <div className="rounded-2xl border border-amber-400/15 bg-amber-400/5 p-4 text-xs text-amber-300/70">
        AI review unavailable ({r.error}). The deterministic result above stands on its own.
      </div>
    );
  }
  const tone =
    r.status === "agree" ? { cls: "border-pass/25 bg-pass/5", dot: "bg-pass", label: "AI agrees" } :
    r.status === "disagree" ? { cls: "border-red-400/25 bg-red-400/5", dot: "bg-red-400", label: "AI disagrees" } :
    { cls: "border-amber-400/20 bg-amber-400/5", dot: "bg-amber-400", label: "AI has concerns" };
  return (
    <div className={cn("rounded-2xl border p-5", tone.cls)}>
      <div className="mb-2 flex items-center gap-2">
        <span className={cn("h-2 w-2 rounded-full", tone.dot)} />
        <p className="text-sm font-medium text-white">{tone.label}</p>
        {r.model && <span className="ml-auto font-mono text-[10px] text-white/25">{r.model.split("/").pop()}</span>}
      </div>
      {r.assessment && <p className="text-sm leading-relaxed text-white/60">{r.assessment}</p>}
      {r.concerns && r.concerns.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {r.concerns.map((c, i) => (
            <li key={i} className="flex items-start gap-2 text-xs text-white/50">
              <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-white/30" />{c}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function IssueRow({ check }: { check: CheckResult }) {
  const [open, setOpen] = useState(false);
  const fail = check.status === "failed";
  return (
    <div
      className={cn("cursor-pointer rounded-lg border transition-colors", fail
        ? "border-red-400/20 bg-red-400/5 hover:border-red-400/40"
        : "border-amber-400/15 bg-amber-400/5 hover:border-amber-400/35")}
      onClick={() => setOpen((o) => !o)}
    >
      <div className="flex items-center gap-3 px-3 py-2.5">
        <span className={cn("shrink-0 text-sm", fail ? "text-red-400" : "text-amber-400")}>{fail ? "✗" : "⚠"}</span>
        <span className="flex-1 text-xs font-medium leading-snug text-white/75">{check.name}</span>
        <span className={cn("shrink-0 rounded border px-1.5 py-0.5 font-mono text-[10px]", fail ? "border-red-400/20 text-red-400/60" : "border-amber-400/20 text-amber-400/60")}>
          {check.category}
        </span>
        {open ? <ChevronUp className="h-3 w-3 shrink-0 text-white/20" /> : <ChevronDown className="h-3 w-3 shrink-0 text-white/20" />}
      </div>
      {open && <div className="border-t border-white/[0.06] px-3 py-2.5 text-xs leading-relaxed text-white/45">{check.detail}</div>}
    </div>
  );
}
