"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Plus, Trash2, Play, Download, Loader2, Check, AlertTriangle, XCircle, Copy } from "lucide-react";
import {
  validate,
  toApiResponse,
  SIMULATION_TYPES,
  type SimulationType,
  type ValidationReport,
} from "@/lib/validation-engine";
import { ScoreRing } from "./charts";
import { JsonView } from "./ui/json-view";
import { cn } from "@/lib/utils";

type VarType = "number" | "boolean" | "string" | "vector" | "array";

interface Variable {
  id: string;
  name: string;
  type: VarType;
  value: string; // raw text; coerced on run
}

const PRESETS: Record<SimulationType, Variable[]> = {
  aerodynamics: [
    v("cd", "number", "0.312"),
    v("cl", "number", "0.847"),
    v("re", "number", "415000"),
    v("mach", "number", "0.044"),
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
    case "number":
      return Number(variable.value);
    case "boolean":
      return variable.value === "true";
    case "string":
      return variable.value;
    case "vector":
    case "array":
      return variable.value
        .split(",")
        .map((s) => Number(s.trim()))
        .filter((n) => !Number.isNaN(n));
    default:
      return variable.value;
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
  const [copied, setCopied] = useState(false);

  function loadPreset(type: SimulationType) {
    setSimType(type);
    setVars(PRESETS[type].map((p) => ({ ...p, id: crypto.randomUUID().slice(0, 6) })));
    setReport(null);
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
    // Small delay so the transition reads as "running".
    setTimeout(() => {
      const values: Record<string, unknown> = {};
      for (const variable of vars) {
        if (variable.name.trim()) values[variable.name.trim()] = coerce(variable);
      }
      const r = validate(values, simType);
      setReport(r);
      setRunning(false);
      onComplete?.(r);
    }, 380);
  }

  function downloadReport() {
    if (!report) return;
    const payload = {
      ...toApiResponse(report, crypto.randomUUID().slice(0, 8)),
      checks: report.checks,
      generated_at: new Date().toISOString(),
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `simapi-report-${payload.job_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const responseJson = report
    ? JSON.stringify(toApiResponse(report, "3f9ca12b"), null, 2)
    : "";

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_1fr]">
      {/* Builder */}
      <div className="card p-5">
        <div className="mb-4">
          <label className="mb-1.5 block text-xs font-medium text-white/55">Simulation type</label>
          <div className="flex flex-wrap gap-1.5">
            {SIMULATION_TYPES.map((t) => (
              <button
                key={t.value}
                onClick={() => loadPreset(t.value)}
                className={cn(
                  "rounded-full px-3 py-1.5 text-xs font-medium transition-all",
                  simType === t.value ? "bg-white text-ink-950" : "border border-white/10 text-white/55 hover:text-white",
                )}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        <div className="mb-2 flex items-center justify-between">
          <label className="text-xs font-medium text-white/55">Variables</label>
          <button onClick={addVar} className="flex items-center gap-1 text-xs text-accent-cyan hover:text-white">
            <Plus className="h-3.5 w-3.5" /> Add variable
          </button>
        </div>

        <div className="space-y-2">
          {vars.map((variable) => (
            <div key={variable.id} className="flex items-center gap-2">
              <input
                value={variable.name}
                onChange={(e) => update(variable.id, { name: e.target.value })}
                spellCheck={false}
                className="w-[38%] rounded-lg border border-white/10 bg-black/30 px-2.5 py-2 font-mono text-xs text-white/80 outline-none focus:border-accent-blue/50"
                aria-label="Variable name"
              />
              <select
                value={variable.type}
                onChange={(e) => update(variable.id, { type: e.target.value as VarType })}
                className="rounded-lg border border-white/10 bg-black/30 px-2 py-2 text-xs text-white/70 outline-none focus:border-accent-blue/50"
                aria-label="Variable type"
              >
                {(["number", "boolean", "string", "vector", "array"] as VarType[]).map((t) => (
                  <option key={t} value={t} className="bg-ink-900">
                    {t}
                  </option>
                ))}
              </select>
              {variable.type === "boolean" ? (
                <select
                  value={variable.value}
                  onChange={(e) => update(variable.id, { value: e.target.value })}
                  className="flex-1 rounded-lg border border-white/10 bg-black/30 px-2.5 py-2 text-xs text-white/80 outline-none focus:border-accent-blue/50"
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
              <button
                onClick={() => remove(variable.id)}
                className="rounded-lg p-2 text-white/30 hover:bg-white/5 hover:text-fail"
                aria-label="Delete variable"
              >
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

        <button onClick={run} className="btn-accent mt-5 w-full" disabled={running}>
          {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
          {running ? "Validating…" : "Run validation"}
        </button>
      </div>

      {/* Results */}
      <div className="card min-h-[400px] p-5">
        <AnimatePresence mode="wait">
          {!report && !running && (
            <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="flex h-full min-h-[360px] flex-col items-center justify-center text-center">
              <p className="text-sm text-white/40">Configure variables, then run a validation.</p>
              <p className="mt-1 text-xs text-white/25">Runs locally in your browser — no data leaves the page.</p>
            </motion.div>
          )}
          {running && (
            <motion.div key="running" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="flex h-full min-h-[360px] items-center justify-center gap-2 text-sm text-white/50">
              <Loader2 className="h-4 w-4 animate-spin text-accent-cyan" /> Running deterministic checks…
            </motion.div>
          )}
          {report && !running && (
            <motion.div key="report" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
              <ResultsView
                report={report}
                responseJson={responseJson}
                onDownload={downloadReport}
                onCopy={() => {
                  navigator.clipboard.writeText(responseJson);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 1500);
                }}
                copied={copied}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

function ResultsView({
  report,
  responseJson,
  onDownload,
  onCopy,
  copied,
}: {
  report: ValidationReport;
  responseJson: string;
  onDownload: () => void;
  onCopy: () => void;
  copied: boolean;
}) {
  const meta =
    report.status === "passed"
      ? { color: "text-pass", ring: "bg-pass/10 ring-pass/30", Icon: Check, label: "PASS" }
      : report.status === "warning"
        ? { color: "text-warn", ring: "bg-warn/10 ring-warn/30", Icon: AlertTriangle, label: "WARNING" }
        : { color: "text-fail", ring: "bg-fail/10 ring-fail/30", Icon: XCircle, label: "FAIL" };

  return (
    <div className="space-y-4">
      <div className={cn("flex items-center justify-between rounded-xl p-4 ring-1", meta.ring)}>
        <div className="flex items-center gap-3">
          <meta.Icon className={cn("h-6 w-6", meta.color)} />
          <div>
            <p className={cn("text-lg font-semibold", meta.color)}>{meta.label}</p>
            <p className="text-xs text-white/45">
              {report.passed}/{report.checksRun} checks passed · {report.executionMs}ms
            </p>
          </div>
        </div>
        <ScoreRing value={report.score} label="Score" color={report.status === "failed" ? "#f87171" : report.status === "warning" ? "#fbbf24" : "#34d399"} />
      </div>

      {report.violations.length > 0 && (
        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-white/40">
            Detected issues ({report.violations.length})
          </h4>
          <div className="space-y-2">
            {report.violations.map((vi, i) => (
              <div key={i} className="flex items-start gap-2.5 rounded-lg border border-white/[0.05] bg-white/[0.02] p-3">
                {vi.severity === "critical" ? (
                  <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-fail" />
                ) : (
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warn" />
                )}
                <div>
                  <p className="font-mono text-xs text-white/70">{vi.field} = {vi.value}</p>
                  <p className="text-xs text-white/45">{vi.reason}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {report.recommendations.length > 0 && (
        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-white/40">Recommendations</h4>
          <ul className="space-y-1.5">
            {report.recommendations.map((r, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-white/55">
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-accent-cyan" />
                {r}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <div className="mb-2 flex items-center justify-between">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-white/40">JSON response</h4>
          <div className="flex gap-2">
            <button onClick={onCopy} className="flex items-center gap-1 text-xs text-white/45 hover:text-white">
              {copied ? <Check className="h-3.5 w-3.5 text-pass" /> : <Copy className="h-3.5 w-3.5" />}
              {copied ? "Copied" : "Copy"}
            </button>
            <button onClick={onDownload} className="flex items-center gap-1 text-xs text-white/45 hover:text-white">
              <Download className="h-3.5 w-3.5" /> Report
            </button>
          </div>
        </div>
        <div className="max-h-56 overflow-auto rounded-lg border border-white/[0.06] bg-black/30 p-3">
          <JsonView text={responseJson} />
        </div>
      </div>
    </div>
  );
}
