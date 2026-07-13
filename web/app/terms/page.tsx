import type { Metadata } from "next";
import { LegalPage } from "../legal/legal-content";

export const metadata: Metadata = { title: "Terms of Service" };

export default function TermsPage() {
  return (
    <LegalPage
      title="Terms of Service"
      updated="July 2026"
      sections={[
        { heading: "Acceptable use", body: "SimAPI is provided for validating engineering simulation data. You agree not to use it to attempt to disrupt the service, reverse-engineer other tenants' data, or exceed your plan's rate limits." },
        { heading: "Availability", body: "We target high availability but the service is provided as-is on non-enterprise plans. Enterprise agreements include a formal SLA." },
        { heading: "Validation results", body: "SimAPI provides an automated assessment to support your engineering judgment. It does not replace professional review or regulatory certification." },
        { heading: "Billing", body: "Paid plans bill monthly based on validation volume. You can cancel at any time; usage is prorated." },
        { heading: "Contact", body: "Questions about these terms? Email legal@simapi.dev." },
      ]}
    />
  );
}
