import type { Metadata } from "next";
import { RunHistory } from "@/components/run/run-history";

export const metadata: Metadata = {
  title: "Reports",
  description: "Recent LaunchScout competitor research reports.",
  alternates: { canonical: "/runs" },
};

export default function RunsPage() {
  return (
    <div className="container-page py-12 sm:py-16">
      <p className="eyebrow">Reports</p>
      <h1 className="mt-3 font-display text-4xl font-semibold tracking-tight sm:text-5xl">Recent research</h1>
      <p className="mt-3 max-w-xl text-muted">Every report the crew has produced, newest first.</p>
      <RunHistory />
    </div>
  );
}
