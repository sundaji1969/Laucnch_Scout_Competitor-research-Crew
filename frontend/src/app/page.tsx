import {
  ArrowRight,
  FileDown,
  Lightbulb,
  MessageSquareWarning,
  PenLine,
  Search,
  ShieldCheck,
  Target,
} from "lucide-react";
import Link from "next/link";
import { IntentLink } from "@/components/intent-link";
import { SAMPLE } from "@/components/landing/sample";
import { Button } from "@/components/ui/button";
import { Badge, Card } from "@/components/ui/primitives";

const STEPS = [
  { icon: Lightbulb, title: "Idea", body: "Describe the business, the city and who you're selling to." },
  { icon: Search, title: "Research", body: "The Market Researcher finds 3–5 real competitors and their prices." },
  {
    icon: MessageSquareWarning,
    title: "Reviews",
    body: "The Review Analyst reads what their customers praise and complain about.",
  },
  { icon: Target, title: "Strategy", body: "The Strategy Analyst maps the market and finds the one clear gap." },
  { icon: PenLine, title: "Write", body: "The Report Writer turns it into a six-section, fully cited report." },
  { icon: FileDown, title: "Deliver", body: "Read it in the app, or download it as Markdown or PDF." },
];

export default function Home() {
  return (
    <>
      {/* Hero */}
      <section className="relative overflow-hidden">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[520px] bg-[radial-gradient(60%_60%_at_70%_0%,color-mix(in_oklab,var(--accent)_16%,transparent),transparent_70%)]"
        />
        <div className="container-page grid gap-12 pb-16 pt-14 sm:pt-20 lg:grid-cols-[1.05fr_1fr] lg:items-center lg:gap-16 lg:pb-24">
          <div>
            <Badge tone="accent" className="mb-6">
              <ShieldCheck className="size-3.5" aria-hidden /> Every price and claim is cited
            </Badge>
            <h1 className="font-display text-[40px] font-semibold leading-[1.05] tracking-[-0.02em] text-balance sm:text-[56px] lg:text-[64px]">
              Know your competitors <em className="font-normal text-accent-strong">before</em> you launch.
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted">
              Four AI agents find the real competitors in your city, what they charge, what customers complain
              about, and the gap nobody serves. Two to three days of research, done in a few minutes.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Button asChild size="lg">
                <IntentLink href="/scout">
                  Start your research <ArrowRight aria-hidden />
                </IntentLink>
              </Button>
              <Button asChild variant="outline" size="lg">
                <Link href="#sample">See a sample report</Link>
              </Button>
            </div>
            <dl className="mt-10 grid max-w-md grid-cols-3 gap-6 border-t border-border pt-6">
              {[
                ["~3 min", "per report"],
                ["4", "specialist agents"],
                ["6", "report sections"],
              ].map(([v, l]) => (
                <div key={l}>
                  <dt className="sr-only">{l}</dt>
                  <dd className="font-display text-2xl font-semibold">{v}</dd>
                  <dd className="mt-0.5 text-[13px] text-muted">{l}</dd>
                </div>
              ))}
            </dl>
          </div>

          <div className="animate-fade-up">
            <SamplePreview />
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how-it-works" className="border-y border-border bg-sunken/60 py-20">
        <div className="container-page">
          <p className="eyebrow">How it works</p>
          <h2 className="mt-3 max-w-2xl font-display text-3xl font-semibold tracking-tight sm:text-4xl">
            A research crew that works in sequence and shows its sources.
          </h2>
          <ol className="mt-12 grid gap-px overflow-hidden rounded-[var(--radius-card)] border border-border bg-border sm:grid-cols-2 lg:grid-cols-3">
            {STEPS.map((s, i) => (
              <li key={s.title} className="flex gap-4 bg-elevated p-6">
                <span className="flex size-10 shrink-0 items-center justify-center rounded-[10px] border border-border bg-bg">
                  <s.icon className="size-[18px] text-accent-strong" aria-hidden />
                </span>
                <div>
                  <p className="font-mono text-xs text-subtle">0{i + 1}</p>
                  <h3 className="mt-0.5 font-semibold">{s.title}</h3>
                  <p className="mt-1.5 text-[15px] leading-relaxed text-muted">{s.body}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* Sample + promise */}
      <section id="sample" className="container-page grid gap-12 pb-8 pt-20 lg:grid-cols-[1fr_1.1fr] lg:items-start">
        <div className="lg:sticky lg:top-28">
          <p className="eyebrow">What you get</p>
          <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight sm:text-4xl">
            Six sections. No filler.
          </h2>
          <ol className="mt-8 space-y-4 text-[15px]">
            {[
              ["Key competitors", "price per unit, channel, strength, weakness, source"],
              ["What customers complain about", "pain points tagged to each competitor"],
              ["Market gap", "the single opportunity nobody serves well"],
              ["Recommended positioning", "a one-line offer with a price"],
              ["30-day launch plan", "week-by-week actions"],
              ["Sources", "a numbered list. Every [n] links to a real page"],
            ].map(([t, d], i) => (
              <li key={t} className="flex gap-4">
                <span className="mt-0.5 font-mono text-xs text-subtle">{i + 1}.</span>
                <span>
                  <span className="font-medium">{t}</span>
                  <span className="text-muted">: {d}</span>
                </span>
              </li>
            ))}
          </ol>
          <p className="mt-8 max-w-md text-[15px] leading-relaxed text-muted">
            No invented competitors, prices or reviews. If a price isn&apos;t published, the report says{" "}
            <span className="font-medium text-fg">&ldquo;Not publicly listed&rdquo;</span> and links the page we
            checked. Every source must have been seen in a real search or page read during the run.
          </p>
          <Button asChild className="mt-8">
            <IntentLink href="/scout">
              Research my idea <ArrowRight aria-hidden />
            </IntentLink>
          </Button>
        </div>
        <SampleGapCard />
      </section>
    </>
  );
}

function SamplePreview() {
  return (
    <Card className="relative overflow-hidden p-0">
      <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-3.5">
        <div className="min-w-0">
          <p className="eyebrow">Sample report</p>
          <p className="truncate text-[15px] font-medium">
            {SAMPLE.idea} · {SAMPLE.city}
          </p>
        </div>
        <Badge tone="success" className="shrink-0">
          Completed
        </Badge>
      </div>
      <div className="px-5 py-4">
        <p className="text-[13px] font-medium text-muted">1. Key competitors</p>
        <table className="mt-3 w-full text-left text-sm">
          <caption className="sr-only">Sample competitor prices</caption>
          <thead>
            <tr className="border-b border-border text-xs text-subtle">
              <th scope="col" className="pb-2 font-medium">
                Competitor
              </th>
              <th scope="col" className="pb-2 font-medium">
                Price
              </th>
              <th scope="col" className="hidden pb-2 font-medium sm:table-cell">
                Channel
              </th>
            </tr>
          </thead>
          <tbody>
            {SAMPLE.rows.map((r) => (
              <tr key={r.name} className="border-b border-border/70 last:border-0">
                <td className="py-2.5 font-medium">{r.name}</td>
                <td className="py-2.5">
                  <span className="tabular-nums">{r.price}</span>{" "}
                  <span className="text-xs text-muted">{r.unit}</span>
                  {r.cite.map((c) => (
                    <sup key={c} className="ml-0.5 font-mono text-[10px] text-accent-strong">
                      [{c}]
                    </sup>
                  ))}
                </td>
                <td className="hidden py-2.5 text-muted sm:table-cell">{r.channel}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="border-t border-border bg-sunken/70 px-5 py-4">
        <p className="text-[13px] font-medium text-muted">4. Recommended positioning</p>
        <p className="mt-1.5 font-display text-lg font-semibold leading-snug">
          {SAMPLE.offer}, <span className="text-accent-strong">{SAMPLE.price}</span>
        </p>
      </div>
    </Card>
  );
}

function SampleGapCard() {
  return (
    <Card className="p-6 sm:p-8">
      <p className="eyebrow">3. Market gap · from the sample</p>
      <p className="mt-4 font-display text-2xl font-medium leading-snug">&ldquo;{SAMPLE.gap}&rdquo;</p>
      <div className="mt-8 border-t border-border pt-6">
        <p className="text-[13px] font-medium text-muted">6. Sources (excerpt)</p>
        <ol className="mt-3 space-y-2 text-sm">
          {SAMPLE.sources.map((s) => (
            <li key={s.n} className="flex gap-3">
              <span className="font-mono text-xs text-subtle">[{s.n}]</span>
              <a
                href={s.url}
                target="_blank"
                rel="noopener noreferrer"
                className="break-all text-accent-strong underline decoration-1 underline-offset-[3px] hover:decoration-2"
              >
                {s.url.replace(/^https?:\/\//, "")}
              </a>
            </li>
          ))}
        </ol>
      </div>
    </Card>
  );
}
