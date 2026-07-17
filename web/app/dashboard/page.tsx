import type { Metadata } from "next";
import { Suspense } from "react";
import { DashboardApp } from "@/components/dashboard-app";

export const metadata: Metadata = {
  title: "Dashboard",
  description: "Manage API keys, view usage, and run the Playground.",
  robots: { index: false, follow: false },
};

export default function DashboardPage() {
  return (
    <Suspense>
      <DashboardApp />
    </Suspense>
  );
}
