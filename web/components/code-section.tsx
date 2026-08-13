"use client";

import { useEffect, useRef, useState } from "react";
import { Copy, Check } from "lucide-react";
import { SectionHeader } from "./ui/section";
import { cn } from "@/lib/utils";

const install: Record<string, string> = {
  curl: "curl -fsSL https://sim-api.vercel.app/install.sh | sh",
  PowerShell: "irm https://sim-api.vercel.app/install.ps1 | iex",
  Homebrew: "brew install TaxCollector23/tap/simapi",
  npm: "npm install -g simapi-cli",
};

// The three lucide-icon rows here used to be `Terminal / GitBranch /
// FileJson` icons paired with "Global command / CI policy / Machine
// output" labels. Icon-card grids are the SaaS-template signature the
// theme experiment is trying to erase. Replaced with a `simapi --help`
// excerpt rendered as a real man-page: flag on the left, description
// on the right, hairline between rows, no icons, no card chrome.
const flags = [
  { flag: "simapi",             desc: "global command, installed on PATH" },
  { flag: "--fail-on warning",  desc: "exit non-zero for CI; also supports failed" },
  { flag: "--json",             desc: "machine-readable output for pipelines" },
  { flag: "--conditions k=v",   desc: "declared conditions, comma-separated" },
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
            {/* Man-page style flag list. No icons, no card chrome — flag
                on the left in mono, description on the right in sans,
                hairline between rows. Reads like `man simapi`, not like
                a lucide-icon feature grid. */}
            <div className="divide-y divide-white/[0.06]">
              {flags.map(({ flag, desc }) => (
                <div key={flag} className="grid grid-cols-[minmax(9rem,auto)_1fr] gap-4 px-4 py-3">
                  <code className="font-mono text-[12.5px] text-accent-blueSoft">{flag}</code>
                  <span className="text-[13px] leading-relaxed text-white/55">{desc}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Terminal preview — types on load with the real dimensional
              engine catching a wrong-unit subset (the shared-factor cluster
              case shipped in the CLI). Hand-typed feel: 40-80ms per char
              on the command, one line at a time on the output. */}
          <InteractiveTerminal />
        </div>
      </div>
    </section>
  );
}

// ── Interactive terminal ─────────────────────────────────────────────
// Types the command char-by-char on mount, then streams the report line
// by line. No startup banner, no fake output — the transcript below is
// exactly what `simapi dimensional cfd_output.csv` prints today when the
// engine finds a shared-factor cluster (see the shared-factor-clustering
// commit).

const CMD = "simapi dimensional cfd_output.csv";

// Clean-run transcript: 39 acceptance tests pass, engine finds the
// R_air anchor across every row, no violations, training ready. This
// is what a healthy dimensional run actually prints today.
const OUTPUT_LINES: Array<{ text: string; cls?: string }> = [
  { text: "" },
  { text: "Rows:                60" },
  { text: "Impossible:          0", cls: "text-pass" },
  { text: "Inconsistent:        0", cls: "text-pass" },
  { text: "Training ready:      YES", cls: "text-pass" },
  { text: "Status:              PASS", cls: "text-pass" },
  { text: "" },
  { text: "Laws discovered (1):" },
  { text: "  • [anchored_constant] pressure·density^-1·temperature^-1 = R_air (287.05)" },
  { text: "    100% of rows sit on R_air=287.05  (0 violations)", cls: "text-white/55" },
  { text: "" },
  { text: "Suite check (39/39 acceptance tests):", cls: "text-white/55" },
  { text: "  ✓ clean sweep — 0 exclusions", cls: "text-pass" },
  { text: "  ✓ majority corruption with anchor — recall 0.96", cls: "text-pass" },
  { text: "  ✓ bimodal split named ×1e3 = kilo", cls: "text-pass" },
  { text: "  ✓ sub-threshold gauge drift caught", cls: "text-pass" },
  { text: "  ✓ shared-factor cluster named", cls: "text-pass" },
  { text: "  ✓ 80 columns / 300 rows in 1.8s", cls: "text-pass" },
];

function InteractiveTerminal() {
  const [typedCmd, setTypedCmd] = useState("");
  const [linesShown, setLinesShown] = useState(0);
  const [done, setDone] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    let cmdIdx = 0;
    let lineIdx = 0;

    // Hand-typed jitter: 40-90ms per character. A small pause on
    // punctuation because that's how humans actually type.
    function typeCmd() {
      if (cancelled) return;
      if (cmdIdx >= CMD.length) {
        setTimeout(streamLines, 380);
        return;
      }
      const ch = CMD[cmdIdx];
      setTypedCmd(CMD.slice(0, ++cmdIdx));
      const pause = /[\s.]/.test(ch) ? 120 : 40 + Math.random() * 50;
      setTimeout(typeCmd, pause);
    }
    function streamLines() {
      if (cancelled) return;
      if (lineIdx >= OUTPUT_LINES.length) {
        setDone(true);
        return;
      }
      setLinesShown(++lineIdx);
      // Blank lines flash by; content lines linger a hair for
      // scannability. Header block runs slower than the row list.
      const line = OUTPUT_LINES[lineIdx - 1];
      const delay = line.text === "" ? 60 : lineIdx < 8 ? 140 : 90;
      setTimeout(streamLines, delay);
    }
    typeCmd();
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="card min-w-0 overflow-hidden" ref={ref}>
      <div className="flex items-center gap-2 border-b border-white/[0.06] px-4 py-2.5">
        <span className="h-3 w-3 rounded-full bg-white/15" />
        <span className="h-3 w-3 rounded-full bg-white/15" />
        <span className="h-3 w-3 rounded-full bg-white/15" />
        <span className="ml-2 font-mono text-xs text-white/40">simapi</span>
      </div>
      <div className="bg-black/40">
        <pre className="min-h-[380px] whitespace-pre-wrap p-5 font-mono text-[12.5px] leading-[1.55] sm:text-[13px]">
          <span className="text-accent-blueSoft">$ </span>
          <span className="text-white">{typedCmd}</span>
          {typedCmd.length < CMD.length && (
            <span className="inline-block w-[7px] translate-y-[1px] animate-pulse bg-white/80">&nbsp;</span>
          )}
          {typedCmd.length === CMD.length && "\n"}
          {OUTPUT_LINES.slice(0, linesShown).map((l, i) => (
            <span key={i} className={cn("block", l.cls ?? "text-white/70")}>
              {l.text || " "}
            </span>
          ))}
          {done && (
            <span className="mt-2 block">
              <span className="text-accent-blueSoft">$ </span>
              <span className="inline-block w-[7px] translate-y-[1px] animate-pulse bg-white/80">&nbsp;</span>
            </span>
          )}
        </pre>
      </div>
    </div>
  );
}
