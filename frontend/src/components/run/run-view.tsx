"use client";

import { AlertCircle, ArrowLeft, RefreshCw, WifiOff } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ReportView } from "@/components/report/report-view";
import { ActivityFeed } from "@/components/run/activity-feed";
import { AgentStepper } from "@/components/run/agent-stepper";
import { Button } from "@/components/ui/button";
import { Badge, Card, Skeleton } from "@/components/ui/primitives";
import { MANAGER, agentByKey } from "@/lib/agents";
import { api, ApiError, type RunDetail } from "@/lib/api";
import { useRunEvents } from "@/lib/use-run-events";
import { formatDuration } from "@/lib/utils";

export function RunView({ runId, reused = false }: { runId: string; reused?: boolean }) {
  const [run, setRun] = useState<RunDetail | null>(null);
  const [loadError, setLoadError] = useState<{ status: number; message: string } | null>(null);

  const [reloadKey, setReloadKey] = useState(0);
  const load = useCallback(() => setReloadKey((k) => k + 1), []);

  useEffect(() => {
    let cancelled = false;
    api
      .getRun(runId)
      .then((r) => {
        if (cancelled) return;
        setRun(r);
        setLoadError(null);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        const err = e instanceof ApiError ? e : new ApiError("Couldn't load this run.", 0);
        setLoadError({ status: err.status, message: err.message });
      });
    return () => {
      cancelled = true;
    };
  }, [runId, reloadKey]);

  const live = !!run && (run.status === "queued" || run.status === "running");
  const state = useRunEvents(runId, live);

  // When the stream reports a terminal event, fetch the finished run (report + structured data).
  useEffect(() => {
    if (!state.terminal) return;
    let tries = 0;
    const fetchFinal = async () => {
      const r = await api.getRun(runId).catch(() => null);
      if (r && r.status !== "queued" && r.status !== "running") setRun(r);
      else if (tries++ < 5) setTimeout(fetchFinal, 800);
    };
    fetchFinal();
  }, [state.terminal, runId]);

  if (loadError) return <LoadError {...loadError} onRetry={load} />;
  if (!run) return <RunSkeleton />;
  if (run.status === "completed" && run.report_markdown) return <ReportView run={run} reused={reused} />;
  if (run.status === "failed") return <Failed run={run} message={state.terminal?.message ?? run.error} />;

  return <LiveRun run={run} state={state} />;
}

function LiveRun({ run, state }: { run: RunDetail; state: ReturnType<typeof useRunEvents> }) {
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => clearInterval(t);
  }, []);
  const started = state.startedAt ?? (run.started_at ? Date.parse(run.started_at) / 1000 : undefined);
  const elapsed = started ? now - started : 0;
  const active = agentByKey(state.activeAgent);
  const finishing = state.terminal?.type === "run_completed";
  const managed = state.events.some((e) => e.agent === MANAGER.key);

  return (
    <div className="container-page py-10 sm:py-14">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="max-w-3xl">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="accent">
              <span className="relative flex size-2" aria-hidden>
                <span className="absolute inline-flex size-full animate-ping rounded-full bg-accent opacity-60" />
                <span className="relative inline-flex size-2 rounded-full bg-accent" />
              </span>
              {run.status === "queued" && !state.events.length ? "In queue" : finishing ? "Finishing up" : "Researching"}
            </Badge>
            {managed && <Badge tone="neutral">Coordinated by {MANAGER.name}</Badge>}
            {state.connection === "reconnecting" && (
              <Badge tone="neutral">
                <WifiOff className="size-3" aria-hidden /> Reconnecting…
              </Badge>
            )}
          </div>
          <h1 className="mt-4 font-display text-3xl font-semibold leading-tight tracking-tight text-balance sm:text-[44px]">
            {run.business_idea} <span className="text-muted">in {run.city}</span>
          </h1>
          <p className="mt-2 text-muted">For: {run.target_customer}</p>
        </div>
        <div className="shrink-0 text-left sm:text-right">
          <p className="eyebrow">Elapsed</p>
          <p className="font-display text-3xl font-semibold tabular-nums" aria-hidden>
            {formatDuration(elapsed)}
          </p>
        </div>
      </div>

      <p className="sr-only" aria-live="polite" aria-atomic="true">
        {finishing
          ? "Research complete. Loading your report."
          : active
            ? `${active.name} is working.`
            : run.status === "queued"
              ? "Your research is in the queue."
              : ""}
      </p>

      <div className="mt-10">
        <AgentStepper agents={state.agents} />
      </div>

      <Card className="mt-6 overflow-hidden p-0">
        <div className="flex items-center justify-between border-b border-border px-4 py-3 sm:px-5">
          <h2 className="text-[15px] font-medium">Live activity</h2>
          <span className="font-mono text-xs text-subtle">
            {state.events.filter((e) => e.type === "tool_called").length} tool calls
          </span>
        </div>
        <ActivityFeed events={state.events} startedAt={state.startedAt} />
      </Card>
      <p className="mt-4 text-[13px] text-muted">
        You can leave this page. The research keeps running and the report will be in{" "}
        <Link href="/runs" className="underline underline-offset-2">
          Reports
        </Link>
        .
      </p>
    </div>
  );
}

function Failed({ run, message }: { run: RunDetail; message?: string | null }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const retry = async () => {
    setBusy(true);
    setErr(null);
    try {
      const { run_id } = await api.createRun({
        business_idea: run.business_idea,
        city: run.city,
        target_customer: run.target_customer,
        known_competitors: run.known_competitors ?? [],
      });
      router.push(`/runs/${run_id}`);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Couldn't restart. Please try again.");
      setBusy(false);
    }
  };
  return (
    <div className="container-page max-w-2xl py-20">
      <Card className="p-8">
        <AlertCircle className="size-8 text-danger" aria-hidden />
        <h1 className="mt-4 font-display text-3xl font-semibold">This research didn&apos;t finish</h1>
        <p className="mt-2 text-muted">
          {run.business_idea} in {run.city}
        </p>
        <p className="mt-6 rounded-[10px] bg-sunken p-4 text-sm leading-relaxed">
          {message || "The crew stopped unexpectedly."}
        </p>
        <p className="mt-4 text-sm text-muted">
          Searches sometimes get rate-limited or a site blocks us. Running it again usually works.
        </p>
        {err && (
          <p role="alert" className="mt-4 text-sm text-danger">
            {err}
          </p>
        )}
        <div className="mt-8 flex flex-wrap gap-3">
          <Button onClick={retry} disabled={busy}>
            <RefreshCw className={busy ? "animate-spin" : ""} aria-hidden /> Run it again
          </Button>
          <Button asChild variant="outline">
            <Link href="/scout">Edit the idea</Link>
          </Button>
        </div>
      </Card>
    </div>
  );
}

function LoadError({ status, message, onRetry }: { status: number; message: string; onRetry: () => void }) {
  const notFound = status === 404;
  return (
    <div className="container-page max-w-xl py-24 text-center">
      <p className="eyebrow">{notFound ? "404" : "Connection problem"}</p>
      <h1 className="mt-3 font-display text-3xl font-semibold">
        {notFound ? "We couldn't find that report" : "Couldn't load this report"}
      </h1>
      <p className="mt-3 text-muted">{notFound ? "The link may be mistyped, or the report was removed." : message}</p>
      <div className="mt-8 flex justify-center gap-3">
        {!notFound && (
          <Button onClick={onRetry}>
            <RefreshCw aria-hidden /> Try again
          </Button>
        )}
        <Button asChild variant="outline">
          <Link href="/runs">
            <ArrowLeft aria-hidden /> All reports
          </Link>
        </Button>
      </div>
    </div>
  );
}

function RunSkeleton() {
  return (
    <div className="container-page py-14" aria-busy="true" aria-label="Loading report">
      <Skeleton className="h-6 w-28 rounded-full" />
      <Skeleton className="mt-5 h-12 w-3/4" />
      <Skeleton className="mt-3 h-5 w-1/3" />
      <div className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-32 rounded-[12px]" />
        ))}
      </div>
      <Skeleton className="mt-6 h-72 rounded-[14px]" />
    </div>
  );
}
