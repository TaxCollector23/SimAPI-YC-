"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Play, RefreshCw, Loader2, CheckCircle, XCircle,
  AlertTriangle, ChevronDown, ChevronUp, Key, Copy,
  Check, Plus, Trash2, Info, Sparkles, Timer,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { PreflightPanel } from "./preflight-panel";
import { HistoryPanel } from "./history-panel";
import { recordRun } from "@/lib/run-history";
import { useAuth } from "@/lib/auth";
import { touchKey } from "@/lib/dashboard-store";
import {
  validate, runDemo, pollAI, generateKey,
  DEMO_KEY, healthCheck,
  type ValidationResult, type Issue,
} from "@/lib/api";

// ── Simulation type config ────────────────────────────────────────────────────
const SIM_TYPES: { value: string; label: string; conditions: { key: string; label: string; unit: string; default: number }[]; example: object[] }[] = [
  {
    value: "aerodynamics", label: "Aerodynamics",
    conditions: [
      { key: "velocity",    label: "Freestream velocity", unit: "m/s",  default: 15   },
      { key: "altitude",    label: "Altitude",            unit: "m",    default: 120  },
      { key: "mach_number", label: "Mach number",         unit: "",     default: 0.044},
    ],
    example: [
      { cd: 0.312, cl: 0.847, re: 415000, ma: 0.044, p: 101325, v: 15.0 },
      { cd: 0.315, cl: 0.851, re: 418000, ma: 0.044, p: 101800, v: 15.0 },
      { cd: 999.0, cl: 0.848, re: 410000, ma: 0.044, p: 101200, v: 15.0 },
      { cd: 0.308, cl: 0.839, re: 421000, ma: 0.044, p: 100900, v: 15.0 },
      { cd: 0.320, cl: 0.855, re: 409000, ma: 0.043, p: 101500, v: 14.2 },
    ],
  },
  {
    value: "structural", label: "Structural / FEA",
    conditions: [
      { key: "temperature", label: "Operating temperature", unit: "K",  default: 293 },
      { key: "load_factor", label: "Load factor",           unit: "",   default: 1.0 },
    ],
    example: [
      { stress: 245e6, strain: 0.00196, elastic_modulus: 125e9, von_mises_stress: 238e6, yield_stress: 550e6, safety_factor: 2.31, poisson_ratio: 0.29, natural_frequency: 142.3, damping_ratio: 0.043 },
      { stress: 251e6, strain: 0.00201, elastic_modulus: 125e9, von_mises_stress: 244e6, yield_stress: 550e6, safety_factor: 2.25, poisson_ratio: 0.29, natural_frequency: 141.8, damping_ratio: 0.044 },
      { stress: 248e6, strain: 0.00198, elastic_modulus: 125e9, von_mises_stress: 265e6, yield_stress: 550e6, safety_factor: 2.27, poisson_ratio: 0.31, natural_frequency: 142.1, damping_ratio: 0.043 },
      { stress: 244e6, strain: 0.00250, elastic_modulus: 125e9, von_mises_stress: 237e6, yield_stress: 550e6, safety_factor: 2.32, poisson_ratio: 0.29, natural_frequency: 142.4, damping_ratio: 0.043 },
      { stress: 248e6, strain: 0.00198, elastic_modulus: 125e9, von_mises_stress: 241e6, yield_stress: 550e6, safety_factor: 2.27, poisson_ratio: 0.29, stress_concentration: 0.85, natural_frequency: 142.1 },
    ],
  },
  {
    value: "thermodynamics", label: "Thermodynamics",
    conditions: [
      { key: "hot_temperature",  label: "Hot reservoir T",  unit: "K", default: 800 },
      { key: "cold_temperature", label: "Cold reservoir T", unit: "K", default: 300 },
    ],
    example: [
      { temperature: 800, heat_flux: 10200, thermal_efficiency: 0.35, carnot_efficiency: 0.625, nusselt_number: 148, prandtl_number: 0.71, emissivity: 0.85 },
      { temperature: 810, heat_flux: 10400, thermal_efficiency: 0.36, carnot_efficiency: 0.625, nusselt_number: 152, prandtl_number: 0.71, emissivity: 0.85 },
      { temperature: 790, heat_flux: 9800,  thermal_efficiency: 0.34, carnot_efficiency: 0.625, nusselt_number: 144, prandtl_number: 0.71, emissivity: 0.85 },
      { temperature: 820, heat_flux: 0,     thermal_efficiency: 1.1,  carnot_efficiency: 0.625, nusselt_number: 156, prandtl_number: 0.71, emissivity: 0.85 },
    ],
  },
  {
    value: "robotics", label: "Robotics / Control",
    conditions: [
      { key: "payload",   label: "Payload mass",  unit: "kg",  default: 5  },
      { key: "velocity",  label: "Max EE speed",  unit: "m/s", default: 1  },
    ],
    example: [
      { joint_torque: 48.2, joint_velocity: 1.52, power_consumption: 73.3, settling_time: 0.82, rise_time: 0.31, overshoot: 0.14, manipulability: 2.4, damping_ratio: 0.65 },
      { joint_torque: 51.8, joint_velocity: 1.48, power_consumption: 76.7, settling_time: 0.79, rise_time: 0.29, overshoot: 0.18, manipulability: 2.6, damping_ratio: 0.68 },
      { joint_torque: 49.5, joint_velocity: 1.55, power_consumption: 74.8, settling_time: 0.85, rise_time: 0.32, overshoot: 0.12, manipulability: 2.3, damping_ratio: 0.62 },
    ],
  },
  {
    value: "fluid_dynamics", label: "Fluid Dynamics / CFD",
    conditions: [
      { key: "velocity",      label: "Inlet velocity",  unit: "m/s",  default: 10  },
      { key: "density",       label: "Fluid density",   unit: "kg/m³", default: 1.225 },
      { key: "length_scale",  label: "Length scale",    unit: "m",    default: 0.5 },
    ],
    example: [
      { velocity: 10.2, pressure: 101400, density: 1.224, reynolds_number: 340000, turbulent_kinetic_energy: 0.12, turbulent_dissipation: 0.045, wall_shear_stress: 0.23 },
      { velocity: 9.8,  pressure: 101300, density: 1.226, reynolds_number: 326000, turbulent_kinetic_energy: 0.11, turbulent_dissipation: 0.042, wall_shear_stress: 0.21 },
      { velocity: 10.5, pressure: 101500, density: 1.223, reynolds_number: 350000, turbulent_kinetic_energy: -0.05, turbulent_dissipation: 0.048, wall_shear_stress: 0.25 },
    ],
  },
  {
    value: "combustion", label: "Combustion",
    conditions: [
      { key: "pressure",    label: "Chamber pressure", unit: "Pa",  default: 506625 },
      { key: "temperature", label: "Inlet temp",       unit: "K",   default: 400    },
    ],
    example: [
      { temperature: 2200, pressure: 506625, equivalence_ratio: 1.0, heat_release_rate: 1.1e6, co2_concentration: 0.12, co_concentration: 0.02, nox_concentration: 0.0012, combustion_efficiency: 0.98, flame_temperature: 2250 },
      { temperature: 2180, pressure: 506500, equivalence_ratio: 0.98, heat_release_rate: 1.05e6, co2_concentration: 0.115, co_concentration: 0.018, nox_concentration: 0.0010, combustion_efficiency: 0.97, flame_temperature: 2230 },
      { temperature: 2210, pressure: 506700, equivalence_ratio: 5.0, heat_release_rate: 9e5, co2_concentration: 0.09, co_concentration: 0.08, nox_concentration: 0.0008, combustion_efficiency: 0.88, flame_temperature: 2190 },
    ],
  },
  {
    value: "materials", label: "Materials Science",
    conditions: [
      { key: "temperature", label: "Test temperature", unit: "K",   default: 293 },
    ],
    example: [
      { yield_strength: 420e6, tensile_strength: 550e6, elastic_modulus: 200e9, poisson_ratio: 0.30, hardness: 180, fracture_toughness: 50e6, grain_size: 0.02, thermal_conductivity: 50, thermal_expansion: 12e-6 },
      { yield_strength: 415e6, tensile_strength: 545e6, elastic_modulus: 200e9, poisson_ratio: 0.30, hardness: 178, fracture_toughness: 49e6, grain_size: 0.021, thermal_conductivity: 50, thermal_expansion: 12e-6 },
      { yield_strength: 600e6, tensile_strength: 400e6, elastic_modulus: 200e9, poisson_ratio: 0.30, hardness: 195, fracture_toughness: 52e6, grain_size: 0.015, thermal_conductivity: 50, thermal_expansion: 12e-6 },
    ],
  },
  { value: "acoustics",        label: "Acoustics",        conditions: [{ key: "frequency", label: "Center frequency", unit: "Hz",  default: 1000 }], example: [] },
  { value: "electromagnetics", label: "Electromagnetics",  conditions: [{ key: "frequency", label: "Frequency",        unit: "Hz",  default: 1e9  }], example: [] },
  { value: "geomechanics",     label: "Geomechanics",      conditions: [{ key: "depth",     label: "Depth below surface", unit: "m", default: 10 }], example: [] },
  { value: "biomechanics",     label: "Biomechanics",      conditions: [{ key: "body_mass", label: "Subject mass",    unit: "kg",  default: 70   }], example: [] },
  { value: "nuclear",          label: "Nuclear",           conditions: [{ key: "power",     label: "Reactor power",  unit: "MW",  default: 1000 }], example: [] },
  { value: "plasma",           label: "Plasma Physics",    conditions: [{ key: "magnetic_field", label: "B field", unit: "T",    default: 5    }], example: [] },
  { value: "chemical",         label: "Chemical Reactor",  conditions: [{ key: "temperature", label: "Reactor T",  unit: "K",    default: 350  }, { key: "pressure", label: "Pressure", unit: "Pa", default: 101325 }], example: [] },
  { value: "hydrodynamics",    label: "Hydrodynamics",     conditions: [{ key: "water_depth", label: "Water depth", unit: "m",   default: 100  }], example: [] },
  { value: "meteorology",      label: "Meteorology",       conditions: [{ key: "altitude",  label: "Altitude",      unit: "m",   default: 0    }], example: [] },
  { value: "tribology",        label: "Tribology",         conditions: [{ key: "load",      label: "Normal load",   unit: "N",   default: 100  }, { key: "sliding_speed", label: "Sliding speed", unit: "m/s", default: 1 }], example: [] },
  { value: "aeroelasticity",   label: "Aeroelasticity",    conditions: [{ key: "velocity",  label: "Flight speed",  unit: "m/s", default: 100  }], example: [] },
  { value: "cryogenics",       label: "Cryogenics",        conditions: [{ key: "temperature", label: "Operating T", unit: "K",   default: 4.2  }], example: [] },
];

function fmtN(n: number | null | undefined): string {
  if (n == null) return "—";
  if (Math.abs(n) >= 1e6 || (Math.abs(n) < 0.001 && n !== 0)) return n.toExponential(3);
  return Number.isInteger(n) ? n.toLocaleString() : n.toFixed(4);
}

function StatusPill({ status }: { status: string }) {
  const map: Record<string, { cls: string; icon: React.ReactNode; label: string }> = {
    passed:  { cls: "bg-pass/10 text-pass border-pass/30",                   icon: <CheckCircle   className="h-3.5 w-3.5" />, label: "PASSED"  },
    warning: { cls: "bg-amber-400/10 text-amber-400 border-amber-400/30",    icon: <AlertTriangle className="h-3.5 w-3.5" />, label: "WARNING" },
    failed:  { cls: "bg-red-400/10 text-red-400 border-red-400/30",          icon: <XCircle       className="h-3.5 w-3.5" />, label: "FAILED"  },
  };
  const m = map[status] ?? map.warning;
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold", m.cls)}>
      {m.icon} {m.label}
    </span>
  );
}

function IssueRow({ issue }: { issue: Issue & { human_name?: string } }) {
  const [expanded, setExpanded] = useState(false);
  const fail = issue.status === "failed";
  const name = (issue as { human_name?: string }).human_name || issue.description || issue.name;
  return (
    <div
      className={cn("rounded-lg border cursor-pointer transition-colors", fail
        ? "border-red-400/20 bg-red-400/5 hover:border-red-400/40"
        : "border-amber-400/15 bg-amber-400/5 hover:border-amber-400/35")}
      onClick={() => setExpanded(v => !v)}
    >
      <div className="flex items-center gap-3 px-3 py-2.5">
        <span className={cn("text-sm shrink-0", fail ? "text-red-400" : "text-amber-400")}>
          {fail ? "✗" : "⚠"}
        </span>
        <span className="flex-1 text-xs text-white/75 font-medium leading-snug">{name}</span>
        <span className={cn("text-[10px] shrink-0 rounded px-1.5 py-0.5 border font-mono",
          fail ? "border-red-400/20 text-red-400/60" : "border-amber-400/20 text-amber-400/60")}>
          {issue.category}
        </span>
        {expanded ? <ChevronUp className="h-3 w-3 text-white/20 shrink-0" /> : <ChevronDown className="h-3 w-3 text-white/20 shrink-0" />}
      </div>
      {expanded && (
        <div className="border-t border-white/[0.06] px-3 py-2.5 text-xs text-white/45 leading-relaxed">
          {issue.detail}
          {issue.value !== null && issue.value !== undefined && (
            <span className="ml-2 font-mono text-white/30">value: {fmtN(issue.value)}</span>
          )}
        </div>
      )}
    </div>
  );
}

/** Time-based progress bar for the AI quick check (~2-18s budget). Not tied to
 * a real byte count — there's nothing to stream — but gives useful feedback
 * that the check is progressing rather than hung. Caps at 92% until the
 * result actually arrives, so it never falsely implies completion. */
function AiProgressBar({ budgetMs = 18000 }: { budgetMs?: number }) {
  const [pct, setPct] = useState(0);
  useEffect(() => {
    const start = Date.now();
    const t = setInterval(() => {
      setPct(Math.min(92, Math.round(((Date.now() - start) / budgetMs) * 100)));
    }, 200);
    return () => clearInterval(t);
  }, [budgetMs]);
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/[0.06]">
      <div
        className="h-full rounded-full bg-purple-400/70 transition-[width] duration-200 ease-linear"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export function ValidationDashboard() {
  const { user } = useAuth();
  const simConfig  = SIM_TYPES[0];
  const [selectedSim, setSelectedSim] = useState(simConfig);
  const [conditions, setConditions]   = useState<Record<string, number>>(
    Object.fromEntries(simConfig.conditions.map(c => [c.key, c.default]))
  );
  const [rawInput,  setRawInput]    = useState(JSON.stringify(simConfig.example, null, 2));
  const [apiKey,    setApiKey]      = useState(DEMO_KEY);
  const [phase,     setPhase]       = useState<"idle"|"running"|"done"|"error">("idle");
  const [result,    setResult]      = useState<ValidationResult | null>(null);
  const [error,     setError]       = useState<string | null>(null);
  const [serverUp,  setServerUp]    = useState<boolean | null>(null);
  const [showAll,   setShowAll]     = useState(false);
  const [showStats, setShowStats]   = useState(false);
  const [aiPoll,    setAiPoll]      = useState(false);
  const [keyGen,    setKeyGen]      = useState(false);
  const [copied,    setCopied]      = useState(false);
  const [tab,       setTab]         = useState<"preflight"|"output"|"history">("output");
  const pollRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    healthCheck().then(setServerUp);
    const t = setInterval(() => healthCheck().then(setServerUp), 6000);
    return () => { clearInterval(t); if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  function stopPoll() {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    setAiPoll(false);
  }

  function startPoll(jobId: string) {
    setAiPoll(true);
    pollRef.current = setInterval(async () => {
      try {
        const d = await pollAI(jobId);
        if (!d.ai_running) {
          stopPoll();
          if (d.ai) {
            setResult(prev => prev ? {
              ...prev,
              ai: d.ai,
              ai_status: d.ai_status,
              ai_exclusions: d.ai_exclusions ?? prev.ai_exclusions,
              exclusions: d.exclusions ?? prev.exclusions,
              trials_excluded: d.trials_excluded ?? prev.trials_excluded,
              trials_valid: d.trials_valid ?? prev.trials_valid,
              exclusion_rate: d.exclusion_rate ?? prev.exclusion_rate,
              status: d.status ?? prev.status,
              training_ready: d.training_ready ?? prev.training_ready,
            } : prev);
          }
        }
      } catch { stopPoll(); }
    }, 1500);
  }

  function changeSim(value: string) {
    const cfg = SIM_TYPES.find(s => s.value === value) ?? SIM_TYPES[0];
    setSelectedSim(cfg);
    setConditions(Object.fromEntries(cfg.conditions.map(c => [c.key, c.default])));
    if (cfg.example.length > 0) setRawInput(JSON.stringify(cfg.example, null, 2));
    setPhase("idle"); setResult(null);
  }

  async function run(demo = false) {
    if (!serverUp) { setError("API server offline. Run: python launch.py"); return; }
    stopPoll(); setPhase("running"); setError(null); setResult(null); setShowAll(false);
    try {
      let res: ValidationResult;
      if (demo) {
        res = await runDemo();
      } else {
        let data: Record<string, unknown>[];
        try { data = JSON.parse(rawInput); }
        catch { throw new Error("Invalid JSON. Check your input above."); }
        if (!Array.isArray(data)) throw new Error("Input must be a JSON array: [{...}, {...}, ...]");
        res = await validate({ data, simulation_type: selectedSim.value, conditions, run_ai: true }, apiKey);
      }
      setResult(res); setPhase("done");
      recordRun({
        simulationType: selectedSim.value, status: res.status,
        engine: (res as { engine?: string }).engine ?? "unknown",
        executionMs: res.processing_ms ?? 0,
        trials_submitted: res.trials_submitted, trials_excluded: res.trials_excluded,
        unique_checks: (res as { unique_checks?: number }).unique_checks ?? res.all_checks,
        issues: (res.issues ?? []).map((i) => ({ name: i.name, human_name: i.human_name ?? i.name, status: i.status })),
        raw: res,
      });
      if (user && apiKey !== DEMO_KEY) touchKey(user.uid);
      if (res.job_id) startPoll(res.job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setPhase("error");
    }
  }

  async function genKey() {
    setKeyGen(true);
    try { const k = await generateKey("My Key"); setApiKey(k.api_key); }
    catch { setError("Could not generate key — is the API server running?"); }
    finally { setKeyGen(false); }
  }

  const issues = result?.issues ?? [];
  const visible = showAll ? issues : issues.slice(0, 8);

  return (
    <div>

      {/* Top bar */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-white/[0.06] bg-ink-900/50 px-5 py-3">
        <div>
          <h1 className="text-base font-semibold text-white">Simulation Validator</h1>
          <p className="text-xs text-white/35">Paste data · Configure · Run physics checks + AI analysis</p>
        </div>
        <div className="flex items-center gap-2">
          <span className={cn("flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs",
            serverUp === null   ? "border-white/10 text-white/30" :
            serverUp            ? "border-pass/30 bg-pass/5 text-pass" :
                                  "border-red-400/30 bg-red-400/5 text-red-400")}>
            <span className={cn("h-1.5 w-1.5 rounded-full",
              serverUp ? "bg-pass animate-pulse" : serverUp === false ? "bg-red-400" : "bg-white/20")} />
            {serverUp === null ? "Checking..." : serverUp ? "API online" : "API offline"}
          </span>
          {result && "engine" in result && (
            <span className="rounded-full border border-accent-cyan/30 bg-accent-cyan/5 px-2.5 py-1.5 text-[10px] text-accent-cyan">
              {String((result as Record<string, unknown>).engine) === "python-1300-checks" ? "Full engine (1300+ checks)" : "Lite engine (20 checks)"}
            </span>
          )}
        </div>
      </div>

      {/* Pre-flight / Output tab switcher */}
      <div className="mb-6 flex gap-1 rounded-xl border border-white/[0.06] bg-ink-900/40 p-1">
        {([["preflight", "Pre-flight"], ["output", "Output validation"], ["history", "History / Compare"]] as const).map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)}
            className={cn("flex-1 rounded-lg px-4 py-2 text-sm font-medium transition-colors",
              tab === id ? "bg-white/10 text-white" : "text-white/45 hover:text-white")}>
            {label}
          </button>
        ))}
      </div>

      {tab === "preflight" ? (
        <PreflightPanel onGotoOutput={() => setTab("output")} />
      ) : tab === "history" ? (
        <HistoryPanel />
      ) : (
      <div className="grid gap-6 lg:grid-cols-[400px_1fr]">

        {/* ── LEFT: Controls ── */}
        <div className="space-y-4">

          {/* Simulation type */}
          <div className="rounded-2xl border border-white/[0.08] bg-ink-900/60 p-4">
            <label className="text-xs uppercase tracking-widest text-white/35 block mb-2">Simulation Type</label>
            <select
              value={selectedSim.value}
              onChange={e => changeSim(e.target.value)}
              className="w-full bg-black/30 border border-white/[0.08] rounded-xl px-3 py-2.5 text-sm text-white/75 outline-none focus:border-accent-blue/50 transition-colors"
            >
              {SIM_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>

          {/* Dynamic conditions */}
          {selectedSim.conditions.length > 0 && (
            <div className="rounded-2xl border border-white/[0.08] bg-ink-900/60 p-4">
              <label className="text-xs uppercase tracking-widest text-white/35 block mb-3">
                Simulation Conditions
              </label>
              <div className="space-y-2.5">
                {selectedSim.conditions.map(c => (
                  <div key={c.key}>
                    <div className="flex items-center justify-between mb-1">
                      <label className="text-xs text-white/50">{c.label}</label>
                      {c.unit && <span className="text-[10px] text-white/25 font-mono">{c.unit}</span>}
                    </div>
                    <input
                      type="number"
                      value={conditions[c.key] ?? c.default}
                      onChange={e => setConditions(prev => ({ ...prev, [c.key]: parseFloat(e.target.value) || c.default }))}
                      className="w-full bg-black/30 border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-white/70 outline-none focus:border-accent-blue/40 transition-colors"
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* API key */}
          <div className="rounded-2xl border border-white/[0.08] bg-ink-900/60 p-4">
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs uppercase tracking-widest text-white/35 flex items-center gap-1.5">
                <Key className="h-3 w-3" /> API Key
              </label>
              <button onClick={genKey} disabled={keyGen}
                className="text-xs text-accent-cyan hover:text-white transition-colors flex items-center gap-1">
                {keyGen ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
                Generate new
              </button>
            </div>
            <div className="flex items-center gap-2">
              <code className="flex-1 truncate rounded-lg bg-black/30 border border-white/[0.06] px-3 py-2 font-mono text-xs text-white/55">
                {apiKey}
              </code>
              <button onClick={() => { navigator.clipboard.writeText(apiKey); setCopied(true); setTimeout(()=>setCopied(false),1800); }}
                className="shrink-0 rounded-lg border border-white/10 p-2 text-white/35 hover:text-white transition-colors">
                {copied ? <Check className="h-3.5 w-3.5 text-pass" /> : <Copy className="h-3.5 w-3.5" />}
              </button>
            </div>
            <p className="mt-1.5 text-[10px] text-white/20">
              {apiKey === DEMO_KEY ? "Shared demo key · Click Generate for a permanent key" : "Your key · active now"}
            </p>
          </div>

          {/* Data input */}
          <div className="rounded-2xl border border-white/[0.08] bg-ink-900/60 p-4">
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs uppercase tracking-widest text-white/35">Data (JSON array)</label>
              <span className="text-[10px] text-white/20">Cd, cd, drag_coefficient — all recognized</span>
            </div>
            <textarea
              value={rawInput}
              onChange={e => setRawInput(e.target.value)}
              rows={14}
              className="w-full bg-black/20 border border-white/[0.06] rounded-xl p-3 font-mono text-xs text-white/60 leading-relaxed resize-y outline-none focus:border-accent-blue/40 transition-colors"
              placeholder={`[\n  {"cd": 0.312, "cl": 0.847, "re": 415000},\n  ...\n]`}
              spellCheck={false}
            />
            <p className="mt-2 text-[10px] text-white/25">
              Each object is one simulation trial. Column names are auto-normalized.
            </p>
          </div>

          {/* Run buttons */}
          <div className="space-y-2">
            <button onClick={() => run(false)} disabled={phase === "running"}
              className="btn-accent w-full flex items-center justify-center gap-2 text-sm">
              {phase === "running"
                ? <><Loader2 className="h-4 w-4 animate-spin" /> Running validation...</>
                : <><Play className="h-4 w-4" /> Run Validation</>}
            </button>
            <button onClick={() => run(true)} disabled={phase === "running"}
              className="btn-ghost w-full flex items-center justify-center gap-2 text-sm">
              <RefreshCw className="h-4 w-4" />
              Load demo dataset (200 trials, 5 corruption types)
            </button>
          </div>

          {/* Info box */}
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4 flex gap-3">
            <Info className="h-4 w-4 text-accent-cyan shrink-0 mt-0.5" />
            <div className="text-xs text-white/35 leading-relaxed space-y-1">
              <p>Physics checks run instantly (~300ms). AI analysis follows in the background and appears automatically.</p>
              <p>All column names are normalized — send <code className="font-mono text-white/50">Cd</code>, <code className="font-mono text-white/50">cd</code>, or <code className="font-mono text-white/50">drag_coefficient</code>.</p>
            </div>
          </div>
        </div>

        {/* ── RIGHT: Results ── */}
        <div className="space-y-4">

          {/* Idle */}
          {phase === "idle" && (
            <div className="rounded-2xl border border-white/[0.07] bg-ink-900/40 flex flex-col items-center justify-center py-40 text-center">
              <div className="h-16 w-16 rounded-full border border-white/[0.08] bg-white/[0.03] flex items-center justify-center mb-4">
                <Play className="h-7 w-7 text-white/15" />
              </div>
              <p className="text-white/35">Configure your simulation and hit Run</p>
              <p className="text-xs text-white/20 mt-1.5">500+ physics checks · AI reasoning · results in seconds</p>
            </div>
          )}

          {/* Running */}
          {phase === "running" && (
            <div className="rounded-2xl border border-white/[0.07] bg-ink-900/40 flex flex-col items-center justify-center py-40">
              <Loader2 className="h-8 w-8 animate-spin text-accent-cyan mb-4" />
              <p className="text-white/50 text-sm">Running physics validation...</p>
              <p className="text-xs text-white/25 mt-1">AI analysis will appear automatically after</p>
            </div>
          )}

          {/* Error */}
          {phase === "error" && (
            <div className="rounded-2xl border border-red-400/20 bg-red-400/5 p-6 space-y-3">
              <p className="font-medium text-red-400">Validation failed</p>
              <p className="text-sm text-red-400/70">{error}</p>
              {error?.includes("offline") && (
                <code className="block bg-black/30 rounded-lg px-4 py-3 font-mono text-xs text-white/50">python launch.py</code>
              )}
            </div>
          )}

          <AnimatePresence>
            {phase === "done" && result && (
              <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">

                {/* Summary header */}
                <div className="rounded-2xl border border-white/[0.08] bg-ink-900/60 p-5">
                  <div className="flex items-center justify-between mb-5">
                    <StatusPill status={result.status} />
                    <div className="flex items-center gap-3 text-xs text-white/30">
                      <span className="font-mono">{result.job_id}</span>
                      <span>·</span>
                      <span className="capitalize">{result.confidence} confidence</span>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    {[
                      { l: "Unique checks", v: String(result.unique_checks ?? result.all_checks), c: "text-accent-cyan" },
                      { l: "Valid trials",  v: `${result.trials_valid} / ${result.trials_submitted}`, c: "text-white" },
                      { l: "Issues",        v: String(result.warnings + result.failed), c: result.failed > 0 ? "text-red-400" : result.warnings > 0 ? "text-amber-400" : "text-pass" },
                      { l: "Time",          v: `${result.processing_ms}ms`, c: "text-pass" },
                    ].map(m => (
                      <div key={m.l} className="rounded-xl bg-white/[0.03] border border-white/[0.05] p-3 text-center">
                        <p className={cn("font-mono text-xl font-semibold", m.c)}>{m.v}</p>
                        <p className="text-[10px] text-white/30 mt-0.5 uppercase tracking-wider">{m.l}</p>
                      </div>
                    ))}
                  </div>

                  <div className={cn("mt-4 rounded-xl border px-4 py-3 text-xs",
                    result.training_ready
                      ? "border-pass/25 bg-pass/5 text-pass"
                      : "border-red-400/25 bg-red-400/5 text-red-400")}>
                    <div className="flex items-center gap-2 font-medium">
                      {result.training_ready
                        ? <><CheckCircle className="h-3.5 w-3.5" /> Training ready — {result.trials_valid} validated trials available for ML pipeline</>
                        : <><XCircle className="h-3.5 w-3.5" /> Not training ready — {result.trials_excluded} trials excluded, review issues below</>}
                    </div>
                    <p className="mt-2 leading-relaxed text-white/45">
                      {result.trials_excluded > 0
                        ? <>SimAPI excluded {result.trials_excluded} anomalous trial{result.trials_excluded !== 1 ? "s" : ""} (e.g. diverged runs like <code className="font-mono text-white/60">cd=999</code>, unit-error rows, sensor drift, duplicates). Training a surrogate model on these injects mislabeled targets and out-of-distribution inputs — they bias predictions and destabilize convergence. Excluding them means your model learns only from physically valid data, which is why {result.status !== "failed" ? "the remaining set is training-ready" : "the set needs cleanup first"}.</>
                        : <>Every trial passed the physics checks, so the full dataset is safe to train on — no anomalies to exclude.</>}
                    </p>
                  </div>
                </div>

                {/* Check bar */}
                <div className="rounded-2xl border border-white/[0.08] bg-ink-900/60 p-5">
                  <p className="text-xs uppercase tracking-widest text-white/30 mb-4">
                    {result.unique_checks ?? "—"} core rules validated across {result.trials_submitted.toLocaleString()} trials — only issues shown below
                  </p>
                  {[
                    { label: "Passed",   n: result.passed,   color: "bg-pass",      text: "text-pass" },
                    { label: "Warnings", n: result.warnings, color: "bg-amber-400", text: "text-amber-400" },
                    { label: "Failed",   n: result.failed,   color: "bg-red-400",   text: "text-red-400" },
                  ].map(r => (
                    <div key={r.label} className="flex items-center gap-3 mb-2.5">
                      <span className={cn("text-xs w-16", r.text)}>{r.label}</span>
                      <div className="flex-1 h-2 rounded-full bg-white/[0.05] overflow-hidden">
                        <div className={cn("h-full rounded-full transition-all duration-700", r.color)}
                          style={{ width: `${Math.round(r.n / result.all_checks * 100)}%` }} />
                      </div>
                      <span className={cn("font-mono text-xs w-8 text-right", r.text)}>{r.n}</span>
                    </div>
                  ))}
                </div>

                {/* Column renames */}
                {Object.keys(result.columns_renamed ?? {}).length > 0 && (
                  <div className="rounded-2xl border border-amber-400/20 bg-amber-400/5 p-4">
                    <p className="text-xs font-medium text-amber-400 mb-2">
                      Column names auto-normalized — {Object.keys(result.columns_renamed).length} renamed
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(result.columns_renamed).map(([from, to]) => (
                        <span key={from} className="font-mono text-[10px] bg-black/20 rounded px-2 py-1 text-white/45">
                          {from} → {to}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Issues — plain English, expandable */}
                <div className="rounded-2xl border border-white/[0.08] bg-ink-900/60 p-5">
                  <p className="text-xs uppercase tracking-widest text-white/30 mb-3">
                    {issues.length === 0
                      ? `All ${result.unique_checks ?? ""} core rules passed across ${result.trials_submitted} trials`
                      : `${issues.length} issue${issues.length !== 1 ? "s" : ""} found — click to expand`}
                  </p>
                  {issues.length === 0 ? (
                    <div className="rounded-xl border border-pass/20 bg-pass/5 px-4 py-3 text-xs text-pass">
                      ✓ Simulation data is physically valid — all checks passed
                    </div>
                  ) : (
                    <>
                      <div className="space-y-1.5">
                        {visible.map(i => <IssueRow key={i.name} issue={i as Issue & { human_name?: string }} />)}
                      </div>
                      {issues.length > 8 && (
                        <button onClick={() => setShowAll(v => !v)}
                          className="mt-3 flex items-center gap-1.5 text-xs text-white/30 hover:text-white transition-colors">
                          {showAll
                            ? <><ChevronUp className="h-3 w-3" /> Show fewer</>
                            : <><ChevronDown className="h-3 w-3" /> Show {issues.length - 8} more issues</>}
                        </button>
                      )}
                    </>
                  )}
                </div>

                {/* Excluded trials — 1-indexed. Physics exclusions are rule-based (no false
                    positives); AI exclusions are reasoning-based (higher recall, clearly labeled). */}
                {result.exclusions.length > 0 && (
                  <div className="rounded-2xl border border-white/[0.08] bg-ink-900/60 p-5">
                    <p className="text-xs uppercase tracking-widest text-white/30 mb-3">
                      {result.exclusions.length} trial{result.exclusions.length !== 1 ? "s" : ""} excluded from ML pipeline
                    </p>
                    <div className="space-y-1.5">
                      {result.exclusions.slice(0, 8).map((e, i) => {
                        const trialIndex = (e as { trial_index?: number }).trial_index ?? -1;
                        const trialNum = (e as { trial_number?: number }).trial_number ?? trialIndex + 1;
                        const isAiFlagged = (result.ai_exclusions ?? []).includes(trialIndex);
                        return (
                          <div key={i} className={cn(
                            "rounded-lg border px-3 py-2 text-xs flex items-start gap-2",
                            isAiFlagged ? "border-purple-400/15 bg-purple-400/[0.04]" : "border-white/[0.06] bg-white/[0.02]",
                          )}>
                            <span className={cn("font-mono shrink-0", isAiFlagged ? "text-purple-400" : "text-red-400")}>
                              Trial {trialNum}
                            </span>
                            <span className="text-white/40 flex-1">{(e as { reason?: string }).reason}</span>
                            {isAiFlagged && (
                              <span className="text-[10px] text-purple-400/60 shrink-0 flex items-center gap-1">
                                <Sparkles className="h-2.5 w-2.5" /> AI
                              </span>
                            )}
                          </div>
                        );
                      })}
                      {result.exclusions.length > 8 && (
                        <p className="text-xs text-white/20 pl-1">+{result.exclusions.length - 8} more</p>
                      )}
                    </div>
                  </div>
                )}

                {/* AI section */}
                <div className="rounded-2xl border border-purple-400/25 bg-purple-400/5 p-5">
                  <div className="flex items-center justify-between mb-4">
                    <p className="text-sm font-medium text-purple-400 flex items-center gap-2">
                      <Sparkles className="h-4 w-4" /> AI Check
                    </p>
                    {result.ai && <span className="text-xs text-white/30 font-mono">{result.ai.processing_ms}ms · {result.ai.model?.split("/").pop()}</span>}
                  </div>

                  {(!result.ai || result.ai_status === "pending") && aiPoll && (
                    <div className="space-y-2">
                      <div className="flex items-center gap-2 text-xs text-purple-400/70">
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        Checking whether this dataset looks normal…
                      </div>
                      <AiProgressBar />
                    </div>
                  )}

                  {result.ai?.verdict && result.ai.status !== "error" && (
                    <div className={cn(
                      "mb-4 flex items-center gap-2 rounded-xl px-4 py-3 text-lg font-semibold",
                      result.ai.verdict === "Normal" ? "bg-pass/10 text-pass" : "bg-amber-400/10 text-amber-400",
                    )}>
                      {result.ai.verdict === "Normal" ? <CheckCircle className="h-5 w-5" /> : <AlertTriangle className="h-5 w-5" />}
                      {result.ai.verdict}
                    </div>
                  )}

                  {result.ai && result.ai.status !== "error" && (
                    <div className="space-y-4">
                      {/* Anomaly score */}
                      <div className="flex items-center gap-3 bg-white/[0.03] rounded-xl p-3">
                        <div className="flex-1">
                          <p className="text-[10px] text-white/30 mb-1.5 uppercase tracking-widest">AI Anomaly Score</p>
                          <div className="h-2 rounded-full bg-white/[0.06] overflow-hidden">
                            <div className="h-full rounded-full transition-all duration-700"
                              style={{
                                width: `${Math.round((result.ai.anomaly_score ?? 0) * 100)}%`,
                                background: (result.ai.anomaly_score ?? 0) < 0.2 ? "#00e676" : (result.ai.anomaly_score ?? 0) < 0.5 ? "#fbbf24" : "#f87171",
                              }} />
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="font-mono text-2xl font-semibold text-white">
                            {Math.round((result.ai.anomaly_score ?? 0) * 100)}%
                          </p>
                          <p className="text-[10px] text-white/30">anomaly</p>
                        </div>
                      </div>

                      {/* Overall assessment */}
                      {result.ai.dataset_summary && (
                        <div className="bg-white/[0.03] rounded-xl p-4 border border-purple-400/10">
                          <p className="text-[10px] uppercase tracking-widest text-purple-400/60 mb-2">Expert Assessment</p>
                          <p className="text-sm text-white/60 leading-relaxed">{result.ai.dataset_summary}</p>
                        </div>
                      )}

                      {/* Corruption probability distribution — only present when the full orchestrator ran */}
                      {result.ai.corruption_probability && Object.keys(result.ai.corruption_probability).length > 0 && (
                        <div className="bg-white/[0.03] rounded-xl p-4 border border-purple-400/10">
                          <p className="text-[10px] uppercase tracking-widest text-purple-400/60 mb-3">Corruption probability distribution</p>
                          <div className="space-y-2">
                            {Object.entries(result.ai.corruption_probability)
                              .sort(([, a], [, b]) => b - a)
                              .map(([label, prob]) => (
                                <div key={label}>
                                  <div className="flex items-center justify-between text-xs text-white/50 mb-1">
                                    <span className="capitalize">{label.replace(/_/g, " ")}</span>
                                    <span className="font-mono">{Math.round(prob * 100)}%</span>
                                  </div>
                                  <div className="h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                                    <div
                                      className="h-full rounded-full bg-purple-400/70"
                                      style={{ width: `${Math.round(prob * 100)}%` }}
                                    />
                                  </div>
                                </div>
                              ))}
                          </div>
                        </div>
                      )}

                      {/* What only AI can see — the most compelling demonstration of value */}
                      {result.ai.what_only_ai_sees && (
                        <div className="rounded-xl border border-purple-400/25 bg-purple-400/[0.08] p-4">
                          <p className="text-[10px] uppercase tracking-widest text-purple-400 mb-2 flex items-center gap-1.5">
                            <Sparkles className="h-3 w-3" /> What only AI can see
                          </p>
                          <p className="text-sm text-white/70 leading-relaxed">{result.ai.what_only_ai_sees}</p>
                        </div>
                      )}

                      {/* Root causes — collapsed individual issues into diagnoses */}
                      {result.ai.root_causes && result.ai.root_causes.length > 0 && (
                        <div className="space-y-2">
                          <p className="text-[10px] uppercase tracking-widest text-white/30">Root causes</p>
                          {result.ai.root_causes.map((rc, i) => (
                            <div key={i} className="rounded-xl border border-red-400/15 bg-red-400/5 p-3">
                              <div className="flex items-center justify-between gap-2 mb-1">
                                <span className="text-xs font-medium text-white/75">{rc.name}</span>
                                <span className="text-[10px] text-white/25 shrink-0">{Math.round(rc.confidence * 100)}% conf</span>
                              </div>
                              <p className="text-xs text-white/45 leading-relaxed">{rc.evidence}</p>
                              {rc.affected_columns && rc.affected_columns.length > 0 && (
                                <p className="mt-1 text-[10px] font-mono text-white/25">
                                  columns: {rc.affected_columns.join(", ")}
                                </p>
                              )}
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Physics comparison */}
                      {(result.ai.physics_agreement || result.ai.physics_gaps) && (
                        <div className="grid gap-2 sm:grid-cols-2">
                          {result.ai.physics_agreement && (
                            <div className="rounded-xl bg-pass/5 border border-pass/15 p-3">
                              <p className="text-[10px] uppercase tracking-widest text-pass/70 mb-1.5">Confirms physics findings</p>
                              <p className="text-xs text-white/50 leading-relaxed">{result.ai.physics_agreement}</p>
                            </div>
                          )}
                          {result.ai.physics_gaps && (
                            <div className="rounded-xl bg-amber-400/5 border border-amber-400/15 p-3">
                              <p className="text-[10px] uppercase tracking-widest text-amber-400/70 mb-1.5">What physics engine missed</p>
                              <p className="text-xs text-white/50 leading-relaxed">{result.ai.physics_gaps}</p>
                            </div>
                          )}
                        </div>
                      )}

                      {/* AI findings */}
                      {(result.ai.findings ?? []).length > 0 && (
                        <div className="space-y-2">
                          <p className="text-[10px] uppercase tracking-widest text-white/30">
                            AI Findings ({result.ai.findings?.length})
                          </p>
                          {(result.ai.findings ?? []).map((f, i) => {
                            const srcBadge = f.source === "confirms_physics" ? "✓ confirms" : f.source === "physics_missed" ? "⚠ new" : "AI only";
                            const srcColor = f.source === "confirms_physics" ? "text-pass/60" : f.source === "physics_missed" ? "text-amber-400/60" : "text-purple-400/60";
                            return (
                              <div key={i} className={cn("rounded-xl border p-3",
                                f.severity === "critical" ? "border-red-400/20 bg-red-400/5" :
                                f.severity === "warning"  ? "border-amber-400/15 bg-amber-400/5" :
                                                            "border-purple-400/10 bg-purple-400/5")}>
                                <div className="flex items-start justify-between gap-2 mb-1.5">
                                  <div className="flex items-center gap-2 flex-wrap">
                                    <span className={f.severity === "critical" ? "text-red-400" : f.severity === "warning" ? "text-amber-400" : "text-purple-400"}>
                                      {f.severity === "critical" ? "✗" : f.severity === "warning" ? "⚠" : "ℹ"}
                                    </span>
                                    <span className="text-xs font-medium text-white/75">{f.title}</span>
                                    <span className={cn("text-[10px] font-mono", srcColor)}>{srcBadge}</span>
                                  </div>
                                  <span className="text-[10px] text-white/25 shrink-0">{Math.round(f.confidence * 100)}% conf</span>
                                </div>
                                <p className="text-xs text-white/45 leading-relaxed pl-4">{f.detail}</p>
                                {f.trials && f.trials.length > 0 && (
                                  <p className="mt-1 text-[10px] font-mono text-white/25 pl-4">
                                    Trials: {f.trials.slice(0,5).map(t => `#${t}`).join(", ")}{f.trials.length > 5 ? "…" : ""}
                                  </p>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      )}

                      {/* Recommendations */}
                      {(result.ai.recommendations ?? []).length > 0 && (
                        <div className="space-y-2">
                          <p className="text-[10px] uppercase tracking-widest text-white/30">Recommendations</p>
                          {(result.ai.recommendations ?? []).map((r, i) => (
                            <div key={i} className="flex gap-2 text-xs text-white/45">
                              <span className="text-accent-cyan shrink-0">→</span>
                              <span>{r}</span>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Phase timings — collapsed debug info */}
                      {result.ai.phase_timings && Object.keys(result.ai.phase_timings).length > 0 && (
                        <details className="rounded-xl border border-white/[0.06] bg-black/20 p-3">
                          <summary className="cursor-pointer text-[10px] uppercase tracking-widest text-white/30 flex items-center gap-1.5">
                            <Timer className="h-3 w-3" /> Debug: orchestrator phase timings
                          </summary>
                          <div className="mt-2 space-y-1">
                            {Object.entries(result.ai.phase_timings).map(([phase, ms]) => (
                              <div key={phase} className="flex justify-between text-[11px] font-mono text-white/40">
                                <span>{phase.replace(/_/g, " ")}</span>
                                <span>{ms}ms</span>
                              </div>
                            ))}
                          </div>
                        </details>
                      )}
                    </div>
                  )}

                  {result.ai?.status === "error" && (
                    <p className="text-xs text-white/30">
                      AI layer unavailable ({result.ai.error}). Physics validation above is complete and standalone.
                    </p>
                  )}
                </div>

                {/* Statistics collapsible */}
                <div className="rounded-2xl border border-white/[0.08] bg-ink-900/60 p-5">
                  <button onClick={() => setShowStats(v => !v)}
                    className="flex items-center justify-between w-full">
                    <p className="text-xs uppercase tracking-widest text-white/30">
                      Column Statistics — {result.trials_valid} valid trials
                    </p>
                    {showStats ? <ChevronUp className="h-4 w-4 text-white/25" /> : <ChevronDown className="h-4 w-4 text-white/25" />}
                  </button>
                  {showStats && (
                    <div className="mt-4 grid gap-2 sm:grid-cols-2">
                      {Object.entries(result.statistics ?? {}).map(([col, s]) => (
                        <div key={col} className="rounded-xl bg-white/[0.02] border border-white/[0.05] p-3">
                          <p className="font-mono text-[10px] text-accent-cyan mb-2">{col}</p>
                          <div className="space-y-0.5">
                            {([["mean", s.mean], ["std", s.std], ["p5–p95", `${fmtN(s.p5)} – ${fmtN(s.p95)}`], ["n valid", s.n], ["cv", s.cv]] as [string, number|string][])
                              .map(([k, v]) => (
                              <div key={k} className="flex justify-between text-[10px]">
                                <span className="text-white/25">{k}</span>
                                <span className="font-mono text-white/55">{typeof v === "number" ? fmtN(v) : v}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
      )}
    </div>
  );
}
