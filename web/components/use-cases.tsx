"use client";

import { motion } from "framer-motion";
import { Plane, Bot, Car, Zap, FlaskConical, Copy } from "lucide-react";
import { SectionHeader } from "./ui/section";

const cases = [
  { icon: Plane, field: "Aerospace", flow: "Validate CFD drag/lift sweeps against physical envelopes before they enter design review or a surrogate model." },
  { icon: Bot, field: "Robotics", flow: "Gate controller simulations on joint-torque, tracking-error, and stability checks before hardware deployment." },
  { icon: Car, field: "Automotive", flow: "Screen thousands of aero and thermal runs nightly; block regressions from reaching the vehicle program." },
  { icon: Zap, field: "Energy", flow: "Verify combustion, heat-exchanger, and structural results for turbines and reactors against conservation laws." },
  { icon: FlaskConical, field: "Scientific computing", flow: "Catch solver divergence and unit-conversion errors before results are published or reused." },
  { icon: Copy, field: "Digital twins", flow: "Continuously validate live simulation streams so the twin never drifts from physical plausibility." },
];

export function UseCases() {
  return (
    <section className="relative border-t border-white/[0.06] py-24 sm:py-32">
      <div className="container-tight">
        <SectionHeader
          eyebrow="Use cases"
          title={<>Built for the teams that simulate the physical world</>}
          lede="Wherever a simulation feeds a decision, SimAPI is the gate that decides whether to trust it."
        />

        <div className="mt-14 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {cases.map((c, i) => (
            <motion.div
              key={c.field}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: (i % 3) * 0.06, duration: 0.5 }}
              className="rounded-2xl border border-white/[0.07] bg-ink-900/50 p-6"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 bg-white/[0.03]">
                  <c.icon className="h-4.5 w-4.5 text-accent-violet" />
                </div>
                <h3 className="text-[15px] font-semibold text-white">{c.field}</h3>
              </div>
              <p className="mt-4 text-sm leading-relaxed text-white/50">{c.flow}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
