"use client";

import { useRef, useState } from "react";
import { motion } from "framer-motion";
import { Play, Loader2, CheckCircle, AlertTriangle, XCircle, ArrowRight, Code2, Sliders, Upload, Plus, Trash2, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { validateSetup, type SetupResult } from "@/lib/api";
import { parseMeshFile, type ParsedMesh } from "@/lib/mesh-parse";

const DEFAULTS = {
  solver: "openfoam",
  turbulence_model: "kOmegaSST",
  inlet_velocity: 15,
  reynolds_number: 1_000_000,
  domain_length: 10,
  characteristic_length: 1,
  total_cells: 500_000,
  estimated_yplus: 45,
  max_non_orthogonality: 65,
  max_aspect_ratio: 200,
  max_skewness: 0.75,
  discretization_order: 2,
  convergence_tolerance: 1e-5,
  max_cfl: 0.8,
};

function buildConfig(v: typeof DEFAULTS) {
  return {
    solver: v.solver, physics: "fluid", simulation_type: "aerodynamics",
    geometry: { domain_length: v.domain_length, characteristic_length: v.characteristic_length },
    flow_conditions: { inlet_velocity: v.inlet_velocity, reynolds_number: v.reynolds_number, temperature: 293.15, pressure: 101325, density: 1.225 },
    mesh: { total_cells: v.total_cells, estimated_yplus: v.estimated_yplus, max_non_orthogonality: v.max_non_orthogonality, max_aspect_ratio: v.max_aspect_ratio, max_skewness: v.max_skewness, min_cell_quality: 0.3, has_boundary_layers: true, boundary_layer_growth_ratio: 1.2 },
    solver_settings: { turbulence_model: v.turbulence_model, discretization_order: v.discretization_order, convergence_tolerance: v.convergence_tolerance, max_cfl: v.max_cfl, max_iterations: 2000, relaxation_velocity: 0.7, relaxation_pressure: 0.3 },
    boundary_conditions: { inlet: "velocityInlet", outlet: "pressureOutlet", walls: "noSlip" },
  };
}

export function PreflightPanel({ onGotoOutput }: { onGotoOutput?: () => void }) {
  const [mode, setMode] = useState<"form" | "json">("form");
  const [form, setForm] = useState(DEFAULTS);
  const [raw, setRaw] = useState(() => JSON.stringify(buildConfig(DEFAULTS), null, 2));
  const [phase, setPhase] = useState<"idle" | "running" | "done" | "error">("idle");
  const [result, setResult] = useState<SetupResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mesh, setMesh] = useState<ParsedMesh | null>(null);
  const [meshErr, setMeshErr] = useState<string | null>(null);
  const [custom, setCustom] = useState<{ k: string; v: string }[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);

  const set = (k: keyof typeof DEFAULTS, val: string) =>
    setForm((f) => ({ ...f, [k]: k === "solver" || k === "turbulence_model" ? val : Number(val) }));

  async function onFile(file: File) {
    setMeshErr(null); setMesh(null);
    const res = await parseMeshFile(file);
    if ("error" in res) setMeshErr(res.error);
    else setMesh(res);
  }

  async function run() {
    setPhase("running"); setError(null); setResult(null);
    try {
      const config: Record<string, any> = mode === "json" ? JSON.parse(raw) : buildConfig(form);
      // Merge uploaded geometry stats (real watertight / cell-count analysis).
      if (mesh) config.mesh = { ...config.mesh, total_cells: mesh.total_cells, open_edges: mesh.open_edges, duplicate_faces: mesh.duplicate_faces };
      // Merge user-defined custom conditions.
      for (const { k, v } of custom) {
        if (!k.trim()) continue;
        const num = Number(v);
        (config.flow_conditions ??= {})[k.trim()] = Number.isFinite(num) && v.trim() !== "" ? num : v;
      }
      const res = await validateSetup(config, mesh ? { total_cells: mesh.total_cells, open_edges: mesh.open_edges, duplicate_faces: mesh.duplicate_faces } : undefined, config.simulation_type ?? "aerodynamics");
      setResult(res); setPhase("done");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e)); setPhase("error");
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[400px_1fr]">
      {/* ── Controls ── */}
      <div className="space-y-4">
        <div className="rounded-2xl border border-white/[0.08] bg-ink-900/60 p-4">
          <div className="mb-3 flex gap-1">
            {(["form", "json"] as const).map((t) => (
              <button key={t} onClick={() => setMode(t)}
                className={cn("flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
                  mode === t ? "bg-white/10 text-white" : "text-white/45 hover:text-white")}>
                {t === "form" ? <Sliders className="h-3.5 w-3.5" /> : <Code2 className="h-3.5 w-3.5" />}
                {t === "form" ? "Form" : "Config JSON"}
              </button>
            ))}
          </div>

          {mode === "form" ? (
            <div className="space-y-3">
              <Field label="Solver">
                <select value={form.solver} onChange={(e) => set("solver", e.target.value)} className={inputCls}>
                  {["openfoam", "ansys", "comsol", "su2", "abaqus"].map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </Field>
              <Field label="Turbulence model">
                <select value={form.turbulence_model} onChange={(e) => set("turbulence_model", e.target.value)} className={inputCls}>
                  {["kOmegaSST", "kEpsilon", "SpalartAllmaras", "laminar"].map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Inlet velocity (m/s)"><input type="number" value={form.inlet_velocity} onChange={(e) => set("inlet_velocity", e.target.value)} className={inputCls} /></Field>
                <Field label="Reynolds number"><input type="number" value={form.reynolds_number} onChange={(e) => set("reynolds_number", e.target.value)} className={inputCls} /></Field>
                <Field label="Domain length (m)"><input type="number" value={form.domain_length} onChange={(e) => set("domain_length", e.target.value)} className={inputCls} /></Field>
                <Field label="Total cells"><input type="number" value={form.total_cells} onChange={(e) => set("total_cells", e.target.value)} className={inputCls} /></Field>
                <Field label="Estimated y+"><input type="number" value={form.estimated_yplus} onChange={(e) => set("estimated_yplus", e.target.value)} className={inputCls} /></Field>
                <Field label="Max non-ortho (°)"><input type="number" value={form.max_non_orthogonality} onChange={(e) => set("max_non_orthogonality", e.target.value)} className={inputCls} /></Field>
                <Field label="Max aspect ratio"><input type="number" value={form.max_aspect_ratio} onChange={(e) => set("max_aspect_ratio", e.target.value)} className={inputCls} /></Field>
                <Field label="Max skewness"><input type="number" step="0.01" value={form.max_skewness} onChange={(e) => set("max_skewness", e.target.value)} className={inputCls} /></Field>
              </div>
            </div>
          ) : (
            <textarea value={raw} onChange={(e) => setRaw(e.target.value)} rows={18} spellCheck={false}
              className="w-full resize-y rounded-xl border border-white/[0.06] bg-black/20 p-3 font-mono text-xs leading-relaxed text-white/60 outline-none focus:border-accent-blue/40" />
          )}

          {/* Custom conditions (fully variable input parameters) */}
          {mode === "form" && (
            <div className="mt-4">
              <div className="mb-1.5 flex items-center justify-between">
                <label className="text-[11px] text-white/45">Custom parameters</label>
                <button onClick={() => setCustom((c) => [...c, { k: "", v: "" }])} className="flex items-center gap-1 text-[11px] text-accent-cyan hover:text-white">
                  <Plus className="h-3 w-3" /> Add
                </button>
              </div>
              <div className="space-y-1.5">
                {custom.map((row, i) => (
                  <div key={i} className="flex items-center gap-1.5">
                    <input value={row.k} onChange={(e) => setCustom((c) => c.map((x, j) => (j === i ? { ...x, k: e.target.value } : x)))} placeholder="parameter" className={cn(inputCls, "flex-1 font-mono text-xs")} />
                    <input value={row.v} onChange={(e) => setCustom((c) => c.map((x, j) => (j === i ? { ...x, v: e.target.value } : x)))} placeholder="value" className={cn(inputCls, "w-24 font-mono text-xs")} />
                    <button onClick={() => setCustom((c) => c.filter((_, j) => j !== i))} className="rounded-lg p-1.5 text-white/30 hover:text-fail"><Trash2 className="h-3.5 w-3.5" /></button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Geometric mesh upload */}
          <div className="mt-4">
            <label className="mb-1.5 block text-[11px] text-white/45">Geometry (optional)</label>
            <input ref={fileRef} type="file" accept=".stl,.json" className="hidden" onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])} />
            <button onClick={() => fileRef.current?.click()} className="flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-white/15 py-2.5 text-xs text-white/55 hover:border-white/30 hover:text-white">
              <Upload className="h-3.5 w-3.5" /> Upload mesh (.stl) or mesh-stats (.json)
            </button>
            {meshErr && <p className="mt-1.5 text-[11px] text-fail">{meshErr}</p>}
            {mesh && (
              <div className="mt-2 rounded-lg border border-white/[0.06] bg-white/[0.02] p-2.5 text-[11px] text-white/55">
                <div className="flex items-center gap-1.5">
                  {mesh.watertight ? <Check className="h-3.5 w-3.5 text-pass" /> : <XCircle className="h-3.5 w-3.5 text-red-400" />}
                  <span className="font-mono">{mesh.total_cells.toLocaleString()} facets</span>
                  <span className={mesh.watertight ? "text-pass" : "text-red-400"}>· {mesh.watertight ? "watertight" : `${mesh.open_edges} open edges`}</span>
                  {mesh.duplicate_faces > 0 && <span className="text-amber-400">· {mesh.duplicate_faces} dup faces</span>}
                </div>
              </div>
            )}
          </div>

          <button onClick={run} disabled={phase === "running"} className="btn-accent mt-4 flex w-full items-center justify-center gap-2 text-sm">
            {phase === "running" ? <><Loader2 className="h-4 w-4 animate-spin" /> Analyzing setup…</> : <><Play className="h-4 w-4" /> Validate setup</>}
          </button>
        </div>
        <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4 text-xs leading-relaxed text-white/40">
          Pre-flight validates your mesh, boundary conditions, and solver settings <em>before</em> you run — and predicts which output checks are likely to fail.
        </div>
      </div>

      {/* ── Results ── */}
      <div className="space-y-4">
        {phase === "idle" && (
          <div className="flex flex-col items-center justify-center rounded-2xl border border-white/[0.07] bg-ink-900/40 py-40 text-center">
            <p className="text-white/35">Configure your setup and hit Validate</p>
            <p className="mt-1.5 text-xs text-white/20">Mesh quality · BC consistency · solver config · physics models</p>
          </div>
        )}
        {phase === "running" && (
          <div className="flex flex-col items-center justify-center rounded-2xl border border-white/[0.07] bg-ink-900/40 py-40">
            <Loader2 className="mb-4 h-8 w-8 animate-spin text-accent-cyan" />
            <p className="text-sm text-white/50">Running pre-flight checks…</p>
          </div>
        )}
        {phase === "error" && (
          <div className="rounded-2xl border border-red-400/20 bg-red-400/5 p-6 text-sm text-red-400/80">{error}</div>
        )}
        {phase === "done" && result && <PreflightResult r={result} onGotoOutput={onGotoOutput} />}
      </div>
    </div>
  );
}

function PreflightResult({ r, onGotoOutput }: { r: SetupResult; onGotoOutput?: () => void }) {
  const meta = r.status === "ready"
    ? { cls: "bg-pass/10 text-pass border-pass/30", Icon: CheckCircle, label: "READY" }
    : r.status === "warning"
      ? { cls: "bg-amber-400/10 text-amber-400 border-amber-400/30", Icon: AlertTriangle, label: "WARNING" }
      : { cls: "bg-red-400/10 text-red-400 border-red-400/30", Icon: XCircle, label: "NOT READY" };
  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
      <div className="rounded-2xl border border-white/[0.08] bg-ink-900/60 p-5">
        <div className="mb-5 flex items-center justify-between">
          <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold", meta.cls)}>
            <meta.Icon className="h-3.5 w-3.5" /> {meta.label}
          </span>
          <span className="text-xs text-white/30">{Math.round(r.estimated_corruption_risk * 100)}% predicted corruption risk</span>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { l: "Checks", v: String(r.all_checks), c: "text-accent-cyan" },
            { l: "Passed", v: String(r.passed), c: "text-pass" },
            { l: "Issues", v: String(r.warnings + r.failed), c: r.failed ? "text-red-400" : r.warnings ? "text-amber-400" : "text-pass" },
            { l: "Time", v: `${r.processing_ms}ms`, c: "text-pass" },
          ].map((m) => (
            <div key={m.l} className="rounded-xl border border-white/[0.05] bg-white/[0.03] p-3 text-center">
              <p className={cn("font-mono text-xl font-semibold", m.c)}>{m.v}</p>
              <p className="mt-0.5 text-[10px] uppercase tracking-wider text-white/30">{m.l}</p>
            </div>
          ))}
        </div>
      </div>

      {(r.predicted_failures?.length ?? r.predicted_error_types.length) > 0 && (
        <div className="rounded-2xl border border-amber-400/25 bg-amber-400/5 p-5">
          <p className="text-sm font-medium text-amber-300">If you run this simulation, SimAPI predicts these output checks will fail:</p>
          <div className="mt-3 space-y-2">
            {(r.predicted_failures ?? r.predicted_error_types.map((t) => ({ check: t, label: t, why: "", fix: "" }))).map((p) => (
              <div key={p.check} className="rounded-xl border border-amber-400/15 bg-black/20 p-3">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-amber-200">{p.label}</span>
                  <code className="font-mono text-[10px] text-amber-200/40">{p.check}</code>
                </div>
                {p.why && <p className="mt-1.5 text-xs leading-relaxed text-white/55"><span className="text-white/35">Why:</span> {p.why}</p>}
                {p.fix && <p className="mt-1 text-xs leading-relaxed text-white/55"><span className="text-accent-cyan">Fix:</span> {p.fix}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {r.issues.length > 0 && (
        <div className="rounded-2xl border border-white/[0.08] bg-ink-900/60 p-5">
          <p className="mb-3 text-xs uppercase tracking-widest text-white/30">{r.issues.length} issue{r.issues.length !== 1 ? "s" : ""} found</p>
          <div className="space-y-1.5">
            {r.issues.map((i) => (
              <div key={i.name} className={cn("rounded-lg border px-3 py-2.5", i.status === "failed" ? "border-red-400/20 bg-red-400/5" : "border-amber-400/15 bg-amber-400/5")}>
                <div className="flex items-center gap-2.5">
                  <span className={cn("text-sm", i.status === "failed" ? "text-red-400" : "text-amber-400")}>{i.status === "failed" ? "✗" : "⚠"}</span>
                  <span className="flex-1 text-xs font-medium text-white/75">{i.human_name}</span>
                  <span className={cn("rounded border px-1.5 py-0.5 font-mono text-[10px]", i.status === "failed" ? "border-red-400/20 text-red-400/60" : "border-amber-400/20 text-amber-400/60")}>{i.category}</span>
                </div>
                {i.detail && <p className="mt-1 pl-6 text-xs text-white/45">{i.detail}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {r.recommendations.length > 0 && (
        <div className="rounded-2xl border border-white/[0.08] bg-ink-900/60 p-5">
          <p className="mb-3 text-xs uppercase tracking-widest text-white/30">Recommendations</p>
          {r.recommendations.map((rec, i) => (
            <div key={i} className="flex gap-2 text-xs text-white/55"><span className="shrink-0 text-accent-cyan">→</span><span>{rec}</span></div>
          ))}
        </div>
      )}

      <button onClick={onGotoOutput} className="flex items-center gap-1.5 text-sm text-accent-cyan hover:text-white">
        Ran the simulation? Validate the output <ArrowRight className="h-3.5 w-3.5" />
      </button>
    </motion.div>
  );
}

const inputCls = "w-full rounded-lg border border-white/[0.08] bg-black/30 px-3 py-2 text-sm text-white/75 outline-none focus:border-accent-blue/40";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-[11px] text-white/45">{label}</label>
      {children}
    </div>
  );
}
