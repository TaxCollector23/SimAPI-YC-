"use client";

import { useEffect, useRef, useState } from "react";
import { Copy, Check } from "lucide-react";
import { SectionHeader } from "./ui/section";
import { cn } from "@/lib/utils";

// One install path per platform: npm on macOS + Windows, Homebrew on Linux.
// Pick an OS tab and you get exactly the command for it — nothing else.
const OSES = ["macOS", "Windows", "Linux"] as const;
type OS = (typeof OSES)[number];

const INSTALL: Record<OS, { cmd: string; note: string }> = {
  macOS: { cmd: "npm install -g simapi-cli", note: "Requires Node 18 or newer." },
  Windows: { cmd: "npm install -g simapi-cli", note: "Requires Node 18 or newer." },
  Linux: { cmd: "brew install TaxCollector23/tap/simapi", note: "Requires Homebrew." },
};

function useCopy() {
  const [copied, setCopied] = useState<string | null>(null);
  const copy = (key: string, text: string) => {
    navigator.clipboard?.writeText(text);
    setCopied(key);
    setTimeout(() => setCopied((c) => (c === key ? null : c)), 1500);
  };
  return { copied, copy };
}

export function CodeSection() {
  const [os, setOs] = useState<OS>(OSES[0]);
  const { copied, copy } = useCopy();
  const { cmd, note } = INSTALL[os];

  return (
    <section className="relative border-b border-white/[0.06] py-24 sm:py-28">
      <div className="container-tight">
        <SectionHeader
          align="left"
          title={<>Install once. Validate every run.</>}
          lede="Pick your platform and run one command. The CLI puts the simapi command on your PATH and talks to the hosted API — from a terminal, a CI job, or a Node workflow."
        />

        <div className="mt-12 grid gap-px overflow-hidden border border-white/10 bg-white/10 lg:grid-cols-[0.9fr_1.1fr]">
          {/* ── Install panel — OS selector, one command per platform ──── */}
          <div className="flex flex-col bg-ink-900">
            <div className="flex items-center border-b border-white/[0.06]">
              {OSES.map((o) => (
                <button
                  key={o}
                  onClick={() => setOs(o)}
                  aria-pressed={o === os}
                  className={cn(
                    "relative px-4 py-2.5 text-[13px] font-medium transition-colors",
                    o === os ? "text-white" : "text-white/40 hover:text-white/70",
                  )}
                >
                  {o}
                  {o === os && <span className="absolute inset-x-3 -bottom-px h-px bg-accent-blue" />}
                </button>
              ))}
            </div>

            {/* The command for the selected OS */}
            <div className="flex items-center justify-between gap-3 border-b border-white/[0.06] px-4 py-5">
              <code className="min-w-0 truncate font-mono text-[13.5px] text-white/90">
                <span className="select-none text-accent-blueSoft">$ </span>
                {cmd}
              </code>
              <button
                onClick={() => copy(os, cmd)}
                aria-label={`Copy ${os} install command`}
                className="flex shrink-0 items-center gap-1.5 text-xs text-white/45 hover:text-white"
              >
                {copied === os ? <Check className="h-3.5 w-3.5 text-pass" /> : <Copy className="h-3.5 w-3.5" />}
                <span className="hidden sm:inline">{copied === os ? "Copied" : "Copy"}</span>
              </button>
            </div>

            <p className="px-4 py-3 text-xs text-white/45">{note}</p>

            {/* Verify step — the natural next line, no flag dump */}
            <div className="mt-auto border-t border-white/[0.06] px-4 py-4">
              <p className="text-[11px] uppercase tracking-wide text-white/30">Then</p>
              <code className="mt-1.5 block font-mono text-[12.5px] text-white/60">
                <span className="select-none text-accent-blueSoft">$ </span>
                simapi validate output.csv
              </code>
            </div>
          </div>

          {/* ── Live terminal ─────────────────────────────────────────── */}
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
// engine finds the R_air anchor across every row.

const CMD = "simapi dimensional cfd_output.csv";

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
      const line = OUTPUT_LINES[lineIdx - 1];
      const delay = line.text === "" ? 60 : lineIdx < 8 ? 140 : 90;
      setTimeout(streamLines, delay);
    }
    typeCmd();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="min-w-0 bg-ink-900" ref={ref}>
      <div className="flex items-center gap-2 border-b border-white/[0.06] px-4 py-2.5">
        <span className="h-3 w-3 rounded-full bg-white/15" />
        <span className="h-3 w-3 rounded-full bg-white/15" />
        <span className="h-3 w-3 rounded-full bg-white/15" />
        <span className="ml-2 font-mono text-xs text-white/40">simapi</span>
      </div>
      <div className="bg-black/40">
        <pre className="min-h-[420px] whitespace-pre-wrap p-5 font-mono text-[12.5px] leading-[1.55] sm:text-[13px]">
          <span className="text-accent-blueSoft">$ </span>
          <span className="text-white">{typedCmd}</span>
          {typedCmd.length < CMD.length && (
            <span className="inline-block w-[7px] translate-y-[1px] animate-pulse bg-white/80">&nbsp;</span>
          )}
          {typedCmd.length === CMD.length && "\n"}
          {OUTPUT_LINES.slice(0, linesShown).map((l, i) => (
            <span key={i} className={cn("block", l.cls ?? "text-white/70")}>
              {l.text || " "}
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
