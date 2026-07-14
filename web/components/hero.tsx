"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Terminal, KeyRound } from "lucide-react";
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
  return (
    <section className="relative overflow-hidden pt-40 pb-16">
      <HeroBackground />

      <div className="container-tight relative">
        <motion.div
          variants={container}
          initial="hidden"
          animate="show"
          className="mx-auto flex max-w-3xl flex-col items-center text-center"
        >
          <motion.div variants={item}>
            <span className="eyebrow">
              <span className="h-1.5 w-1.5 rounded-full bg-accent-cyan animate-pulse-soft" />
              Simulation validation API
            </span>
          </motion.div>

          <motion.h1
            variants={item}
            className="mt-7 text-balance text-5xl font-semibold leading-[1.05] tracking-tight text-white sm:text-6xl md:text-7xl"
          >
            Validate simulation results
            <br />
            before they reach{" "}
            <span className="text-gradient">production</span>.
          </motion.h1>

          <motion.p
            variants={item}
            className="mt-6 max-w-xl text-lg leading-relaxed text-white/55"
          >
            Upload simulation outputs and detect impossible values, failed constraints,
            and physics violations before your team trusts the data.
          </motion.p>

          <motion.div variants={item} className="mt-9 flex flex-wrap items-center justify-center gap-3">
            <Link href="/dashboard" className="btn-accent">
              <KeyRound className="h-4 w-4" /> Get API Key
            </Link>
            <Link href="/docs" className="btn-ghost">
              <Terminal className="h-4 w-4" /> View Documentation
            </Link>
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
}
