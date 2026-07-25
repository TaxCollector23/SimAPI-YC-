"use client";

import { useState } from "react";
import { CheckCircle, XCircle, AlertTriangle, ChevronDown, ChevronUp, ShieldAlert, Layers } from "lucide-react";
import { cn } from "@/lib/utils";
import type { DimensionalResult, DimensionalLaw, DimensionalRowFinding } from "@/lib/api";

function fmtN(n: number | null | undefined): string {
  if (n == null) return "—";
  if (Math.abs(n) >= 1e6 || (Math.abs(n) < 0.001 && n !== 0)) return n.toExponential(3);
  return Number.isInteger(n) ? n.toLocaleString() : n.toFixed(4);
}

const CLASS_META: Record<DimensionalRowFinding["output_class"], { label: string; cls: string; icon: React.ReactNode; desc: string }> = {
  impossible: {
    label: "Impossible", cls: "border-red-400/20 bg-red-400/5 text-red-400",
    icon: <XCircle className="h-3.5 w-3.5" />,
    desc: "Anchor, semantic-bound, or structural violation. Re-run these trials.",
  },
  inconsistent: {
    label: "Inconsistent", cls: "border-amber-400/20 bg-amber-400/5 text-amber-400",
    icon: <AlertTriangle className="h-3.5 w-3.5" />,
    desc: "Disagrees with the function the rest of the dataset defines. Human review.",
  },
  unsuitable_for_training: {
    label: "Unsuitable for training", cls: "border-purple-400/20 bg-purple-400/5 text-purple-400",
    icon: <Layers className="h-3.5 w-3.5" />,
    desc: "Physically valid, harmful to learn from (duplicates, coverage gaps, leakage).",
  },
};

function RowFindingCard({ f }: { f: DimensionalRowFinding }) {
  const [open, setOpen] = useState(false);
  const meta = CLASS_META[f.output_class] ?? CLASS_META.inconsistent;
  return (
    <div className={cn("rounded-lg border cursor-pointer transition-colors", meta.cls)} onClick={() => setOpen(v => !v)}>
      <div className="flex items-center gap-3 px-3 py-2.5">
        {meta.icon}
        <span className="text-xs font-mono text-white/40 shrink-0">row {f.row_index}</span>
        <span className="flex-1 text-xs text-white/75 leading-snug truncate">{f.reason}</span>
        <span className="text-[10px] shrink-0 rounded px-1.5 py-0.5 border border-current/20 font-mono opacity-70">
          {f.layer}
        </span>
        {open ? <ChevronUp className="h-3 w-3 text-white/20 shrink-0" /> : <ChevronDown className="h-3 w-3 text-white/20 shrink-0" />}
      </div>
      {open && (
        <div className="border-t border-white/[0.06] px-3 py-2.5 text-xs text-white/45 leading-relaxed space-y-1">
          <p>{f.reason}</p>
          <p className="text-white/30">weight: {fmtN(f.weight)}{f.factor != null ? ` · factor: ${fmtN(f.factor)}x` : ""}</p>
          {f.counterfactual_repair && (
            <p className="text-accent-cyan/70">Counterfactual repair: {f.counterfactual_repair}</p>
          )}
        </div>
      )}
    </div>
  );
}

function LawCard({ law }: { law: DimensionalLaw }) {
  const kindLabel: Record<string, string> = {
    anchored_constant: "Anchored constant", pi_constant: "Pi law (constant group)",
    bimodal_split: "Bimodal split", temporal_drift: "Temporal drift",
  };
  return (
    <div className="rounded-lg border border-white/[0.08] bg-white/[0.02] px-3 py-2.5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-mono text-white/70 truncate">{law.label}</span>
        <span className="text-[10px] shrink-0 rounded px-1.5 py-0.5 border border-accent-cyan/20 text-accent-cyan/70 font-mono">
          {kindLabel[law.kind] ?? law.kind}
        </span>
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-white/35">
        <span>coverage: {(law.coverage * 100).toFixed(1)}%</span>
        <span>violations: {law.n_violations}</span>
        {law.expected_value != null && <span>expected: {fmtN(law.expected_value)}</span>}
        {law.observed_median != null && <span>observed median: {fmtN(law.observed_median)}</span>}
      </div>
      {law.note && <p className="mt-1 text-[11px] text-white/30">{law.note}</p>}
    </div>
  );
}

export function DimensionalResultPanel({ result }: { result: DimensionalResult }) {
  const [rowFilter, setRowFilter] = useState<"all" | DimensionalRowFinding["output_class"]>("all");
  const [showAllRows, setShowAllRows] = useState(false);
  const [showLaws, setShowLaws] = useState(true);
  const [showSuppressions, setShowSuppressions] = useState(false);

  const filteredRows = result.row_findings.filter(f => rowFilter === "all" || f.output_class === rowFilter);
  const visibleRows = showAllRows ? filteredRows : filteredRows.slice(0, 8);

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="rounded-2xl border border-white/[0.08] bg-ink-900/60 p-5">
        <div className="flex items-center justify-between mb-5">
          <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold",
            result.training_ready ? "bg-pass/10 text-pass border-pass/30" : "bg-red-400/10 text-red-400 border-red-400/30")}>
            {result.training_ready ? <CheckCircle className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
            {result.training_ready ? "TRAINING READY" : "IMPOSSIBLE ROWS PRESENT"}
          </span>
          <span className="font-mono text-xs text-white/30">{result.job_id} · {result.n_rows} rows</span>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { l: "Impossible", v: result.n_impossible, c: "text-red-400" },
            { l: "Inconsistent", v: result.n_inconsistent, c: "text-amber-400" },
            { l: "Unsuitable for training", v: result.n_unsuitable_for_training, c: "text-purple-400" },
            { l: "Anchored constants found", v: result.n_anchored_constants, c: "text-accent-cyan" },
          ].map(s => (
            <div key={s.l} className="rounded-xl border border-white/[0.06] bg-black/20 p-3">
              <p className={cn("text-2xl font-semibold tabular-nums", s.c)}>{s.v}</p>
              <p className="mt-0.5 text-[11px] text-white/35">{s.l}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Laws discovered */}
      <div className="rounded-2xl border border-white/[0.08] bg-ink-900/60 p-4">
        <button onClick={() => setShowLaws(v => !v)} className="flex w-full items-center justify-between">
          <span className="text-xs uppercase tracking-widest text-white/35">
            Laws discovered ({result.laws_discovered.length})
          </span>
          {showLaws ? <ChevronUp className="h-3.5 w-3.5 text-white/25" /> : <ChevronDown className="h-3.5 w-3.5 text-white/25" />}
        </button>
        {showLaws && (
          <div className="mt-3 space-y-2">
            {result.laws_discovered.length === 0
              ? <p className="text-xs text-white/25">No dimensionless laws or anchored constants were discovered in this dataset.</p>
              : result.laws_discovered.map((law, i) => <LawCard key={i} law={law} />)}
          </div>
        )}
      </div>

      {/* Row findings */}
      <div className="rounded-2xl border border-white/[0.08] bg-ink-900/60 p-4">
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs uppercase tracking-widest text-white/35">
            Row findings ({filteredRows.length})
          </span>
          <div className="flex gap-1">
            {(["all", "impossible", "inconsistent", "unsuitable_for_training"] as const).map(f => (
              <button key={f} onClick={() => setRowFilter(f)}
                className={cn("rounded-full px-2 py-0.5 text-[10px] border transition-colors",
                  rowFilter === f ? "border-accent-cyan/40 text-accent-cyan bg-accent-cyan/5" : "border-white/10 text-white/35 hover:text-white/60")}>
                {f === "all" ? "All" : CLASS_META[f].label}
              </button>
            ))}
          </div>
        </div>
        {filteredRows.length === 0 ? (
          <div className="flex items-center gap-2 rounded-lg border border-pass/20 bg-pass/5 px-3 py-3 text-xs text-pass">
            <CheckCircle className="h-3.5 w-3.5" /> No rows flagged in this class.
          </div>
        ) : (
          <div className="space-y-1.5">
            {visibleRows.map((f, i) => <RowFindingCard key={i} f={f} />)}
            {filteredRows.length > 8 && (
              <button onClick={() => setShowAllRows(v => !v)} className="w-full text-center text-xs text-accent-cyan/70 hover:text-accent-cyan py-2">
                {showAllRows ? "Show less" : `Show all ${filteredRows.length}`}
              </button>
            )}
          </div>
        )}
      </div>

      {/* Training suitability (dataset-level, not row-level) */}
      {result.training_suitability.length > 0 && (
        <div className="rounded-2xl border border-purple-400/20 bg-purple-400/5 p-4">
          <span className="text-xs uppercase tracking-widest text-purple-400/70 mb-2 block">
            Dataset-level training suitability
          </span>
          <div className="space-y-2">
            {result.training_suitability.map((s, i) => (
              <div key={i} className="text-xs text-white/60 leading-relaxed">
                <span className="font-mono text-purple-400/80">{s.kind}</span> — {s.detail}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Units resolved */}
      <div className="rounded-2xl border border-white/[0.08] bg-ink-900/60 p-4">
        <span className="text-xs uppercase tracking-widest text-white/35 mb-3 block">Units resolved (Layer 0)</span>
        <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-3">
          {Object.entries(result.units_resolved).map(([col, u]) => (
            <div key={col} className="rounded-lg border border-white/[0.06] bg-black/20 px-2.5 py-1.5">
              <p className="text-[11px] font-mono text-white/60 truncate">{col}</p>
              <p className="text-[10px] text-white/30">
                {u.unit_label} · {(u.confidence * 100).toFixed(0)}% · {u.source}
              </p>
            </div>
          ))}
        </div>
        {result.units_conflicts.length > 0 && (
          <div className="mt-3 rounded-lg border border-amber-400/20 bg-amber-400/5 px-3 py-2 text-xs text-amber-400/80">
            {result.units_conflicts.length} units conflict{result.units_conflicts.length > 1 ? "s" : ""}: an LLM-labeled
            dimension disagreed with what a discovered law implied.
          </div>
        )}
      </div>

      {/* Declared-condition assertions */}
      {result.condition_assertions.length > 0 && (
        <div className="rounded-2xl border border-white/[0.08] bg-ink-900/60 p-4">
          <span className="text-xs uppercase tracking-widest text-white/35 mb-3 block">Declared conditions (Layer 7)</span>
          <div className="space-y-2">
            {result.condition_assertions.map((a, i) => (
              <div key={i} className="text-xs text-white/55 leading-relaxed">
                <span className="font-mono text-white/70">{a.label}</span>: declared {fmtN(a.declared)}, implied {fmtN(a.implied)}
                <span className="text-white/30"> ({(a.rel_dev * 100).toFixed(2)}% deviation)</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Suppressions audit trail */}
      <div className="rounded-2xl border border-white/[0.08] bg-ink-900/60 p-4">
        <button onClick={() => setShowSuppressions(v => !v)} className="flex w-full items-center justify-between">
          <span className="flex items-center gap-1.5 text-xs uppercase tracking-widest text-white/35">
            <ShieldAlert className="h-3.5 w-3.5" /> Suppression audit trail ({result.suppressions.length})
          </span>
          {showSuppressions ? <ChevronUp className="h-3.5 w-3.5 text-white/25" /> : <ChevronDown className="h-3.5 w-3.5 text-white/25" />}
        </button>
        {showSuppressions && (
          <div className="mt-3 space-y-1.5">
            {result.suppressions.length === 0
              ? <p className="text-xs text-white/25">Nothing was skipped for this dataset.</p>
              : result.suppressions.map((s, i) => (
                <p key={i} className="text-xs text-white/45 leading-relaxed border-l-2 border-white/10 pl-2.5">{s}</p>
              ))}
          </div>
        )}
      </div>

      {/* Known-impossible boundary — always shown, not suppressible */}
      <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-4">
        <p className="text-[10px] uppercase tracking-widest text-white/30 mb-1.5">What this cannot detect</p>
        <p className="text-xs text-white/35 leading-relaxed">{result.known_impossible}</p>
      </div>
    </div>
  );
}
