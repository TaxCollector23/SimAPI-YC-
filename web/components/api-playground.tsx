"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Play, Copy, Check, Loader2, Zap } from "lucide-react";
import { SectionHeader } from "./ui/section";
import { cn } from "@/lib/utils";

const DEFAULT_BODY = `{
  "simulation_type": "aerodynamics",
  "conditions": { "velocity": 15.0, "altitude": 120.0 },
  "data": [
    { "cd": 0.312, "cl": 0.847, "re": 415000, "ma": 0.044 },
    { "cd": 0.315, "cl": 0.851, "re": 418000, "ma": 0.044 },
    { "cd": 999.0,  "cl": 0.848, "re": 410000, "ma": 0.044 }
  ]
}`;

interface Result {
  status: string;
  code: number;
  ms: number;
  requestId: string;
  body: string;
}

/** Client-side mock of POST /v1/validate — inspects the payload for issues. */
function mockValidate(raw: string): Result {
  const requestId = crypto.randomUUID().replace(/-/g, "").slice(0, 12);
  const ms = Math.round((18 + Math.random() * 14) * 10) / 10;
  let parsed: { data?: Record<string, number>[]; simulation_type?: string };
  try {
    parsed = JSON.parse(raw);
  } catch {
    return {
      status: "error",
      code: 422,
      ms,
      requestId,
      body: JSON.stringify(
        { error: { code: "validation_failed", message: "Request body is not valid JSON.", request_id: requestId } },
        null,
        2,
      ),
    };
  }

  const rows = Array.isArray(parsed.data) ? parsed.data : [];
  const bounds: Record<string, [number, number]> = {
    cd: [0.0005, 3.5],
    cl: [-4.5, 6.0],
    ma: [0, 0.99],
  };
  const issues: { name: string; status: string; detail: string }[] = [];
  let excluded = 0;
  rows.forEach((row, i) => {
    for (const [k, [lo, hi]] of Object.entries(bounds)) {
      const v = row[k];
      if (v === undefined) continue;
      if (Number.isNaN(v) || v < lo || v > hi) {
        issues.push({
          name: `plausibility_${k}`,
          status: "failed",
          detail: `trial ${i}: ${k}=${v} outside [${lo}, ${hi}]`,
        });
        excluded++;
      }
    }
  });

  const status = issues.length ? "failed" : rows.length < 30 ? "warning" : "passed";
  const code = 200;
  const body = {
    job_id: requestId.slice(0, 8),
    status,
    confidence: status === "passed" ? "high" : status === "warning" ? "medium" : "low",
    trials_submitted: rows.length,
    trials_valid: rows.length - excluded,
    trials_excluded: excluded,
    training_ready: status !== "failed" && rows.length - excluded >= 2,
    all_checks: 287,
    passed: 287 - issues.length,
    warnings: status === "warning" ? 6 : 0,
    failed: issues.length,
    issues: issues.slice(0, 5),
    processing_ms: ms,
    ai_status: "pending",
  };
  return { status, code, ms, requestId, body: JSON.stringify(body, null, 2) };
}

export function ApiPlayground() {
  const [input, setInput] = useState(DEFAULT_BODY);
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  function submit() {
    setLoading(true);
    setResult(null);
    setTimeout(() => {
      setResult(mockValidate(input));
      setLoading(false);
    }, 480);
  }

  function copy() {
    if (!result) return;
    navigator.clipboard.writeText(result.body);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <section id="playground" className="relative py-24 sm:py-32">
      <div className="container-tight">
        <SectionHeader
          eyebrow="API playground"
          title={<>Try the API without leaving the page</>}
          lede="Edit the request body and validate. This runs a faithful client-side model of the real endpoint."
        />

        <div className="mx-auto mt-12 grid max-w-5xl gap-4 lg:grid-cols-2">
          {/* Request */}
          <div className="card overflow-hidden">
            <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-2.5">
              <div className="flex items-center gap-2 font-mono text-xs">
                <span className="rounded bg-accent-blue/15 px-1.5 py-0.5 text-accent-cyan">POST</span>
                <span className="text-white/50">/v1/validate</span>
              </div>
              <button onClick={submit} className="btn-accent !px-3.5 !py-1.5 !text-xs" disabled={loading}>
                {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                Validate
              </button>
            </div>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              spellCheck={false}
              className="h-[340px] w-full resize-none bg-transparent p-4 font-mono text-[12.5px] leading-relaxed text-white/80 outline-none"
            />
          </div>

          {/* Response */}
          <div className="card overflow-hidden">
            <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-2.5">
              <div className="flex items-center gap-2 font-mono text-xs">
                <span className="text-white/40">Response</span>
                {result && (
                  <span
                    className={cn(
                      "rounded px-1.5 py-0.5",
                      result.code < 400 ? "bg-pass/15 text-pass" : "bg-fail/15 text-fail",
                    )}
                  >
                    {result.code}
                  </span>
                )}
              </div>
              {result && (
                <div className="flex items-center gap-3 font-mono text-[11px] text-white/40">
                  <span className="flex items-center gap-1">
                    <Zap className="h-3 w-3 text-accent-cyan" /> {result.ms}ms
                  </span>
                  <button onClick={copy} className="flex items-center gap-1 hover:text-white">
                    {copied ? <Check className="h-3 w-3 text-pass" /> : <Copy className="h-3 w-3" />}
                  </button>
                </div>
              )}
            </div>
            <div className="h-[340px] overflow-auto p-4">
              {!result && !loading && (
                <p className="font-mono text-[12.5px] text-white/30">
                  {"// Click Validate to send the request…"}
                </p>
              )}
              {loading && (
                <p className="flex items-center gap-2 font-mono text-[12.5px] text-white/40">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" /> validating…
                </p>
              )}
              {result && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                  <JsonView text={result.body} />
                  <p className="mt-3 border-t border-white/[0.06] pt-3 font-mono text-[11px] text-white/35">
                    request_id: {result.requestId}
                  </p>
                </motion.div>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

/** Minimal JSON syntax highlighter. */
function JsonView({ text }: { text: string }) {
  const html = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g, (m) => {
      let cls = "text-emerald-300"; // string
      if (/^"/.test(m)) cls = /:$/.test(m) ? "text-sky-300" : "text-emerald-300";
      else if (/true|false/.test(m)) cls = "text-accent-violet";
      else if (/null/.test(m)) cls = "text-white/40";
      else cls = "text-amber-200";
      return `<span class="${cls}">${m}</span>`;
    });
  return (
    <pre
      className="whitespace-pre-wrap font-mono text-[12.5px] leading-relaxed text-white/60"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
