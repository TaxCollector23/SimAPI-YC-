"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Plus } from "lucide-react";
import { SectionHeader } from "./ui/section";
import { cn } from "@/lib/utils";

const faqs = [
  {
    q: "What exactly does SimAPI validate?",
    a: "Two layers. A deterministic engine runs 287 physics and statistical checks — plausibility bounds, conservation laws, dimensional and cross-variable consistency, outlier and distribution analysis — across 21 simulation domains. An optional AI layer then reasons over the full distributions to catch subtler issues the rules can't encode.",
  },
  {
    q: "Which simulation formats and tools are supported?",
    a: "CSV, JSON, VTK, NumPy, and OpenFOAM post-processing output, with aggressive column-alias normalization so results from ANSYS, OpenFOAM, STAR-CCM+, Fluent, COMSOL, SU2, and Abaqus validate without renaming columns.",
  },
  {
    q: "How fast is it?",
    a: "The deterministic layer returns in under 30ms for typical runs. The AI layer runs asynchronously and is polled separately, so your pipeline never blocks on it.",
  },
  {
    q: "Do I have to send my data to your servers?",
    a: "For enterprise, no. SimAPI ships as a container and supports private, in-VPC, and fully air-gapped deployments so proprietary simulation data never leaves your infrastructure.",
  },
  {
    q: "How does it fit into CI/CD?",
    a: "Call the API from any pipeline step and branch on the returned status — passed, warning, or failed. GitHub Actions, GitLab CI, and Jenkins examples are in the docs.",
  },
  {
    q: "Is the AI layer required?",
    a: "No. It's fully optional. Without an AI key configured, the deterministic engine runs exactly the same and the AI section reports as disabled — physics validation is never affected.",
  },
  {
    q: "What happens to invalid trials?",
    a: "They're excluded with a per-trial reason and severity, and the response reports an exclusion rate plus a training_ready flag so you know instantly whether the dataset is safe for ML.",
  },
];

export function Faq() {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <section id="faq" className="relative py-24 sm:py-32">
      <div className="container-tight">
        <SectionHeader eyebrow="FAQ" title={<>Questions, answered</>} />
        <div className="mx-auto mt-12 max-w-3xl divide-y divide-white/[0.07] overflow-hidden rounded-2xl border border-white/[0.07]">
          {faqs.map((f, i) => (
            <div key={i} className="bg-ink-900/40">
              <button
                onClick={() => setOpen(open === i ? null : i)}
                className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left"
              >
                <span className="text-[15px] font-medium text-white">{f.q}</span>
                <Plus
                  className={cn(
                    "h-4 w-4 shrink-0 text-white/40 transition-transform",
                    open === i && "rotate-45",
                  )}
                />
              </button>
              <AnimatePresence initial={false}>
                {open === i && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
                    className="overflow-hidden"
                  >
                    <p className="px-5 pb-5 text-sm leading-relaxed text-white/55">{f.a}</p>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
