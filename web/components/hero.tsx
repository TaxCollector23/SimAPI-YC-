"use client";

import Link from "next/link";
import { useState } from "react";
import { motion } from "framer-motion";
import { Copy, Check } from "lucide-react";
import { HeroBackground } from "./hero-background";

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.07, delayChildren: 0.04 } },
};
const item = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.22, 1, 0.36, 1] } },
};

const INSTALL = "npm install -g simapi-cli";

export function Hero() {
  return (
    <section className="relative overflow-hidden border-b border-white/[0.06] pt-36 pb-20 sm:pt-40 sm:pb-24">
      <HeroBackground />

      <div className="container-tight relative">
        <motion.div
          variants={container}
          initial={false}
          animate="show"
          className="flex w-full max-w-3xl flex-col items-start text-left"
        >
          <motion.h1
            variants={item}
            className="text-balance text-4xl font-semibold leading-[1.06] tracking-tight text-white sm:text-[52px] md:text-[60px]"
          >
            Your solver won&apos;t tell you the run is wrong. SimAPI will.
          </motion.h1>

          <motion.p
            variants={item}
            className="mt-6 max-w-2xl text-base leading-relaxed text-white/60 sm:text-lg"
          >
            SimAPI checks simulation output and setup against physical law — catching
            diverged runs, unit-conversion slips, sensor drift, and impossible values
            before the data reaches a design review, an autonomy stack, or an ML pipeline.
          </motion.p>

          <motion.div variants={item} className="mt-9 flex flex-wrap items-center gap-x-6 gap-y-3">
            <Link href="/dashboard" className="btn-accent">
              Get an API key
            </Link>
            <Link href="/docs" className="btn-primary">
              Read the docs
            </Link>
          </motion.div>

          <motion.div variants={item} className="mt-8 w-full max-w-md">
            <InstallCommand />
          </motion.div>

          <motion.p
            variants={item}
            className="mt-6 font-mono text-xs tracking-tight text-white/40"
          >
            CFD, FEA, robotics &nbsp;·&nbsp; CLI, SDK, REST &nbsp;·&nbsp; CI fail gates
          </motion.p>
        </motion.div>
      </div>
    </section>
  );
}

function InstallCommand() {
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex items-center justify-between gap-3 border border-white/10 bg-black/40 px-4 py-3">
      <code className="min-w-0 truncate font-mono text-[13px] text-white/85">
        <span className="select-none text-accent-blueSoft">$ </span>
        {INSTALL}
      </code>
      <button
        type="button"
        onClick={() => {
          navigator.clipboard?.writeText(INSTALL);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        }}
        aria-label="Copy install command"
        className="flex shrink-0 items-center gap-1.5 text-xs text-white/45 transition-colors hover:text-white"
      >
        {copied ? <Check className="h-3.5 w-3.5 text-pass" /> : <Copy className="h-3.5 w-3.5" />}
        <span className="hidden sm:inline">{copied ? "Copied" : "Copy"}</span>
      </button>
    </div>
  );
}
