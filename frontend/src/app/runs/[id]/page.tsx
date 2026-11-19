import type { Metadata } from "next";
import { RunView } from "@/components/run/run-view";

export const metadata: Metadata = {
  title: "Research report",
  robots: { index: false, follow: false },
};

export default async function RunPage({ params }: PageProps<"/runs/[id]">) {
  const { id } = await params;
  return <RunView runId={id} />;
}
