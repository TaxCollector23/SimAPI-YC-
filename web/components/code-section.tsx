"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Copy, Check } from "lucide-react";
import { SectionHeader } from "./ui/section";
import { cn } from "@/lib/utils";

const install: Record<string, string> = {
  Python: "pip install simapi",
  "Node / CLI": "npm install -g simapi",
  Homebrew: "brew install simapi   # coming soon",
};

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
  JavaScript: `import { SimAPI } from "simapi";

const client = new SimAPI(process.env.SIMAPI_API_KEY);

const result = await client.validate(cfdRun, {
  simulationType: "aerodynamics",
  conditions: { velocity: 15.0, altitude: 120.0 },
});

console.log(result.status);          // "passed"
console.log(result.trials_valid);    // 196`,
  TypeScript: `import { SimAPI, type ValidationResult } from "simapi";

const client = new SimAPI(process.env.SIMAPI_API_KEY!);

const result: ValidationResult = await client.validate(cfdRun, {
  simulationType: "aerodynamics",
  conditions: { velocity: 15, altitude: 120 },
});

if (result.status === "failed") throw new Error("Simulation rejected");`,
  cURL: `curl -X POST https://sim-api.vercel.app/api/v1/validate \\
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
  const installTabs = Object.keys(install);
  const [inst, setInst] = useState(installTabs[0]);
  const [copied, setCopied] = useState<"install" | "code" | null>(null);

  function copy(which: "install" | "code", text: string) {
    navigator.clipboard.writeText(text);
    setCopied(which);
    setTimeout(() => setCopied(null), 1500);
  }

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
              <div className="flex gap-1">
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
                onClick={() => copy("install", install[inst])}
                className="flex items-center gap-1.5 px-2 text-xs text-white/45 hover:text-white"
              >
                {copied === "install" ? <Check className="h-3.5 w-3.5 text-pass" /> : <Copy className="h-3.5 w-3.5" />}
              </button>
            </div>
            <pre className="overflow-x-auto p-4 font-mono text-[13px] text-white/75">
              <span className="text-accent-cyan">$ </span>{install[inst]}
            </pre>
          </div>

          {/* Usage */}
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
              <button
                onClick={() => copy("code", snippets[lang])}
                className="flex items-center gap-1.5 px-2 text-xs text-white/45 hover:text-white"
              >
                {copied === "code" ? <Check className="h-3.5 w-3.5 text-pass" /> : <Copy className="h-3.5 w-3.5" />}
                {copied === "code" ? "Copied" : "Copy"}
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
