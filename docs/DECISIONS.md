# Architecture & Engineering Decisions

A running log of decisions made while building LaunchScout. Newest at the bottom of each section.

## Repository
- **Monorepo** at repository root (`frontend/`, `backend/`, `deploy/`, `.github/`). The brief's `launchscout/` folder is the repo root itself.
- Default branch `main`; conventional commits.

## Backend
- **Python 3.12**, dependency management via `pip` + `pyproject.toml` (uv not installed on the dev machine; pip keeps Docker builds simple).
- **CrewAI 1.15.x** with `@CrewBase`, `config/agents.yaml`, `config/tasks.yaml` — matches the CrewAI project convention from the spec.
- LLM chosen purely from `LLM_MODEL` env (LiteLLM string). No provider is hard-coded.
- Structured outputs: `CompetitorList`, `ReviewInsights`, `StrategyMatrix` (Pydantic v2) on tasks 1–3, each competitor with `source_urls: list[HttpUrl]`.
- Task-1 guardrail: function guardrail that parses the pydantic output and rejects < 3 competitors / missing price / missing source; `guardrail_max_retries=2`.
- "Not publicly listed" is an accepted price value, provided a source URL of the checked page is present (data-integrity rule).
- Post-run validator in `app/services/report_validator.py` — independent of CrewAI so it is unit-testable and also used by the worker to fail the job.
- Tool failures (Serper rate limit, scrape blocked) are caught in thin tool wrappers that return an error string to the agent instead of raising, so the agent continues with other sources.
- Agents are mapped to progress events by agent id first, then by the role-template prefix (roles contain `{city}`, which CrewAI interpolates at kickoff).
- `guardrails.py` deliberately omits `from __future__ import annotations`: CrewAI inspects the guardrail's return annotation at runtime and requires a real `tuple[bool, Any]`.
- The runner always (over)writes `outputs/<run_id>/report.md` from the final task output after kickoff. The Report Writer still saves it with `FileWriterTool` per spec; the runner's copy guarantees the saved file is byte-identical to what was validated.
- User inputs strip `{` `}` (CrewAI interpolation syntax), HTML tags and control characters before reaching prompts.
- Offline tests use a scripted `BaseLLM` subclass, so the real CrewAI pipeline (guardrail retry, `output_pydantic` conversion, event bus) is exercised without network or keys.
- mypy runs in strict mode with `disallow_untyped_decorators = false`, because CrewAI's `@agent`/`@task`/`event_bus.on` decorators are untyped.
- Installed extras: `crewai[anthropic,litellm]`. Anthropic/OpenAI/Gemini prefixes use CrewAI's native SDKs, and every other `LLM_MODEL` prefix falls back to LiteLLM.

## Job execution (planned for Phase 3)
- CrewAI's event bus is process-global. The worker therefore runs each crew in its own **subprocess**, which isolates progress events per run and lets `RUN_TIMEOUT_SECONDS` be enforced by killing the process.
