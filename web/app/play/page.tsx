import type { Metadata } from "next";
import { ValidationDashboard } from "@/components/validation-dashboard";

export const metadata: Metadata = {
  title: "Playground",
  description: "Run a simulation validation in the browser — free, no account required.",
};

// Public playground, no login required — same ValidationDashboard component
// the authenticated dashboard uses, so behavior always matches the backend
// exactly (same engine, same checks). The authenticated /dashboard version
// additionally saves run history; this one doesn't require an account.
export default function PlayPage() {
  return (
    <div className="container-tight pt-28 pb-24">
      <ValidationDashboard />
    </div>
  );
}
