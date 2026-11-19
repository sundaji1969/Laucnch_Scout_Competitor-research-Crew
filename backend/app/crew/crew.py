"""The LaunchScout crew: four agents, four tasks, sequential process."""

from __future__ import annotations

from typing import Any

from crewai import LLM, Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import FileWriterTool

from app.config import Settings, get_settings
from app.crew.guardrails import competitor_list_guardrail
from app.crew.schemas import CompetitorList, ReviewInsights, StrategyMatrix
from app.crew.tools.safe_tools import scrape_tool, search_tool


def build_llm(settings: Settings) -> LLM:
    """LLM is chosen purely from LLM_MODEL (provider/model). Never hard-coded."""
    return LLM(model=settings.llm_model, temperature=settings.llm_temperature)


@CrewBase
class LaunchScoutCrew:
    """Competitor research crew."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    agents: list[Agent]
    tasks: list[Task]

    def __init__(self, settings: Settings | None = None, llm: Any | None = None) -> None:
        self.settings = settings or get_settings()
        self.llm = llm if llm is not None else build_llm(self.settings)

    def _research_tools(self) -> list[Any]:
        return [
            search_tool(country=self.settings.serper_country, locale=self.settings.serper_locale),
            scrape_tool(),
        ]

    # ------------------------------------------------------------------ agents
    @agent
    def market_researcher(self) -> Agent:
        return Agent(
            config=self.agents_config["market_researcher"],  # type: ignore[index]
            tools=self._research_tools(),
            llm=self.llm,
            allow_delegation=False,
            max_iter=25,
            verbose=self.settings.crew_verbose,
        )

    @agent
    def review_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["review_analyst"],  # type: ignore[index]
            tools=self._research_tools(),
            llm=self.llm,
            allow_delegation=False,
            max_iter=25,
            verbose=self.settings.crew_verbose,
        )

    @agent
    def strategy_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["strategy_analyst"],  # type: ignore[index]
            tools=[],
            llm=self.llm,
            allow_delegation=False,
            verbose=self.settings.crew_verbose,
        )

    @agent
    def report_writer(self) -> Agent:
        return Agent(
            config=self.agents_config["report_writer"],  # type: ignore[index]
            tools=[FileWriterTool()],
            llm=self.llm,
            allow_delegation=False,
            verbose=self.settings.crew_verbose,
        )

    # ------------------------------------------------------------------- tasks
    @task
    def market_research_task(self) -> Task:
        return Task(
            config=self.tasks_config["market_research_task"],  # type: ignore[index]
            output_pydantic=CompetitorList,
            guardrail=competitor_list_guardrail,
            guardrail_max_retries=self.settings.guardrail_max_retries,
        )

    @task
    def review_analysis_task(self) -> Task:
        return Task(
            config=self.tasks_config["review_analysis_task"],  # type: ignore[index]
            output_pydantic=ReviewInsights,
        )

    @task
    def strategy_task(self) -> Task:
        return Task(
            config=self.tasks_config["strategy_task"],  # type: ignore[index]
            output_pydantic=StrategyMatrix,
        )

    @task
    def report_task(self) -> Task:
        return Task(config=self.tasks_config["report_task"])  # type: ignore[index]

    # -------------------------------------------------------------------- crew
    @crew
    def crew(self) -> Crew:
        hierarchical = self.settings.process_mode.lower() == "hierarchical"
        kwargs: dict[str, Any] = {}
        if hierarchical:  # stretch goal, behind PROCESS_MODE flag
            kwargs["manager_llm"] = self.llm
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.hierarchical if hierarchical else Process.sequential,
            verbose=self.settings.crew_verbose,
            **kwargs,
        )
