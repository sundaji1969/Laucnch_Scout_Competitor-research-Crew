"use client";

import { ArrowRight, FileSearch, MapPin, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge, Card, Skeleton } from "@/components/ui/primitives";
import { api, ApiError, type RunSummary } from "@/lib/api";
import { formatDuration, formatRelative } from "@/lib/utils";

const STATUS: Record<RunSummary["status"], { label: string; tone: "neutral" | "accent" | "success" | "danger" }> = {
  queued: { label: "Queued", tone: "neutral" },
  running: { label: "Running", tone: "accent" },
  completed: { label: "Ready", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
};

export function RunHistory() {
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [reloadKey, setReloadKey] = useState(0);
  const load = useCallback(() => {
    setError(null);
    setReloadKey((k) => k + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    api
      .listRuns(30)
      .then((r) => !cancelled && setRuns(r.items))
      .catch((e: unknown) => !cancelled && setError(e instanceof ApiError ? e.message : "Couldn't load reports."));
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  if (error)
    return (
      <div className="mt-12 rounded-[14px] border border-border p-8 text-center">
        <p className="text-muted">{error}</p>
        <Button className="mt-4" variant="outline" onClick={load}>
          <RefreshCw aria-hidden /> Try again
        </Button>
      </div>
    );

  if (!runs)
    return (
      <ul className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-busy="true" aria-label="Loading reports">
        {Array.from({ length: 6 }).map((_, i) => (
          <li key={i}>
            <Skeleton className="h-[188px] rounded-[14px]" />
          </li>
        ))}
      </ul>
    );

  if (!runs.length)
    return (
      <div className="mt-12 flex flex-col items-center rounded-[14px] border border-dashed border-border-strong px-6 py-16 text-center">
        <FileSearch className="size-10 text-subtle" aria-hidden />
        <h2 className="mt-4 font-display text-2xl font-semibold">No reports yet</h2>
        <p className="mt-2 max-w-sm text-muted">Start your first research. It takes about three minutes.</p>
        <Button asChild className="mt-6">
          <Link href="/scout">
            Start research <ArrowRight aria-hidden />
          </Link>
        </Button>
      </div>
    );

  return (
    <ul className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {runs.map((r) => {
        const s = STATUS[r.status];
        return (
          <li key={r.id}>
            <Link href={`/runs/${r.id}`} className="group block h-full rounded-[var(--radius-card)]">
              <Card className="flex h-full flex-col p-5 transition-[border-color,transform] duration-200 group-hover:-translate-y-0.5 group-hover:border-border-strong">
                <div className="flex items-center justify-between gap-2">
                  <Badge tone={s.tone}>{s.label}</Badge>
                  <span className="text-xs text-subtle">{formatRelative(r.created_at)}</span>
                </div>
                <h2 className="mt-4 line-clamp-2 font-display text-xl font-semibold leading-snug">{r.business_idea}</h2>
                <p className="mt-1.5 flex items-center gap-1.5 text-sm text-muted">
                  <MapPin className="size-3.5" aria-hidden /> {r.city}
                </p>
                {(r.status === "running" || r.status === "queued") && (
                  <p className="mt-4 text-sm text-muted">
                    {r.status === "running" ? "The crew is researching this now." : "Waiting for a free agent crew."}
                  </p>
                )}
                {r.market_gap && (
                  <p className="mt-4 line-clamp-2 text-sm leading-relaxed text-muted">
                    <span className="font-medium text-fg">Gap: </span>
                    {r.market_gap}
                  </p>
                )}
                <div className="mt-auto flex items-center justify-between pt-5 text-xs text-subtle">
                  <span>
                    {r.status === "completed"
                      ? `${r.competitor_count} competitors${r.duration_seconds ? ` · ${formatDuration(r.duration_seconds)}` : ""}`
                      : r.status === "failed"
                        ? "Didn't finish"
                        : "In progress"}
                  </span>
                  <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" aria-hidden />
                </div>
              </Card>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
