/** Typed client for the LaunchScout API. No secrets ever reach the browser. */

export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "").replace(/\/$/, "");

export type RunStatus = "queued" | "running" | "completed" | "failed";

export interface Competitor {
  name: string;
  website?: string | null;
  price_per_unit: string;
  price_value?: number | null;
  currency?: string;
  offers?: string[];
  sales_channels?: string[];
  notes?: string;
  source_urls: string[];
}

export interface MatrixRow {
  competitor: string;
  price_per_unit: string;
  price_value?: number | null;
  channel: string;
  strength: string;
  weakness: string;
  differentiation_score: number;
  source_urls: string[];
}

export interface Strategy {
  matrix: MatrixRow[];
  market_gap: string;
  gap_evidence?: string[];
  recommended_offer: string;
  recommended_price: string;
  recommended_price_value?: number | null;
  positioning_rationale: string;
  risks?: string[];
}

export interface RunSummary {
  id: string;
  status: RunStatus;
  business_idea: string;
  city: string;
  target_customer: string;
  created_at: string;
  finished_at?: string | null;
  duration_seconds?: number | null;
  competitor_count: number;
  market_gap?: string | null;
}

export interface Source {
  number: number;
  title: string;
  url: string;
}

export interface RunDetail extends RunSummary {
  known_competitors: string[];
  started_at?: string | null;
  error?: string | null;
  competitors?: { competitors: Competitor[] } | null;
  reviews?: unknown;
  strategy?: Strategy | null;
  report_markdown?: string | null;
  sources: Source[];
  llm_model?: string | null;
  total_tokens?: number | null;
  search_calls?: number | null;
}

export interface RunInput {
  business_idea: string;
  city: string;
  target_customer: string;
  known_competitors: string[];
  turnstile_token?: string | null;
  /** Skip reuse of a recent identical report and start new research. */
  fresh?: boolean;
}

export type AgentKey = "market_researcher" | "review_analyst" | "strategy_analyst" | "report_writer";

export type RunEventType =
  | "agent_started"
  | "tool_called"
  | "tool_result_summary"
  | "task_completed"
  | "run_completed"
  | "run_failed";

export interface RunEvent {
  type: RunEventType;
  run_id: string;
  ts: number;
  seq?: number;
  agent?: AgentKey | "research_director" | "unknown";
  tool?: string;
  message?: string;
  level?: "warning";
  data?: Record<string, unknown>;
  duration_seconds?: number;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public fieldErrors: { field: string; message: string }[] = [],
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      cache: "no-store",
    });
  } catch {
    throw new ApiError("Can't reach LaunchScout right now. Check your connection and try again.", 0);
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    let errors: { field: string; message: string }[] = [];
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : detail;
      errors = Array.isArray(body.errors) ? body.errors : [];
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(detail, res.status, errors);
  }
  return (await res.json()) as T;
}

export const api = {
  createRun: (input: RunInput) =>
    request<{ run_id: string; status: RunStatus; events_url: string; reused?: boolean }>("/api/runs", {
      method: "POST",
      body: JSON.stringify(input),
    }),
  getRun: (id: string) => request<RunDetail>(`/api/runs/${encodeURIComponent(id)}`),
  listRuns: (limit = 24) => request<{ items: RunSummary[] }>(`/api/runs?limit=${limit}`),
  eventsUrl: (id: string, after?: number) =>
    `${API_BASE}/api/runs/${encodeURIComponent(id)}/events${after ? `?after=${after}` : ""}`,
  reportUrl: (id: string, ext: "md" | "pdf") => `${API_BASE}/api/runs/${encodeURIComponent(id)}/report.${ext}`,
};
