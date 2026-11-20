import type { AgentKey } from "./api";

export interface AgentMeta {
  key: AgentKey;
  name: string;
  initials: string;
  role: string;
  tools: string[];
}

export const AGENTS: AgentMeta[] = [
  {
    key: "market_researcher",
    name: "Market Researcher",
    initials: "MR",
    role: "Finds 3–5 real competitors in your city, with prices, offers and channels.",
    tools: ["Google search", "Web reader"],
  },
  {
    key: "review_analyst",
    name: "Review Analyst",
    initials: "RA",
    role: "Reads Google, Zomato, Swiggy, Justdial and Instagram reviews for each competitor.",
    tools: ["Google search", "Web reader"],
  },
  {
    key: "strategy_analyst",
    name: "Strategy Analyst",
    initials: "SA",
    role: "Builds the comparison matrix, finds the gap, and sets your price and positioning.",
    tools: ["Reasoning only"],
  },
  {
    key: "report_writer",
    name: "Report Writer",
    initials: "RW",
    role: "Writes the six-section report with a 30-day plan and numbered sources.",
    tools: ["File writer"],
  },
];

/** Manager in PROCESS_MODE=hierarchical: it briefs and checks the four specialists, so it
 *  appears in the activity feed but is not a step of the timeline. */
export const MANAGER = {
  key: "research_director",
  name: "Research Director",
  initials: "RD",
  role: "Assigns each step to its specialist and checks the work before passing it on.",
  tools: ["Delegation"],
} as const;

export const agentByKey = (key?: string) =>
  key === MANAGER.key ? MANAGER : AGENTS.find((a) => a.key === key);
