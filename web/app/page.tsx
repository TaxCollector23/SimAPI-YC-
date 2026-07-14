import { Hero } from "@/components/hero";
import { CodeSection } from "@/components/code-section";
import { Features } from "@/components/features";
import { Cta } from "@/components/cta";

export default function HomePage() {
  return (
    <>
      <Hero />
      <CodeSection />
      <Features />
      <Cta />
    </>
  );
}
