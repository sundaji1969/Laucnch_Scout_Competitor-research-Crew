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
