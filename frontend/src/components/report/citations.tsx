"use client";

import { createContext, isValidElement, useContext, type ReactNode } from "react";
import { cn, domainOf } from "@/lib/utils";

interface CitationCtx {
  sources: Map<number, string>;
  active: number | null;
  focus: (n: number) => void;
}

export const CitationContext = createContext<CitationCtx>({
  sources: new Map(),
  active: null,
  focus: () => {},
});

const CITE_RE = /\[(\d{1,3})\]/g;

export function CitationChip({ n }: { n: number }) {
  const { sources, focus, active } = useContext(CitationContext);
  const url = sources.get(n);
  const label = url ? `Source ${n}: ${domainOf(url)}` : `Source ${n}`;
  return (
    <button
      type="button"
      onClick={() => focus(n)}
      title={url ? domainOf(url) : undefined}
      aria-label={label}
      className={cn(
        "mx-[1px] inline-flex h-[18px] min-w-[20px] -translate-y-[1px] items-center justify-center rounded-[5px] border px-1 align-middle font-mono text-[10.5px] font-semibold leading-none transition-colors",
        active === n
          ? "border-accent bg-accent text-accent-fg"
          : "border-border-strong bg-sunken text-accent-strong hover:border-accent hover:bg-accent-soft",
      )}
    >
      {n}
    </button>
  );
}

/** Replace "[n]" in string children with clickable citation chips (recurses into elements). */
export function withCitations(children: ReactNode): ReactNode {
  if (typeof children === "string") {
    const parts: ReactNode[] = [];
    let last = 0;
    for (const m of children.matchAll(CITE_RE)) {
      const idx = m.index ?? 0;
      if (idx > last) parts.push(children.slice(last, idx));
      parts.push(<CitationChip key={`c${idx}`} n={Number(m[1])} />);
      last = idx + m[0].length;
    }
    if (!parts.length) return children;
    if (last < children.length) parts.push(children.slice(last));
    return parts;
  }
  if (Array.isArray(children)) return children.map((c, i) => <Frag key={i}>{withCitations(c)}</Frag>);
  if (isValidElement(children)) return children;
  return children;
}

function Frag({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
