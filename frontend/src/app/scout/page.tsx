import type { Metadata } from "next";
import { ScoutForm } from "@/components/scout/scout-form";
import { Card } from "@/components/ui/primitives";
import { AGENTS } from "@/lib/agents";

export const metadata: Metadata = {
  title: "New research",
  description: "Describe your business idea, city and customer. Four AI agents will research your market.",
  alternates: { canonical: "/scout" },
};

export default function ScoutPage() {
  return (
    <div className="container-page grid gap-12 py-12 sm:py-16 lg:grid-cols-[1.35fr_1fr] lg:gap-16">
      <div>
        <p className="eyebrow">New research</p>
        <h1 className="mt-3 font-display text-4xl font-semibold tracking-tight sm:text-5xl">
          What are you launching?
        </h1>
        <p className="mt-4 max-w-xl text-lg text-muted">
          Three details is all the crew needs. The more specific you are, the sharper the competitors.
        </p>
        <Card className="mt-10 p-5 sm:p-8">
          <ScoutForm />
        </Card>
      </div>

      <aside aria-labelledby="crew-heading" className="lg:pt-28">
        <h2 id="crew-heading" className="eyebrow">
          Your research crew
        </h2>
        <ol className="mt-5 space-y-3">
          {AGENTS.map((a, i) => (
            <li key={a.key} className="flex gap-4 rounded-[12px] border border-border bg-elevated/60 p-4">
              <span className="flex size-10 shrink-0 items-center justify-center rounded-full border border-border-strong bg-bg font-mono text-xs font-semibold">
                {a.initials}
              </span>
              <div>
                <p className="text-[15px] font-medium">
                  <span className="mr-2 font-mono text-xs text-subtle">{i + 1}</span>
                  {a.name}
                </p>
                <p className="mt-1 text-sm leading-relaxed text-muted">{a.role}</p>
              </div>
            </li>
          ))}
        </ol>
      </aside>
    </div>
  );
}
