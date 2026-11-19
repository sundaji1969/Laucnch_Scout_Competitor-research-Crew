"use client";

import { Check, Copy, FileDown, FileText, Plus } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { CitationContext, withCitations } from "@/components/report/citations";
import { PriceChart } from "@/components/report/price-chart";
import { Button } from "@/components/ui/button";
import { Badge, Card } from "@/components/ui/primitives";
import { api, type RunDetail } from "@/lib/api";
import { cn, domainOf, formatDuration } from "@/lib/utils";

const SECTIONS = [
  { id: "key-competitors", label: "Key competitors", match: /key competitors/i },
  { id: "complaints", label: "Customer complaints", match: /complain/i },
  { id: "market-gap", label: "Market gap", match: /market gap/i },
  { id: "positioning", label: "Positioning", match: /positioning/i },
  { id: "launch-plan", label: "30-day plan", match: /30.day|launch plan/i },
  { id: "sources", label: "Sources", match: /^\s*(\d+\.\s*)?sources/i },
];

function sectionId(text: string) {
  return SECTIONS.find((s) => s.match.test(text))?.id ?? text.toLowerCase().replace(/[^a-z0-9]+/g, "-");
}

function textOf(node: React.ReactNode): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(textOf).join("");
  if (node && typeof node === "object" && "props" in node) {
    return textOf((node as { props: { children?: React.ReactNode } }).props.children);
  }
  return "";
}

/** Split off the markdown "Sources" section: we render sources from structured data with anchors. */
function splitSources(md: string): string {
  const m = md.match(/\n#{1,3}\s*(\d+\.\s*)?Sources\b[\s\S]*$/i);
  return m ? md.slice(0, m.index) : md;
}

export function ReportView({ run }: { run: RunDetail }) {
  const [active, setActive] = useState<number | null>(null);
  const [current, setCurrent] = useState<string>(SECTIONS[0].id);
  const [copied, setCopied] = useState(false);

  const sourceMap = useMemo(() => new Map(run.sources.map((s) => [s.number, s.url])), [run.sources]);
  const body = useMemo(() => splitSources(run.report_markdown ?? ""), [run.report_markdown]);

  const focus = useCallback((n: number) => {
    setActive(n);
    const el = document.getElementById(`source-${n}`);
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
    el?.focus({ preventScroll: true });
  }, []);

  // scroll-spy for the table of contents
  useEffect(() => {
    const els = SECTIONS.map((s) => document.getElementById(s.id)).filter(Boolean) as HTMLElement[];
    const io = new IntersectionObserver(
      (entries) => {
        const vis = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (vis[0]) setCurrent(vis[0].target.id);
      },
      { rootMargin: "-90px 0px -45% 0px" },
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [body]);

  const components: Components = useMemo(
    () => ({
      h1: () => null,
      h2: ({ children }) => {
        const id = sectionId(textOf(children));
        return (
          <h2 id={id} className="scroll-mt-24">
            {children}
          </h2>
        );
      },
      p: ({ children }) => <p>{withCitations(children)}</p>,
      li: ({ children }) => <li>{withCitations(children)}</li>,
      strong: ({ children }) => <strong>{withCitations(children)}</strong>,
      table: ({ children }) => (
        <div
          className="not-prose -mx-4 my-6 overflow-x-auto sm:mx-0"
          tabIndex={0}
          role="region"
          aria-label="Competitor table"
        >
          <table className="w-full min-w-[720px] border-collapse text-left text-[14px] leading-snug">{children}</table>
        </div>
      ),
      thead: ({ children }) => <thead className="border-b-2 border-fg/80">{children}</thead>,
      th: ({ children }) => (
        <th
          scope="col"
          className="whitespace-nowrap px-3 py-2.5 text-[12px] font-semibold uppercase tracking-wide text-muted first:sticky first:left-0 first:bg-bg first:pl-4 sm:first:pl-3"
        >
          {children}
        </th>
      ),
      td: ({ children }) => (
        <td className="border-b border-border px-3 py-3 align-top first:sticky first:left-0 first:bg-bg first:pl-4 first:font-medium sm:first:pl-3">
          {withCitations(children)}
        </td>
      ),
      a: ({ href, children }) => (
        <a href={href} target="_blank" rel="noopener noreferrer">
          {children}
        </a>
      ),
    }),
    [],
  );

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(run.report_markdown ?? "");
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      /* clipboard blocked */
    }
  };

  const competitors = run.competitors?.competitors ?? [];

  return (
    <CitationContext.Provider value={{ sources: sourceMap, active, focus }}>
      <div className="container-page pb-8 pt-10 sm:pt-14">
        {/* Header */}
        <div className="flex flex-col gap-6 border-b border-border pb-8 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="success">Report ready</Badge>
              {run.duration_seconds ? (
                <span className="text-[13px] text-muted">
                  Researched in {formatDuration(run.duration_seconds)} · {competitors.length} competitors ·{" "}
                  {run.sources.length} sources
                </span>
              ) : null}
            </div>
            <h1 className="mt-4 font-display text-[34px] font-semibold leading-[1.1] tracking-tight text-balance sm:text-5xl">
              {run.business_idea}
              <span className="text-muted"> in {run.city}</span>
            </h1>
            <p className="mt-3 text-muted">For: {run.target_customer}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline" size="sm">
              <a href={api.reportUrl(run.id, "md")} download>
                <FileText aria-hidden /> Markdown
              </a>
            </Button>
            <Button asChild variant="outline" size="sm">
              <a href={api.reportUrl(run.id, "pdf")} download>
                <FileDown aria-hidden /> PDF
              </a>
            </Button>
            <Button variant="outline" size="sm" onClick={copy} aria-live="polite">
              {copied ? <Check aria-hidden /> : <Copy aria-hidden />} {copied ? "Copied" : "Copy"}
            </Button>
          </div>
        </div>

        <div className="grid gap-10 pt-10 lg:grid-cols-[200px_minmax(0,1fr)] lg:gap-14">
          {/* TOC */}
          <nav aria-label="Report sections" className="hidden lg:block">
            <div className="sticky top-24">
              <p className="eyebrow mb-3">On this page</p>
              <ol className="space-y-1 border-l border-border">
                {SECTIONS.map((s, i) => (
                  <li key={s.id}>
                    <a
                      href={`#${s.id}`}
                      aria-current={current === s.id ? "location" : undefined}
                      className={cn(
                        "-ml-px block border-l py-1.5 pl-4 text-[14px] transition-colors",
                        current === s.id
                          ? "border-accent font-medium text-fg"
                          : "border-transparent text-muted hover:text-fg",
                      )}
                    >
                      <span className="mr-2 font-mono text-[11px] text-subtle">{i + 1}</span>
                      {s.label}
                    </a>
                  </li>
                ))}
              </ol>
              <Button asChild variant="ghost" size="sm" className="mt-6 -ml-3">
                <Link href="/scout">
                  <Plus aria-hidden /> New research
                </Link>
              </Button>
            </div>
          </nav>

          <div className="min-w-0">
            {/* At a glance */}
            {run.strategy && (
              <section aria-labelledby="glance" className="mb-12 grid gap-4 xl:grid-cols-[1fr_1.15fr]">
                <h2 id="glance" className="sr-only">
                  At a glance
                </h2>
                <Card className="flex flex-col justify-between gap-6 p-6">
                  <div>
                    <p className="eyebrow">The gap</p>
                    <p className="mt-3 font-display text-xl font-medium leading-snug">{run.strategy.market_gap}</p>
                  </div>
                  <div className="rounded-[10px] bg-sunken p-4">
                    <p className="eyebrow">Your offer</p>
                    <p className="mt-2 text-[15px] font-medium leading-snug">{run.strategy.recommended_offer}</p>
                    <PriceLine price={run.strategy.recommended_price} value={run.strategy.recommended_price_value} />
                  </div>
                </Card>
                <Card className="p-6">
                  <p className="eyebrow mb-4">Price vs differentiation</p>
                  <PriceChart strategy={run.strategy} />
                </Card>
              </section>
            )}

            <article className="prose-report max-w-[760px]">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
                {body}
              </ReactMarkdown>

              <h2 id="sources" className="scroll-mt-24">
                6. Sources
              </h2>
              <ol className="!list-none !pl-0">
                {run.sources.map((s) => (
                  <li
                    key={s.number}
                    id={`source-${s.number}`}
                    tabIndex={-1}
                    className={cn(
                      "-mx-3 flex gap-3 rounded-[10px] px-3 py-2.5 text-[15px] outline-none transition-colors duration-500",
                      active === s.number ? "bg-accent-soft" : "",
                    )}
                  >
                    <span className="w-7 shrink-0 font-mono text-[13px] text-subtle">[{s.number}]</span>
                    <span className="min-w-0">
                      <span className="block">{s.title || domainOf(s.url)}</span>
                      <a href={s.url} target="_blank" rel="noopener noreferrer" className="break-all text-[13px]">
                        {s.url.replace(/^https?:\/\//, "")}
                      </a>
                    </span>
                  </li>
                ))}
              </ol>
            </article>
          </div>
        </div>
      </div>
    </CitationContext.Provider>
  );
}

const PRICE_RE = /^\s*(₹|Rs\.?|INR|\$|€|£)?\s*([\d,]+(?:\.\d+)?)\s*(.*)$/i;

/** Big headline price; any long qualifier ("per session (includes …)") goes underneath in body text. */
function PriceLine({ price, value }: { price: string; value?: number | null }) {
  if (price.length <= 22) {
    return <p className="mt-1 font-display text-2xl font-semibold text-accent-strong">{price}</p>;
  }
  const m = price.match(PRICE_RE);
  const symbol = m?.[1] && !/^(rs|inr)/i.test(m[1]) ? m[1] : "₹";
  const headline = m ? `${symbol}${m[2]}` : value ? `₹${value.toLocaleString("en-IN")}` : null;
  const rest = m ? m[3].trim() : price;
  if (!headline) {
    return <p className="mt-1 text-[15px] font-semibold text-accent-strong">{price}</p>;
  }
  return (
    <p className="mt-1">
      <span className="font-display text-2xl font-semibold text-accent-strong">{headline}</span>
      {rest && <span className="mt-1 block text-[13px] leading-snug text-muted">{rest}</span>}
    </p>
  );
}
