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

export const agentByKey = (key?: string) => AGENTS.find((a) => a.key === key);
