"use client";

import { motion, useReducedMotion } from "framer-motion";
import { Check } from "lucide-react";
import type { AgentKey } from "@/lib/api";
import { AGENTS } from "@/lib/agents";
import type { AgentProgress } from "@/lib/use-run-events";
import { cn, formatDuration } from "@/lib/utils";

export function AgentStepper({
  agents,
  failed,
}: {
  agents: Record<AgentKey, AgentProgress>;
  failed?: boolean;
}) {
  const reduce = useReducedMotion();
  return (
    <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" aria-label="Research crew progress">
      {AGENTS.map((a, i) => {
        const p = agents[a.key];
        const active = p.status === "active" && !failed;
        const done = p.status === "done";
        const took = p.startedAt && p.finishedAt ? p.finishedAt - p.startedAt : undefined;
        return (
          <li
            key={a.key}
            aria-current={active ? "step" : undefined}
            className={cn(
              "relative rounded-[12px] border p-4 transition-colors duration-300",
              active ? "border-accent bg-elevated shadow-soft" : "border-border bg-elevated/60",
            )}
          >
            <div className="flex items-center gap-3">
              <span
                className={cn(
                  "relative flex size-10 shrink-0 items-center justify-center rounded-full border font-mono text-xs font-semibold transition-colors",
                  done && "border-transparent bg-fg text-bg",
                  active && "border-accent bg-accent-soft text-accent-strong animate-pulse-ring",
                  !done && !active && "border-border-strong bg-bg text-subtle",
                )}
                aria-hidden
              >
                {done ? (
                  <motion.span initial={reduce ? false : { scale: 0.4 }} animate={{ scale: 1 }}>
                    <Check className="size-4" />
                  </motion.span>
                ) : (
                  a.initials
                )}
              </span>
              <div className="min-w-0">
                <p className="font-mono text-[11px] text-subtle">Agent {i + 1}</p>
                <p className="truncate text-[15px] font-medium">{a.name}</p>
              </div>
            </div>
            <p className="mt-3 text-[13px] leading-relaxed text-muted" aria-live="off">
              {active && <span className="font-medium text-accent-strong">Working… </span>}
              {done && p.summary ? (
                <span className="line-clamp-3">{p.summary}</span>
              ) : done ? (
                "Done"
              ) : active ? (
                <span className="line-clamp-2">{a.role}</span>
              ) : (
                "Waiting"
              )}
            </p>
            {done && took !== undefined && (
              <p className="mt-2 font-mono text-[11px] text-subtle">{formatDuration(took)}</p>
            )}
            {i < AGENTS.length - 1 && (
              <span
                aria-hidden
                className={cn(
                  "absolute -right-3 top-9 hidden h-px w-3 lg:block",
                  done ? "bg-fg" : "bg-border-strong",
                )}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}
