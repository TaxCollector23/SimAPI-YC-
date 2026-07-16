"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Terminal, KeyRound, ShieldCheck } from "lucide-react";
import { HeroBackground } from "./hero-background";

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08, delayChildren: 0.05 } },
};
const item = {
  hidden: { opacity: 0, y: 18 },
  show: { opacity: 1, y: 0, transition: { duration: 0.7, ease: [0.22, 1, 0.36, 1] } },
};

export function Hero() {
  const proofPoints = ["CFD, FEA, robotics", "CLI, SDK, REST API", "CI fail gates"];

  return (
    <section className="relative overflow-hidden pt-36 pb-16 sm:pt-40">
      <HeroBackground />

      <div className="container-tight relative">
        <motion.div
          variants={container}
          initial={false}
          animate="show"
          className="mx-auto flex w-full max-w-4xl flex-col items-center text-center"
        >
          <motion.div variants={item}>
            <span className="eyebrow">
              <span className="h-1.5 w-1.5 rounded-full bg-accent-cyan animate-pulse-soft" />
              Simulation validation
            </span>
          </motion.div>

          <motion.h1
            variants={item}
            className="mt-7 w-full text-balance text-3xl font-semibold leading-[1.08] tracking-tight text-white sm:text-6xl md:text-[68px]"
          >
            Your solver won&apos;t tell you the run is{" "}
            <span className="text-gradient">wrong</span>.
            <br className="hidden sm:block" /> SimAPI will.
          </motion.h1>

          <motion.p
            variants={item}
            className="mt-6 w-full max-w-2xl text-base leading-relaxed text-white/60 sm:text-lg"
          >
            SimAPI checks simulation output and setup against physical law — catching
            diverged runs, unit-conversion slips, sensor drift, and impossible values
            before the data reaches a design review, an autonomy stack, or an ML pipeline.
          </motion.p>

          <motion.div variants={item} className="mt-9 flex w-full flex-wrap items-center justify-center gap-3">
            <Link href="/dashboard" className="btn-accent">
              <KeyRound className="h-4 w-4" /> Get API Key
            </Link>
            <Link href="/docs" className="btn-ghost">
              <Terminal className="h-4 w-4" /> View Documentation
            </Link>
          </motion.div>

          <motion.div
            variants={item}
            className="mt-8 flex w-full flex-wrap items-center justify-center gap-2 text-xs text-white/42"
          >
            {proofPoints.map((point) => (
              <span
                key={point}
                className="inline-flex items-center gap-1.5 rounded-full border border-white/[0.08] bg-black/20 px-3 py-1.5"
              >
                <ShieldCheck className="h-3.5 w-3.5 text-pass" />
                {point}
              </span>
            ))}
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
}
