"""Translate CrewAI event-bus events into LaunchScout's typed progress events.

Event types emitted (spec): ``agent_started``, ``tool_called``,
``tool_result_summary``, ``task_completed``, ``run_completed``, ``run_failed``.
Each event is a plain JSON-serialisable dict so it can go straight to Redis pub/sub.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from typing import Any
from urllib.parse import urlparse

from app.crew.schemas import CompetitorList, ReviewInsights, StrategyMatrix

Emit = Callable[[dict[str, Any]], None]

AGENT_KEYS = ["market_researcher", "review_analyst", "strategy_analyst", "report_writer"]
AGENT_LABELS = {
    "market_researcher": "Market Researcher",
    "review_analyst": "Review Analyst",
    "strategy_analyst": "Strategy Analyst",
    "report_writer": "Report Writer",
}
_URL_RE = re.compile(r"https?://[^\s\"'<>)\]]+")


def make_event(event_type: str, run_id: str, **fields: Any) -> dict[str, Any]:
    return {"type": event_type, "run_id": run_id, "ts": time.time(), **fields}


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.removeprefix("www.") or url
    except ValueError:
        return url


def _args(tool_args: Any) -> dict[str, Any]:
    if isinstance(tool_args, dict):
        return tool_args
    if isinstance(tool_args, str):
        try:
            parsed = json.loads(tool_args)
            return parsed if isinstance(parsed, dict) else {"input": tool_args}
        except json.JSONDecodeError:
            return {"input": tool_args}
    return {}


def describe_tool_call(tool_name: str, tool_args: Any) -> str:
    a = _args(tool_args)
    name = tool_name.lower()
    if "search" in name or "serper" in name:
        return f"Searching: {a.get('search_query') or a.get('query') or a.get('input', '')}".strip()
    if "scrape" in name or "website" in name:
        url = str(a.get("website_url") or a.get("url") or a.get("input", ""))
        return f"Reading: {url}" if url else "Reading a web page"
    if "file" in name and "writ" in name:
        return f"Saving {a.get('filename', 'report.md')}"
    return f"Using {tool_name}"


def summarise_tool_result(tool_name: str, output: Any, tool_args: Any = None) -> str:
    text = output if isinstance(output, str) else json.dumps(output, default=str)[:20000]
    name = tool_name.lower()
    if text.startswith(("SEARCH FAILED", "SCRAPE FAILED")):
        return text.split(".")[0]
    if "search" in name or "serper" in name:
        urls = list(dict.fromkeys(_URL_RE.findall(text)))
        domains = list(dict.fromkeys(_domain(u) for u in urls))
        if not urls:
            return "No results"
        return f"{len(urls)} results · " + ", ".join(domains[:4])
    if "scrape" in name or "website" in name:
        url = str(_args(tool_args).get("website_url") or "")
        size = f"{len(text) / 1000:.0f}k characters" if len(text) >= 1000 else f"{len(text)} characters"
        return f"Read {_domain(url)} · {size}" if url else f"Read {size}"
    if "file" in name and "writ" in name:
        return "Report saved" if not text.lower().startswith(("error", "an error")) else text[:160]
    return text[:140]


_MODEL_FOR_AGENT: dict[str, type[Any]] = {
    "market_researcher": CompetitorList,
    "review_analyst": ReviewInsights,
    "strategy_analyst": StrategyMatrix,
}


def summarise_task_output(agent_key: str, output: Any) -> tuple[str, dict[str, Any]]:
    """Human summary + small structured payload for a finished task."""
    pyd = getattr(output, "pydantic", None)
    if pyd is None and agent_key in _MODEL_FOR_AGENT:
        raw = str(getattr(output, "raw", "") or "")
        try:
            pyd = _MODEL_FOR_AGENT[agent_key].model_validate_json(raw[raw.find("{") : raw.rfind("}") + 1])
        except ValueError:
            pyd = None
    if isinstance(pyd, CompetitorList):
        names = [c.name for c in pyd.competitors]
        return f"Found {len(names)} competitors: {', '.join(names)}", {"competitors": names}
    if isinstance(pyd, ReviewInsights):
        n_c = sum(len(r.complaints) for r in pyd.reviews)
        return (
            f"Analysed reviews for {len(pyd.reviews)} competitors · {n_c} complaints · "
            f"{len(pyd.common_pain_points)} recurring pain points",
            {"pain_points": [p.pain_point for p in pyd.common_pain_points]},
        )
    if isinstance(pyd, StrategyMatrix):
        return f"Market gap: {pyd.market_gap}", {"recommended_price": pyd.recommended_price}
    raw = str(getattr(output, "raw", output) or "")
    if agent_key == "report_writer":
        return f"Report written · {len(raw.split()):,} words", {}
    return raw[:160], {}


@contextmanager
def crew_progress(
    run_id: str, emit: Emit, role_to_key: dict[str, str], id_to_key: dict[str, str] | None = None
) -> Iterator[None]:
    """Register scoped CrewAI event handlers that forward typed progress events to ``emit``."""
    from crewai.events import crewai_event_bus
    from crewai.events.types.agent_events import AgentExecutionStartedEvent
    from crewai.events.types.task_events import TaskCompletedEvent
    from crewai.events.types.tool_usage_events import (
        ToolUsageErrorEvent,
        ToolUsageFinishedEvent,
        ToolUsageStartedEvent,
    )

    state: dict[str, str] = {"agent": ""}

    ids = id_to_key or {}
    # Roles contain placeholders like "{city}" that CrewAI fills in at kickoff, so match on the
    # literal prefix before the first placeholder as well as on the exact role.
    prefixes = {r.split("{", 1)[0].strip().lower(): k for r, k in role_to_key.items()}

    def key_for(role: str | None, agent_id: Any = None) -> str:
        if agent_id is not None and str(agent_id) in ids:
            return ids[str(agent_id)]
        if role:
            r = role.strip()
            if r in role_to_key:
                return role_to_key[r]
            for prefix, k in prefixes.items():
                if prefix and r.lower().startswith(prefix):
                    return k
        return state["agent"] or "unknown"

    def safe_emit(event: dict[str, Any]) -> None:
        with suppress(Exception):  # progress must never break the crew
            emit(event)

    with crewai_event_bus.scoped_handlers():

        @crewai_event_bus.on(AgentExecutionStartedEvent)
        def _agent_started(source: Any, event: AgentExecutionStartedEvent) -> None:
            key = key_for(getattr(event.agent, "role", None), getattr(event.agent, "id", None))
            state["agent"] = key
            safe_emit(
                make_event(
                    "agent_started",
                    run_id,
                    agent=key,
                    label=AGENT_LABELS.get(key, key),
                    index=AGENT_KEYS.index(key) if key in AGENT_KEYS else -1,
                    message=f"{AGENT_LABELS.get(key, key)} started",
                )
            )

        @crewai_event_bus.on(ToolUsageStartedEvent)
        def _tool_started(source: Any, event: ToolUsageStartedEvent) -> None:
            key = key_for(event.agent_role, event.agent_id)
            safe_emit(
                make_event(
                    "tool_called",
                    run_id,
                    agent=key,
                    tool=event.tool_name,
                    message=describe_tool_call(event.tool_name, event.tool_args),
                )
            )

        @crewai_event_bus.on(ToolUsageFinishedEvent)
        def _tool_finished(source: Any, event: ToolUsageFinishedEvent) -> None:
            key = key_for(event.agent_role, event.agent_id)
            safe_emit(
                make_event(
                    "tool_result_summary",
                    run_id,
                    agent=key,
                    tool=event.tool_name,
                    message=summarise_tool_result(event.tool_name, event.output, event.tool_args),
                )
            )

        @crewai_event_bus.on(ToolUsageErrorEvent)
        def _tool_error(source: Any, event: ToolUsageErrorEvent) -> None:
            key = key_for(event.agent_role, event.agent_id)
            safe_emit(
                make_event(
                    "tool_result_summary",
                    run_id,
                    agent=key,
                    tool=event.tool_name,
                    level="warning",
                    message=f"{event.tool_name} failed, trying other sources",
                )
            )

        @crewai_event_bus.on(TaskCompletedEvent)
        def _task_completed(source: Any, event: TaskCompletedEvent) -> None:
            task_agent = getattr(event.task, "agent", None)
            role = getattr(task_agent, "role", None) or getattr(event.output, "agent", None)
            key = key_for(role, getattr(task_agent, "id", None))
            message, data = summarise_task_output(key, event.output)
            safe_emit(make_event("task_completed", run_id, agent=key, message=message, data=data))

        yield
