"use client";

import Image from "next/image";
import { useState } from "react";
import { Copy, Check, Terminal, GitBranch, FileJson } from "lucide-react";
import { SectionHeader } from "./ui/section";
import { cn } from "@/lib/utils";

const install: Record<string, string> = {
  curl: "curl -fsSL https://sim-api.vercel.app/install.sh | sh",
  PowerShell: "irm https://sim-api.vercel.app/install.ps1 | iex",
  Homebrew: "brew install TaxCollector23/tap/simapi",
  npm: "npm install -g simapi-cli",
};

const checks = [
  { icon: Terminal, label: "Global command", value: "simapi" },
  { icon: GitBranch, label: "CI policy", value: "--fail-on warning" },
  { icon: FileJson, label: "Machine output", value: "--json" },
];

export function CodeSection() {
  const installTabs = Object.keys(install);
  const [inst, setInst] = useState(installTabs[0]);
  const [copied, setCopied] = useState(false);

  return (
    <section className="relative pb-24 pt-4 sm:pb-28">
      <div className="container-tight">
        <SectionHeader
          eyebrow="CLI and SDK"
          title={<>Install once. Validate every run.</>}
          lede="Use the hosted API from a terminal, CI job, or Node workflow. The npm package installs as simapi-cli and exposes the simapi command."
        />

        <div className="mx-auto mt-10 grid max-w-5xl gap-4 lg:grid-cols-[0.85fr_1.15fr]">
          {/* Install options */}
          <div className="card min-w-0 overflow-hidden">
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
            <pre className="overflow-x-auto border-b border-white/[0.06] p-4 font-mono text-[13px] text-white/75">
              <span className="text-accent-cyan">$ </span>
              {install[inst]}
            </pre>
            <div className="grid divide-y divide-white/[0.06]">
              {checks.map(({ icon: Icon, label, value }) => (
                <div key={label} className="flex items-center justify-between gap-4 px-4 py-3">
                  <div className="flex items-center gap-2.5 text-sm text-white/62">
                    <Icon className="h-4 w-4 text-accent-cyan" />
                    {label}
                  </div>
                  <code className="rounded-md border border-white/[0.08] bg-black/25 px-2 py-1 font-mono text-xs text-white/70">
                    {value}
                  </code>
                </div>
              ))}
            </div>
          </div>

          {/* Terminal preview */}
          <div className="card min-w-0 overflow-hidden">
            <div className="flex items-center gap-2 border-b border-white/[0.06] px-4 py-2.5">
              <span className="h-3 w-3 rounded-full bg-white/15" />
              <span className="h-3 w-3 rounded-full bg-white/15" />
              <span className="h-3 w-3 rounded-full bg-white/15" />
              <span className="ml-2 font-mono text-xs text-white/40">simapi validate</span>
            </div>
            <div className="bg-black/40">
              <Image
                src="/cli-banner.png"
                alt="SimAPI CLI startup banner"
                width={1776}
                height={785}
                className="h-auto w-full border-b border-white/[0.06]"
                priority
              />
              <pre className="p-5 font-mono text-[13px] leading-relaxed sm:text-[14px]">
                <span className="text-accent-cyan">$ </span>
                <span className="text-accent-blue">simapi validate simulations.json</span>
                {"\n"}
                <span className="text-white/45">{"\n"}</span>
                <span className="text-white/55">
{`  Validation report  simulations.json
  ──────────────────────────────────────────────
  Status                 `}<span className="text-pass">PASSED</span>{`
  Validation score       98
  Execution time         23ms`}
                </span>
              </pre>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
