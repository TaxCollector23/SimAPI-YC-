import { Hero } from "@/components/hero";
import { CodeSection } from "@/components/code-section";
import { Features } from "@/components/features";
import { Domains } from "@/components/domains";
import { BenchmarkStats } from "@/components/benchmark-stats";
import { Cta } from "@/components/cta";

export default function HomePage() {
  return (
    <>
      <Hero />
      <CodeSection />
      <Features />
      <Domains />
      <BenchmarkStats />
      <Cta />
    </>
  );
}
