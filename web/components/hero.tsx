"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, Terminal, KeyRound } from "lucide-react";
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
    <section className="relative min-h-[92vh] overflow-hidden pt-32">
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

          <motion.div variants={item} className="mt-14 w-full">
            <TerminalCard />
          </motion.div>

          <motion.p variants={item} className="mt-6 text-xs uppercase tracking-[0.2em] text-white/35">
            287 checks · 21 domains · deterministic
          </motion.p>
        </motion.div>
      </div>
    </section>
  );
}

function TerminalCard() {
  return (
    <div className="mx-auto max-w-2xl overflow-hidden rounded-2xl border border-white/[0.08] bg-ink-900/70 shadow-glow backdrop-blur-md">
      <div className="flex items-center gap-2 border-b border-white/[0.06] px-4 py-3">
        <span className="h-3 w-3 rounded-full bg-white/15" />
        <span className="h-3 w-3 rounded-full bg-white/15" />
        <span className="h-3 w-3 rounded-full bg-white/15" />
        <span className="ml-2 font-mono text-xs text-white/40">simapi — validate</span>
      </div>
      <div className="p-5 text-left font-mono text-[13px] leading-relaxed">
        <p className="text-white/40">
          <span className="text-accent-cyan">$</span> curl -X POST api.simapi.dev/v1/validate \
        </p>
        <p className="pl-4 text-white/40">
          -H <span className="text-emerald-300">&quot;X-API-Key: sk_live_…&quot;</span> -d @cfd_run.json
        </p>
        <div className="mt-3 rounded-lg border border-white/[0.06] bg-black/30 p-3">
          <span className="text-white/50">{"{"}</span>
          <br />
          <span className="pl-4 text-white/50">
            &quot;status&quot;: <span className="text-pass">&quot;passed&quot;</span>,
          </span>
          <br />
          <span className="pl-4 text-white/50">
            &quot;confidence&quot;: <span className="text-accent-cyan">&quot;high&quot;</span>,
          </span>
          <br />
          <span className="pl-4 text-white/50">
            &quot;training_ready&quot;: <span className="text-pass">true</span>,
          </span>
          <br />
          <span className="pl-4 text-white/50">
            &quot;all_checks&quot;: <span className="text-white/80">287</span>,
            &quot;processing_ms&quot;: <span className="text-white/80">23.4</span>
          </span>
          <br />
          <span className="text-white/50">{"}"}</span>
        </div>
        <p className="mt-3 flex items-center gap-2 text-white/40">
          <ArrowRight className="h-3.5 w-3.5 text-pass" /> validated in 23ms · request_id: 3f9c…a12
        </p>
      </div>
    </div>
  );
}
