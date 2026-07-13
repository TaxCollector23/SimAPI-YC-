"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Play,
  RotateCcw,
  Check,
  Loader2,
  AlertTriangle,
  XCircle,
  Sparkles,
  Wrench,
} from "lucide-react";
import { scenarios, verdictMeta, pipelineStages, type Scenario } from "@/lib/demo-data";
import { LineChart, Heatmap, ScoreRing } from "./charts";
import { SectionHeader } from "./ui/section";
import { cn } from "@/lib/utils";

type Phase = "idle" | "running" | "done";

export function InteractiveDemo() {
  const [scenarioId, setScenarioId] = useState(scenarios[0].id);
  const [phase, setPhase] = useState<Phase>("idle");
  const [stage, setStage] = useState(-1);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const scenario = scenarios.find((s) => s.id === scenarioId)!;

  function clearTimers() {
    timers.current.forEach(clearTimeout);
    timers.current = [];
  }

  function run() {
    clearTimers();
    setPhase("running");
    setStage(0);
    const stepMs = 720;
    pipelineStages.forEach((_, i) => {
      timers.current.push(
        setTimeout(() => setStage(i), i * stepMs),
      );
    });
    timers.current.push(
      setTimeout(() => {
        setPhase("done");
        setStage(pipelineStages.length);
      }, pipelineStages.length * stepMs + 300),
    );
  }

  function reset() {
    clearTimers();
    setPhase("idle");
    setStage(-1);
  }

  // Re-run automatically when switching scenarios after a completed run.
  function pickScenario(id: string) {
    setScenarioId(id);
    if (phase === "done") {
      // brief re-validate flash
      clearTimers();
      setPhase("running");
      setStage(pipelineStages.length - 1);
      timers.current.push(setTimeout(() => setPhase("done"), 520));
    }
  }

  useEffect(() => () => clearTimers(), []);

  return (
    <section id="demo" className="relative py-24 sm:py-32">
      <div className="container-tight">
        <SectionHeader
          eyebrow="Live demo"
          title={<>See a simulation validated in real time</>}
          lede="Run the pipeline, then flip between a clean run and a broken one to watch the verdict change instantly."
        />

        <div className="mx-auto mt-12 max-w-5xl">
          {/* Controls */}
          <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
            <div className="flex flex-wrap gap-1.5 rounded-full border border-white/[0.08] bg-ink-900/60 p-1">
              {scenarios.map((s) => (
                <button
                  key={s.id}
                  onClick={() => pickScenario(s.id)}
                  className={cn(
                    "rounded-full px-3.5 py-1.5 text-xs font-medium transition-all",
                    s.id === scenarioId
                      ? "bg-white text-ink-950"
                      : "text-white/55 hover:text-white",
                  )}
                >
                  {s.label}
                </button>
              ))}
            </div>

            <div className="flex gap-2">
              {phase !== "idle" && (
                <button onClick={reset} className="btn-ghost">
                  <RotateCcw className="h-4 w-4" /> Reset
                </button>
              )}
              <button onClick={run} className="btn-accent" disabled={phase === "running"}>
                {phase === "running" ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Play className="h-4 w-4" />
                )}
                {phase === "done" ? "Run again" : "Run demo"}
              </button>
            </div>
          </div>

          {/* Stage / dashboard surface */}
          <div className="card mt-6 min-h-[560px] overflow-hidden p-6 sm:p-8">
            <AnimatePresence mode="wait">
              {phase === "idle" && <IdleState key="idle" scenario={scenario} onRun={run} />}
              {phase === "running" && <Pipeline key="pipeline" stage={stage} />}
              {phase === "done" && <Dashboard key="dash" scenario={scenario} />}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </section>
  );
}

function IdleState({ scenario, onRun }: { scenario: Scenario; onRun: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="flex min-h-[500px] flex-col items-center justify-center text-center"
    >
      <div className="rounded-2xl border border-white/[0.08] bg-black/20 p-4 font-mono text-xs text-white/45">
        <p className="text-white/35"># dataset selected</p>
        <p className="mt-1">
          cfd_run.json · <span className="text-white/70">{scenario.trials} trials</span> ·{" "}
          aerodynamics
        </p>
        <p className="mt-1 text-white/35">// {scenario.blurb}</p>
      </div>
      <button onClick={onRun} className="btn-accent mt-8">
        <Play className="h-4 w-4" /> Run validation
      </button>
      <p className="mt-4 text-xs text-white/35">
        No signup required · runs entirely in your browser
      </p>
    </motion.div>
  );
}

function Pipeline({ stage }: { stage: number }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="flex min-h-[500px] flex-col justify-center gap-3"
    >
      {pipelineStages.map((s, i) => {
        const state = i < stage ? "done" : i === stage ? "active" : "pending";
        return (
          <motion.div
            key={s.key}
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.05 }}
            className={cn(
              "flex items-center gap-4 rounded-xl border p-4 transition-colors",
              state === "active"
                ? "border-accent-blue/40 bg-accent-blue/[0.06]"
                : state === "done"
                  ? "border-pass/20 bg-pass/[0.04]"
                  : "border-white/[0.06] bg-white/[0.01]",
            )}
          >
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-white/10">
              {state === "done" ? (
                <Check className="h-4 w-4 text-pass" />
              ) : state === "active" ? (
                <Loader2 className="h-4 w-4 animate-spin text-accent-cyan" />
              ) : (
                <span className="text-xs text-white/30">{i + 1}</span>
              )}
            </div>
            <div className="min-w-0 flex-1">
              <p
                className={cn(
                  "text-sm font-medium",
                  state === "pending" ? "text-white/40" : "text-white",
                )}
              >
                {s.label}
              </p>
              <p className="truncate text-xs text-white/40">{s.detail}</p>
            </div>
            {state === "active" && (
              <div className="hidden h-1 w-24 overflow-hidden rounded-full bg-white/10 sm:block">
                <motion.div
                  className="h-full bg-accent-gradient"
                  initial={{ width: "0%" }}
                  animate={{ width: "100%" }}
                  transition={{ duration: 0.72 }}
                />
              </div>
            )}
          </motion.div>
        );
      })}
    </motion.div>
  );
}

function Dashboard({ scenario }: { scenario: Scenario }) {
  const meta = verdictMeta[scenario.verdict];
  const Icon =
    scenario.verdict === "pass" ? Check : scenario.verdict === "warning" ? AlertTriangle : XCircle;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.4 }}
      className="grid gap-6 lg:grid-cols-[1.1fr_1fr]"
    >
      {/* Left: verdict + scores + charts */}
      <div className="space-y-5">
        <div className={cn("flex items-center justify-between rounded-xl p-4 ring-1", meta.ring)}>
          <div className="flex items-center gap-3">
            <Icon className={cn("h-6 w-6", meta.color)} />
            <div>
              <p className={cn("text-lg font-semibold", meta.color)}>{meta.label}</p>
              <p className="text-xs text-white/45">
                {scenario.trials - scenario.excluded}/{scenario.trials} trials valid ·{" "}
                {scenario.checksRun} checks · {scenario.processingMs}ms
              </p>
            </div>
          </div>
          <span className="font-mono text-xs text-white/35">req_3f9c…a12</span>
        </div>

        <div className="flex justify-around rounded-xl border border-white/[0.06] bg-black/20 p-4">
          <ScoreRing value={scenario.physicsScore} label="Physics" color="#3b82f6" />
          <ScoreRing value={scenario.statisticalScore} label="Statistical" color="#22d3ee" />
          <ScoreRing value={scenario.aiConfidence} label="AI confidence" color="#8b5cf6" />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <ChartCard title="Pressure coefficient">
            <LineChart data={scenario.pressure} color="#22d3ee" />
          </ChartCard>
          <ChartCard title="Velocity profile">
            <LineChart data={scenario.velocity} color="#3b82f6" />
          </ChartCard>
          <ChartCard title="Solver residuals">
            <LineChart data={scenario.residuals} color="#8b5cf6" fill={false} />
          </ChartCard>
          <ChartCard title="Field heatmap">
            <Heatmap grid={scenario.heatmap} />
          </ChartCard>
        </div>
      </div>

      {/* Right: anomalies + AI + fixes */}
      <div className="space-y-5">
        <div className="rounded-xl border border-white/[0.06] bg-black/20 p-4">
          <div className="mb-3 flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-accent-violet" />
            <h4 className="text-sm font-semibold text-white">AI summary</h4>
          </div>
          <p className="text-sm leading-relaxed text-white/60">{scenario.aiSummary}</p>
        </div>

        <div className="rounded-xl border border-white/[0.06] bg-black/20 p-4">
          <h4 className="mb-3 text-sm font-semibold text-white">
            Detected anomalies{" "}
            <span className="text-white/40">({scenario.anomalies.length})</span>
          </h4>
          <div className="space-y-2">
            {scenario.anomalies.length === 0 && (
              <p className="flex items-center gap-2 text-sm text-pass">
                <Check className="h-4 w-4" /> No anomalies detected.
              </p>
            )}
            {scenario.anomalies.map((a, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: 8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.15 + i * 0.06 }}
                className="flex items-start gap-3 rounded-lg border border-white/[0.05] bg-white/[0.02] p-3"
              >
                {a.severity === "critical" ? (
                  <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-fail" />
                ) : (
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warn" />
                )}
                <div className="min-w-0">
                  <p className="font-mono text-xs text-white/70">
                    trial {a.trial} · {a.field} = {a.value}
                  </p>
                  <p className="text-xs text-white/45">{a.reason}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>

        {scenario.fixes.length > 0 && (
          <div className="rounded-xl border border-white/[0.06] bg-black/20 p-4">
            <div className="mb-3 flex items-center gap-2">
              <Wrench className="h-4 w-4 text-accent-cyan" />
              <h4 className="text-sm font-semibold text-white">Suggested fixes</h4>
            </div>
            <ul className="space-y-2">
              {scenario.fixes.map((f, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-white/55">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-accent-cyan" />
                  {f}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </motion.div>
  );
}

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-black/20 p-3">
      <p className="mb-2 text-[11px] uppercase tracking-wider text-white/40">{title}</p>
      <div className="h-24">{children}</div>
    </div>
  );
}
