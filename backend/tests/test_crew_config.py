"""Acceptance: four distinct agents, exact expected_outputs, guardrail, sequential process."""

from typing import Any

from crewai import Process

from app.crew.crew import LaunchScoutCrew
from app.crew.guardrails import competitor_list_guardrail
from app.crew.schemas import CompetitorList, ReviewInsights, StrategyMatrix
from tests.fakes import ScriptedLLM

HEADINGS = (
    "## 1. Key Competitors",
    "## 2. What Customers Complain About",
    "## 3. Market Gap",
    "## 4. Recommended Positioning",
    "## 5. 30-Day Launch Plan",
    "## 6. Sources",
)


def _crew(settings: Any) -> Any:
    return LaunchScoutCrew(settings=settings, llm=ScriptedLLM()).crew()


def test_four_agents_with_distinct_role_goal_backstory(settings: Any) -> None:
    crew = _crew(settings)
    assert len(crew.agents) == 4
    for attr in ("role", "goal", "backstory"):
        values = [getattr(a, attr).strip() for a in crew.agents]
        assert len(set(values)) == 4, f"agents share a {attr}"
        assert all(len(v) > 20 for v in values)


def test_sequential_by_default(settings: Any) -> None:
    assert _crew(settings).process == Process.sequential


def test_tools_per_agent(settings: Any) -> None:
    crew = _crew(settings)
    names = [sorted(type(t).__name__ for t in a.tools) for a in crew.agents]
    assert names[0] == ["LocalPriceTool", "SafeScrapeWebsiteTool", "SafeSerperDevTool"]
    assert names[1] == ["SafeScrapeWebsiteTool", "SafeSerperDevTool"]
    assert names[2] == []
    assert names[3] == ["FileWriterTool"]


def test_places_lookup_can_be_turned_off(settings: Any) -> None:
    settings.places_lookup_enabled = False
    crew = _crew(settings)
    assert sorted(type(t).__name__ for t in crew.agents[0].tools) == [
        "SafeScrapeWebsiteTool",
        "SafeSerperDevTool",
    ]


def test_every_task_has_specific_expected_output(settings: Any) -> None:
    crew = _crew(settings)
    assert len(crew.tasks) == 4
    for t in crew.tasks:
        assert len(t.expected_output) > 150
    final = crew.tasks[3].expected_output
    for heading in HEADINGS:
        assert heading in final


def test_structured_outputs_and_guardrail(settings: Any) -> None:
    t1, t2, t3, _ = _crew(settings).tasks
    assert t1.output_pydantic is CompetitorList
    assert t2.output_pydantic is ReviewInsights
    assert t3.output_pydantic is StrategyMatrix
    assert t1.guardrail is competitor_list_guardrail
    assert t1.guardrail_max_retries == 2


def test_context_chain(settings: Any) -> None:
    t1, t2, t3, t4 = _crew(settings).tasks
    assert t2.context == [t1]
    assert t3.context == [t1, t2]
    assert t4.context == [t1, t2, t3]


def test_hierarchical_flag(settings: Any) -> None:
    settings.process_mode = "hierarchical"
    assert _crew(settings).process == Process.hierarchical
