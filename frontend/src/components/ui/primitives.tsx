import * as React from "react";
import { cn } from "@/lib/utils";

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("rounded-[var(--radius-card)] border border-border bg-elevated shadow-soft", className)}
      {...props}
    />
  );
}

export function Badge({
  className,
  tone = "neutral",
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { tone?: "neutral" | "accent" | "success" | "danger" }) {
  const tones = {
    neutral: "border-border bg-sunken text-muted",
    accent: "border-transparent bg-accent-soft text-accent-strong",
    success: "border-transparent bg-[color-mix(in_oklab,var(--success)_14%,transparent)] text-success",
    danger: "border-transparent bg-[color-mix(in_oklab,var(--danger)_14%,transparent)] text-danger",
  } as const;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}

export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div aria-hidden className={cn("skeleton", className)} {...props} />;
}
