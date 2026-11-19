"""Full crew kickoff with a scripted LLM: guardrail retry, pydantic outputs, events, file save."""

from typing import Any

import pytest

from app.crew.crew import LaunchScoutCrew
from app.crew.inputs import RunInputs
from app.crew.runner import run_crew
from app.services.report_validator import ReportValidationError
from tests.fakes import COMPETITORS, TOO_FEW, ScriptedLLM

INPUTS = RunInputs(
    business_idea="Healthy millet meal boxes", city="Coimbatore", target_customer="Office workers"
)


def _factory(llm: ScriptedLLM) -> Any:
    return lambda s: LaunchScoutCrew(settings=s, llm=llm).crew()


def test_end_to_end_mocked(settings: Any) -> None:
    events: list[dict[str, Any]] = []
    llm = ScriptedLLM(research_outputs=[TOO_FEW, COMPETITORS])  # guardrail must reject first try
    result = run_crew(
        INPUTS, run_id="test1", emit=events.append, settings=settings, crew_factory=_factory(llm)
    )

    report = (settings.outputs_path / "test1" / "report.md").read_text("utf-8")
    assert "## 6. Sources" in report
    assert len(result.structured["competitors"]["competitors"]) == 3
    assert result.structured["strategy"]["recommended_price"] == "₹169 per meal"

    types = [e["type"] for e in events]
    started = [e["agent"] for e in events if e["type"] == "agent_started"]
    assert started[0] == "market_researcher"
    assert started[-1] == "report_writer"
    assert set(started) == {"market_researcher", "review_analyst", "strategy_analyst", "report_writer"}
    assert types.count("task_completed") == 4
    assert types[-1] == "run_completed"
    first_done = next(e for e in events if e["type"] == "task_completed")
    assert first_done["message"].startswith("Found 3 competitors")


def test_invalid_report_fails_run(settings: Any) -> None:
    events: list[dict[str, Any]] = []
    llm = ScriptedLLM(report="# Report\n\n## 1. Key Competitors\nnothing here")
    with pytest.raises(ReportValidationError):
        run_crew(INPUTS, run_id="test2", emit=events.append, settings=settings, crew_factory=_factory(llm))
    assert events[-1]["type"] == "run_failed"
    assert "Missing section" in events[-1]["message"]
