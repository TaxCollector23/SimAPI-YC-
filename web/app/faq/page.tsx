import type { Metadata } from "next";
import { Faq } from "@/components/faq";

export const metadata: Metadata = {
  title: "FAQ",
  description: "Answers to common questions about SimAPI — what it validates, formats, speed, privacy, and CI/CD.",
};

export default function FaqPage() {
  return (
    <div className="pt-16">
      <Faq />
    </div>
  );
}
