"use client";

import { useState } from "react";
import { Copy, Check } from "lucide-react";
import { SectionHeader } from "./ui/section";
import { cn } from "@/lib/utils";

const install: Record<string, string> = {
  curl: "curl -fsSL https://sim-api.vercel.app/install.sh | sh",
  PowerShell: "irm https://sim-api.vercel.app/install.ps1 | iex",
  Homebrew: "brew install TaxCollector23/tap/simapi",
  npm: "npm install -g simapi",
  pip: "pip install simapi",
};

// SIMAPI banner — same art and cyan→blue gradient the CLI prints.
const ART = [
  "███████╗██╗███╗   ███╗ █████╗ ██████╗ ██╗",
  "██╔════╝██║████╗ ████║██╔══██╗██╔══██╗██║",
  "███████╗██║██╔████╔██║███████║██████╔╝██║",
  "╚════██║██║██║╚██╔╝██║██╔══██║██╔═══╝ ██║",
  "███████║██║██║ ╚═╝ ██║██║  ██║██║     ██║",
  "╚══════╝╚═╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝",
];
const GRAD = ["#22d3ee", "#2abef0", "#32aaf3", "#3796f5", "#3a87f6", "#3b82f6"];

export function CodeSection() {
  const installTabs = Object.keys(install);
  const [inst, setInst] = useState(installTabs[0]);
  const [copied, setCopied] = useState(false);

  return (
    <section className="relative pb-24 pt-4 sm:pb-28">
      <div className="container-tight">
        <SectionHeader
          eyebrow="Get started"
          title={<>Install the CLI</>}
          lede="Install in one line. Validate in three."
        />

        <div className="mx-auto mt-10 max-w-3xl space-y-4">
          {/* Install options */}
          <div className="card overflow-hidden">
            <div className="flex items-center justify-between border-b border-white/[0.06] px-3 py-2">
              <div className="flex flex-wrap gap-1">
                {installTabs.map((t) => (
                  <button
                    key={t}
                    onClick={() => setInst(t)}
                    className={cn(
                      "rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
                      t === inst ? "bg-white/10 text-white" : "text-white/45 hover:text-white",
                    )}
                  >
                    {t}
                  </button>
                ))}
              </div>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(install[inst]);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 1500);
                }}
                className="flex items-center gap-1.5 px-2 text-xs text-white/45 hover:text-white"
              >
                {copied ? <Check className="h-3.5 w-3.5 text-pass" /> : <Copy className="h-3.5 w-3.5" />}
              </button>
            </div>
            <pre className="overflow-x-auto p-4 font-mono text-[13px] text-white/75">
              <span className="text-accent-cyan">$ </span>
              {install[inst]}
            </pre>
          </div>

          {/* Terminal preview */}
          <div className="card overflow-hidden">
            <div className="flex items-center gap-2 border-b border-white/[0.06] px-4 py-2.5">
              <span className="h-3 w-3 rounded-full bg-white/15" />
              <span className="h-3 w-3 rounded-full bg-white/15" />
              <span className="h-3 w-3 rounded-full bg-white/15" />
              <span className="ml-2 font-mono text-xs text-white/40">simapi</span>
            </div>
            <div className="overflow-x-auto bg-black/40 p-5">
              <pre className="font-mono text-[11px] leading-[1.15] sm:text-[13px]">
                {ART.map((line, i) => (
                  <div key={i} style={{ color: GRAD[i] }}>
                    {line}
                  </div>
                ))}
              </pre>
              <pre className="mt-3 font-mono text-[12px] leading-relaxed sm:text-[13px]">
                <span className="text-white/90">        SimAPI CLI v1.0.0</span>
                {"\n"}
                <span className="text-white/40">  Validate simulation results before they reach production.</span>
              </pre>
              <pre className="mt-4 font-mono text-[13px] leading-relaxed sm:text-[14px]">
                <span className="text-accent-cyan">$ </span>
                <span className="text-accent-blue">simapi validate simulations.json</span>
              </pre>
              <pre className="mt-2 font-mono text-[12.5px] leading-relaxed text-white/55">
{`  Validation report  simulations.json
  ──────────────────────────────────────────────
  Status                 `}<span className="text-pass">PASSED</span>{`
  Validation score       98
  Execution time         23ms`}
              </pre>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
