"use client";

import { X } from "lucide-react";
import { useId, useState } from "react";
import { cn } from "@/lib/utils";

interface ChipInputProps {
  value: string[];
  onChange: (next: string[]) => void;
  max?: number;
  placeholder?: string;
  describedBy?: string;
  id?: string;
}

/** Type a name and press Enter or comma to add it. Backspace on empty input removes the last chip. */
export function ChipInput({ value, onChange, max = 8, placeholder, describedBy, id }: ChipInputProps) {
  const [draft, setDraft] = useState("");
  const listId = useId();

  const add = (raw: string) => {
    const parts = raw
      .split(",")
      .map((p) => p.trim())
      .filter(Boolean);
    if (!parts.length) return;
    const next = [...value];
    for (const p of parts) {
      if (next.length >= max) break;
      if (p.length > 80) continue;
      if (!next.some((v) => v.toLowerCase() === p.toLowerCase())) next.push(p);
    }
    onChange(next);
    setDraft("");
  };

  return (
    <div
      className={cn(
        "flex min-h-12 flex-wrap items-center gap-2 rounded-[10px] border border-border-strong bg-elevated px-3 py-2",
        "focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-[var(--accent-ring)]",
      )}
    >
      <ul id={listId} aria-label="Known competitors" className="contents">
        {value.map((chip) => (
          <li
            key={chip}
            className="inline-flex items-center gap-1 rounded-full bg-sunken py-1 pl-3 pr-1 text-sm"
          >
            {chip}
            <button
              type="button"
              onClick={() => onChange(value.filter((v) => v !== chip))}
              className="rounded-full p-0.5 text-muted hover:bg-border hover:text-fg"
              aria-label={`Remove ${chip}`}
            >
              <X className="size-3.5" aria-hidden />
            </button>
          </li>
        ))}
      </ul>
      <input
        id={id}
        value={draft}
        disabled={value.length >= max}
        onChange={(e) => {
          const v = e.target.value;
          if (v.endsWith(",")) add(v);
          else setDraft(v);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            add(draft);
          } else if (e.key === "Backspace" && !draft && value.length) {
            onChange(value.slice(0, -1));
          }
        }}
        onBlur={() => add(draft)}
        onPaste={(e) => {
          const text = e.clipboardData.getData("text");
          if (text.includes(",")) {
            e.preventDefault();
            add(text);
          }
        }}
        placeholder={value.length >= max ? `Up to ${max} competitors` : placeholder}
        aria-describedby={describedBy}
        className="min-w-[10ch] flex-1 bg-transparent py-1 text-[15px] outline-none placeholder:text-subtle"
      />
    </div>
  );
}
