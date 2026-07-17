import { Hero } from "@/components/hero";
import { CodeSection } from "@/components/code-section";
import { BenchmarkStats } from "@/components/benchmark-stats";
import { Cta } from "@/components/cta";

export default function HomePage() {
  return (
    <>
      <Hero />
      <CodeSection />
      <BenchmarkStats />
      <Cta />
    </>
  );
}
