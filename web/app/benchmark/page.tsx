import type { Metadata } from "next";
import { BenchmarkStats } from "@/components/benchmark-stats";

export const metadata: Metadata = {
  title: "Benchmarks",
  description: "SimAPI benchmark results — detection precision, recall, and model impact.",
};

export default function BenchmarkPage() {
  return (
    <div className="pt-16">
      <BenchmarkStats />
    </div>
  );
}
