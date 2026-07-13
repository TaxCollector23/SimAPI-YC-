import type { Metadata } from "next";
import { LegalPage } from "../legal/legal-content";

export const metadata: Metadata = { title: "Privacy Policy" };

export default function PrivacyPage() {
  return (
    <LegalPage
      title="Privacy Policy"
      updated="July 2026"
      sections={[
        { heading: "Data we process", body: "SimAPI processes the simulation data you submit solely to return a validation result. On enterprise plans with private deployment, your data never leaves your infrastructure." },
        { heading: "Retention", body: "Job results are retained transiently to support polling and reports, then evicted on a configurable TTL. You can request deletion at any time." },
        { heading: "Third parties", body: "The optional AI reasoning layer sends de-identified statistical summaries — never raw proprietary geometry — to the configured model provider. It can be disabled entirely." },
        { heading: "Security", body: "We use API-key authentication, rate limiting, encrypted transport, and secret scanning. See our security policy for responsible disclosure." },
        { heading: "Contact", body: "Questions about privacy? Email privacy@simapi.dev." },
      ]}
    />
  );
}
