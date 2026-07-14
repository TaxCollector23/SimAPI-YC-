import type { Metadata } from "next";
import { DashboardApp } from "@/components/dashboard-app";

export const metadata: Metadata = {
  title: "Dashboard",
  description: "Manage API keys, view usage, and run simulation validations.",
  robots: { index: false, follow: false },
};

export default function DashboardPage() {
  return <DashboardApp />;
}
