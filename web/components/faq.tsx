"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Plus } from "lucide-react";
import { SectionHeader } from "./ui/section";
import { cn } from "@/lib/utils";

const faqs = [
  {
    q: "What exactly does SimAPI validate?",
    a: "Two deterministic engines run on every request. The physics rule engine checks per-domain plausibility bounds, conservation laws, and cross-variable relations (Re = ρvL/μ, Ma = v/c, P = ρRT) across 21 simulation domains. The dimensional-analysis cascade resolves each column to an SI dimension, discovers the dimensionless (Buckingham-π) groups in the data itself, anchors them to known physical constants, and tests the data against them. An optional AI layer clusters and narrates findings — it never re-derives physics.",
  },
  {
    q: "Which simulation formats and tools are supported?",
    a: "CSV, JSON, YAML, TOML, TXT/Markdown, VTK, NumPy, and OpenFOAM. An aggressive column-alias map normalizes names across ANSYS, OpenFOAM, STAR-CCM+, Fluent, COMSOL, SU2, Abaqus, and MATLAB conventions, so checks fire without renaming columns. The report lists exactly which aliases were applied.",
  },
  {
    q: "How fast is it?",
    a: "The pre-flight mesh/setup check runs in well under 200ms with no external calls. Full output validation depends on row count and which layers fire — the published benchmark runs the entire dimensional cascade over ~9,300 rows in a few seconds on a CPU-only container. The optional AI layer runs asynchronously and is polled separately, so your pipeline never blocks on it.",
  },
  {
    q: "Do I have to send my data to your servers?",
    a: "No. The default path is entirely deterministic Python and the engine is MIT-licensed, so you can self-host the container — including fully air-gapped — and data never leaves your infrastructure. The hosted API is a convenience, not a requirement.",
  },
  {
    q: "How does it fit into CI/CD?",
    a: "Run the CLI in any pipeline step and branch on the verdict — passed, warning, or failed. A ready-to-copy GitHub Action wrapping the CLI's exit-code gate ships in integrations/github-action, and the same simapi --fail-on pattern works in GitLab CI or Jenkins.",
  },
  {
    q: "Is the AI layer required?",
    a: "No — it is opt-in and off by default. It only runs when an OpenRouter key is configured and you pass run_ai=true. Without a key it reports as disabled and the deterministic engines run exactly the same. Every AI phase fails down, never out: the physics result is always complete and standalone.",
  },
  {
    q: "What happens to invalid trials?",
    a: "Each row is classified: impossible (violates a definition or hard physical bound), inconsistent (contradicts a discovered law, an anchored constant, or a declared condition), or unsuitable_for_training. The response carries an exclusion_rate and a training_ready flag, plus a per-row reason — so you know instantly whether the dataset is safe for ML, and why any row was excluded.",
  },
];

export function Faq() {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <section id="faq" className="relative py-24 sm:py-32">
      <div className="container-tight">
        <SectionHeader eyebrow="FAQ" title={<>Questions, answered</>} />
        <div className="mx-auto mt-12 max-w-3xl divide-y divide-white/[0.07] overflow-hidden rounded-2xl border border-white/[0.07]">
          {faqs.map((f, i) => (
            <div key={i} className="bg-ink-900/40">
              <button
                onClick={() => setOpen(open === i ? null : i)}
                className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left"
              >
                <span className="text-[15px] font-medium text-white">{f.q}</span>
                <Plus
                  className={cn(
                    "h-4 w-4 shrink-0 text-white/40 transition-transform",
                    open === i && "rotate-45",
                  )}
                />
              </button>
              <AnimatePresence initial={false}>
                {open === i && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
                    className="overflow-hidden"
                  >
                    <p className="px-5 pb-5 text-sm leading-relaxed text-white/55">{f.a}</p>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
