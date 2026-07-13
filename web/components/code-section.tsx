"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Copy, Check } from "lucide-react";
import { SectionHeader } from "./ui/section";
import { cn } from "@/lib/utils";

const snippets: Record<string, string> = {
  Python: `import simapi

result = simapi.validate(
    data="cfd_output.csv",
    simulation_type="aerodynamics",
    conditions={"velocity": 15.0, "altitude": 120.0},
)

print(result.status)            # "passed"
print(result.training_ready)    # True
print(result.drag_coefficient)  # StatResult(mean=0.312, std=0.018)`,
  JavaScript: `import { SimAPI } from "@simapi/sdk";

const client = new SimAPI({ apiKey: process.env.SIMAPI_API_KEY });

const result = await client.validate({
  data: cfdRun,
  simulationType: "aerodynamics",
  conditions: { velocity: 15.0, altitude: 120.0 },
});

console.log(result.status);          // "passed"
console.log(result.trainingReady);   // true`,
  TypeScript: `import { SimAPI, type ValidationResult } from "@simapi/sdk";

const client = new SimAPI({ apiKey: process.env.SIMAPI_API_KEY! });

const result: ValidationResult = await client.validate({
  data: cfdRun,
  simulationType: "aerodynamics",
  conditions: { velocity: 15, altitude: 120 },
});

if (result.status === "failed") throw new Error("Simulation rejected");`,
  cURL: `curl -X POST https://api.simapi.dev/v1/validate \\
  -H "X-API-Key: $SIMAPI_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "simulation_type": "aerodynamics",
    "conditions": { "velocity": 15.0 },
    "data": [{ "cd": 0.312, "cl": 0.847, "re": 415000 }]
  }'`,
};

export function CodeSection() {
  const langs = Object.keys(snippets);
  const [lang, setLang] = useState(langs[0]);
  const [copied, setCopied] = useState(false);

  function copy() {
    navigator.clipboard.writeText(snippets[lang]);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <section className="relative border-t border-white/[0.06] bg-ink-900/30 py-24 sm:py-32">
      <div className="container-tight">
        <SectionHeader
          eyebrow="Developer experience"
          title={<>Three lines to a trusted result</>}
          lede="A clean, typed client in every language your team ships in — generated from a single OpenAPI spec."
        />

        <div className="mx-auto mt-12 max-w-3xl">
          <div className="card overflow-hidden">
            <div className="flex items-center justify-between border-b border-white/[0.06] px-3 py-2">
              <div className="flex gap-1">
                {langs.map((l) => (
                  <button
                    key={l}
                    onClick={() => setLang(l)}
                    className={cn(
                      "rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
                      l === lang ? "bg-white/10 text-white" : "text-white/45 hover:text-white",
                    )}
                  >
                    {l}
                  </button>
                ))}
              </div>
              <button onClick={copy} className="flex items-center gap-1.5 px-2 text-xs text-white/45 hover:text-white">
                {copied ? <Check className="h-3.5 w-3.5 text-pass" /> : <Copy className="h-3.5 w-3.5" />}
                {copied ? "Copied" : "Copy"}
              </button>
            </div>
            <AnimatePresence mode="wait">
              <motion.pre
                key={lang}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
                className="overflow-x-auto p-5 font-mono text-[13px] leading-relaxed text-white/70"
              >
                <code>{snippets[lang]}</code>
              </motion.pre>
            </AnimatePresence>
          </div>
        </div>
      </div>
    </section>
  );
}
