import { Hero } from "@/components/hero";
import { InteractiveDemo } from "@/components/interactive-demo";
import { ApiPlayground } from "@/components/api-playground";
import { Workflow } from "@/components/workflow";
import { Features } from "@/components/features";
import { UseCases } from "@/components/use-cases";
import { CodeSection } from "@/components/code-section";
import { SocialProof } from "@/components/social-proof";
import { Faq } from "@/components/faq";
import { Cta } from "@/components/cta";

export default function HomePage() {
  return (
    <>
      <Hero />
      <InteractiveDemo />
      <Workflow />
      <Features />
      <ApiPlayground />
      <UseCases />
      <CodeSection />
      <SocialProof />
      <Faq />
      <Cta />
    </>
  );
}
