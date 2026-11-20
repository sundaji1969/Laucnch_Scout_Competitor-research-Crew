"""The LaunchScout crew: four agents, four tasks, sequential process."""

from __future__ import annotations

from typing import Any

from crewai import LLM, Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import FileWriterTool

from app.config import Settings, get_settings
from app.crew import delegation
from app.crew.guardrails import (
    competitor_list_guardrail,
    review_insights_guardrail,
    set_price_lookup,
    strategy_from_specialist_guardrail,
)
from app.crew.schemas import CompetitorList, ReviewInsights, StrategyMatrix
from app.crew.tools.safe_tools import places_tool, scrape_tool, search_tool


def build_llm(settings: Settings, model: str | None = None) -> LLM:
    """LLM is chosen purely from env (provider/model strings). Never hard-coded."""
    return LLM(model=model or settings.llm_model, temperature=settings.llm_temperature)


class TrackedAgent(Agent):  # type: ignore[misc]
    """An Agent that records each finished execution in ``delegation`` under its key.

    Delegation calls the coworker's ``execute_task`` directly, so this sees the specialist's
    work whether the crew runs it (sequential) or the manager delegates to it (hierarchical).
    """

    tracking_key: str = ""

    def execute_task(self, task: Any, context: str | None = None, tools: Any = None) -> Any:
        result = super().execute_task(task, context, tools)
        delegation.record(self.tracking_key, result)
        return result


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
        # The two tool-using research agents can run on a cheaper model (LLM_MODEL_RESEARCH);
        # strategy and writing stay on LLM_MODEL, where reasoning and prose quality show.
        research_model = self.settings.llm_model_research.strip()
        if llm is not None or not research_model or research_model == self.settings.llm_model:
            self.research_llm = self.llm
        else:
            self.research_llm = build_llm(self.settings, research_model)

    def _research_tools(self) -> list[Any]:
        s = self.settings
        return [
            search_tool(
                country=s.serper_country,
                locale=s.serper_locale,
                n_results=s.serper_results,
                cache_ttl=s.search_cache_ttl_seconds,
                redis_url=s.redis_url,
            ),
            scrape_tool(max_chars=s.scrape_max_chars),
        ]

    def _price_tools(self) -> list[Any]:
        """Google Maps price ranges for local businesses (Swiggy/Zomato menus aren't readable).

        The same lookup backs the task-1 guardrail's fill-in for competitors the agent left
        unpriced (see guardrails.fill_prices_from_maps).
        """
        s = self.settings
        if not s.places_lookup_enabled:
            set_price_lookup(None)
            return []
        tool = places_tool(
            api_key=s.serper_api_key,
            country=s.serper_country,
            locale=s.serper_locale,
            cache_ttl=s.search_cache_ttl_seconds,
            redis_url=s.redis_url,
        )
        set_price_lookup(tool.lookup)
        return [tool]

    # ------------------------------------------------------------------ agents
    @agent
    def market_researcher(self) -> Agent:
        return TrackedAgent(
            tracking_key="market_researcher",
            config=self.agents_config["market_researcher"],  # type: ignore[index]
            tools=self._research_tools() + self._price_tools(),
            llm=self.research_llm,
            allow_delegation=False,
            max_iter=self.settings.agent_max_iter,
            verbose=self.settings.crew_verbose,
        )

    @agent
    def review_analyst(self) -> Agent:
        return TrackedAgent(
            tracking_key="review_analyst",
            config=self.agents_config["review_analyst"],  # type: ignore[index]
            tools=self._research_tools(),
            llm=self.research_llm,
            allow_delegation=False,
            max_iter=self.settings.agent_max_iter,
            verbose=self.settings.crew_verbose,
        )

    @agent
    def strategy_analyst(self) -> Agent:
        return TrackedAgent(
            tracking_key="strategy_analyst",
            config=self.agents_config["strategy_analyst"],  # type: ignore[index]
            tools=[],
            llm=self.llm,
            allow_delegation=False,
            verbose=self.settings.crew_verbose,
        )

    @agent
    def report_writer(self) -> Agent:
        return TrackedAgent(
            tracking_key="report_writer",
            config=self.agents_config["report_writer"],  # type: ignore[index]
            # sandboxed to the outputs directory: the agent cannot write anywhere else
            tools=[FileWriterTool(base_dir=str(self.settings.outputs_path.resolve()))],
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
            guardrail=review_insights_guardrail,
            guardrail_max_retries=self.settings.guardrail_max_retries,
        )

    @task
    def strategy_task(self) -> Task:
        extra: dict[str, Any] = {}
        if self._hierarchical():
            # The Strategy Analyst has no tools, so nothing else makes the director delegate
            # this step: require that the analyst ran, and use the analyst's own answer.
            extra = {
                "guardrail": strategy_from_specialist_guardrail,
                "guardrail_max_retries": self.settings.guardrail_max_retries,
            }
        return Task(
            config=self.tasks_config["strategy_task"],  # type: ignore[index]
            output_pydantic=StrategyMatrix,
            **extra,
        )

    @task
    def report_task(self) -> Task:
        return Task(config=self.tasks_config["report_task"])  # type: ignore[index]

    # ----------------------------------------------------------------- manager
    def research_director(self) -> Agent:
        """Manager for PROCESS_MODE=hierarchical. Deliberately not an @agent: CrewAI requires the
        manager to stay out of the agents list, and to have no tools of its own (it is given
        delegation tools that only reach the specialist each task is assigned to)."""
        return Agent(
            config=self.agents_config["research_director"],  # type: ignore[index]
            tools=[],
            llm=self.llm,
            allow_delegation=True,
            verbose=self.settings.crew_verbose,
        )

    # -------------------------------------------------------------------- crew
    def _hierarchical(self) -> bool:
        return self.settings.process_mode.lower() == "hierarchical"

    @crew
    def crew(self) -> Crew:
        delegation.reset()  # one crew per process: start this run's record of who did what
        hierarchical = self._hierarchical()
        kwargs: dict[str, Any] = {}
        if hierarchical:  # stretch goal, behind PROCESS_MODE flag
            # Tasks keep their specialist, so the director can only delegate each task to
            # its owner; guardrails and output models still apply to what it hands back.
            kwargs["manager_agent"] = self.research_director()
        crew = Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.hierarchical if hierarchical else Process.sequential,
            verbose=self.settings.crew_verbose,
            **kwargs,
        )
        if hierarchical:
            # Task copies its agent's tools onto itself (Task.check_tools, which re-runs on
            # assignment and when the Crew validates its tasks), and the manager executes each
            # task with the task's tools, so the director searched and scraped itself instead
            # of delegating (seen in the first hierarchical run). Empty the lists beneath the
            # validator once the crew is built: the director keeps only its delegation tools,
            # and specialists still use their own tools when a task is delegated to them.
            for t in crew.tasks:
                object.__setattr__(t, "tools", [])
        return crew
