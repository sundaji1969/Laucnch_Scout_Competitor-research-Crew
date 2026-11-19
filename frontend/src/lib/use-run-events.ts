"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { api, type AgentKey, type RunEvent } from "./api";

export type ConnectionState = "connecting" | "open" | "reconnecting" | "closed";

export interface AgentProgress {
  status: "waiting" | "active" | "done";
  startedAt?: number;
  finishedAt?: number;
  summary?: string;
}

export interface RunEventsState {
  events: RunEvent[];
  connection: ConnectionState;
  agents: Record<AgentKey, AgentProgress>;
  activeAgent?: AgentKey;
  terminal?: RunEvent;
  startedAt?: number;
}

const AGENT_ORDER: AgentKey[] = ["market_researcher", "review_analyst", "strategy_analyst", "report_writer"];
const MAX_BACKOFF_MS = 15000;

/**
 * Subscribes to a run's Server-Sent Events stream.
 * - De-duplicates by `seq` and keeps events sorted.
 * - Reconnects with exponential backoff, resuming after the last seq it saw.
 * - Stops once a terminal event (run_completed / run_failed) arrives.
 */
export function useRunEvents(runId: string, enabled = true): RunEventsState {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const seen = useRef<Set<number>>(new Set());
  const lastSeq = useRef(0);
  const done = useRef(false);

  useEffect(() => {
    if (!enabled) return;
    let es: EventSource | null = null;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let attempt = 0;
    let cancelled = false;

    const connect = () => {
      if (cancelled || done.current) return;
      es = new EventSource(api.eventsUrl(runId, lastSeq.current || undefined));
      es.onopen = () => {
        attempt = 0;
        setConnection("open");
      };
      es.onmessage = (msg) => {
        let ev: RunEvent;
        try {
          ev = JSON.parse(msg.data) as RunEvent;
        } catch {
          return;
        }
        if (ev.seq) {
          if (seen.current.has(ev.seq)) return;
          seen.current.add(ev.seq);
          lastSeq.current = Math.max(lastSeq.current, ev.seq);
        }
        setEvents((prev) => {
          const next = [...prev, ev];
          next.sort((a, b) => (a.seq ?? Number.MAX_SAFE_INTEGER) - (b.seq ?? Number.MAX_SAFE_INTEGER));
          return next;
        });
        if (ev.type === "run_completed" || ev.type === "run_failed") {
          done.current = true;
          es?.close();
          setConnection("closed");
        }
      };
      es.onerror = () => {
        es?.close();
        if (done.current || cancelled) return;
        setConnection("reconnecting");
        const delay = Math.min(MAX_BACKOFF_MS, 1000 * 2 ** attempt) + Math.random() * 400;
        attempt += 1;
        retry = setTimeout(connect, delay);
      };
    };

    connect();
    return () => {
      cancelled = true;
      clearTimeout(retry);
      es?.close();
    };
  }, [runId, enabled]);

  return useMemo(() => {
    const agents = Object.fromEntries(
      AGENT_ORDER.map((k) => [k, { status: "waiting" } as AgentProgress]),
    ) as Record<AgentKey, AgentProgress>;
    let activeAgent: AgentKey | undefined;
    let terminal: RunEvent | undefined;
    for (const ev of events) {
      const key = ev.agent as AgentKey | undefined;
      if (ev.type === "agent_started" && key && agents[key]) {
        // previous agents are done once a later one starts (sequential process)
        const idx = AGENT_ORDER.indexOf(key);
        AGENT_ORDER.slice(0, idx).forEach((k) => {
          if (agents[k].status !== "done") agents[k] = { ...agents[k], status: "done", finishedAt: ev.ts };
        });
        if (agents[key].status !== "done") {
          agents[key] = { ...agents[key], status: "active", startedAt: agents[key].startedAt ?? ev.ts };
        }
        activeAgent = key;
      }
      if (ev.type === "task_completed" && key && agents[key]) {
        agents[key] = { ...agents[key], status: "done", finishedAt: ev.ts, summary: ev.message };
        if (activeAgent === key) activeAgent = undefined;
      }
      if (ev.type === "run_completed" || ev.type === "run_failed") {
        terminal = ev;
        activeAgent = undefined;
      }
    }
    if (terminal?.type === "run_completed") {
      AGENT_ORDER.forEach((k) => (agents[k] = { ...agents[k], status: "done" }));
    }
    return {
      events,
      connection,
      agents,
      activeAgent,
      terminal,
      startedAt: events[0]?.ts,
    };
  }, [events, connection]);
}
