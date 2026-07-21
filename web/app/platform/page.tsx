import type { Metadata } from "next";
import { Features } from "@/components/features";
import { BenchmarkStats } from "@/components/benchmark-stats";
import { Cta } from "@/components/cta";

export const metadata: Metadata = {
  title: "Platform",
  description:
    "The SimAPI validation platform: deterministic physics checks, AI-assisted review, regression detection, CI/CD integration, and more.",
};

export default function PlatformPage() {
  return (
    <div className="pt-16">
      <Features />
      <BenchmarkStats />
      <Cta />
    </div>
  );
}
