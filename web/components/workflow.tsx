"use client";

import { motion } from "framer-motion";
import { Boxes, Upload, ShieldCheck, FileText, GitBranch, CheckCircle2, Database } from "lucide-react";
import { SectionHeader } from "./ui/section";

const steps = [
  { icon: Boxes, label: "Simulation generated", sub: "CFD · FEA · robotics" },
  { icon: Upload, label: "Uploaded", sub: "API · SDK · CLI" },
  { icon: ShieldCheck, label: "Validated", sub: "287 checks + AI" },
  { icon: FileText, label: "Report created", sub: "scores · anomalies" },
  { icon: GitBranch, label: "CI/CD gate", sub: "pass / warn / fail" },
  { icon: CheckCircle2, label: "Approved", sub: "design review" },
  { icon: Database, label: "ML dataset", sub: "training-ready" },
];

export function Workflow() {
  return (
    <section className="relative border-y border-white/[0.06] bg-ink-900/30 py-24 sm:py-32">
      <div className="container-tight">
        <SectionHeader
          eyebrow="Workflow"
          title={<>From solver to trusted dataset</>}
          lede="SimAPI slots into the pipeline you already have — as a gate between simulation and everything downstream."
        />

        <div className="mt-14 overflow-x-auto pb-4">
          <div className="flex min-w-max items-stretch gap-3">
            {steps.map((s, i) => (
              <motion.div
                key={s.label}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.07, duration: 0.5 }}
                className="flex items-center gap-3"
              >
                <div className="flex w-40 flex-col items-center gap-3 rounded-2xl border border-white/[0.07] bg-ink-900/60 p-5 text-center">
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-white/10 bg-white/[0.03]">
                    <s.icon className="h-5 w-5 text-accent-cyan" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-white">{s.label}</p>
                    <p className="mt-0.5 text-[11px] text-white/40">{s.sub}</p>
                  </div>
                </div>
                {i < steps.length - 1 && (
                  <div className="relative h-px w-6 bg-white/10">
                    <motion.div
                      className="absolute inset-0 bg-accent-gradient"
                      initial={{ scaleX: 0 }}
                      whileInView={{ scaleX: 1 }}
                      viewport={{ once: true }}
                      transition={{ delay: i * 0.07 + 0.2, duration: 0.4 }}
                      style={{ originX: 0 }}
                    />
                  </div>
                )}
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
