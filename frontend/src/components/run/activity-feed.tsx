"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { AlertTriangle, CheckCircle2, CircleDot, FileText, Globe, Search, XCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { RunEvent } from "@/lib/api";
import { agentByKey } from "@/lib/agents";
import { cn } from "@/lib/utils";

function iconFor(ev: RunEvent) {
  if (ev.type === "run_failed") return XCircle;
  if (ev.type === "run_completed" || ev.type === "task_completed") return CheckCircle2;
  if (ev.level === "warning") return AlertTriangle;
  if (ev.type === "tool_called") {
    const m = ev.message ?? "";
    if (m.startsWith("Searching")) return Search;
    if (m.startsWith("Reading")) return Globe;
    return FileText;
  }
  return CircleDot;
}

function stamp(ev: RunEvent, start?: number) {
  if (!start) return "";
  const s = Math.max(0, Math.round(ev.ts - start));
  return `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, "0")}`;
}

export function ActivityFeed({ events, startedAt }: { events: RunEvent[]; startedAt?: number }) {
  const reduce = useReducedMotion();
  const scroller = useRef<HTMLDivElement>(null);
  const [pinned, setPinned] = useState(true);

  useEffect(() => {
    const el = scroller.current;
    if (el && pinned) el.scrollTo({ top: el.scrollHeight, behavior: reduce ? "auto" : "smooth" });
  }, [events.length, pinned, reduce]);

  const visible = events;

  return (
    <div className="relative">
      <div
        ref={scroller}
        onScroll={(e) => {
          const el = e.currentTarget;
          setPinned(el.scrollHeight - el.scrollTop - el.clientHeight < 48);
        }}
        className="max-h-[440px] overflow-y-auto overscroll-contain px-4 py-3 sm:px-5"
        tabIndex={0}
        aria-label="Live activity log"
      >
        {visible.length === 0 ? (
          <div className="space-y-3 py-2" aria-hidden>
            {[70, 55, 82].map((w) => (
              <div key={w} className="flex items-center gap-3">
                <div className="skeleton size-4 rounded-full" />
                <div className="skeleton h-3.5" style={{ width: `${w}%` }} />
              </div>
            ))}
          </div>
        ) : (
          <ol className="space-y-0.5 font-mono text-[13px]">
            <AnimatePresence initial={false}>
              {visible.map((ev, i) => {
                const Icon = iconFor(ev);
                const agent = agentByKey(ev.agent);
                const isTask = ev.type === "task_completed" || ev.type === "agent_started";
                const key = ev.seq ?? `${ev.type}-${i}`;
                return (
                  <motion.li
                    key={key}
                    initial={reduce ? false : { opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.2 }}
                    className={cn(
                      "grid grid-cols-[3.2rem_1rem_1fr] items-start gap-2 rounded-md px-1.5 py-1.5",
                      isTask && "bg-sunken/70",
                    )}
                  >
                    <span className="tabular-nums text-subtle">{stamp(ev, startedAt)}</span>
                    <Icon
                      aria-hidden
                      className={cn(
                        "mt-[3px] size-3.5",
                        ev.type === "run_failed" && "text-danger",
                        ev.level === "warning" && "text-accent-strong",
                        (ev.type === "task_completed" || ev.type === "run_completed") && "text-success",
                        ev.type === "tool_called" && "text-muted",
                      )}
                    />
                    <span className={cn("min-w-0 break-words", isTask ? "text-fg" : "text-muted")}>
                      {ev.type === "agent_started" ? (
                        <span className="font-sans font-medium text-fg">{agent?.name ?? "Agent"} started</span>
                      ) : (
                        <>
                          {agent && ev.type !== "tool_called" && ev.type !== "tool_result_summary" && (
                            <span className="font-sans font-medium text-fg">{agent.name}: </span>
                          )}
                          {ev.type === "tool_result_summary" && <span className="text-subtle">↳ </span>}
                          {ev.message}
                        </>
                      )}
                    </span>
                  </motion.li>
                );
              })}
            </AnimatePresence>
          </ol>
        )}
      </div>
      {!pinned && (
        <button
          type="button"
          onClick={() => setPinned(true)}
          className="absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full border border-border bg-elevated px-3 py-1 text-xs shadow-soft"
        >
          Jump to latest
        </button>
      )}
    </div>
  );
}
