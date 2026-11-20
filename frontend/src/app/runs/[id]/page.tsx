import type { Metadata } from "next";
import { RunView } from "@/components/run/run-view";

export const metadata: Metadata = {
  title: "Research report",
  robots: { index: false, follow: false },
};

export default async function RunPage({ params, searchParams }: PageProps<"/runs/[id]">) {
  const [{ id }, query] = await Promise.all([params, searchParams]);
  return <RunView runId={id} reused={query.reused === "1"} />;
}
